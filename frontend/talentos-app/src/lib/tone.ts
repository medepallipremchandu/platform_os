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
