# Lifted from monorepo-v0.14.1/src/mostlyright/_stations.py
# Source SHA: 514fcdab227e845145ca32b989355647466231d9
# Lift date: 2026-05-22
# Modifications:
#   - Phase 3.1 (2026-05-23): added ``country`` field (default "US" for backward
#     compat with the 20 v0.14.1 entries) + 40 international ICAO entries.
#     International entries set ``ghcnh_id=""`` because NCEI's GHCNh dataset is
#     US-only; the adapter layer skips the GHCNh fetch for non-US stations.
#   - Added :func:`is_us_station` helper for the adapter-coverage gate in
#     ``research()``.
"""Station registry — 60 stations (20 US + 40 international) with ICAO / lat-lon metadata.

Lives under ``src/tradewinds/_internal`` so it ships in the wheel and is
available to pip-installed SDK users. Phase 3.1 expanded the v0.14.1
20-station Kalshi registry to 60 stations covering Polymarket's
international weather markets (Europe, Asia, Oceania, Americas-non-US).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StationInfo:
    """Station metadata used by both SDK (live forecasts) and ingest (backfill).

    Attributes:
        code: For US stations, the 3-letter NWS code (e.g. ``"ATL"``). For
            international stations, the 4-letter ICAO (e.g. ``"EGLL"``) is used
            as ``code`` since there's no 3-letter NWS analog outside the US.
        ghcnh_id: NCEI GHCNh station identifier (e.g. ``"USW00013874"``).
            **Empty string** for international stations — NCEI's GHCNh dataset
            is US-only, so the adapter layer skips the GHCNh fetch for non-US
            stations and relies on IEM (which carries global METAR/AWOS).
        icao: 4-letter ICAO identifier (e.g. ``"KATL"``, ``"EGLL"``).
        name: Full station name.
        tz: IANA timezone name (e.g. ``"America/New_York"``).
        latitude: WGS84 latitude (decimal degrees).
        longitude: WGS84 longitude (decimal degrees; negative = west).
        country: ISO 3166-1 alpha-2 country code. Defaults to ``"US"`` to
            preserve the v0.14.1 contract on the 20 original entries.
    """

    code: str
    ghcnh_id: str
    icao: str
    name: str
    tz: str
    latitude: float
    longitude: float
    country: str = "US"


STATIONS: dict[str, StationInfo] = {
    # ------------------------------------------------------------------
    # US — 20 Kalshi-traded stations (v0.14.1 verbatim).
    # ------------------------------------------------------------------
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
    # ------------------------------------------------------------------
    # International — 40 ICAOs covering Polymarket's intl weather markets.
    # ``ghcnh_id=""`` because NCEI GHCNh is US-only; adapter layer skips
    # GHCNh for these stations (see ``research._fetch_observations_range``).
    # ICAO is used as both ``code`` and registry key.
    # ------------------------------------------------------------------
    # Europe.
    "EGLL": StationInfo(
        code="EGLL",
        ghcnh_id="",
        icao="EGLL",
        name="London Heathrow",
        tz="Europe/London",
        latitude=51.4706,
        longitude=-0.4619,
        country="GB",
    ),
    "EGKK": StationInfo(
        code="EGKK",
        ghcnh_id="",
        icao="EGKK",
        name="London Gatwick",
        tz="Europe/London",
        latitude=51.1481,
        longitude=-0.1903,
        country="GB",
    ),
    "LFPG": StationInfo(
        code="LFPG",
        ghcnh_id="",
        icao="LFPG",
        name="Paris Charles de Gaulle",
        tz="Europe/Paris",
        latitude=49.0097,
        longitude=2.5479,
        country="FR",
    ),
    "LFPB": StationInfo(
        code="LFPB",
        ghcnh_id="",
        icao="LFPB",
        name="Paris Le Bourget",
        tz="Europe/Paris",
        latitude=48.9694,
        longitude=2.4414,
        country="FR",
    ),
    "LFPO": StationInfo(
        code="LFPO",
        ghcnh_id="",
        icao="LFPO",
        name="Paris Orly",
        tz="Europe/Paris",
        latitude=48.7233,
        longitude=2.3794,
        country="FR",
    ),
    "EDDF": StationInfo(
        code="EDDF",
        ghcnh_id="",
        icao="EDDF",
        name="Frankfurt am Main",
        tz="Europe/Berlin",
        latitude=50.0379,
        longitude=8.5622,
        country="DE",
    ),
    "EDDB": StationInfo(
        code="EDDB",
        ghcnh_id="",
        icao="EDDB",
        name="Berlin Brandenburg",
        tz="Europe/Berlin",
        latitude=52.3667,
        longitude=13.5033,
        country="DE",
    ),
    "EDDM": StationInfo(
        code="EDDM",
        ghcnh_id="",
        icao="EDDM",
        name="Munich Franz Josef Strauss",
        tz="Europe/Berlin",
        latitude=48.3538,
        longitude=11.7861,
        country="DE",
    ),
    "LEMD": StationInfo(
        code="LEMD",
        ghcnh_id="",
        icao="LEMD",
        name="Madrid Barajas",
        tz="Europe/Madrid",
        latitude=40.4719,
        longitude=-3.5626,
        country="ES",
    ),
    "LEBL": StationInfo(
        code="LEBL",
        ghcnh_id="",
        icao="LEBL",
        name="Barcelona El Prat",
        tz="Europe/Madrid",
        latitude=41.2974,
        longitude=2.0833,
        country="ES",
    ),
    "LIRF": StationInfo(
        code="LIRF",
        ghcnh_id="",
        icao="LIRF",
        name="Rome Fiumicino",
        tz="Europe/Rome",
        latitude=41.8003,
        longitude=12.2389,
        country="IT",
    ),
    "LIMC": StationInfo(
        code="LIMC",
        ghcnh_id="",
        icao="LIMC",
        name="Milan Malpensa",
        tz="Europe/Rome",
        latitude=45.6306,
        longitude=8.7281,
        country="IT",
    ),
    "EHAM": StationInfo(
        code="EHAM",
        ghcnh_id="",
        icao="EHAM",
        name="Amsterdam Schiphol",
        tz="Europe/Amsterdam",
        latitude=52.3086,
        longitude=4.7639,
        country="NL",
    ),
    "EKCH": StationInfo(
        code="EKCH",
        ghcnh_id="",
        icao="EKCH",
        name="Copenhagen Kastrup",
        tz="Europe/Copenhagen",
        latitude=55.6181,
        longitude=12.6561,
        country="DK",
    ),
    "ESSA": StationInfo(
        code="ESSA",
        ghcnh_id="",
        icao="ESSA",
        name="Stockholm Arlanda",
        tz="Europe/Stockholm",
        latitude=59.6519,
        longitude=17.9186,
        country="SE",
    ),
    "EFHK": StationInfo(
        code="EFHK",
        ghcnh_id="",
        icao="EFHK",
        name="Helsinki-Vantaa",
        tz="Europe/Helsinki",
        latitude=60.3172,
        longitude=24.9633,
        country="FI",
    ),
    "LSZH": StationInfo(
        code="LSZH",
        ghcnh_id="",
        icao="LSZH",
        name="Zurich",
        tz="Europe/Zurich",
        latitude=47.4647,
        longitude=8.5492,
        country="CH",
    ),
    "LOWW": StationInfo(
        code="LOWW",
        ghcnh_id="",
        icao="LOWW",
        name="Vienna International",
        tz="Europe/Vienna",
        latitude=48.1103,
        longitude=16.5697,
        country="AT",
    ),
    "EPWA": StationInfo(
        code="EPWA",
        ghcnh_id="",
        icao="EPWA",
        name="Warsaw Chopin",
        tz="Europe/Warsaw",
        latitude=52.1657,
        longitude=20.9671,
        country="PL",
    ),
    "UUEE": StationInfo(
        code="UUEE",
        ghcnh_id="",
        icao="UUEE",
        name="Moscow Sheremetyevo",
        tz="Europe/Moscow",
        latitude=55.9728,
        longitude=37.4147,
        country="RU",
    ),
    # Asia.
    "RJTT": StationInfo(
        code="RJTT",
        ghcnh_id="",
        icao="RJTT",
        name="Tokyo Haneda",
        tz="Asia/Tokyo",
        latitude=35.5522,
        longitude=139.7800,
        country="JP",
    ),
    "RJAA": StationInfo(
        code="RJAA",
        ghcnh_id="",
        icao="RJAA",
        name="Tokyo Narita",
        tz="Asia/Tokyo",
        latitude=35.7647,
        longitude=140.3864,
        country="JP",
    ),
    "RKSI": StationInfo(
        code="RKSI",
        ghcnh_id="",
        icao="RKSI",
        name="Seoul Incheon",
        tz="Asia/Seoul",
        latitude=37.4691,
        longitude=126.4505,
        country="KR",
    ),
    "ZBAA": StationInfo(
        code="ZBAA",
        ghcnh_id="",
        icao="ZBAA",
        name="Beijing Capital",
        tz="Asia/Shanghai",
        latitude=40.0801,
        longitude=116.5846,
        country="CN",
    ),
    "ZSPD": StationInfo(
        code="ZSPD",
        ghcnh_id="",
        icao="ZSPD",
        name="Shanghai Pudong",
        tz="Asia/Shanghai",
        latitude=31.1443,
        longitude=121.8083,
        country="CN",
    ),
    "VHHH": StationInfo(
        code="VHHH",
        ghcnh_id="",
        icao="VHHH",
        name="Hong Kong International",
        tz="Asia/Hong_Kong",
        latitude=22.3080,
        longitude=113.9185,
        country="HK",
    ),
    "RCTP": StationInfo(
        code="RCTP",
        ghcnh_id="",
        icao="RCTP",
        name="Taipei Taoyuan",
        tz="Asia/Taipei",
        latitude=25.0777,
        longitude=121.2328,
        country="TW",
    ),
    "WSSS": StationInfo(
        code="WSSS",
        ghcnh_id="",
        icao="WSSS",
        name="Singapore Changi",
        tz="Asia/Singapore",
        latitude=1.3644,
        longitude=103.9915,
        country="SG",
    ),
    "VTBS": StationInfo(
        code="VTBS",
        ghcnh_id="",
        icao="VTBS",
        name="Bangkok Suvarnabhumi",
        tz="Asia/Bangkok",
        latitude=13.6900,
        longitude=100.7501,
        country="TH",
    ),
    "VABB": StationInfo(
        code="VABB",
        ghcnh_id="",
        icao="VABB",
        name="Mumbai Chhatrapati Shivaji",
        tz="Asia/Kolkata",
        latitude=19.0887,
        longitude=72.8679,
        country="IN",
    ),
    "VIDP": StationInfo(
        code="VIDP",
        ghcnh_id="",
        icao="VIDP",
        name="Delhi Indira Gandhi",
        tz="Asia/Kolkata",
        latitude=28.5562,
        longitude=77.1000,
        country="IN",
    ),
    "OMDB": StationInfo(
        code="OMDB",
        ghcnh_id="",
        icao="OMDB",
        name="Dubai International",
        tz="Asia/Dubai",
        latitude=25.2532,
        longitude=55.3657,
        country="AE",
    ),
    "OERK": StationInfo(
        code="OERK",
        ghcnh_id="",
        icao="OERK",
        name="Riyadh King Khalid International",
        tz="Asia/Riyadh",
        latitude=24.9576,
        longitude=46.6988,
        country="SA",
    ),
    "OTHH": StationInfo(
        code="OTHH",
        ghcnh_id="",
        icao="OTHH",
        name="Doha Hamad International",
        tz="Asia/Qatar",
        latitude=25.2731,
        longitude=51.6080,
        country="QA",
    ),
    # Oceania.
    "YSSY": StationInfo(
        code="YSSY",
        ghcnh_id="",
        icao="YSSY",
        name="Sydney Kingsford Smith",
        tz="Australia/Sydney",
        latitude=-33.9461,
        longitude=151.1772,
        country="AU",
    ),
    "YMML": StationInfo(
        code="YMML",
        ghcnh_id="",
        icao="YMML",
        name="Melbourne Tullamarine",
        tz="Australia/Melbourne",
        latitude=-37.6733,
        longitude=144.8433,
        country="AU",
    ),
    "YBBN": StationInfo(
        code="YBBN",
        ghcnh_id="",
        icao="YBBN",
        name="Brisbane",
        tz="Australia/Brisbane",
        latitude=-27.3842,
        longitude=153.1175,
        country="AU",
    ),
    "NZAA": StationInfo(
        code="NZAA",
        ghcnh_id="",
        icao="NZAA",
        name="Auckland",
        tz="Pacific/Auckland",
        latitude=-37.0081,
        longitude=174.7917,
        country="NZ",
    ),
    "NZWN": StationInfo(
        code="NZWN",
        ghcnh_id="",
        icao="NZWN",
        name="Wellington",
        tz="Pacific/Auckland",
        latitude=-41.3272,
        longitude=174.8053,
        country="NZ",
    ),
    # Americas (non-US).
    "SBGR": StationInfo(
        code="SBGR",
        ghcnh_id="",
        icao="SBGR",
        name="São Paulo Guarulhos",
        tz="America/Sao_Paulo",
        latitude=-23.4356,
        longitude=-46.4731,
        country="BR",
    ),
    "SAEZ": StationInfo(
        code="SAEZ",
        ghcnh_id="",
        icao="SAEZ",
        name="Buenos Aires Ezeiza",
        tz="America/Argentina/Buenos_Aires",
        latitude=-34.8222,
        longitude=-58.5358,
        country="AR",
    ),
}


def is_us_station(icao: str) -> bool:
    """Return True iff ``icao`` is a US station in STATIONS with country=="US".

    Used by :func:`tradewinds.research._fetch_observations_range` to gate
    the GHCNh fetch — NCEI's GHCNh dataset is US-only, so international
    stations skip that fetcher and rely on IEM (which carries global
    METAR/AWOS via the unified ASOS-1min/IEM AWOS network).

    The check is conservative on two axes:

    1. ICAO must start with ``"K"`` — covers CONUS (Alaska/Hawaii/territories
       use ``"P*"`` prefixes; those would not be in this registry today).
    2. The station must be present in :data:`STATIONS` with ``country == "US"``.

    Both gates must pass; a non-registered ``"K..."`` ICAO returns ``False``.

    Args:
        icao: 4-letter ICAO identifier.

    Returns:
        ``True`` for the 20 US registry entries; ``False`` for the 40
        international entries and for unknown ICAOs.
    """
    if not icao or not icao.startswith("K"):
        return False
    # ICAO is the registry key for international entries; for US entries the
    # 3-letter NWS code is the key. Scan by .icao attribute (matches either).
    for s in STATIONS.values():
        if s.icao == icao:
            return s.country == "US"
    return False
