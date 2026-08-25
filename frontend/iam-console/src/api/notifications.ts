import axios, { type InternalAxiosRequestConfig } from "axios";
import { ensureFreshSession } from "./client";
import { getAccessToken } from "../lib/auth";
import type {
  CreateProviderConfigRequest,
  EmailLogPage,
  NotificationProviderConfig,
  ProviderKind,
  ProviderSpec,
  ProviderTestResult,
  ResolvedProviders,
  UpdateProviderConfigRequest,
} from "../types";

const NOTIFICATION_SERVICE_URL = import.meta.env.VITE_NOTIFICATION_SERVICE_URL || "http://localhost:8104";

/** notification-service is a second backend this console talks to - it validates the very same
 * iam-service RS256 access token, as a relying party, so the session is shared and there is
 * nothing extra to sign into.
 *
 * A separate axios instance rather than a second baseURL on `iamClient`, because the two are
 * different origins with different lifecycles. Token refresh is still delegated to `client.ts`
 * (`ensureFreshSession`) so there is exactly one refresh-rotation implementation in the app -
 * duplicating it here would mean two callers racing to rotate the same refresh token, which the
 * server treats as reuse and punishes by revoking the whole family. */
export const notificationClient = axios.create({
  baseURL: NOTIFICATION_SERVICE_URL,
  headers: { "Content-Type": "application/json" },
});

notificationClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  try {
    await ensureFreshSession();
  } catch {
    // Fall through - the request will 401 and the caller surfaces it.
  }
  const token = getAccessToken();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

/** The provider registry: every provider notification-service knows, with its field spec. The
 * config form is rendered from this, so a provider added on the backend appears here with no
 * frontend change. */
export async function listProviderCatalog(): Promise<ProviderSpec[]> {
  const { data } = await notificationClient.get<ProviderSpec[]>("/providers/catalog");
  return data;
}

export async function listProviderConfigs(
  organizationId: string,
  kind?: ProviderKind,
): Promise<NotificationProviderConfig[]> {
  const { data } = await notificationClient.get<NotificationProviderConfig[]>(
    `/organizations/${organizationId}/notification-providers`,
    { params: { kind } },
  );
  return data;
}

/** What the organization's notifications will actually use right now, after the
 * organization-config-or-platform-default fallback. */
export async function getResolvedProviders(organizationId: string): Promise<ResolvedProviders> {
  const { data } = await notificationClient.get<ResolvedProviders>(
    `/organizations/${organizationId}/notification-providers/resolved`,
  );
  return data;
}

export async function createProviderConfig(
  organizationId: string,
  payload: CreateProviderConfigRequest,
): Promise<NotificationProviderConfig> {
  const { data } = await notificationClient.post<NotificationProviderConfig>(
    `/organizations/${organizationId}/notification-providers`,
    payload,
  );
  return data;
}

/** Omitting a secret inside `config` keeps the stored value - the API never returns secrets, so
 * a round-tripped form has nothing to resend. */
export async function updateProviderConfig(
  organizationId: string,
  configId: string,
  payload: UpdateProviderConfigRequest,
): Promise<NotificationProviderConfig> {
  const { data } = await notificationClient.patch<NotificationProviderConfig>(
    `/organizations/${organizationId}/notification-providers/${configId}`,
    payload,
  );
  return data;
}

/** Soft delete: the row is archived and disabled, never removed - the platform-wide convention. */
export async function archiveProviderConfig(
  organizationId: string,
  configId: string,
): Promise<NotificationProviderConfig> {
  const { data } = await notificationClient.delete<NotificationProviderConfig>(
    `/organizations/${organizationId}/notification-providers/${configId}`,
  );
  return data;
}

/** Opens a real connection to the configured relay or broker. Answers 200 with `{ok: false}` on
 * a bad credential rather than erroring - a failed test is an expected outcome, not a fault. */
export async function testProviderConfig(organizationId: string, configId: string): Promise<ProviderTestResult> {
  const { data } = await notificationClient.post<ProviderTestResult>(
    `/organizations/${organizationId}/notification-providers/${configId}/test`,
  );
  return data;
}

export async function listEmailLogs(organizationId: string, limit = 25, offset = 0): Promise<EmailLogPage> {
  const { data } = await notificationClient.get<EmailLogPage>(`/organizations/${organizationId}/email-logs`, {
    params: { limit, offset },
  });
  return data;
}
