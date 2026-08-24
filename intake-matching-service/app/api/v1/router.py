from fastapi import APIRouter, Depends

from app.api.v1 import jd_analysis, resume_analysis, submissions
from app.core.security import verify_api_key

router = APIRouter(dependencies=[Depends(verify_api_key)])
router.include_router(jd_analysis.router)
router.include_router(resume_analysis.router)
router.include_router(submissions.router)
