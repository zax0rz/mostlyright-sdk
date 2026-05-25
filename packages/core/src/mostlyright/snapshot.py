# Lifted from monorepo-v0.14.1/src/mostlyright/snapshot.py
# Source SHA: 514fcdab227e845145ca32b989355647466231d9
# Lift date: 2026-05-22
# Modifications:
#   - import-rename: mostlyright.models.observation -> tradewinds._internal.models.observation
#   - import-rename: mostlyright.versioning -> tradewinds._internal.versioning
#   - import-rename: mostlyright._toon -> tradewinds._internal._toon (lifted in PR #2 fix branch)
#   - ruff auto-fix UP017 (timezone.utc -> datetime.UTC)
#   - ruff-clean ambiguous-unicode (RUF002/003): EN DASH and MINUS SIGN in comments
#     and docstrings replaced with HYPHEN-MINUS. No code-path change.
"""Historical data snapshot — all data available at a given UTC moment.

Snapshot answers: "What would an AI agent have known at time T for station X?"

Key concepts:
- LOCAL STANDARD TIME (LST): station's standard UTC offset, DST ignored.
  Kalshi NHIGH/NLOW contracts define the settlement window in LST.
- Settlement window: midnight-midnight LST for a given date.
  During US daylight saving, the clock window is 1:00 AM-1:00 AM next day
  (EDT), but the UTC bounds are the same year-round.
- CLI publication delay: NWS issues the overnight final CLI ~04:00-10:00 UTC
  (midnight-5 AM ET) the day after observation. Default assumption: 10 AM ET
  = 10 h after midnight LST. Climate record is withheld from the snapshot
  until as_of is past that threshold.
- as_of: observations are filtered to [window_start_utc, as_of] (both bounds).

NOTE: `forecasts` field stubs to None. Full support requires the
sprint2/forecast-backfill branch to be merged into main.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from tradewinds._internal.models.observation import Observation
from tradewinds._internal.versioning import DataVersion

# ---------------------------------------------------------------------------
# Station → IANA timezone database
# Used to extract the LOCAL STANDARD TIME UTC offset (January reference date).
# ---------------------------------------------------------------------------

_STATION_TZ: dict[str, str] = {
    # Eastern (UTC-5 standard / UTC-4 DST)
    "NYC": "America/New_York",
    "JFK": "America/New_York",
    "LGA": "America/New_York",
    "EWR": "America/New_York",
    "ATL": "America/New_York",
    "BOS": "America/New_York",
    "PHL": "America/New_York",
    "DCA": "America/New_York",
    "IAD": "America/New_York",
    "BWI": "America/New_York",
    "MIA": "America/New_York",
    "MCO": "America/New_York",
    "TPA": "America/New_York",
    "CLT": "America/New_York",
    "RDU": "America/New_York",
    "CLE": "America/New_York",
    "PIT": "America/New_York",
    "BUF": "America/New_York",
    "DTW": "America/Detroit",
    "IND": "America/Indiana/Indianapolis",
    "CVG": "America/New_York",
    "CMH": "America/New_York",
    "SYR": "America/New_York",
    "ALB": "America/New_York",
    "BTV": "America/New_York",
    "ORF": "America/New_York",
    "RIC": "America/New_York",
    "GSO": "America/New_York",
    "CHS": "America/New_York",
    "SAV": "America/New_York",
    "JAX": "America/New_York",
    "RSW": "America/New_York",
    "PBI": "America/New_York",
    "FLL": "America/New_York",
    # Central (UTC-6 standard / UTC-5 DST)
    "ORD": "America/Chicago",
    "MDW": "America/Chicago",
    "DFW": "America/Chicago",
    "DAL": "America/Chicago",
    "IAH": "America/Chicago",
    "HOU": "America/Chicago",
    "MSP": "America/Chicago",
    "STL": "America/Chicago",
    "MCI": "America/Chicago",
    "OMA": "America/Chicago",
    "MKE": "America/Chicago",
    "MSY": "America/Chicago",
    "MEM": "America/Chicago",
    "BNA": "America/Chicago",
    "OKC": "America/Chicago",
    "SAT": "America/Chicago",
    "AUS": "America/Chicago",
    "DSM": "America/Chicago",
    "TUL": "America/Chicago",
    "LIT": "America/Chicago",
    "BIR": "America/Chicago",
    "SDF": "America/Chicago",
    "HSV": "America/Chicago",
    "BHM": "America/Chicago",
    "MOB": "America/Chicago",
    "BTR": "America/Chicago",
    "SHV": "America/Chicago",
    # Mountain (UTC-7 standard / UTC-6 DST)
    "DEN": "America/Denver",
    "SLC": "America/Denver",
    "ABQ": "America/Denver",
    "BOI": "America/Boise",
    "BZN": "America/Denver",
    "GJT": "America/Denver",
    # Arizona: no DST (UTC-7 always)
    "PHX": "America/Phoenix",
    "TUS": "America/Phoenix",
    # Pacific (UTC-8 standard / UTC-7 DST)
    "LAX": "America/Los_Angeles",
    "SFO": "America/Los_Angeles",
    "SEA": "America/Los_Angeles",
    "PDX": "America/Los_Angeles",
    "LAS": "America/Los_Angeles",
    "SAN": "America/Los_Angeles",
    "OAK": "America/Los_Angeles",
    "SJC": "America/Los_Angeles",
    "SMF": "America/Los_Angeles",
    "RNO": "America/Los_Angeles",
    "FAT": "America/Los_Angeles",
    "SNA": "America/Los_Angeles",
    "ONT": "America/Los_Angeles",
    "BUR": "America/Los_Angeles",
    # Alaska (UTC-9 standard / UTC-8 DST)
    "ANC": "America/Anchorage",
    "FAI": "America/Anchorage",
    "JNU": "America/Juneau",
    # Hawaii (UTC-10, no DST)
    "HNL": "Pacific/Honolulu",
    "OGG": "Pacific/Honolulu",
    "KOA": "Pacific/Honolulu",
}

# Reference datetime in January (no DST in Northern Hemisphere US).
# July reference is the southern-hemisphere fallback: Sydney / Auckland /
# São Paulo / Buenos Aires are on standard time in July (their winter).
_JAN_REF = datetime(2024, 1, 15, 12, 0)
_JUL_REF = datetime(2024, 7, 15, 12, 0)

# NWS CLI typical publication time: 10 hours after midnight LST
# (overnight final issued ~04:00-10:00 UTC = midnight-5 AM ET)
CLI_PUBLICATION_DELAY_HOURS = 10.0


def _station_code_normalized(station: str) -> str:
    """Strip leading 'K' and uppercase — 'KNYC' → 'NYC'."""
    s = station.strip().upper()
    if len(s) == 4 and s.startswith("K"):
        return s[1:]
    return s


def _lst_offset(station: str, tz_override: str | None = None) -> timedelta:
    """Return the LOCAL STANDARD TIME UTC offset for a station.

    Uses the January UTC offset (no DST in January for all US stations).

    Args:
        station: Station code (3- or 4-letter, e.g. "NYC" or "KNYC").
        tz_override: IANA timezone name to use instead of the built-in map.
            Use when the station is not in _STATION_TZ. E.g. "America/Chicago".

    Returns:
        A negative timedelta, e.g. timedelta(hours=-5) for Eastern.

    Raises:
        ValueError: If station is not in the known timezone map and tz_override
            is not provided. No silent fallback — an unknown station means the
            settlement window calculation would be silently wrong.
    """
    code = _station_code_normalized(station)
    if tz_override:
        tz_name = tz_override
    elif code in _STATION_TZ:
        tz_name = _STATION_TZ[code]
    else:
        # Phase 3.1 extension: fall back to the expanded STATIONS registry
        # so intl ICAOs (EGLL, RJTT, ...) resolve without a tz_override.
        # The original 20-US tz map stays the primary lookup (preserves the
        # v0.14.1 byte-equivalence path for US settlement-date math).
        from tradewinds._internal._stations import STATIONS

        info = STATIONS.get(code)
        if info is None:
            # Also accept the raw ICAO key in case the caller passed an ICAO
            # whose normalization didn't match (e.g. non-K-prefix intl ICAO).
            for s in STATIONS.values():
                if s.icao == station.strip().upper() or s.code == code:
                    info = s
                    break
        if info is None:
            raise ValueError(
                f"Unknown station timezone: {code!r}. "
                f"Add it to _STATION_TZ or pass tz_override='America/...'."
            )
        tz_name = info.tz
    tz = ZoneInfo(tz_name)
    # Phase 3.1: pick a reference moment that is NOT in DST so the returned
    # offset is the true LST offset. Sample January first (correct for every
    # US station and every northern-hemisphere zone). If January reports DST
    # (which happens for southern-hemisphere zones — YSSY/YMML/NZAA/NZWN/
    # SBGR/SAEZ all sit in their summer in January), fall back to July, which
    # is winter (= no DST) for those zones.
    aware_jan = _JAN_REF.replace(tzinfo=tz)
    if aware_jan.dst() == timedelta(0):
        offset = aware_jan.utcoffset()
    else:
        aware_jul = _JUL_REF.replace(tzinfo=tz)
        offset = aware_jul.utcoffset()
    return offset if offset is not None else timedelta(hours=-5)


def _parse_as_of(as_of: str | datetime) -> datetime:
    """Parse as_of to an aware UTC datetime.

    Accepts:
    - ISO 8601 string with or without timezone (bare = UTC assumed)
    - datetime object (naive = UTC assumed)
    """
    if isinstance(as_of, datetime):
        if as_of.tzinfo is None:
            return as_of.replace(tzinfo=UTC)
        return as_of.astimezone(UTC)
    s = as_of.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def settlement_date_for(
    as_of: str | datetime,
    station: str,
    tz_override: str | None = None,
) -> str:
    """Return the Kalshi settlement date (YYYY-MM-DD LST) for a UTC moment.

    Kalshi NHIGH/NLOW contracts cover midnight-midnight LOCAL STANDARD TIME.
    DST is ignored: the window is always fixed to the standard UTC offset.

    Args:
        as_of: UTC moment (ISO string or aware datetime).
        station: Station code (e.g. "NYC", "ATL", "KORD").
        tz_override: IANA timezone name override for unknown stations.

    Returns:
        ISO date string (YYYY-MM-DD) representing the settlement date in LST.

    Examples:
        >>> settlement_date_for("2024-07-04T03:00:00Z", "NYC")
        '2024-07-03'  # 03:00 UTC = 22:00 EDT = 22:00 LST (UTC-5) → July 3
    """
    utc_dt = _parse_as_of(as_of)
    offset = _lst_offset(station, tz_override=tz_override)
    lst_dt = utc_dt + offset  # offset is negative → subtract magnitude
    return lst_dt.date().isoformat()


def settlement_window_utc(
    date_str: str,
    station: str,
    tz_override: str | None = None,
) -> tuple[datetime, datetime]:
    """Return UTC start/end of the Kalshi settlement window for a date.

    The window is midnight-midnight LST, expressed in UTC.

    Args:
        date_str: ISO date string (YYYY-MM-DD) in LST.
        station: Station code.
        tz_override: IANA timezone name override for unknown stations.

    Returns:
        (window_start_utc, window_end_utc) as timezone-aware UTC datetimes.
    """
    from datetime import date as _date

    offset = _lst_offset(station, tz_override=tz_override)
    lst_date = _date.fromisoformat(date_str)

    # midnight LST = 00:00 LST = 00:00 UTC - offset (offset is negative)
    # Example: UTC-5 → midnight LST = 05:00 UTC
    midnight_lst_naive = datetime(lst_date.year, lst_date.month, lst_date.day, 0, 0)
    window_start = (midnight_lst_naive - offset).replace(tzinfo=UTC)
    window_end = window_start + timedelta(days=1)
    return window_start, window_end


def cli_available_at(
    date_str: str,
    station: str,
    delay_hours: float = CLI_PUBLICATION_DELAY_HOURS,
    tz_override: str | None = None,
) -> datetime:
    """Return the UTC time at which the NWS CLI for a date is expected to be available.

    NWS overnight final CLI is issued approximately 10 hours after midnight LST
    (i.e., 10 AM local standard time the following day).

    Args:
        date_str: Settlement date (YYYY-MM-DD in LST).
        station: Station code.
        delay_hours: Hours after midnight LST when CLI is published. Default 10.
        tz_override: IANA timezone name override for unknown stations.

    Returns:
        Aware UTC datetime when CLI is expected.
    """
    _, window_end = settlement_window_utc(date_str, station, tz_override=tz_override)
    # CLI for date D is published ~delay_hours after midnight LST on D+1
    # window_end is already midnight LST of D+1
    return window_end + timedelta(hours=delay_hours)


@dataclass
class DataSnapshot:
    """All data available at a historical moment for a station.

    Used for AI-native data access: reproducible, temporally honest,
    settlement-window-aware.

    Attributes:
        station: Station code (normalized, e.g. "NYC").
        as_of: Query timestamp (UTC ISO 8601 string).
        settlement_date: Kalshi settlement date (YYYY-MM-DD in LST).
        window_start_utc: UTC start of the settlement window (midnight LST).
        window_end_utc: UTC end of the settlement window (midnight LST + 24h).
        observations: METAR/SPECI observations within [window_start_utc, as_of].
        climate: NWS CLI climate record for settlement_date. None if not yet
            published at as_of (CLI expected ~10 AM ET next day).
        climate_unavailable_reason: Explanation when climate is None. Either
            a data gap message or a publication delay message with expected time.
            None when climate is available.
        cli_publication_delay_hours: Hours assumed for CLI publication delay.
        forecasts: Placeholder for forecast data. Always None until
            sprint2/forecast-backfill is merged into main.
        version: DataVersion for this snapshot. Deterministic hash of
            station + sorted observation timestamps. as_of stored as metadata only.
    """

    station: str
    as_of: str
    settlement_date: str
    window_start_utc: str
    window_end_utc: str
    observations: list[Observation]
    climate: dict[str, Any] | None
    climate_unavailable_reason: str | None
    cli_publication_delay_hours: float
    forecasts: list[dict[str, Any]] | None  # stub: requires forecast-backfill branch
    version: DataVersion

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict (matches specs/snapshot.json)."""
        return {
            "station": self.station,
            "as_of": self.as_of,
            "settlement_date": self.settlement_date,
            "window_start_utc": self.window_start_utc,
            "window_end_utc": self.window_end_utc,
            # Codex P2 fix: use storage shape (no computed fields) so to_dict()
            # matches snapshot.json schema (observation.json has additionalProperties: false).
            "observations": [o.to_storage_dict() for o in self.observations],
            "climate": self.climate,
            "climate_unavailable_reason": self.climate_unavailable_reason,
            "cli_publication_delay_hours": self.cli_publication_delay_hours,
            "forecasts": self.forecasts,
            # data_version is a string per specs/snapshot.json — spec-compliant as-is.
            "data_version": self.version.latest_observation or "empty",
        }

    def to_toon(self) -> str:
        """Encode as TOON v3.0 string for LLM/AI agent consumption."""
        from tradewinds._internal._toon import encode

        d = self.to_dict()
        # Replace observations list with storage dicts for tabular encoding
        d["observations"] = [o.to_storage_dict() for o in self.observations]
        return encode(d)


def build_snapshot(
    station: str,
    as_of: str | datetime,
    observations: list[Observation],
    all_climate: list[dict[str, Any]],
    cli_publication_delay_hours: float = CLI_PUBLICATION_DELAY_HOURS,
    tz_override: str | None = None,
) -> DataSnapshot:
    """Build a DataSnapshot from pre-fetched observations and climate records.

    Filters observations to [window_start_utc, as_of] (both bounds inclusive).
    Filters climate to what was available at as_of per publication delay.
    Called by MostlyRightClient.snapshot() after fetching from API.

    Args:
        station: Station code.
        as_of: Query timestamp.
        observations: All observations for the station (caller may pre-filter by
            date range; this function applies the settlement window lower bound).
        all_climate: Climate records for the station/date (may be empty).
        cli_publication_delay_hours: Hours after midnight LST for CLI publication.
        tz_override: IANA timezone name override for unknown stations.

    Returns:
        DataSnapshot with temporally-honest data.

    Raises:
        ValueError: If station is not in the known timezone map and tz_override
            is not provided.
    """
    utc_dt = _parse_as_of(as_of)
    as_of_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    code = _station_code_normalized(station)

    settlement_date = settlement_date_for(utc_dt, code, tz_override=tz_override)
    win_start, win_end = settlement_window_utc(settlement_date, code, tz_override=tz_override)

    # Filter: only observations within [window_start, as_of] (both bounds).
    # The filter uses parsed datetimes (not pre-formatted strings) so DST-aware
    # tz offsets survive correctly — see _parse_obs_dt below.

    def _parse_obs_dt(ts: str) -> datetime | None:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except (ValueError, AttributeError):
            return None

    filtered_obs = [
        o
        for o in observations
        if (obs_dt := _parse_obs_dt(o.observed_at)) is not None and win_start <= obs_dt <= utc_dt
    ]

    # Climate: filter to settlement_date only, then check publication threshold
    _PRIORITY = {
        "final": 3.0,
        "ncei_final": 2.5,
        "correction": 2.0,
        "preliminary": 1.0,
        "estimated": 0.0,
    }
    date_climate = [r for r in all_climate if r.get("observation_date") == settlement_date]
    cli_threshold = cli_available_at(
        settlement_date, code, cli_publication_delay_hours, tz_override=tz_override
    )
    climate_record: dict[str, Any] | None = None
    if utc_dt >= cli_threshold and date_climate:
        sorted_climate = sorted(
            date_climate,
            key=lambda r: _PRIORITY.get(r.get("report_type", ""), -1),
            reverse=True,
        )
        climate_record = sorted_climate[0] if sorted_climate else None

    # Determine reason for None climate
    if climate_record is not None:
        climate_reason: str | None = None
    elif not date_climate:
        climate_reason = f"No CLI record found for {settlement_date} at station {code}."
    else:
        pub_str = cli_threshold.strftime("%Y-%m-%dT%H:%M:%SZ")
        climate_reason = (
            f"CLI not yet published. Expected at {pub_str} "
            f"({cli_publication_delay_hours:.0f}h after midnight LST)."
        )

    # Build DataVersion from filtered observations
    obs_timestamps = [o.observed_at for o in filtered_obs]
    data_version = DataVersion.from_timestamps(
        station=code,
        as_of=as_of_str,
        observation_timestamps=obs_timestamps,
    )

    return DataSnapshot(
        station=code,
        as_of=as_of_str,
        settlement_date=settlement_date,
        window_start_utc=win_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_end_utc=win_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        observations=filtered_obs,
        climate=climate_record,
        climate_unavailable_reason=climate_reason,
        cli_publication_delay_hours=cli_publication_delay_hours,
        forecasts=None,  # stub: requires sprint2/forecast-backfill
        version=data_version,
    )
