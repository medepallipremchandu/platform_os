import type { BadgeTone } from "../components/ui/Badge";

/** Central place mapping domain values -> visual tone, so every page renders the same
 * verdict/action/score consistently instead of re-deriving colors ad hoc. */

export function toneForVerdict(verdict: string): BadgeTone {
  const v = verdict.toLowerCase();
  if (v.includes("strong")) return "success";
  if (v.includes("gap")) return "danger";
  return "warning";
}

export function toneForAuditAction(action: string): BadgeTone {
  switch (action) {
    case "created":
      return "success";
    case "updated":
    case "skill_updated":
    case "rubric_updated":
      return "warning";
    case "deleted":
      return "danger";
    default:
      return "neutral";
  }
}

export function toneForQuestionType(type: string): BadgeTone {
  switch (type) {
    case "coding":
      return "info";
    case "mcq":
      return "brand";
    default:
      return "neutral";
  }
}

export function toneForDifficulty(difficulty: string | null): BadgeTone {
  switch (difficulty) {
    case "easy":
      return "success";
    case "medium":
      return "warning";
    case "hard":
      return "danger";
    default:
      return "neutral";
  }
}

export function toneForScore(percentage: number): BadgeTone {
  if (percentage >= 75) return "success";
  if (percentage >= 45) return "warning";
  return "danger";
}

// --- Candidate calls (voice-agent-service) ---
// The exact status enum wasn't confirmed until voice-agent-service was reachable mid-build - it
// turned out to be upper-snake-case (e.g. "FAILED", "NO_ANSWER"), not the lowercase this was
// first guessed as. Compared case-insensitively here as extra insurance.

const TERMINAL_CALL_STATUSES = new Set([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "NO_ANSWER",
  "VOICEMAIL",
  "BUSY",
  "ERROR",
]);

/** Mirrors the backend's app.services.voice_call_service.is_terminal - used to decide when to
 * stop polling GET /submissions/{id}/calls. */
export function isTerminalCallStatus(status: string): boolean {
  return TERMINAL_CALL_STATUSES.has(status.toUpperCase());
}

export function toneForCallStatus(status: string): BadgeTone {
  switch (status.toUpperCase()) {
    case "COMPLETED":
      return "success";
    case "FAILED":
    case "ERROR":
    case "NO_ANSWER":
    case "BUSY":
      return "danger";
    case "CANCELLED":
    case "VOICEMAIL":
      return "neutral";
    case "QUEUED":
      return "neutral";
    default:
      // DIALING / RINGING / CONNECTED / IN_PROGRESS / anything unrecognized-but-in-flight
      return "warning";
  }
}
