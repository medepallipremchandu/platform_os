# TalentOS Assessment Service

FastAPI service that runs the actual interview once a candidate has been submitted against a
JD: question generation, question answering (descriptive/MCQ/coding with real code execution),
evaluation, and the candidate's score card.

> Part of a 2-service architecture. See [`../intake-matching-service`](../intake-matching-service)
> for JD analysis, resume analysis, and JD↔resume matching, and [`../README.md`](../README.md)
> for the overall layout. Each service owns its own database - this one never queries
> intake-matching-service's database directly.

All commands below assume your working directory is `assessment-service/`.

## Where the domain data comes from

This service owns nothing about JDs or resumes directly. When a submission (JD + resume pair,
created in intake-matching-service) is ready to be interviewed, `POST /api/v1/interview-sessions
{submission_id}` fetches a one-time snapshot of that submission's job title, candidate name, and
skills/rubrics over HTTP (`GET .../submissions/{id}/for-assessment` on intake-matching-service,
using `INTAKE_MATCHING_API_KEY`) and stores its own local copy as an `InterviewSession`. That
call is idempotent - calling it again for the same `submission_id` returns the existing session.
Everything downstream (questions, evaluations, score card) runs entirely against that local copy.

## Architecture

```
main.py                    Entrypoint - `python main.py` starts uvicorn (app.main:app)
app/
  config.py                Settings (env vars via pydantic-settings)
  logging_config.py        Console + rotating file logging, per-request request_id
  database.py              SQLAlchemy engine/session (PostgreSQL)
  models/                  SQLAlchemy ORM models (InterviewSession, Skill, Rubric, Question, Evaluation, ...)
  schemas/                 Pydantic request/response schemas + internal LLM-output schemas
  core/                    Exceptions, API-key auth, request-logging middleware
  services/
    llm/                   LLMProvider interface + Claude/Azure OpenAI implementations + fallback client
    intake_client.py       HTTP client for the one call this service makes to intake-matching-service
    interview_session_service.py
    question_service.py
    evaluation_service.py
    code_execution_service.py
  prompts/                 Prompt templates for each LLM task
  api/v1/                  Route handlers
alembic/                   DB migrations
```

## Domain model

- **Interview session**: a local snapshot of one submission - job title, candidate name,
  skills, and rubrics (weights summing to 100 per skill, e.g. Java -> Concurrency 40%,
  Collections 30%, OOP 30%).
- **Question generation**: request N questions of a given type (`descriptive` | `mcq` |
  `coding`) for a skill; each question maps to one or more of that skill's rubrics with a
  weight (summing to <=100 for that question) plus grading criteria.
- **Coding questions run real code**: submitted code executes as a subprocess (Python/JS)
  against the question's test cases (visible + hidden), matching stdout exactly - the same
  model real coding-judge platforms use. "Run" / "Run all testcases" execute visible cases
  only, without persisting anything; a real submission also runs the hidden cases and persists
  the result. **Security note**: this has no container/network/filesystem sandboxing beyond a
  timeout - fine for an internal, API-key-gated tool, not safe to expose publicly as-is.
- **Evaluation**: descriptive answers are graded by the LLM against each rubric's criteria (0-100
  each); MCQ/coding are graded deterministically (correct/incorrect, test pass rate) and that
  score applied uniformly across the question's rubrics. `weighted_contribution = expected_weight
  * achieved_score / 100`.
- **Final submit / score card**: `POST /evaluations/submit-batch` evaluates every answered
  question on an interview session in one call and returns an overall score plus a per-skill
  breakdown.

## LLM provider fallback

Claude (Anthropic) is the primary provider; Azure OpenAI is the automatic fallback. Every
generation call goes through `LLMClient.get_json()`, which tries the primary provider first
(with one retry on a malformed/unparseable response), then falls back to the secondary
provider on any failure. Swap providers or models purely via `.env` - no code changes needed.

## Setup

### 1. Create the database

```sql
CREATE DATABASE talentos_assessment;
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`: `DATABASE_URL`, `API_KEY`, `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL`,
`AZURE_OPENAI_*`, and `INTAKE_MATCHING_SERVICE_URL`/`INTAKE_MATCHING_API_KEY` (must match
intake-matching-service's own `API_KEY`).

### 3. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run migrations, then start

```bash
alembic upgrade head
python main.py
```

Serves at `http://localhost:8001` (interactive docs at `/docs`). Every request except
`/health` requires `X-API-Key`.

## API

| Method | Path                                      | Description                                                |
|--------|---------------------------------------------|--------------------------------------------------------------|
| GET    | `/health`                                   | Liveness check, no auth                                       |
| POST   | `/api/v1/interview-sessions`                | `{submission_id}` -> snapshot skills/rubrics (idempotent)      |
| GET    | `/api/v1/interview-sessions`                | List interview sessions                                        |
| GET    | `/api/v1/interview-sessions/{id}`           | Fetch a session + its skills/rubrics                            |
| POST   | `/api/v1/questions/generate`                | `{skill_id, num_questions, question_type}` -> questions          |
| POST   | `/api/v1/questions/generate-batch`          | Same, for multiple skills/types in one call                    |
| GET    | `/api/v1/questions/{skill_id}`              | List questions for a skill                                      |
| POST   | `/api/v1/questions/{id}/run-code`           | Dry-run code against visible test cases only, not persisted     |
| POST   | `/api/v1/evaluations`                       | Evaluate one answer                                              |
| POST   | `/api/v1/evaluations/submit-batch`          | Evaluate many answers at once -> score card                      |
| GET    | `/api/v1/evaluations/{id}`                  | Fetch a stored evaluation                                        |

Full request/response schemas are at `/docs` (Swagger UI) once the server is running.

## Logging

Structured log lines (timestamp, level, request id, logger, message) go to both the console
and a rotating file at `logs/app.log` (10MB x 5 backups). Every HTTP request gets a
`request_id` that tags every log line produced while handling it, including LLM/service calls.

## Tests

```bash
pytest
```
