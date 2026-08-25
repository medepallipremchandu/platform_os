import type { OrgUser, PrincipalType, ServicePrincipal } from "../types";
import { getClaims } from "./auth";

const PERMISSION_PREFIX = "talentos.";

/** Display labels for the service-namespace segment of a permission code
 * (`talentos.<namespace>.<resource>.<action>`) - the single place mapping the raw namespace
 * string to something a human reads in the role permission picker, matching the `tone.ts`
 * centralization pattern from the sibling app so no page re-derives this grouping itself. */
const NAMESPACE_LABELS: Record<string, string> = {
  iam: "Identity & Access (IAM)",
  intake: "Intake & Matching",
  agentbuilder: "Agent Builder",
};

export function namespaceForPermission(code: string): string {
  const withoutPrefix = code.startsWith(PERMISSION_PREFIX) ? code.slice(PERMISSION_PREFIX.length) : code;
  return withoutPrefix.split(".")[0] || "other";
}

export function namespaceLabel(namespace: string): string {
  return NAMESPACE_LABELS[namespace] || namespace;
}

export interface PermissionGroup {
  namespace: string;
  label: string;
  codes: string[];
}

export function groupPermissionsByNamespace(codes: string[]): PermissionGroup[] {
  const groups = new Map<string, string[]>();
  for (const code of codes) {
    const namespace = namespaceForPermission(code);
    if (!groups.has(namespace)) groups.set(namespace, []);
    groups.get(namespace)!.push(code);
  }
  return [...groups.entries()]
    .map(([namespace, list]) => ({ namespace, label: namespaceLabel(namespace), codes: list.sort() }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

/** Resolves a role assignment's `principal_id` to something a human reads, by cross-referencing
 * the org's users/service-principals lists the caller already has loaded (iam-service doesn't
 * resolve this server-side - see `RoleAssignment` in types.ts). Falls back to the raw id if the
 * principal isn't found in either list (e.g. it was since removed). */
export function principalLabelFor(
  principalType: PrincipalType,
  principalId: string,
  users: OrgUser[],
  servicePrincipals: ServicePrincipal[],
): string {
  if (principalType === "user") {
    const user = users.find((u) => u.user_id === principalId);
    return user ? user.display_name || user.email : principalId;
  }
  const sp = servicePrincipals.find((s) => s.id === principalId);
  return sp ? sp.name : principalId;
}

export function hasPermission(code: string): boolean {
  const claims = getClaims();
  return !!claims?.permissions?.includes(code);
}

export function hasAnyPermission(codes: string[]): boolean {
  return codes.some((code) => hasPermission(code));
}

/**
 * Permission codes the console's own UI gates on directly. Only `organizations.manage` and
 * `audit.read` are given verbatim in the iam-service contract; the rest follow the same
 * `talentos.iam.<resource>.<action>` convention shown by those two plus `users.invite` (also
 * given verbatim) and are this console's best-effort naming until iam-service's seed script is
 * final - see the README's "assumptions" section.
 */
export const PERMISSIONS = {
  ORGANIZATIONS_MANAGE: "talentos.iam.organizations.manage",
  USERS_INVITE: "talentos.iam.users.invite",
  USERS_MANAGE: "talentos.iam.users.manage",
  ROLES_MANAGE: "talentos.iam.roles.manage",
  ROLE_ASSIGNMENTS_MANAGE: "talentos.iam.role_assignments.manage",
  SERVICE_PRINCIPALS_MANAGE: "talentos.iam.service_principals.manage",
  AUDIT_READ: "talentos.iam.audit.read",
} as const;
