# portal

The single login entry point for the TalentOS platform.

A user opens `portal`, signs in once, and lands on a launcher screen listing the other
platform apps they have access to. Picking one hands off the session (as a token pair) to
that app and navigates there directly. `portal` hosts no business features of its own - just
auth and this launcher.

## How it fits the platform

Today, `iam-console` has its own login page and `talentos-app` redirects there when it has no
session. That's being restructured so `portal` is the *only* app with a login form:

- `iam-console`, `talentos-app`, and `agent-builder-console` are (or are becoming) pure
  "relying party" apps: each one just checks for a valid session on load, and if it doesn't
  have one, redirects to `portal` with `?return_to=<its own URL>`.
- `portal` authenticates the user against `iam-service`, then either:
  - hands the resulting tokens straight back to `return_to` (the redirect case), or
  - shows the launcher (a direct visit to `portal` with no `return_to`).
- Clicking a launcher tile performs the same handoff: the tokens are appended to that app's
  URL in the fragment (`#access_token=...&refresh_token=...&organization_id=...`), never the
  query string, so they aren't sent to the receiving server or logged. The receiving app reads
  `location.hash` once on load, stores the tokens, and strips the fragment.

This mirrors the handoff mechanism `iam-console`'s `LoginPage.tsx`/`lib/auth.ts` and
`talentos-app`'s `lib/auth.ts` (`consumeHandoffFragment`) already implement today - `portal` is
essentially the login+handoff half of that round trip extracted into its own app, so it can be
the one place every relying-party app points at instead of `iam-console`.

## Launcher tile visibility

Each tile is gated on the signed-in user's access token carrying at least one permission whose
code starts with a given prefix (decoded client-side from the JWT's `permissions` claim - the
token isn't re-verified here, iam-service already did that):

| Tile | Destination | Required permission prefix |
| --- | --- | --- |
| IAM Console | `VITE_IAM_CONSOLE_URL` | `talentos.iam.` |
| Agent Builder | `VITE_AGENT_BUILDER_CONSOLE_URL` | `talentos.agentbuilder.` |
| TalentOS | `VITE_TALENTOS_APP_URL` | `talentos.intake.` |

A tile with no matching permission is hidden entirely, not just disabled. If a user has none
of the three, the launcher shows an empty-state message instead of a blank grid.

## Setup

```bash
npm install
cp .env.example .env   # then adjust URLs if any service runs somewhere non-default
npm run dev            # http://localhost:5175
```

`npm run build` type-checks (`tsc -b`) and produces a production build via Vite.

## Environment variables

See `.env.example`. All backend/app URLs are configured this way - nothing is hardcoded:

- `VITE_IAM_SERVICE_URL` - the only backend `portal` talks to directly (`/auth/login`,
  `/auth/logout`).
- `VITE_IAM_CONSOLE_URL`, `VITE_TALENTOS_APP_URL`, `VITE_AGENT_BUILDER_CONSOLE_URL` - the
  three launcher destinations. These double as the allow-list for `?return_to=` - a handoff is
  only ever sent to one of these origins, never to an arbitrary URL a query param could name.

## Source layout

- `src/lib/auth.ts` - token storage (sessionStorage, key-prefixed `portal.*`), JWT decode,
  session checks, permission-prefix gating, and the `buildHandoffUrl`/`isAllowedReturnTarget`
  handoff mechanism.
- `src/lib/destinations.ts` - the platform's other apps, sourced from env vars, with the
  permission prefix and icon used to render/gate each launcher tile.
- `src/api/` - the `iam-service` client (`client.ts`) and the login/logout calls (`iam.ts`),
  including the multi-org 409 handling.
- `src/pages/LoginPage.tsx` - email + password form, multi-org picker, and the `return_to`
  handoff.
- `src/pages/LauncherPage.tsx` - the tile grid, sign-out, and "signed in as" label.
- `src/components/ui/` - the same design-token-driven component library as `iam-console`
  (`Button`, `Card`, `EmptyState`, `Spinner`, `icons.tsx`), trimmed to what this app uses.
- `src/index.css` / `src/App.css` - design tokens and component styles, copied from
  `iam-console` so the two apps read as one product family.
