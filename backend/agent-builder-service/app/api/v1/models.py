from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, get_db, require_permission
from app.core import permissions
from app.core.exceptions import NotFoundError
from app.core.iam_client import post_audit_event
from app.models.model import Model
from app.schemas.model import ModelCreateRequest, ModelOut, ModelUpdateRequest
from app.services.model_service import create_model, deactivate_model, update_model

router = APIRouter(prefix="/models", tags=["models"])


def _get_model_or_404(db: Session, model_id: UUID, organization_id) -> Model:
    model = db.query(Model).filter(Model.id == model_id, Model.organization_id == organization_id).first()
    if model is None:
        raise NotFoundError(f"Model {model_id} not found")
    return model


@router.post("", response_model=ModelOut, status_code=201)
def create_model_endpoint(
    payload: ModelCreateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.MODELS_MANAGE)),
    authorization: str | None = Header(default=None),
):
    model = create_model(
        db,
        name=payload.name,
        provider=payload.provider,
        model_id=payload.model_id,
        api_key=payload.api_key,
        actor=actor.email_or_name,
        organization_id=actor.org_id,
        endpoint=payload.endpoint,
        api_version=payload.api_version,
    )
    post_audit_event(authorization, action="model.created", target_type="model", target_id=model.id)
    return model


@router.get("", response_model=list[ModelOut])
def list_models(
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_READ)),
):
    return (
        db.query(Model)
        .filter(Model.is_active.is_(True), Model.organization_id == actor.org_id)
        .order_by(Model.created_at.desc())
        .all()
    )


@router.get("/{model_id}", response_model=ModelOut)
def get_model(
    model_id: UUID,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.AGENTS_READ)),
):
    return _get_model_or_404(db, model_id, actor.org_id)


@router.patch("/{model_id}", response_model=ModelOut)
def patch_model(
    model_id: UUID,
    payload: ModelUpdateRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.MODELS_MANAGE)),
    authorization: str | None = Header(default=None),
):
    """Renames the model and/or re-encrypts a freshly re-entered credential in place -
    `provider`/`model_id` are not editable (see ModelUpdateRequest)."""
    model = _get_model_or_404(db, model_id, actor.org_id)
    update_model(
        db,
        model,
        name=payload.name,
        api_key=payload.api_key,
        endpoint=payload.endpoint,
        api_version=payload.api_version,
    )
    post_audit_event(authorization, action="model.updated", target_type="model", target_id=model.id)
    return model


@router.delete("/{model_id}", response_model=ModelOut)
def delete_model(
    model_id: UUID,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(require_permission(permissions.MODELS_MANAGE)),
    authorization: str | None = Header(default=None),
):
    model = _get_model_or_404(db, model_id, actor.org_id)
    model = deactivate_model(db, model)
    post_audit_event(authorization, action="model.deleted", target_type="model", target_id=model.id)
    return model
