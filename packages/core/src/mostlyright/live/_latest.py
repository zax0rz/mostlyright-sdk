"""Phase 11 — one-shot `latest()` fetch.

Single-source poll: hit AWC or IEM ONCE, parse the response, return the
most-recent observation row with its source identity tag. No fusion, no
cache, no QC.

This is also the per-tick implementation underneath `stream()` — both
surfaces share the same fetch path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from mostlyright._internal._bounds import validate_icao_for_path
from mostlyright._internal.models.station import StationInfo
from mostlyright.core.exceptions import NoLiveDataError
from mostlyright.live._sources import source_tag, validate_source


def _normalize_station(station: str) -> str:
    """Accept "KNYC" or "NYC" — emit the 4-letter ICAO ("KNYC") form for fetchers."""
    s = station.strip().upper()
    if len(s) == 3:
        return f"K{s}"
    return s


def _require_weather() -> None:
    """Raise a friendly ImportError if the `mostlyrightmd-weather` sibling
    distribution isn't installed.

    `mostlyright.live` lives in `mostlyright-core` but the AWC/IEM fetchers
    + parsers are in `mostlyrightmd-weather`. Per CORE's pyproject note,
    weather is intentionally NOT a runtime dep of core (would create a
    distribution cycle). Users who want `live` must install with the
    `[research]` extra or `mostlyrightmd-weather` directly.
    """
    try:
        import mostlyright.weather  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised on clean install only
        raise ImportError(
            "mostlyright.live.stream/latest requires `mostlyrightmd-weather`. "
            "Install via `pip install mostlyrightmd[research]` or `pip install "
            "mostlyrightmd-weather`."
        ) from exc


async def _fetch_awc_latest(station: str) -> list[dict[str, Any]]:
    """Poll AWC once for the given station and return parsed observation rows."""
    _require_weather()
    from mostlyright.weather._awc import awc_to_observation
    from mostlyright.weather._fetchers.awc import fetch_awc_metars

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

    Issues TWO HTTP requests per poll — one for routine METARs
    (``report_type=3``) and one for SPECI specials (``report_type=4``).
    IEM strips the ``SPECI`` keyword from the raw METAR text and serves
    SPECIs only via ``report_type=4``, so fetching only routine METARs
    would miss intra-hour specials and `_pick_most_recent` could return
    an older METAR when a fresher SPECI exists. Both requests use the
    exact-window single-day path with ``skip_cache=True`` so the live
    poll never poisons the canonical year-aligned parquet cache used by
    ``research()``.
    """
    _require_weather()
    import tempfile
    from pathlib import Path

    from mostlyright.weather._fetchers.iem_asos import download_iem_asos
    from mostlyright.weather._iem import parse_iem_file

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

    from datetime import date as _date

    today = datetime.now(UTC).date()
    yesterday = _date.fromordinal(today.toordinal() - 1)
    tag = source_tag("iem")
    rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="tw-live-iem-") as tmp:
        dest_dir = Path(tmp)
        # Issue both report types — routine METARs (3) AND SPECI specials (4) —
        # across TWO UTC days [yesterday, today]. The previous-day inclusion is
        # the iter-4 codex fix: shortly after 00:00 UTC, the current-day
        # window has no observations yet (IEM hasn't ingested the day's first
        # METAR), so a today-only fetch would always return empty even when a
        # minutes-old METAR exists from the prior UTC day. `download_iem_asos(
        # exact_window=True)` treats `end` as INCLUSIVE and advances `day2` by
        # one day internally for IEM's exclusive-end semantics — so
        # (yesterday, today) gives a two-day [yesterday, today+1) window.
        for report_type, override in ((3, "METAR"), (4, "SPECI")):
            paths = await asyncio.to_thread(
                download_iem_asos,
                station_info,
                yesterday,
                today,
                dest_dir,
                skip_cache=True,
                report_type=report_type,
                exact_window=True,
            )
            for path in paths:
                for obs in parse_iem_file(path, observation_type_override=override):
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
