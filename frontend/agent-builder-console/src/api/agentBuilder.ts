import { agentBuilderClient } from "./client";
import type {
  Agent,
  AgentCreateRequest,
  AgentCredential,
  AgentSummary,
  AgentUsageEntry,
  Model,
  ModelCreateRequest,
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

// --- Agents ---

export async function listAgents(): Promise<AgentSummary[]> {
  const { data } = await agentBuilderClient.get<AgentSummary[]>("/agents");
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
