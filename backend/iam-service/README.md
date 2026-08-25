# TalentOS IAM Service

The platform's identity and access control plane, modeled on Azure AD/Entra ID + Azure RBAC:
**Organizations** as the tenant boundary, **Users** and **Service Principals** as principals,
**Roles** built from a fixed **Permission** catalog and assigned to principals **at a scope**,
and a single platform-wide **audit trail** of every authn/authz decision and business-data
mutation. `talentos-app` and `agent-builder-service` become Bearer-token relying
parties of this service - they validate tokens locally against its published JWKS and never
query its database directly.

See `docs/superpowers/specs/2026-08-24-iam-service-design.md` (repo root) for the full design.

## Concepts

- **Organization**: top-level tenant boundary. Every resource platform-wide belongs to
  exactly one org.
- **User**: a human identity, globally unique by email. A user can belong to several orgs via
  **OrganizationMembership**; an access token is always scoped to exactly one active org at a
  time (switch with `POST /auth/token/switch-org`).
- **ServicePrincipal**: a non-human, machine-to-machine identity. Optionally *resource-bound*
  (`resource_type`/`resource_id` set) for a narrowly-scoped, independently-revocable
  credential such as one specific agent-builder-service agent's invoke key.
- **Permission**: a namespaced string from a fixed, seeded catalog, e.g.
  `talentos.intake.requirements.write`. Never created via the API.
- **RoleDefinition**: a named set of permissions. `organization_id = NULL` marks a **built-in**
  role (seeded once, global, visible to every organization, read-only via the API); a
  non-null `organization_id` marks a **custom** role owned by that org.
- **RoleAssignment**: binds a principal (`user` or `service_principal`) to a `RoleDefinition`
  at a scope - either `organization` (the role applies everywhere in that org) or `service`
  (the role applies only within one named platform service, e.g. `agent-builder`).
- **RefreshToken**: hashed, rotated on every use, grouped into a `family_id` rotation chain.
  Reusing an already-rotated token is treated as theft evidence and revokes the whole chain.
- **AuditLogEntry**: append-only record of every login, token refresh, permission check
  (granted or denied), and business-data mutation platform-wide. No update/delete endpoint
  exists for it.

### Permission resolution (computed at token-issue time)

An access token's `permissions` claim is the union of:

1. permissions from every `RoleDefinition` assigned to the principal via a `RoleAssignment`
   at **organization** scope for the token's active org, and
2. permissions from every `RoleAssignment` at **service** scope whose `scope_id` is
   `"<org_id>:<service_name>"`, across all known platform services.

Because permissions are embedded in the token, a role change takes effect on that principal's
next token refresh (at most `ACCESS_TOKEN_EXPIRE_MINUTES`, 15 by default) - the same trade-off
Azure AD makes with its own token lifetimes. `revoked_token_jti` is an emergency-only deny-list
for the rare "kill this token right now" case.

## Setup

```bash
# CREATE DATABASE talentos_iam;
cp .env.example .env   # review DATABASE_URL, JWT_*, lockout/password policy, bootstrap admin creds

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt   # (or requirements.txt for a non-dev install)

alembic upgrade head

python scripts/generate_signing_key.py          # writes keys/private.pem + keys/public.pem
python scripts/seed_permissions_and_roles.py    # seeds the permission catalog + built-in roles
python scripts/bootstrap.py                     # creates the first org + admin user (see .env)

python main.py                                  # serves http://localhost:8003
```

`scripts/bootstrap.py` is the *only* way the first Organization and User get created - there
is no authenticated caller yet to go through `POST /organizations`. Every organization created
afterwards goes through the normal authenticated API by an existing Owner/Admin.

## API

No `/api/v1` prefix - every path below is mounted at the service root, since other services
and `iam-console` depend on these exact paths.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | none | Liveness check |
| GET | `/.well-known/jwks.json` | none | Public RS256 signing key(s), RFC 7517 JWK Set |
| POST | `/auth/login` | none | Email+password to access+refresh token. 409 with membership list if the org is ambiguous |
| POST | `/auth/token` | none (creds in body) | Service principal client-credentials grant |
| POST | `/auth/token/refresh` | refresh token | Rotates access+refresh token; detects reuse |
| POST | `/auth/token/switch-org` | access token | Re-scopes a token to another active membership |
| POST | `/auth/logout` | access token | Revokes all of the caller's refresh tokens |
| POST | `/auth/password-reset/request` | none | Logs a reset link (email delivery stubbed) |
| POST | `/auth/password-reset/confirm` | none | Redeems the reset token, sets a new password |
| POST | `/organizations` | `talentos.iam.organizations.manage` | Create an organization |
| GET | `/organizations` | access token | List organizations the caller belongs to |
| POST | `/organizations/{id}/users` | `talentos.iam.users.invite` | Invite a user into an org |
| GET | `/organizations/{id}/users` | `talentos.iam.users.manage` or membership | List org members |
| PATCH | `/organizations/{id}/users/{user_id}` | `talentos.iam.users.manage` | Enable/disable a member |
| GET | `/role-definitions?organization_id=` | access token | Built-ins + that org's customs |
| POST | `/role-definitions` | `talentos.iam.roles.manage` | Author a custom role |
| PATCH / DELETE | `/role-definitions/{id}` | `talentos.iam.roles.manage` | Edit/delete a custom role (403 on built-ins) |
| POST | `/role-assignments` | `talentos.iam.role_assignments.manage` | Assign a role at a scope |
| GET | `/role-assignments?organization_id=` | access token | List assignments in an org |
| DELETE | `/role-assignments/{id}` | `talentos.iam.role_assignments.manage` | Revoke an assignment |
| POST | `/service-principals` | `talentos.iam.service_principals.manage` | Create a service/resource-bound SP - secret shown once |
| GET | `/service-principals?organization_id=` | access token | List SPs (masked, never the secret) |
| POST | `/service-principals/{id}/secret/rotate` | `talentos.iam.service_principals.manage` | Rotate a client secret |
| DELETE | `/service-principals/{id}` | `talentos.iam.service_principals.manage` | Revoke an SP |
| POST | `/audit/events` | any valid access token | Ingest one audit event (org/actor derived from the token, never trusted from the body) |
| GET | `/audit/events?organization_id=&actor_id=&action=&date_from=&date_to=` | `talentos.iam.audit.read` | Paginated audit query |

### Permission catalog

Seeded by `scripts/seed_permissions_and_roles.py`:

```
talentos.iam.organizations.manage         talentos.intake.requirements.read/write/delete
talentos.iam.users.invite                 talentos.intake.applicants.read/write/delete
talentos.iam.users.manage                 talentos.intake.submissions.read/write/delete
talentos.iam.roles.manage                 talentos.intake.interviews.read/write
talentos.iam.role_assignments.manage      talentos.agentbuilder.models.manage
talentos.iam.service_principals.manage    talentos.agentbuilder.agents.read/write/publish/manage_keys
talentos.iam.audit.read
```

### Built-in roles

Organization Owner (everything) - Organization Admin (everything except
`talentos.iam.organizations.manage`) - Requirements Manager (full `talentos.intake.*` CRUD) -
Recruiter (`talentos.intake.*` read/write, no delete) - Agent Builder Admin (all
`talentos.agentbuilder.*`) - Agent Builder Contributor (`agents.read`/`agents.write` only) -
Viewer (read-only across intake + agent-builder).

## Security notes

- Passwords: Argon2id (`argon2-cffi`), minimum length from `PASSWORD_MIN_LENGTH` (default 12,
  no forced complexity rules).
- Login lockout: `LOGIN_LOCKOUT_THRESHOLD` failed attempts within a rolling
  `LOGIN_LOCKOUT_WINDOW_MINUTES` window locks the account for `LOGIN_LOCKOUT_DURATION_MINUTES`
  (defaults: 10 / 15 / 15). Every attempt, lockout included, is audited.
- Tokens: RS256 (`PyJWT` + `cryptography`), private key never leaves this service; the public
  key is published at `/.well-known/jwks.json` with a `kid` (`JWT_KEY_ID`) so keys can be
  rotated without downtime. Access tokens live `ACCESS_TOKEN_EXPIRE_MINUTES` (default 15).
- Refresh tokens: stored only as a SHA-256 hash, rotated on every use, grouped by `family_id`.
  Reuse of an already-rotated token revokes the entire family (theft/replay detection).
- Service principal secrets: generated once, shown once, stored only as a SHA-256 hash - same
  one-time-reveal pattern as agent-builder-service's agent API keys.
- `POST /audit/events` derives `organization_id`/`actor_type`/`actor_id` from the caller's own
  verified token, never from the request body, so one org can't stamp another org's audit log.
- CORS is locked to `CORS_ORIGINS` (the known `frontend` and `iam-console` origins).
- No config is hardcoded: `DATABASE_URL`, `PORT`, `CORS_ORIGINS`, JWT key paths/kid/lifetimes,
  lockout thresholds, password policy, and the bootstrap org/admin identity all come from
  `.env` via `app/config.py`. The platform's fixed service-name list
  (`talentos-app`/`agent-builder`/`iam`, used to build `scope_id` for service-scoped role
  assignments) is legitimate domain modeling, not operational config, so it lives as a Python
  enum (`app/core/constants.py`) rather than an env var.

## Tests

```bash
pytest
```

Tests spin up a separate `talentos_iam_test` database on the same local Postgres server
(created automatically if missing) and a throwaway RS256 keypair - they never touch
`talentos_iam` or the real signing keys. Coverage includes login success/failure/lockout,
refresh-token rotation and reuse detection, the client-credentials grant, permission
resolution across organization and service scope, the JWKS endpoint shape, and a full
RBAC denial-then-grant flow.
