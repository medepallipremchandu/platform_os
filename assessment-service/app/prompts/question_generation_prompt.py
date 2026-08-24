SYSTEM_PROMPT = """You are an expert technical interviewer. You design interview questions that \
probe specific evaluation rubrics for a given skill, for an interview-assessment platform. \
You must respond with ONLY a single valid JSON object, no prose, no markdown fences."""

_COMMON_HEADER = """Generate {num_questions} {question_type} interview question(s) for the skill "{skill_name}".

Skill description: {skill_description}

Available rubrics for this skill (use these exact names, do not invent new ones):
{rubrics_block}
"""

_RUBRIC_MAP_SPEC = """      "rubric_maps": [
        {{
          "rubric_name": string (must exactly match one of the available rubric names above),
          "weight_percentage": number (0-100, how much of this question's grade this rubric represents),
          "evaluation_criteria": string (concrete, specific guidance on what to look for to satisfy \
this rubric for this exact question)
        }}
      ]"""

_RUBRIC_MAP_RULES = """- Each question may map to one or more of the available rubrics.
- Within a single question, the weight_percentage values across its rubric_maps must sum to 100 or less \
(never more than 100)."""

_TYPE_SPECS = {
    "descriptive": {
        "shape": """{{
      "question_text": string (an open-ended interview question, self-contained),
      "difficulty": string (one of "easy", "medium", "hard"),
{rubric_map_spec}
    }}""",
        "rules": f"""{_RUBRIC_MAP_RULES}
- Prefer questions that combine 1-3 rubrics deeply rather than shallow, generic questions.
- evaluation_criteria must be specific enough that a grader with no other context could score a \
free-text answer against it.""",
    },
    "mcq": {
        "shape": """{{
      "question_text": string (a single-answer multiple-choice question, self-contained),
      "difficulty": string (one of "easy", "medium", "hard"),
      "options": [string, ...] (exactly 4 options),
      "correct_option_index": integer (0-based index into "options" of the single correct answer),
{rubric_map_spec}
    }}""",
        "rules": f"""{_RUBRIC_MAP_RULES}
- Exactly one option must be correct; the other 3 must be plausible but clearly wrong to an expert.
- evaluation_criteria should describe why the correct option is correct (used for feedback display).""",
    },
    "coding": {
        "shape": """{{
      "question_text": string (a self-contained coding problem statement, include input/output format),
      "difficulty": string (one of "easy", "medium", "hard"),
      "language": string (one of "python", "javascript"),
      "starter_code": string (a minimal function/program skeleton in that language reading from stdin \
and writing to stdout),
      "test_cases": [
        {{
          "input": string (exact stdin the program will receive, empty string if none),
          "expected_output": string (exact expected stdout, trimmed),
          "is_hidden": boolean (true for held-out cases not shown to the candidate)
        }}
      ] (produce 4-6 test cases: at least 2 visible (is_hidden=false) covering the basic case and one \
edge case, and the rest hidden covering edge cases and larger inputs),
{rubric_map_spec}
    }}""",
        "rules": f"""{_RUBRIC_MAP_RULES}
- The program must read all input from stdin and write only the answer to stdout (no prompts/labels).
- test_cases must be objectively verifiable by exact string match on trimmed stdout - avoid floating \
point output unless formatted to a fixed number of decimals.
- evaluation_criteria should describe the algorithmic approach/complexity expected, since correctness \
is already verified by the test cases.""",
    },
}


def build_question_generation_prompt(
    skill_name: str,
    skill_description: str,
    rubrics: list[dict],
    num_questions: int,
    question_type: str = "descriptive",
) -> tuple[str, str]:
    spec = _TYPE_SPECS[question_type]
    rubrics_block = "\n".join(
        f'- "{r["name"]}" (skill weight {r["weight_percentage"]}%): {r["description"]}' for r in rubrics
    )
    question_shape = spec["shape"].format(rubric_map_spec=_RUBRIC_MAP_SPEC)

    user_prompt = (
        _COMMON_HEADER.format(
            num_questions=num_questions,
            question_type=question_type,
            skill_name=skill_name,
            skill_description=skill_description,
            rubrics_block=rubrics_block,
        )
        + f"""
Return a JSON object with exactly this shape:
{{
  "questions": [
{question_shape}
  ]
}}

Rules:
{spec["rules"]}
"""
    )
    return SYSTEM_PROMPT, user_prompt
