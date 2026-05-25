"""HTTP-layer exception hierarchy (drop-in equivalent to therminal-py).

These exceptions mirror the surface ``therminal-py`` exposed for HTTP
transport errors. ``TherminalError`` remains as the HTTP-layer marker so
existing call sites (Phase 1 fetchers) continue to catch it, but it is now
a subclass of :class:`mostlyright.core.exceptions.TradewindsError` so that
user code which catches ``TradewindsError`` also catches transport errors.
Deprecation target: v0.2+ may collapse these into ``SourceUnavailableError``.
"""

from mostlyright.core.exceptions import TradewindsError


class TherminalError(TradewindsError):
    """Base exception for mostlyright HTTP-layer errors.

    Subclass of :class:`TradewindsError` since Phase 2 — catching
    ``TradewindsError`` now catches transport errors too. The HTTP-layer
    ``status_code`` attribute is the only attribute on the original
    ``therminal-py`` surface; structured ``error_code`` / ``source`` /
    ``request_id`` flow through ``TradewindsError.__init__``.
    """

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(TherminalError):
    """Resource not found (HTTP 404)."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class RateLimitError(TherminalError):
    """Rate limit exceeded (HTTP 429). Check retry_after attribute."""

    def __init__(self, retry_after: int = 1):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s", status_code=429)


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
