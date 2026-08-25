import type { BadgeTone } from "../components/ui/Badge";
import type { CallStatus, Visibility } from "../types";

/** Central place mapping domain values -> visual tone, so every page renders the same
 * status/visibility badge consistently instead of re-deriving colors ad hoc, matching the
 * `tone.ts` centralization pattern from iam-console/agent-builder-console. */

export function toneForCallStatus(status: CallStatus): BadgeTone {
  switch (status) {
    case "COMPLETED":
      return "success";
    case "FAILED":
    case "CALL_BLOCKED":
    case "CONSENT_DENIED":
      return "danger";
    case "BUSY":
    case "NO_ANSWER":
    case "TIMEOUT":
    case "DISCONNECTED":
      return "warning";
    case "CANCELLED":
      return "neutral";
    case "CREATED":
    case "QUEUED":
    case "DIALING":
    case "RINGING":
    case "CONNECTED":
    case "CONSENT_PENDING":
    case "CONVERSATION":
    case "SUMMARY":
      return "info";
    default:
      return "neutral";
  }
}

export function toneForVisibility(visibility: Visibility): BadgeTone {
  return visibility === "organization" ? "brand" : "info";
}

export function toneForRevocation(revokedAt: string | null): BadgeTone {
  return revokedAt ? "neutral" : "success";
}

export function toneForActiveState(deactivatedAt: string | null): BadgeTone {
  return deactivatedAt ? "neutral" : "success";
}
