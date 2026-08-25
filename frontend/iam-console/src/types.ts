// Types mirror iam-service's documented API contract (see
// docs/superpowers/specs/2026-08-24-iam-service-design.md). iam-service may not exist yet or may
// be mid-build; nothing here should assume more than that design doc specifies.

export interface ApiErrorBody {
  detail?: string | { msg: string; loc: (string | number)[] }[];
}

// --- Auth / tokens ---
// Login itself happens in `portal`, not here - this app only ever consumes an already-issued
// session via the URL-fragment handoff (see lib/auth.ts).

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  organization_id: string;
}

/** Shape of the decoded access-token JWT payload (RS256, unencrypted - safe to read client-side). */
export interface AccessTokenClaims {
  sub: string;
  principal_type: "user" | "service_principal";
  org_id: string;
  permissions: string[];
  resource_scope?: { type: string; id: string };
  iat: number;
  exp: number;
  jti: string;
  email?: string;
  name?: string;
}

// --- Organizations ---

export interface Organization {
  id: string;
  name: string;
  created_at: string;
}

// --- Users ---

export type UserStatus = "invited" | "active" | "disabled";

/** One row of `GET /organizations/{id}/users` - `id` is the membership row's id, `user_id` is
 * the actual user's id (the one to use as a role assignment's `principal_id`).
 * `membership_status` (active/disabled) is what invite/enable/disable actually controls;
 * `user_status` reflects the underlying user account and isn't editable from here. */
export interface OrgUser {
  id: string;
  user_id: string;
  email: string;
  display_name: string | null;
  membership_status: UserStatus;
  user_status: UserStatus;
  created_at: string;
}

export interface InviteUserRequest {
  email: string;
  display_name: string;
}

export interface UpdateUserStatusRequest {
  status: UserStatus;
}

// --- Roles & permissions ---

export interface RoleDefinition {
  id: string;
  name: string;
  organization_id: string | null;
  is_builtin: boolean;
  permissions: string[];
}

export interface CreateRoleDefinitionRequest {
  name: string;
  organization_id: string;
  permission_codes: string[];
}

export interface UpdateRoleDefinitionRequest {
  name?: string;
  permission_codes?: string[];
}

// --- Role assignments ---

export type PrincipalType = "user" | "service_principal";
export type ScopeType = "organization" | "service";
export const KNOWN_SERVICES = ["talentos-app", "agent-builder", "iam"] as const;
export type ServiceName = (typeof KNOWN_SERVICES)[number];

/** iam-service doesn't resolve a display label for the principal - callers cross-reference
 * `principal_id` against the users/service-principals lists they already load (see
 * `lib/permissions.ts::principalLabelFor`). */
export interface RoleAssignment {
  id: string;
  principal_type: PrincipalType;
  principal_id: string;
  role_definition_id: string;
  role_name: string;
  organization_id: string;
  scope_type: ScopeType;
  scope_id: string;
  created_at: string;
}

export interface CreateRoleAssignmentRequest {
  principal_type: PrincipalType;
  principal_id: string;
  role_definition_id: string;
  scope_type: ScopeType;
  service_name?: ServiceName;
}

// --- Service principals ---

export interface ServicePrincipal {
  id: string;
  client_id: string;
  name: string;
  resource_type: string | null;
  resource_id: string | null;
  revoked_at: string | null;
}

export interface CreateServicePrincipalRequest {
  name: string;
  organization_id: string;
  resource_type?: string;
  resource_id?: string;
}

/** Only ever returned once, from create or rotate - never persisted or re-fetchable. `create`
 * returns `{service_principal, client_secret}` and `rotate` returns just `{client_secret}`;
 * api/iam.ts normalizes both into this flat shape (rotate merges the secret onto the row
 * already held in the caller's state, since the endpoint doesn't re-return the full object). */
export interface ServicePrincipalWithSecret extends ServicePrincipal {
  client_secret: string;
}

// --- Permissions ---

export interface Permission {
  code: string;
  description: string | null;
}

// --- Audit log ---

export type AuditActorType = "user" | "service_principal" | "system";
export type AuditResult = "success" | "denied" | "error";

export interface AuditLogEntry {
  id: string;
  occurred_at: string;
  actor_type: AuditActorType;
  actor_id: string;
  action: string;
  target_type: string;
  target_id: string;
  result: AuditResult;
  correlation_id: string;
  source_ip: string | null;
  changes: Record<string, { old: unknown; new: unknown }> | null;
}

export interface AuditLogFilters {
  organization_id: string;
  actor_id?: string;
  action?: string;
  result?: AuditResult;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface AuditLogPageResponse {
  items: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
}
