class AppException(Exception):
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppException):
    status_code = 404
    detail = "Not found"


class ConflictError(AppException):
    status_code = 409
    detail = "Conflict"


class ValidationError(AppException):
    status_code = 422
    detail = "Validation error"


class ForbiddenError(AppException):
    status_code = 403
    detail = "Forbidden"


class ConversationAgentError(Exception):
    """Raised when agent-builder-service fails to produce a usable conversation turn after
    exhausting its own primary/fallback model retries, or returns something that isn't the
    JSON object shape the calling turn expects."""
