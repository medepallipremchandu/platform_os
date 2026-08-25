// Types mirror iam-service's documented API contract (see
// docs/superpowers/specs/2026-08-24-iam-service-design.md). `portal` only ever calls the
// auth endpoints (login/logout) - it has no business-domain API surface of its own, so this
// is a trimmed-down copy of iam-console's `types.ts` with everything else removed.

export interface ApiErrorBody {
  detail?: string | { msg: string; loc: (string | number)[] }[];
}

export interface OrgMembershipOption {
  id: string;
  name: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  /** Null for a platform superadmin, who belongs to no organization. */
  organization_id: string | null;
}

/** Shape of the decoded access-token JWT payload (RS256, unencrypted - safe to read client-side). */
export interface AccessTokenClaims {
  sub: string;
  principal_type: "user" | "service_principal";
  /** Null for a platform superadmin, who belongs to no organization. */
  org_id: string | null;
  permissions: string[];
  resource_scope?: { type: string; id: string };
  iat: number;
  exp: number;
  jti: string;
  email?: string;
  name?: string;
  /** The platform tier above organizations - a separate axis from `permissions`, which is
   * empty for a superadmin precisely because they hold no org-scoped roles. */
  is_superadmin?: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
  organization_id?: string;
}

/** Returned as the body of a 409 when the account has multiple org memberships and none was
 * specified - the login page then re-prompts for an org and re-submits. Wire shape is
 * `{detail: {message, memberships: [{organization_id, organization_name}]}}`; api/iam.ts maps
 * that into `OrgMembershipOption[]`. */
export interface LoginMultiOrgResponse {
  memberships: OrgMembershipOption[];
}
