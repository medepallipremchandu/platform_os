# TalentOS

AI-assisted hiring platform: four backend services (each with its own database) plus five React
frontends, all secured by a single enterprise IAM layer with one shared login.

- **IAM** (`iam-service` + `iam-console`) - Organizations, Users, Roles, Permissions, Role
  Assignments, and Service Principals, Azure-AD/Entra-style. Every other service authenticates
  against it and enforces permissions from it; every authentication event, permission decision,
  and business-data mutation platform-wide lands in its audit log, timestamped.
- **Portal** (`portal`) - the platform's one login page. Log in once, then launch whichever of
  the other apps you have access to; each hands your session to the other, so there's no second
  login.
- **JD analysis, resume analysis, submissions & matching, interview assessment** - the
  recruiting flow (`talentos-app` backend + frontend): analyze a JD and a resume, pair them into
  a submission with an enterprise-grade match analysis, generate and run a real interview
  (descriptive/MCQ/coding, with actual code execution), evaluate, produce a score card.
- **Agent builder** (`agent-builder-service` + `agent-builder-console`) - every AI call above
  goes through a published *agent* (a prompt template bound to a model, with limits), not a
  hardcoded prompt/model in application code. Models, prompts, and limits are all managed here,
  Azure-AI-Foundry style; each agent's invoke credential is itself an IAM-issued, resource-bound
  Service Principal.
- **Voice agent** (`voice-agent-service` + `voice-agent-console`) - an AI voice-calling platform
  capability: register telephony provider credentials (Twilio, extensible), define reusable
  "call agent" configs (a conversation script + a configurable no-answer/busy retry policy), and
  place outbound AI-driven phone calls that carry on a real spoken conversation, extract
  structured fields, and produce a summary. Every provider and call-agent config can be exposed
  to the whole organization or restricted to specific people. The conversation itself is just
  another published agent in `agent-builder-service` - no second AI-credential system exists.
  `talentos-app` uses it to let a JD carry a call-screening config, then place and review AI
  phone screens per candidate submission.

## Layout

```
backend/
  iam-service/               Platform superadmins, Organizations (+ their permission ceilings),
                              Users, Roles, Permissions, Role Assignments, Service Principals,
                              JWT/JWKS issuance, platform-wide audit log.
                              DB: talentos_iam. Port 8113.
  notification-service/      Transactional email, and the per-organization email/queue provider
                              configuration behind it. Celery worker + a small config API.
                              DB: talentos_notifications. Port 8104.
  agent-builder-service/     Model catalog + agents (prompts/limits) + /invoke. DB:
                              talentos_agent_builder. Port 8102.
  talentos-app/              JD analysis, resume analysis, submissions/matching, interview
                              sessions, question generation, evaluation, score card, JD
                              call-screening config + per-submission AI phone screens.
                              DB: talentos_app. Port 8000.
  voice-agent-service/       Telephony provider credentials, call agent configs (script + retry
                              policy), outbound AI calls, transcripts, summaries. DB:
                              talentos_voice_agent. Port 8004.
frontend/
  portal/                     The one login page + launcher, plus the set-password page both
                               invites and forgot-password land on. Port 5175.
  iam-console/                Admin console: organizations (superadmin), users, roles, role
                               assignments, service principals, notification providers, audit
                               log. Port 5174.
  agent-builder-console/      Models + agents management. Port 5176.
  voice-agent-console/        Telephony providers, call agent configs, calls/transcripts/
                               summaries. Port 5177.
  talentos-app/                The recruiting UI: requirements, applicants, submissions,
                               interviews, JD call-screening config, candidate call history.
                               Port 5173.
```

`iam-console`, `agent-builder-console`, `voice-agent-console`, and `talentos-app` (frontend) are
all pure relying-party apps with **no login form of their own** - each checks for a valid session
and, if it doesn't have one, redirects to `portal` with `?return_to=<its own URL>`. After logging
in once, `portal` hands the session to whichever app the user picks via a one-time token handoff
in the URL fragment, which the receiving app consumes on load and immediately strips from the
address bar. `portal`'s launcher only shows a tile for an app the user actually has permission to
use (decoded from the access token's `permissions` claim).

`talentos-app` (backend), `agent-builder-service`, and `voice-agent-service` hold all business
logic; none has its own user/role/permission model - all three are relying parties of
`iam-service`, validating its RS256-signed JWTs locally (via its published JWKS) and enforcing a
`talentos.<service>.<resource>.<action>` permission on every mutating and most read endpoints.
`talentos-app` (backend) has no model/provider/prompt code of its own - every AI step calls
`agent-builder-service`'s `/invoke` endpoint, authenticating with a Bearer token obtained by
exchanging that agent's IAM Service Principal credentials; `voice-agent-service` does the same
for its conversation-turn/summary agents. `talentos-app` also holds its own IAM Service Principal
(role: "Voice Agent Contributor") to call `voice-agent-service` on a recruiter's behalf when a
call is triggered from a submission. See each service's README for detail, and
`docs/superpowers/specs/2026-08-24-iam-service-design.md` for the full IAM design.

## Running everything (after first-time setup)

Once each service has its venv, database and `.env` in place (see **First-time setup** below),
use the control script rather than eleven terminals:

```powershell
platform_os\scripts\services.ps1            # status table for every backend + frontend
platform_os\scripts\services.ps1 restart    # stop everything, start it again, in dependency order
platform_os\scripts\services.ps1 stop
platform_os\scripts\services.ps1 start -Backend
platform_os\scripts\services.ps1 restart -Only iam-service,iam-console
```

Each service opens in its own titled PowerShell window so logs stay readable per service.
`status` also flags a **phantom listener** - a socket stuck in LISTEN with no surviving process,
which keeps serving stale code and refuses new binds. That has cost this repo ports 8002, 8003
and 8103; the only remedy that works is moving the service and repointing every consuming
`.env`.

## First-time setup (local)

Start in this order - each depends on the one(s) before it being reachable.

1. **iam-service**
   ```bash
   cd backend/iam-service
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_iam;
   alembic upgrade head
   python scripts/generate_signing_key.py       # writes the RS256 keypair under keys/
   python main.py                                # serves http://localhost:8113
   # in another terminal:
   python scripts/seed_permissions_and_roles.py   # seeds the permission catalog + built-in roles
   python scripts/bootstrap.py                    # seeds the ONE platform administrator
   ```

   `bootstrap.py` seeds a single account: the platform administrator
   (`BOOTSTRAP_ADMIN_EMAIL`, default `admin@talentos-platform.com`). It belongs to no
   organization - that absence *is* the tier - and it holds unrestricted platform access.
   Everything else, organizations included, is created from iam-console by that account.

2. **notification-service** (needed for invite / password-reset email; iam-service starts fine
   without it, and just logs the links instead)
   ```bash
   cd backend/notification-service
   python -m venv .venv && .venv\Scriptsctivate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_notifications;
   cp .env.example .env
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   #   -> paste into PROVIDER_SECRET_KEY in .env
   alembic upgrade head
   python run_worker.py                            # the Celery worker (Windows: --pool=solo, the default)
   # in another terminal, for the provider-configuration API:
   uvicorn app.main:app --port 8104
   ```

3. **agent-builder-service**
   ```bash
   cd backend/agent-builder-service
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_agent_builder;
   alembic upgrade head
   python scripts/bootstrap_iam_identity.py       # mints this service's own IAM machine identity
   python main.py                                  # serves http://localhost:8102
   # once ANTHROPIC_API_KEY/AZURE_OPENAI_* are set in .env:
   python scripts/seed_models_and_agents.py        # registers models + creates the 7 starter agents
   ```
   Log in as the bootstrap admin against `iam-service`, then `POST /api/v1/agents/{id}/publish`
   each agent to mint its IAM Service Principal invoke credential - or just do this from
   `agent-builder-console` (step 6) once it's running.

4. **voice-agent-service**
   ```bash
   cd backend/voice-agent-service
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_voice_agent;
   alembic upgrade head
   python scripts/bootstrap_iam_identity.py        # mints this service's own IAM machine identity
   python scripts/seed_call_agents.py              # registers + publishes its 3 conversation agents
   python main.py                                   # serves http://localhost:8004
   ```
   Placing a real outbound call needs a real Twilio account and a publicly-reachable `BASE_URL`
   (a tunnel - see the service's own README) for Twilio's webhooks to reach it; everything else
   (providers, call agent configs, the retry scheduler) works without one.

5. **talentos-app** (backend)
   ```bash
   cd backend/talentos-app
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   # CREATE DATABASE talentos_app;
   alembic upgrade head
   # fill in the 7 agents' *_AGENT_CLIENT_ID/_CLIENT_SECRET pairs from step 2 into .env
   python scripts/bootstrap_voice_agent_identity.py   # mints this service's voice-agent-service identity
   python main.py          # serves http://localhost:8000
   ```

6. **portal** (separate terminal)
   ```bash
   cd frontend/portal
   npm install
   cp .env.example .env
   npm run dev              # serves http://localhost:5175
   ```

7. **iam-console**, **agent-builder-console**, **voice-agent-console**, **talentos-app**
   (frontend) - each in its own terminal:
   ```bash
   cd frontend/<app>
   npm install
   cp .env.example .env
   npm run dev
   ```
   (ports 5174, 5176, 5177, 5173 respectively)

Each service's default `.env` already points at the others on these ports.

## End-to-end flow

1. Visit `portal` (`:5175`) and log in with your organization's credentials.
2. Pick a tile - only the apps you have permission to use are shown:
   - **TalentOS** - analyze a JD (`/requirements`) and a resume (`/applicants`), pair them into
     a submission (`/submissions/new`, runs the match analysis), start an assessment, generate
     questions per skill/type, answer them, Final submit, see the score card. On a JD, set its
     "Call screening" config; on a submission, trigger an AI phone screen and review the
     transcript/summary inline.
   - **Agent Builder** - register a model, create an agent, publish it, watch its usage log.
   - **Voice Agent** - register a telephony provider's credentials, create a call agent config
     (persona/objective/fields to extract/retry policy), place/review calls directly.
   - **IAM Console** - manage organizations, users, roles, role assignments, service
     principals, and review the full audit trail.
3. Any tile you open carries your session with you - no second login.

Every action above is permission-gated (an unassigned user gets a 403, not just a hidden button)
and every authentication event, permission decision, and data mutation is recorded in
`iam-service`'s audit log with who, what, when, and the result.
