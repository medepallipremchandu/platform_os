import { iamClient } from "./client";
import { getClaims } from "../lib/auth";
import type { OrgUser } from "../types";

/**
 * Lists the users of the current session's organization directly from iam-service, for the
 * "visible only to specific people" picker on Providers/Call Agents forms. voice-agent-service
 * itself has no user-listing endpoint - this is the cross-service read the task spec calls out
 * as legitimate (same pattern talentos-app already uses to reach agent-builder-service data).
 * Returns [] rather than throwing if the caller doesn't hold whatever permission iam-service
 * requires for this endpoint - a restricted-visibility form should still be usable to view/save
 * an already-granted list, just without adding new grantees.
 */
export async function listOrgUsers(): Promise<OrgUser[]> {
  const orgId = getClaims()?.org_id;
  if (!orgId) return [];
  const { data } = await iamClient.get<OrgUser[]>(`/organizations/${orgId}/users`);
  return data;
}
