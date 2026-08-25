# Organization-level logins + notifications — **complete**

Originally a handoff for work killed mid-flight by a spend limit. That work is now finished, and
this document records what was built and the two decisions that differ from the original plan.

Everything below is implemented, tested and **verified live** against running services.

---

## Platform state

5 backend services + 5 frontends, all IAM-secured:

| Service | Port | DB | Tests |
|---|---|---|---|
| `backend/iam-service` | **8113** | `talentos_iam` | 53 |
| `backend/notification-service` | **8104** | `talentos_notifications` | 40 |
| `backend/agent-builder-service` | **8102** | `talentos_agent_builder` | — |
| `backend/talentos-app` | 8000 | `talentos_app` | — |
| `backend/voice-agent-service` | 8004 | `talentos_voice_agent` | — |
| `frontend/talentos-app` | 5173 | — | |
| `frontend/iam-console` | 5174 | — | |
| `frontend/portal` | 5175 | — | |
| `frontend/agent-builder-console` | 5176 | — | |
| `frontend/voice-agent-console` | 5177 | — | |

**Note the non-default ports**: `iam-service` is on **8113** and `agent-builder-service` on
**8102**. Ports 8002, 8003 and then 8103 each developed an unkillable phantom listener - a socket
still in LISTEN with no surviving process record, surviving `Stop-Process`, `taskkill` and a long
wait - serving stale code and refusing new binds. Moving the service and repointing every
consuming `.env` is the accepted remedy here; it has now been needed three times.

`iam-service/scripts/bootstrap.py` seeds exactly one account:

| | Email | Password | Org |
|---|---|---|---|
| Platform administrator | `admin@talentos-platform.com` | `change-me-local-dev-password` | **none, by design** |

`is_superadmin = True`, so it satisfies every permission check and has unrestricted reach.
Organizations and their admins are created from iam-console by this account - there is no
starter organization any more.

---

## What was built

### 1. The superadmin tier (`iam-service`)

`User.is_superadmin` + an `is_superadmin` claim on every user access token, and a
`require_superadmin` dependency that is **a separate axis from `require_permission`** — a user
holding every `talentos.iam.*` permission is an extremely powerful org admin and is still
refused. Login has an explicit branch for a superadmin with no organization membership, issuing
`org_id: null`, `permissions: []`, `is_superadmin: true`.

### 2. Organization entitlement ceilings

`Organization.allowed_permissions` (JSONB; `NULL`/empty = unrestricted, so nothing that already
existed changed behaviour). Enforced in exactly one place —
`permission_service.resolve_permissions`, which runs on every token issuance — so a role granting
something outside the ceiling never reaches any token, and lowering a ceiling takes effect on the
very next token without rewriting a single role.

### 3. One-shot tenant provisioning

`POST /organizations` (superadmin-only) creates, in one transaction: the organization, its
ceiling, its first admin as a `status="invited"` user with no password, that admin's built-in
**Organization Admin** assignment, and the invite email. At least one permission code is
required.

### 4. `notification-service` — provider-based email **and** queue

Both axes are tenant-configurable, with one rule: *the organization's own enabled provider wins;
otherwise the platform default applies.*

* email providers: `smtp`, `sendgrid`, `console` (the log sink)
* queue providers: `postgres`, `redis`, `rabbitmq`, `sqs`

**Two-tier queueing.** Producers always publish `notifications.send_email` to the fixed platform
broker — a tenant misconfiguring their broker must never be able to break organization creation
or a password reset. The dispatcher then re-publishes `notifications.deliver_email` onto *that
organization's* broker if it has one (a worker started with `--organization <id>` consumes it),
or back onto the platform broker if it does not. If a tenant broker is unreachable, it falls back
to the platform broker and records that it did.

Adding a provider is one class plus one registry entry — the catalog endpoint, the console's
config form, validation, secret encryption and the "Test connection" button all derive from the
fields the class declares. Secrets are Fernet-encrypted and **write-only**: never returned, and
omitting one on an update keeps the stored value.

### 5. Unified invite / first-login / forgot-password

One token type, one endpoint. `POST /auth/password-reset/confirm` serves both, and also flips a
`status="invited"` user to `"active"`. There is deliberately no separate activation token or
`/auth/activate`. Both flows land on `portal`'s `/set-password`, which sits outside the session
guard.

### 6. Frontends

* **portal** — `SetPasswordPage` (`/set-password?token=…`) and `ForgotPasswordPage`, both outside
  the auth guard, plus a "Forgot your password?" link on the login form.
* **iam-console** — `isSuperAdmin()` (a flag check, kept distinct from `hasPermission`), a
  superadmin-only `OrganizationsPage` (list/search/sort every tenant, create with an admin +
  ceiling, edit entitlements, deactivate/reactivate), a `NotificationProvidersPage` whose forms
  are rendered from the backend's provider catalog, and a `RequireOrganization` route guard so a
  superadmin session with `org_id: null` never fires `organization_id=null` requests.

---

## Two decisions that differ from the original plan

**A superadmin can now scope a session to any active organization without a membership**
(`POST /auth/token/switch-org`). `GET /organizations` returns every organization to a superadmin,
so a switcher listing organizations they could not enter would have been a dead end. This grants
*scope*, not authority: permissions still come only from role assignments they actually hold
there, so the resulting token carries an empty permission list plus `is_superadmin`.

**The superadmin bypass is one-way, and that is the whole design.** A superadmin satisfies every
`require_permission` check; no set of permissions ever satisfies `require_superadmin`.

The bypass is not a convenience. A superadmin holds no org-scoped permissions at all, so without
it they could create a tenant and its first admin and then be permanently locked out of that
tenant - unable to appoint a replacement if the admin left. The endpoints it covers all take
their organization from the path or body rather than the caller's token, so it grants reach
without smuggling in ambient scope. `notification-service` implements the same rule in
`require_org_permission`.

---

## Two bugs worth remembering

**`CELERY_BROKER_URL` must never be a setting name.** `celery.app.utils.Settings.broker_url` is a
*property* that returns `os.environ["CELERY_BROKER_URL"]` ahead of anything the application
configures — a hard override, re-read on every access, and `Celery(broker=…)` is only "auto-set"
so it loses too. While notification-service's own setting had that name, **every tenant Celery app
silently came up pointed at the platform broker**: mail was still delivered, nothing errored, the
console still said "your Redis", and the tenant's queue was simply never used. The setting is now
`NOTIFICATIONS_BROKER_URL`, and `app/celery_app.py` strips both `CELERY_BROKER_URL` and
`CELERY_RESULT_BACKEND` from the environment (loudly) before building any app. Regression test:
`test_a_tenant_app_publishes_to_the_tenant_broker_not_the_platform_one`.

**Declare indexes on the model, not only in the migration.** The test database is built by
`Base.metadata.create_all()`, so a partial unique index that lived only in the Alembic migration
did not exist under test. The tests passed a swap-the-enabled-provider case that failed against a
real migrated database (the new enabled row collided with the incumbent, because siblings were
being disabled *after* the insert rather than before).

---

## Verified live, not just under test

Against real running services, a real Postgres/Kombu broker and a real second "tenant" broker
(`talentos_org_queue_demo`):

- superadmin with zero memberships logs in — `org_id: null`, `permissions: []`
- a non-superadmin holding `talentos.iam.organizations.manage` gets **403** from `POST /organizations`
- creating an organization provisions its admin, role assignment and invite email
- the invited admin **cannot** log in until they redeem the token; then they can
- their token is intersected down to the ceiling (Organization Admin grants far more)
- lowering the ceiling changes the very next token
- all three templates (`org_admin_invite`, `user_invite`, `password_reset`) delivered, with the
  set-password link recoverable from the worker log
- an org admin reading another organization's providers gets **403**; a superadmin gets **200**
- a secret is never returned by any read path
- **the tenant-queue hop**: dispatcher parks `deliver_email` in the organization's own broker
  (platform worker does not touch it), and `run_worker.py --organization <id>` drains it and
  delivers through the organization's own email provider

---

## Standing constraints for this repo

- **Never `git commit` or `git push`** — a standing instruction for this whole project.
- No hardcoding: every operational constant lives in `.env` / pydantic-settings.
- Windows: Celery's prefork pool does not work; `run_worker.py` defaults to `--pool=solo`.
  `uvicorn --reload` spawns its real worker via `multiprocessing.spawn` with a **different PID**
  than the parent — find it with
  `Get-CimInstance Win32_Process | Where-Object {$_.CommandLine -match 'multiprocessing'}`.

---

## Tenant isolation - audited 2026-08-25

Every organization's data is private to it. Verified endpoint by endpoint across talentos-app,
agent-builder-service and voice-agent-service, not assumed.

**The mechanism is a join, not a column.** Only root entities carry `organization_id`
(jd_analyses, resume_analyses, submissions, models, agents, calls, call_agent_configs,
telephony_provider_configs). Children - skills, questions, interview_sessions, evaluations,
conversation_turns, call_events, call_summaries, agent_credentials - carry none, and are isolated
by the service layer joining back to a scoped root. The deepest chain is
`Evaluation -> Question -> Skill -> JDAnalysis`, filtered on `JDAnalysis.organization_id`.

That is sound, but it makes isolation a property of *query construction* rather than of the
schema: no constraint fires if a refactor drops the join. A column-level survey therefore looks
alarming and is misleading - the absence of `organization_id` on `interview_sessions` is by
design, not an oversight.

Three access paths deliberately do not filter by organization, and each is correct:

- `POST /invoke` (agent-builder) - the agent id comes from the caller's own `resource_scope`
  claim, minted for that one agent. A token can only invoke what it was issued for.
- `POST /webhooks/twilio/...` (voice-agent) - loads the call by id, then validates the Twilio
  signature using *that call's own organization's* credentials. The org is derived from the
  call, never asserted by the caller.
- `POST /webhooks/voice-agent/{id}` (talentos-app) - shared-secret authenticated, returns 204,
  discloses nothing, and only refreshes the status of the call named in the URL.

### What now guards it

`talentos-app/tests/test_organization_scoping.py` covered the root entities. It now also covers
the deep chains - questions-via-skill, interview sessions (get and list), and the three-hop
evaluation - plus a positive case, since proving the filter rejects the wrong tenant is worthless
without proving it still admits the right one.

These were mutation-tested: deleting the `organization_id` filter from
`_get_evaluation_or_404` turns the expected 404 into a **200 returning another tenant's
evaluation**, and the test fails. The guard is real, not decorative.
