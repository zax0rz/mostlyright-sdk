"""Structured exception hierarchy for the tradewinds SDK and MCP server.

Every exception subclasses :class:`TradewindsError` and exposes a
:meth:`TradewindsError.to_dict` method that returns a JSON-safe dict
suitable for placement in the MCP ``error.data`` field of a JSON-RPC error
response. Attributes mirror the design doc §D + §R contract; payload values
are coerced via :func:`tradewinds.core._json_safe.to_json_safe` so the
returned dict survives ``json.dumps`` without further customization.

Role names for ``SourceMismatchError`` are standardized at ``"observations"``,
``"forecasts"``, ``"settlement"`` (per design.md §R). The column-prefix
abbreviations ``obs_`` / ``fcst_`` / ``settle_`` are NOT valid role names.

``MostlyRightMCPError`` remains importable as a deprecation alias for one
release cycle (removal scheduled for v0.3). Importing it emits a single
``DeprecationWarning`` per session.
"""

from __future__ import annotations

import warnings
from typing import Any

from ._json_safe import to_json_safe

__all__ = [
    "LeakageError",
    "PayloadTooLargeError",
    "SchemaValidationError",
    "SourceMismatchError",
    "SourceUnavailableError",
    "TemporalDriftError",
    "TradewindsError",
    # ``MostlyRightMCPError`` is intentionally NOT in ``__all__``. It is
    # available via module ``__getattr__`` for one release cycle with a
    # DeprecationWarning; removal target v0.3.
]


class TradewindsError(Exception):
    """Base class for all tradewinds structured errors.

    ``error_code`` is a stable enum (e.g. ``"SOURCE_UNAVAILABLE"``) used by
    callers / agents to branch on without parsing message text. ``source`` is
    the source ID involved (``"iem.archive"`` etc.) when applicable, and
    ``request_id`` correlates an MCP JSON-RPC request when applicable.
    """

    #: Subclass override — the stable string enum surfaced via ``error_code``.
    default_error_code: str = "TRADEWINDS_ERROR"

    def __init__(
        self,
        message: str = "",
        *,
        error_code: str | None = None,
        source: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.error_code: str = error_code or self.default_error_code
        self.source: str | None = source
        self.request_id: str | None = request_id

    # ------------------------------------------------------------------
    # JSON-safe payload
    # ------------------------------------------------------------------
    def _payload(self) -> dict[str, Any]:
        """Subclass hook returning the structured attributes for ``to_dict``.

        Subclasses extend this with their own attributes. Values are passed
        through :func:`to_json_safe` by :meth:`to_dict`, so subclasses don't
        need to coerce values themselves.
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "source": self.source,
            "request_id": self.request_id,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict suitable for MCP ``error.data``."""
        return to_json_safe(self._payload())


class SourceUnavailableError(TradewindsError):
    """A source (HTTP endpoint, vendored parser, etc.) returned an error or
    was otherwise unreachable. Carries enough metadata for callers to decide
    whether to retry and after how long.
    """

    default_error_code = "SOURCE_UNAVAILABLE"

    def __init__(
        self,
        message: str = "",
        *,
        source: str | None = None,
        http_status: int | None = None,
        retryable: bool = False,
        retry_after_s: float | None = None,
        underlying: str = "",
        url: str | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=source,
            request_id=request_id,
        )
        self.http_status: int | None = http_status
        self.retryable: bool = retryable
        self.retry_after_s: float | None = retry_after_s
        self.underlying: str = underlying
        self.url: str | None = url

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            http_status=self.http_status,
            retryable=self.retryable,
            retry_after_s=self.retry_after_s,
            underlying=self.underlying,
            url=self.url,
        )
        return payload


class SchemaValidationError(TradewindsError):
    """A DataFrame failed schema validation. Carries the full violation list
    (capped at 10,000 — surplus written to file via §Q file-path mode by the
    SDK) and a small inline sample for MCP wire serialization (≤10 entries).
    """

    default_error_code = "SCHEMA_VALIDATION_FAILED"

    def __init__(
        self,
        message: str = "",
        *,
        schema_id: str,
        violations: list[dict[str, Any]] | None = None,
        quarantine_count: int = 0,
        sample_violations: list[dict[str, Any]] | None = None,
        source: str | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=source,
            request_id=request_id,
        )
        self.schema_id: str = schema_id
        self.violations: list[dict[str, Any]] = list(violations or [])
        self.quarantine_count: int = quarantine_count
        self.sample_violations: list[dict[str, Any]] = list(sample_violations or [])

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            schema_id=self.schema_id,
            violations=self.violations,
            quarantine_count=self.quarantine_count,
            sample_violations=self.sample_violations,
        )
        return payload


class SourceMismatchError(TradewindsError):
    """The data's source does not match the schema's registered source, and
    the caller did not opt out via ``allow_source_drift``. ``role`` (if set)
    identifies which leg of a ``pull_pairs`` request mismatched and uses the
    canonical long form: ``"observations"`` / ``"forecasts"`` / ``"settlement"``.
    """

    default_error_code = "SOURCE_MISMATCH"

    #: Canonical role-name vocabulary (design.md §R).
    VALID_ROLES = frozenset({"observations", "forecasts", "settlement"})

    def __init__(
        self,
        message: str = "",
        *,
        schema_source: str,
        data_source: str,
        role: str | None = None,
        catalog_warning: str | None = None,
        source: str | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=source,
            request_id=request_id,
        )
        self.schema_source: str = schema_source
        self.data_source: str = data_source
        self.role: str | None = role
        self.catalog_warning: str | None = catalog_warning

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            schema_source=self.schema_source,
            data_source=self.data_source,
            role=self.role,
            catalog_warning=self.catalog_warning,
        )
        return payload


class LeakageError(TradewindsError):
    """Temporal leakage detected — at least one row has ``knowledge_time``
    greater than the asserted ``as_of`` cutoff. Carries the count and a small
    sample of violating rows for actionable surfacing.
    """

    default_error_code = "LEAKAGE_DETECTED"

    def __init__(
        self,
        message: str = "",
        *,
        as_of: str,
        violating_count: int,
        sample_violations: list[dict[str, Any]] | None = None,
        source: str | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=source,
            request_id=request_id,
        )
        self.as_of: str = as_of
        self.violating_count: int = violating_count
        self.sample_violations: list[dict[str, Any]] = list(sample_violations or [])

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            as_of=self.as_of,
            violating_count=self.violating_count,
            sample_violations=self.sample_violations,
        )
        return payload


class TemporalDriftError(TradewindsError):
    """Raised by the reproducibility audit (design.md §P) when one or more
    rows have ``retrieved_at`` outside the asserted range AND fall within the
    volatile window of ``now``. Indicates the source materially re-amended
    historical rows since the schema's registered capture.
    """

    default_error_code = "TEMPORAL_DRIFT"

    def __init__(
        self,
        message: str = "",
        *,
        schema_id: str,
        asserted_range: tuple[str, str],
        violating_rows: int,
        sample_violations: list[dict[str, Any]] | None = None,
        source: str | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=source,
            request_id=request_id,
        )
        self.schema_id: str = schema_id
        self.asserted_range: tuple[str, str] = asserted_range
        self.violating_rows: int = violating_rows
        self.sample_violations: list[dict[str, Any]] = list(sample_violations or [])

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            schema_id=self.schema_id,
            asserted_range=list(self.asserted_range),
            violating_rows=self.violating_rows,
            sample_violations=self.sample_violations,
        )
        return payload


class PayloadTooLargeError(TradewindsError):
    """The MCP server rejected an inline payload whose declared size exceeded
    the cap. ``accepted_modes`` advertises the alternatives (e.g. file-path
    mode per design.md §Q).
    """

    default_error_code = "PAYLOAD_TOO_LARGE"

    def __init__(
        self,
        message: str = "",
        *,
        declared_size: int,
        limit: int,
        accepted_modes: list[str] | None = None,
        source: str | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=source,
            request_id=request_id,
        )
        self.declared_size: int = declared_size
        self.limit: int = limit
        self.accepted_modes: list[str] = list(accepted_modes or [])

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            declared_size=self.declared_size,
            limit=self.limit,
            accepted_modes=self.accepted_modes,
        )
        return payload


# ----------------------------------------------------------------------
# Deprecation alias: MostlyRightMCPError → TradewindsError
# ----------------------------------------------------------------------
_DEPRECATION_WARNINGS_EMITTED: set[str] = set()


def __getattr__(name: str) -> Any:
    """Lazy attribute access — emit DeprecationWarning once per session
    for the legacy ``MostlyRightMCPError`` name. Removal target: v0.3.
    """
    if name == "MostlyRightMCPError":
        if name not in _DEPRECATION_WARNINGS_EMITTED:
            warnings.warn(
                "MostlyRightMCPError is deprecated; use TradewindsError. Removal in v0.3.",
                DeprecationWarning,
                stacklevel=2,
            )
            _DEPRECATION_WARNINGS_EMITTED.add(name)
        return TradewindsError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
