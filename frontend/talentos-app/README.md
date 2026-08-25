# TalentOS Frontend

React + TypeScript (Vite) UI for [`talentos-app`](../../backend/talentos-app) (all
recruiting/assessment data and logic).

Recruiting flow: analyze a JD and a resume -> create a submission (runs the match analysis) ->
start an assessment from that submission -> generate questions per skill/type -> answer them
(with Run/Run-all-testcases for coding) -> Final submit -> score card with a red/green answer
review.

Model + agent management (the "Agent Builder" section this app used to host) has moved to its
own standalone frontend, [`agent-builder-console`](../agent-builder-console) - this app no
longer calls `agent-builder-service` directly (its *backend* still does, server-to-server,
unaffected by this split).

## Structure

```
src/
  api/
    client.ts          intakeClient axios instance (:8000), Bearer-token interceptor + silent refresh
    intake.ts            typed calls to talentos-app's backend (everything recruiting-related)
  types.ts               TS types mirroring the service's response schemas
  components/            JDAnalysisForm, ResumeUploadForm, SkillCard, QuestionConfigPanel,
                          QuestionCard, EvaluationResult, ScoreCard, AnswerReview,
                          MatchAnalysisCard, AuditHistory, JDEditForm, Tabs, ui/ (design system)
  pages/
    JDListPage / NewJDAnalysisPage / JDDetailPage
    ResumeListPage / NewResumeAnalysisPage / ResumeDetailPage
    SubmissionListPage / NewSubmissionPage / SubmissionDetailPage
    InterviewSessionPage   (skills&rubrics / configure&generate / questions / score card)
```

## Setup

```bash
npm install
cp .env.example .env   # defaults already point at the local service
npm run dev
```

Runs at `http://localhost:5173`. Requires the `talentos-app` backend running (see the root
[`README.md`](../README.md) for how to start it) and an IAM-issued session (see `src/lib/auth.ts`
- this app is an IAM relying party, redirecting to the portal app to log in).

## Scripts

- `npm run dev` - dev server with HMR
- `npm run build` - type-check (`tsc -b`) and production build to `dist/`
- `npm run preview` - preview the production build locally
