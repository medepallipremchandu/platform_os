SYSTEM_PROMPT = """You are an expert technical recruiter extracting structured candidate data from \
resumes for an interview-assessment platform. You must respond with ONLY a single valid JSON \
object, no prose, no markdown fences."""

_USER_TEMPLATE = """Extract structured information from the following resume text.

Resume text:
---
{resume_text}
---

Return a JSON object with exactly this shape:
{{
  "candidate_name": string or null,
  "candidate_email": string or null,
  "candidate_phone": string or null,
  "total_experience_years": number or null (estimated total professional experience in years),
  "summary": string (2-4 sentence summary of the candidate's profile and seniority),
  "skills": [
    {{
      "name": string,
      "years_experience": number or null,
      "proficiency": string or null (one of "beginner", "intermediate", "advanced", "expert")
    }}
  ],
  "work_history": [
    {{
      "company": string,
      "title": string,
      "start_date": string or null,
      "end_date": string or null (or "Present"),
      "description": string (key responsibilities and achievements)
    }}
  ],
  "education": [
    {{
      "institution": string,
      "degree": string or null,
      "field_of_study": string or null,
      "graduation_year": string or null
    }}
  ],
  "certifications": [string, ...]
}}

Rules:
- Extract every distinct skill mentioned or clearly evidenced (technical and non-technical).
- Infer years_experience/proficiency for a skill only when the resume gives enough evidence; otherwise use null.
- Order work_history most recent first.
- If a field cannot be determined from the text, use null (or an empty list for list fields).
"""


def build_resume_analysis_prompt(resume_text: str) -> tuple[str, str]:
    return SYSTEM_PROMPT, _USER_TEMPLATE.format(resume_text=resume_text)
