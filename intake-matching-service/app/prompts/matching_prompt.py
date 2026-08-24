SYSTEM_PROMPT = """You are an expert technical recruiter evaluating how well a candidate's resume \
matches a job description, benchmarked against current market expectations for similar roles. \
You must respond with ONLY a single valid JSON object, no prose, no markdown fences."""

_USER_TEMPLATE = """Compare this candidate's resume against this job description and produce a \
detailed match analysis.

Job description:
---
Title: {job_title}
Role context: {role_context}
Responsibilities: {responsibilities}
Qualifications: {qualifications}

Required skills (with internal rubric breakdown for context):
{skills_block}
---

Candidate resume:
---
Summary: {resume_summary}
Total experience: {total_experience_years} years
Skills: {resume_skills}
Work history: {work_history}
Education: {education}
Certifications: {certifications}
---

Return a JSON object with exactly this shape:
{{
  "overall_match_percentage": number (0-100, your best overall assessment - you MUST derive this \
from the individual skill_matches below, weighted by jd_weight_percentage),
  "skill_matches": [
    {{
      "skill_name": string (must match one of the required skills above),
      "jd_weight_percentage": number (0-100, relative importance of this skill to the role; \
across all skill_matches these must sum to 100),
      "required_level": string (what level of this skill the role demands, e.g. "expert - 5+ years"),
      "candidate_evidence": string (what in the resume evidences - or fails to evidence - this skill),
      "match_percentage": number (0-100, how well the candidate meets this specific skill's requirement),
      "verdict": string (one of "strong match", "partial match", "gap")
    }}
  ],
  "strengths": [string, ...] (3-5 concrete candidate strengths relative to this specific role),
  "gaps": [string, ...] (concrete gaps or risks relative to this specific role, empty list if none),
  "market_context_commentary": string (2-4 sentences: how this candidate's profile compares to what \
the current market/typical hiring bar looks like for this kind of role - e.g. typical years of \
experience, common skill combinations, competitiveness),
  "recommendation": string (1-2 sentences: a concrete hiring/interview recommendation, e.g. which \
skills to probe deepest in the interview)
}}

Rules:
- Produce one skill_matches entry per required skill listed above - do not skip any, do not invent new ones.
- Be rigorous and specific; do not default to generous scores. A missing skill should score low with \
verdict "gap", not be glossed over.
"""


def build_matching_prompt(
    job_title: str,
    role_context: str,
    responsibilities: list[str],
    qualifications: list[str],
    skills: list[dict],
    resume_summary: str,
    total_experience_years: float | None,
    resume_skills: list[dict],
    work_history: list[dict],
    education: list[dict],
    certifications: list[str],
) -> tuple[str, str]:
    skills_block = "\n".join(
        f'- "{s["name"]}": {s["description"]} (rubrics: '
        + ", ".join(f'{r["name"]} [{r["weight_percentage"]}%]' for r in s["rubrics"])
        + ")"
        for s in skills
    )
    user_prompt = _USER_TEMPLATE.format(
        job_title=job_title,
        role_context=role_context,
        responsibilities="; ".join(responsibilities),
        qualifications="; ".join(qualifications),
        skills_block=skills_block,
        resume_summary=resume_summary,
        total_experience_years=total_experience_years if total_experience_years is not None else "unknown",
        resume_skills=", ".join(
            f'{s["name"]}'
            + (f' ({s["years_experience"]}y)' if s.get("years_experience") else "")
            + (f' [{s["proficiency"]}]' if s.get("proficiency") else "")
            for s in resume_skills
        )
        or "none listed",
        work_history="; ".join(
            f'{w["title"]} at {w["company"]} ({w.get("start_date", "?")} - {w.get("end_date", "?")}): {w["description"]}'
            for w in work_history
        )
        or "none listed",
        education="; ".join(
            f'{e.get("degree", "")} {e.get("field_of_study", "")} - {e["institution"]} ({e.get("graduation_year", "?")})'
            for e in education
        )
        or "none listed",
        certifications=", ".join(certifications) or "none listed",
    )
    return SYSTEM_PROMPT, user_prompt
