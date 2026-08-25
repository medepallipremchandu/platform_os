"""Celery worker entry point.

Two modes, same code:

    # Platform worker - consumes tier-1 ingest AND the default delivery queue.
    # Every organization that has NOT brought its own queue is served by this one.
    .venv/Scripts/python.exe run_worker.py

    # Tenant worker - consumes notifications.deliver_email from ONE organization's own broker.
    # Only needed for an organization that has enabled a queue provider.
    .venv/Scripts/python.exe run_worker.py --organization <organization-uuid>

Windows: Celery's default prefork pool does not work here (it relies on fork), so the pool
defaults to "solo" on win32 and prefork elsewhere. Override with --pool if you know better.
"""
import argparse
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="TalentOS notification worker")
    parser.add_argument(
        "--organization",
        help=(
            "Consume from THIS organization's own queue provider instead of the platform broker. "
            "Only valid for an organization with an enabled queue provider."
        ),
    )
    parser.add_argument("--pool", default="solo" if sys.platform == "win32" else "prefork")
    parser.add_argument("--loglevel", default="INFO")
    parser.add_argument("--concurrency", default=None)
    args = parser.parse_args()

    from app.celery_app import build_celery_app, celery_app
    from app.config import get_settings
    from app.database import get_db_session
    from app.logging_config import configure_logging

    configure_logging()
    import app.tasks  # noqa: F401  - registers both tasks on the default app

    settings = get_settings()

    if args.organization:
        from app.services import resolver

        db = get_db_session()
        try:
            queue = resolver.resolve_queue_provider(db, uuid.UUID(args.organization))
        finally:
            db.close()
        if queue is None:
            print(
                f"Organization {args.organization} has no enabled queue provider. "
                "Its notifications are served by the platform worker - start that instead "
                "(run_worker.py with no --organization).",
                file=sys.stderr,
            )
            return 1
        worker_app = build_celery_app(
            f"talentos-notifications-{args.organization}",
            queue.provider.broker_url(),
            queue.provider.transport_options(),
        )
        worker_app.conf.task_default_queue = settings.NOTIFICATIONS_QUEUE_NAME
        # Re-register the tasks on this app: @shared_task binds lazily to whichever apps exist,
        # so deliver_email is picked up, while send_email stays bound to the platform app only -
        # exactly right, since dispatch must never run off a tenant broker.
        worker_app.autodiscover_tasks(["app"], force=True)
        print(f"Consuming organization {args.organization}'s own {queue.key} queue")
        target = worker_app
    else:
        print(f"Consuming the platform broker ({settings.NOTIFICATIONS_BROKER_URL.split('@')[-1]})")
        target = celery_app

    argv = ["worker", f"--loglevel={args.loglevel}", f"--pool={args.pool}", "-Q", settings.NOTIFICATIONS_QUEUE_NAME]
    if args.concurrency:
        argv.append(f"--concurrency={args.concurrency}")
    target.worker_main(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
