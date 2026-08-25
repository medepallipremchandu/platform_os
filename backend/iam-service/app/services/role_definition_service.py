import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.permission import Permission
from app.models.role_definition import RoleDefinition
from app.models.role_definition_permission import RoleDefinitionPermission


def list_role_definitions(db: Session, organization_id: uuid.UUID) -> list[RoleDefinition]:
    stmt = (
        select(RoleDefinition)
        .options(selectinload(RoleDefinition.permissions))
        .where(or_(RoleDefinition.organization_id.is_(None), RoleDefinition.organization_id == organization_id))
        .order_by(RoleDefinition.is_builtin.desc(), RoleDefinition.name)
    )
    return list(db.execute(stmt).scalars().all())


def _get_or_404(db: Session, role_definition_id: uuid.UUID) -> RoleDefinition:
    role = db.get(RoleDefinition, role_definition_id)
    if role is None:
        raise NotFoundError("Role definition not found")
    return role


def _set_permissions(db: Session, role: RoleDefinition, permission_codes: list[str]) -> None:
    db.query(RoleDefinitionPermission).filter(RoleDefinitionPermission.role_definition_id == role.id).delete()
    if permission_codes:
        perms = db.execute(select(Permission).where(Permission.code.in_(permission_codes))).scalars().all()
        found_codes = {p.code for p in perms}
        missing = set(permission_codes) - found_codes
        if missing:
            from app.core.exceptions import InvalidStateError

            raise InvalidStateError(f"Unknown permission code(s): {', '.join(sorted(missing))}")
        for perm in perms:
            db.add(RoleDefinitionPermission(role_definition_id=role.id, permission_id=perm.id))


def create_role_definition(
    db: Session, *, organization_id: uuid.UUID, name: str, description: str | None, permission_codes: list[str]
) -> RoleDefinition:
    role = RoleDefinition(organization_id=organization_id, name=name, description=description, is_builtin=False)
    db.add(role)
    db.flush()
    _set_permissions(db, role, permission_codes)
    db.commit()
    db.refresh(role)
    return role


def update_role_definition(
    db: Session,
    role_definition_id: uuid.UUID,
    *,
    name: str | None,
    description: str | None,
    permission_codes: list[str] | None,
) -> RoleDefinition:
    role = _get_or_404(db, role_definition_id)
    if role.is_builtin:
        raise ForbiddenError("Built-in role definitions cannot be edited")
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    if permission_codes is not None:
        _set_permissions(db, role, permission_codes)
    db.commit()
    db.refresh(role)
    return role


def delete_role_definition(db: Session, role_definition_id: uuid.UUID) -> None:
    role = _get_or_404(db, role_definition_id)
    if role.is_builtin:
        raise ForbiddenError("Built-in role definitions cannot be deleted")
    db.delete(role)
    db.commit()
