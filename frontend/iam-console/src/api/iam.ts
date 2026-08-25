import { iamClient } from "./client";
import type {
  AuditLogFilters,
  AuditLogPageResponse,
  CreateRoleAssignmentRequest,
  CreateRoleDefinitionRequest,
  CreateServicePrincipalRequest,
  InviteUserRequest,
  OrgUser,
  Organization,
  Permission,
  RoleAssignment,
  RoleDefinition,
  ServicePrincipal,
  ServicePrincipalWithSecret,
  TokenPair,
  UpdateRoleDefinitionRequest,
  UpdateUserStatusRequest,
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

export async function listOrganizations(): Promise<Organization[]> {
  const { data } = await iamClient.get<Organization[]>("/organizations");
  return data;
}

export async function createOrganization(name: string): Promise<Organization> {
  const { data } = await iamClient.post<Organization>("/organizations", { name });
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

export async function updateUserStatus(
  organizationId: string,
  userId: string,
  payload: UpdateUserStatusRequest,
): Promise<OrgUser> {
  const { data } = await iamClient.patch<OrgUser>(`/organizations/${organizationId}/users/${userId}`, payload);
  return data;
}

// --- Role definitions ---

export async function listRoleDefinitions(organizationId: string): Promise<RoleDefinition[]> {
  const { data } = await iamClient.get<RoleDefinition[]>("/role-definitions", {
    params: { organization_id: organizationId },
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

export async function deleteRoleDefinition(id: string): Promise<void> {
  await iamClient.delete(`/role-definitions/${id}`);
}

// --- Role assignments ---

export async function listRoleAssignments(organizationId: string): Promise<RoleAssignment[]> {
  const { data } = await iamClient.get<RoleAssignment[]>("/role-assignments", {
    params: { organization_id: organizationId },
  });
  return data;
}

export async function createRoleAssignment(payload: CreateRoleAssignmentRequest): Promise<RoleAssignment> {
  const { data } = await iamClient.post<RoleAssignment>("/role-assignments", payload);
  return data;
}

export async function deleteRoleAssignment(id: string): Promise<void> {
  await iamClient.delete(`/role-assignments/${id}`);
}

// --- Service principals ---

export async function listServicePrincipals(organizationId: string): Promise<ServicePrincipal[]> {
  const { data } = await iamClient.get<ServicePrincipal[]>("/service-principals", {
    params: { organization_id: organizationId },
  });
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
