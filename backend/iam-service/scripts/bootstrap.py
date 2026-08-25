"""Seeds the ONE account the platform starts with: the platform administrator.

`is_superadmin = True` and **no organization membership**. That absence is the tier, not an
oversight - a superadmin sits above organizations, so there is no org scope for a RoleAssignment
to hang off, and login has an explicit branch for it (`org_id: null`, `permissions: []`,
`is_superadmin: true`). The bypass in `app/api/deps.py::require_permission` is what gives this
account unrestricted reach: it satisfies every permission check, while no set of permissions
ever satisfies `require_superadmin`.

Nothing else is seeded - no starter organization, no demo users. Creating organizations and
appointing their admins is precisely what this account exists to do, and it does it from
iam-console. (Earlier versions of this script also created a first organization with an
Organization Owner; that predates the superadmin tier and is exactly what it replaced.)

Run `scripts/seed_permissions_and_roles.py` first - the permission catalog and built-in roles
have to exist before an organization can be given an entitlement ceiling.

Reads BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD from .env. Idempotent: an existing user
with that email is promoted rather than duplicated, and re-running is a no-op.

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
from app.models.user import User  # noqa: E402


def bootstrap_platform_admin(db, settings) -> None:
    email = settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is not None:
        changed = False
        if not user.is_superadmin:
            # The account predates the superadmin tier, or was created as an ordinary user.
            user.is_superadmin = True
            changed = True
        if user.status != "active":
            user.status = "active"
            changed = True
        if changed:
            db.commit()
            print(f"Promoted existing user {email} to platform administrator.")
        else:
            print(f"Platform administrator {email} already exists - nothing to do.")
        return

    db.add(
        User(
            email=email,
            password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            display_name="Platform Administrator",
            status="active",
            is_superadmin=True,
        )
    )
    db.commit()
    print("Platform administrator created.")
    print(f"  Email:        {email}")
    print("  Organization: none - by design; this account creates them.")


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        bootstrap_platform_admin(db, settings)
    finally:
        db.close()


if __name__ == "__main__":
    main()
