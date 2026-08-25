"""Talks to iam-service's service-principal-management endpoints on behalf of publish/rotate,
using THIS SERVICE'S OWN machine identity (app.core.iam_client.get_service_token()) - never
the publishing user's token. This is what backs an agent's invoke credential (design doc §6):
a resource-bound ServicePrincipal, one per agent, independently issuable/rotatable/revocable.
"""
import httpx

from app.config import get_settings
from app.core.iam_client import get_service_token


def create_resource_bound_service_principal(*, agent_name: str, organization_id, agent_id) -> dict:
    """Returns the raw iam-service response: {"service_principal": {...}, "client_secret": "..."}."""
    settings = get_settings()
    resp = httpx.post(
        f"{settings.IAM_SERVICE_URL}/service-principals",
        json={
            "name": f"agent-invoke:{agent_name}",
            "organization_id": str(organization_id),
            "resource_type": "agent",
            "resource_id": str(agent_id),
        },
        headers={"Authorization": f"Bearer {get_service_token()}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


def rotate_service_principal_secret(*, service_principal_id: str) -> str:
    """Returns the new plaintext client_secret."""
    settings = get_settings()
    resp = httpx.post(
        f"{settings.IAM_SERVICE_URL}/service-principals/{service_principal_id}/secret/rotate",
        headers={"Authorization": f"Bearer {get_service_token()}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["client_secret"]


def revoke_service_principal(*, service_principal_id: str) -> None:
    """Revokes the ServicePrincipal in iam-service so any future client-credentials grant for
    it is rejected immediately (`sp.is_revoked` is checked at token-issuance time - see
    iam-service's `auth_service.client_credentials_grant`). Used when an agent is archived: its
    invoke credential must stop being able to mint new tokens right away. Does not invalidate
    an access token already issued and still within its short expiry - this is a relying-party
    JWT design (local JWKS verification, no per-request revocation check), not a bug."""
    settings = get_settings()
    resp = httpx.delete(
        f"{settings.IAM_SERVICE_URL}/service-principals/{service_principal_id}",
        headers={"Authorization": f"Bearer {get_service_token()}"},
        timeout=10.0,
    )
    if resp.status_code not in (204, 404):
        resp.raise_for_status()
