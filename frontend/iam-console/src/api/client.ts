import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { ApiErrorBody, TokenPair } from "../types";
import { clearTokens, getAccessToken, getRefreshToken, isAccessTokenExpired, storeTokens } from "../lib/auth";

const IAM_SERVICE_URL = import.meta.env.VITE_IAM_SERVICE_URL || "http://localhost:8003";

/** Registered by AuthProvider on mount and called whenever a refresh attempt itself fails, so
 * the app can clear session state and route back to /login. Kept out of this module (rather than
 * importing the router/context here) so client.ts stays a plain data layer. */
let sessionExpiredHandler: (() => void) | null = null;
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  sessionExpiredHandler = handler;
}

/** Calls iam-service: auth, organizations, users, role definitions, role assignments, service
 * principals, and the platform-wide audit log - the single control-plane backend this console
 * talks to. */
export const iamClient = axios.create({
  baseURL: IAM_SERVICE_URL,
  headers: { "Content-Type": "application/json" },
});

// Endpoints that must never carry a (possibly stale) Authorization header or trigger a refresh
// attempt - refreshing them would recurse, and login/refresh are called before any token exists.
const PUBLIC_PATHS = ["/auth/login", "/auth/token/refresh", "/.well-known/jwks.json"];

function isPublicPath(url?: string): boolean {
  return !!url && PUBLIC_PATHS.some((path) => url.startsWith(path));
}

// A bare axios instance with no interceptors, used only for the refresh call itself so it never
// recurses back through the request interceptor below.
const refreshClient = axios.create({
  baseURL: IAM_SERVICE_URL,
  headers: { "Content-Type": "application/json" },
});

let refreshPromise: Promise<TokenPair> | null = null;

/** Rotates the refresh token (per the design doc's reuse-detection scheme) and stores the new
 * pair. Concurrent callers share one in-flight request instead of each firing their own. */
async function refreshAccessToken(): Promise<TokenPair> {
  if (refreshPromise) return refreshPromise;
  const refresh_token = getRefreshToken();
  if (!refresh_token) throw new Error("No refresh token available");

  refreshPromise = refreshClient
    .post<TokenPair>("/auth/token/refresh", { refresh_token })
    .then(({ data }) => {
      storeTokens(data);
      return data;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

/** Refreshes the session if the access token is at/near expiry and a refresh token is available.
 * Silent on failure - callers that need the outcome should catch/inspect separately. Exported so
 * AuthProvider can also call this proactively on an interval, not just lazily per-request. */
export async function ensureFreshSession(bufferSeconds = 30): Promise<void> {
  if (isAccessTokenExpired(bufferSeconds) && getRefreshToken()) {
    await refreshAccessToken();
  }
}

iamClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (isPublicPath(config.url)) return config;

  try {
    await ensureFreshSession();
  } catch {
    // Fall through - the request will 401 and the response interceptor below handles it.
  }

  const token = getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

iamClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const shouldRetry =
      error.response?.status === 401 && originalRequest && !originalRequest._retried && !isPublicPath(originalRequest.url);

    if (shouldRetry && originalRequest) {
      originalRequest._retried = true;
      try {
        const tokens = await refreshAccessToken();
        originalRequest.headers.set("Authorization", `Bearer ${tokens.access_token}`);
        return iamClient(originalRequest);
      } catch {
        clearTokens();
        sessionExpiredHandler?.();
      }
    }
    return Promise.reject(error);
  },
);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
    if (error.message) return error.message;
  }
  return "Something went wrong. Please try again.";
}
