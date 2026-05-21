"""Day 0.7 spike — historical multi-day AWC + IEM + NWS CLI fetch.

THROWAWAY. Do NOT lift this into packages/. Day 2 rewrites cleanly using Vu's
`_internal/` lift.

Goal: prove that `research_spike("KNYC", "2025-04-01", "2025-04-07")` can hit
public APIs with no auth and return rows that LOOK like v0.14.1's `pairs()` rows.

What this proves (or breaks):
- IEM ASOS (`asos.py`) historical METAR for an arbitrary 7-day window — primary path.
- IEM CLI (`cli.py`) settlement / NWS climate for the same window — settlement label.
- AWC live (`aviationweather.gov/api/data/metar`) — sanity check that the live
  endpoint is reachable for the LAST 7 days (cannot do 2025-04-01 from May 2026).

Scope cuts per founder-build-lane.md Day 0.7:
- No packaging, no caching, no merge policy, no real parser.
- Just pull raw responses, pick a few fields, prove the path works.

URL patterns lifted (READ-ONLY) from monorepo-v0.14.1:
- IEM ASOS:  ingest/sources/iem_gap_fill.py:_build_iem_url
- IEM CLI:   ingest/sources/climate_sync.py:download_cli
- AWC live:  ingest/sources/awc_poller.py:fetch_latest
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
IEM_CLI_URL = "https://mesonet.agron.iastate.edu/json/cli.py"
AWC_METAR_URL = "https://aviationweather.gov/api/data/metar"

POLITE_DELAY_S = 1.0
HTTP_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class SpikeStation:
    """Minimal station shim; v0.14.1 uses ingest.stations.StationInfo."""

    icao: str  # e.g. "KNYC"

    @property
    def code(self) -> str:
        """3-letter code for IEM (strip leading 'K')."""
        return self.icao[1:] if self.icao.startswith("K") and len(self.icao) == 4 else self.icao


def fetch_iem_asos(
    station: SpikeStation,
    start: date,
    end: date,
    report_type: int = 3,
) -> str:
    """Fetch historical METAR CSV from IEM ASOS for a date range.

    report_type: 3 = METAR (routine), 4 = SPECI (special).
    IEM treats `end` as EXCLUSIVE — to include observations on `end - 1`, set
    `end` to the day AFTER your inclusive last date.

    Returns the raw CSV body. Caller parses; spike just verifies the path.
    """
    params = {
        "station": station.code,
        "data": "all",
        "tz": "Etc/UTC",
        "format": "comma",
        "latlon": "no",
        "elev": "no",
        "missing": "M",
        "trace": "T",
        "direct": "no",
        "report_type": str(report_type),
        "year1": str(start.year),
        "month1": str(start.month),
        "day1": str(start.day),
        "year2": str(end.year),
        "month2": str(end.month),
        "day2": str(end.day),
    }
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
        r = client.get(IEM_ASOS_URL, params=params)
        r.raise_for_status()
        return r.text


def fetch_iem_cli(station: SpikeStation, year: int) -> list[dict[str, Any]]:
    """Fetch NWS CLI climate reports for a station-year from IEM's cli.py.

    Returns list of climate report dicts. IEM may wrap as {"results": [...]} —
    we unwrap. Each dict has fields like `station`, `valid` (date), `high`,
    `low`, `precip`, `product`, etc.
    """
    params = {"station": station.icao, "year": str(year)}
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
        r = client.get(IEM_CLI_URL, params=params)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "results" in data:
            data = data["results"]
        if not isinstance(data, list):
            raise ValueError(f"Unexpected IEM CLI shape: {type(data).__name__}")
        return data


def fetch_awc_live(station: SpikeStation, hours: int = 168) -> list[dict[str, Any]]:
    """Fetch AWC live METARs for the last N hours (max ~168 = 7 days).

    AWC live has no historical depth — used here only as a sanity check that
    the endpoint is reachable. Real historical fetch goes through IEM ASOS.
    """
    params = {"ids": station.icao, "format": "json", "taf": "false", "hours": str(hours)}
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
        r = client.get(AWC_METAR_URL, params=params)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            raise ValueError(f"Unexpected AWC shape: {type(data).__name__}")
        return data


def _filter_cli_dates(rows: list[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
    """Filter CLI rows whose `valid` date falls in [start, end] inclusive."""
    out: list[dict[str, Any]] = []
    for r in rows:
        v = r.get("valid", "")
        try:
            d = datetime.strptime(v, "%Y-%m-%d").date() if v else None
        except ValueError:
            d = None
        if d and start <= d <= end:
            out.append(r)
    return out


def _count_metar_rows(csv_body: str) -> int:
    """Count non-header, non-comment lines in an IEM ASOS CSV body."""
    lines = csv_body.splitlines()
    n = 0
    for line in lines:
        if not line or line.startswith("#"):
            continue
        # IEM ASOS comma format: header begins with "station,valid," — skip it
        if line.startswith("station,"):
            continue
        n += 1
    return n


def _first_metar_row(csv_body: str) -> str | None:
    """Return the first data line from an IEM ASOS CSV (after header)."""
    for line in csv_body.splitlines():
        if not line or line.startswith("#") or line.startswith("station,"):
            continue
        return line
    return None


def research_spike(
    station_icao: str,
    from_date_str: str,
    to_date_str: str,
) -> dict[str, Any]:
    """Spike orchestrator — joins IEM ASOS METAR + IEM CLI climate for a window.

    Returns a dict summary: counts, sample rows, errors. Does NOT return a
    DataFrame. Day 2 rewrite produces the actual `pairs()`-shaped output.
    """
    station = SpikeStation(icao=station_icao)
    start = datetime.strptime(from_date_str, "%Y-%m-%d").date()
    end = datetime.strptime(to_date_str, "%Y-%m-%d").date()
    end_exclusive = end + timedelta(days=1)  # IEM ASOS end is exclusive

    summary: dict[str, Any] = {
        "station": station_icao,
        "from_date": from_date_str,
        "to_date": to_date_str,
        "ts_utc": datetime.now(UTC).isoformat(),
        "errors": {},
    }

    # 1. Historical METAR from IEM ASOS
    try:
        csv_body = fetch_iem_asos(station, start, end_exclusive, report_type=3)
        summary["iem_asos_metar"] = {
            "bytes": len(csv_body),
            "row_count": _count_metar_rows(csv_body),
            "first_row": _first_metar_row(csv_body),
        }
    except (httpx.HTTPError, ValueError) as exc:
        summary["errors"]["iem_asos_metar"] = f"{type(exc).__name__}: {exc}"

    # 2. Historical SPECI from IEM ASOS (separate request per v0.14.1 pattern)
    try:
        csv_speci = fetch_iem_asos(station, start, end_exclusive, report_type=4)
        summary["iem_asos_speci"] = {
            "bytes": len(csv_speci),
            "row_count": _count_metar_rows(csv_speci),
            "first_row": _first_metar_row(csv_speci),
        }
    except (httpx.HTTPError, ValueError) as exc:
        summary["errors"]["iem_asos_speci"] = f"{type(exc).__name__}: {exc}"

    # 3. NWS CLI climate from IEM cli.py — pull the year, filter to window
    try:
        cli_rows = fetch_iem_cli(station, year=start.year)
        in_window = _filter_cli_dates(cli_rows, start, end)
        summary["iem_cli_climate"] = {
            "year_total_rows": len(cli_rows),
            "in_window_rows": len(in_window),
            "sample_in_window": in_window[:2],
        }
    except (httpx.HTTPError, ValueError) as exc:
        summary["errors"]["iem_cli_climate"] = f"{type(exc).__name__}: {exc}"

    # 4. AWC live sanity check (will only return last ~7 days, not 2025-04 dates)
    try:
        awc_rows = fetch_awc_live(station, hours=168)
        summary["awc_live"] = {
            "row_count": len(awc_rows),
            "sample_row": awc_rows[0] if awc_rows else None,
            "note": "AWC live has no historical depth — included as endpoint reachability check.",
        }
    except (httpx.HTTPError, ValueError) as exc:
        summary["errors"]["awc_live"] = f"{type(exc).__name__}: {exc}"

    summary["go_no_go"] = (
        "GO"
        if (
            summary.get("iem_asos_metar", {}).get("row_count", 0) > 0
            and summary.get("iem_cli_climate", {}).get("in_window_rows", 0) > 0
        )
        else "NO-GO"
    )

    return summary


def main(argv: list[str]) -> int:
    """Run the spike against the lane-doc example: KNYC, 2025-04-01..07."""
    if len(argv) == 4:
        station, from_d, to_d = argv[1], argv[2], argv[3]
    else:
        station, from_d, to_d = "KNYC", "2025-04-01", "2025-04-07"

    print(f"# Day 0.7 spike — {station} {from_d}..{to_d}", flush=True)
    result = research_spike(station, from_d, to_d)
    print(json.dumps(result, indent=2, default=str))

    print(f"\n# Verdict: {result['go_no_go']}", flush=True)
    if result["errors"]:
        print(f"# Errors: {list(result['errors'].keys())}", flush=True)
    return 0 if result["go_no_go"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
