import uuid

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.iam_client import decode_access_token
from app.schemas.invoke import InvokeRequest, InvokeResponse
from app.services.invoke_service import invoke_agent

router = APIRouter(tags=["invoke"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    return token


def _resolve_agent_id_from_token(authorization: str | None) -> uuid.UUID:
    """Validates the caller's token (signature + expiry only - a service-principal token has
    no `permissions` claim to check) and resolves which agent to invoke from its
    `resource_scope` claim - never from a path/body parameter, matching the previous
    X-Agent-Key-identifies-the-agent behavior (design doc §6)."""
    token = _extract_bearer_token(authorization)
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    resource_scope = claims.get("resource_scope")
    if not resource_scope or resource_scope.get("type") != "agent":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token is not scoped to an agent")

    try:
        return uuid.UUID(resource_scope["id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token has an invalid agent resource scope")


@router.post("/invoke", response_model=InvokeResponse)
async def invoke_agent_endpoint(
    payload: InvokeRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Authenticated by a service-principal Bearer token whose `resource_scope` identifies the
    agent to invoke (minted from a client_id/client_secret pair issued at publish time - see
    /agents/{id}/publish) - not the service-wide admin auth used by every other route."""
    agent_id = _resolve_agent_id_from_token(authorization)
    result = await invoke_agent(db, agent_id, payload.variables)
    return InvokeResponse(**result)
