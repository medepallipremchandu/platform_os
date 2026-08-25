import axios from "axios";
import { attachAuth } from "./client";
import type { CallAgentConfig } from "../types";

const VOICE_AGENT_SERVICE_URL = import.meta.env.VITE_VOICE_AGENT_SERVICE_URL || "http://localhost:8004";

/** The ONE place this app talks to voice-agent-service directly from the browser, using the
 * recruiter's own IAM bearer token (same attachAuth interceptor as intakeClient) - purely to
 * populate a "pick a call agent config" dropdown on the JD detail page. Every other
 * voice-calling operation goes through this app's own backend instead (see src/api/voiceAgent.ts)
 * so it can mediate the actual call placement with its own machine credential. This app never
 * rebuilds voice-agent-console's management UI (creating/editing call agents, providers, etc). */
export const voiceAgentDirectClient = axios.create({
  baseURL: VOICE_AGENT_SERVICE_URL,
  headers: { "Content-Type": "application/json" },
});
attachAuth(voiceAgentDirectClient);

/** voice-agent-service wraps list responses as `{ items: [...] }`. */
interface CallAgentConfigListResponse {
  items: CallAgentConfig[];
}

export async function listCallAgentConfigs(): Promise<CallAgentConfig[]> {
  const { data } = await voiceAgentDirectClient.get<CallAgentConfigListResponse>("/call-agents");
  return data.items;
}
