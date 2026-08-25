import axios from "axios";
import { clearTokens, getAccessToken, getRefreshToken, isAccessTokenExpired, redirectToLogin, storeTokens } from "../lib/auth";
import type { ApiErrorBody, TokenPair } from "../types";

const VOICE_AGENT_SERVICE_URL = import.meta.env.VITE_VOICE_AGENT_SERVICE_URL || "http://localhost:8004";
const IAM_SERVICE_URL = import.meta.env.VITE_IAM_SERVICE_URL || "http://localhost:8113";

/** voice-agent-service (and iam-service, for the couple of direct calls below) are IAM relying
 * parties: every request needs `Authorization: Bearer <access_token>`, refreshed proactively
 * before it expires and reactively on a 401, obtained by logging in via the portal app (see
 * lib/auth.ts's redirect/handoff flow). Mirrors agent-builder-console's client.ts exactly. */

let refreshInFlight: Promise<TokenPair> | null = null;

async function refreshSession(): Promise<TokenPair> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) throw new Error("No refresh token");
  const { data } = await axios.post<TokenPair>(`${IAM_SERVICE_URL}/auth/token/refresh`, { refresh_token: refreshToken });
  storeTokens(data);
  return data;
}

/** Ensures the stored access token is valid, refreshing it first if it's within 30s of expiry.
 * Coalesces concurrent callers onto a single in-flight refresh. */
export async function ensureFreshSession(): Promise<void> {
  if (!getAccessToken() || !isAccessTokenExpired(30)) return;
  if (!refreshInFlight) {
    refreshInFlight = refreshSession().finally(() => {
      refreshInFlight = null;
    });
  }
  try {
    await refreshInFlight;
  } catch {
    clearTokens();
    redirectToLogin();
    throw new Error("Session expired");
  }
}

function attachAuth(client: ReturnType<typeof axios.create>) {
  client.interceptors.request.use(async (config) => {
    await ensureFreshSession();
    const token = getAccessToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const original = error.config;
      if (axios.isAxiosError(error) && error.response?.status === 401 && !original._retried) {
        original._retried = true;
        try {
          const tokens = await refreshSession();
          original.headers.Authorization = `Bearer ${tokens.access_token}`;
          return client(original);
        } catch {
          clearTokens();
          redirectToLogin();
        }
      }
      return Promise.reject(error);
    },
  );
}

/** Calls voice-agent-service's admin API (providers/call agents/calls) - the primary backend
 * this app talks to. */
export const voiceAgentClient = axios.create({
  baseURL: VOICE_AGENT_SERVICE_URL,
  headers: { "Content-Type": "application/json" },
});
attachAuth(voiceAgentClient);

/** Calls iam-service directly for two things: (1) token refresh (above, via plain axios calls,
 * not this client) and (2) `GET /organizations/{id}/users` to populate the restricted-visibility
 * user picker - a legitimate cross-service read, since both services are IAM relying parties
 * trusting the same bearer token (see `src/api/iam.ts`). */
export const iamClient = axios.create({
  baseURL: IAM_SERVICE_URL,
  headers: { "Content-Type": "application/json" },
});
attachAuth(iamClient);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
    if (error.message) return error.message;
  }
  return "Something went wrong. Please try again.";
}
