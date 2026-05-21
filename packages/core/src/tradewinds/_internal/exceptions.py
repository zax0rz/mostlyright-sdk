"""MostlyRight SDK exceptions.

Identical hierarchy to therminal-py for drop-in migration.
"""


class TherminalError(Exception):
    """Base exception for all MostlyRight SDK errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(TherminalError):
    """Resource not found (HTTP 404)."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class RateLimitError(TherminalError):
    """Rate limit exceeded (HTTP 429). Check retry_after attribute."""

    def __init__(self, retry_after: int = 1):
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after}s", status_code=429
        )


class ValidationError(TherminalError):
    """Invalid request parameters (HTTP 400)."""

    def __init__(self, message: str = "Invalid request"):
        super().__init__(message, status_code=400)


class AuthenticationError(TherminalError):
    """Authentication required or failed (HTTP 401)."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class ForbiddenError(TherminalError):
    """Access denied (HTTP 403)."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403)


class ServerError(TherminalError):
    """Server-side error (HTTP 5xx)."""

    def __init__(self, message: str = "Server error", status_code: int = 500):
        super().__init__(message, status_code=status_code)
