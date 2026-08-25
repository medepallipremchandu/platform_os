import axios, { type InternalAxiosRequestConfig } from "axios";
import type { ApiErrorBody } from "../types";
import { getAccessToken } from "../lib/auth";

const IAM_SERVICE_URL = import.meta.env.VITE_IAM_SERVICE_URL || "http://localhost:8003";

/** Calls iam-service. Unlike iam-console, `portal` never makes an authenticated call that
 * outlives the login moment (it decodes the freshly-minted access token locally to drive the
 * launcher, then hands the whole token pair off) - so there's no refresh-on-401 interceptor here,
 * just a plain client for `/auth/login` and a best-effort `/auth/logout` on sign-out. */
export const iamClient = axios.create({
  baseURL: IAM_SERVICE_URL,
  headers: { "Content-Type": "application/json" },
});

// /auth/login must never carry a (possibly stale) Authorization header - it's called before any
// token exists.
const PUBLIC_PATHS = ["/auth/login"];

function isPublicPath(url?: string): boolean {
  return !!url && PUBLIC_PATHS.some((path) => url.startsWith(path));
}

iamClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (isPublicPath(config.url)) return config;
  const token = getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(", ");
    if (error.message) return error.message;
  }
  return "Something went wrong. Please try again.";
}
