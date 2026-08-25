from fastapi import APIRouter

from app.api import call_agents, calls, health, providers, webhooks

router = APIRouter()
router.include_router(health.router)
router.include_router(providers.router)
router.include_router(call_agents.router)
router.include_router(calls.router)
router.include_router(webhooks.router)
