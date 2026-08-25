"""The provider-configuration API.

This service has two entry points against one codebase and one database:

  * this FastAPI app - how an organization registers, tests, enables and audits its own email
    and queue providers (uvicorn app.main:app, port 8104)
  * the Celery worker  - what actually consumes and delivers notifications (run_worker.py)

They are deliberately separate processes. The worker must keep draining the queue during an API
deploy, and a hung SMTP relay must never be able to take the configuration UI down with it.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.providers import router as providers_router
from app.config import get_settings
from app.logging_config import configure_logging
from app.middleware import RequestContextLogMiddleware

logger = logging.getLogger("app")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(title=settings.APP_NAME, version="0.1.0")
    app.add_middleware(RequestContextLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @app.get("/health", tags=["health"])
    def health_check():
        return {"status": "ok"}

    app.include_router(providers_router)

    logger.info("%s started in %s mode", settings.APP_NAME, settings.ENV)
    return app


app = create_app()
