export interface ApiErrorBody {
  detail?: string | { msg: string; loc: (string | number)[] }[];
}

// --- Models ---

export type ModelProvider = "claude" | "azure_openai";

export interface Model {
  id: string;
  organization_id: string;
  model_code: string;
  name: string;
  provider: ModelProvider;
  model_id: string;
  endpoint: string | null;
  api_version: string | null;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
}

export interface ModelCreateRequest {
  name: string;
  provider: ModelProvider;
  model_id: string;
  api_key: string;
  endpoint?: string;
  api_version?: string;
}

/** `provider`/`model_id` are intentionally not part of this type - the backend rejects changing
 * either via PATCH (that's a different model deployment; create a new one instead). */
export interface ModelUpdateRequest {
  name?: string;
  api_key?: string;
  endpoint?: string;
  api_version?: string;
}

// --- Agents ---

export type AgentStatus = "draft" | "published" | "archived";

export interface Agent {
  id: string;
  organization_id: string;
  agent_code: string;
  name: string;
  description: string | null;
  system_prompt: string;
  user_prompt_template: string;
  input_variables: string[];
  primary_model: Model;
  fallback_model: Model | null;
  max_output_tokens: number;
  timeout_seconds: number;
  rate_limit_per_minute: number;
  status: AgentStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string | null;
  published_at: string | null;
  archived_at: string | null;
}

export interface AgentSummary {
  id: string;
  agent_code: string;
  name: string;
  status: AgentStatus;
  primary_model: Model;
  created_by: string | null;
  created_at: string;
  archived_at: string | null;
}

export interface AgentCreateRequest {
  name: string;
  description?: string;
  system_prompt: string;
  user_prompt_template: string;
  primary_model_id: string;
  fallback_model_id?: string;
  max_output_tokens?: number;
  timeout_seconds?: number;
  rate_limit_per_minute?: number;
}

/**
 * An agent's invoke credential, minted from iam-service as a resource-bound `ServicePrincipal`
 * (`resource_type=agent`) the first time the agent is published. This service never stores or
 * returns the `client_secret` after the moment it's minted/rotated (see `PublishResult` /
 * `regenerateAgentCredential` below) - only the (safe-to-display) `client_id` persists, which is
 * what this type represents. Pair a `client_id` with a freshly-issued `client_secret` and
 * exchange them for a Bearer token via iam-service's `POST /auth/token` to call `/invoke`.
 */
export interface AgentCredential {
  id: string;
  client_id: string;
  created_at: string;
  revoked_at: string | null;
}

export interface AgentUsageEntry {
  id: string;
  success: boolean;
  provider_used: string | null;
  latency_ms: number;
  error_message: string | null;
  created_at: string;
}

// --- IAM session (this app is a relying party of iam-service via the portal app's login) ---

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
  iat: number;
  exp: number;
  jti: string;
  email?: string;
  name?: string;
}
