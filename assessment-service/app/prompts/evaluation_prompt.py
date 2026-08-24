SYSTEM_PROMPT = """You are an expert, impartial technical interview grader for an interview-assessment \
platform. You score a candidate's answer against specific rubrics and evaluation criteria. \
You must respond with ONLY a single valid JSON object, no prose, no markdown fences."""

_USER_TEMPLATE = """Question asked:
---
{question_text}
---

Candidate's answer:
---
{candidate_answer}
---

Score the answer against each of the following rubrics for this question:
{rubrics_block}

Return a JSON object with exactly this shape:
{{
  "rubric_scores": [
    {{
      "rubric_name": string (must exactly match one of the rubric names above),
      "achieved_score_percentage": number (0-100, how well the answer satisfies this rubric's criteria),
      "feedback": string (specific, concrete feedback justifying the score for this rubric)
    }}
  ],
  "summary": string (2-3 sentence overall assessment of the answer)
}}

Rules:
- Score every rubric listed above, even if the answer did not address it (score it low with feedback saying so).
- achieved_score_percentage reflects how well THIS rubric's criteria were met (0 = not at all, 100 = fully), \
independent of the rubric's weight.
- Be rigorous and specific; do not default to generous scores.
"""


def build_evaluation_prompt(question_text: str, candidate_answer: str, rubric_maps: list[dict]) -> tuple[str, str]:
    rubrics_block = "\n".join(
        f'- "{m["rubric_name"]}" (weight {m["weight_percentage"]}%): {m["evaluation_criteria"]}'
        for m in rubric_maps
    )
    user_prompt = _USER_TEMPLATE.format(
        question_text=question_text, candidate_answer=candidate_answer, rubrics_block=rubrics_block
    )
    return SYSTEM_PROMPT, user_prompt
