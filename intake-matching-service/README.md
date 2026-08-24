# TalentOS Intake & Matching Service

FastAPI service owning the "front door" of the TalentOS pipeline: analyzing job descriptions,
analyzing resumes, and matching a candidate's resume against a job description.

> Part of a 2-service architecture. See [`../assessment-service`](../assessment-service) for
> question generation/interview/evaluation, and [`../README.md`](../README.md) for the overall
> layout. Each service owns its own database - they never share tables directly.

## Domain

- **JD analysis**: JD text in -> job/role context, weighted skill rubrics out (unchanged from
  the original single-service design).
- **Resume analysis**: resume file (PDF/DOCX; legacy `.doc` is rejected with a message to
  convert) -> extracted candidate name/contact, experience, skills, work history, education,
  certifications.
- **Submission**: pairs one JD analysis with one resume analysis. Creating a submission
  triggers a **match analysis** - a skill-by-skill comparison of the resume against the JD's
  weighted rubrics, with strengths, gaps, and commentary on how the candidate compares to
  current market expectations for the role, plus a hiring/interview recommendation.

## Service-to-service contract

`GET /api/v1/submissions/{id}/for-assessment` is called by `assessment-service` (using this
service's `API_KEY`) to snapshot the job title, candidate name, and skills/rubrics needed to
run an interview for that submission. `assessment-service` stores its own local copy - it does
not query this service's database directly.

## Setup

```bash
# 1. Create the database
#    CREATE DATABASE talentos_intake_matching;

cp .env.example .env   # then fill in DATABASE_URL / API keys

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

alembic upgrade head
python main.py          # serves http://localhost:8000
```

## API

| Method | Path                                        | Description                                    |
|--------|----------------------------------------------|-------------------------------------------------|
| GET    | `/health`                                    | Liveness check, no auth                          |
| POST   | `/api/v1/jd-analysis`                        | Analyze a JD text                                |
| GET    | `/api/v1/jd-analysis`                        | List JD analyses                                 |
| GET    | `/api/v1/jd-analysis/{id}`                   | Fetch a JD analysis                              |
| PATCH  | `/api/v1/jd-analysis/{id}`                   | Edit a JD analysis (audited)                     |
| DELETE | `/api/v1/jd-analysis/{id}`                   | Soft-delete a JD analysis                        |
| GET    | `/api/v1/jd-analysis/{id}/audit-log`         | Change history                                   |
| POST   | `/api/v1/resume-analysis`                    | Upload + analyze a resume (multipart `file`)     |
| GET    | `/api/v1/resume-analysis`                    | List resume analyses                             |
| GET    | `/api/v1/resume-analysis/{id}`               | Fetch a resume analysis                          |
| DELETE | `/api/v1/resume-analysis/{id}`               | Soft-delete a resume analysis                    |
| POST   | `/api/v1/submissions`                        | Pair a JD + resume, runs the match analysis      |
| GET    | `/api/v1/submissions`                        | List submissions (with match %)                  |
| GET    | `/api/v1/submissions/{id}`                   | Fetch a submission + its match analysis          |
| DELETE | `/api/v1/submissions/{id}`                   | Soft-delete a submission                         |
| GET    | `/api/v1/submissions/{id}/for-assessment`    | Internal: assessment-service's snapshot contract |

Every request (except `/health`) requires `X-API-Key`; mutations also accept `X-Actor-Email`
for audit stamping (defaults to `"system"`).

## Tests

```bash
pytest
```
