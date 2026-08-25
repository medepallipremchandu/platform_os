/**
 * Permission codes this console gates its UI on - taken verbatim from the voice-agent-service
 * API contract (every endpoint except `GET /health` requires one of these).
 */
export const PERMISSIONS = {
  PROVIDERS_MANAGE: "talentos.voiceagent.providers.manage",
  PROVIDERS_READ: "talentos.voiceagent.providers.read",
  CALLAGENTS_WRITE: "talentos.voiceagent.callagents.write",
  CALLAGENTS_READ: "talentos.voiceagent.callagents.read",
  CALLS_WRITE: "talentos.voiceagent.calls.write",
  CALLS_READ: "talentos.voiceagent.calls.read",
} as const;

export { hasAnyPermission, hasPermission } from "./auth";
