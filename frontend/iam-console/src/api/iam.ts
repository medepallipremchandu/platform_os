import { iamClient } from "./client";
import type {
  AuditLogFilters,
  AuditLogPageResponse,
  CreateOrganizationRequest,
  CreateRoleAssignmentRequest,
  CreateRoleDefinitionRequest,
  CreateServicePrincipalRequest,
  InviteUserRequest,
  OrgUser,
  Organization,
  OrganizationWithAdmin,
  Permission,
  RoleAssignment,
  RoleDefinition,
  ServicePrincipal,
  ServicePrincipalWithSecret,
  TokenPair,
  UpdateEntitlementsRequest,
  UpdateOrganizationRequest,
  UpdateRoleDefinitionRequest,
  UpdateServicePrincipalRequest,
  UpdateUserMembershipRequest,
} from "../types";

// --- Auth ---
// Login itself now happens in `portal` (the platform's one login page); this app only ever
// receives an already-issued session via the URL-fragment handoff (see lib/auth.ts).

export async function refreshTokens(refreshToken: string): Promise<TokenPair> {
  const { data } = await iamClient.post<TokenPair>("/auth/token/refresh", { refresh_token: refreshToken });
  return data;
}

export async function switchOrganization(organizationId: string): Promise<TokenPair> {
  const { data } = await iamClient.post<TokenPair>("/auth/token/switch-org", { organization_id: organizationId });
  return data;
}

export async function logout(): Promise<void> {
  await iamClient.post("/auth/logout");
}

// --- Organizations ---

/** Scoped server-side to what the caller can see: every organization for a superadmin, only
 * their own memberships for anyone else. There is no separate "list all" endpoint. */
export async function listOrganizations(): Promise<Organization[]> {
  const { data } = await iamClient.get<Organization[]>("/organizations");
  return data;
}

/** Superadmin-only. Provisions the organization, its permission ceiling, its first admin, that
 * admin's Organization Admin role assignment and the invite email in one call - so the response
 * carries both the organization and the admin that was created. */
export async function createOrganization(payload: CreateOrganizationRequest): Promise<OrganizationWithAdmin> {
  const { data } = await iamClient.post<OrganizationWithAdmin>("/organizations", payload);
  return data;
}

/** Superadmin-only. Replaces the whole ceiling; an empty list clears it back to unrestricted.
 * Takes effect on the next token issued to any member - nothing else needs re-synchronizing. */
export async function updateOrganizationEntitlements(
  id: string,
  payload: UpdateEntitlementsRequest,
): Promise<Organization> {
  const { data } = await iamClient.patch<Organization>(`/organizations/${id}/entitlements`, payload);
  return data;
}

export async function renameOrganization(id: string, payload: UpdateOrganizationRequest): Promise<Organization> {
  const { data } = await iamClient.patch<Organization>(`/organizations/${id}`, payload);
  return data;
}

export async function deactivateOrganization(id: string): Promise<Organization> {
  const { data } = await iamClient.post<Organization>(`/organizations/${id}/deactivate`);
  return data;
}

export async function reactivateOrganization(id: string): Promise<Organization> {
  const { data } = await iamClient.post<Organization>(`/organizations/${id}/reactivate`);
  return data;
}

// --- Users ---

export async function listOrgUsers(organizationId: string): Promise<OrgUser[]> {
  const { data } = await iamClient.get<OrgUser[]>(`/organizations/${organizationId}/users`);
  return data;
}

export async function inviteUser(organizationId: string, payload: InviteUserRequest): Promise<OrgUser> {
  const { data } = await iamClient.post<OrgUser>(`/organizations/${organizationId}/users`, payload);
  return data;
}

export async function updateOrgUser(
  organizationId: string,
  userId: string,
  payload: UpdateUserMembershipRequest,
): Promise<OrgUser> {
  const { data } = await iamClient.patch<OrgUser>(`/organizations/${organizationId}/users/${userId}`, payload);
  return data;
}

// --- Role definitions ---

export async function listRoleDefinitions(organizationId: string, includeArchived = false): Promise<RoleDefinition[]> {
  const { data } = await iamClient.get<RoleDefinition[]>("/role-definitions", {
    params: { organization_id: organizationId, include_archived: includeArchived || undefined },
  });
  return data;
}

export async function createRoleDefinition(payload: CreateRoleDefinitionRequest): Promise<RoleDefinition> {
  const { data } = await iamClient.post<RoleDefinition>("/role-definitions", payload);
  return data;
}

export async function updateRoleDefinition(id: string, payload: UpdateRoleDefinitionRequest): Promise<RoleDefinition> {
  const { data } = await iamClient.patch<RoleDefinition>(`/role-definitions/${id}`, payload);
  return data;
}

/** Soft delete: iam-service archives the role (`archived_at`) rather than removing it - see
 * the DELETE /role-definitions/{id} handler. Named `archiveRoleDefinition` here so call sites
 * read honestly instead of implying a hard delete. */
export async function archiveRoleDefinition(id: string): Promise<void> {
  await iamClient.delete(`/role-definitions/${id}`);
}

// --- Role assignments ---

export async function listRoleAssignments(organizationId: string, includeRevoked = false): Promise<RoleAssignment[]> {
  const { data } = await iamClient.get<RoleAssignment[]>("/role-assignments", {
    params: { organization_id: organizationId, include_revoked: includeRevoked || undefined },
  });
  return data;
}

export async function createRoleAssignment(payload: CreateRoleAssignmentRequest): Promise<RoleAssignment> {
  const { data } = await iamClient.post<RoleAssignment>("/role-assignments", payload);
  return data;
}

/** Soft delete: iam-service revokes the assignment (`revoked_at`) rather than removing it. */
export async function revokeRoleAssignment(id: string): Promise<void> {
  await iamClient.delete(`/role-assignments/${id}`);
}

// --- Service principals ---

export async function listServicePrincipals(organizationId: string): Promise<ServicePrincipal[]> {
  const { data } = await iamClient.get<ServicePrincipal[]>("/service-principals", {
    params: { organization_id: organizationId },
  });
  return data;
}

export async function renameServicePrincipal(id: string, payload: UpdateServicePrincipalRequest): Promise<ServicePrincipal> {
  const { data } = await iamClient.patch<ServicePrincipal>(`/service-principals/${id}`, payload);
  return data;
}

/** POST /service-principals returns `{service_principal, client_secret}` - flattened here so
 * callers get a single object matching `ServicePrincipalWithSecret`. */
export async function createServicePrincipal(payload: CreateServicePrincipalRequest): Promise<ServicePrincipalWithSecret> {
  const { data } = await iamClient.post<{ service_principal: ServicePrincipal; client_secret: string }>(
    "/service-principals",
    payload,
  );
  return { ...data.service_principal, client_secret: data.client_secret };
}

/** Rotate only returns `{client_secret}` (no full object) - the caller merges it onto the
 * service-principal row it already has in state. */
export async function rotateServicePrincipalSecret(sp: ServicePrincipal): Promise<ServicePrincipalWithSecret> {
  const { data } = await iamClient.post<{ client_secret: string }>(`/service-principals/${sp.id}/secret/rotate`);
  return { ...sp, client_secret: data.client_secret };
}

export async function revokeServicePrincipal(id: string): Promise<void> {
  await iamClient.delete(`/service-principals/${id}`);
}

// --- Permissions ---

export async function listPermissions(): Promise<Permission[]> {
  const { data } = await iamClient.get<Permission[]>("/permissions");
  return data;
}

// --- Audit log ---

/** GET /audit/events returns `{items, total, limit, offset}` - real offset-based pagination. */
export async function listAuditEvents(filters: AuditLogFilters): Promise<AuditLogPageResponse> {
  const { data } = await iamClient.get<AuditLogPageResponse>("/audit/events", { params: filters });
  return data;
}
