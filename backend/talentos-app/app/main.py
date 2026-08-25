import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.api.webhooks import router as webhooks_router
from app.config import get_settings
from app.core.exceptions import AppException
from app.core.middleware import RequestContextLogMiddleware
from app.logging_config import configure_logging

logger = logging.getLogger("app")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix="/api/v1")
    # Deliberately NOT under api_v1_router: it's called by voice-agent-service, not an
    # interactive user, and authenticates via a query-param secret instead of an IAM bearer
    # token - see app/api/webhooks.py.
    app.include_router(webhooks_router)

    logger.info("%s started in %s mode", settings.APP_NAME, settings.ENV)
    return app


app = create_app()
