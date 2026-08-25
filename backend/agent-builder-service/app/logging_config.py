import logging
import logging.handlers
import os
from contextvars import ContextVar

from app.config import get_settings

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get()
        return True


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"


def configure_logging() -> None:
    settings = get_settings()
    os.makedirs(settings.LOG_DIR, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # Avoid duplicate handlers on reload
    root_logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)
    request_id_filter = RequestIdFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(request_id_filter)
    root_logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(settings.LOG_DIR, "app.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_id_filter)
    root_logger.addHandler(file_handler)

    # Quiet down noisy third-party loggers a bit
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
