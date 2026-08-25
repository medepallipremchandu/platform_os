from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, current_actor, get_db
from app.models.permission import Permission

router = APIRouter(prefix="/permissions", tags=["permissions"])


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str | None


@router.get("", response_model=list[PermissionOut])
def list_permissions(db: Session = Depends(get_db), _actor: CurrentActor = Depends(current_actor)):
    return list(db.execute(select(Permission).order_by(Permission.code)).scalars().all())
