import type { AccessTokenClaims, TokenPair } from "../types";
import { APP_DESTINATIONS } from "./destinations";

/** sessionStorage (not localStorage) so a session doesn't silently outlive the tab - matches the
 * "sign out everywhere" / short-lived-token posture in the iam-service design doc, and the same
 * choice iam-console/talentos-app already make. Each app runs on its own origin/port so
 * sessionStorage is already naturally isolated per-app, but a `portal.`-prefixed key is used
 * anyway for readability (and to avoid any confusion if this ever runs alongside another app
 * under the same origin, e.g. in a future combined deployment). */
const ACCESS_TOKEN_KEY = "portal.access_token";
const REFRESH_TOKEN_KEY = "portal.refresh_token";

/** Decode a JWT payload without verifying its signature. Safe to do client-side: the payload is
 * base64url-encoded, not encrypted, and iam-service (the only party that needs to trust it) does
 * its own signature verification server-side. This is purely so `portal` can read the
 * `permissions` / `org_id` / `email` claims to gate launcher tiles and show a "signed in as"
 * label. */
export function decodeToken(token: string): AccessTokenClaims | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join(""),
    );
    return JSON.parse(json) as AccessTokenClaims;
  } catch {
    return null;
  }
}

export function storeTokens(tokens: Pick<TokenPair, "access_token" | "refresh_token">): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  sessionStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getClaims(): AccessTokenClaims | null {
  const token = getAccessToken();
  return token ? decodeToken(token) : null;
}

/** True once the token is within `bufferSeconds` of `exp` (or already past it). */
export function isAccessTokenExpired(bufferSeconds = 0): boolean {
  const claims = getClaims();
  if (!claims) return true;
  const nowSeconds = Date.now() / 1000;
  return claims.exp - bufferSeconds <= nowSeconds;
}

export function hasValidSession(): boolean {
  return getAccessToken() !== null && getRefreshToken() !== null && !isAccessTokenExpired();
}

/** "Signed in as ..." display: the user's email, falling back to a `name` claim, falling back to
 * the raw subject id if neither is present - same fallback order as iam-console's
 * `currentPrincipalLabel`. */
export function currentPrincipalLabel(): string {
  const claims = getClaims();
  if (!claims) return "";
  return claims.email || claims.name || claims.sub;
}

/** Gates a launcher tile: true if the current session carries at least one permission whose
 * code starts with `prefix` (e.g. `"talentos.iam."`). */
export function hasPermissionPrefix(prefix: string): boolean {
  const claims = getClaims();
  return !!claims?.permissions?.some((code) => code.startsWith(prefix));
}

/** The platform tier above organizations.
 *
 * Load-bearing for the launcher: a superadmin belongs to no organization and therefore holds NO
 * org-scoped permissions at all, so `hasPermissionPrefix` is false for every tile. Gating purely
 * on permissions would hand them an empty launcher with no way into the one console they exist
 * to use. */
export function isSuperAdmin(): boolean {
  return getClaims()?.is_superadmin === true;
}

const ALLOWED_RETURN_ORIGINS = APP_DESTINATIONS.map((destination) => {
  try {
    return new URL(destination.url).origin;
  } catch {
    return null;
  }
}).filter((origin): origin is string => origin !== null);

/** A relying-party app (iam-console, talentos-app, agent-builder-console) redirects here with
 * `?return_to=<its own URL>` when it has no valid session. Only ever hand tokens back to one of
 * the platform's own known apps (`APP_DESTINATIONS`) - never redirect a token to an arbitrary URL
 * a query param could name. */
export function isAllowedReturnTarget(url: string): boolean {
  try {
    return ALLOWED_RETURN_ORIGINS.includes(new URL(url).origin);
  } catch {
    return false;
  }
}

/** Builds the post-login handoff URL: the tokens go in the fragment (`#...`), not the query
 * string, so they aren't sent to the receiving server or captured in access logs - the receiving
 * app reads `location.hash` once on load and immediately clears it via `history.replaceState`
 * (see talentos-app's `consumeHandoffFragment`). */
export function buildHandoffUrl(returnTo: string, tokens: TokenPair, organizationId: string | null): string {
  const fragment = new URLSearchParams({
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  });
  // Omitted rather than sent as the string "null" for a superadmin session, which the receiving
  // app would happily store and then use in an `organization_id=null` request.
  if (organizationId) fragment.set("organization_id", organizationId);
  return `${returnTo}#${fragment.toString()}`;
}
