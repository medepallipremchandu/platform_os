import axios from "axios";
import { iamClient } from "./client";
import type { LoginRequest, OrgMembershipOption, TokenPair } from "../types";

export type LoginResult =
  | { status: "success"; tokens: TokenPair }
  | { status: "multi_org"; memberships: OrgMembershipOption[] };

/** POST /auth/login. On a multi-org account with no `organization_id` specified, iam-service
 * answers 409 with `{detail: {message, memberships: [{organization_id, organization_name}]}}` -
 * the login page re-prompts for an org and re-submits with it. */
export async function login(payload: LoginRequest): Promise<LoginResult> {
  try {
    const { data } = await iamClient.post<TokenPair>("/auth/login", payload);
    return { status: "success", tokens: data };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 409) {
      const detail = (error.response.data as { detail?: { memberships?: unknown } })?.detail;
      const raw = Array.isArray(detail?.memberships) ? detail.memberships : [];
      const memberships: OrgMembershipOption[] = (
        raw as { organization_id: string; organization_name: string }[]
      ).map((m) => ({ id: m.organization_id, name: m.organization_name }));
      return { status: "multi_org", memberships };
    }
    throw error;
  }
}

/** Best-effort server-side revoke on sign-out. Callers clear local tokens regardless of whether
 * this succeeds. */
export async function logout(): Promise<void> {
  await iamClient.post("/auth/logout");
}

/** POST /auth/password-reset/request. Answers 202 whether or not the address exists - callers
 * must not render anything that would reveal which. */
export async function requestPasswordReset(email: string): Promise<void> {
  await iamClient.post("/auth/password-reset/request", { email });
}

/** POST /auth/password-reset/confirm - the single endpoint behind BOTH the invite/first-login
 * flow and forgot-password. iam-service uses one token type for both, and also flips a
 * status="invited" user to "active" here, so there is no separate activation call to make. */
export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await iamClient.post("/auth/password-reset/confirm", { token, new_password: newPassword });
}
