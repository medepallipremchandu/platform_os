"""One-time bootstrap: creates voice-agent-service's own machine identity in iam-service.

This service needs its own machine identity to post system-attributed audit events for the two
Twilio webhook routes (voice/status), which have no end-user bearer token of their own - Twilio
itself calls them, not IAM. That's a different, more privileged kind of caller than any of the
`talentos.voiceagent.*` permissions an end user needs, so it gets its own service principal here,
kept separate from ordinary per-user permission checks - same pattern as
agent-builder-service/scripts/bootstrap_iam_identity.py.

  1. Logs into iam-service as the bootstrap admin (IAM_BOOTSTRAP_ADMIN_EMAIL/PASSWORD in .env).
  2. Creates a generic (non-resource-bound) ServicePrincipal named "voice-agent-service".
  3. Grants it the built-in "Organization Admin" role at organization scope (POST /audit/events
     itself needs no specific permission - any valid token works - but a real role keeps this
     identity's headroom consistent with the platform's other bootstrapped service identities).
  4. Prints the resulting client_id/client_secret - put them in .env as
     IAM_CLIENT_ID / IAM_CLIENT_SECRET.

Idempotent: if .env already has non-placeholder values for IAM_CLIENT_ID/IAM_CLIENT_SECRET, this
is a no-op.

Usage (from voice-agent-service/):
    .venv/Scripts/python.exe scripts/bootstrap_iam_identity.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.config import get_settings  # noqa: E402

SERVICE_PRINCIPAL_NAME = "voice-agent-service"
REQUIRED_ROLE_NAME = "Organization Admin"


def _already_configured(settings) -> bool:
    placeholder_values = {"", None}
    return settings.IAM_CLIENT_ID not in placeholder_values and settings.IAM_CLIENT_SECRET not in placeholder_values


def main() -> None:
    settings = get_settings()

    if _already_configured(settings):
        print(
            "IAM_CLIENT_ID/IAM_CLIENT_SECRET are already set in .env with non-placeholder "
            "values - skipping bootstrap (idempotent)."
        )
        return

    if not settings.IAM_BOOTSTRAP_ADMIN_EMAIL or not settings.IAM_BOOTSTRAP_ADMIN_PASSWORD:
        raise SystemExit("IAM_BOOTSTRAP_ADMIN_EMAIL / IAM_BOOTSTRAP_ADMIN_PASSWORD must be set in .env")
    if not settings.BOOTSTRAP_ORGANIZATION_ID:
        raise SystemExit("BOOTSTRAP_ORGANIZATION_ID must be set in .env")

    organization_id = settings.BOOTSTRAP_ORGANIZATION_ID
    base_url = settings.IAM_SERVICE_URL

    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        # 1. Log in as the bootstrap admin.
        login_resp = client.post(
            "/auth/login",
            json={
                "email": settings.IAM_BOOTSTRAP_ADMIN_EMAIL,
                "password": settings.IAM_BOOTSTRAP_ADMIN_PASSWORD,
                "organization_id": organization_id,
            },
        )
        login_resp.raise_for_status()
        admin_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Create the generic (non-resource-bound) service principal.
        create_resp = client.post(
            "/service-principals",
            json={"name": SERVICE_PRINCIPAL_NAME, "organization_id": organization_id},
            headers=headers,
        )
        create_resp.raise_for_status()
        created = create_resp.json()
        sp = created["service_principal"]
        client_secret = created["client_secret"]
        client_id = sp["client_id"]

        # 3. Find the built-in "Organization Admin" role.
        roles_resp = client.get("/role-definitions", params={"organization_id": organization_id}, headers=headers)
        roles_resp.raise_for_status()
        roles = roles_resp.json()
        org_admin_role = next((r for r in roles if r["name"] == REQUIRED_ROLE_NAME), None)
        if org_admin_role is None:
            raise SystemExit(
                f"Built-in role '{REQUIRED_ROLE_NAME}' not found via GET /role-definitions - "
                "has iam-service's scripts/seed_permissions_and_roles.py been run?"
            )

        # 4. Grant that role to the service principal, at organization scope.
        assign_resp = client.post(
            "/role-assignments",
            json={
                "principal_type": "service_principal",
                "principal_id": sp["id"],
                "role_definition_id": org_admin_role["id"],
                "organization_id": organization_id,
                "scope_type": "organization",
            },
            headers=headers,
        )
        assign_resp.raise_for_status()

    print("Bootstrap complete.")
    print(f"  Service principal: {SERVICE_PRINCIPAL_NAME} (id={sp['id']})")
    print(f"  Role granted: {REQUIRED_ROLE_NAME} (organization scope)")
    print()
    print("Put these into voice-agent-service/.env:")
    print(f"  IAM_CLIENT_ID={client_id}")
    print(f"  IAM_CLIENT_SECRET={client_secret}")
    print()
    print("(client_secret is shown exactly once - it is not recoverable after this.)")


if __name__ == "__main__":
    main()
