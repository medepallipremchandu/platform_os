/**
 * Permission codes this console gates its UI on - taken verbatim from agent-builder-service's
 * API contract (every endpoint except `GET /health` requires one of these; see that service's
 * README "API" table for the exact per-route mapping).
 */
export const PERMISSIONS = {
  MODELS_MANAGE: "talentos.agentbuilder.models.manage",
  AGENTS_READ: "talentos.agentbuilder.agents.read",
  AGENTS_WRITE: "talentos.agentbuilder.agents.write",
  AGENTS_PUBLISH: "talentos.agentbuilder.agents.publish",
  AGENTS_MANAGE_KEYS: "talentos.agentbuilder.agents.manage_keys",
} as const;

export { hasAnyPermission, hasPermission } from "./auth";
