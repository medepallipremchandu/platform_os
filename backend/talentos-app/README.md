# TalentOS Intake & Matching Service

The one service holding all recruiting/assessment data: JD analysis, resume analysis,
submissions & matching, interview sessions, question generation, evaluation, and the score
card. It has no model/provider/prompt code of its own - every AI step calls
[`agent-builder-service`](../agent-builder-service)'s `/invoke` endpoint with that task's own
agent key. See [`../README.md`](../README.md) for the overall layout.

## Domain

- **JD analysis**: JD text in -> job/role context, weighted skill rubrics out.
- **Resume analysis**: resume file (PDF/DOCX; legacy `.doc` is rejected with a message to
  convert) -> extracted candidate name/contact, experience, skills, work history, education,
  certifications.
- **Submission**: pairs one JD analysis with one resume analysis. Creating a submission
  triggers a **match analysis** - a skill-by-skill comparison against the JD's weighted
  rubrics, with strengths, gaps, market-context commentary, and a hiring recommendation.
- **Interview session**: marks that an assessment has started for a submission. Skills/rubrics
  come directly from `submission.jd_analysis.skills` - no snapshot or service-to-service call
  needed, since this all lives in one database now.
- **Question generation**: per skill, request N questions of a type (`descriptive` | `mcq` |
  `coding`) - each type is a separate agent (their JSON output shapes differ too much to share
  one prompt). Coding questions carry real test cases.
- **Coding evaluation runs real code**: submitted code executes as a subprocess (Python/JS)
  against the question's test cases (visible + hidden), matching stdout exactly. "Run" / "Run
  all testcases" execute visible cases only without persisting; a real submission also runs
  the hidden cases and persists the result. **Security note**: no container/network/filesystem
  sandboxing beyond a timeout - fine for an internal, API-key-gated tool, not for public use.
- **Descriptive evaluation** is graded by an agent against each rubric's criteria (0-100 each);
  MCQ/coding are graded deterministically and that score applied uniformly across the
  question's rubrics.
- **Final submit / score card**: `POST /evaluations/submit-batch` evaluates every answered
  question on a session in one call and returns an overall score plus a per-skill breakdown.

## Calling agent-builder-service

Every agent call goes through `app/services/agent_client.py`, which exchanges that task's
IAM-issued Service Principal credential (`*_AGENT_CLIENT_ID`/`*_AGENT_CLIENT_SECRET` in
`.env` - see `.env.example`) for a short-lived access token via `iam-service`'s
`POST /auth/token` (cached until ~1 minute before it expires - see
`app/core/iam_client.AgentCredentialTokenCache`), then POSTs `{variables: {...}}` to
`agent-builder-service`'s `/invoke` with `Authorization: Bearer <token>` instead of a static
`X-Agent-Key`. There are 7 agents: JD analysis, resume analysis, matching, question generation
x3 (one per type), and descriptive-answer grading. Any list-to-text formatting a prompt needs
(e.g. turning a JD's skills into a readable block for the matching prompt) happens here in
Python, not in the agent's template - the template only does `{{name}}` substitution.

## Setup

```bash
# 1. Create the database
#    CREATE DATABASE talentos_app;

cp .env.example .env
# Fill in DATABASE_URL, IAM_SERVICE_URL, and the 7 *_AGENT_CLIENT_ID/_CLIENT_SECRET pairs -
# these come from agent-builder-service's own IAM migration re-issuing each agent's invoke
# credential as a resource-bound Service Principal (see that service's README).

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

alembic upgrade 0003
python scripts/backfill_organization_id.py   # one-time: stamps pre-IAM-migration rows
alembic upgrade head

python main.py          # serves http://localhost:8000
```

## API

| Method | Path                                      | Description                                                |
|--------|---------------------------------------------|----------------------------------------------------------------|
| GET    | `/health`                                   | Liveness check, no auth                                         |
| POST   | `/api/v1/jd-analysis`                       | Analyze a JD text                                                |
| GET    | `/api/v1/jd-analysis`                       | List JD analyses                                                 |
| GET    | `/api/v1/jd-analysis/{id}`                  | Fetch a JD analysis                                              |
| PATCH  | `/api/v1/jd-analysis/{id}`                  | Edit a JD analysis (audited)                                     |
| DELETE | `/api/v1/jd-analysis/{id}`                  | Soft-delete a JD analysis                                        |
| GET    | `/api/v1/jd-analysis/{id}/audit-log`        | Change history                                                   |
| POST   | `/api/v1/resume-analysis`                   | Upload + analyze a resume (multipart `file`)                     |
| GET    | `/api/v1/resume-analysis`                   | List resume analyses                                             |
| GET    | `/api/v1/resume-analysis/{id}`              | Fetch a resume analysis                                          |
| DELETE | `/api/v1/resume-analysis/{id}`              | Soft-delete a resume analysis                                    |
| POST   | `/api/v1/submissions`                       | Pair a JD + resume, runs the match analysis                      |
| GET    | `/api/v1/submissions`                       | List submissions (with match %)                                  |
| GET    | `/api/v1/submissions/{id}`                  | Fetch a submission + its match analysis                          |
| DELETE | `/api/v1/submissions/{id}`                  | Soft-delete a submission                                         |
| POST   | `/api/v1/interview-sessions`                | `{submission_id}` -> start (or resume) an assessment              |
| GET    | `/api/v1/interview-sessions`                | List interview sessions                                          |
| GET    | `/api/v1/interview-sessions/{id}`           | Fetch a session + its skills/rubrics                              |
| POST   | `/api/v1/questions/generate`                | `{skill_id, num_questions, question_type}` -> questions            |
| POST   | `/api/v1/questions/generate-batch`          | Same, for multiple skills/types in one call                      |
| GET    | `/api/v1/questions/{skill_id}`              | List questions for a skill                                        |
| POST   | `/api/v1/questions/{id}/run-code`           | Dry-run code against visible test cases only, not persisted       |
| POST   | `/api/v1/evaluations`                       | Evaluate one answer                                                |
| POST   | `/api/v1/evaluations/submit-batch`          | Evaluate many answers at once -> score card                        |
| GET    | `/api/v1/evaluations/{id}`                  | Fetch a stored evaluation                                          |

Every request (except `/health`) requires `Authorization: Bearer <access token>` issued by
`iam-service` (validated locally against its published JWKS - see `app/core/iam_client.py`),
plus a specific permission per route:

| Route(s) | Permission |
|---|---|
| `POST /jd-analysis`, `PATCH /jd-analysis/{id}` | `talentos.intake.requirements.write` |
| `GET /jd-analysis`, `GET /jd-analysis/{id}`, `GET /jd-analysis/{id}/audit-log` | `talentos.intake.requirements.read` |
| `DELETE /jd-analysis/{id}` | `talentos.intake.requirements.delete` |
| `POST /resume-analysis` | `talentos.intake.applicants.write` |
| `GET /resume-analysis`, `GET /resume-analysis/{id}`, `GET /resume-analysis/{id}/audit-log` | `talentos.intake.applicants.read` |
| `DELETE /resume-analysis/{id}` | `talentos.intake.applicants.delete` |
| `POST /submissions` | `talentos.intake.submissions.write` |
| `GET /submissions`, `GET /submissions/{id}`, `GET /submissions/{id}/audit-log` | `talentos.intake.submissions.read` |
| `DELETE /submissions/{id}` | `talentos.intake.submissions.delete` |
| `POST /interview-sessions` | `talentos.intake.interviews.write` |
| `GET /interview-sessions`, `GET /interview-sessions/{id}` | `talentos.intake.interviews.read` |
| `POST /questions/generate`, `POST /questions/generate-batch`, `POST /questions/{id}/run-code` | `talentos.intake.interviews.write` |
| `GET /questions/{skill_id}` | `talentos.intake.interviews.read` |
| `POST /evaluations`, `POST /evaluations/submit-batch` | `talentos.intake.interviews.write` |
| `GET /evaluations/{id}` | `talentos.intake.interviews.read` |
| `GET /health` | none |

`created_by`/`modified_by`/`deleted_by` are stamped from the verified token
(`claims.email or claims.name or claims.sub`) instead of the old free-text `X-Actor-Email`
header. `organization_id` on `jd_analyses`/`resume_analyses`/`submissions` (and transitively,
via a join, on everything under them) comes from the token's `org_id` claim, never from the
request body, and every list/get endpoint filters by it. Every mutation also posts an audit
event to `iam-service` (`POST /audit/events`, using the caller's own bearer token) in addition
to this service's own local `audit_logs` table.

## Tests

```bash
pytest
```
