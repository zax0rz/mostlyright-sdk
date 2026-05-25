"""Phase 11 — per-source registry + polite floors.

Each upstream public API has its own politeness contract. We hard-code the
minimum-allowed `poll_seconds` per source so callers cannot accidentally
hammer the endpoint. Values below the floor raise ValueError at stream()
startup, not on the first tick — fail fast.

AWC: 30s floor. The aviationweather.gov live endpoint serves recent METARs
    with no documented rate limit; 30s is the floor we've validated empirically
    won't trip anti-abuse heuristics.
IEM: 60s floor. mesonet.agron.iastate.edu is a university server; the IEM
    documentation explicitly requests 1+ req/s with reasonable headroom.
    A 60s cadence comfortably stays below their threshold.
"""

from __future__ import annotations

from typing import Final

# Canonical ordered tuple of supported sources. ORDER MATTERS for the
# default-source resolution in stream()/latest() and for error-message
# stability — keep AWC first.
SUPPORTED_SOURCES: Final[tuple[str, ...]] = ("awc", "iem")

# Minimum allowed poll cadence per source. Streams that pass `poll_seconds`
# below the floor raise ValueError at startup. Streams that omit `poll_seconds`
# default to the floor for the active source.
POLITE_FLOORS_S: Final[dict[str, float]] = {
    "awc": 30.0,
    "iem": 60.0,
}

# Canonical per-source `source` field tag emitted on every observation row.
SOURCE_IDENTITY_TAGS: Final[dict[str, str]] = {
    "awc": "awc.live",
    "iem": "iem.live",
}


def validate_source(source: str | None) -> str:
    """Normalize and validate a source kwarg.

    Args:
        source: Caller-supplied source string. ``None`` → defaults to first
            entry in ``SUPPORTED_SOURCES`` (AWC). Case-insensitive.

    Returns:
        The normalized lowercase source name (one of ``SUPPORTED_SOURCES``).

    Raises:
        ValueError: When the source is not in ``SUPPORTED_SOURCES``.
    """
    if source is None:
        return SUPPORTED_SOURCES[0]
    normalized = source.strip().lower()
    if normalized not in SUPPORTED_SOURCES:
        raise ValueError(
            f"unknown live source {source!r}; supported: {SUPPORTED_SOURCES!r}"
        )
    return normalized


def validate_poll_seconds(poll_seconds: float | None, source: str) -> float:
    """Apply the polite-floor invariant to a caller-supplied cadence.

    Args:
        poll_seconds: Caller-supplied poll cadence. ``None`` → use the floor.
        source: A *validated* source name (call ``validate_source`` first).

    Returns:
        The cadence to use, in seconds.

    Raises:
        ValueError: When ``poll_seconds`` is below the polite floor.
    """
    floor = POLITE_FLOORS_S[source]
    if poll_seconds is None:
        return floor
    if poll_seconds < floor:
        raise ValueError(
            f"poll_seconds={poll_seconds} below polite floor "
            f"{floor}s for source={source!r}"
        )
    return float(poll_seconds)


def source_tag(source: str) -> str:
    """Map a validated source name to its canonical row-level identity tag."""
    return SOURCE_IDENTITY_TAGS[source]


__all__ = [
    "POLITE_FLOORS_S",
    "SOURCE_IDENTITY_TAGS",
    "SUPPORTED_SOURCES",
    "source_tag",
    "validate_poll_seconds",
    "validate_source",
]
