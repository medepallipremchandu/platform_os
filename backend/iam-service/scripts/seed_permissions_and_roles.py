"""Seeds the platform-wide permission catalog and the built-in (global, organization_id=NULL)
RoleDefinitions every organization can assign roles from. Safe to re-run: permissions are
looked up by their unique `code`, role definitions by (organization_id IS NULL, name), so
already-seeded rows are left untouched and only missing ones are inserted.

Usage (from iam-service/):
    .venv/Scripts/python.exe scripts/seed_permissions_and_roles.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.permission import Permission  # noqa: E402
from app.models.role_definition import RoleDefinition  # noqa: E402
from app.models.role_definition_permission import RoleDefinitionPermission  # noqa: E402

# --- Exact permission catalog - other services check for these exact strings. ---
PERMISSIONS: list[tuple[str, str]] = [
    ("talentos.iam.organizations.manage", "Create and manage organizations"),
    ("talentos.iam.users.invite", "Invite users into an organization"),
    ("talentos.iam.users.manage", "Manage (list/disable/enable) users within an organization"),
    ("talentos.iam.roles.manage", "Author, edit and delete custom role definitions"),
    ("talentos.iam.role_assignments.manage", "Assign and revoke roles at a scope"),
    ("talentos.iam.service_principals.manage", "Create, rotate and revoke service principals"),
    ("talentos.iam.audit.read", "Read the platform-wide audit log"),
    ("talentos.intake.requirements.read", "Read job requirements"),
    ("talentos.intake.requirements.write", "Create/edit job requirements"),
    ("talentos.intake.requirements.delete", "Delete job requirements"),
    ("talentos.intake.applicants.read", "Read applicants"),
    ("talentos.intake.applicants.write", "Create/edit applicants"),
    ("talentos.intake.applicants.delete", "Delete applicants"),
    ("talentos.intake.submissions.read", "Read submissions"),
    ("talentos.intake.submissions.write", "Create/edit submissions"),
    ("talentos.intake.submissions.delete", "Delete submissions"),
    ("talentos.intake.interviews.read", "Read interview sessions"),
    ("talentos.intake.interviews.write", "Create/edit interview sessions"),
    ("talentos.agentbuilder.models.manage", "Register/manage model deployments"),
    ("talentos.agentbuilder.agents.read", "Read agents"),
    ("talentos.agentbuilder.agents.write", "Create/edit agents"),
    ("talentos.agentbuilder.agents.publish", "Publish agents"),
    ("talentos.agentbuilder.agents.manage_keys", "Rotate/revoke agent invoke credentials"),
]

ALL_CODES = [code for code, _ in PERMISSIONS]
ALL_EXCEPT_ORG_MANAGE = [c for c in ALL_CODES if c != "talentos.iam.organizations.manage"]
INTAKE_ALL = [c for c in ALL_CODES if c.startswith("talentos.intake.")]
INTAKE_READ_WRITE = [c for c in INTAKE_ALL if not c.endswith(".delete")]
AGENTBUILDER_ALL = [c for c in ALL_CODES if c.startswith("talentos.agentbuilder.")]

# --- Exact built-in roles to seed. ---
BUILTIN_ROLES: list[dict] = [
    {
        "name": "Organization Owner",
        "description": "Full control, including managing all role assignments and the organization itself.",
        "permission_codes": ALL_CODES,
    },
    {
        "name": "Organization Admin",
        "description": "Manage users and role assignments; cannot manage the organization itself.",
        "permission_codes": ALL_EXCEPT_ORG_MANAGE,
    },
    {
        "name": "Requirements Manager",
        "description": "Full CRUD on requirements/applicant/submission/interview data.",
        "permission_codes": INTAKE_ALL,
    },
    {
        "name": "Recruiter",
        "description": "Read/write on requirements/applicants/submissions/interviews; no delete.",
        "permission_codes": INTAKE_READ_WRITE,
    },
    {
        "name": "Agent Builder Admin",
        "description": "Manage models and agents, publish agents, rotate keys.",
        "permission_codes": AGENTBUILDER_ALL,
    },
    {
        "name": "Agent Builder Contributor",
        "description": "Create/edit agents; cannot manage models or rotate keys.",
        "permission_codes": ["talentos.agentbuilder.agents.read", "talentos.agentbuilder.agents.write"],
    },
    {
        "name": "Viewer",
        "description": "Read-only, org-wide.",
        "permission_codes": [
            "talentos.intake.requirements.read",
            "talentos.intake.applicants.read",
            "talentos.intake.submissions.read",
            "talentos.intake.interviews.read",
            "talentos.agentbuilder.agents.read",
        ],
    },
]


def seed_permissions(db) -> dict[str, Permission]:
    existing = {p.code: p for p in db.execute(select(Permission)).scalars().all()}
    created = 0
    for code, description in PERMISSIONS:
        if code in existing:
            continue
        perm = Permission(code=code, description=description)
        db.add(perm)
        db.flush()
        existing[code] = perm
        created += 1
    db.commit()
    print(f"Permissions: {created} created, {len(PERMISSIONS) - created} already present ({len(PERMISSIONS)} total).")
    return existing


def seed_builtin_roles(db, permissions_by_code: dict[str, Permission]) -> None:
    existing_roles = {
        r.name: r
        for r in db.execute(select(RoleDefinition).where(RoleDefinition.organization_id.is_(None))).scalars().all()
    }
    created = 0
    for spec in BUILTIN_ROLES:
        role = existing_roles.get(spec["name"])
        if role is None:
            role = RoleDefinition(
                organization_id=None,
                name=spec["name"],
                description=spec["description"],
                is_builtin=True,
            )
            db.add(role)
            db.flush()
            created += 1
            print(f"  created role '{spec['name']}'")
        else:
            print(f"  role '{spec['name']}' already exists - checking permission mappings")

        existing_perm_ids = {
            rdp.permission_id
            for rdp in db.execute(
                select(RoleDefinitionPermission).where(RoleDefinitionPermission.role_definition_id == role.id)
            ).scalars()
        }
        added = 0
        for code in spec["permission_codes"]:
            perm = permissions_by_code[code]
            if perm.id in existing_perm_ids:
                continue
            db.add(RoleDefinitionPermission(role_definition_id=role.id, permission_id=perm.id))
            added += 1
        if added:
            print(f"    +{added} permission mapping(s)")
    db.commit()
    print(f"Built-in roles: {created} created, {len(BUILTIN_ROLES) - created} already present.")


def main() -> None:
    db = SessionLocal()
    try:
        permissions_by_code = seed_permissions(db)
        seed_builtin_roles(db, permissions_by_code)
    finally:
        db.close()


if __name__ == "__main__":
    main()
