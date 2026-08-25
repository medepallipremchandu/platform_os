from fastapi import APIRouter, Depends

from app.api.v1 import evaluations, interview_sessions, jd_analysis, questions, resume_analysis, submissions
from app.core.iam_client import current_actor

# Every route under /api/v1 requires *some* valid IAM-issued Bearer token (401 if
# missing/invalid); each individual route additionally depends on require_permission(...) for
# the specific action it performs (403 if the token's permissions claim doesn't include it) -
# see each router module and app/core/permissions.py for the mapping.
router = APIRouter(dependencies=[Depends(current_actor)])
router.include_router(jd_analysis.router)
router.include_router(resume_analysis.router)
router.include_router(submissions.router)
router.include_router(interview_sessions.router)
router.include_router(questions.router)
router.include_router(evaluations.router)
