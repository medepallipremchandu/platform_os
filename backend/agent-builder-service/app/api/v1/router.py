from fastapi import APIRouter, Depends

from app.api.v1 import agents, invoke, models
from app.core.iam_client import current_actor

router = APIRouter()

# Every route below requires SOME valid iam-service-issued Bearer token (current_actor);
# each individual route additionally layers a specific require_permission(...) dependency
# (see agents.py/models.py) matching the seeded permission catalog.
_admin_router = APIRouter(dependencies=[Depends(current_actor)])
_admin_router.include_router(models.router)
_admin_router.include_router(agents.router)

router.include_router(_admin_router)
router.include_router(invoke.router)  # its own auth - a resource-bound service-principal token, not an admin permission check
