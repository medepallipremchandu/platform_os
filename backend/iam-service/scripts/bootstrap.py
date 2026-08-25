"""One-time bootstrap (design doc §13, step 1): creates the first Organization and its first
User directly against the database, with the Organization Owner role pre-assigned at
organization scope. There is no authenticated caller yet to do this through the API, so it
can't go through POST /organizations - every organization created afterwards does.

Reads BOOTSTRAP_ORG_NAME / BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD from .env.
Idempotent: if an organization with that name already exists, this is a no-op.

Usage (from iam-service/):
    .venv/Scripts/python.exe scripts/bootstrap.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.password import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.organization_membership import OrganizationMembership  # noqa: E402
from app.models.role_assignment import RoleAssignment  # noqa: E402
from app.models.role_definition import RoleDefinition  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        existing_org = db.execute(
            select(Organization).where(Organization.name == settings.BOOTSTRAP_ORG_NAME)
        ).scalar_one_or_none()
        if existing_org is not None:
            print(f"Organization '{settings.BOOTSTRAP_ORG_NAME}' already exists (id={existing_org.id}) - skipping bootstrap.")
            print(f"Bootstrap admin email: {settings.BOOTSTRAP_ADMIN_EMAIL}")
            return

        owner_role = db.execute(
            select(RoleDefinition).where(
                RoleDefinition.organization_id.is_(None),
                RoleDefinition.name == "Organization Owner",
                RoleDefinition.is_builtin.is_(True),
            )
        ).scalar_one_or_none()
        if owner_role is None:
            raise RuntimeError(
                "Built-in 'Organization Owner' role not found - run scripts/seed_permissions_and_roles.py first."
            )

        org = Organization(name=settings.BOOTSTRAP_ORG_NAME)
        db.add(org)
        db.flush()

        email = settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower()
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                display_name="Bootstrap Admin",
                status="active",
            )
            db.add(user)
            db.flush()

        db.add(OrganizationMembership(user_id=user.id, organization_id=org.id, status="active"))

        db.add(
            RoleAssignment(
                principal_type="user",
                principal_id=user.id,
                role_definition_id=owner_role.id,
                organization_id=org.id,
                scope_type="organization",
                scope_id=str(org.id),
            )
        )
        db.commit()

        print("Bootstrap complete.")
        print(f"  Organization id: {org.id}")
        print(f"  Organization name: {org.name}")
        print(f"  Admin email: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
