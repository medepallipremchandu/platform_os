# TalentOS

AI-assisted hiring platform, split into two independent microservices (each with its own
database) plus a shared React frontend:

- **JD analysis** (job text -> job/role context + weighted skill rubrics)
- **Resume analysis** (PDF/DOCX upload -> structured candidate profile)
- **Submissions & matching** (pair a JD + resume, get an enterprise-grade match analysis:
  skill-by-skill fit, strengths/gaps, market-context commentary, hiring recommendation)
- **Interview assessment** (from a submission: generate questions, run a real interview -
  descriptive/MCQ/coding with actual code execution - evaluate, produce a score card)

## Layout

```
intake-matching-service/   JD analysis, resume analysis, submissions/matching. DB: talentos_intake_matching. Port 8000.
assessment-service/        Interview sessions, question generation, evaluation, score card. DB: talentos_assessment. Port 8001.
frontend/                  React + TypeScript (Vite) UI that talks to both services.
```

The two backend services never share a database or query each other's tables directly.
`assessment-service` fetches what it needs (job title, candidate name, skills/rubrics) from
`intake-matching-service` over HTTP when an interview session is started, and keeps its own
local copy from then on - see each service's README for the exact contract.

See [`intake-matching-service/README.md`](intake-matching-service/README.md),
[`assessment-service/README.md`](assessment-service/README.md), and
[`frontend/README.md`](frontend/README.md) for setup and API details of each part.

## Quick start (local)

1. **intake-matching-service**
   ```bash
   cd intake-matching-service
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_intake_matching;
   alembic upgrade head
   python main.py          # serves http://localhost:8000
   ```
2. **assessment-service** (separate terminal)
   ```bash
   cd assessment-service
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_assessment;
   alembic upgrade head
   python main.py          # serves http://localhost:8001
   ```
3. **frontend** (separate terminal)
   ```bash
   cd frontend
   npm install
   cp .env.example .env
   npm run dev              # serves http://localhost:5173
   ```

Each service's default `.env` is already set up to talk to the others on these ports
(`assessment-service`'s `INTAKE_MATCHING_API_KEY` must match `intake-matching-service`'s
`API_KEY`; both default to the same dev key).

## End-to-end flow

1. Analyze a JD (`/` in the UI) and a resume (`/resumes`).
2. Create a submission pairing them (`/submissions/new`) - this runs the match analysis.
3. From the submission page, "Start assessment" - creates an interview session in
   assessment-service from a snapshot of that JD's skills/rubrics.
4. On the interview session page: generate questions per skill/type, answer them (with
   Run/Run-all-testcases for coding), Final submit, see the score card.
