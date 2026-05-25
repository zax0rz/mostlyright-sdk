"""TimePoint: UTC-aware timestamp wrapper for mostlyright.core.

Load-bearing for the temporal-safety invariants described in docs/design.md
(see "Definitions" — event_time, knowledge_time, retrieved_at semantics).

Every timestamp in mostlyright.core is UTC-aware. TimePoint:
- normalizes any tz-aware input to UTC internally
- rejects naive datetimes loudly (ValueError with "naive" in message)
- rejects date-only ISO strings loudly (ValueError)
- preserves microsecond precision through ISO round-trips
- compares and hashes by UTC value, so two TimePoints constructed from
  the same instant via different inputs are equal and have the same hash

Uses stdlib zoneinfo (3.11+) for IANA zone display conversions.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd

# Accepted input types for the TimePoint constructor.
TimePointInput = datetime | pd.Timestamp | str


class TimePoint:
    """A UTC-aware timestamp normalized to UTC for storage.

    Construction accepts:
    - ``datetime.datetime`` with ``tzinfo`` set (converted to UTC)
    - ``pandas.Timestamp`` with ``tz`` set (converted to UTC)
    - ISO 8601 string with a timezone (parsed and converted to UTC)

    Rejects:
    - naive ``datetime`` / ``pd.Timestamp`` (``tzinfo`` / ``tz`` is ``None``)
    - date-only ISO strings (no time component, e.g. ``"2026-05-21"``)

    Storage is a ``datetime`` with ``tzinfo=timezone.utc`` and microsecond
    precision preserved.
    """

    __slots__ = ("_utc",)

    def __init__(self, value: TimePointInput) -> None:
        self._utc = _coerce_to_utc_datetime(value)

    # --- accessors ----------------------------------------------------------

    def to_utc(self) -> datetime:
        """Return the underlying UTC ``datetime`` (microseconds preserved)."""
        return self._utc

    def iso(self) -> str:
        """Return an ISO 8601 UTC string.

        Includes microseconds only when non-zero, matching standard
        ``datetime.isoformat()`` behavior (e.g.
        ``"2026-05-21T14:30:00+00:00"`` or
        ``"2026-05-21T14:30:00.123456+00:00"``).
        """
        return self._utc.isoformat()

    def as_zone(self, tz: str) -> datetime:
        """Convert to a different IANA zone via ``zoneinfo.ZoneInfo``.

        Display helper only — the canonical storage stays UTC. Raises
        ``zoneinfo.ZoneInfoNotFoundError`` if ``tz`` is not a known IANA
        timezone.
        """
        return self._utc.astimezone(ZoneInfo(tz))

    # --- constructors -------------------------------------------------------

    @classmethod
    def now(cls) -> TimePoint:
        """Return a ``TimePoint`` for the current UTC time."""
        return cls(datetime.now(UTC))

    @classmethod
    def from_pandas(cls, ts: pd.Timestamp) -> TimePoint:
        """Construct from a tz-aware ``pandas.Timestamp``.

        Explicit alternative to passing a Timestamp to ``TimePoint(...)``
        — useful when the caller wants the pandas-specific dispatch path
        to be unambiguous.

        Raises ``ValueError`` if ``ts`` is ``pd.NaT`` (missing-data sentinel).
        """
        # Reject NaT before the isinstance check: NaT is a pd.Timestamp
        # instance, so the type check below would pass and we'd get a
        # misleading "naive" error from the coercion path.
        _reject_nat_or_nan(ts)
        if not isinstance(ts, pd.Timestamp):
            raise TypeError(f"TimePoint.from_pandas requires pd.Timestamp; got {type(ts).__name__}")
        return cls(ts)

    # --- operators ----------------------------------------------------------

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, TimePoint):
            return NotImplemented
        return self._utc < other._utc

    def __le__(self, other: object) -> bool:
        if not isinstance(other, TimePoint):
            return NotImplemented
        return self._utc <= other._utc

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimePoint):
            return NotImplemented
        return self._utc == other._utc

    def __hash__(self) -> int:
        # Equal TimePoints must have equal hashes; key off the UTC value.
        return hash(self._utc)

    def __repr__(self) -> str:
        return f"TimePoint({self._utc.isoformat()!r})"


# ---------------------------------------------------------------------------
# Internal coercion helpers
# ---------------------------------------------------------------------------


def _reject_nat_or_nan(value: object) -> None:
    """Reject pandas NaT and float NaN before they reach the datetime/pd
    coercion paths.

    ``pd.NaT`` is an instance of both ``pd.Timestamp`` and ``datetime`` but
    silently misroutes through the datetime path and surfaces as a confusing
    "naive datetime (NaT)" error. Float NaN can sneak in from incomplete
    pandas columns. Reject both up-front with a precise message.
    """
    if value is pd.NaT:
        raise ValueError(
            "TimePoint does not accept NaT/NaN; got pd.NaT. "
            "Filter or fill missing timestamps before constructing TimePoint."
        )
    if isinstance(value, float) and math.isnan(value):
        raise ValueError(
            "TimePoint does not accept NaT/NaN; got float NaN. "
            "Filter or fill missing timestamps before constructing TimePoint."
        )


def _coerce_to_utc_datetime(value: TimePointInput) -> datetime:
    """Coerce supported inputs to a UTC ``datetime``.

    Raises:
        ValueError: if the input is NaT/NaN, naive (no tzinfo), a date-only
            ISO string, or otherwise unparseable.
        TypeError: if the input type is not supported.
    """
    # NaT/NaN check must precede the isinstance(pd.Timestamp/datetime) check
    # because pd.NaT is an instance of both; otherwise the datetime path
    # surfaces a misleading "naive datetime (NaT)" message.
    _reject_nat_or_nan(value)

    # pandas.Timestamp is a subclass of datetime.datetime; check it first
    # so we route through pandas' tz handling rather than datetime's.
    if isinstance(value, pd.Timestamp):
        return _from_pandas_timestamp(value)
    if isinstance(value, datetime):
        return _from_datetime(value)
    if isinstance(value, str):
        return _from_iso_string(value)
    raise TypeError(
        f"TimePoint accepts datetime, pd.Timestamp, or ISO string; got {type(value).__name__}"
    )


def _from_datetime(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError(
            "TimePoint requires tz-aware timestamp; got naive datetime "
            f"({dt!r}). Attach a tzinfo (e.g. datetime.timezone.utc) before "
            "constructing a TimePoint."
        )
    # A tzinfo subclass may return None from utcoffset() (e.g. some legacy
    # third-party tz classes). Python's stdlib treats that as "effectively
    # naive" and astimezone(UTC) silently reinterprets the value using the
    # host's local zone -- environment-dependent behavior. Reject it loudly
    # so the caller learns the tz they attached is broken.
    if dt.utcoffset() is None:
        raise ValueError(
            "TimePoint requires tz-aware timestamp with a defined offset; "
            f"got tzinfo with utcoffset()=None ({dt!r}). Use a concrete "
            "timezone such as datetime.timezone.utc or zoneinfo.ZoneInfo(...)."
        )
    return dt.astimezone(UTC)


def _from_pandas_timestamp(ts: pd.Timestamp) -> datetime:
    """Convert a tz-aware ``pd.Timestamp`` to a UTC stdlib ``datetime``.

    Pandas Timestamps carry nanosecond precision, but stdlib ``datetime``
    is microsecond-only. ``to_pydatetime()`` silently truncates the
    sub-microsecond portion (e.g. ``.123456789`` -> ``.123456``). This
    truncation is intentional and matches every other path's precision
    (ISO strings, datetime inputs, parquet round-trips); it is documented
    in the design's TOON loss notes §I.

    We pass ``warn=False`` to suppress the ``UserWarning`` pandas emits on
    non-zero nanoseconds — we already document the truncation behavior
    and don't want repeated warnings spamming caller logs.
    """
    if ts.tz is None:
        raise ValueError(
            "TimePoint requires tz-aware timestamp; got naive pd.Timestamp "
            f"({ts!r}). Use ts.tz_localize(...) before constructing a TimePoint."
        )
    return ts.tz_convert("UTC").to_pydatetime(warn=False)


def _from_iso_string(s: str) -> datetime:
    # Reject empty / whitespace-only strings up front; fromisoformat would
    # raise a less helpful message.
    if not s or not s.strip():
        raise ValueError("TimePoint requires non-empty ISO 8601 string")

    # Strip surrounding whitespace before the date-only heuristic so a
    # leading space doesn't smuggle a bare date past the "T or space"
    # check. (A literal interior space is the ISO 3339 date/time
    # separator, which is what we use to distinguish dates from datetimes
    # -- but a leading/trailing whitespace token isn't that separator.)
    stripped = s.strip()

    # ISO 8601 datetime requires a date/time separator ("T" or space).
    # A bare date like "2026-05-21" has neither; reject before parsing so
    # the error names the actual problem.
    if "T" not in stripped and " " not in stripped:
        raise ValueError(
            f"TimePoint requires datetime, not date (got {s!r}). "
            "Use an ISO 8601 datetime with a timezone, e.g. "
            "'2026-05-21T14:30:00+00:00'."
        )

    try:
        parsed = datetime.fromisoformat(stripped)
    except ValueError as exc:
        raise ValueError(f"TimePoint could not parse ISO 8601 string {s!r}: {exc}") from exc

    if parsed.tzinfo is None:
        raise ValueError(
            "TimePoint requires tz-aware timestamp; got naive ISO string "
            f"({s!r}). Include a timezone offset (e.g. '+00:00' or '-05:00')."
        )
    return parsed.astimezone(UTC)
