import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    changed_by: str
    changes: dict | None
    changed_at: datetime
