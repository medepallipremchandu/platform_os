"""Named permission-code constants for this service's endpoints.

These strings must match the fixed catalog seeded once in iam-service
(iam-service/scripts/seed_permissions_and_roles.py - see its README "Permission catalog"
section). They are never created or edited here; this module exists purely so the literal
strings live in one place instead of being scattered across router files.
"""

# talentos.intake.requirements.* - JD analysis
REQUIREMENTS_READ = "talentos.intake.requirements.read"
REQUIREMENTS_WRITE = "talentos.intake.requirements.write"
REQUIREMENTS_DELETE = "talentos.intake.requirements.delete"

# talentos.intake.applicants.* - resume analysis
APPLICANTS_READ = "talentos.intake.applicants.read"
APPLICANTS_WRITE = "talentos.intake.applicants.write"
APPLICANTS_DELETE = "talentos.intake.applicants.delete"

# talentos.intake.submissions.* - JD/resume pairing + match analysis
SUBMISSIONS_READ = "talentos.intake.submissions.read"
SUBMISSIONS_WRITE = "talentos.intake.submissions.write"
SUBMISSIONS_DELETE = "talentos.intake.submissions.delete"

# talentos.intake.interviews.* - interview sessions, questions, evaluations (no delete
# permission exists in the catalog for this group - there is no DELETE endpoint for any of
# these resources today)
INTERVIEWS_READ = "talentos.intake.interviews.read"
INTERVIEWS_WRITE = "talentos.intake.interviews.write"
