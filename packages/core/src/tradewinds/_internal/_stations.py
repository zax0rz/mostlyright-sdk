# Lifted from monorepo-v0.14.1/src/mostlyright/_stations.py
# Source SHA: 514fcdab227e845145ca32b989355647466231d9
# Lift date: 2026-05-22
# Modifications: none (pure-data module; no imports to rename).
"""Station registry — 20 stations with ICAO / lat-lon metadata.

Lives under ``src/mostlyright`` (not ``ingest/``) so it's available to
pip-installed SDK users. The ``ingest`` side re-exports from here for
backward compat; server-side code also uses this registry to orchestrate
fetching per station.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StationInfo:
    """Station metadata used by both SDK (live forecasts) and ingest (backfill)."""

    code: str  # 3-letter NWS code: ATL
    ghcnh_id: str  # NCEI GHCNh station ID: USW00013874
    icao: str  # 4-letter ICAO: KATL
    name: str
    tz: str  # IANA timezone
    latitude: float  # WGS84 latitude (airport reference point)
    longitude: float  # WGS84 longitude (negative = west)


STATIONS: dict[str, StationInfo] = {
    "ATL": StationInfo(
        code="ATL",
        ghcnh_id="USW00013874",
        icao="KATL",
        name="Hartsfield-Jackson Atlanta International",
        tz="America/New_York",
        latitude=33.6407,
        longitude=-84.4277,
    ),
    "AUS": StationInfo(
        code="AUS",
        ghcnh_id="USW00013904",
        icao="KAUS",
        name="Austin-Bergstrom International",
        tz="America/Chicago",
        latitude=30.1975,
        longitude=-97.6664,
    ),
    "BOS": StationInfo(
        code="BOS",
        ghcnh_id="USW00014739",
        icao="KBOS",
        name="Boston Logan International",
        tz="America/New_York",
        latitude=42.3656,
        longitude=-71.0096,
    ),
    "DCA": StationInfo(
        code="DCA",
        ghcnh_id="USW00013743",
        icao="KDCA",
        name="Washington Reagan National",
        tz="America/New_York",
        latitude=38.8512,
        longitude=-77.0402,
    ),
    "DEN": StationInfo(
        code="DEN",
        ghcnh_id="USW00003017",
        icao="KDEN",
        name="Denver International",
        tz="America/Denver",
        latitude=39.8561,
        longitude=-104.6737,
    ),
    "DFW": StationInfo(
        code="DFW",
        ghcnh_id="USW00003927",
        icao="KDFW",
        name="Dallas-Fort Worth International",
        tz="America/Chicago",
        latitude=32.8998,
        longitude=-97.0403,
    ),
    "HOU": StationInfo(
        code="HOU",
        ghcnh_id="USW00012918",
        icao="KHOU",
        name="Houston Hobby",
        tz="America/Chicago",
        latitude=29.6454,
        longitude=-95.2789,
    ),
    "LAS": StationInfo(
        code="LAS",
        ghcnh_id="USW00023169",
        icao="KLAS",
        name="Harry Reid (McCarran) International",
        tz="America/Los_Angeles",
        latitude=36.0840,
        longitude=-115.1537,
    ),
    "LAX": StationInfo(
        code="LAX",
        ghcnh_id="USW00023174",
        icao="KLAX",
        name="Los Angeles International",
        tz="America/Los_Angeles",
        latitude=33.9425,
        longitude=-118.4081,
    ),
    "MDW": StationInfo(
        code="MDW",
        ghcnh_id="USW00014819",
        icao="KMDW",
        name="Chicago Midway International",
        tz="America/Chicago",
        latitude=41.7868,
        longitude=-87.7522,
    ),
    "MIA": StationInfo(
        code="MIA",
        ghcnh_id="USW00012839",
        icao="KMIA",
        name="Miami International",
        tz="America/New_York",
        latitude=25.7959,
        longitude=-80.2870,
    ),
    "MSP": StationInfo(
        code="MSP",
        ghcnh_id="USW00014922",
        icao="KMSP",
        name="Minneapolis-St Paul International",
        tz="America/Chicago",
        latitude=44.8848,
        longitude=-93.2223,
    ),
    "MSY": StationInfo(
        code="MSY",
        ghcnh_id="USW00012916",
        icao="KMSY",
        name="New Orleans Louis Armstrong International",
        tz="America/Chicago",
        latitude=29.9934,
        longitude=-90.2580,
    ),
    "NYC": StationInfo(
        code="NYC",
        ghcnh_id="USW00094728",
        icao="KNYC",
        name="Central Park, New York",
        tz="America/New_York",
        latitude=40.7789,
        longitude=-73.9692,
    ),
    "OKC": StationInfo(
        code="OKC",
        ghcnh_id="USW00013967",
        icao="KOKC",
        name="Oklahoma City Will Rogers World",
        tz="America/Chicago",
        latitude=35.3931,
        longitude=-97.6007,
    ),
    "PHL": StationInfo(
        code="PHL",
        ghcnh_id="USW00013739",
        icao="KPHL",
        name="Philadelphia International",
        tz="America/New_York",
        latitude=39.8721,
        longitude=-75.2411,
    ),
    "PHX": StationInfo(
        code="PHX",
        ghcnh_id="USW00023183",
        icao="KPHX",
        name="Phoenix Sky Harbor International",
        tz="America/Phoenix",
        latitude=33.4373,
        longitude=-112.0078,
    ),
    "SAT": StationInfo(
        code="SAT",
        ghcnh_id="USW00012921",
        icao="KSAT",
        name="San Antonio International",
        tz="America/Chicago",
        latitude=29.5337,
        longitude=-98.4698,
    ),
    "SEA": StationInfo(
        code="SEA",
        ghcnh_id="USW00024233",
        icao="KSEA",
        name="Seattle-Tacoma International",
        tz="America/Los_Angeles",
        latitude=47.4502,
        longitude=-122.3088,
    ),
    "SFO": StationInfo(
        code="SFO",
        ghcnh_id="USW00023234",
        icao="KSFO",
        name="San Francisco International",
        tz="America/Los_Angeles",
        latitude=37.6213,
        longitude=-122.3790,
    ),
}
