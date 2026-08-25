import type { BadgeTone } from "../components/ui/Badge";
import type { AuditResult, ScopeType, UserStatus } from "../types";

/** Central place mapping domain values -> visual tone, so every page renders the same
 * status/result badge consistently instead of re-deriving colors ad hoc. */

export function toneForAuditResult(result: AuditResult): BadgeTone {
  switch (result) {
    case "success":
      return "success";
    case "denied":
      return "warning";
    case "error":
      return "danger";
    default:
      return "neutral";
  }
}

export function toneForUserStatus(status: UserStatus): BadgeTone {
  switch (status) {
    case "active":
      return "success";
    case "invited":
      return "info";
    case "disabled":
      return "neutral";
    default:
      return "neutral";
  }
}

export function toneForScopeType(scope: ScopeType): BadgeTone {
  return scope === "organization" ? "brand" : "info";
}

export function toneForRoleKind(isBuiltin: boolean): BadgeTone {
  return isBuiltin ? "neutral" : "brand";
}

export function toneForRevocation(revokedAt: string | null): BadgeTone {
  return revokedAt ? "neutral" : "success";
}
