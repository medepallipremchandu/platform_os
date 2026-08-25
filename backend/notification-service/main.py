"""Entrypoint for the provider-configuration API. Run with: python main.py

Matches the `python main.py` convention every other backend in this repo uses.

Note that this starts only the HTTP API. The Celery worker - the half that actually delivers
notifications - is a separate process with its own entrypoint, `run_worker.py`. They are
deliberately independent: the worker must keep draining the queue during an API deploy, and a
hung SMTP relay must never take the configuration UI down with it.
"""
import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_config=None,  # we configure logging ourselves in app.logging_config
    )


if __name__ == "__main__":
    main()
