"""Exact-window obs fetcher — bypasses year-aligned monthly cache.

Used by `tradewinds.weather.obs(strategy="exact_window")` to serve small,
caller-bounded windows (e.g. 1-month backtest replays) without pulling a
full calendar year of IEM CSV.

DOES NOT WRITE to the canonical `observations/{STATION}/{YYYY}/{MM}.parquet`
cache — exact_window queries are treated as transient. Callers who need
warm-cache speedups for repeated calls should use `strategy="warm_cache"`.

Source filtering is enforced at the FETCHER BOUNDARY (not post-merge):
post-merge filtering would silently drop rows where the named source lost
the priority tie to a HIGHER-priority source that this call also fetched.
By gating each fetcher behind `source in (None, "<name>")`, the merge sees
only rows from the requested source(s) and the priority resolution is
semantically correct.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from tradewinds._internal.merge import merge_observations
from tradewinds.weather._awc import awc_to_observation
from tradewinds.weather._fetchers.awc import fetch_awc_metars
from tradewinds.weather._fetchers.ghcnh import download_ghcnh
from tradewinds.weather._fetchers.iem_asos import download_iem_asos
from tradewinds.weather._ghcnh import parse_ghcnh_file
from tradewinds.weather._iem import parse_iem_file

if TYPE_CHECKING:
    from tradewinds._internal.models.station import StationInfo


Source = Literal["iem", "ghcnh", "awc"]


def _exact_fetch_observations(
    info: "StationInfo",
    from_date_iso: str,
    to_date_iso: str,
    *,
    source: Source | None = None,
) -> list[dict[str, Any]]:
    """Fetch obs rows for the exact [from_date, to_date] window.

    Skips year-normalization in IEM by passing ``exact_window=True`` to
    ``download_iem_asos``. Does NOT write to the canonical monthly parquet cache.

    Parameters
    ----------
    info : StationInfo
        Resolved station metadata (icao, code, ghcnh_id, ...).
    from_date_iso, to_date_iso : str
        ISO YYYY-MM-DD strings, inclusive bounds for the obs window.
    source : {"iem", "ghcnh", "awc"} | None
        If set, only that source is queried (fetcher-boundary enforcement).
        If None, all three are queried and merged via SOURCE_PRIORITY in
        ``tradewinds._internal.merge.observations`` (AWC > IEM > GHCNh).

    Returns
    -------
    list[dict]
        Merged observation rows for the window. NOT cached to canonical
        monthly parquet; callers wanting cache benefit should use
        ``strategy="warm_cache"``.
    """
    # Local import: research depends on weather, but _exact_fetch only needs
    # the _sources_root helper for path layout — keep the dependency one-way
    # by importing inside the function.
    from tradewinds.research import _sources_root

    from_date = date.fromisoformat(from_date_iso)
    to_date = date.fromisoformat(to_date_iso)
    # Mirror research.py:1167 — extend by 1 day to capture the pre-midnight
    # UTC tail of the last LST settlement window.
    extended_to = to_date + timedelta(days=1)

    sources_root = _sources_root()
    rows: list[dict[str, Any]] = []

    # --- IEM ASOS ----------------------------------------------------------
    # Fetcher-boundary enforcement: skip IEM entirely if caller asked for a
    # different source. Separate dest_dir namespace (per B-5) — exact-window
    # CSVs live in `sources/iem_asos_exact/`, NEVER in `sources/iem_asos/`.
    if source in (None, "iem"):
        iem_exact_dir = sources_root / "iem_asos_exact"
        # IEM has two report types: 3 (METAR) and 4 (SPECI). Mirror the
        # canonical _fetch_iem_month behavior so the merge sees both.
        for report_type, override in ((3, "METAR"), (4, "SPECI")):
            paths = download_iem_asos(
                info,
                from_date,
                extended_to,
                iem_exact_dir,
                report_type=report_type,
                exact_window=True,
            )
            for p in paths:
                rows.extend(parse_iem_file(p, observation_type_override=override))

    # --- AWC METAR (live 168h only) ---------------------------------------
    # ``fetch_awc_metars`` is live-only — no date range. If ``to_date`` is older
    # than ``now - 168h``, AWC will return zero rows for the window. Skip the
    # HTTP call in that case.
    if source in (None, "awc"):
        now_utc = datetime.now(UTC)
        awc_horizon = now_utc.date() - timedelta(days=7)
        if to_date >= awc_horizon:
            raw_metars = fetch_awc_metars([info.icao], hours=168)
            for m in raw_metars:
                obs = awc_to_observation(m)
                if obs is None:
                    continue
                # Filter to station + date range (AWC may serve unrelated
                # stations from cached responses; defensive).
                if obs.get("station_code") != info.code:
                    continue
                obs_date = (obs.get("observed_at") or "")[:10]
                if from_date_iso <= obs_date <= to_date_iso:
                    rows.append(obs)

    # --- GHCNh (per-station-year) -----------------------------------------
    if source in (None, "ghcnh"):
        import httpx

        ghcnh_dir = sources_root / "ghcnh"
        # Per-station-year files; iterate calendar years touching the window.
        for year in range(from_date.year, extended_to.year + 1):
            try:
                psv_path = download_ghcnh(info.ghcnh_id, year, ghcnh_dir)
            except httpx.HTTPStatusError as exc:
                # NCEI returns 404 for stations without data; mirror
                # _fetch_ghcnh_year's graceful skip.
                if exc.response.status_code == 404:
                    continue
                raise
            for row in parse_ghcnh_file(psv_path):
                if row.get("station_code") != info.code:
                    continue
                obs_date = (row.get("observed_at") or "")[:10]
                if from_date_iso <= obs_date <= to_date_iso:
                    rows.append(row)

    # Pre-sort by (observed_at, source) BEFORE merge — mirrors research.py R2
    # mitigation. merge_observations uses first-seen-wins at equal priority
    # and returns `list(best.values())` in dict-insertion order, so input
    # order is load-bearing for both tie-break determinism AND survivor order.
    rows.sort(key=lambda r: (r.get("observed_at") or "", r.get("source") or ""))

    # merge_observations takes a single positional list, NO source_priority kwarg.
    # Priority is hard-coded via SOURCE_PRIORITY in the merge module. Source
    # filtering already happened at the fetcher boundary above — do NOT
    # post-filter merged rows by source.
    return merge_observations(rows)
