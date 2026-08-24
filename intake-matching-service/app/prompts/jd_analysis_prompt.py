SYSTEM_PROMPT = """You are an expert technical recruiter and job analyst. You extract structured \
information from job descriptions for an interview-assessment platform. \
You must respond with ONLY a single valid JSON object, no prose, no markdown fences."""

_USER_TEMPLATE = """Analyze the following job description and extract structured context.

Job description:
---
{jd_text}
---

Return a JSON object with exactly this shape:
{{
  "job_title": string,
  "role_context": string (what this role is, where it sits in the org, seniority),
  "job_context_summary": string (2-4 sentence summary of the job and its purpose),
  "responsibilities": [string, ...],
  "qualifications": [string, ...],
  "skills": [
    {{
      "name": string (a single skill, e.g. "Java", "System Design", "Communication"),
      "description": string (why this skill matters for this role),
      "rubrics": [
        {{
          "name": string (a specific evaluation dimension within the skill, e.g. "Concurrency" for Java),
          "description": string (what mastery of this dimension looks like),
          "weight_percentage": number (0-100, how much this rubric contributes to the skill overall)
        }}
      ]
    }}
  ]
}}

Rules:
- Extract every distinct skill implied by the JD (technical and non-technical).
- For each skill, break it into 2-5 rubrics whose weight_percentage values sum to exactly 100.
- Be specific and concrete, do not use generic filler text.
"""


def build_jd_analysis_prompt(jd_text: str) -> tuple[str, str]:
    return SYSTEM_PROMPT, _USER_TEMPLATE.format(jd_text=jd_text)
