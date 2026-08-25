# TalentOS IAM Service — Design

Status: **approved pending final read-through**
Author: Claude (with pmedepalli@sageitinc.com)
Date: 2026-08-24

## 1. Problem & goals

Today, `agent-builder-service` and `intake-matching-service` each trust a single
shared `X-API-Key` per service plus a free-text, unverified `X-Actor-Email` header
for audit stamping. There is no concept of a user, an organization, a role, or a
permission anywhere in the platform, and no centralized record of who did what,
when.

The platform needs a real identity and access control plane, modeled on Azure
AD/Entra ID + Azure RBAC:

- **Organizations** as the tenant/isolation boundary, with **Users** inside them.
- **Roles** built from **Permissions**, assigned to principals **at a scope**.
- Every other service authenticates callers against this plane and enforces
  permissions before performing an action.
- **Every transaction, timestamped**, in a single platform-wide audit trail.
- A **separate backend service** (`iam-service`) and a **separate frontend**
  (`iam-console`) — not folded into the existing recruiting frontend.

### Non-goals (this build)

- **MFA** — schema supports it (`users.mfa_enabled`, `users.mfa_secret_encrypted`),
  but TOTP enrollment/verification is not built now. Deferred per explicit decision.
- **Resource-level RBAC for human role assignments** — e.g. "this user can only
  see JD #123." Role assignments in this build stop at Organization or Service
  scope. Deferred per explicit decision; schema leaves room for it (see §4.3).
- **Groups** — role assignments target Users or Service Principals directly.
  The schema's `principal_type` enum already reserves a `group` value so this
  can be added later without a migration that breaks existing data.
- Full OIDC authorization-code/redirect flow, PIM-style time-bound elevation,
  billing, and email delivery infrastructure (password reset generates a token;
  actually emailing it is a stub/log line for now, same rigor as the rest of
  this codebase's local-dev posture).

## 2. Service boundaries

| Service | Role | Port (proposed) | DB |
|---|---|---|---|
| `iam-service` | Identity/authorization control plane: orgs, users, roles, permissions, role assignments, service principals, tokens, platform-wide audit log | 8003 | `talentos_iam` |
| `iam-console` | Standalone frontend: login, org switcher, user/role/assignment management, service principal management, audit log viewer | 5174 | — |
| `intake-matching-service` | Existing. Becomes a Bearer-token relying party. | 8000 | `talentos_intake_matching` |
| `agent-builder-service` | Existing. Becomes a Bearer-token relying party; its per-agent invoke credential becomes an IAM-issued Service Principal (see §6). | 8002 | `talentos_agent_builder` |
| `frontend` | Existing recruiting + agent-builder UI. Redirects to `iam-console` to authenticate, then carries the issued token. | 5173 | — |

`iam-service` is a peer service, not a shared library — `intake-matching-service`
and `agent-builder-service` depend on it only through (a) validating JWTs locally
against its published JWKS, and (b) a small outbound call to post audit events.
Neither service ever queries `iam-service`'s database directly.

## 3. Core domain model

| Entity | Purpose | Azure analogue |
|---|---|---|
| `Organization` | Top-level tenant boundary. Every resource platform-wide (JDs, agents, models, submissions...) belongs to exactly one org. | AAD tenant |
| `User` | Human identity: email (unique per org), Argon2id password hash, display name, status (`invited`/`active`/`disabled`). | AAD user |
| `OrganizationMembership` | Join of `User` ↔ `Organization`, with status. A user may belong to several orgs; a token is always scoped to one active org (§5). | Tenant guest/member access |
| `ServicePrincipal` | Non-human identity for machine-to-machine calls. Two flavors, distinguished by `resource_type`/`resource_id` being null or set (§6): a *service* SP (e.g., a backend calling another backend generically) or a *resource-bound* SP (e.g., one specific agent's invoke credential). | AAD App Registration / Managed Identity + (resource-bound flavor) a data-plane access key like a Storage Account key |
| `RoleDefinition` | Named set of permissions. `is_builtin=true` rows ship with the platform and cannot be edited/deleted; `is_builtin=false` rows are custom, authored per org. | RBAC role definition |
| `Permission` | Namespaced string catalog, seeded once, e.g. `talentos.intake.requirements.write`, `talentos.agentbuilder.agents.publish`, `talentos.iam.users.invite`. | `Microsoft.Compute/virtualMachines/read` |
| `RoleDefinitionPermission` | Join of `RoleDefinition` ↔ `Permission`. | — |
| `RoleAssignment` | Binds a principal (`user` or `service_principal`) to a `RoleDefinition` at a `Scope`. | RBAC role assignment |
| `RefreshToken` | Hashed, rotated on use; `family_id` links a chain so reuse of a stale token revokes the whole chain. | AAD refresh token |
| `AuditLogEntry` | Immutable record of every authn/authz decision and every business-data mutation platform-wide. | Activity Log + Sign-in Log |

### 3.1 Scope (decided: Organization + Service level only)

```
scope_type: "organization" | "service"
scope_id:   <organization.id>  when scope_type = organization
            "<organization.id>:<service_name>"  when scope_type = service
```

`service_name` is one of a small fixed set the platform knows about
(`intake-matching`, `agent-builder`, `iam`). A `RoleAssignment` at
`organization` scope grants the role everywhere in that org; at `service`
scope it grants the role only within that one service. There is deliberately
no `resource` scope_type in this build — adding one later only means adding a
new enum value and a `scope_id` convention (`org:service:resource_id`); no
existing rows need to change.

### 3.2 Built-in roles (seeded, per organization at creation time)

| Role | Summary |
|---|---|
| Organization Owner | Full control, incl. managing all role assignments and the org itself. |
| Organization Admin | Manage users and role assignments; cannot delete the org. |
| Requirements Manager | Full CRUD on JD/resume/submission/interview data. |
| Recruiter | Read/write on requirements/applicants/submissions/interviews; no delete, no user management. |
| Agent Builder Admin | Manage models and agents, publish agents, rotate keys. |
| Agent Builder Contributor | Create/edit agents; cannot manage models or rotate keys. |
| Viewer | Read-only, org-wide. |

Org admins may also define custom `RoleDefinition`s by picking any subset of
the seeded `Permission` catalog.

## 4. Authentication

### 4.1 Flows

- `POST /auth/login` — email + password → access token + refresh token. This
  is the platform's only first-party client today, so a full OAuth
  authorization-code redirect isn't needed yet; the token endpoints are shaped
  so that flow can be added later without breaking this one.
- `POST /auth/token` — `client_id` + `client_secret` (client-credentials grant)
  → access token for a `ServicePrincipal`. No refresh token; the caller simply
  requests a new one before expiry (see caching note in §6).
- `POST /auth/token/refresh` — rotates the refresh token. Reusing an
  already-rotated token revokes the entire `family_id` chain (theft
  detection).
- `POST /auth/logout` — revokes all of the caller's refresh tokens ("sign out
  everywhere"). Access tokens are stateless and simply expire.
- `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm` —
  emailed-token flow; email delivery is logged, not actually sent, matching
  this codebase's existing local-dev posture elsewhere.

### 4.2 Password & lockout policy

Argon2id hashing. Minimum length 12, no forced complexity rules (length is the
stronger signal). Lockout for 15 minutes after 10 failed attempts within a
rolling 15-minute window, itself an audited event.

### 4.3 Switching organizations

Because a user can belong to more than one org, and a token is scoped to
exactly one org (§5), the console offers an org switcher that calls
`POST /auth/token/switch-org` (requires the user to already have an active
session and membership in the target org) to mint a new access token for that
org — no full re-login needed, mirroring how AAD tenant-scoped tokens work.

## 5. Tokens

Signed **RS256**. The private key lives only in `iam-service`; the public key
is published at `GET /.well-known/jwks.json` with a `kid` per active key so
keys can be rotated without downtime (old `kid` stays valid until its tokens
expire). This is the load-bearing design choice: `intake-matching-service` and
`agent-builder-service` validate tokens **locally** from the cached JWKS, with
no synchronous call to `iam-service` on the request path — necessary for
latency and for `iam-service` not becoming a single point of failure for every
request platform-wide.

Access token claims:

```
sub            user id or service_principal id
principal_type "user" | "service_principal"
org_id         the active organization for this token
permissions    resolved effective permission strings at issue time
resource_scope { type: "agent", id: "<agent_id>" }  — only present for a
               resource-bound ServicePrincipal (§6); absent otherwise
iat / exp / jti
```

Access tokens live **15 minutes**. Embedding resolved permissions in the token
trades instant revocation for local, zero-latency checks — a role change or a
revoked assignment takes effect on that principal's next token refresh, at
most 15 minutes later. This is the same trade-off Azure AD makes with its own
token lifetimes, and is explicitly acceptable here given the platform's scale.
An emergency-only deny-list table (`jti`, `revoked_at`, checked as a cheap
indexed lookup alongside signature validation) is kept for the rare "kill this
token right now" case (e.g. a compromised service principal secret) without
waiting out the 15 minutes.

## 6. Reconciling per-agent credentials with Org/Service-only scope

Two decisions were made independently and need to fit together: agent invoke
credentials move under IAM Service Principals, but role-assignment scope only
goes down to the Service level, not per-resource. Today, each of the 7 agents
in `agent-builder-service` has its own distinct, independently-revocable key —
that granularity has to survive.

The resolution: a `ServicePrincipal` can optionally be **resource-bound** at
creation time via `resource_type` + `resource_id` columns on the
`ServicePrincipal` row itself — this is a property of that one credential, not
a general-purpose scope a `RoleAssignment` can target. It sidesteps adding
resource-level `RoleAssignment` scoping (still deferred, per §3.1) while still
giving each agent its own narrowly-scoped, independently-revocable, centrally
audited credential. This mirrors how Azure itself keeps two separate
mechanisms side by side: RBAC role assignments (management-plane, coarse) and
per-resource data-plane keys (e.g. a Storage Account access key) that exist
outside RBAC scope but are still an Azure-issued, Azure-tracked credential.

Mechanically:

1. When an agent is published in `agent-builder-service`, it calls
   `iam-service`'s `POST /service-principals` with
   `{resource_type: "agent", resource_id: <agent.id>, org_id}` instead of
   generating its own `agtk_...` key locally. `iam-service` returns
   `{client_id, client_secret}` — the secret is shown once, exactly like
   today's `agtk_` key, and stored only as a hash.
2. `intake-matching-service` (the caller) exchanges that `client_id`/
   `client_secret` for a short-lived access token via `iam-service`'s
   `POST /auth/token`, and **caches it until shortly before `exp`** — so the
   steady-state `/invoke` call path is unchanged latency-wise: one token
   refresh roughly every 15 minutes per agent, not one per invocation.
3. The call to `agent-builder-service`'s `/invoke` carries
   `Authorization: Bearer <token>` instead of `X-Agent-Key`. `agent-builder-service`
   validates the JWT locally via JWKS, then checks `resource_scope.type == "agent"`
   and `resource_scope.id == <the agent being invoked>` — a direct equality
   check, not a permission-catalog lookup.
4. Rotating a credential (today's "regenerate key") becomes
   `POST /service-principals/{id}/secret/rotate` on `iam-service`; the old
   secret's already-issued tokens simply expire within 15 minutes.

Everything about managing an agent (create/edit/publish/list) is still gated
by ordinary `RoleAssignment` permission checks at Service scope (e.g.
`talentos.agentbuilder.agents.publish` on the `agent-builder` service) — only
the *invoke* credential itself is resource-bound.

## 7. Authorization enforcement in consuming services

A small shared Python module, `iam_client` (published as a local package both
services depend on, not a network call per request):

- Fetches and caches the JWKS on startup, refreshing on a `kid` miss.
- Validates an incoming `Authorization: Bearer` token's signature and
  expiry.
- Exposes a FastAPI dependency:
  `require_permission("talentos.intake.requirements.write")` → 401 if no/invalid
  token, 403 if the token's `permissions` claim doesn't contain it.
- Exposes `current_actor()` → `{principal_type, id, org_id}`, replacing every
  place that currently reads the free-text `X-Actor-Email` header. This is
  what gets written into every existing `AuditLog`/`created_by`/`changed_by`
  column from now on — a verified identity instead of a self-reported string.

Every mutating endpoint in both services picks up a `require_permission(...)`
dependency matching the seeded permission catalog (§3.2 lists the roles those
permissions roll up into).

## 8. Audit logging

Every service posts audit events to `iam-service` —
`POST /audit/events`, fire-and-forget with local buffering so a slow audit
write never blocks the caller's actual request — rather than keeping its own
log table. One consistent, org-scoped, append-only trail covers:

- Authentication events: login success/failure, lockout, token refresh,
  logout, password reset.
- Authorization decisions: every permission check, grant or denial — no
  sampling. This is the direct implementation of "every single transaction,"
  the requirement that started this design; volume/retention tuning is a
  Phase 2 operational concern, not a reason to drop records now.
- Business-data mutations: every create/update/delete across
  `intake-matching-service` and `agent-builder-service` — generalizing the
  diff-based `(entity_type, entity_id, action, changed_by, changes, changed_at)`
  pattern already built for JD analysis into the single platform-wide table
  below.

```
AuditLogEntry
  id, organization_id, occurred_at,
  actor_type ("user" | "service_principal" | "system"), actor_id,
  action, target_type, target_id,
  result ("success" | "denied" | "error"),
  correlation_id, source_ip, user_agent,
  changes (JSONB, nullable — before/after diff for mutations)
```

`correlation_id` is generated at the frontend (or at the first service that
receives a request) and threaded through every downstream call, so one
user-initiated action's full cross-service trail can be reconstructed from the
audit log alone. The table is insert-only at the application layer — no
update/delete endpoint exists for it. `iam-console`'s audit viewer is the only
UI surface that reads it (filterable by actor, org, date range, action,
result).

## 9. `iam-service` API surface

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | none | Email+password → access + refresh token |
| POST | `/auth/token` | none (client creds in body) | Service principal client-credentials grant |
| POST | `/auth/token/refresh` | refresh token | Rotate access + refresh token |
| POST | `/auth/token/switch-org` | access token | Re-scope a token to a different org membership |
| POST | `/auth/logout` | access token | Revoke all refresh tokens for the caller |
| POST | `/auth/password-reset/request` / `/confirm` | none | Emailed-token reset flow |
| GET | `/.well-known/jwks.json` | none | Public signing keys |
| POST / GET | `/organizations` | access token + permission | Create/list organizations |
| POST / GET / PATCH | `/organizations/{id}/users` | access token + permission | Invite/list/update org members |
| GET | `/role-definitions` | access token | List built-in + custom roles |
| POST / PATCH / DELETE | `/role-definitions` | access token + permission | Author custom roles |
| POST / GET / DELETE | `/role-assignments` | access token + permission | Assign/list/revoke a role at a scope |
| POST / GET | `/service-principals` | access token + permission | Create/list service + resource-bound SPs |
| POST | `/service-principals/{id}/secret/rotate` | access token + permission | Rotate a client secret |
| POST | `/audit/events` | access token (service principal) | Ingest one audit event |
| GET | `/audit/events` | access token + permission | Query the audit trail (used by `iam-console`) |

## 10. `iam-console` (frontend)

Standalone React + TypeScript (Vite) app, same stack as the existing
frontend, deployed and run separately (own `npm run dev`, own port). Pages:

- **Login** — email/password; lands on the org switcher if multiple
  memberships exist.
- **Users** — list, invite, disable, view a user's role assignments.
- **Roles** — built-in (read-only) and custom role definitions; a permission
  picker grouped by service for authoring custom roles.
- **Role assignments** — assign a principal (user or service principal) to a
  role at Organization or Service scope; revoke.
- **Service principals** — list, create, rotate secret; resource-bound ones
  (e.g. agent invoke credentials) show which resource they're bound to.
- **Audit log** — filterable table (actor, date range, action, result),
  matching the `AuditLogEntry` shape in §8.

The existing `frontend` app redirects unauthenticated users here to log in
(carrying a `return_to` so the user lands back where they started), then
stores the issued access/refresh token and attaches
`Authorization: Bearer <token>` on all calls to `intake-matching-service` and
`agent-builder-service`, silently refreshing before the 15-minute expiry.

## 11. Data model (tables)

```
organizations
users
organization_memberships
service_principals        (org_id, client_id, secret_hash, resource_type NULL, resource_id NULL, revoked_at)
role_definitions           (org_id NULL for built-ins, name, is_builtin)
permissions                (seeded catalog, e.g. "talentos.intake.requirements.write")
role_definition_permissions
role_assignments           (principal_type, principal_id, role_definition_id, scope_type, scope_id)
refresh_tokens              (token_hash, family_id, user_id, revoked_at)
audit_log_entries
```

## 12. Security hardening

Argon2id password hashing; RS256 with `kid`-based rotation; refresh-token
rotation with reuse detection; login/token endpoint rate limiting; account
lockout; service-principal secrets hashed the same way agent keys are today
(SHA-256, shown once); CORS locked to the known frontend origins
(`frontend` and `iam-console`); the audit log as the append-only source of
truth for "every single transaction," per the original ask.

## 13. Migration plan

Ordered so each step is independently testable and nothing is left half-migrated:

1. Build and stand up `iam-service` fully, seed the built-in roles/permission
   catalog. **Bootstrap** (a one-time script, same pattern as
   `agent-builder-service/scripts/seed_models_and_agents.py`) creates the
   first Organization and its first User directly against the database, with
   the Organization Owner role pre-assigned — there is no authenticated caller
   yet to do this through the API, so it can't go through `POST /organizations`.
   Every Organization created afterwards goes through the normal authenticated
   API, created by an existing Owner/Admin.
2. Migrate `agent-builder-service`: admin endpoints move from `X-API-Key` to
   `Authorization: Bearer` + `require_permission(...)`; the 7 existing agents'
   `agtk_...` keys are replaced by resource-bound Service Principals per §6
   (re-issued once, same one-time-reveal UX as today).
3. Migrate `intake-matching-service`: same Bearer-token switch for its admin
   endpoints; its `agent_client.py` starts exchanging each agent's
   `client_id`/`client_secret` for a cached token instead of sending a static
   `X-Agent-Key`.
4. Point the existing `frontend` at `iam-console` for login and swap its
   stored `VITE_API_KEY` for a real session token.
5. Retire `X-API-Key` and `X-Actor-Email` from both services entirely once
   step 4 is verified end-to-end.

## 14. Phasing

**This build (Phase 1):** everything in §2–§13 above.

**Explicitly deferred (Phase 2, not started here):** MFA, Groups,
resource-level `RoleAssignment` scoping for human users, custom-role-authoring
UI polish, real password-reset email delivery, PIM-style time-bound elevated
access. Real Azure IAM has these; they're called out here so the omission is a
decision, not an oversight.
