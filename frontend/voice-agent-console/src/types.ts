export interface ApiErrorBody {
  detail?: string | { msg: string; loc: (string | number)[] }[];
}

// --- Visibility (shared by providers and call agent configs) ---

export type Visibility = "organization" | "restricted";

// --- Telephony providers ---

/** Only Twilio's field set is wired up today (Account SID / Auth Token / From number) per the
 * contract - the `provider` string and `credentials` bag are intentionally free-form so a new
 * provider type is just a new branch in the create form, not a schema change. */
export type ProviderType = "twilio";

export interface TelephonyProviderConfig {
  id: string;
  name: string;
  provider: string;
  phone_number: string;
  visibility: Visibility;
  created_by: string | null;
  created_at: string;
  revoked_at: string | null;
}

export interface TwilioCredentials {
  accountSid: string;
  authToken: string;
  fromNumber: string;
}

export interface CreateProviderRequest {
  name: string;
  provider: string;
  phone_number: string;
  credentials: Record<string, string>;
  visibility: Visibility;
  grant_user_ids?: string[];
}

/** All fields optional - PATCH /providers/{id} only updates what's supplied. Omitting
 * `credentials` entirely leaves the stored (encrypted) credentials untouched; supplying it
 * replaces them outright (partial credential updates aren't supported - see ProvidersPage). */
export interface UpdateProviderRequest {
  name?: string;
  phone_number?: string;
  credentials?: Record<string, string>;
}

// --- Call agent configs ---

export type CallAgentFieldType = "string" | "number" | "boolean" | "date";

export interface CallAgentField {
  name: string;
  type: CallAgentFieldType;
  description: string;
}

/** The statuses a retry policy can trigger on. Kept as a subset of `CallStatus` (only the
 * terminal-ish "didn't complete" outcomes make sense to retry). */
export const RETRYABLE_CALL_STATUSES = [
  "NO_ANSWER",
  "BUSY",
  "FAILED",
  "TIMEOUT",
  "DISCONNECTED",
  "CALL_BLOCKED",
] as const;
export type RetryableCallStatus = (typeof RETRYABLE_CALL_STATUSES)[number];

export interface CallAgentConfig {
  id: string;
  name: string;
  description: string | null;
  persona: string;
  objective: string;
  consent_line: string;
  closing_line: string;
  fields: CallAgentField[];
  max_conversation_duration_minutes: number;
  retry_max_attempts: number;
  retry_interval_minutes: number;
  retry_on_statuses: string[];
  telephony_provider_config_id: string;
  visibility: Visibility;
  created_by: string | null;
  created_at: string;
  updated_at: string | null;
  deactivated_at: string | null;
}

export interface CallAgentConfigRequest {
  name: string;
  description?: string;
  persona: string;
  objective: string;
  consent_line: string;
  closing_line: string;
  fields: CallAgentField[];
  max_conversation_duration_minutes: number;
  retry_max_attempts: number;
  retry_interval_minutes: number;
  retry_on_statuses: string[];
  telephony_provider_config_id: string;
  visibility: Visibility;
  grant_user_ids?: string[];
}

// --- Calls ---

export type CallStatus =
  | "CREATED"
  | "QUEUED"
  | "DIALING"
  | "RINGING"
  | "CONNECTED"
  | "CONSENT_PENDING"
  | "CONSENT_DENIED"
  | "CONVERSATION"
  | "SUMMARY"
  | "COMPLETED"
  | "FAILED"
  | "BUSY"
  | "NO_ANSWER"
  | "DISCONNECTED"
  | "TIMEOUT"
  | "CANCELLED"
  | "CALL_BLOCKED";

export const CALL_STATUSES: CallStatus[] = [
  "CREATED",
  "QUEUED",
  "DIALING",
  "RINGING",
  "CONNECTED",
  "CONSENT_PENDING",
  "CONSENT_DENIED",
  "CONVERSATION",
  "SUMMARY",
  "COMPLETED",
  "FAILED",
  "BUSY",
  "NO_ANSWER",
  "DISCONNECTED",
  "TIMEOUT",
  "CANCELLED",
  "CALL_BLOCKED",
];

/** A call still in-flight can be cancelled; these are the only statuses that block it. */
const TERMINAL_CALL_STATUSES: CallStatus[] = [
  "COMPLETED",
  "FAILED",
  "BUSY",
  "NO_ANSWER",
  "DISCONNECTED",
  "TIMEOUT",
  "CANCELLED",
  "CALL_BLOCKED",
  "CONSENT_DENIED",
];
export function isCallInFlight(status: CallStatus): boolean {
  return !TERMINAL_CALL_STATUSES.includes(status);
}

export interface CallSummaryRow {
  id: string;
  to_number: string;
  from_number: string | null;
  status: CallStatus;
  attempt_number: number;
  root_call_id: string | null;
  created_at: string;
  connected_at: string | null;
  ended_at: string | null;
  end_reason: string | null;
}

export interface CallScript {
  persona: string;
  objective: string;
  consent_line: string;
  closing_line: string;
  fields: CallAgentField[];
}

export interface CallDetail extends CallSummaryRow {
  call_agent_config_id?: string | null;
  telephony_provider_config_id?: string | null;
  call_script?: CallScript | null;
  max_conversation_duration_minutes?: number | null;
  webhook_url?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface CallEvent {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ConversationTurn {
  id: string;
  turn_index: number;
  speaker: "ai" | "callee";
  text: string;
  created_at: string;
}

export interface CallSummaryDetail {
  summary_text: string;
  extracted_fields: Record<string, unknown>;
  created_at: string;
}

/** GET /calls is paginated; the exact envelope isn't spelled out in the contract, so this follows
 * the same {items,total,limit,offset} convention used elsewhere in this platform (iam-console's
 * audit log) rather than inventing a new one. See README's "assumptions" section. */
export interface CallListResponse {
  items: CallSummaryRow[];
  total: number;
  limit: number;
  offset: number;
}

export type CallSortKey = "created_at" | "status" | "attempt_number";

export interface CallListFilters {
  status?: CallStatus;
  search?: string;
  sortBy?: CallSortKey;
  sortDir?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export interface CreateCallFromAgentRequest {
  call_agent_config_id: string;
  to_number: string;
  webhook_url?: string;
  metadata?: Record<string, unknown>;
}

export interface CreateCallInlineRequest {
  to_number: string;
  telephony_provider_config_id: string;
  call_script: CallScript;
  max_conversation_duration_minutes: number;
  webhook_url?: string;
  metadata?: Record<string, unknown>;
}

export type CreateCallRequest = CreateCallFromAgentRequest | CreateCallInlineRequest;

export interface CancelCallRequest {
  graceful: boolean;
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

/** A row from iam-service's `GET /organizations/{id}/users` - used only to populate the
 * "visible only to specific people" user picker on Providers/Call Agents forms. */
export interface OrgUser {
  id: string;
  user_id: string;
  email: string;
  display_name: string | null;
}
