# IAM Console

React + TypeScript (Vite) admin UI for [`iam-service`](../../backend/iam-service) - TalentOS's
identity and access control plane: organizations, users, roles/permissions, role assignments,
service principals, and the platform-wide audit log. Standalone app, own port, deployed
separately from every other frontend, matching the design in
`docs/superpowers/specs/2026-08-24-iam-service-design.md`.

This app has **no login page of its own** - [`portal`](../portal) is the platform's single login
entry point. An unauthenticated visit here redirects to `portal`; a successful login there hands
the session back via a one-time token handoff in the URL fragment (see "How sessions work"
below).

## What this is for

Every other service in the platform (`talentos-app`, `agent-builder-service`) is a Bearer-token
relying party against `iam-service`. This console is where an Organization Owner/Admin:

- Manages org membership: invite users, disable/enable them, see what roles they hold.
- Authors roles: built-in roles (Owner, Admin, Requirements Manager, Recruiter, Agent Builder
  Admin/Contributor, Viewer) are read-only; custom roles combine any subset of the permission
  catalog, grouped by service namespace (IAM / Intake & Matching / Agent Builder) in the picker.
- Assigns a role to a user or a service principal at Organization or Service scope, and revokes
  assignments.
- Issues and rotates Service Principal credentials (machine identities, optionally bound to one
  specific resource such as an agent's invoke credential) - secrets are shown exactly once, on
  create or on rotate, then never again.
- Reads the audit log: every authn/authz decision and business-data mutation platform-wide,
  filterable by actor/action/date range/result.

## Structure

```
src/
  api/
    client.ts      one axios instance (iamClient) with an auto-refresh interceptor: proactively
                    refreshes the access token shortly before it expires, retries once on a 401,
                    and reports a hard refresh failure so the app can drop back to portal.
    iam.ts          typed calls for every documented iam-service endpoint (organizations, users,
                    role definitions, role assignments, service principals, permissions, audit
                    log - everything except login, which happens in `portal`).
  types.ts          TS types mirroring iam-service's documented API contract.
  lib/
    auth.ts         sessionStorage token storage + JWT decode (no signature verification needed
                    client-side - iam-service is the only party that verifies it) + expiry checks
                    + `consumeHandoffFragment`/`redirectToLogin` (the relying-party half of the
                    portal handoff).
    permissions.ts  hasPermission()/hasAnyPermission() UI gating, the service-namespace grouping
                    table for the role permission picker, and `principalLabelFor` (resolving a
                    role assignment's principal id to a human-readable name client-side).
    tone.ts         domain value -> Badge tone mapping (audit result, user status, scope, etc.)
                    so every page renders the same badge color for the same meaning.
    format.ts       shared date/initials formatting.
    navigation.ts   sidebar nav items + topbar section title, permission-filtered.
  components/
    auth/           AuthContext (session state, org list, proactive refresh timer) + RequireAuth
                    route guard (redirects to `portal`, not an in-app /login route).
    layout/         AppLayout / Sidebar / Topbar / OrgSwitcher.
    ui/             Button, Badge, Card, PageHeader, EmptyState, Skeleton, StatCard, Table, Modal,
                    ConfirmDialog, SearchableSelect, icons.tsx (inline SVGs, no icon library) -
                    same design-token system and component shapes as talentos-app's ui/ library.
    PermissionPicker.tsx / SecretRevealModal.tsx  IAM-specific composite components.
  pages/
    DashboardPage               org name, quick counts, links out
    UsersPage / UserDetailPage  list/invite/disable, a user's role assignments
    RolesPage                   built-in (read-only) + custom roles, grouped permission picker
    RoleAssignmentsPage         assign principal + role + scope, list/revoke
    ServicePrincipalsPage       list/create/rotate/revoke, one-time secret reveal
    AuditLogPage                filterable, sortable, result badges, real offset/total pagination
```

## Setup

```bash
npm install
cp .env.example .env   # defaults already point at iam-service on :8003 and portal on :5175
npm run dev
```

Runs at `http://localhost:5174`. Requires `iam-service` running with CORS allowing
`http://localhost:5174`, and (to actually log in) `portal` running at `http://localhost:5175`.

## Environment variables

Everything environment-specific comes from `VITE_*` vars - nothing is hardcoded in source.

| Variable | Default | Purpose |
|---|---|---|
| `VITE_IAM_SERVICE_URL` | `http://localhost:8003` | Base URL of `iam-service`, used by every call in `src/api/iam.ts`. |
| `VITE_PORTAL_URL` | `http://localhost:5175` | Where an unauthenticated visit redirects to log in. |

## How sessions work

- There is no login form here. `RequireAuth` sends an unauthenticated visitor to
  `{VITE_PORTAL_URL}/login?return_to=<this app's URL>`. After a successful login, `portal`
  redirects back to that URL with `#access_token=...&refresh_token=...&organization_id=...` in
  the fragment; `main.tsx` calls `consumeHandoffFragment()` before the app even mounts, so the
  very first render already sees the session, and the fragment is stripped from the address bar
  immediately via `history.replaceState`.
- The access token is short-lived (15 min) and kept in `sessionStorage` (not `localStorage`) so a
  session doesn't silently outlive the tab. It's a signed (RS256) JWT; the console decodes its
  payload client-side (without verifying the signature - it doesn't need to, `iam-service` already
  did) to read `permissions`, `org_id`, and an `email`/`name` claim for the "logged in as" display.
- `src/api/client.ts`'s request interceptor refreshes the token whenever it's within 30 seconds of
  `exp`, and `AuthContext` additionally polls every 60 seconds so a session stays alive through an
  idle period (e.g. reading the audit log for a while) without needing an API call to trigger it.
  A response interceptor is the fallback: on a 401 it refreshes once and retries; if the refresh
  itself fails, the session is cleared and the app redirects back to `portal`.
- "Sign out" clears local tokens and redirects to `portal` the same way.
- Every permission-gated button/section checks the decoded `permissions` claim client-side
  (`lib/permissions.ts`) so the UI stays coherent (hidden/disabled) instead of just eating a 403 -
  the backend is still the actual enforcement point.

## Scripts

- `npm run dev` - dev server with HMR on port 5174
- `npm run build` - type-check (`tsc -b`) and production build to `dist/`
- `npm run preview` - preview the production build locally
- `npm run lint` - oxlint
