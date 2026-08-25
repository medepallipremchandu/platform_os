import type { AccessTokenClaims, TokenPair } from "../types";

/** sessionStorage (not localStorage) so a session doesn't silently outlive the tab, matching
 * iam-console's own posture. */
const ACCESS_TOKEN_KEY = "talentos.access_token";
const REFRESH_TOKEN_KEY = "talentos.refresh_token";

const PORTAL_URL = import.meta.env.VITE_PORTAL_URL || "http://localhost:5175";

/** Decode a JWT payload without verifying its signature - safe client-side, see iam-console's
 * identical helper for why (the backends are the only parties that need to verify it). */
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

export function isAccessTokenExpired(bufferSeconds = 0): boolean {
  const claims = getClaims();
  if (!claims) return true;
  const nowSeconds = Date.now() / 1000;
  return claims.exp - bufferSeconds <= nowSeconds;
}

export function hasValidSession(): boolean {
  return getAccessToken() !== null && getRefreshToken() !== null && !isAccessTokenExpired();
}

export function currentPrincipalLabel(): string {
  const claims = getClaims();
  if (!claims) return "";
  return claims.email || claims.name || claims.sub;
}

export function hasPermission(code: string): boolean {
  return !!getClaims()?.permissions?.includes(code);
}

/** Reads a post-login token handoff out of the URL fragment (set by iam-console after a
 * successful login with `?return_to=<this app's URL>`), stores it, and strips the fragment from
 * the address bar so the tokens don't linger in browser history. Returns true if a handoff was
 * consumed. */
export function consumeHandoffFragment(): boolean {
  const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (!hash) return false;
  const params = new URLSearchParams(hash);
  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");
  if (!accessToken || !refreshToken) return false;
  storeTokens({ access_token: accessToken, refresh_token: refreshToken });
  const url = new URL(window.location.href);
  url.hash = "";
  window.history.replaceState({}, "", url.toString());
  return true;
}

/** Sends the browser to `portal` (the platform's one login page) to log in, carrying the
 * current URL as `return_to` so the handoff above lands the user back where they started. */
export function redirectToLogin(): void {
  const returnTo = encodeURIComponent(window.location.href);
  window.location.href = `${PORTAL_URL}/login?return_to=${returnTo}`;
}
