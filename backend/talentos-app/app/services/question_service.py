import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import InvalidStateError
from app.models.jd_analysis import Skill
from app.models.question import QUESTION_TYPES, Question, QuestionRubricMap, QuestionTestCase
from app.schemas.llm_outputs import LLMQuestion, LLMQuestionGeneration
from app.services import agent_client, code_execution_service
from app.services.code_execution_service import TestCaseExecutionResult

logger = logging.getLogger("app.services.question")

_AGENT_NAME_BY_TYPE = {
    "descriptive": "QUESTION_GEN_DESCRIPTIVE_AGENT",
    "mcq": "QUESTION_GEN_MCQ_AGENT",
    "coding": "QUESTION_GEN_CODING_AGENT",
}


def _scale_down_if_over_100(question: LLMQuestion) -> LLMQuestion:
    total = sum(m.weight_percentage for m in question.rubric_maps)
    if total > 100:
        for m in question.rubric_maps:
            m.weight_percentage = round(m.weight_percentage * 100 / total, 2)
    return question


async def generate_questions(
    db: Session, skill: Skill, num_questions: int, question_type: str = "descriptive"
) -> list[Question]:
    if question_type not in QUESTION_TYPES:
        raise InvalidStateError(f"Unknown question_type '{question_type}'. Must be one of {QUESTION_TYPES}")
    if not skill.rubrics:
        raise InvalidStateError(f"Skill '{skill.name}' has no rubrics to generate questions from")

    rubrics_by_name = {r.name.strip().lower(): r for r in skill.rubrics}
    rubrics_block = "\n".join(
        f'- "{r.name}" (skill weight {r.weight_percentage}%): {r.description}' for r in skill.rubrics
    )

    agent_name = _AGENT_NAME_BY_TYPE[question_type]
    variables = {
        "num_questions": str(num_questions),
        "skill_name": skill.name,
        "skill_description": skill.description or "",
        "rubrics_block": rubrics_block,
    }
    raw_output = await agent_client.invoke(agent_name, variables)
    generation = LLMQuestionGeneration.model_validate(raw_output)

    questions: list[Question] = []
    for llm_question in generation.questions:
        llm_question = _scale_down_if_over_100(llm_question)
        question = Question(
            skill_id=skill.id,
            question_type=question_type,
            question_text=llm_question.question_text,
            difficulty=llm_question.difficulty,
            options=llm_question.options,
            correct_option_index=llm_question.correct_option_index,
            language=llm_question.language,
            starter_code=llm_question.starter_code,
        )

        if question_type == "coding":
            for tc in llm_question.test_cases or []:
                question.test_cases.append(
                    QuestionTestCase(input=tc.input, expected_output=tc.expected_output, is_hidden=tc.is_hidden)
                )
            if not question.test_cases:
                logger.warning("Discarding coding question with no test cases: %s", llm_question.question_text)
                continue

        for llm_map in llm_question.rubric_maps:
            rubric = rubrics_by_name.get(llm_map.rubric_name.strip().lower())
            if rubric is None:
                logger.warning(
                    "Skipping unmatched rubric name '%s' returned for skill '%s'",
                    llm_map.rubric_name,
                    skill.name,
                )
                continue
            question.rubric_maps.append(
                QuestionRubricMap(
                    rubric_id=rubric.id,
                    weight_percentage=llm_map.weight_percentage,
                    evaluation_criteria=llm_map.evaluation_criteria,
                )
            )

        if question.rubric_maps:
            questions.append(question)
        else:
            logger.warning("Discarding question with no matched rubrics: %s", llm_question.question_text)

    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)
    logger.info("Generated %d %s question(s) for skill %s", len(questions), question_type, skill.id)
    return questions


def run_candidate_code_dry(question: Question, code: str, scope: str) -> list[TestCaseExecutionResult]:
    """Executes code against visible test cases only, without persisting anything - backs the
    "Run" (scope=sample: first visible case) and "Run all testcases" (scope=visible: all
    visible cases) buttons. Hidden test cases are never run here; they're reserved for the
    real, persisted evaluation on final submit."""
    if question.question_type != "coding":
        raise InvalidStateError("Only coding questions can be run")
    if not question.language:
        raise InvalidStateError(f"Coding question {question.id} has no language configured")

    visible_cases = [tc for tc in question.test_cases if not tc.is_hidden]
    if not visible_cases:
        raise InvalidStateError("This question has no visible test cases to run against")
    cases_to_run = visible_cases[:1] if scope == "sample" else visible_cases

    settings = get_settings()
    return code_execution_service.run_test_cases(
        language=question.language,
        code=code,
        test_cases=cases_to_run,
        timeout_seconds=settings.CODE_EXECUTION_TIMEOUT_SECONDS,
        max_output_chars=settings.CODE_EXECUTION_MAX_OUTPUT_CHARS,
    )
