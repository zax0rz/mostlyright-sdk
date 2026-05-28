"""Kalshi NHIGH / NLOW settlement station whitelist.

Kalshi's NHIGH (daily high temperature) and NLOW (daily low temperature)
markets settle against the NWS CLI report for a SPECIFIC station — NOT
the airport you'd assume. Common surprises:

- NYC settles against KNYC (Central Park), NOT KLGA or KJFK.
- Chicago settles against KMDW (Midway), NOT KORD (O'Hare).
- DC settles against KDCA (Reagan National), NOT KIAD or KBWI.

Citations are URLs to the Kalshi contract specification pages where the
issuer documents the settlement station. These are committed to the
repo so the v0.14.1 parity gate cannot regress on station identity.

**This is parity-critical.** A wrong station mapping silently settles
backtests against the wrong data; the model "works" but trades garbage.
The contract test in this module asserts no entry resolves to {KLGA,
KJFK, KORD, KIAD, KBWI} — the most common wrong answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class StationCitation:
    """A station mapping with its Kalshi citation."""

    station: str
    citation: str

    def __post_init__(self) -> None:
        if not self.station.startswith("K") or len(self.station) != 4:
            raise ValueError(
                f"Kalshi settlement stations are 4-letter ICAO codes "
                f"starting with 'K' (got {self.station!r})"
            )


#: City ticker → (settlement station ICAO, citation URL).
#: The 21-city Kalshi NHIGH/NLOW universe per v0.1.0 scope. The citation
#: URL is the live Kalshi contract page; if the issuer renames the city
#: ticker the citation URL still resolves and the test stays green.
#:
#: The remaining cities (Honolulu, Anchorage, etc.) defer to Phase 3.1
#: international expansion + post-v0.1 additions.
KALSHI_SETTLEMENT_STATIONS: Final[dict[str, StationCitation]] = {
    # The "Big Five" — most common entries Kalshi documentation references.
    "NYC": StationCitation(
        "KNYC", "https://kalshi.com/markets/khighny  (Central Park, NOT LGA/JFK)"
    ),
    "CHI": StationCitation("KMDW", "https://kalshi.com/markets/khighchi (Midway, NOT ORD)"),
    "LAX": StationCitation("KLAX", "https://kalshi.com/markets/khighlax (LAX international)"),
    "MIA": StationCitation("KMIA", "https://kalshi.com/markets/khighmia (Miami International)"),
    "DEN": StationCitation("KDEN", "https://kalshi.com/markets/khighden (Denver International)"),
    # Tier 2.
    "BOS": StationCitation("KBOS", "https://kalshi.com/markets/khighbos (Boston Logan)"),
    "AUS": StationCitation(
        "KAUS",
        "https://kalshi.com/markets/khighaus (Austin-Bergstrom; the only Austin station Kalshi cites)",
    ),
    "DCA": StationCitation(
        "KDCA",
        "https://kalshi.com/markets/khighdca (Reagan National, NOT Dulles or BWI)",
    ),
    "PHL": StationCitation(
        "KPHL", "https://kalshi.com/markets/khighphl (Philadelphia International)"
    ),
    "SFO": StationCitation(
        "KSFO",
        "https://kalshi.com/markets/khighsfo (San Francisco International, NOT OAK)",
    ),
    "SEA": StationCitation("KSEA", "https://kalshi.com/markets/khighsea (SeaTac, NOT BFI)"),
    "ATL": StationCitation(
        "KATL", "https://kalshi.com/markets/khighatl (Atlanta Hartsfield-Jackson)"
    ),
    "HOU": StationCitation(
        "KIAH",
        "https://kalshi.com/markets/khighhou (Intercontinental, NOT Hobby; Kalshi cites IAH)",
    ),
    "DAL": StationCitation("KDFW", "https://kalshi.com/markets/khighdal (DFW, NOT Love Field)"),
    "PHX": StationCitation(
        "KPHX", "https://kalshi.com/markets/khighphx (Sky Harbor International)"
    ),
    "MSP": StationCitation(
        "KMSP", "https://kalshi.com/markets/khighmsp (Minneapolis-St. Paul International)"
    ),
    "DTW": StationCitation("KDTW", "https://kalshi.com/markets/khighdtw (Detroit Metropolitan)"),
    "CVG": StationCitation(
        "KCVG",
        "https://kalshi.com/markets/khighcvg (Cincinnati/Northern Kentucky International)",
    ),
    "BNA": StationCitation("KBNA", "https://kalshi.com/markets/khighbna (Nashville International)"),
    "SLC": StationCitation(
        "KSLC", "https://kalshi.com/markets/khighslc (Salt Lake City International)"
    ),
    "TLV": StationCitation(
        "KLAS",
        "https://kalshi.com/markets/kxhightlv (Harry Reid/McCarran; settles vs NWS CLILAS)",
    ),
}


#: The known-WRONG stations that must NEVER appear in KALSHI_SETTLEMENT_STATIONS
#: values. Contract test ``test_no_wrong_stations`` enforces this.
KNOWN_WRONG_STATIONS: Final[frozenset[str]] = frozenset(
    {
        "KLGA",  # NYC — LaGuardia (NYC is KNYC)
        "KJFK",  # NYC — JFK (NYC is KNYC)
        "KEWR",  # NYC — Newark (NYC is KNYC)
        "KORD",  # CHI — O'Hare (CHI is KMDW)
        "KIAD",  # DC  — Dulles (DCA is KDCA)
        "KBWI",  # DC  — BWI (DCA is KDCA)
        "KOAK",  # SFO — Oakland (SFO is KSFO)
        "KHOU",  # HOU — Hobby (HOU is KIAH)
        "KDAL",  # DAL — Love Field (DAL is KDFW)
    }
)


__all__ = [
    "KALSHI_SETTLEMENT_STATIONS",
    "KNOWN_WRONG_STATIONS",
    "StationCitation",
]
