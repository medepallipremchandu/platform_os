"""Entrypoint. Run with: python main.py

Starts the FastAPI app (app.main:app) under uvicorn using settings from .env.
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
