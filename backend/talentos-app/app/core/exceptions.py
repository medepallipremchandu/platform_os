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


class BadRequestError(AppException):
    """Raised when the request itself is fine but required data is missing on the referenced
    record (e.g. no candidate phone number on file)."""

    status_code = 400


class ConflictError(AppException):
    """Raised when an action can't proceed because of the current state of another resource
    (e.g. no call-agent config configured/enabled for a JD yet)."""

    status_code = 409


class LLMProviderError(AppException):
    status_code = 502
