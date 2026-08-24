from fastapi import Header, HTTPException, status

from app.config import get_settings


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    settings = get_settings()
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def get_actor(x_actor_email: str | None = Header(default=None, alias="X-Actor-Email")) -> str:
    """Identifies who is making the request, for audit stamping (created_by/modified_by/deleted_by).

    There's no login system yet, so callers self-report via this header; defaults to "system".
    """
    return x_actor_email or "system"
