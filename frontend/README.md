# TalentOS Frontend

React + TypeScript (Vite) UI for the two backend services:
[`intake-matching-service`](../intake-matching-service) (JD/resume analysis, submissions,
matching) and [`assessment-service`](../assessment-service) (interview sessions, question
generation, evaluation, score card).

Flow: analyze a JD and a resume -> create a submission (runs the match analysis) -> start an
assessment from that submission -> generate questions per skill/type -> answer them (with
Run/Run-all-testcases for coding) -> Final submit -> score card with a red/green answer review.

## Structure

```
src/
  api/
    client.ts        two axios instances: intakeClient (:8000) and assessmentClient (:8001)
    intake.ts         typed calls to intake-matching-service (JD/resume/submissions)
    assessment.ts      typed calls to assessment-service (interview sessions/questions/evaluations)
  types.ts             TS types mirroring both services' response schemas
  components/          JDAnalysisForm, ResumeUploadForm, SkillCard, QuestionConfigPanel,
                        QuestionCard, EvaluationResult, ScoreCard, AnswerReview,
                        MatchAnalysisCard, AuditHistory, JDEditForm, Tabs
  pages/
    JDListPage / NewJDAnalysisPage / JDDetailPage
    ResumeListPage / NewResumeAnalysisPage / ResumeDetailPage
    SubmissionListPage / NewSubmissionPage / SubmissionDetailPage
    InterviewSessionPage   (skills&rubrics / configure&generate / questions / score card)
```

## Setup

```bash
npm install
cp .env.example .env   # defaults already point at both local services
npm run dev
```

Runs at `http://localhost:5173`. Requires both backend services running (see the root
[`README.md`](../README.md) for how to start them), with `VITE_API_KEY` matching both
services' `API_KEY`, and each service's `CORS_ORIGINS` including `http://localhost:5173`
(the default in both `.env.example` files).

## Scripts

- `npm run dev` - dev server with HMR
- `npm run build` - type-check (`tsc -b`) and production build to `dist/`
- `npm run preview` - preview the production build locally
