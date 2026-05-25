"""Tests for ``mostlyright._internal._pairs`` - the pairs() row builder.

Lifted from monorepo-v0.14.1/tests/test_sdk_pairs.py (lines 1-614), strictly
the pure-function test classes:

- ``TestMarketCloseUtc``
- ``TestObsAggregates``
- ``TestSelectBestRun``
- ``TestAggregateFcstTempsIem``
- ``TestAggregateFcstTempsOpenmeteo``
- ``TestBuildPairsRow``
- ``TestBuildPairs``
- ``TestFcstKeysAlwaysPresent``
- ``TestPairsTzOverride``

The hosted-API tests (``TestPairsIncludeForecastWiring`` - lines 624-774)
are intentionally NOT lifted; they exercise ``MostlyRightClient.pairs(...)``,
which does not exist in mostlyright (the local-first SDK replaces the hosted
join with :func:`mostlyright.research.research`).

Modifications:
- ``from mostlyright.pairs import ...`` -> ``from mostlyright._internal._pairs import ...``
- Otherwise byte-faithful to v0.14.1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from mostlyright._internal._pairs import (
    _aggregate_fcst_temps_iem,
    _aggregate_fcst_temps_openmeteo,
    _obs_aggregates,
    _select_best_run,
    build_pairs,
    build_pairs_row,
    market_close_utc,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obs(
    temp_f: float | None = 75.0, wind_kt: int | None = 10, precip: float | None = None
) -> dict:
    return {
        "temp_f": temp_f,
        "dewpoint_f": 60.0 if temp_f else None,
        "wind_speed_kt": wind_kt,
        "wind_gust_kt": None,
        "precip_1hr_inches": precip,
    }


def _climate(high: float = 85.0, low: float = 65.0, report_type: str = "final") -> dict:
    return {
        "observation_date": "2024-07-04",
        "high_temp_f": high,
        "low_temp_f": low,
        "report_type": report_type,
    }


def _iem_record(
    issued_at: str,
    valid_at: str,
    temperature_f: float = 83.0,
    model: str = "GFS",
    pop_6hr_pct: float | None = None,
    qpf_6hr_in: float | None = None,
) -> dict:
    """IEM MOS hourly forecast record matching specs/forecast.json."""
    return {
        "issued_at": issued_at,
        "valid_at": valid_at,
        "temperature_f": temperature_f,
        "model": model,
        "pop_6hr_pct": pop_6hr_pct,
        "qpf_6hr_in": qpf_6hr_in,
    }


def _om_record(
    valid_at: str,
    temperature_c: float = 28.0,
    model: str = "open-meteo-gfs",
    precipitation_probability_pct: float | None = None,
) -> dict:
    """Open-Meteo hourly forecast record matching specs/forecast_series.json."""
    return {
        "valid_at": valid_at,
        "temperature_c": temperature_c,
        "model": model,
        "precipitation_probability_pct": precipitation_probability_pct,
        # No issued_at - this distinguishes Open-Meteo from IEM MOS
    }


# ---------------------------------------------------------------------------
# market_close_utc
# ---------------------------------------------------------------------------


class TestMarketCloseUtc:
    def test_nyc_standard_offset(self) -> None:
        # 4:30 PM EST = 21:30 UTC
        result = market_close_utc("2024-07-04", "NYC")
        assert result == datetime(2024, 7, 4, 21, 30, tzinfo=UTC)

    def test_chicago_central_offset(self) -> None:
        # 4:30 PM CST = 22:30 UTC
        result = market_close_utc("2024-07-04", "ORD")
        assert result == datetime(2024, 7, 4, 22, 30, tzinfo=UTC)

    def test_dst_ignored(self) -> None:
        # During EDT (summer), LST is still EST (UTC-5) -> same UTC result
        summer = market_close_utc("2024-07-04", "NYC")
        winter = market_close_utc("2024-01-04", "NYC")
        assert summer == datetime(2024, 7, 4, 21, 30, tzinfo=UTC)
        assert winter == datetime(2024, 1, 4, 21, 30, tzinfo=UTC)


# ---------------------------------------------------------------------------
# _obs_aggregates
# ---------------------------------------------------------------------------


class TestObsAggregates:
    def test_empty_list(self) -> None:
        result = _obs_aggregates([])
        assert result["obs_count"] == 0
        assert result["obs_high_f"] is None
        assert result["obs_low_f"] is None

    def test_single_obs(self) -> None:
        result = _obs_aggregates([_obs(temp_f=75.0)])
        assert result["obs_high_f"] == 75.0
        assert result["obs_low_f"] == 75.0
        assert result["obs_mean_f"] == 75.0
        assert result["obs_count"] == 1

    def test_high_low_from_multiple(self) -> None:
        result = _obs_aggregates([_obs(70.0), _obs(80.0), _obs(75.0)])
        assert result["obs_high_f"] == 80.0
        assert result["obs_low_f"] == 70.0

    def test_precip_sum(self) -> None:
        result = _obs_aggregates([_obs(precip=0.1), _obs(precip=0.2), _obs(precip=None)])
        assert result["obs_total_precip_in"] == pytest.approx(0.3)

    def test_no_precip_none_when_all_missing(self) -> None:
        result = _obs_aggregates([_obs(precip=None), _obs(precip=None)])
        assert result["obs_total_precip_in"] is None

    def test_null_temps_skipped(self) -> None:
        result = _obs_aggregates([_obs(temp_f=None), _obs(temp_f=75.0)])
        assert result["obs_high_f"] == 75.0
        assert result["obs_count"] == 2


# ---------------------------------------------------------------------------
# _select_best_run
# ---------------------------------------------------------------------------


class TestSelectBestRun:
    def test_returns_none_if_no_records(self) -> None:
        cutoff = datetime(2024, 7, 4, 21, 30, tzinfo=UTC)
        issued, records = _select_best_run([], cutoff)
        assert issued is None
        assert records == []

    def test_returns_none_if_all_after_cutoff(self) -> None:
        cutoff = datetime(2024, 7, 4, 21, 30, tzinfo=UTC)
        recs = [
            _iem_record("2024-07-04T22:00:00Z", "2024-07-04T23:00:00Z"),
        ]
        issued, records = _select_best_run(recs, cutoff)
        assert issued is None
        assert records == []

    def test_picks_latest_run_before_cutoff(self) -> None:
        cutoff = datetime(2024, 7, 4, 21, 30, tzinfo=UTC)
        recs = [
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T15:00:00Z", model="GFS"),
            _iem_record("2024-07-04T18:00:00Z", "2024-07-04T21:00:00Z", model="NBM"),
            _iem_record("2024-07-04T22:00:00Z", "2024-07-05T01:00:00Z", model="HRRR"),
        ]
        issued, records = _select_best_run(recs, cutoff)
        assert issued == "2024-07-04T18:00:00Z"
        assert len(records) == 1
        assert records[0]["model"] == "NBM"

    def test_returns_all_records_of_best_run(self) -> None:
        cutoff = datetime(2024, 7, 4, 21, 30, tzinfo=UTC)
        recs = [
            _iem_record("2024-07-04T18:00:00Z", "2024-07-04T18:00:00Z", temperature_f=80.0),
            _iem_record("2024-07-04T18:00:00Z", "2024-07-04T19:00:00Z", temperature_f=81.0),
            _iem_record("2024-07-04T18:00:00Z", "2024-07-04T20:00:00Z", temperature_f=82.0),
        ]
        issued, records = _select_best_run(recs, cutoff)
        assert issued == "2024-07-04T18:00:00Z"
        assert len(records) == 3

    def test_exactly_at_cutoff_included(self) -> None:
        cutoff = datetime(2024, 7, 4, 21, 30, tzinfo=UTC)
        recs = [_iem_record("2024-07-04T21:30:00Z", "2024-07-04T22:00:00Z")]
        issued, records = _select_best_run(recs, cutoff)
        assert issued == "2024-07-04T21:30:00Z"
        assert len(records) == 1


# ---------------------------------------------------------------------------
# _aggregate_fcst_temps_iem
# ---------------------------------------------------------------------------


class TestAggregateFcstTempsIem:
    # NYC settlement window for Jul 4: 2024-07-04T05:00:00Z to 2024-07-05T05:00:00Z
    WIN_START = "2024-07-04T05:00:00Z"
    WIN_END = "2024-07-05T05:00:00Z"

    def test_basic_max_min(self) -> None:
        records = [
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T08:00:00Z", temperature_f=75.0),
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T14:00:00Z", temperature_f=89.0),
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T20:00:00Z", temperature_f=85.0),
        ]
        high, low = _aggregate_fcst_temps_iem(records, self.WIN_START, self.WIN_END)
        assert high == 89.0
        assert low == 75.0

    def test_excludes_records_outside_window(self) -> None:
        records = [
            _iem_record(
                "2024-07-04T12:00:00Z", "2024-07-04T03:00:00Z", temperature_f=60.0
            ),  # before window
            _iem_record(
                "2024-07-04T12:00:00Z", "2024-07-04T14:00:00Z", temperature_f=89.0
            ),  # in window
            _iem_record(
                "2024-07-04T12:00:00Z", "2024-07-05T06:00:00Z", temperature_f=99.0
            ),  # after window
        ]
        high, low = _aggregate_fcst_temps_iem(records, self.WIN_START, self.WIN_END)
        assert high == 89.0
        assert low == 89.0

    def test_returns_none_if_no_records_in_window(self) -> None:
        records = [
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T03:00:00Z", temperature_f=60.0),
        ]
        high, low = _aggregate_fcst_temps_iem(records, self.WIN_START, self.WIN_END)
        assert high is None
        assert low is None

    def test_skips_none_temperatures(self) -> None:
        records = [
            {
                "issued_at": "2024-07-04T12:00:00Z",
                "valid_at": "2024-07-04T14:00:00Z",
                "temperature_f": None,
                "model": "GFS",
            },
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T15:00:00Z", temperature_f=85.0),
        ]
        high, low = _aggregate_fcst_temps_iem(records, self.WIN_START, self.WIN_END)
        assert high == 85.0
        assert low == 85.0


# ---------------------------------------------------------------------------
# _aggregate_fcst_temps_openmeteo
# ---------------------------------------------------------------------------


class TestAggregateFcstTempsOpenmeteo:
    WIN_START = "2024-07-04T05:00:00Z"
    WIN_END = "2024-07-05T05:00:00Z"

    def test_converts_celsius_to_fahrenheit(self) -> None:
        # 0C = 32F, 100C = 212F
        records = [
            _om_record("2024-07-04T08:00:00Z", temperature_c=0.0),
            _om_record("2024-07-04T14:00:00Z", temperature_c=100.0),
        ]
        high, low = _aggregate_fcst_temps_openmeteo(records, self.WIN_START, self.WIN_END)
        assert high == pytest.approx(212.0)
        assert low == pytest.approx(32.0)

    def test_basic_max_min(self) -> None:
        records = [
            _om_record("2024-07-04T08:00:00Z", temperature_c=20.0),  # 68F
            _om_record("2024-07-04T14:00:00Z", temperature_c=32.0),  # 89.6F
            _om_record("2024-07-04T20:00:00Z", temperature_c=28.0),  # 82.4F
        ]
        high, low = _aggregate_fcst_temps_openmeteo(records, self.WIN_START, self.WIN_END)
        assert high == pytest.approx(89.6)
        assert low == pytest.approx(68.0)

    def test_excludes_records_outside_window(self) -> None:
        records = [
            _om_record("2024-07-04T03:00:00Z", temperature_c=10.0),  # before
            _om_record("2024-07-04T14:00:00Z", temperature_c=32.0),  # in
            _om_record("2024-07-05T06:00:00Z", temperature_c=99.0),  # after
        ]
        high, low = _aggregate_fcst_temps_openmeteo(records, self.WIN_START, self.WIN_END)
        assert high == pytest.approx(89.6)
        assert low == pytest.approx(89.6)

    def test_returns_none_if_no_records_in_window(self) -> None:
        records = [_om_record("2024-07-04T03:00:00Z", temperature_c=10.0)]
        high, low = _aggregate_fcst_temps_openmeteo(records, self.WIN_START, self.WIN_END)
        assert high is None
        assert low is None


# ---------------------------------------------------------------------------
# build_pairs_row
# ---------------------------------------------------------------------------


class TestBuildPairsRow:
    def test_basic_structure(self) -> None:
        row = build_pairs_row(
            date_str="2024-07-04",
            station="NYC",
            observations=[_obs(75.0)],
            climate=_climate(85.0, 65.0),
            forecasts=None,
        )
        assert row["date"] == "2024-07-04"
        assert row["station"] == "NYC"
        assert row["cli_high_f"] == 85.0
        assert row["cli_low_f"] == 65.0
        assert row["cli_report_type"] == "final"
        assert row["obs_high_f"] == 75.0
        assert row["obs_count"] == 1

    def test_no_climate(self) -> None:
        row = build_pairs_row("2024-07-04", "NYC", [], None, None)
        assert row["cli_high_f"] is None
        assert row["cli_low_f"] is None

    def test_non_dict_climate_treated_as_none(self) -> None:
        # Intentionally pass a non-dict to exercise the defensive guard -
        # the type checker sees this as invalid and correctly flags it.
        row = build_pairs_row(
            "2024-07-04",
            "NYC",
            [],
            "not_a_dict",  # type: ignore[arg-type]  # guarding against runtime misuse
            None,
        )
        assert row["cli_high_f"] is None
        assert row["cli_low_f"] is None

    def test_with_iem_forecast_uses_hourly_aggregation(self) -> None:
        # NYC window Jul 4: 05:00Z-29:00Z. Records at 08:00Z and 14:00Z are in window.
        records = [
            _iem_record(
                "2024-07-04T12:00:00Z",
                "2024-07-04T08:00:00Z",
                temperature_f=75.0,
                model="GFS",
            ),
            _iem_record(
                "2024-07-04T12:00:00Z",
                "2024-07-04T14:00:00Z",
                temperature_f=89.0,
                model="GFS",
            ),
        ]
        row = build_pairs_row("2024-07-04", "NYC", [], None, records)
        assert row["fcst_high_f"] == 89.0
        assert row["fcst_low_f"] == 75.0
        assert row["fcst_model"] == "GFS"

    def test_with_open_meteo_forecast_aggregates_temperature_c(self) -> None:
        records = [
            _om_record("2024-07-04T08:00:00Z", temperature_c=20.0),  # 68F
            _om_record("2024-07-04T14:00:00Z", temperature_c=32.0),  # 89.6F
        ]
        row = build_pairs_row("2024-07-04", "NYC", [], None, records)
        assert row["fcst_high_f"] == pytest.approx(89.6)
        assert row["fcst_low_f"] == pytest.approx(68.0)
        assert row["fcst_model"] == "open-meteo-gfs"

    def test_iem_preferred_over_open_meteo(self) -> None:
        """IEM MOS result takes precedence; Open-Meteo only used as fallback."""
        iem = [
            _iem_record(
                "2024-07-04T12:00:00Z",
                "2024-07-04T14:00:00Z",
                temperature_f=89.0,
                model="GFS",
            )
        ]
        om = [_om_record("2024-07-04T14:00:00Z", temperature_c=99.0)]  # very hot - should not win
        row = build_pairs_row("2024-07-04", "NYC", [], None, iem + om)
        assert row["fcst_high_f"] == 89.0
        assert row["fcst_model"] == "GFS"

    def test_open_meteo_fallback_when_iem_yields_no_window_data(self) -> None:
        """If IEM MOS run has no valid_at records in the settlement window, fall back."""
        # IEM record valid_at is outside the window (03:00Z is before 05:00Z window start)
        iem = [_iem_record("2024-07-04T12:00:00Z", "2024-07-04T03:00:00Z", temperature_f=999.0)]
        om = [_om_record("2024-07-04T14:00:00Z", temperature_c=30.0)]  # 86F
        row = build_pairs_row("2024-07-04", "NYC", [], None, iem + om)
        assert row["fcst_high_f"] == pytest.approx(86.0)
        assert row["fcst_model"] == "open-meteo-gfs"

    def test_fcst_pop_6hr_pct_from_iem(self) -> None:
        records = [
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T08:00:00Z", pop_6hr_pct=20.0),
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T14:00:00Z", pop_6hr_pct=60.0),
        ]
        row = build_pairs_row("2024-07-04", "NYC", [], None, records)
        assert row["fcst_pop_6hr_pct"] == 60.0  # max

    def test_fcst_qpf_6hr_in_sum(self) -> None:
        records = [
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T08:00:00Z", qpf_6hr_in=0.1),
            _iem_record("2024-07-04T12:00:00Z", "2024-07-04T14:00:00Z", qpf_6hr_in=0.2),
        ]
        row = build_pairs_row("2024-07-04", "NYC", [], None, records)
        assert row["fcst_qpf_6hr_in"] == pytest.approx(0.3)

    def test_forecast_none_when_unavailable(self) -> None:
        row = build_pairs_row("2024-07-04", "NYC", [], None, None)
        # When forecasts=None, fcst_* keys are present with None values
        assert "fcst_high_f" in row
        assert row["fcst_high_f"] is None

    def test_market_close_utc_present(self) -> None:
        row = build_pairs_row("2024-07-04", "NYC", [], None, None)
        assert row["market_close_utc"] == "2024-07-04T21:30:00Z"

    def test_k_prefix_station_normalized(self) -> None:
        row = build_pairs_row("2024-07-04", "KNYC", [], None, None)
        assert row["station"] == "NYC"

    def test_selects_best_run_before_market_close(self) -> None:
        """Only the model run issued before 4:30 PM LST is used."""
        records = [
            _iem_record(
                "2024-07-04T12:00:00Z",
                "2024-07-04T14:00:00Z",
                temperature_f=83.0,
                model="GFS",
            ),
            # After market close (21:30Z = 4:30 PM EST)
            _iem_record(
                "2024-07-04T22:00:00Z",
                "2024-07-04T23:00:00Z",
                temperature_f=99.0,
                model="HRRR",
            ),
        ]
        row = build_pairs_row("2024-07-04", "NYC", [], None, records)
        assert row["fcst_high_f"] == 83.0
        assert row["fcst_model"] == "GFS"


# ---------------------------------------------------------------------------
# build_pairs
# ---------------------------------------------------------------------------


class TestBuildPairs:
    def test_empty_dates(self) -> None:
        rows = build_pairs("NYC", [], {}, {})
        assert rows == []

    def test_multiple_dates(self) -> None:
        dates = ["2024-07-04", "2024-07-05"]
        obs_by_date = {
            "2024-07-04": [_obs(75.0)],
            "2024-07-05": [_obs(80.0)],
        }
        # Annotate to match build_pairs' climate_by_date value type
        # (dict invariance - literal inference gives dict[str, dict[_,_]]
        # which is not assignable to dict[str, dict[str, Any] | None]).
        climate_by_date: dict[str, dict[str, Any] | None] = {
            "2024-07-04": _climate(85.0, 65.0),
            "2024-07-05": _climate(90.0, 70.0),
        }
        rows = build_pairs("NYC", dates, obs_by_date, climate_by_date)
        assert len(rows) == 2
        assert rows[0]["date"] == "2024-07-04"
        assert rows[1]["date"] == "2024-07-05"
        assert rows[0]["cli_high_f"] == 85.0
        assert rows[1]["cli_high_f"] == 90.0

    def test_missing_date_uses_empty(self) -> None:
        rows = build_pairs("NYC", ["2024-07-04"], {}, {})
        assert len(rows) == 1
        assert rows[0]["obs_count"] == 0
        assert rows[0]["cli_high_f"] is None

    def test_to_dataframe(self) -> None:
        pytest.importorskip("pandas")
        import pandas as pd

        dates = ["2024-07-04", "2024-07-05"]
        rows = build_pairs("NYC", dates, {}, {})
        df = pd.DataFrame(rows).set_index("date")
        assert "cli_high_f" in df.columns
        assert "obs_high_f" in df.columns
        assert len(df) == 2


# ---------------------------------------------------------------------------
# Blocker fixes: fcst_* keys always present; tz_override on pairs
# ---------------------------------------------------------------------------

_FCST_KEYS = frozenset(
    {
        "fcst_high_f",
        "fcst_low_f",
        "fcst_model",
        "fcst_issued_at",
        "fcst_pop_6hr_pct",
        "fcst_qpf_6hr_in",
    }
)


class TestFcstKeysAlwaysPresent:
    """pairs rows must always contain all fcst_* keys, even as None."""

    def test_no_forecast_data_keys_present(self) -> None:
        """forecasts=None -> all fcst_* keys present with None values."""
        row = build_pairs_row("2024-07-04", "NYC", [], None, None)
        assert set(row) >= _FCST_KEYS, f"Missing keys: {_FCST_KEYS - set(row)}"

    def test_no_forecast_data_all_none(self) -> None:
        row = build_pairs_row("2024-07-04", "NYC", [], None, None)
        for key in _FCST_KEYS:
            assert row[key] is None, f"Expected None for {key}, got {row[key]!r}"

    def test_empty_forecast_list_keys_present(self) -> None:
        """forecasts=[] (empty list) -> all fcst_* keys still present."""
        row = build_pairs_row("2024-07-04", "NYC", [], None, [])
        assert set(row) >= _FCST_KEYS, f"Missing keys: {_FCST_KEYS - set(row)}"

    def test_with_forecast_data_keys_present(self) -> None:
        """Even when forecast data yields values, all six keys must be present."""
        iem = [
            {
                "issued_at": "2024-07-04T12:00:00Z",
                "valid_at": "2024-07-04T18:00:00Z",
                "temperature_f": 90.0,
                "model": "GFS",
                "pop_6hr_pct": None,
                "qpf_6hr_in": None,
            }
        ]
        row = build_pairs_row("2024-07-04", "NYC", [], None, iem)
        assert set(row) >= _FCST_KEYS, f"Missing keys: {_FCST_KEYS - set(row)}"

    def test_build_pairs_rows_all_have_fcst_keys(self) -> None:
        """build_pairs() output: every row has all fcst_* keys."""
        dates = ["2024-07-04", "2024-07-05", "2024-07-06"]
        rows = build_pairs("NYC", dates, {}, {}, forecasts_by_date=None)
        for row in rows:
            assert set(row) >= _FCST_KEYS, f"Row {row['date']} missing: {_FCST_KEYS - set(row)}"


class TestPairsTzOverride:
    """tz_override passes through to settlement_window_utc."""

    def test_tz_override_accepted_no_error(self) -> None:
        """tz_override does not raise for a known station (override ignored when station known)."""
        row = build_pairs_row("2024-07-04", "NYC", [], None, None, tz_override="America/New_York")
        assert row["date"] == "2024-07-04"

    def test_tz_override_build_pairs(self) -> None:
        rows = build_pairs("NYC", ["2024-07-04"], {}, {}, tz_override="America/New_York")
        assert len(rows) == 1
        assert set(rows[0]) >= _FCST_KEYS


class TestMarketCloseUtcTzOverride:
    """Iter-6 F1 fix: ``market_close_utc`` must thread ``tz_override``.

    v0.14.1's ``pairs.py`` silently dropped the override in this call,
    causing two bugs:
    1. Unknown stations + override crashed inside ``_lst_offset(station)``.
    2. Known stations with an override used a different LST cutoff than
       ``settlement_window_utc``, yielding inconsistent forecast-window
       boundaries.

    Parity impact: zero - all 5 Phase 1 fixtures use registry stations
    with ``tz_override=None``, so the change is a no-op for the gate.
    """

    def test_unknown_station_with_override_does_not_crash(self) -> None:
        """A station not in the registry plus a tz_override must succeed."""
        # 'ABC' is not in _STATION_TZ; without the fix this raises ValueError.
        result = market_close_utc("2024-07-04", "ABC", tz_override="America/New_York")
        assert result == datetime(2024, 7, 4, 21, 30, tzinfo=UTC)

    def test_known_station_override_changes_offset(self) -> None:
        """A registry station passed with a different override uses the override.

        NYC defaults to America/New_York (UTC-5 LST → 21:30 UTC close).
        Override to America/Chicago (UTC-6 LST → 22:30 UTC close).
        """
        default_close = market_close_utc("2024-07-04", "NYC")
        override_close = market_close_utc("2024-07-04", "NYC", tz_override="America/Chicago")
        assert default_close == datetime(2024, 7, 4, 21, 30, tzinfo=UTC)
        assert override_close == datetime(2024, 7, 4, 22, 30, tzinfo=UTC)

    def test_build_pairs_row_threads_override_to_market_close(self) -> None:
        """``build_pairs_row`` propagates ``tz_override`` to ``market_close_utc``."""
        row = build_pairs_row(
            "2024-07-04",
            "NYC",
            [],
            None,
            None,
            tz_override="America/Chicago",
        )
        # 4:30 PM CST = 22:30 UTC (not 21:30 UTC that NYC default would produce).
        assert row["market_close_utc"] == "2024-07-04T22:30:00Z"

    def test_build_pairs_row_unknown_station_with_override(self) -> None:
        """A station outside the registry now works end-to-end with override."""
        row = build_pairs_row(
            "2024-07-04",
            "ABC",
            [],
            None,
            None,
            tz_override="America/New_York",
        )
        assert row["station"] == "ABC"
        assert row["market_close_utc"] == "2024-07-04T21:30:00Z"
