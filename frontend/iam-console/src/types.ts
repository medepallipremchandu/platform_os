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
  /** Null for a platform superadmin, who belongs to no organization. Every org-scoped fetch in
   * this app must therefore guard on it rather than assuming a UUID - see `useOrgId()`. */
  org_id: string | null;
  permissions: string[];
  resource_scope?: { type: string; id: string };
  iat: number;
  exp: number;
  jti: string;
  email?: string;
  name?: string;
  /** The platform tier above organizations. A separate axis from `permissions` on purpose: an
   * organization owner holding every talentos.iam.* permission is still not a superadmin. Gate
   * on `isSuperAdmin()`, never on a permission code. */
  is_superadmin?: boolean;
}

// --- Organizations ---

export interface Organization {
  id: string;
  name: string;
  is_active: boolean;
  /** The permission ceiling: codes this organization is allowed to grant at all. `null` means
   * unrestricted, NOT "none allowed" - iam-service intersects with it only when it is non-empty. */
  allowed_permissions: string[] | null;
  created_at: string;
}

export interface UpdateOrganizationRequest {
  name: string;
}

/** Superadmin-only tenant provisioning: organization, ceiling and first admin in one call. */
export interface CreateOrganizationRequest {
  name: string;
  admin_email: string;
  admin_display_name?: string;
  allowed_permission_codes: string[];
}

export interface OrganizationAdmin {
  id: string;
  email: string;
  display_name: string | null;
  status: UserStatus;
}

export interface OrganizationWithAdmin {
  organization: Organization;
  admin: OrganizationAdmin;
}

export interface UpdateEntitlementsRequest {
  allowed_permission_codes: string[];
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

/** Both fields optional (send only what changed) - at least one is required by the server. */
export interface UpdateUserMembershipRequest {
  status?: UserStatus;
  display_name?: string;
}

// --- Roles & permissions ---

export interface RoleDefinition {
  id: string;
  name: string;
  organization_id: string | null;
  is_builtin: boolean;
  archived_at: string | null;
  created_at: string;
  // The API returns the full permission catalog rows (id/code/description) attached to this
  // role, not bare codes - see `permissionCodesOf()` in lib/permissions.ts for the one place
  // that flattens this down to the string[] a create/update payload actually needs.
  permissions: Permission[];
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
export const KNOWN_SERVICES = ["talentos-app", "agent-builder", "voice-agent", "iam"] as const;
export type ServiceName = (typeof KNOWN_SERVICES)[number];

/** iam-service doesn't resolve a display label for the principal - callers cross-reference
 * `principal_id` against the users/service-principals lists they already load (see
 * `lib/permissions.ts::principalLabelFor`). */
export interface RoleAssignment {
  id: string;
  principal_type: PrincipalType;
  principal_id: string;
  role_definition_id: string;
  role_definition_name: string | null;
  organization_id: string;
  scope_type: ScopeType;
  scope_id: string;
  revoked_at: string | null;
  created_at: string;
}

export interface CreateRoleAssignmentRequest {
  principal_type: PrincipalType;
  principal_id: string;
  role_definition_id: string;
  organization_id: string;
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
  created_at: string;
}

export interface CreateServicePrincipalRequest {
  name: string;
  organization_id: string;
  resource_type?: string;
  resource_id?: string;
}

export interface UpdateServicePrincipalRequest {
  name: string;
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
  id: string;
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

// --- Notification providers (notification-service, not iam-service) ---

export type ProviderKind = "email" | "queue";

/** One configurable field of a provider, as declared by the provider class itself. The console
 * renders forms from this rather than hardcoding a form per vendor, which is why adding a
 * provider on the backend needs no change here. */
export interface ProviderFieldSpec {
  name: string;
  label: string;
  type: "string" | "int" | "bool" | "email" | "text";
  required: boolean;
  secret: boolean;
  default: unknown;
  help: string | null;
  placeholder: string | null;
}

export interface ProviderSpec {
  kind: ProviderKind;
  key: string;
  label: string;
  description: string;
  fields: ProviderFieldSpec[];
}

/** Note what is absent: any secret value. Secrets are write-only - `secrets_set` names which
 * secret fields have a stored value so the form can show "set" without ever receiving it. */
export interface NotificationProviderConfig {
  id: string;
  organization_id: string;
  kind: ProviderKind;
  provider: string;
  name: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
  secrets_set: string[];
  last_test_at: string | null;
  last_test_ok: boolean | null;
  last_test_message: string | null;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
}

export interface CreateProviderConfigRequest {
  kind: ProviderKind;
  provider: string;
  name: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
}

export interface UpdateProviderConfigRequest {
  name?: string;
  config?: Record<string, unknown>;
  is_enabled?: boolean;
}

export interface ProviderTestResult {
  ok: boolean;
  message: string;
}

/** What this organization's notifications will ACTUALLY use right now, after the
 * organization-config-or-platform-default fallback. Shown so nobody has to infer effective
 * behaviour from a list of rows. */
export interface ResolvedProviders {
  email_provider: string;
  email_scope: "organization" | "platform";
  queue_provider: string;
  queue_scope: "organization" | "platform";
}

export interface EmailLogEntry {
  id: string;
  organization_id: string | null;
  to_email: string;
  template: string;
  status: string;
  provider: string | null;
  provider_scope: string | null;
  error_message: string | null;
  created_at: string;
  sent_at: string | null;
}

export interface EmailLogPage {
  items: EmailLogEntry[];
  total: number;
  limit: number;
  offset: number;
}
