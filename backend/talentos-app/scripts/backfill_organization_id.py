"""One-time data migration: stamps every existing jd_analyses/resume_analyses/submissions row
with BOOTSTRAP_ORGANIZATION_ID (from .env), so the 0004 migration can safely make
organization_id NOT NULL. Everything created after this service's IAM migration lands sets
organization_id from the caller's verified token instead (see app/api/v1/*.py) - this script
only exists to backfill rows that predate that change.

Run between the 0003 (add nullable column) and 0004 (make NOT NULL) alembic migrations:

    .venv/Scripts/python.exe -m alembic upgrade 0003
    .venv/Scripts/python.exe scripts/backfill_organization_id.py
    .venv/Scripts/python.exe -m alembic upgrade head

Idempotent: rows that already have an organization_id are left untouched.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.jd_analysis import JDAnalysis  # noqa: E402
from app.models.resume_analysis import ResumeAnalysis  # noqa: E402
from app.models.submission import Submission  # noqa: E402


def main() -> None:
    settings = get_settings()
    if not settings.BOOTSTRAP_ORGANIZATION_ID:
        raise SystemExit("BOOTSTRAP_ORGANIZATION_ID is not set in .env - refusing to backfill.")

    org_id = uuid.UUID(settings.BOOTSTRAP_ORGANIZATION_ID)

    db = SessionLocal()
    try:
        totals = {}
        for model in (JDAnalysis, ResumeAnalysis, Submission):
            updated = (
                db.query(model)
                .filter(model.organization_id.is_(None))
                .update({model.organization_id: org_id}, synchronize_session=False)
            )
            totals[model.__tablename__] = updated
        db.commit()

        for table, count in totals.items():
            print(f"Backfilled {count} row(s) in {table} with organization_id={org_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
