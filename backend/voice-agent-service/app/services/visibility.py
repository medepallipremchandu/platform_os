"""Shared visibility/exposure semantics for TelephonyProviderConfig and CallAgentConfig.

A resource with visibility="organization" is listable/usable by anyone in the org holding the
right permission. One with visibility="restricted" is listable/usable only by its creator plus
whoever holds a row in its Grant table - EXCEPT for a caller whose token has
principal_type == "service_principal" (a machine caller acting on the org's behalf, not a
specific human), which always sees every org-scoped resource regardless of visibility, since
per-user restriction is a human-permission concept that doesn't apply to a machine credential.

Both the creator check and the grant table use the same "who" identity string
(CurrentActor.email_or_name) as created_by, matching the platform-wide convention for actor
identity - there is no separate user-id column to key grants off of.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.iam_client import CurrentActor


def visible_query(session: Session, model, grant_model, grant_fk_column, actor: CurrentActor):
    """Returns a SQLAlchemy Select for `model`, scoped to the caller's organization and filtered
    by visibility rules. Callers add any further filters (e.g. `.where(model.id == id)`) on top.
    """
    query = select(model).where(model.organization_id == actor.org_id)

    if actor.principal_type == "service_principal":
        return query  # machine caller: sees every org-scoped resource regardless of visibility

    granted_ids = select(grant_fk_column).where(grant_model.user_id == actor.email_or_name)
    return query.where(
        or_(
            model.visibility == "organization",
            model.created_by == actor.email_or_name,
            model.id.in_(granted_ids),
        )
    )


def can_access(instance, grant_user_ids: set[str], actor: CurrentActor) -> bool:
    """Non-query variant of the same rule, for a single already-loaded instance (used by
    get-by-id endpoints after the row has already been fetched by organization_id + id)."""
    if actor.principal_type == "service_principal":
        return True
    if instance.visibility == "organization":
        return True
    if instance.created_by == actor.email_or_name:
        return True
    return actor.email_or_name in grant_user_ids
