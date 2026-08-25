/**
 * Permission codes this app gates its UI on - taken verbatim from talentos-app (backend)'s
 * app/core/permissions.py, the literal source of truth for the string spelling. There is
 * deliberately no delete permission for the interviews group (Question/Evaluation/
 * InterviewSession are append-only audit records) - do not invent one here either.
 */
export const PERMISSIONS = {
  REQUIREMENTS_READ: "talentos.intake.requirements.read",
  REQUIREMENTS_WRITE: "talentos.intake.requirements.write",
  REQUIREMENTS_DELETE: "talentos.intake.requirements.delete",
  APPLICANTS_READ: "talentos.intake.applicants.read",
  APPLICANTS_WRITE: "talentos.intake.applicants.write",
  APPLICANTS_DELETE: "talentos.intake.applicants.delete",
  SUBMISSIONS_READ: "talentos.intake.submissions.read",
  SUBMISSIONS_WRITE: "talentos.intake.submissions.write",
  SUBMISSIONS_DELETE: "talentos.intake.submissions.delete",
  INTERVIEWS_READ: "talentos.intake.interviews.read",
  INTERVIEWS_WRITE: "talentos.intake.interviews.write",
  VOICEAGENT_CALLS_READ: "talentos.voiceagent.calls.read",
  VOICEAGENT_CALLS_WRITE: "talentos.voiceagent.calls.write",
} as const;

export { hasAnyPermission, hasPermission } from "./auth";
