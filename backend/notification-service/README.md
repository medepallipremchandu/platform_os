# notification-service

Transactional email for the TalentOS platform, and the per-organization provider configuration
that decides how it is sent.

Two entry points, one codebase, one database (`talentos_notifications`):

| Process | Command | What it does |
|---|---|---|
| Config API | `uvicorn app.main:app --port 8104` | Lets an organization register, test, enable and audit its own email/queue providers |
| Worker | `python run_worker.py` | Consumes and delivers notifications |

They are deliberately separate processes: the worker must keep draining the queue during an API
deploy, and a hung SMTP relay must never take the configuration UI down with it.

---

## The shape of the thing

Two independent, tenant-configurable axes:

* **email provider** – *how* an organization's mail physically leaves the platform
  (`smtp`, `sendgrid`, or the `console` sink)
* **queue provider** – *which broker* its notifications are dispatched onto
  (`postgres`, `redis`, `rabbitmq`, `sqs`)

One rule governs both: **an organization's own enabled provider wins; otherwise the platform
default applies.** That fallback is what makes the whole feature additive — an organization that
configures nothing behaves exactly as it did before tenant providers existed, and no backfill was
needed to keep it working.

### Two-tier queueing

```
iam-service                    notification-service
(producer only)                 platform worker                    tenant worker
     |                                |                          (only if the org
     |  notifications.send_email      |                           has its own queue)
     +------> PLATFORM broker ------->| dispatcher                       |
              (fixed, .env)           |   resolve queue provider         |
                                      |                                  |
                                      +-- org has none ---------+        |
                                      |   deliver_email --------|------->| (same worker)
                                      |                         |
                                      +-- org has one ----------+
                                          deliver_email ---> TENANT broker ---> tenant worker
                                                                                    |
                                                                     resolve EMAIL provider
                                                                     send + write EmailLog
```

**Tier 1 (ingest) is not tenant-configurable, on purpose.** Every producer publishes
`notifications.send_email` to the platform broker, always. A tenant misconfiguring their own
broker must never be able to break organization creation or a password reset — producers stay
decoupled from tenant state entirely.

**Tier 2 (delivery) is.** The dispatcher looks up the organization's queue provider and
re-publishes `notifications.deliver_email` onto *their* broker; a worker started with
`--organization <id>` consumes it. If the organization has no queue of its own, delivery is
enqueued back onto the platform broker and the same worker picks it up. Dispatch always enqueues
rather than ever delivering inline, so retry, backoff and acknowledgement behave identically
either way.

If a tenant broker is unreachable, the dispatcher falls back to the platform broker and records
that it did. An undeliverable invite is worse than a slow one.

### Adding a provider

Write the class, add it to the tuple in `app/providers/registry.py`. That is the whole change.
The catalog endpoint, iam-console's config form, validation, secret encryption and the "Test
connection" button all pick it up, because every provider declares its own fields (see
`app/providers/base.py::ProviderField`) instead of a form being hardcoded per vendor.

---

## Cross-service task contract

Fixed. iam-service is the only producer today; it shares a broker URL and a task name with this
service and nothing else — no shared code, no shared models.

```
task     "notifications.send_email"
kwargs   {to_email: str, template: str, context: dict, organization_id: str | None}
template "org_admin_invite" | "user_invite" | "password_reset"
context  org_admin_invite / user_invite: {organization_name, display_name, set_password_url}
         password_reset:                 {display_name, reset_url}
```

`organization_id` is what selects the organization's own providers. Omitting it is legal and
means "use the platform default".

---

## Secrets

Tenant provider secrets (SMTP passwords, API keys, broker DSNs) are **write-only**. Each provider
class declares which of its fields are secret; those are split out, Fernet-encrypted into
`secrets_encrypted` with `PROVIDER_SECRET_KEY`, and never returned by the API. Responses carry
`secrets_set` — the *names* of the secret fields that have a stored value — so the console can
show "password: set" without ever receiving it. Omitting a secret on an update keeps the stored
one, so an operator can change an SMTP port without re-typing the password.

Changing `PROVIDER_SECRET_KEY` makes every stored secret undecryptable; they must be re-entered.

---

## ⚠ Never name a setting `CELERY_BROKER_URL`

`celery.app.utils.Settings.broker_url` is a **property** that returns
`os.environ["CELERY_BROKER_URL"]` ahead of anything the application configures — not a default, a
hard override, re-read on every access. `CELERY_RESULT_BACKEND` behaves the same way.

In a service that builds one Celery app per tenant broker, that is catastrophic *and silent*:
every tenant app resolves to whatever the variable says. Mail is still delivered, nothing errors,
the console still says "your Redis", and the tenant's queue is simply never used. This service's
setting is therefore `NOTIFICATIONS_BROKER_URL`, and `app/celery_app.py` actively strips both
variables from the environment (loudly) before building any app. See
`tests/test_providers.py::test_a_tenant_app_publishes_to_the_tenant_broker_not_the_platform_one`.

---

## Local setup

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt

# CREATE DATABASE talentos_notifications;
cp .env.example .env
# Generate a Fernet key for PROVIDER_SECRET_KEY:
.venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

.venv/Scripts/python.exe -m alembic upgrade head
```

The Alembic migration deliberately does **not** create the Kombu broker tables (`kombu_queue`,
`kombu_message`). Kombu's SQLAlchemy transport creates those itself on first connect, in the same
database. They are broker internals, not application schema.

### Running

```bash
# Config API
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8104 --reload

# Platform worker - serves every organization that has NOT brought its own queue
.venv/Scripts/python.exe run_worker.py

# Tenant worker - only for an organization with an enabled queue provider
.venv/Scripts/python.exe run_worker.py --organization <organization-uuid>
```

**Windows:** Celery's default prefork pool does not work (it relies on `fork`), so `run_worker.py`
defaults to `--pool=solo` on win32. Verified working on Windows 11 with Celery 5.4.

### Tests

```bash
.venv/Scripts/python.exe -m pytest -q     # 40 tests
```

Uses a dedicated `talentos_notifications_test` database and runs Celery eager, so both hops of
the dispatch path execute for real in-process without a broker or worker.

Note that the test schema is built by `Base.metadata.create_all()`, so **every index and
constraint must be declared on the model, not only in the migration**. The partial unique index
`uq_notification_provider_enabled_per_kind` was once migration-only, and the tests happily passed
a case that failed against a migrated database.

---

## No SMTP in this environment

With `SMTP_HOST` empty the platform default resolves to the `console` provider: the fully rendered
email — **including the set-password / reset link** — is written to the log at INFO and
`EmailLog.status` is recorded as `logged_no_smtp_configured`, never `sent`. That is what makes the
invite and forgot-password flows exercisable end to end with no credentials anywhere, and it
matches the convention iam-service's `password_reset_service` already used.

---

## API

All organization-scoped routes are authorized by `app/core_iam.py::require_org_permission`: a
platform superadmin passes for any organization; everyone else must both hold the permission and
be acting inside that organization. A token scoped to org A never reaches org B's mail
credentials, no matter what permissions it carries.

| Method | Path | Permission |
|---|---|---|
| GET | `/providers/catalog` | none (a static registry description) |
| GET | `/organizations/{id}/notification-providers` | `...providers.read` or `.manage` |
| GET | `/organizations/{id}/notification-providers/resolved` | `...providers.read` or `.manage` |
| POST | `/organizations/{id}/notification-providers` | `...providers.manage` |
| PATCH | `/organizations/{id}/notification-providers/{config_id}` | `...providers.manage` |
| DELETE | `/organizations/{id}/notification-providers/{config_id}` | `...providers.manage` (archives) |
| POST | `/organizations/{id}/notification-providers/{config_id}/test` | `...providers.manage` |
| GET | `/organizations/{id}/email-logs` | `...logs.read` or `providers.manage` |

Permission codes are `talentos.notifications.providers.read` / `.manage` and
`talentos.notifications.logs.read`, seeded by
`iam-service/scripts/seed_permissions_and_roles.py` (built-in role: **Notification Admin**).
