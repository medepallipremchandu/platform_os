# Voice Agent Console

The standalone admin frontend for `voice-agent-service` - the platform's AI voice-calling
capability. Register telephony provider credentials, define reusable "call agent" configs
(conversation script + retry policy), place outbound AI-driven phone calls, and review call
transcripts/summaries.

This app follows the same pattern as its sibling consoles - `iam-console` (org/user/role admin)
and `agent-builder-console` (model + agent management): each major platform capability gets its
own dedicated frontend, with a separate `portal` app as the platform's single login page and
launcher, handing off a session to whichever of these apps the user picks.

## Architecture

- **Relying party, not an identity provider.** This app never logs a user in itself. It reads a
  post-login token handoff out of the URL fragment (`#access_token=...&refresh_token=...`), set by
  the `portal` app, stores the tokens in `sessionStorage`, and strips the fragment from the address
  bar. If there's no valid session, it redirects to `portal`'s `/login?return_to=<this app's URL>`
  so the user can log in and get handed back here. See `src/lib/auth.ts`.
- **Bearer-token API client with silent refresh.** `src/api/client.ts`'s `voiceAgentClient` is an
  axios instance that attaches `Authorization: Bearer <access_token>` to every request,
  proactively refreshing the token when it's within 30s of expiry (and reactively on a 401),
  coalescing concurrent refreshes into one in-flight call. On refresh failure, it clears the
  session and redirects back to the portal to log in again. Copied near-verbatim from
  `agent-builder-console`.
- **Permission-gated UI.** Every page/action decodes the access token's `permissions` claim
  client-side (`src/lib/auth.ts#hasPermission`) and gates itself on the exact permission codes
  voice-agent-service's contract requires - see `src/lib/permissions.ts`. A principal without a
  given permission sees an explicit "access denied" state rather than a broken page, and the
  sidebar only lists sections the session can actually read (`src/lib/navigation.ts`).
- **Talks to two backends**: primarily `voice-agent-service` (default `http://localhost:8004`) for
  everything providers/call-agents/calls; and directly to `iam-service` (default
  `http://localhost:8003`) for (a) token refresh and (b) `GET /organizations/{id}/users`, to
  populate the "visible only to specific people" user picker on the Providers/Call Agents forms.
  voice-agent-service has no user-listing endpoint of its own, so this is a deliberate
  cross-service read - the same pattern `talentos-app` already uses when it needs
  `agent-builder-service`/other-service data for its own pickers, both services being IAM relying
  parties trusting the same bearer token.

## Pages

- **Providers** (`/providers`) - list telephony provider configs (name, provider type, phone
  number, visibility, status), register a new one, revoke. Only the Twilio field set (Account SID
  / Auth Token / From number) is wired up today; the form is structured so a second provider type
  is just another branch of the credentials section, not a rewrite. Credentials are write-only -
  the API never returns them once saved, and this console never tries to display them again.
- **Call Agents** (`/call-agents`) - list call agent configs (provider, retry policy summary,
  visibility, status); create/edit a persona, objective, consent/closing lines, a dynamic
  repeatable "fields to extract" list (name/type/description), max conversation duration, a retry
  policy (max attempts, interval, and which call statuses trigger a retry), a provider, and
  visibility; deactivate (soft - the config stays on record).
- **Calls** (`/calls`) - paginated, filterable-by-status list of every call placed; a "Place a
  call" flow (`/calls/new`) that either picks a saved Call Agent or builds one inline for a
  one-off; a detail page (`/calls/:id`) with the full event timeline, the speaker-labeled
  conversation transcript, the summary + extracted fields, and a "Cancel call" action (graceful or
  immediate) while the call is still in flight.

## Visibility model

Every provider and call agent config carries `visibility: "organization" | "restricted"`. The
create/edit forms surface this as a first-class toggle - "Visible to everyone in this
organization" vs. "Visible only to specific people" - with the latter revealing a searchable
multi-select of the org's users (`src/components/ui/VisibilityPicker.tsx` +
`MultiUserSelect.tsx`), modeled on `iam-console`'s `RoleAssignmentsPage`/`SearchableSelect`
principal picker.

## Setup

```bash
cp .env.example .env   # adjust URLs if your services run elsewhere
npm install
npm run dev             # serves http://localhost:5177
```

## Environment variables

| Variable                          | Default                  | Purpose                                                                                   |
|------------------------------------|--------------------------|---------------------------------------------------------------------------------------------|
| `VITE_VOICE_AGENT_SERVICE_URL`    | `http://localhost:8004`  | `voice-agent-service`'s API - providers, call agent configs, calls                          |
| `VITE_IAM_SERVICE_URL`            | `http://localhost:8003`  | Direct token-refresh calls and the org user picker (`GET /organizations/{id}/users`)         |
| `VITE_PORTAL_URL`                 | `http://localhost:5175`  | Where an unauthenticated visitor is sent to log in (`/login`)                                |

## Build

```bash
npm run build   # tsc -b && vite build
```

## Assumptions made beyond the fixed API contract

`voice-agent-service` is being built in parallel and wasn't reachable while this console was
built, so the following filled-in details are this console's best-effort guess at shapes the
contract didn't fully spell out - flagged here rather than silently assumed:

- **`GET /calls` pagination envelope.** The contract says the list is "paginated" without giving
  a shape. This console assumes `{items, total, limit, offset}` with `limit`/`offset` query params
  - the same convention `iam-console` uses for its audit log (`AuditLogPageResponse`), for
  platform-wide consistency rather than inventing a new one.
- **Call agent config visibility grants aren't re-readable.** The contract's `GET`/`PATCH` shapes
  for a call agent config don't include the current `grant_user_ids` list, only the create/edit
  request body accepts it. So editing a restricted-visibility config's grant list is a full
  replace, not an incremental add/remove - the edit form says so explicitly. The same is true for
  providers (there's no `GET /providers/{id}` in the contract at all, only list + create +
  revoke, so providers aren't editable after creation regardless).
- **Field types for "fields to extract".** The contract gives `{name, type, description}` without
  enumerating valid `type` values. This console offers `string | number | boolean | date` as a
  reasonable minimal set; the field is otherwise passed through as opaque strings so a backend
  that accepts a different vocabulary won't be blocked by client-side validation.
- **Retry-triggering statuses.** The contract lists retry example statuses as `NO_ANSWER, BUSY`
  without giving the full retryable subset. This console's checklist offers `NO_ANSWER, BUSY,
  FAILED, TIMEOUT, DISCONNECTED, CALL_BLOCKED` - the "didn't complete" outcomes from the full
  `CallStatus` enum - and sends whatever subset is checked as plain strings, so it isn't blocked if
  the backend's actual retryable set differs.
- **`voice-agent-service` has no user-listing endpoint** (confirmed absent from the contract), so
  the visibility picker calls `iam-service`'s `GET /organizations/{id}/users` directly, per the
  task's own suggestion.

None of these assumptions are load-bearing for the rest of the app - each one is isolated to a
single request payload or response shape and can be adjusted in `src/types.ts` /
`src/api/voiceAgent.ts` once the real service is up without touching page logic.
