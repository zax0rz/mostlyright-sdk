"""Structured exception hierarchy for the mostlyright SDK and MCP server.

Every exception subclasses :class:`TradewindsError` and exposes a
:meth:`TradewindsError.to_dict` method that returns a JSON-safe dict
suitable for placement in the MCP ``error.data`` field of a JSON-RPC error
response. Attributes mirror the design doc §D + §R contract; payload values
are coerced via :func:`mostlyright.core._json_safe.to_json_safe` so the
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
from datetime import datetime
from typing import Any

from ._json_safe import to_json_safe

__all__ = [
    "DeprecatedModelWarning",
    "GribIntegrityError",
    "HistoricalDepthError",
    "LeakageError",
    "LiveStreamError",
    "NoLiveDataError",
    "NoLiveForNwpError",
    "NwpError",
    "NwpModelNotAvailableError",
    "NwpModelRetiredError",
    "PayloadTooLargeError",
    "SchemaValidationError",
    "SourceMismatchError",
    "SourceUnavailableError",
    "StormNotFoundError",
    "TemporalDriftError",
    "TradewindsError",
    # ``MostlyRightMCPError`` is intentionally NOT in ``__all__``. It is
    # available via module ``__getattr__`` for one release cycle with a
    # DeprecationWarning; removal target v0.3.
]


class TradewindsError(Exception):
    """Base class for all mostlyright structured errors.

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
# Phase 3.2: NWP forecast errors
# ----------------------------------------------------------------------


class NwpError(TradewindsError):
    """Base class for Phase 3.2 NWP forecast errors.

    Subclasses cover the three failure modes a quant fetching live NWP
    data hits in practice: an unsupported model (ECMWF Tier-2 reserved
    for v0.2), no live cycle reachable from any wired mirror, or
    decoded GRIB2 bytes that failed integrity / structural validation.
    """

    default_error_code = "NWP_ERROR"


class NwpModelNotAvailableError(NwpError):
    """Model is declared in the public enum but not implemented in this version.

    Raised for the four ECMWF Tier-2 models (``ecmwf_ifs_hres``,
    ``ecmwf_ifs_ens``, ``ecmwf_aifs_single``, ``ecmwf_aifs_ens``) which
    require hosted infrastructure to backfill and are deferred to v0.2.
    ``model`` carries the offending model id and ``available_in`` names
    the release that will land it.
    """

    default_error_code = "NWP_MODEL_NOT_AVAILABLE"

    def __init__(
        self,
        message: str = "",
        *,
        model: str,
        available_in: str = "v0.2",
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=f"nwp.{model}",
            request_id=request_id,
        )
        self.model: str = model
        self.available_in: str = available_in

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(model=self.model, available_in=self.available_in)
        return payload


class NoLiveForNwpError(NwpError):
    """All wired mirrors failed to serve a live cycle for ``(model, cycle)``.

    Carries the mirror chain that was tried and the per-mirror failure
    summary so callers can audit why every fallback failed. Distinct
    from :class:`SourceUnavailableError` because the recovery action is
    different — for NWP, the typical fix is to wait for the next cycle
    rather than retry the same one.
    """

    default_error_code = "NWP_NO_LIVE"

    def __init__(
        self,
        message: str = "",
        *,
        model: str,
        mirrors_tried: list[str] | None = None,
        last_status: int | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=f"nwp.{model}",
            request_id=request_id,
        )
        self.model: str = model
        self.mirrors_tried: list[str] = list(mirrors_tried or [])
        self.last_status: int | None = last_status

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            model=self.model,
            mirrors_tried=self.mirrors_tried,
            last_status=self.last_status,
        )
        return payload


class GribIntegrityError(NwpError):
    """A fetched GRIB2 byte-range failed structural / integrity validation.

    Raised when the GRIB2 record retrieved via byte-range does not match
    its ``.idx`` claim, decodes with missing variables, or cfgrib
    surfaces an "unexpected end of message" / "messages out of order"
    error. Carries the variable that triggered the error plus the
    ``(byte_offset, byte_end)`` of the offending record so the caller
    can replay or skip.
    """

    default_error_code = "NWP_GRIB_INTEGRITY"

    def __init__(
        self,
        message: str = "",
        *,
        model: str,
        variable: str | None = None,
        byte_offset: int | None = None,
        byte_end: int | None = None,
        underlying: str = "",
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=f"nwp.{model}",
            request_id=request_id,
        )
        self.model: str = model
        self.variable: str | None = variable
        self.byte_offset: int | None = byte_offset
        self.byte_end: int | None = byte_end
        self.underlying: str = underlying

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            model=self.model,
            variable=self.variable,
            byte_offset=self.byte_offset,
            byte_end=self.byte_end,
            underlying=self.underlying,
        )
        return payload


class HistoricalDepthError(NwpError):
    """A requested NWP cycle is older than the archive's depth.

    Per Phase 17 FORECAST-07: each NWP model has an AWS BDP depth
    (HRRR ≥2014-07-30, GFS ≥2021-01-01, GEFS ≥2017-01-01, NBM ≥2020,
    ECMWF IFS ≥2022-01-01, AIFS ≥2024-02-25). MSC family always raises
    (24h Datamart retention) — pass ``archive_depth=None`` for the
    live-only case.

    Attributes:
        model: Model id (e.g. ``"hrrr"``, ``"hrdps"``).
        requested_cycle: UTC datetime the caller asked for.
        archive_depth: Earliest cycle the archive holds, or ``None`` for
            live-only models (MSC 24h retention, NOMADS-only legacy).
    """

    default_error_code = "NWP_HISTORICAL_DEPTH"

    def __init__(
        self,
        message: str = "",
        *,
        model: str,
        requested_cycle: datetime | None = None,
        archive_depth: datetime | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=f"nwp.{model}",
            request_id=request_id,
        )
        self.model: str = model
        self.requested_cycle: datetime | None = requested_cycle
        self.archive_depth: datetime | None = archive_depth

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            model=self.model,
            requested_cycle=(self.requested_cycle.isoformat() if self.requested_cycle else None),
            archive_depth=(self.archive_depth.isoformat() if self.archive_depth else None),
        )
        return payload


class DeprecatedModelWarning(DeprecationWarning):
    """Warning emitted when a deprecated NWP model is fetched.

    Used for NAM / HREF / HiResW which retire 2026-08-31 per NWS scn26-47
    (Herbie issue #540). Subclass of :class:`DeprecationWarning` so callers
    can promote it to an error via ``warnings.filterwarnings("error",
    category=DeprecatedModelWarning)``.
    """


class StormNotFoundError(NwpError):
    """A HAFS storm query (id or name) doesn't match any active storm.

    Phase 17 PLAN-06 / FORECAST-14. Carries the query and the list of
    currently-active storm IDs so callers can present a useful error.
    Historical HAFS access requires passing the canonical storm_id
    directly (Storms() only knows currently-active storms).
    """

    default_error_code = "NWP_STORM_NOT_FOUND"

    def __init__(
        self,
        message: str = "",
        *,
        query: str = "",
        active_storms: list[str] | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source="nwp.hafs",
            request_id=request_id,
        )
        self.query: str = query
        self.active_storms: list[str] = list(active_storms or [])

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(query=self.query, active_storms=list(self.active_storms))
        return payload


class NwpModelRetiredError(NwpError):
    """Caller asked for a model past its retirement date.

    Phase 17 PLAN-06 / FORECAST-06: NAM / HREF / HiResW retire 2026-08-31
    per NWS scn26-47 (Herbie issue #540). The retirement date is loaded
    from :data:`mostlyright.weather._fetchers._url_transitions.LEGACY_MODELS_RETIRE`.
    Carries ``replacement_suggestions`` so callers can wire a graceful
    fallback (HRRR / RAP / RRFS).
    """

    default_error_code = "NWP_MODEL_RETIRED"

    def __init__(
        self,
        message: str = "",
        *,
        model: str = "",
        retired_on: datetime | None = None,
        replacement_suggestions: list[str] | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=f"nwp.{model}",
            request_id=request_id,
        )
        self.model: str = model
        self.retired_on: datetime | None = retired_on
        self.replacement_suggestions: list[str] = list(replacement_suggestions or [])

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(
            model=self.model,
            retired_on=self.retired_on.isoformat() if self.retired_on else None,
            replacement_suggestions=list(self.replacement_suggestions),
        )
        return payload


# ----------------------------------------------------------------------
# Live streaming (Phase 11)
# ----------------------------------------------------------------------


class LiveStreamError(TradewindsError):
    """Base class for ``mostlyright.live.stream`` / ``live.latest`` failures.

    Live-streaming errors are deliberately a separate sub-tree from
    :class:`SourceUnavailableError` because the recovery path differs —
    for a live stream, the caller is in a polling loop and "no data yet"
    is the COMMON case, not an exception. :class:`NoLiveDataError` is
    only raised by the one-shot :func:`mostlyright.live.latest` surface;
    :func:`mostlyright.live.stream` swallows empty-tick errors and waits
    for the next polite-floor cycle.
    """

    default_error_code = "LIVE_STREAM_ERROR"


class NoLiveDataError(LiveStreamError):
    """:func:`mostlyright.live.latest` returned no observations for the station.

    Carries the resolved ICAO ``station`` and the canonical source identity
    tag (``"awc.live"`` / ``"iem.live"``) so caller logs can branch by
    source without re-parsing the message.
    """

    default_error_code = "NO_LIVE_DATA"

    def __init__(
        self,
        message: str = "",
        *,
        station: str,
        source: str,
        request_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            source=source,
            request_id=request_id,
        )
        self.station: str = station

    def _payload(self) -> dict[str, Any]:
        payload = super()._payload()
        payload.update(station=self.station)
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
