"""Phase 11 — one-shot `latest()` fetch.

Single-source poll: hit AWC or IEM ONCE, parse the response, return the
most-recent observation row with its source identity tag. No fusion, no
cache, no QC.

This is also the per-tick implementation underneath `stream()` — both
surfaces share the same fetch path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

from tradewinds._internal._bounds import validate_icao_for_path
from tradewinds._internal.models.station import StationInfo
from tradewinds.core.exceptions import NoLiveDataError
from tradewinds.live._sources import source_tag, validate_source


def _normalize_station(station: str) -> str:
    """Accept "KNYC" or "NYC" — emit the 4-letter ICAO ("KNYC") form for fetchers."""
    s = station.strip().upper()
    if len(s) == 3:
        return f"K{s}"
    return s


async def _fetch_awc_latest(station: str) -> list[dict[str, Any]]:
    """Poll AWC once for the given station and return parsed observation rows."""
    from tradewinds.weather._awc import awc_to_observation
    from tradewinds.weather._fetchers.awc import fetch_awc_metars

    icao = _normalize_station(station)
    raw_metars = await asyncio.to_thread(fetch_awc_metars, [icao], 1)
    rows: list[dict[str, Any]] = []
    tag = source_tag("awc")
    for raw in raw_metars:
        obs = awc_to_observation(raw)
        if obs is None:
            continue
        obs["source"] = tag
        rows.append(obs)
    return rows


async def _fetch_iem_latest(station: str) -> list[dict[str, Any]]:
    """Poll IEM once for the given station and return parsed observation rows.

    Uses the exact-window IEM ASOS path with ``today_utc`` → ``today_utc + 1``
    and ``skip_cache=True`` so the live poll never poisons the canonical
    year-aligned parquet cache used by ``research()``.
    """
    import tempfile
    from pathlib import Path

    from tradewinds.weather._fetchers.iem_asos import download_iem_asos
    from tradewinds.weather._iem import parse_iem_file

    icao = _normalize_station(station)
    station_code = icao[1:] if icao.startswith("K") and len(icao) == 4 else icao
    validate_icao_for_path(station_code)
    # `download_iem_asos` only reads `station.code` + `station.icao` (the rest
    # are present on the dataclass for SDK consumers but unused here). Pass
    # sentinel values for the remaining required fields — keeping them
    # explicit so the lift surfaces if `download_iem_asos` ever starts
    # reading extra fields off the StationInfo.
    station_info = StationInfo(
        code=station_code,
        name=icao,
        icao=icao,
        timezone="UTC",
        utc_offset_standard=0,
        latitude=0.0,
        longitude=0.0,
    )

    today = datetime.now(UTC).date()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    tag = source_tag("iem")
    rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="tw-live-iem-") as tmp:
        dest_dir = Path(tmp)
        paths = await asyncio.to_thread(
            download_iem_asos,
            station_info,
            today,
            tomorrow,
            dest_dir,
            skip_cache=True,
            report_type=3,
            exact_window=True,
        )
        for path in paths:
            for obs in parse_iem_file(path, observation_type_override="METAR"):
                obs["source"] = tag
                rows.append(obs)
    return rows


async def _fetch_latest(station: str, source: str) -> list[dict[str, Any]]:
    """Dispatch to the per-source fetch."""
    if source == "awc":
        return await _fetch_awc_latest(station)
    if source == "iem":
        return await _fetch_iem_latest(station)
    raise AssertionError(f"unhandled live source {source!r}")


def _pick_most_recent(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the row with the largest ``observed_at``; SPECI > METAR at ties."""
    if not rows:
        return None
    return max(
        rows,
        key=lambda r: (r.get("observed_at", ""), r.get("observation_type") == "SPECI"),
    )


async def latest(
    station: str,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    """Return the most-recent observation row for ``station`` from a SINGLE source.

    Args:
        station: ICAO (``"KNYC"``) or 3-letter US ID (``"NYC"``).
        source: One of ``"awc"`` (default) or ``"iem"``. Case-insensitive.

    Returns:
        Observation dict with ``source`` field set to ``"awc.live"`` or
        ``"iem.live"``.

    Raises:
        ValueError: When ``source`` is not in ``SUPPORTED_SOURCES``.
        NoLiveDataError: When the upstream returned no observations.
    """
    src = validate_source(source)
    rows = await _fetch_latest(station, src)
    picked = _pick_most_recent(rows)
    if picked is None:
        raise NoLiveDataError(
            f"no live data for station={station!r} source={src!r}",
            station=_normalize_station(station),
            source=source_tag(src),
        )
    return picked


__all__ = ["latest"]
