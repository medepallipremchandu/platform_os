# TalentOS Agent Builder Service

The AI control plane for the whole platform - an Azure-AI-Foundry-style layer for managing
model deployments and the agents built on top of them. No other service hardcodes a model,
provider, or prompt: every AI task is a published **agent**, invoked with an IAM-issued
credential.

This service is a **relying party** on `iam-service` (the platform's identity/authorization
control plane, default `http://localhost:8003`): every admin endpoint requires a verified
`Authorization: Bearer <token>` issued by iam-service, carrying the right permission; every
agent's invoke credential is an iam-service `ServicePrincipal`, not a locally-generated key.
See `d:/TalentOS_All_Services/platform_os/docs/superpowers/specs/2026-08-24-iam-service-design.md`
for the full design.

## Concepts

- **Organization**: every model and agent belongs to exactly one organization
  (`organization_id`, set server-side from the caller's verified token - never from the
  request body). List/get endpoints are always scoped to the caller's organization.
- **Model**: a registered, ready-to-use deployment (Claude or Azure OpenAI), with credentials
  encrypted at rest. Admins register these once; everyone else just picks from the list.
- **Agent**: a prompt template (`{{variable}}` placeholders) bound to a primary model (and an
  optional fallback model for resilience), with limits (max output tokens, timeout, rate
  limit). Starts as a **draft**; **publish** it to mint an invoke credential; **archive** it
  (soft-delete - the row is never removed) to retire it. An archived agent can never be
  re-published or invoked, and its invoke credential is revoked in iam-service the moment it's
  archived so it can't mint a new access token either. `GET /agents` excludes archived agents
  by default - pass `include_archived=true` to see them.
- **Agent invoke credential**: on first publish, this service calls iam-service's
  `POST /service-principals` (using its own machine identity - see "IAM bootstrap" below) to
  mint a *resource-bound* `ServicePrincipal` (`resource_type=agent`, `resource_id=<agent id>`).
  The returned `client_id`/`client_secret` pair is this agent's credential - the `client_secret`
  is shown exactly once, never recoverable after that. `POST /agents/{id}/keys/regenerate`
  rotates it via iam-service's `POST /service-principals/{id}/secret/rotate`.
- **Invocation log**: every `/invoke` call is recorded (success/failure, provider used,
  latency) - the audit trail an enterprise deployment needs for usage tracking and debugging.

## Setup

```bash
# CREATE DATABASE talentos_agent_builder;
cp .env.example .env   # set ENCRYPTION_KEY (see comment in the file) and DATABASE_URL

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python main.py          # serves http://localhost:8002
```

### IAM bootstrap (one-time, per environment)

This service needs its own machine identity in iam-service to call the
service-principal-management endpoints on `/publish`/`/keys/regenerate` - separate from, and
more privileged than, the permission an end user needs to click "Publish"
(`talentos.agentbuilder.agents.publish`).

```bash
# with iam-service running and IAM_BOOTSTRAP_ADMIN_EMAIL/PASSWORD + BOOTSTRAP_ORGANIZATION_ID set in .env
python scripts/bootstrap_iam_identity.py
```

This logs into iam-service as the org's bootstrap admin, creates a `ServicePrincipal` named
`agent-builder-service`, grants it the built-in **Organization Admin** role (which carries
`talentos.iam.service_principals.manage`) at organization scope, and prints a `client_id`/
`client_secret` pair to copy into `.env` as `IAM_CLIENT_ID`/`IAM_CLIENT_SECRET`. Idempotent -
safe to re-run once those are set.

### Organization-scoping an existing database

If this database predates organization scoping, run, in order:

```bash
alembic upgrade 0002                       # adds organization_id, nullable
python scripts/backfill_organization_id.py # sets it on every existing row (BOOTSTRAP_ORGANIZATION_ID)
alembic upgrade head                       # 0003 (credential table restructure) + 0004 (NOT NULL)
```

To seed the starter catalog used by talentos-app (Claude + Azure OpenAI models,
plus the 7 agents for JD analysis, resume analysis, matching, question generation x3 types,
and descriptive-answer grading):

```bash
# fill in ANTHROPIC_API_KEY / AZURE_OPENAI_* in .env first (see the "Seed-only" section)
python scripts/seed_models_and_agents.py
```

This prints each agent's `client_secret` **exactly once** - copy them into
`talentos-app/.env`.

## API

Every route (except `/health`) requires a valid iam-service-issued `Authorization: Bearer
<token>`; every admin route additionally requires a specific permission from that token's
`permissions` claim. `/invoke` is the one exception - it's authenticated by a resource-bound
service-principal token instead of a permission check (see below).

| Method | Path                                   | Required permission                          | Description                                  |
|--------|-----------------------------------------|-----------------------------------------------|-----------------------------------------------|
| GET    | `/health`                               | none                                           | Liveness check                                 |
| POST   | `/api/v1/models`                        | `talentos.agentbuilder.models.manage`          | Register a model deployment                    |
| GET    | `/api/v1/models`                        | `talentos.agentbuilder.agents.read`            | List active models (this org only)             |
| GET    | `/api/v1/models/{id}`                   | `talentos.agentbuilder.agents.read`            | Fetch a model (this org only)                  |
| PATCH  | `/api/v1/models/{id}`                   | `talentos.agentbuilder.models.manage`          | Rename and/or re-enter credentials in place     |
| DELETE | `/api/v1/models/{id}`                   | `talentos.agentbuilder.models.manage`          | Deactivate a model                             |
| POST   | `/api/v1/agents`                        | `talentos.agentbuilder.agents.write`           | Create a draft agent                           |
| GET    | `/api/v1/agents`                        | `talentos.agentbuilder.agents.read`            | List agents (this org only, `?include_archived=true` to include archived) |
| GET    | `/api/v1/agents/{id}`                   | `talentos.agentbuilder.agents.read`            | Fetch an agent (incl. prompt, limits, model)   |
| PATCH  | `/api/v1/agents/{id}`                   | `talentos.agentbuilder.agents.write`           | Edit a draft (re-derives input_variables)      |
| POST   | `/api/v1/agents/{id}/publish`           | `talentos.agentbuilder.agents.publish`         | Publish - mints an invoke credential once      |
| DELETE | `/api/v1/agents/{id}`                   | `talentos.agentbuilder.agents.publish`         | Archive (soft-delete) - revokes its invoke credential immediately |
| POST   | `/api/v1/agents/{id}/keys/regenerate`   | `talentos.agentbuilder.agents.manage_keys`     | Rotate the credential (old one stops working)  |
| GET    | `/api/v1/agents/{id}/keys`              | `talentos.agentbuilder.agents.manage_keys`     | List credential previews (never the secret)    |
| GET    | `/api/v1/agents/{id}/usage`             | `talentos.agentbuilder.agents.read`            | Last 100 invocation log entries                |
| POST   | `/api/v1/invoke`                        | *(resource-scope check, not a permission)*     | Run a published agent with a set of variables  |

Permission mapping rationale: `agents.write` covers routine draft edits (create/PATCH);
`agents.publish` covers agent *lifecycle* transitions that mint or revoke the invoke credential
(publish and archive alike - archive is publish's mirror image); `agents.manage_keys` is
reserved for credential-only operations (rotate/list) that don't otherwise change the agent's
lifecycle state; `models.manage` covers every model mutation (create/PATCH/deactivate), since
model credentials are always more sensitive than agent metadata.

Every mutation (create/update/publish/archive/rotate/delete on models and agents) posts an
audit event to iam-service's `POST /audit/events`, attributed to the caller whose bearer token
made the request.

### Calling `/invoke` (for `talentos-app` or any other consumer)

`/invoke` no longer accepts `X-Agent-Key`. Instead:

1. Exchange an agent's `client_id`/`client_secret` (from publish/regenerate above) for a
   short-lived access token via iam-service:

   ```bash
   curl -X POST http://localhost:8003/auth/token \
     -H "Content-Type: application/json" \
     -d '{"client_id": "<client_id>", "client_secret": "<client_secret>"}'
   ```

   Cache the returned `access_token` until shortly before its `expires_in` (15 minutes) and
   refresh by repeating the exchange - do not do this exchange per-invocation.

2. Call `/invoke` with that token:

   ```bash
   curl -X POST http://localhost:8002/api/v1/invoke \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{"variables": {"jd_text": "..."}}'
   ```

   The agent to invoke is resolved from the token's `resource_scope` claim - there is no
   agent-identifying path parameter or request field, same as the old
   `X-Agent-Key`-identifies-the-agent behavior. A token not scoped to an agent gets `403`; an
   invalid/expired token gets `401`; an agent that doesn't exist or isn't published gets `404`.

## Security notes

- Model provider credentials are encrypted at rest with Fernet (`ENCRYPTION_KEY`). Generate
  your own for anything beyond local dev - the shipped default is for local development only.
- Agent invoke credentials (`client_secret`) are never stored by this service at all - only
  iam-service holds the hash. This service stores only the `service_principal_id` and the
  (safe-to-display) `client_id`.
- Every model/agent is scoped to exactly one organization (`organization_id`, always taken
  from the caller's verified token, never the request body); list/get endpoints filter to the
  caller's own organization.
- This service validates iam-service's JWTs locally against its published JWKS - no
  synchronous call to iam-service on the request path for ordinary admin/read requests.

## Tests

```bash
pytest
```
