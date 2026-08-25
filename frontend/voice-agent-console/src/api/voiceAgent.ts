import { voiceAgentClient } from "./client";
import type {
  CallAgentConfig,
  CallAgentConfigRequest,
  CallDetail,
  CallEvent,
  CallListFilters,
  CallListResponse,
  CallSummaryDetail,
  ConversationTurn,
  CreateCallRequest,
  CreateProviderRequest,
  TelephonyProviderConfig,
  UpdateProviderRequest,
} from "../types";

// --- Telephony providers ---
// Requires talentos.voiceagent.providers.read (list) / .manage (create, edit, revoke).

export async function listProviders(includeRevoked = false): Promise<TelephonyProviderConfig[]> {
  const { data } = await voiceAgentClient.get<{ items: TelephonyProviderConfig[] }>("/providers", {
    params: { include_revoked: includeRevoked },
  });
  return data.items;
}

export async function createProvider(payload: CreateProviderRequest): Promise<TelephonyProviderConfig> {
  const { data } = await voiceAgentClient.post<TelephonyProviderConfig>("/providers", payload);
  return data;
}

/** Renames/re-points a provider, and optionally re-encrypts its credentials (only when
 * `payload.credentials` is supplied - otherwise the stored credentials are left untouched).
 * Credentials are never returned in the response, same as create/list. */
export async function updateProvider(id: string, payload: UpdateProviderRequest): Promise<TelephonyProviderConfig> {
  const { data } = await voiceAgentClient.patch<TelephonyProviderConfig>(`/providers/${id}`, payload);
  return data;
}

export async function revokeProvider(id: string): Promise<void> {
  await voiceAgentClient.delete(`/providers/${id}`);
}

// --- Call agent configs ---
// Requires talentos.voiceagent.callagents.read (list/view) / .write (create, edit, delete).

export async function listCallAgentConfigs(includeInactive = false): Promise<CallAgentConfig[]> {
  const { data } = await voiceAgentClient.get<{ items: CallAgentConfig[] }>("/call-agents", {
    params: { include_inactive: includeInactive },
  });
  return data.items;
}

export async function getCallAgentConfig(id: string): Promise<CallAgentConfig> {
  const { data } = await voiceAgentClient.get<CallAgentConfig>(`/call-agents/${id}`);
  return data;
}

export async function createCallAgentConfig(payload: CallAgentConfigRequest): Promise<CallAgentConfig> {
  const { data } = await voiceAgentClient.post<CallAgentConfig>("/call-agents", payload);
  return data;
}

export async function updateCallAgentConfig(id: string, payload: Partial<CallAgentConfigRequest>): Promise<CallAgentConfig> {
  const { data } = await voiceAgentClient.patch<CallAgentConfig>(`/call-agents/${id}`, payload);
  return data;
}

/** Soft-deactivate, per the contract - the config stays on record, just no longer usable to
 * place new calls. */
export async function deactivateCallAgentConfig(id: string): Promise<void> {
  await voiceAgentClient.delete(`/call-agents/${id}`);
}

// --- Calls ---
// Requires talentos.voiceagent.calls.read (list/view/transcript/summary) / .write (place/cancel).

export async function listCalls(filters: CallListFilters = {}): Promise<CallListResponse> {
  const { data } = await voiceAgentClient.get<CallListResponse>("/calls", {
    params: {
      status: filters.status,
      search: filters.search || undefined,
      sort_by: filters.sortBy,
      sort_dir: filters.sortDir,
      limit: filters.limit ?? 25,
      offset: filters.offset ?? 0,
    },
  });
  return data;
}

export async function getCall(id: string): Promise<CallDetail> {
  const { data } = await voiceAgentClient.get<CallDetail>(`/calls/${id}`);
  return data;
}

export async function createCall(payload: CreateCallRequest): Promise<CallDetail> {
  const { data } = await voiceAgentClient.post<CallDetail>("/calls", payload);
  return data;
}

export async function getCallEvents(id: string): Promise<CallEvent[]> {
  const { data } = await voiceAgentClient.get<CallEvent[]>(`/calls/${id}/events`);
  return data;
}

export async function getCallConversation(id: string): Promise<ConversationTurn[]> {
  const { data } = await voiceAgentClient.get<ConversationTurn[]>(`/calls/${id}/conversation`);
  return data;
}

export async function getCallSummary(id: string): Promise<CallSummaryDetail | null> {
  const { data } = await voiceAgentClient.get<CallSummaryDetail | null>(`/calls/${id}/summary`);
  return data;
}

export async function cancelCall(id: string, graceful: boolean): Promise<CallDetail> {
  const { data } = await voiceAgentClient.post<CallDetail>(`/calls/${id}/cancel`, { graceful });
  return data;
}
