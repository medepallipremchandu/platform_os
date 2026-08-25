# Agent Builder Console

The standalone admin frontend for `agent-builder-service` - the platform's AI control plane.
Manage model deployments (Claude / Azure OpenAI) and the agents (prompt templates + limits)
built on top of them, and publish agents to mint their invoke credentials.

This app was split out of `talentos-app`'s former "Agent Builder" section so that each major
platform capability gets its own dedicated frontend: `iam-console` (org/user/role admin),
`talentos-app` (recruiting), and this app (model + agent management). A separate `portal` app
is the platform's single login page and launcher, handing off a session to whichever of these
apps the user picks.

## Architecture

- **Relying party, not an identity provider.** This app never logs a user in itself. It reads a
  post-login token handoff out of the URL fragment (`#access_token=...&refresh_token=...&organization_id=...`),
  set by the `portal` app, stores the tokens in `sessionStorage`, and strips the fragment from the
  address bar. If there's no valid session, it redirects to `portal`'s `/login?return_to=<this
  app's URL>` so the user can log in and get handed back here. See `src/lib/auth.ts`.
- **Bearer-token API client with silent refresh.** `src/api/client.ts`'s `agentBuilderClient` is
  an axios instance that attaches `Authorization: Bearer <access_token>` to every request,
  proactively refreshing the token when it's within 30s of expiry (and reactively on a 401),
  coalescing concurrent refreshes into one in-flight call. On refresh failure, it clears the
  session and redirects back to the portal to log in again.
- **Talks to exactly one backend**: `agent-builder-service` (default `http://localhost:8002/api/v1`).
  It never calls `talentos-app`'s or `iam-console`'s backends - only the `iam-service` token
  refresh endpoint directly, same pattern as `talentos-app`.

## Pages

- **Agents** (`/agents`) - list agents, their status (draft/published), and primary model.
- **Agents -> New agent** (`/agents/new`) - create a draft agent: system prompt, user prompt
  template (`{{placeholders}}` become required input variables automatically), primary/fallback
  model, and limits (max output tokens, timeout, rate limit).
- **Agents -> detail** (`/agents/:id`) - view an agent, publish it (mints its invoke credential),
  regenerate the credential, see the credential(s) on record (`client_id` + status - never the
  secret after the moment it's shown), and recent invocation usage.
- **Models** (`/models`) - list registered model deployments and register a new one (Claude or
  Azure OpenAI, with credentials encrypted at rest server-side).

## A note on agent invoke credentials (post-IAM-migration)

`agent-builder-service` went through an IAM migration: agents no longer get a simple, locally-
generated API key. Publishing an agent now mints a resource-bound iam-service `ServicePrincipal`
(`resource_type=agent`), and the pair needed to actually call `/invoke` is:

- `client_secret` - returned **once**, either in the `publish` response (first publish only) or
  the `keys/regenerate` response. This app never re-displays it after that.
- `client_id` - safe to display indefinitely, fetched separately via `GET /agents/{id}/keys`
  (`listAgentCredentials` in `src/api/agentBuilder.ts`), shown in the agent detail page's
  "Credentials" table.

To actually invoke an agent, exchange both for a short-lived Bearer token via iam-service's
`POST /auth/token`, then call `agent-builder-service`'s `POST /invoke` with it - see
`agent-builder-service`'s README for the full flow. This console only manages
publish/regenerate/view; it doesn't call `/invoke` itself.

## Setup

```bash
cp .env.example .env   # adjust URLs if your services run elsewhere
npm install
npm run dev             # serves http://localhost:5176
```

## Environment variables

| Variable                            | Default                          | Purpose                                                          |
|--------------------------------------|-----------------------------------|-------------------------------------------------------------------|
| `VITE_AGENT_BUILDER_API_BASE_URL`    | `http://localhost:8002/api/v1`   | `agent-builder-service`'s admin API                                |
| `VITE_IAM_SERVICE_URL`               | `http://localhost:8003`          | Direct token-refresh calls (`POST /auth/token/refresh`)            |
| `VITE_PORTAL_URL`                    | `http://localhost:5175`          | Where an unauthenticated visitor is sent to log in (`/login`)      |

## Build

```bash
npm run build   # tsc -b && vite build
```
