# TalentOS

AI-assisted hiring platform: three backend services (each with its own database) plus four React
frontends, all secured by a single enterprise IAM layer with one shared login.

- **IAM** (`iam-service` + `iam-console`) - Organizations, Users, Roles, Permissions, Role
  Assignments, and Service Principals, Azure-AD/Entra-style. Every other service authenticates
  against it and enforces permissions from it; every authentication event, permission decision,
  and business-data mutation platform-wide lands in its audit log, timestamped.
- **Portal** (`portal`) - the platform's one login page. Log in once, then launch whichever of
  the other apps you have access to; each hands your session to the other, so there's no second
  login.
- **JD analysis** (job text -> job/role context + weighted skill rubrics)
- **Resume analysis** (PDF/DOCX upload -> structured candidate profile)
- **Submissions & matching** (pair a JD + resume, get an enterprise-grade match analysis:
  skill-by-skill fit, strengths/gaps, market-context commentary, hiring recommendation)
- **Interview assessment** (from a submission: generate questions, run a real interview -
  descriptive/MCQ/coding with actual code execution - evaluate, produce a score card)
- **Agent builder** (`agent-builder-service` + `agent-builder-console`) - every AI call above
  goes through a published *agent* (a prompt template bound to a model, with limits), not a
  hardcoded prompt/model in application code. Models, prompts, and limits are all managed here,
  Azure-AI-Foundry style; each agent's invoke credential is itself an IAM-issued, resource-bound
  Service Principal.

## Layout

```
backend/
  iam-service/               Organizations, Users, Roles, Permissions, Role Assignments, Service
                              Principals, JWT/JWKS issuance, platform-wide audit log.
                              DB: talentos_iam. Port 8003.
  agent-builder-service/     Model catalog + agents (prompts/limits) + /invoke. DB:
                              talentos_agent_builder. Port 8002.
  talentos-app/              JD analysis, resume analysis, submissions/matching, interview
                              sessions, question generation, evaluation, score card.
                              DB: talentos_app. Port 8000.
frontend/
  portal/                     The one login page + launcher. No business features of its own.
                               Port 5175.
  iam-console/                Admin console: users, roles, role assignments, service
                               principals, audit log. Port 5174.
  agent-builder-console/      Models + agents management (moved out of the recruiting UI so it's
                               its own dedicated app). Port 5176.
  talentos-app/                The recruiting UI: requirements, applicants, submissions,
                               interviews. Port 5173.
```

`iam-console`, `agent-builder-console`, and `talentos-app` (frontend) are all pure relying-party
apps with **no login form of their own** - each checks for a valid session and, if it doesn't
have one, redirects to `portal` with `?return_to=<its own URL>`. After logging in once, `portal`
hands the session to whichever app the user picks (or straight back to whichever app redirected
it there) via a one-time token handoff in the URL fragment, which the receiving app consumes on
load and immediately strips from the address bar. `portal`'s launcher only shows a tile for an
app the user actually has permission to use (decoded from the access token's `permissions`
claim), so someone with no `talentos.agentbuilder.*` grant never even sees an Agent Builder tile.

`talentos-app` (backend) and `agent-builder-service` hold all business logic; neither has its
own user/role/permission model - both are relying parties of `iam-service`, validating its
RS256-signed JWTs locally (via its published JWKS) and enforcing a
`talentos.<service>.<resource>.<action>` permission on every mutating and most read endpoints.
`talentos-app` (backend) also has no model/provider/prompt code of its own - every AI step
(JD analysis, resume analysis, matching, question generation, descriptive-answer grading) calls
`agent-builder-service`'s `/invoke` endpoint, authenticating with a Bearer token obtained by
exchanging that agent's IAM Service Principal credentials. See each service's README for detail,
and `docs/superpowers/specs/2026-08-24-iam-service-design.md` for the full IAM design.

## Quick start (local)

Start in this order - each depends on the one(s) before it being reachable.

1. **iam-service**
   ```bash
   cd backend/iam-service
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_iam;
   alembic upgrade head
   python scripts/generate_signing_key.py       # writes the RS256 keypair under keys/
   python main.py                                # serves http://localhost:8003
   # in another terminal:
   python scripts/seed_permissions_and_roles.py   # seeds the permission catalog + built-in roles
   python scripts/bootstrap.py                    # creates the first Organization + admin User
   ```

2. **agent-builder-service**
   ```bash
   cd backend/agent-builder-service
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_agent_builder;
   alembic upgrade head
   python scripts/bootstrap_iam_identity.py       # mints this service's own IAM machine identity
   python main.py                                  # serves http://localhost:8002
   # once ANTHROPIC_API_KEY/AZURE_OPENAI_* are set in .env:
   python scripts/seed_models_and_agents.py        # registers models + creates the 7 starter agents
   ```
   Log in as the bootstrap admin against `iam-service`, then `POST /api/v1/agents/{id}/publish`
   each agent to mint its IAM Service Principal invoke credential (shown once) - or just do this
   from `agent-builder-console` (step 6) once it's running.

3. **talentos-app** (backend)
   ```bash
   cd backend/talentos-app
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_app;
   alembic upgrade head
   # fill in the 7 agents' *_AGENT_CLIENT_ID/_CLIENT_SECRET pairs from step 2 into .env
   python main.py          # serves http://localhost:8000
   ```

4. **portal** (separate terminal)
   ```bash
   cd frontend/portal
   npm install
   cp .env.example .env
   npm run dev              # serves http://localhost:5175
   ```

5. **iam-console** (separate terminal)
   ```bash
   cd frontend/iam-console
   npm install
   cp .env.example .env
   npm run dev              # serves http://localhost:5174
   ```

6. **agent-builder-console** (separate terminal)
   ```bash
   cd frontend/agent-builder-console
   npm install
   cp .env.example .env
   npm run dev              # serves http://localhost:5176
   ```

7. **talentos-app** (frontend, separate terminal)
   ```bash
   cd frontend/talentos-app
   npm install
   cp .env.example .env
   npm run dev              # serves http://localhost:5173
   ```

Each service's default `.env` already points at the others on these ports.

## End-to-end flow

1. Visit `portal` (`:5175`) and log in with your organization's credentials.
2. Pick a tile - only the apps you have permission to use are shown:
   - **TalentOS** - analyze a JD (`/requirements`) and a resume (`/applicants`), pair them into
     a submission (`/submissions/new`, runs the match analysis), start an assessment, generate
     questions per skill/type, answer them (with Run/Run-all-testcases for coding), Final
     submit, see the score card.
   - **Agent Builder** - register a model, create an agent (prompt + model + limits), publish
     it to mint its IAM invoke credential, watch its usage log.
   - **IAM Console** - manage organizations, users, roles, role assignments, service
     principals, and review the full audit trail.
3. Any tile you open carries your session with you - no second login.

Every action above is permission-gated (an unassigned user gets a 403, not just a hidden button)
and every authentication event, permission decision, and data mutation is recorded in
`iam-service`'s audit log with who, what, when, and the result.
