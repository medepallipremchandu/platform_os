import type { BadgeTone } from "../components/ui/Badge";
import type { AgentStatus } from "../types";

/** Central place mapping domain values -> visual tone, so every page renders the same
 * status/revocation badge consistently instead of re-deriving colors ad hoc per page (this
 * used to be a local `statusTone()` helper in AgentListPage and inline ternaries in
 * AgentDetailPage - consolidated here to match the `tone.ts` pattern used across every other
 * console in the platform, e.g. voice-agent-console/iam-console). */

export function toneForAgentStatus(status: AgentStatus): BadgeTone {
  switch (status) {
    case "published":
      return "success";
    case "archived":
      return "neutral";
    case "draft":
    default:
      return "warning";
  }
}

export function toneForRevocation(revokedAt: string | null): BadgeTone {
  return revokedAt ? "neutral" : "success";
}

export function toneForModelActive(isActive: boolean): BadgeTone {
  return isActive ? "success" : "neutral";
}

export function toneForInvocationSuccess(success: boolean): BadgeTone {
  return success ? "success" : "danger";
}
