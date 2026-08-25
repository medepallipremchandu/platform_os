class AppException(Exception):
    status_code: int = 500

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppException):
    status_code = 404


class InvalidStateError(AppException):
    """Raised when a request is well-formed but violates a business rule."""

    status_code = 422


class LLMProviderError(AppException):
    status_code = 502
