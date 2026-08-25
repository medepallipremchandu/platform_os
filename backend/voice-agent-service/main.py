from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Allows running this file directly (`python main.py`) regardless of the current working
# directory, mirroring the reference implementation's app/main.py.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from app.api.router import router as api_router  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.exceptions import AppException  # noqa: E402
from app.services.retry_poller import poll_forever  # noqa: E402

settings = get_settings()
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    poller_task = asyncio.create_task(poll_forever(settings.RETRY_POLL_INTERVAL_SECONDS))
    logger.info(
        "Retry poller started (interval=%ss). BASE_URL=%s (must be a public tunnel for real "
        "Twilio callbacks to reach this service).",
        settings.RETRY_POLL_INTERVAL_SECONDS,
        settings.BASE_URL,
    )
    try:
        yield
    finally:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(api_router)

    logger.info("%s started in %s mode", settings.APP_NAME, settings.ENV)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.RELOAD, log_level=settings.LOG_LEVEL.lower())
