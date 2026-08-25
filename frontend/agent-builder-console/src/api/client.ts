import axios from "axios";
import { clearTokens, getAccessToken, getRefreshToken, isAccessTokenExpired, redirectToLogin, storeTokens } from "../lib/auth";
import type { ApiErrorBody, TokenPair } from "../types";

const AGENT_BUILDER_API_BASE_URL =
  import.meta.env.VITE_AGENT_BUILDER_API_BASE_URL || "http://localhost:8002/api/v1";
const IAM_SERVICE_URL = import.meta.env.VITE_IAM_SERVICE_URL || "http://localhost:8113";

/** agent-builder-service is an IAM relying party: every request needs `Authorization: Bearer
 * <access_token>`, refreshed proactively before it expires and reactively on a 401, obtained by
 * logging in via the portal app (see lib/auth.ts's redirect/handoff flow). */

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

/** Calls agent-builder-service's admin API (models/agents management) - the single backend this
 * app talks to. */
export const agentBuilderClient = axios.create({
  baseURL: AGENT_BUILDER_API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});
attachAuth(agentBuilderClient);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
    if (error.message) return error.message;
  }
  return "Something went wrong. Please try again.";
}
