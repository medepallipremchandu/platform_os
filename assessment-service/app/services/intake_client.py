"""Thin HTTP client for calling intake-matching-service. This is the only way
assessment-service ever touches that service's data - never a direct DB query."""
import logging

import httpx

from app.config import get_settings
from app.core.exceptions import LLMProviderError, NotFoundError

logger = logging.getLogger("app.services.intake_client")


async def fetch_submission_for_assessment(submission_id: str) -> dict:
    settings = get_settings()
    url = f"{settings.INTAKE_MATCHING_SERVICE_URL}/submissions/{submission_id}/for-assessment"

    try:
        async with httpx.AsyncClient(timeout=settings.INTAKE_MATCHING_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers={"X-API-Key": settings.INTAKE_MATCHING_API_KEY})
    except httpx.RequestError as exc:
        logger.error("Failed to reach intake-matching-service at %s: %s", url, exc)
        raise LLMProviderError(f"Could not reach intake-matching-service: {exc}") from exc

    if response.status_code == 404:
        raise NotFoundError(f"Submission {submission_id} not found in intake-matching-service")
    if response.status_code != 200:
        logger.error("intake-matching-service returned %s for %s: %s", response.status_code, url, response.text)
        raise LLMProviderError(f"intake-matching-service returned {response.status_code}")

    return response.json()
