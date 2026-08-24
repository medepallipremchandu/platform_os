import logging

from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.core.exceptions import InvalidStateError, NotFoundError
from app.models.evaluation import Evaluation, EvaluationRubricScore, EvaluationTestCaseResult
from app.models.question import Question
from app.prompts.evaluation_prompt import build_evaluation_prompt
from app.schemas.evaluation import EvaluationRequest
from app.schemas.llm_outputs import LLMEvaluation
from app.services import code_execution_service
from app.services.llm.llm_client import LLMClient

logger = logging.getLogger("app.services.evaluation")


def _apply_uniform_score(evaluation: Evaluation, question: Question, achieved_score_percentage: float) -> float:
    """Applies the same achieved_score_percentage to every rubric mapped to the question
    (used for mcq/coding, where correctness is a single objective signal, not per-rubric)."""
    total_weighted = 0.0
    for rubric_map in question.rubric_maps:
        expected_weight = float(rubric_map.weight_percentage)
        weighted_contribution = round(expected_weight * achieved_score_percentage / 100, 2)
        total_weighted += weighted_contribution
        evaluation.rubric_scores.append(
            EvaluationRubricScore(
                question_rubric_map_id=rubric_map.id,
                rubric_id=rubric_map.rubric_id,
                expected_weight_percentage=expected_weight,
                achieved_score_percentage=round(achieved_score_percentage, 2),
                weighted_contribution=weighted_contribution,
                feedback=None,
            )
        )
    return round(total_weighted, 2)


async def _evaluate_descriptive(
    db: Session, question: Question, candidate_answer: str, llm_client: LLMClient
) -> Evaluation:
    rubric_map_payload = [
        {
            "rubric_name": m.rubric.name,
            "weight_percentage": float(m.weight_percentage),
            "evaluation_criteria": m.evaluation_criteria,
        }
        for m in question.rubric_maps
    ]

    system_prompt, user_prompt = build_evaluation_prompt(
        question_text=question.question_text,
        candidate_answer=candidate_answer,
        rubric_maps=rubric_map_payload,
    )
    result: LLMEvaluation = await llm_client.get_json(system_prompt, user_prompt, LLMEvaluation)
    scores_by_rubric_name = {s.rubric_name.strip().lower(): s for s in result.rubric_scores}

    evaluation = Evaluation(
        question_id=question.id, candidate_answer=candidate_answer, summary=result.summary, overall_score_percentage=0
    )

    total_weighted = 0.0
    for rubric_map in question.rubric_maps:
        llm_score = scores_by_rubric_name.get(rubric_map.rubric.name.strip().lower())
        achieved = llm_score.achieved_score_percentage if llm_score else 0.0
        feedback = llm_score.feedback if llm_score else "No score returned for this rubric by the model."

        expected_weight = float(rubric_map.weight_percentage)
        weighted_contribution = round(expected_weight * achieved / 100, 2)
        total_weighted += weighted_contribution

        evaluation.rubric_scores.append(
            EvaluationRubricScore(
                question_rubric_map_id=rubric_map.id,
                rubric_id=rubric_map.rubric_id,
                expected_weight_percentage=expected_weight,
                achieved_score_percentage=round(achieved, 2),
                weighted_contribution=weighted_contribution,
                feedback=feedback,
            )
        )

    evaluation.overall_score_percentage = round(total_weighted, 2)
    return evaluation


def _evaluate_mcq(question: Question, selected_option_index: int) -> Evaluation:
    is_correct = selected_option_index == question.correct_option_index
    achieved = 100.0 if is_correct else 0.0

    selected_text = (
        question.options[selected_option_index]
        if question.options and 0 <= selected_option_index < len(question.options)
        else None
    )
    evaluation = Evaluation(
        question_id=question.id,
        candidate_answer=selected_text,
        selected_option_index=selected_option_index,
        overall_score_percentage=0,
    )
    evaluation.overall_score_percentage = _apply_uniform_score(evaluation, question, achieved)

    correct_text = (
        question.options[question.correct_option_index]
        if question.options and question.correct_option_index is not None
        else "unknown"
    )
    evaluation.summary = (
        "Correct." if is_correct else f"Incorrect. The correct option was: {correct_text}"
    )
    for score in evaluation.rubric_scores:
        score.feedback = evaluation.summary
    return evaluation


def _evaluate_coding(question: Question, candidate_code: str) -> Evaluation:
    if not question.language:
        raise InvalidStateError(f"Coding question {question.id} has no language configured")
    if not question.test_cases:
        raise InvalidStateError(f"Coding question {question.id} has no test cases to evaluate against")

    settings = get_settings()
    results = code_execution_service.run_test_cases(
        language=question.language,
        code=candidate_code,
        test_cases=question.test_cases,
        timeout_seconds=settings.CODE_EXECUTION_TIMEOUT_SECONDS,
        max_output_chars=settings.CODE_EXECUTION_MAX_OUTPUT_CHARS,
    )
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    pass_rate = round(passed_count / total_count * 100, 2) if total_count else 0.0

    evaluation = Evaluation(
        question_id=question.id,
        candidate_answer=candidate_code,
        candidate_code=candidate_code,
        overall_score_percentage=0,
    )
    evaluation.overall_score_percentage = _apply_uniform_score(evaluation, question, pass_rate)
    evaluation.summary = f"{passed_count}/{total_count} test cases passed."

    for result in results:
        evaluation.test_case_results.append(
            EvaluationTestCaseResult(
                question_test_case_id=result.test_case.id,
                input=result.test_case.input,
                expected_output=result.test_case.expected_output,
                actual_output=result.actual_output,
                passed=result.passed,
                is_hidden=result.test_case.is_hidden,
                stderr=result.stderr,
                execution_time_ms=result.execution_time_ms,
            )
        )
    return evaluation


async def evaluate_answer(
    db: Session, question: Question, payload: EvaluationRequest, llm_client: LLMClient
) -> Evaluation:
    if question.question_type == "descriptive":
        if payload.candidate_answer is None:
            raise InvalidStateError("This is a descriptive question - provide candidate_answer")
        evaluation = await _evaluate_descriptive(db, question, payload.candidate_answer, llm_client)
    elif question.question_type == "mcq":
        if payload.selected_option_index is None:
            raise InvalidStateError("This is an mcq question - provide selected_option_index")
        evaluation = _evaluate_mcq(question, payload.selected_option_index)
    elif question.question_type == "coding":
        if payload.candidate_code is None:
            raise InvalidStateError("This is a coding question - provide candidate_code")
        evaluation = _evaluate_coding(question, payload.candidate_code)
    else:
        raise InvalidStateError(f"Unknown question_type '{question.question_type}'")

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    logger.info(
        "Evaluation %s for %s question %s scored %.2f%%",
        evaluation.id,
        question.question_type,
        question.id,
        evaluation.overall_score_percentage,
    )
    return evaluation


async def evaluate_batch(
    db: Session, answers: list[EvaluationRequest], llm_client: LLMClient
) -> tuple[list[Evaluation], float, list[dict]]:
    """Evaluates every answer in one 'final submit' action and rolls the results up into an
    overall score plus a per-skill breakdown - the candidate's score card."""
    evaluations: list[Evaluation] = []
    skill_totals: dict = {}

    for answer in answers:
        question = (
            db.query(Question)
            .options(
                selectinload(Question.rubric_maps),
                selectinload(Question.test_cases),
                selectinload(Question.skill),
            )
            .filter(Question.id == answer.question_id)
            .first()
        )
        if question is None:
            raise NotFoundError(f"Question {answer.question_id} not found")

        evaluation = await evaluate_answer(db, question, answer, llm_client)
        evaluations.append(evaluation)

        bucket = skill_totals.setdefault(
            question.skill_id, {"skill_name": question.skill.name, "scores": []}
        )
        bucket["scores"].append(float(evaluation.overall_score_percentage))

    skill_scores = [
        {
            "skill_id": skill_id,
            "skill_name": info["skill_name"],
            "average_score_percentage": round(sum(info["scores"]) / len(info["scores"]), 2),
            "question_count": len(info["scores"]),
        }
        for skill_id, info in skill_totals.items()
    ]
    overall = (
        round(sum(float(e.overall_score_percentage) for e in evaluations) / len(evaluations), 2)
        if evaluations
        else 0.0
    )
    logger.info("Batch submit: %d answers, overall score %.2f%%", len(evaluations), overall)
    return evaluations, overall, skill_scores
