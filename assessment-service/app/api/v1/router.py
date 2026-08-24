from fastapi import APIRouter, Depends

from app.api.v1 import evaluations, interview_sessions, questions
from app.core.security import verify_api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])
router.include_router(interview_sessions.router)
router.include_router(questions.router)
router.include_router(evaluations.router)
