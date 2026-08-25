import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_config import request_id_ctx_var

logger = logging.getLogger("app.request")


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_ctx_var.set(request_id)
        start = time.perf_counter()
        logger.info("--> %s %s", request.method, request.url.path)
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "<-- %s %s %s (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception("<-- %s %s failed after %.1fms", request.method, request.url.path, duration_ms)
            raise
        finally:
            request_id_ctx_var.reset(token)
