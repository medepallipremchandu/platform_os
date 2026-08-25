"""One-time data backfill (run after migration 0002, before migration 0004): sets
organization_id on every existing models/agents row to the value read from .env's
BOOTSTRAP_ORGANIZATION_ID - this environment's single existing organization. Every row
created going forward gets its organization_id from the creating request's verified token
instead (see app/api/v1/models.py / agents.py).

Idempotent: only touches rows where organization_id IS NULL.

Usage (from agent-builder-service/):
    .venv/Scripts/python.exe scripts/backfill_organization_id.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402


def main() -> None:
    settings = get_settings()
    organization_id = uuid.UUID(settings.BOOTSTRAP_ORGANIZATION_ID)

    db = SessionLocal()
    try:
        models_updated = db.execute(
            text("UPDATE models SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": str(organization_id)},
        ).rowcount
        agents_updated = db.execute(
            text("UPDATE agents SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": str(organization_id)},
        ).rowcount
        db.commit()
        print(f"Backfilled organization_id={organization_id}")
        print(f"  models updated: {models_updated}")
        print(f"  agents updated: {agents_updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
