"""Wave 2 smoke test for :func:`tradewinds.research.research`.

This is the **dtype-and-shape smoke gate** for the Phase 1 Wave 2 orchestrator.
Full byte-equivalent parity against ``mostlyright==0.14.1`` lands in Wave 3
(``tests/test_parity.py``); Wave 2 only proves the local-first pipeline runs
end-to-end against a mocked HTTP layer and produces a DataFrame whose
column set + dtypes match the case-1 parity fixture.

Mock surface (via ``respx``):

- IEM ASOS ``cgi-bin/request/asos.py`` -> minimal METAR-only CSV
- IEM CLI ``json/cli.py`` -> minimal 7-day climate JSON
- NCEI GHCNh ``by-year/.../psv/...`` -> 404 (graceful degrade)
- AWC ``api/data/metar`` -> not invoked (case-1 is historical, outside
  the 168h AWC window)

The fixtures intentionally do NOT mirror real upstream byte sequences -
that is Wave 3's job. Wave 2 cares about: "did the pipeline traverse all
its layers, write to the cache, and emit a DataFrame with the right
schema?"
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq
import pytest

respx = pytest.importorskip("respx")


CASE_1_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "parity"
    / "case_1_KNYC_2025-01-06_2025-01-12.parquet"
)


def _iem_csv_for_month(station_code: str, year: int, month: int) -> str:
    """Return an IEM ASOS comma CSV payload with a handful of valid METAR rows.

    The byte layout matches IEM's actual ``format=comma`` response: comment
    lines starting with ``#`` followed by a header row with ``station,valid,
    tmpf,dwpf,...,metar`` and one row per observation.
    """
    if month == 1:
        days = (6, 7, 8, 9, 10, 11, 12, 13)
        temps = (30.0, 32.0, 35.0, 40.0, 38.0, 33.0, 28.0, 31.0)
    else:
        # Other months are fetched only when the orchestrator extends past
        # to_date. Case-1 stays within January so this branch is unused;
        # return an empty header-only file to keep the fetcher happy.
        return "# IEM mock\nstation,valid,tmpf,dwpf,drct,sknt,gust,p01i,alti,mslp,vsby,skyc1,skyl1,skyc2,skyl2,skyc3,skyl3,skyc4,skyl4,wxcodes,peak_wind_gust,peak_wind_drct,peak_wind_time,snowdepth,metar\n"

    lines = [
        "# IEM mock (Wave 2 smoke fixture)",
        "station,valid,tmpf,dwpf,drct,sknt,gust,p01i,alti,mslp,vsby,skyc1,skyl1,skyc2,skyl2,skyc3,skyl3,skyc4,skyl4,wxcodes,peak_wind_gust,peak_wind_drct,peak_wind_time,snowdepth,metar",
    ]
    for day, temp_f in zip(days, temps, strict=True):
        # Two observations per day (00:51Z and 12:51Z) so obs_count > 1
        # exercises the aggregation path.
        for hour, minute in ((0, 51), (12, 51)):
            valid = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
            metar = (
                f"K{station_code} {day:02d}{hour:02d}{minute:02d}Z 09014G25KT 10SM "
                f"CLR M00/M05 A2968 RMK AO2 SLP049"
            )
            row = [
                station_code,  # station
                valid,  # valid
                f"{temp_f:.2f}",  # tmpf
                f"{temp_f - 8:.2f}",  # dwpf
                "90.00",  # drct
                "14.00",  # sknt
                "25.00",  # gust
                "0.00",  # p01i
                "29.68",  # alti
                "1004.90",  # mslp
                "10.00",  # vsby
                "CLR",  # skyc1
                "M",  # skyl1
                "M",  # skyc2
                "M",  # skyl2
                "M",  # skyc3
                "M",  # skyl3
                "M",  # skyc4
                "M",  # skyl4
                "M",  # wxcodes
                "M",  # peak_wind_gust
                "M",  # peak_wind_drct
                "M",  # peak_wind_time
                "M",  # snowdepth
                metar,  # metar
            ]
            lines.append(",".join(row))
    return "\n".join(lines) + "\n"


def _cli_json_for_year(year: int) -> dict[str, Any]:
    """Return an IEM CLI ``{"results": [...]}`` payload.

    One climate record per day in 2025-01-06 .. 2025-01-12 (the case-1
    window). Includes ``product`` so ``infer_report_type`` picks ``final``,
    which carries the highest ``REPORT_TYPE_PRIORITY`` and survives the
    merge step intact.
    """
    if year != 2025:
        return {"results": []}
    records = []
    for day, high, low in (
        (6, 38, 25),
        (7, 41, 28),
        (8, 44, 30),
        (9, 47, 33),
        (10, 43, 31),
        (11, 39, 27),
        (12, 36, 24),
    ):
        records.append(
            {
                "valid": f"2025-01-{day:02d}",
                "high": high,
                "low": low,
                # "CDUS41 KOKX 130930" -> 09:30 UTC product = "final"
                # (after CLI_PUBLICATION_DELAY threshold).
                "product": f"CDUS41 KOKX {day + 1:02d}0930",
            }
        )
    return {"results": records}


@pytest.fixture
def tmp_cache_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect the tradewinds cache to ``tmp_path`` for the duration of the test."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def mocked_http() -> Any:
    """Yield a respx mock router with the Wave 2 endpoints stubbed.

    - IEM ASOS: any request matching the request URL returns the synthetic CSV
      for the (year, month) parsed from the URL params.
    - IEM CLI: per-year JSON response (404 for years outside the test window).
    - GHCNh: 404 for every request (case-1 doesn't depend on GHCNh).
    - AWC: not invoked - asserted via "any uncovered request raises" in respx.
    """

    def _iem_asos_response(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        station = params.get("station", "")
        year = int(params.get("year1", "2025"))
        month = int(params.get("month1", "1"))
        return httpx.Response(200, text=_iem_csv_for_month(station, year, month))

    def _iem_cli_response(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        year = int(params.get("year", "2025"))
        return httpx.Response(200, json=_cli_json_for_year(year))

    def _ghcnh_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="")

    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=r"mesonet\.agron\.iastate\.edu/cgi-bin/request/asos\.py.*").mock(
            side_effect=_iem_asos_response
        )
        router.get(url__regex=r"mesonet\.agron\.iastate\.edu/json/cli\.py.*").mock(
            side_effect=_iem_cli_response
        )
        router.get(
            url__regex=r"ncei\.noaa\.gov/.*global-historical-climatology-network/hourly.*"
        ).mock(side_effect=_ghcnh_response)
        yield router


class TestResearchSmoke:
    """End-to-end pipeline smoke against respx-mocked HTTP."""

    def test_returns_dataframe_with_correct_shape(
        self, mocked_http: Any, tmp_cache_env: Path
    ) -> None:
        from tradewinds import research

        df = research("KNYC", "2025-01-06", "2025-01-12")

        import pandas as pd

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 7, f"expected 7 settlement days, got {len(df)}"

    def test_columns_match_case_1_fixture(self, mocked_http: Any, tmp_cache_env: Path) -> None:
        from tradewinds import research

        df = research("KNYC", "2025-01-06", "2025-01-12")
        # date is the DataFrame index after pairs_to_dataframe; the fixture
        # stores it as a column. Compare the union to keep the test pinned to
        # column identity and not index-vs-column accident.
        actual_columns = set(df.columns) | {df.index.name}
        fixture_columns = set(pq.read_table(CASE_1_FIXTURE).column_names)
        assert actual_columns == fixture_columns, (
            f"missing: {fixture_columns - actual_columns}, "
            f"extra: {actual_columns - fixture_columns}"
        )

    def test_dtypes_align_with_case_1_fixture(self, mocked_http: Any, tmp_cache_env: Path) -> None:
        """dtype-only smoke. Wave 3 asserts byte values; Wave 2 asserts kinds."""
        from tradewinds import research

        df = research("KNYC", "2025-01-06", "2025-01-12")
        # The fixture's ``date`` column is timestamp[ns]; pairs_to_dataframe
        # promotes it to a DatetimeIndex - check the index kind for parity.
        assert df.index.name == "date"
        import pandas as pd

        assert pd.api.types.is_datetime64_any_dtype(df.index)

        def _is_stringish(series: pd.Series) -> bool:
            return pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)

        # Climate temps in v0.14.1 are int (Fahrenheit, whole degrees).
        assert pd.api.types.is_integer_dtype(df["cli_high_f"])
        assert pd.api.types.is_integer_dtype(df["cli_low_f"])
        # cli_report_type roundtrips as the pandas 2.x ``str`` dtype when
        # loaded from the parity parquet fixture and as object dtype when
        # emitted fresh from ``pairs_to_dataframe``. Both are acceptable for
        # Wave 2's smoke; Wave 3's full parity test resolves the dtype via
        # the fallback ladder documented in PLAN.md Open Q3.
        assert _is_stringish(df["cli_report_type"])
        # Observation aggregates - floats from the IEM Fahrenheit values.
        assert pd.api.types.is_float_dtype(df["obs_high_f"])
        assert pd.api.types.is_float_dtype(df["obs_low_f"])
        assert pd.api.types.is_float_dtype(df["obs_mean_f"])
        # Counts and wind kts are ints.
        assert pd.api.types.is_integer_dtype(df["obs_count"])
        assert pd.api.types.is_integer_dtype(df["obs_max_wind_kt"])
        # Forecast columns are all-None when include_forecast=False (object
        # dtype because pandas typed them via NoneType - matches the parity
        # fixture's null-typed columns).
        for col in (
            "fcst_high_f",
            "fcst_low_f",
            "fcst_model",
            "fcst_issued_at",
            "fcst_pop_6hr_pct",
            "fcst_qpf_6hr_in",
        ):
            assert df[col].isna().all(), f"{col} should be all-None when include_forecast=False"

    def test_first_row_has_observation_and_climate(
        self, mocked_http: Any, tmp_cache_env: Path
    ) -> None:
        from tradewinds import research

        df = research("KNYC", "2025-01-06", "2025-01-12")
        first = df.iloc[0]
        assert first["obs_count"] > 0
        assert first["cli_high_f"] is not None
        assert first["cli_low_f"] is not None
        assert first["station"] == "NYC", "station must be normalized to 3-letter code"

    def test_market_close_utc_is_iso_string(self, mocked_http: Any, tmp_cache_env: Path) -> None:
        from tradewinds import research

        df = research("KNYC", "2025-01-06", "2025-01-12")
        # 4:30 PM EST = 21:30 UTC year-round (DST ignored per v0.14.1).
        assert df["market_close_utc"].iloc[0] == "2025-01-06T21:30:00Z"

    def test_as_dataframe_false_returns_list_of_dicts(
        self, mocked_http: Any, tmp_cache_env: Path
    ) -> None:
        from tradewinds import research

        rows = research("KNYC", "2025-01-06", "2025-01-12", as_dataframe=False)
        assert isinstance(rows, list)
        assert len(rows) == 7
        assert all(isinstance(r, dict) for r in rows)
        # raw rows have date as a key (not a DatetimeIndex)
        assert rows[0]["date"] == "2025-01-06"
        assert rows[0]["station"] == "NYC"

    def test_cache_materialized_after_first_call(
        self, mocked_http: Any, tmp_cache_env: Path
    ) -> None:
        """The orchestrator should write the parquet cache for the fetched month."""
        from tradewinds import research

        research("KNYC", "2025-01-06", "2025-01-12")
        obs_path = tmp_cache_env / "v1" / "observations" / "KNYC" / "2025" / "01.parquet"
        climate_path = tmp_cache_env / "v1" / "climate" / "KNYC" / "2025.parquet"
        # January 2025 is historical from 2026-05-22 (the GSD currentDate),
        # so the LST-month-skip predicate is False and the cache should be
        # materialized. If those preconditions ever shift, this assert will
        # surface it rather than silently passing a stale fixture.
        assert obs_path.exists(), f"expected observation cache at {obs_path}"
        assert climate_path.exists(), f"expected climate cache at {climate_path}"


class TestRegistryCoverage:
    """Regression for codex iter-1 P1.

    The orchestrator must not raise on any station in the 20-entry registry.
    Previously the cache's ``_lst_offset`` fallback only knew 10 stations and
    raised ``ValueError`` for the rest, silently breaking ``research()`` for
    every registry entry outside the hardcoded whitelist (KAUS, KDCA, KDFW,
    KHOU, KLAS, KMDW, KMSP, KOKC, KPHL, KSAT, KSFO). The fix delegates to
    ``tradewinds.snapshot._lst_offset`` (the canonical v0.14.1 map); this
    test asserts the cache layer accepts every advertised station so the
    regression cannot return.

    Uses ``cache_path`` (a cheap operation that exercises the LST-offset path
    transitively via ``validate_icao_for_path``) rather than a full
    ``research()`` call - the goal is to lock in the contract without paying
    for a per-station HTTP mock matrix.
    """

    def test_every_station_resolves_via_cache_layer(self, tmp_cache_env: Path) -> None:
        from tradewinds._internal._stations import STATIONS
        from tradewinds.weather.cache import _lst_offset

        for code, info in STATIONS.items():
            for variant in (code, info.icao):
                # Should NOT raise ValueError for any registry station.
                offset = _lst_offset(variant)
                assert offset is not None, f"_lst_offset returned None for {variant!r}"


class TestIncludeForecastRaises:
    def test_include_forecast_true_raises_not_implemented(self, tmp_cache_env: Path) -> None:
        """Phase 1 is observations + climate only; forecast is Phase 3.2."""
        from tradewinds import research

        with pytest.raises(NotImplementedError, match="include_forecast"):
            research("KNYC", "2025-01-06", "2025-01-12", include_forecast=True)


class TestUnknownStation:
    def test_unknown_station_raises(self, tmp_cache_env: Path) -> None:
        from tradewinds import research

        with pytest.raises(ValueError, match="Unknown station"):
            research("ZZZ", "2025-01-06", "2025-01-12")


# ---------------------------------------------------------------------------
# Pure-function helper tests (no HTTP, no fixtures)
# ---------------------------------------------------------------------------


class TestMonthRange:
    def test_single_month(self) -> None:
        from tradewinds.research import _month_range

        assert _month_range("2025-01-06", "2025-01-12") == [(2025, 1)]

    def test_spans_year_boundary(self) -> None:
        from tradewinds.research import _month_range

        assert _month_range("2024-12-01", "2025-01-15") == [(2024, 12), (2025, 1)]

    def test_multi_month(self) -> None:
        from tradewinds.research import _month_range

        assert _month_range("2025-02-01", "2025-04-30") == [
            (2025, 2),
            (2025, 3),
            (2025, 4),
        ]

    def test_inverted_range_empty(self) -> None:
        from tradewinds.research import _month_range

        assert _month_range("2025-02-01", "2025-01-01") == []


class TestMonthWindow:
    def test_january(self) -> None:
        from datetime import date

        from tradewinds.research import _month_window

        first, last = _month_window(2025, 1)
        assert first == date(2025, 1, 1)
        assert last == date(2025, 1, 31)

    def test_february_non_leap(self) -> None:
        from datetime import date

        from tradewinds.research import _month_window

        first, last = _month_window(2025, 2)
        assert first == date(2025, 2, 1)
        assert last == date(2025, 2, 28)

    def test_february_leap(self) -> None:
        from datetime import date

        from tradewinds.research import _month_window

        first, last = _month_window(2024, 2)
        assert first == date(2024, 2, 1)
        assert last == date(2024, 2, 29)

    def test_december_rolls_to_january_next_year(self) -> None:
        from datetime import date

        from tradewinds.research import _month_window

        first, last = _month_window(2024, 12)
        assert first == date(2024, 12, 1)
        assert last == date(2024, 12, 31)


class TestMonthOverlapsAwcWindow:
    def test_far_historical_month_outside_window(self) -> None:
        from datetime import datetime

        from tradewinds.research import _month_overlaps_awc_window

        now = datetime(2025, 6, 15, tzinfo=UTC)
        assert _month_overlaps_awc_window(2025, 1, now=now) is False

    def test_current_month_inside_window(self) -> None:
        from datetime import datetime

        from tradewinds.research import _month_overlaps_awc_window

        now = datetime(2025, 6, 15, tzinfo=UTC)
        assert _month_overlaps_awc_window(2025, 6, now=now) is True

    def test_previous_month_within_168h(self) -> None:
        from datetime import datetime

        from tradewinds.research import _month_overlaps_awc_window

        # Now is Jun 3 -- 168h ago is May 27, which is in May.
        now = datetime(2025, 6, 3, tzinfo=UTC)
        assert _month_overlaps_awc_window(2025, 5, now=now) is True

    def test_previous_month_outside_168h(self) -> None:
        from datetime import datetime

        from tradewinds.research import _month_overlaps_awc_window

        # Now is Jun 15 -- 168h ago is Jun 8, well into June. May is excluded.
        now = datetime(2025, 6, 15, tzinfo=UTC)
        assert _month_overlaps_awc_window(2025, 5, now=now) is False


class TestResolveStation:
    def test_three_letter_code(self) -> None:
        from tradewinds.research import _resolve_station

        info = _resolve_station("NYC")
        assert info.code == "NYC"
        assert info.icao == "KNYC"

    def test_four_letter_icao_normalized(self) -> None:
        from tradewinds.research import _resolve_station

        info = _resolve_station("KNYC")
        assert info.code == "NYC"
        assert info.icao == "KNYC"

    def test_lowercase_input_normalized(self) -> None:
        from tradewinds.research import _resolve_station

        info = _resolve_station("knyc")
        assert info.code == "NYC"

    def test_unknown_raises(self) -> None:
        from tradewinds.research import _resolve_station

        with pytest.raises(ValueError, match="Unknown station"):
            _resolve_station("ZZZ")
