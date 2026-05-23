"""Phase 3.1 — International station expansion + daily_extremes rollup.

Phase 3.1 v0.1.0 scope: expand the v0.14.1 20-US station registry to 60
(20 US + 40 international ICAOs), add the per-event station resolver for
multi-airport cities (Paris LFPG/LFPB split), add ``daily_extremes()``
rollup with station-local IANA calendar day semantics, and surface
whole-°C source-precision for international stations.

The full STATIONS dict lives in ``_internal/_stations.py``; this module
exposes the public extension surface — ``daily_extremes(df, station_tz)``
+ ``DeferredMarketError`` for sources we can't ship until v0.2 (Taipei
CWA, HK HKO).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tradewinds.core.exceptions import TradewindsError

if TYPE_CHECKING:
    import pandas as pd


__all__ = [
    "DeferredMarketError",
    "INTERNATIONAL_STATIONS",
    "daily_extremes",
]


class DeferredMarketError(TradewindsError):
    """A market resolves to a station whose data source is deferred to v0.2.

    Currently raised for Taipei (CWA client) and Hong Kong-lowest (HKO
    client). v0.2 will land both clients and remove the deferral.
    """

    default_error_code = "DEFERRED_MARKET"


#: Phase 3.1 international ICAOs — 40 stations covering the markets
#: Polymarket lists as of v0.1.0 scope. Each entry maps the ICAO to its
#: IANA timezone (needed for station-local calendar-day extremes).
INTERNATIONAL_STATIONS: dict[str, str] = {
    # Europe.
    "EGLL": "Europe/London",  # London Heathrow
    "EGKK": "Europe/London",  # London Gatwick
    "LFPG": "Europe/Paris",  # Paris CDG
    "LFPB": "Europe/Paris",  # Paris Le Bourget
    "LFPO": "Europe/Paris",  # Paris Orly
    "EDDF": "Europe/Berlin",  # Frankfurt
    "EDDB": "Europe/Berlin",  # Berlin Brandenburg
    "EDDM": "Europe/Berlin",  # Munich
    "LEMD": "Europe/Madrid",  # Madrid Barajas
    "LEBL": "Europe/Madrid",  # Barcelona El Prat
    "LIRF": "Europe/Rome",  # Rome Fiumicino
    "LIMC": "Europe/Rome",  # Milan Malpensa
    "EHAM": "Europe/Amsterdam",  # Amsterdam Schiphol
    "EKCH": "Europe/Copenhagen",  # Copenhagen
    "ESSA": "Europe/Stockholm",  # Stockholm Arlanda
    "EFHK": "Europe/Helsinki",  # Helsinki
    "LSZH": "Europe/Zurich",  # Zurich
    "LOWW": "Europe/Vienna",  # Vienna
    "EPWA": "Europe/Warsaw",  # Warsaw
    "UUEE": "Europe/Moscow",  # Moscow Sheremetyevo
    # Asia.
    "RJTT": "Asia/Tokyo",  # Tokyo Haneda
    "RJAA": "Asia/Tokyo",  # Tokyo Narita
    "RKSI": "Asia/Seoul",  # Seoul Incheon
    "ZBAA": "Asia/Shanghai",  # Beijing Capital
    "ZSPD": "Asia/Shanghai",  # Shanghai Pudong
    "VHHH": "Asia/Hong_Kong",  # Hong Kong (deferred for HKO data)
    "RCTP": "Asia/Taipei",  # Taipei Taoyuan (deferred for CWA data)
    "WSSS": "Asia/Singapore",  # Singapore Changi
    "VTBS": "Asia/Bangkok",  # Bangkok Suvarnabhumi
    "VABB": "Asia/Kolkata",  # Mumbai
    "VIDP": "Asia/Kolkata",  # Delhi
    "OMDB": "Asia/Dubai",  # Dubai
    "OERK": "Asia/Riyadh",  # Riyadh
    "OTHH": "Asia/Qatar",  # Doha Hamad
    # Oceania.
    "YSSY": "Australia/Sydney",  # Sydney
    "YMML": "Australia/Melbourne",  # Melbourne
    "YBBN": "Australia/Brisbane",  # Brisbane
    "NZAA": "Pacific/Auckland",  # Auckland
    "NZWN": "Pacific/Auckland",  # Wellington
    # Americas (non-US).
    "SBGR": "America/Sao_Paulo",  # São Paulo Guarulhos
    "SAEZ": "America/Argentina/Buenos_Aires",  # Buenos Aires Ezeiza
}


#: Markets routed to stations whose data source is deferred to v0.2.
DEFERRED_STATIONS: frozenset[str] = frozenset({"VHHH", "RCTP"})


def daily_extremes(
    df: pd.DataFrame,
    *,
    station_tz: str,
) -> pd.DataFrame:
    """Roll up observations to station-local calendar-day temperature extremes.

    Args:
        df: DataFrame with at least ``event_time`` (tz-aware UTC) and
            ``temp_c`` / ``temp_f`` columns.
        station_tz: IANA timezone name (e.g. ``"Asia/Tokyo"``).

    Returns:
        DataFrame with one row per local calendar day, columns
        ``local_date``, ``temp_max_c``, ``temp_min_c``, ``temp_max_f``,
        ``temp_min_f`` (whole-°C precision per the international source
        contract — round half-up to match issuer reporting).
    """
    from zoneinfo import ZoneInfo

    import pandas as pd

    if df.empty:
        return pd.DataFrame(
            {
                "local_date": pd.Series([], dtype="object"),
                "temp_max_c": pd.Series([], dtype="float64"),
                "temp_min_c": pd.Series([], dtype="float64"),
                "temp_max_f": pd.Series([], dtype="float64"),
                "temp_min_f": pd.Series([], dtype="float64"),
            }
        )

    if "event_time" not in df.columns:
        raise ValueError("df must contain an 'event_time' column")

    tz = ZoneInfo(station_tz)
    local = df["event_time"].dt.tz_convert(tz)
    df = df.assign(local_date=local.dt.date)
    agg = (
        df.groupby("local_date")
        .agg(
            temp_max_c=("temp_c", "max"),
            temp_min_c=("temp_c", "min"),
        )
        .reset_index()
    )
    # International source convention: whole-°C reporting + matching °F.
    agg["temp_max_c"] = agg["temp_max_c"].round().astype("float64")
    agg["temp_min_c"] = agg["temp_min_c"].round().astype("float64")
    agg["temp_max_f"] = (agg["temp_max_c"] * 9 / 5 + 32).round().astype("float64")
    agg["temp_min_f"] = (agg["temp_min_c"] * 9 / 5 + 32).round().astype("float64")
    return agg
