# TalentOS Voice Agent Service

An AI voice-calling platform capability: any application (including this platform's own
`talentos-app`) registers telephony provider credentials, defines a reusable **call agent** (a
conversation script + retry policy), and places outbound AI-driven phone calls that carry on a
real spoken conversation, extract structured data, and produce a summary.

This service is a **relying party** on `iam-service` (default `http://localhost:8003`, see
`d:/TalentOS_All_Services/platform_os/docs/superpowers/specs/2026-08-24-iam-service-design.md`)
and delegates all conversation generation to `agent-builder-service` (default
`http://localhost:8002`) - there is no direct model/provider call or per-org AI credential in
this codebase at all.

## Concepts

- **TelephonyProviderConfig**: a registered telephony account (e.g. Twilio) an org can dial
  through. `provider` is an open string with a small adapter registry
  (`app/providers/telephony.get_telephony_provider`), not an enum - adding a new provider is one
  new adapter class + one registry entry. Credentials are Fernet-encrypted at rest
  (`CREDENTIAL_ENCRYPTION_KEY`) and never returned in any API response.
- **CallAgentConfig**: a reusable script (persona/objective/consent line/closing line/fields to
  extract) + retry policy (`retry_max_attempts`, `retry_interval_minutes`, `retry_on_statuses`) +
  which `TelephonyProviderConfig` to dial through. Editing it later never changes an in-flight or
  historical `Call` - every `Call` snapshots the script and retry policy it was created with.
- **Call**: one actual call attempt, driven by the state machine in `app/core/state_machine.py`
  (`CREATED -> QUEUED -> DIALING -> RINGING -> CONNECTED -> CONSENT_PENDING -> CONVERSATION ->
  SUMMARY -> COMPLETED`, with `BUSY`/`NO_ANSWER`/`FAILED`/`DISCONNECTED`/`TIMEOUT`/`CANCELLED`/
  `CALL_BLOCKED`/`CONSENT_DENIED` as terminal states). Twilio's webhooks
  (`/webhooks/twilio/voice/{call_id}`, `/webhooks/twilio/status/{call_id}`) drive the whole
  in-call turn loop and terminal-status transitions.
- **Conversation generation**: delegated entirely to `agent-builder-service` via 3 published
  agents (Consent Turn, Main Conversation Turn, Summary - see `scripts/seed_call_agents.py`),
  invoked through `app/services/conversation_client.py`. This is a deliberate architectural
  choice: the reference implementation this service was built from had its own per-org AI
  provider/credential system; that's redundant with `agent-builder-service`, the platform's
  single canonical place for model/prompt/agent management, so it isn't reproduced here.
- **Visibility**: a `TelephonyProviderConfig` or `CallAgentConfig` with `visibility="organization"`
  is listable/usable by anyone in the org holding the right permission. One with
  `visibility="restricted"` is listable/usable only by its creator plus whoever has a row in its
  Grant table - **except** a caller whose token has `principal_type == "service_principal"` (a
  machine caller acting on the org's behalf), which always sees every org-scoped resource
  regardless of visibility. Enforced in `app/services/visibility.py`, used by both the provider
  and call-agent service layers.
- **Retry**: when a `Call` reaches a terminal state that is in its own `retry_on_statuses` AND
  `attempt_number < retry_max_attempts`, `next_retry_at` is stamped
  (`app/services/calls_service.transition`). A background asyncio loop
  (`app/services/retry_poller.py`, started from `main.py`'s lifespan, polling every
  `RETRY_POLL_INTERVAL_SECONDS`) finds due retries and places a brand-new `Call` row (same
  script/provider/webhook/metadata, `attempt_number+1`, `root_call_id` pointing at the first
  attempt), dialed exactly like a fresh call.

## Setup

```bash
# CREATE DATABASE talentos_voice_agent;
cp .env.example .env   # set CREDENTIAL_ENCRYPTION_KEY, BOOTSTRAP_ORGANIZATION_ID, BASE_URL

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python main.py          # serves http://localhost:8004
```

### IAM bootstrap (one-time, per environment)

This service mints its own machine identity, used only to post system-attributed audit events
for the two Twilio webhook routes (which have no end-user bearer token of their own - Twilio
calls them, not IAM):

```bash
# with iam-service running and IAM_BOOTSTRAP_ADMIN_EMAIL/PASSWORD + BOOTSTRAP_ORGANIZATION_ID set
python scripts/bootstrap_iam_identity.py
```

Prints `IAM_CLIENT_ID`/`IAM_CLIENT_SECRET` to copy into `.env`. Idempotent.

### Conversation agents (one-time, per environment)

```bash
# with agent-builder-service running and already having at least one active Model registered
# (run agent-builder-service's own scripts/seed_models_and_agents.py first if not)
python scripts/seed_call_agents.py
```

Registers and publishes 3 agents in agent-builder-service (Consent Turn, Main Conversation Turn,
Summary - prompts ported from the reference implementation's
`app/services/conversation.py` into `{{variable}}` template syntax) and prints their
`CLIENT_ID`/`CLIENT_SECRET` pairs to copy into `.env`.

### Twilio / public URL (needed only for a real, live call)

Twilio must be able to POST back into this service's `/webhooks/twilio/*` routes over the public
internet. **`localhost` is not reachable by Twilio** - local dev needs a tunnel:

```bash
ngrok http 8004                                # BASE_URL=https://<random>.ngrok-free.app
# or
cloudflared tunnel --url http://localhost:8004  # BASE_URL=https://<random>.trycloudflare.com
```

Set `BASE_URL` in `.env` to the tunnel's `https://` URL and restart. Without this, a call will
dial and ring but never progress past `DIALING`/`RINGING` - Twilio has nowhere to deliver the
`<Gather>` turn-loop callbacks. Everything else in this service (providers, call-agents, calls
CRUD, visibility rules, idempotency, retry scheduling, cancellation) works without a tunnel.

## API

Every route except `/health` and the two `/webhooks/twilio/*` routes requires a valid
iam-service-issued `Authorization: Bearer <token>` carrying the listed permission.
`organization_id` on every created resource is always taken from the verified token, never the
request body.

| Method | Path                                | Permission                                | Description |
|--------|--------------------------------------|--------------------------------------------|--------------|
| GET    | `/health`                             | none                                        | Liveness check |
| POST   | `/providers`                          | `talentos.voiceagent.providers.manage`      | Register a telephony provider config |
| GET    | `/providers`                          | `talentos.voiceagent.providers.read`        | List (visibility-filtered), never includes credentials |
| DELETE | `/providers/{id}`                     | `talentos.voiceagent.providers.manage`      | Revoke |
| POST   | `/call-agents`                        | `talentos.voiceagent.callagents.write`      | Create a call agent config |
| GET    | `/call-agents`                        | `talentos.voiceagent.callagents.read`       | List (visibility-filtered) |
| GET    | `/call-agents/{id}`                   | `talentos.voiceagent.callagents.read`       | Fetch one |
| PATCH  | `/call-agents/{id}`                   | `talentos.voiceagent.callagents.write`      | Update |
| DELETE | `/call-agents/{id}`                   | `talentos.voiceagent.callagents.write`      | Soft-delete (`is_active=false`) |
| POST   | `/calls`                              | `talentos.voiceagent.calls.write`           | Place a call (saved config or fully inline). Supports `Idempotency-Key` header. Returns 202. |
| GET    | `/calls`                              | `talentos.voiceagent.calls.read`            | List (org-scoped, paginated) |
| GET    | `/calls/{id}`                         | `talentos.voiceagent.calls.read`            | Fetch one |
| GET    | `/calls/{id}/events`                  | `talentos.voiceagent.calls.read`            | Lifecycle event log |
| GET    | `/calls/{id}/conversation`            | `talentos.voiceagent.calls.read`            | Turn-by-turn transcript |
| GET    | `/calls/{id}/summary`                 | `talentos.voiceagent.calls.read`            | Generated summary + final extracted fields |
| POST   | `/calls/{id}/cancel`                  | `talentos.voiceagent.calls.write`           | Cancel (`{"graceful": bool}`) |
| POST   | `/webhooks/twilio/voice/{call_id}`    | *(Twilio signature, not IAM)*                | Turn-loop callback |
| POST   | `/webhooks/twilio/status/{call_id}`   | *(Twilio signature, not IAM)*                | Provider status callback |

### `POST /calls` body

Either:
```json
{"call_agent_config_id": "...", "to_number": "+1...", "webhook_url": null, "metadata": {}}
```
or fully inline (no saved config - `retry_max_attempts` is always `0` for an inline call, since
there's no config to carry a retry policy):
```json
{
  "to_number": "+1...",
  "telephony_provider_config_id": "...",
  "call_script": {"persona": "...", "objective": "...", "consent_line": "...", "closing_line": "...", "fields": []},
  "max_conversation_duration_minutes": 5,
  "webhook_url": null,
  "metadata": {}
}
```

## Security notes

- Telephony credentials are encrypted at rest with Fernet (`CREDENTIAL_ENCRYPTION_KEY`) and never
  appear in any API response, at creation or afterward.
- Every resource is scoped to exactly one organization, taken from the caller's verified token.
- Visibility (`organization`/`restricted`) is enforced in the service layer
  (`app/services/visibility.py`), not just hidden in the UI - a `service_principal` caller always
  bypasses `restricted` visibility, since per-user restriction is a human-permission concept.
- The two Twilio webhook routes authenticate via `X-Twilio-Signature`, verified against the
  organization's stored, decrypted Twilio auth token - never an IAM bearer token, since Twilio
  itself calls them. Because there's no inbound bearer token to attribute an audit event to,
  these two routes post their audit events using this service's own machine identity
  (`app/core/iam_client.get_service_token`) - i.e. as a system actor, once per webhook request
  (chosen over skipping audit entirely for these routes, so lifecycle events triggered by Twilio
  still show up in the audit trail, just attributed to the service rather than a human).
- Callee/candidate speech is always carried in a JSON *variable* passed to agent-builder-service,
  never interpolated into instruction text - mitigates prompt injection (same rule the reference
  implementation followed).

## Tests

```bash
pytest
```

33 tests covering: health/auth/permission checks, provider CRUD + credential-never-returned +
visibility (organization/restricted/creator/service-principal-bypass), call-agent CRUD +
visibility + soft-delete, call creation (saved-config and inline paths) + idempotency + cancel +
organization scoping, the call state machine, retry scheduling on `transition()`, the retry
poller (`run_once`) driven directly against manipulated `next_retry_at` values with the telephony
provider stubbed out, and `conversation_client`'s variable-building/error-handling against a
stubbed `httpx.AsyncClient`. None of this requires a real Twilio account or a running
agent-builder-service/iam-service - the test suite mints its own signed tokens
(`tests/conftest.py`, same pattern as `talentos-app/tests/conftest.py`) and stubs every outbound
network call.

## Live verification performed

Against a real, running Postgres 5432, `iam-service` (`localhost:8003`), and
`agent-builder-service` (`localhost:8002`):

- `alembic upgrade head` against a fresh `talentos_voice_agent` database - succeeded.
- Full `pytest` suite - **33/33 passed**.
- `scripts/bootstrap_iam_identity.py` - ran for real, minted a `voice-agent-service`
  `ServicePrincipal` in iam-service with the `Organization Admin` role, `IAM_CLIENT_ID`/
  `IAM_CLIENT_SECRET` written to `.env`.
- `scripts/seed_call_agents.py` - ran for real against agent-builder-service, created + published
  all 3 conversation agents (`AGT08`/`AGT09`/`AGT10`), all 3 `CLIENT_ID`/`CLIENT_SECRET` pairs
  written to `.env`.
- Started the service; `GET /health` returns `200 {"status":"ok"}` with no auth.
- `GET /providers`, `/call-agents`, `/calls` all return **401** with no token.
- With a real admin access token from iam-service (carrying the real, currently-seeded
  `talentos.voiceagent.*` permissions - confirmed by inspecting the token's own `permissions`
  claim), all three return **200** with `{"items": []}`.
- Created a `TelephonyProviderConfig` with fake Twilio-shaped credentials: response and every
  subsequent `GET`/list never include `credentials` or `encrypted_credentials`.
- Created a `CallAgentConfig` referencing that provider - succeeded, snapshot fields correct.
- Created a **restricted** provider as the admin user; confirmed a real client-credentials token
  minted for voice-agent-service's own `service_principal` identity (`principal_type ==
  "service_principal"`) sees it in `GET /providers` even without a grant - the bypass rule,
  proven live end-to-end against the real database and real iam-service tokens.
- Placed a live inline call through the real Twilio SDK with intentionally-fake credentials: it
  correctly progressed `CREATED -> QUEUED`, attempted the real Twilio API call, got a real `401
  Authentication Error` back from Twilio, and transitioned to `FAILED` with
  `end_reason: PROVIDER_ERROR` - the event log shows all three transitions with Twilio's actual
  error text. Cancelling an already-terminal call correctly returned `409`.
- Ran the retry poller (`retry_poller.run_once`) directly against the live database: inserted a
  `Call` row with `next_retry_at` in the past, ran the poller, and it created a real successor
  `Call` (`attempt_number=2`, `root_call_id` pointing at the original, dialed for real through the
  Twilio SDK - failed again on the fake credentials, as expected) and cleared the original's
  `next_retry_at`.

**What was not verified, and why (expected, per the task's own scope):**
- No real Twilio account or public tunnel was available in this sandboxed environment, so no
  call ever actually rang a phone or drove a live `/webhooks/twilio/voice` turn loop end to end.
  Every `FAILED` result above is Twilio correctly rejecting fake credentials over a real network
  call - i.e. the integration itself is proven, just not against a real phone call. The
  `/webhooks/twilio/*` handlers' turn-loop logic (consent gather -> conversation turns -> summary)
  is instead covered by porting/adapting the reference implementation's already-working
  orchestration and by `conversation_client`'s own unit tests against a stubbed
  `agent-builder-service`.
- The "restricted resource is hidden from a **different human user**" half of the visibility
  matrix (as opposed to the creator, and as opposed to the service-principal bypass, both proven
  live above) was verified via the automated pytest suite (real Postgres, real FastAPI app,
  locally-signed test tokens - `tests/test_providers.py::test_restricted_provider_hidden_from_other_user_until_granted`,
  `tests/test_call_agents.py::test_restricted_call_agent_visibility`) rather than a second live
  IAM login: minting a second real, logged-in human user requires completing iam-service's
  invite-acceptance email flow, which is orthogonal to voice-agent-service itself and not
  something this service can drive from the outside.

## Deviations / judgment calls from the spec

- JSON field names are `snake_case` throughout (matching this platform's convention in
  `agent-builder-service`/`talentos-app`), not the reference implementation's `camelCase`.
- `Call` carries `telephony_provider_config_id` and a `retry_max_attempts`/`retry_interval_minutes`/
  `retry_on_statuses` snapshot directly (not just `call_agent_config_id`), so a fully inline call
  (no saved `CallAgentConfig`) still has a self-contained retry policy and the webhook handlers
  never need to re-resolve a `CallAgentConfig` to find the provider to verify a signature against.
- In-call turn-loop counters (`silence_count`, `consent_retry_count`, `warned_2min`,
  `warned_1min`) are dedicated `Call` columns, not folded into the tenant-facing `metadata` field
  the way the reference implementation did - avoids ever silently mutating caller-supplied
  metadata.
- `CallResponse` additionally exposes `retry_max_attempts`/`retry_interval_minutes`/
  `retry_on_statuses` (not explicitly listed in the spec's API surface) so a caller can see
  whether/when a given call might still retry.
- Grants (`TelephonyProviderConfigGrant.user_id`, `CallAgentConfigGrant.user_id`) key off the same
  actor-identity string as `created_by` (`CurrentActor.email_or_name`) rather than a separate
  user-id column, since the spec's own model listing doesn't define one and this keeps creator
  and grant checks consistent.
