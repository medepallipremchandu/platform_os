"""Registers the starter model catalog (Claude primary, Azure OpenAI fallback) and creates +
publishes the 7 agents the rest of the platform depends on, porting the prompts that used to
be hardcoded in talentos-app/assessment-service.

Each publish mints a resource-bound iam-service ServicePrincipal (see app/services/agent_credentials.py)
using this service's own machine identity (IAM_CLIENT_ID/IAM_CLIENT_SECRET in .env - run
scripts/bootstrap_iam_identity.py first). Prints each agent's plaintext client_secret exactly
once (never recoverable after this) - copy them into talentos-app's .env.

Usage (from agent-builder-service/):
    .venv/Scripts/python.exe scripts/seed_models_and_agents.py
"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.services.agent_service import create_agent, publish_agent  # noqa: E402
from app.services.model_service import create_model  # noqa: E402

ACTOR = "seed_script"
ORGANIZATION_ID = uuid.UUID(get_settings().BOOTSTRAP_ORGANIZATION_ID)

RUBRIC_MAP_SHAPE = """      "rubric_maps": [
        {
          "rubric_name": string (must exactly match one of the available rubric names above),
          "weight_percentage": number (0-100, how much of this question's grade this rubric represents),
          "evaluation_criteria": string (concrete, specific guidance on what to look for to satisfy this rubric for this exact question)
        }
      ]"""

RUBRIC_MAP_RULES = """- Each question may map to one or more of the available rubrics.
- Within a single question, the weight_percentage values across its rubric_maps must sum to 100 or less (never more than 100)."""

QUESTION_GEN_HEADER = """Generate {{num_questions}} __QUESTION_TYPE__ interview question(s) for the skill "{{skill_name}}".

Skill description: {{skill_description}}

Available rubrics for this skill (use these exact names, do not invent new ones):
{{rubrics_block}}
"""

AGENTS = [
    {
        "name": "JD Analysis Agent",
        "description": "Extracts job/role context and weighted skill rubrics from a job description.",
        "system_prompt": (
            "You are an expert technical recruiter and job analyst. You extract structured "
            "information from job descriptions for an interview-assessment platform. "
            "You must respond with ONLY a single valid JSON object, no prose, no markdown fences."
        ),
        "user_prompt_template": """Analyze the following job description and extract structured context.

Job description:
---
{{jd_text}}
---

Return a JSON object with exactly this shape:
{
  "job_title": string,
  "role_context": string (what this role is, where it sits in the org, seniority),
  "job_context_summary": string (2-4 sentence summary of the job and its purpose),
  "responsibilities": [string, ...],
  "qualifications": [string, ...],
  "skills": [
    {
      "name": string (a single skill, e.g. "Java", "System Design", "Communication"),
      "description": string (why this skill matters for this role),
      "rubrics": [
        {
          "name": string (a specific evaluation dimension within the skill, e.g. "Concurrency" for Java),
          "description": string (what mastery of this dimension looks like),
          "weight_percentage": number (0-100, how much this rubric contributes to the skill overall)
        }
      ]
    }
  ]
}

Rules:
- Extract every distinct skill implied by the JD (technical and non-technical).
- For each skill, break it into 2-5 rubrics whose weight_percentage values sum to exactly 100.
- Be specific and concrete, do not use generic filler text.
""",
    },
    {
        "name": "Resume Analysis Agent",
        "description": "Extracts a structured candidate profile from resume text.",
        "system_prompt": (
            "You are an expert technical recruiter extracting structured candidate data from "
            "resumes for an interview-assessment platform. You must respond with ONLY a single "
            "valid JSON object, no prose, no markdown fences."
        ),
        "user_prompt_template": """Extract structured information from the following resume text.

Resume text:
---
{{resume_text}}
---

Return a JSON object with exactly this shape:
{
  "candidate_name": string or null,
  "candidate_email": string or null,
  "candidate_phone": string or null,
  "total_experience_years": number or null (estimated total professional experience in years),
  "summary": string (2-4 sentence summary of the candidate's profile and seniority),
  "skills": [
    {
      "name": string,
      "years_experience": number or null,
      "proficiency": string or null (one of "beginner", "intermediate", "advanced", "expert")
    }
  ],
  "work_history": [
    {
      "company": string,
      "title": string,
      "start_date": string or null,
      "end_date": string or null (or "Present"),
      "description": string (key responsibilities and achievements)
    }
  ],
  "education": [
    {
      "institution": string,
      "degree": string or null,
      "field_of_study": string or null,
      "graduation_year": string or null
    }
  ],
  "certifications": [string, ...]
}

Rules:
- Extract every distinct skill mentioned or clearly evidenced (technical and non-technical).
- Infer years_experience/proficiency for a skill only when the resume gives enough evidence; otherwise use null.
- Order work_history most recent first.
- If a field cannot be determined from the text, use null (or an empty list for list fields).
""",
    },
    {
        "name": "JD-Resume Matching Agent",
        "description": "Compares a candidate's resume against a JD's weighted rubrics and produces a match analysis.",
        "system_prompt": (
            "You are an expert technical recruiter evaluating how well a candidate's resume "
            "matches a job description, benchmarked against current market expectations for "
            "similar roles. You must respond with ONLY a single valid JSON object, no prose, "
            "no markdown fences."
        ),
        "user_prompt_template": """Compare this candidate's resume against this job description and produce a detailed match analysis.

Job description:
---
Title: {{job_title}}
Role context: {{role_context}}
Responsibilities: {{responsibilities}}
Qualifications: {{qualifications}}

Required skills (with internal rubric breakdown for context):
{{skills_block}}
---

Candidate resume:
---
Summary: {{resume_summary}}
Total experience: {{total_experience_years}} years
Skills: {{resume_skills}}
Work history: {{work_history}}
Education: {{education}}
Certifications: {{certifications}}
---

Return a JSON object with exactly this shape:
{
  "overall_match_percentage": number (0-100, your best overall assessment - you MUST derive this from the individual skill_matches below, weighted by jd_weight_percentage),
  "skill_matches": [
    {
      "skill_name": string (must match one of the required skills above),
      "jd_weight_percentage": number (0-100, relative importance of this skill to the role; across all skill_matches these must sum to 100),
      "required_level": string (what level of this skill the role demands, e.g. "expert - 5+ years"),
      "candidate_evidence": string (what in the resume evidences - or fails to evidence - this skill),
      "match_percentage": number (0-100, how well the candidate meets this specific skill's requirement),
      "verdict": string (one of "strong match", "partial match", "gap")
    }
  ],
  "strengths": [string, ...] (3-5 concrete candidate strengths relative to this specific role),
  "gaps": [string, ...] (concrete gaps or risks relative to this specific role, empty list if none),
  "market_context_commentary": string (2-4 sentences: how this candidate's profile compares to what the current market/typical hiring bar looks like for this kind of role - e.g. typical years of experience, common skill combinations, competitiveness),
  "recommendation": string (1-2 sentences: a concrete hiring/interview recommendation, e.g. which skills to probe deepest in the interview)
}

Rules:
- Produce one skill_matches entry per required skill listed above - do not skip any, do not invent new ones.
- Be rigorous and specific; do not default to generous scores. A missing skill should score low with verdict "gap", not be glossed over.
""",
    },
    {
        "name": "Question Generation Agent - Descriptive",
        "description": "Generates open-ended interview questions from a skill's rubrics.",
        "system_prompt": (
            "You are an expert technical interviewer. You design interview questions that probe "
            "specific evaluation rubrics for a given skill, for an interview-assessment platform. "
            "You must respond with ONLY a single valid JSON object, no prose, no markdown fences."
        ),
        "user_prompt_template": QUESTION_GEN_HEADER.replace("__QUESTION_TYPE__", "descriptive")
        + """
Return a JSON object with exactly this shape:
{
  "questions": [
    {
      "question_text": string (an open-ended interview question, self-contained),
      "difficulty": string (one of "easy", "medium", "hard"),
"""
        + RUBRIC_MAP_SHAPE
        + """
    }
  ]
}

Rules:
"""
        + RUBRIC_MAP_RULES
        + """
- Prefer questions that combine 1-3 rubrics deeply rather than shallow, generic questions.
- evaluation_criteria must be specific enough that a grader with no other context could score a free-text answer against it.
""",
    },
    {
        "name": "Question Generation Agent - MCQ",
        "description": "Generates single-answer multiple-choice interview questions from a skill's rubrics.",
        "system_prompt": (
            "You are an expert technical interviewer. You design interview questions that probe "
            "specific evaluation rubrics for a given skill, for an interview-assessment platform. "
            "You must respond with ONLY a single valid JSON object, no prose, no markdown fences."
        ),
        "user_prompt_template": QUESTION_GEN_HEADER.replace("__QUESTION_TYPE__", "mcq")
        + """
Return a JSON object with exactly this shape:
{
  "questions": [
    {
      "question_text": string (a single-answer multiple-choice question, self-contained),
      "difficulty": string (one of "easy", "medium", "hard"),
      "options": [string, ...] (exactly 4 options),
      "correct_option_index": integer (0-based index into "options" of the single correct answer),
"""
        + RUBRIC_MAP_SHAPE
        + """
    }
  ]
}

Rules:
"""
        + RUBRIC_MAP_RULES
        + """
- Exactly one option must be correct; the other 3 must be plausible but clearly wrong to an expert.
- evaluation_criteria should describe why the correct option is correct (used for feedback display).
""",
    },
    {
        "name": "Question Generation Agent - Coding",
        "description": "Generates coding problems with test cases from a skill's rubrics.",
        "system_prompt": (
            "You are an expert technical interviewer. You design interview questions that probe "
            "specific evaluation rubrics for a given skill, for an interview-assessment platform. "
            "You must respond with ONLY a single valid JSON object, no prose, no markdown fences."
        ),
        "user_prompt_template": QUESTION_GEN_HEADER.replace("__QUESTION_TYPE__", "coding")
        + """
Return a JSON object with exactly this shape:
{
  "questions": [
    {
      "question_text": string (a self-contained coding problem statement, include input/output format),
      "difficulty": string (one of "easy", "medium", "hard"),
      "language": string (one of "python", "javascript"),
      "starter_code": string (a minimal function/program skeleton in that language reading from stdin and writing to stdout),
      "test_cases": [
        {
          "input": string (exact stdin the program will receive, empty string if none),
          "expected_output": string (exact expected stdout, trimmed),
          "is_hidden": boolean (true for held-out cases not shown to the candidate)
        }
      ] (produce 4-6 test cases: at least 2 visible (is_hidden=false) covering the basic case and one edge case, and the rest hidden covering edge cases and larger inputs),
"""
        + RUBRIC_MAP_SHAPE
        + """
    }
  ]
}

Rules:
"""
        + RUBRIC_MAP_RULES
        + """
- The program must read all input from stdin and write only the answer to stdout (no prompts/labels).
- test_cases must be objectively verifiable by exact string match on trimmed stdout - avoid floating point output unless formatted to a fixed number of decimals.
- evaluation_criteria should describe the algorithmic approach/complexity expected, since correctness is already verified by the test cases.
""",
    },
    {
        "name": "Descriptive Answer Evaluation Agent",
        "description": "Grades a candidate's free-text answer against a question's weighted rubrics.",
        "system_prompt": (
            "You are an expert, impartial technical interview grader for an interview-assessment "
            "platform. You score a candidate's answer against specific rubrics and evaluation "
            "criteria. You must respond with ONLY a single valid JSON object, no prose, no "
            "markdown fences."
        ),
        "user_prompt_template": """Question asked:
---
{{question_text}}
---

Candidate's answer:
---
{{candidate_answer}}
---

Score the answer against each of the following rubrics for this question:
{{rubrics_block}}

Return a JSON object with exactly this shape:
{
  "rubric_scores": [
    {
      "rubric_name": string (must exactly match one of the rubric names above),
      "achieved_score_percentage": number (0-100, how well the answer satisfies this rubric's criteria),
      "feedback": string (specific, concrete feedback justifying the score for this rubric)
    }
  ],
  "summary": string (2-3 sentence overall assessment of the answer)
}

Rules:
- Score every rubric listed above, even if the answer did not address it (score it low with feedback saying so).
- achieved_score_percentage reflects how well THIS rubric's criteria were met (0 = not at all, 100 = fully), independent of the rubric's weight.
- Be rigorous and specific; do not default to generous scores.
""",
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        claude_model = create_model(
            db,
            name="Claude Sonnet 5 (primary)",
            provider="claude",
            model_id=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
            api_key=os.environ["ANTHROPIC_API_KEY"],
            actor=ACTOR,
            organization_id=ORGANIZATION_ID,
        )
        azure_model = create_model(
            db,
            name="Azure OpenAI (fallback)",
            provider="azure_openai",
            model_id=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            actor=ACTOR,
            organization_id=ORGANIZATION_ID,
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
        print(f"Registered models: {claude_model.model_code} (primary), {azure_model.model_code} (fallback)\n")

        print(f"{'Agent':<40} {'Code':<8} client_secret (copy now - shown once)")
        print("-" * 100)
        for spec in AGENTS:
            agent = create_agent(
                db,
                name=spec["name"],
                description=spec["description"],
                system_prompt=spec["system_prompt"],
                user_prompt_template=spec["user_prompt_template"],
                primary_model_id=claude_model.id,
                fallback_model_id=azure_model.id,
                max_output_tokens=8192,
                timeout_seconds=60,
                rate_limit_per_minute=60,
                actor=ACTOR,
                organization_id=ORGANIZATION_ID,
            )
            agent, plaintext_client_secret = publish_agent(db, agent, ACTOR)
            print(f"{agent.name:<40} {agent.agent_code:<8} {plaintext_client_secret}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
