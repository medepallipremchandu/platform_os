import { agentBuilderClient } from "./client";
import type {
  Agent,
  AgentCreateRequest,
  AgentCredential,
  AgentSummary,
  AgentUsageEntry,
  Model,
  ModelCreateRequest,
  ModelUpdateRequest,
} from "../types";

// --- Models ---

export async function listModels(): Promise<Model[]> {
  const { data } = await agentBuilderClient.get<Model[]>("/models");
  return data;
}

export async function createModel(payload: ModelCreateRequest): Promise<Model> {
  const { data } = await agentBuilderClient.post<Model>("/models", payload);
  return data;
}

/** Renames the model and/or re-encrypts a freshly re-entered credential in place - `provider`
 * and `model_id` can't be changed this way (see `ModelUpdateRequest`). */
export async function updateModel(id: string, payload: ModelUpdateRequest): Promise<Model> {
  const { data } = await agentBuilderClient.patch<Model>(`/models/${id}`, payload);
  return data;
}

/** Deactivates the model (soft-delete): it stops being offered when creating/editing agents,
 * but agents already pointing at it keep working. */
export async function deactivateModel(id: string): Promise<Model> {
  const { data } = await agentBuilderClient.delete<Model>(`/models/${id}`);
  return data;
}

// --- Agents ---

export async function listAgents(options?: { includeArchived?: boolean }): Promise<AgentSummary[]> {
  const { data } = await agentBuilderClient.get<AgentSummary[]>("/agents", {
    params: options?.includeArchived ? { include_archived: true } : undefined,
  });
  return data;
}

export async function getAgent(id: string): Promise<Agent> {
  const { data } = await agentBuilderClient.get<Agent>(`/agents/${id}`);
  return data;
}

export async function createAgent(payload: AgentCreateRequest): Promise<Agent> {
  const { data } = await agentBuilderClient.post<Agent>("/agents", payload);
  return data;
}

export async function updateAgent(id: string, payload: Partial<AgentCreateRequest>): Promise<Agent> {
  const { data } = await agentBuilderClient.patch<Agent>(`/agents/${id}`, payload);
  return data;
}

/**
 * Publishing mints an invoke credential (an iam-service `ServicePrincipal`) the first time an
 * agent is published. `client_secret` is only present on that first call - shown exactly once,
 * never recoverable after this response. Republishing an already-published agent returns
 * `client_secret: null`; use `regenerateAgentCredential` to mint a fresh secret for the existing
 * credential.
 */
export async function publishAgent(id: string): Promise<{ agent: Agent; client_secret: string | null }> {
  const { data } = await agentBuilderClient.post<{ agent: Agent; client_secret: string | null }>(
    `/agents/${id}/publish`,
  );
  return data;
}

/** Rotates the agent's invoke credential via iam-service - the old client_secret stops working
 * immediately. Returns the new client_secret, shown exactly once. */
export async function regenerateAgentCredential(id: string): Promise<string> {
  const { data } = await agentBuilderClient.post<{ client_secret: string }>(`/agents/${id}/keys/regenerate`);
  return data.client_secret;
}

/** Lists this agent's credential(s) - safe-to-display `client_id` only, never the secret. */
export async function listAgentCredentials(id: string): Promise<AgentCredential[]> {
  const { data } = await agentBuilderClient.get<AgentCredential[]>(`/agents/${id}/keys`);
  return data;
}

export async function getAgentUsage(id: string): Promise<AgentUsageEntry[]> {
  const { data } = await agentBuilderClient.get<AgentUsageEntry[]>(`/agents/${id}/usage`);
  return data;
}

/** Archives the agent (soft-delete: the row is never removed, only `status` flips to
 * "archived"). Revokes its active invoke credential in iam-service immediately, and it can
 * never be republished or edited again - create a new agent instead. */
export async function archiveAgent(id: string): Promise<Agent> {
  const { data } = await agentBuilderClient.delete<Agent>(`/agents/${id}`);
  return data;
}
