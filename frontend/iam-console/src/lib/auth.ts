import type { AccessTokenClaims, TokenPair } from "../types";

/** sessionStorage (not localStorage) so a session doesn't silently outlive the tab - matches the
 * "sign out everywhere" / short-lived-token posture in the iam-service design doc. */
const ACCESS_TOKEN_KEY = "iam_console.access_token";
const REFRESH_TOKEN_KEY = "iam_console.refresh_token";

/** Decode a JWT payload without verifying its signature. Safe to do client-side: the payload is
 * base64url-encoded, not encrypted, and iam-service (the only party that needs to trust it) does
 * its own signature verification server-side. This is purely so the console can read the
 * `permissions` / `org_id` / `email` claims to drive UI gating and the "logged in as" display. */
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

export function storeTokens(tokens: TokenPair): void {
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

/** True once the token is within `bufferSeconds` of `exp` (or already past it). Used both to
 * decide whether to proactively refresh before a request, and to validate a stored session on
 * app load. */
export function isAccessTokenExpired(bufferSeconds = 0): boolean {
  const claims = getClaims();
  if (!claims) return true;
  const nowSeconds = Date.now() / 1000;
  return claims.exp - bufferSeconds <= nowSeconds;
}

export function hasValidSession(): boolean {
  return getAccessToken() !== null && getRefreshToken() !== null && !isAccessTokenExpired();
}

/** "Logged in as ..." display: the user's email for a human principal, the service principal's
 * name for a machine principal, falling back to the raw subject id if neither claim is present. */
export function currentPrincipalLabel(): string {
  const claims = getClaims();
  if (!claims) return "";
  return claims.email || claims.name || claims.sub;
}

const PORTAL_URL = import.meta.env.VITE_PORTAL_URL || "http://localhost:5175";

/** Declared here rather than imported from api/client.ts: that module imports from this one, so
 * importing it back would be a cycle. */
const IAM_SERVICE_URL = import.meta.env.VITE_IAM_SERVICE_URL || "http://localhost:8113";

/** Reads a post-login token handoff out of the URL fragment (set by `portal`, the platform's
 * one login page, after a successful login with `?return_to=<this app's URL>`), stores it, and
 * strips the fragment from the address bar. Must run before anything reads session state (see
 * `main.tsx`, which calls this before the app mounts) so the very first render already sees the
 * freshly-arrived session. Returns true if a handoff was consumed. */
export function consumeHandoffFragment(): boolean {
  const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (!hash) return false;
  const params = new URLSearchParams(hash);
  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");
  if (!accessToken || !refreshToken) return false;
  storeTokens({ access_token: accessToken, refresh_token: refreshToken, token_type: "bearer", expires_in: 0, organization_id: "" });
  const url = new URL(window.location.href);
  url.hash = "";
  window.history.replaceState({}, "", url.toString());
  return true;
}

/** Sends the browser to `portal` to log in, carrying the current URL as `return_to` so the
 * handoff above lands the user back where they started. */
export function redirectToLogin(): void {
  const returnTo = encodeURIComponent(window.location.href);
  window.location.href = `${PORTAL_URL}/login?return_to=${returnTo}`;
}

/** Signs out of the whole platform, not just this app.
 *
 * Clearing this app's own storage is not enough. Every app keeps its session in its OWN
 * sessionStorage, so clearing only here bounces to `portal`, which still has a valid session and
 * hands the very same one straight back through the `return_to` handoff - to the user that looks
 * like the page reloading and never logging out. Sign-out therefore has to finish at `portal`,
 * which owns the session everything else is handed from. */
export function redirectToLogout(): void {
  // Revoke server-side from HERE, before leaving. portal's /logout also calls this endpoint, but
  // only with portal's own token - and portal may have no live session in this browser (the user
  // arrived by a handoff in another tab, or portal's sessionStorage was cleared). Doing it from
  // the app the user actually clicked in makes the revoke unconditional.
  //
  // keepalive is the load-bearing part: the navigation on the last line would otherwise cancel
  // this request in flight, which is exactly the "logout doesn't work" symptom - local state
  // cleared, refresh token still live on the server.
  const token = getAccessToken();
  if (token) {
    void fetch(`${IAM_SERVICE_URL}/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      keepalive: true,
    }).catch(() => {
      // Best-effort. The local session is cleared either way, and portal's /logout retries.
    });
  }
  clearTokens();
  window.location.href = `${PORTAL_URL}/logout`;
}

