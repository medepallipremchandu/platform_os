import logging
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.model import Model
from app.services import crypto

logger = logging.getLogger("app.services.model")


def _next_model_code(db: Session) -> str:
    seq_value = db.execute(text("SELECT nextval('model_code_seq')")).scalar_one()
    return f"MDL{seq_value:02d}"


def create_model(
    db: Session,
    name: str,
    provider: str,
    model_id: str,
    api_key: str,
    actor: str,
    organization_id: uuid.UUID,
    endpoint: str | None = None,
    api_version: str | None = None,
) -> Model:
    model = Model(
        model_code=_next_model_code(db),
        organization_id=organization_id,
        name=name,
        provider=provider,
        model_id=model_id,
        endpoint=endpoint,
        api_version=api_version,
        api_key_encrypted=crypto.encrypt(api_key),
        created_by=actor,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    logger.info("Model %s (%s) registered: %s/%s", model.model_code, model.id, provider, model_id)
    return model


def deactivate_model(db: Session, model: Model) -> Model:
    model.is_active = False
    db.commit()
    db.refresh(model)
    return model


def update_model(
    db: Session,
    model: Model,
    *,
    name: str | None = None,
    api_key: str | None = None,
    endpoint: str | None = None,
    api_version: str | None = None,
) -> Model:
    """Renames the model and/or re-encrypts a freshly re-entered credential. `provider` and
    `model_id` are never touched here - see ModelUpdateRequest's docstring."""
    if name is not None:
        model.name = name
    if api_key is not None:
        model.api_key_encrypted = crypto.encrypt(api_key)
    if endpoint is not None:
        model.endpoint = endpoint
    if api_version is not None:
        model.api_version = api_version
    db.commit()
    db.refresh(model)
    logger.info("Model %s (%s) updated", model.model_code, model.id)
    return model
