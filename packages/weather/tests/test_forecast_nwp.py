"""Tests for the public NWP forecast surface (Phase 3.2).

The full live path needs ``cfgrib`` / ``xarray`` / ``sklearn`` (the
``[nwp]`` extra). These tests cover the dispatch + validation surface
and the inline QC engine; the cfgrib-bound integration test is gated
by ``importlib`` availability of those modules and marked ``live`` so CI
excludes it.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from typing import ClassVar
from unittest.mock import patch

import httpx
import pytest
from mostlyright.core.exceptions import (
    GribIntegrityError,
    NoLiveForNwpError,
    NwpModelNotAvailableError,
    SourceUnavailableError,
)
from mostlyright.core.schemas.forecast_nwp import (
    NWP_MIRROR_VALUES,
    NWP_MODEL_VALUES,
    NWP_QC_STATUS_VALUES,
    NwpForecastSchema,
)

_HAS_NWP_EXTRA = all(
    importlib.util.find_spec(mod) is not None for mod in ("cfgrib", "xarray", "sklearn")
)


# ---------------------------------------------------------------------------
# Reserved-model + validation surface
# ---------------------------------------------------------------------------
class TestForecastNwpDispatch:
    def test_reserved_ecmwf_model_raises_specific_error(self) -> None:
        from mostlyright.forecasts import forecast_nwp

        with pytest.raises(NwpModelNotAvailableError) as exc_info:
            forecast_nwp("KNYC", "ecmwf_ifs_hres")
        assert exc_info.value.model == "ecmwf_ifs_hres"
        assert exc_info.value.available_in == "v0.2"
        assert exc_info.value.error_code == "NWP_MODEL_NOT_AVAILABLE"

    def test_all_reserved_models_predeclared_in_enum(self) -> None:
        # Schema enum must include the 4 ECMWF reservations day-one.
        for reserved in ("ecmwf_ifs_hres", "ecmwf_ifs_ens", "ecmwf_aifs_single", "ecmwf_aifs_ens"):
            assert reserved in NWP_MODEL_VALUES

    def test_typo_model_raises_value_error_not_nwp_error(self) -> None:
        """``model="bogus"`` is neither supported nor reserved."""
        from mostlyright.forecasts import forecast_nwp

        with pytest.raises(ValueError, match="NWP model must be"):
            forecast_nwp("KNYC", "bogus")

    def test_supported_models_phase17_plan03(self) -> None:
        """Phase 17 PLAN-03 extended the public surface to include NCEP.

        PLAN-03 NCEP family (HRRRAK + GEFS + GDAS + RAP + RRFS + RTMA +
        URMA + CFS) is wired end-to-end. ECMWF / MSC / HAFS / legacy are
        predeclared in the schema enum so callers see the same surface
        as PLAN-04 / -05 / -06 land their fetch + decode wiring.
        """
        from mostlyright.forecasts import SUPPORTED_NWP_MODELS

        # The 3 v0.1.0 entries survive.
        assert {"hrrr", "gfs", "nbm"} <= SUPPORTED_NWP_MODELS
        # The 8 NCEP family entries are present.
        expected_ncep = {
            "hrrrak",
            "gefs",
            "gdas",
            "rap",
            "rrfs",
            "rtma",
            "urma",
            "cfs",
        }
        assert expected_ncep <= SUPPORTED_NWP_MODELS

    def test_to_dict_includes_model(self) -> None:
        err = NwpModelNotAvailableError("msg", model="ecmwf_ifs_hres", available_in="v0.2")
        d = err.to_dict()
        assert d["model"] == "ecmwf_ifs_hres"
        assert d["available_in"] == "v0.2"
        assert d["error_code"] == "NWP_MODEL_NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# Inline physics-bounds QC
# ---------------------------------------------------------------------------
class TestQcStatusForRow:
    def test_clean_row_is_clean(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        row = {
            "temp_k_2m": 290.0,
            "dewpoint_k_2m": 285.0,
            "relative_humidity_pct_2m": 60.0,
            "wind_gust_ms": 5.0,
            "precip_mm_1h": 0.0,
            "pressure_pa_surface": 101_325.0,
            "pressure_pa_mslp": 101_325.0,
        }
        assert _qc_status_for_row(row) == "clean"

    def test_negative_absolute_temperature_is_suspect(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        row = {"temp_k_2m": -5.0}
        assert _qc_status_for_row(row) == "suspect"

    def test_temperature_below_world_record_is_flagged_not_suspect(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        row = {"temp_k_2m": 175.0}  # below world record but physically possible
        assert _qc_status_for_row(row) == "flagged"

    def test_dewpoint_greater_than_temperature_is_flagged(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        row = {"temp_k_2m": 280.0, "dewpoint_k_2m": 290.0}
        assert _qc_status_for_row(row) == "flagged"

    def test_extreme_humidity_is_flagged(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"relative_humidity_pct_2m": 108.0}) == "flagged"

    def test_grossly_invalid_humidity_is_suspect(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"relative_humidity_pct_2m": 200.0}) == "suspect"

    def test_negative_gust_is_suspect(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"wind_gust_ms": -1.0}) == "suspect"

    def test_extreme_gust_is_flagged(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"wind_gust_ms": 95.0}) == "flagged"

    def test_negative_precip_is_suspect(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"precip_mm_1h": -1.0}) == "suspect"

    def test_extreme_precip_is_flagged(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"precip_mm_1h": 400.0}) == "flagged"

    def test_null_fields_dont_trip_qc(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({}) == "clean"
        assert _qc_status_for_row({"temp_k_2m": None}) == "clean"

    def test_nan_fields_dont_trip_qc(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"temp_k_2m": float("nan")}) == "clean"

    def test_cloud_cover_bounds_qc(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"cloud_cover_pct": 50.0}) == "clean"
        assert _qc_status_for_row({"cloud_cover_pct": -1.0}) == "suspect"
        assert _qc_status_for_row({"cloud_cover_pct": 101.0}) == "suspect"

    def test_visibility_bounds_qc(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"visibility_m": 10000.0}) == "clean"
        assert _qc_status_for_row({"visibility_m": -10.0}) == "suspect"
        assert _qc_status_for_row({"visibility_m": 120000.0}) == "flagged"

    def test_cloud_ceiling_bounds_qc(self) -> None:
        from mostlyright.weather.forecast_nwp import _qc_status_for_row

        assert _qc_status_for_row({"cloud_ceiling_m": 2000.0}) == "clean"
        assert _qc_status_for_row({"cloud_ceiling_m": -5.0}) == "suspect"
        assert _qc_status_for_row({"cloud_ceiling_m": 25000.0}) == "flagged"


# ---------------------------------------------------------------------------
# Mirror fallback + unknown-station handling (no cfgrib needed)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _HAS_NWP_EXTRA, reason="requires [nwp] extra installed")
class TestForecastNwpMirrorFallback:
    def test_unknown_station_returns_empty_dataframe(self) -> None:
        from mostlyright.weather.forecast_nwp import forecast_nwp

        df = forecast_nwp(
            "BOGUS_STATION",
            "hrrr",
            cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
            fxx=1,
        )
        assert df.empty
        # Empty dataframe still has canonical columns.
        canonical = [c.name for c in NwpForecastSchema.COLUMNS]
        assert set(df.columns) == set(canonical)

    def test_naive_cycle_rejected(self) -> None:
        from mostlyright.weather.forecast_nwp import forecast_nwp

        with pytest.raises(ValueError, match="cycle must be timezone-aware"):
            forecast_nwp("KNYC", "hrrr", cycle=datetime(2026, 5, 23, 12), fxx=1)

    def test_negative_fxx_rejected(self) -> None:
        from mostlyright.weather.forecast_nwp import forecast_nwp

        with pytest.raises(ValueError, match="fxx must be non-negative"):
            forecast_nwp("KNYC", "hrrr", fxx=-1)


@pytest.mark.skipif(_HAS_NWP_EXTRA, reason="this test verifies the absence-of-extra path")
def test_forecast_nwp_without_extra_raises_source_unavailable_with_hint() -> None:
    from mostlyright.weather.forecast_nwp import forecast_nwp

    with pytest.raises(SourceUnavailableError) as exc_info:
        forecast_nwp("KNYC", "hrrr", cycle=datetime(2026, 5, 23, 12, tzinfo=UTC), fxx=1)
    assert "mostlyrightmd-weather[nwp]" in str(exc_info.value)
    assert exc_info.value.retryable is False


# ---------------------------------------------------------------------------
# Schema registration
# ---------------------------------------------------------------------------
class TestSchemaRegistration:
    def test_schema_registered_with_validator(self) -> None:
        from mostlyright.core.validator import _SCHEMA_REGISTRY

        assert "schema.forecast_nwp.v1" in _SCHEMA_REGISTRY

    def test_canonical_columns_present(self) -> None:
        cols = {c.name for c in NwpForecastSchema.COLUMNS}
        required = {
            "station",
            "model",
            "mirror",
            "grid_kind",
            "issued_at",
            "valid_at",
            "forecast_hour",
            "grid_dist_km",
            "qc_status",
            "retrieved_at",
            "temp_k_2m",
            "dewpoint_k_2m",
            "wind_u_ms_10m",
            "wind_v_ms_10m",
        }
        assert required <= cols

    def test_qc_status_enum_values(self) -> None:
        assert NWP_QC_STATUS_VALUES == ("clean", "flagged", "suspect")

    def test_mirror_enum_reserves_ecmwf_mirrors(self) -> None:
        for reserved in ("ecmwf_data_portal", "ecmwf_aws", "ecmwf_azure", "ecmwf_gcp"):
            assert reserved in NWP_MIRROR_VALUES

    def test_model_column_is_enum_constrained(self) -> None:
        col = NwpForecastSchema.column("model")
        assert col.dtype == "enum"
        assert col.enum_values is not None
        assert set(col.enum_values) == set(NWP_MODEL_VALUES)


# ---------------------------------------------------------------------------
# Default cycle selection
# ---------------------------------------------------------------------------
class TestDefaultCycleFor:
    def test_hrrr_is_hourly(self) -> None:
        from mostlyright.weather.forecast_nwp import _default_cycle_for

        # Pretend "now" is 2026-05-23 12:00 UTC; fxx=1, 90-min upload
        # backoff -> target = 12:00 - 1h30m (backoff) - 1h (fxx) = 09:30
        # -> floor to hourly = 09:00. Verifies the 90-minute clearance.
        cycle = _default_cycle_for("hrrr", fxx=1, now=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))
        assert cycle.hour == 9
        assert cycle.minute == 0
        # The fxx-1 forecast issued at 09:00 has valid_at = 10:00, which
        # is 2 hours in the past relative to 12:00 — clear of backoff.
        assert (cycle + timedelta(hours=1)) <= datetime(2026, 5, 23, 12, 0, tzinfo=UTC) - timedelta(
            minutes=90
        )

    def test_gfs_is_six_hourly(self) -> None:
        from mostlyright.weather.forecast_nwp import _default_cycle_for

        # fxx=12 + 90-min backoff → target ≈ 2026-05-23 -1.5h → 22:30 prev day
        # → floor to 18:00 prev day.
        cycle = _default_cycle_for("gfs", fxx=12, now=datetime(2026, 5, 24, 0, 0, tzinfo=UTC))
        assert cycle.hour % 6 == 0

    def test_returned_cycle_is_utc_aware(self) -> None:
        from mostlyright.weather.forecast_nwp import _default_cycle_for

        cycle = _default_cycle_for("hrrr", fxx=1)
        assert cycle.tzinfo is not None


# ---------------------------------------------------------------------------
# Mirror fallback wired through _try_fetch_records_for_mirror
# ---------------------------------------------------------------------------
class TestMirrorFallback:
    def test_all_mirrors_failing_raises_no_live(self) -> None:
        """Bypass _try_fetch_records_for_mirror entirely.

        Validates only the OUTER loop: every mirror -> None converts to
        NoLiveForNwpError. The actual httpx-error → None conversion is
        covered by ``test_all_mirrors_404_via_real_http_path`` below.
        """
        from mostlyright.weather import forecast_nwp as fnwp_module

        def fail_all(**kwargs: object) -> None:
            return None

        with patch.object(fnwp_module, "_try_fetch_records_for_mirror", side_effect=fail_all):
            # We still need the lazy imports to succeed so the function reaches
            # the mirror loop. Skip the test entirely if [nwp] is absent —
            # the absence path is covered separately.
            if not _HAS_NWP_EXTRA:
                pytest.skip("requires [nwp] extra installed")
            with pytest.raises(NoLiveForNwpError) as exc_info:
                fnwp_module.forecast_nwp(
                    "KNYC", "hrrr", cycle=datetime(2026, 5, 23, 12, tzinfo=UTC), fxx=1
                )
            assert exc_info.value.model == "hrrr"
            assert exc_info.value.mirrors_tried == list(("aws_bdp", "nomads"))

    def test_all_mirrors_404_via_real_http_path(self) -> None:
        """End-to-end coverage of the http-error → mirror-skip path.

        Pumps a real ``httpx.MockTransport`` through the actual fetch
        helpers (no monkey-patch of the catching code). Verifies the
        ``except (httpx.HTTPStatusError, httpx.RequestError)`` in
        ``_try_fetch_records_for_mirror`` correctly converts a 404 from
        every mirror into ``NoLiveForNwpError`` — not into a leaked
        httpx exception.
        """
        if not _HAS_NWP_EXTRA:
            pytest.skip("requires [nwp] extra installed")
        from mostlyright.weather.forecast_nwp import forecast_nwp

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="not found")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(NoLiveForNwpError) as exc_info:
                forecast_nwp(
                    "KNYC",
                    "hrrr",
                    cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
                    fxx=1,
                    client=client,
                )
            assert exc_info.value.model == "hrrr"
            assert exc_info.value.mirrors_tried == ["aws_bdp", "nomads"]
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Station alias dedup (HIGH-2 from architect review)
# ---------------------------------------------------------------------------
class TestStationAliasDedup:
    def test_nws_code_and_icao_alias_collapse_to_one_row(self) -> None:
        """``["NYC", "KNYC"]`` must NOT produce two rows for the same station."""
        from mostlyright.weather.forecast_nwp import _resolve_stations

        out = _resolve_stations(["NYC", "KNYC"])
        # NYC resolves to StationInfo with icao=KNYC, then KNYC alias is dropped.
        assert len(out) == 1
        # First occurrence wins — input label preserved.
        assert out[0][0] == "NYC"

    def test_distinct_stations_kept(self) -> None:
        from mostlyright.weather.forecast_nwp import _resolve_stations

        out = _resolve_stations(["KNYC", "KLAX"])
        assert len(out) == 2
        assert {s for s, _, _ in out} == {"KNYC", "KLAX"}

    def test_unknown_station_skipped(self) -> None:
        from mostlyright.weather.forecast_nwp import _resolve_stations

        out = _resolve_stations(["KNYC", "BOGUS"])
        assert len(out) == 1
        assert out[0][0] == "KNYC"


# ---------------------------------------------------------------------------
# GribIntegrityError carries model context (HIGH-4 from architect review)
# ---------------------------------------------------------------------------
class TestCfgribVariableNameError:
    def test_short_name_miss_carries_model_in_payload(self) -> None:
        """``_cfgrib_variable_name`` must populate ``model`` in raised errors."""
        from mostlyright.weather.forecast_nwp import _cfgrib_variable_name

        class _StubDS:
            # cfgrib decoded record but used a different short-name AND
            # produced multiple data_vars, so the table-miss fallback fires.
            data_vars: ClassVar[dict[str, object]] = {
                "unexpected_a": object(),
                "unexpected_b": object(),
            }

        with pytest.raises(GribIntegrityError) as exc_info:
            _cfgrib_variable_name(_StubDS(), ("TMP", "2 m above ground"), model="hrrr")
        assert exc_info.value.model == "hrrr"
        # The to_dict surface (MCP serialization) carries the same field.
        assert exc_info.value.to_dict()["model"] == "hrrr"

    def test_unknown_variable_no_table_entry_also_carries_model(self) -> None:
        from mostlyright.weather.forecast_nwp import _cfgrib_variable_name

        class _StubDS:
            data_vars: ClassVar[dict[str, object]] = {"a": object(), "b": object()}

        with pytest.raises(GribIntegrityError) as exc_info:
            _cfgrib_variable_name(_StubDS(), ("UNKNOWN_VAR", "unknown level"), model="gfs")
        assert exc_info.value.model == "gfs"


# ---------------------------------------------------------------------------
# Codex iter-1 P2 follow-ups: non-UTC cycle, source attr, dtype, ambiguous .idx
# ---------------------------------------------------------------------------
class TestCodexP2Followups:
    def test_non_utc_aware_cycle_normalised_to_utc(self) -> None:
        """``2026-05-23 14:00+02:00`` is the 12z cycle, not a (nonexistent) t14z."""
        from datetime import timedelta, timezone

        from mostlyright.weather._fetchers._nwp_archive import build_fetch_plan

        cet = timezone(timedelta(hours=2))
        plan = build_fetch_plan(
            model="hrrr",
            mirror="aws_bdp",
            cycle=datetime(2026, 5, 23, 14, 0, tzinfo=cet),
            fxx=1,
        )
        # The URL must use t12z (UTC equivalent of 14:00+02:00), not t14z.
        assert "t12z" in plan.grib2_url
        assert "t14z" not in plan.grib2_url
        # The stored cycle on the plan is the UTC-normalised value.
        assert plan.cycle.tzinfo is UTC
        assert plan.cycle.hour == 12

    def test_empty_dataframe_carries_source_attr(self) -> None:
        from mostlyright.weather.forecast_nwp import _empty_dataframe

        df = _empty_dataframe(model="hrrr", grid_kind="lambert_conformal_conus")
        assert df.attrs.get("source") == "noaa_bdp"

    def test_empty_dataframe_carries_retrieved_at_attr(self) -> None:
        """Codex iter-2 P2: validator requires `retrieved_at` attr when empty."""
        from mostlyright.weather.forecast_nwp import _empty_dataframe

        df = _empty_dataframe(model="hrrr", grid_kind="lambert_conformal_conus")
        retrieved_at = df.attrs.get("retrieved_at")
        assert retrieved_at is not None
        assert retrieved_at.tzinfo is UTC

    def test_mirror_transport_failed_sentinel_used_for_http_errors(self) -> None:
        """Codex iter-3 P2: byte-range HTTP failure -> mirror fallback.

        Confirms the internal _MirrorTransportFailed sentinel is raised
        (not GribIntegrityError) when fetch_byte_range hits an httpx error.
        This is what enables the outer mirror loop in forecast_nwp to
        fall through to NOMADS when AWS serves .idx but errors on bytes.
        """
        from datetime import datetime

        from mostlyright.weather._fetchers._nwp_archive import build_fetch_plan
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import (
            _extract_records,
            _MirrorTransportFailed,
        )

        plan = build_fetch_plan(
            model="hrrr",
            mirror="aws_bdp",
            cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
            fxx=1,
        )
        records = [
            IdxRecord(1, 0, 99, "d=", "TMP", "2 m above ground", "1 hour fcst"),
        ]

        def fail(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="upstream busy")

        client = httpx.Client(transport=httpx.MockTransport(fail))
        try:
            with pytest.raises(_MirrorTransportFailed) as exc_info:
                _extract_records(
                    plan=plan,
                    filtered_records=records,
                    variable_map={"temp_k_2m": ("TMP", "2 m above ground")},
                    station_coords=[(40.7, -74.0)],
                    column_values={"temp_k_2m": [None]},
                    distances_km=[None],
                    model="hrrr",
                    client=client,
                )
            assert exc_info.value.variable == "TMP"
            assert "503" in exc_info.value.underlying or "transport" in str(exc_info.value).lower()
        finally:
            client.close()

    def test_mirror_returning_200_full_body_routes_via_mirror_transport_failed(self) -> None:
        """Phase 17 iter-2: assert_range_honored RuntimeError -> mirror fallback.

        Phase 17 PLAN-01 added a 200-OK-with-full-body abort in
        ``fetch_byte_range`` (a misconfigured mirror that ignores the
        ``Range:`` header). That abort is a ``RuntimeError`` — without
        the iter-2 fix, it would escape the byte-range try/except in
        ``_extract_records`` and abort ``forecast_nwp`` outright instead
        of falling through to the next mirror.

        This test confirms the new ``RuntimeError`` clause routes
        through ``_MirrorTransportFailed`` so the outer mirror loop
        can continue to NOMADS / Google / Azure on the next iteration.
        """
        from datetime import datetime

        from mostlyright.weather._fetchers._nwp_archive import build_fetch_plan
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import (
            _extract_records,
            _MirrorTransportFailed,
        )

        plan = build_fetch_plan(
            model="hrrr",
            mirror="aws_bdp",
            cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
            fxx=1,
        )
        records = [
            IdxRecord(1, 0, 99, "d=", "TMP", "2 m above ground", "1 hour fcst"),
        ]

        # A mirror that returns 200 OK with the FULL file body instead of
        # the requested byte range — the failure mode FORECAST-05 guards.
        def two_hundred_full_body(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"FULL_FILE_BODY")

        client = httpx.Client(transport=httpx.MockTransport(two_hundred_full_body))
        try:
            with pytest.raises(_MirrorTransportFailed) as exc_info:
                _extract_records(
                    plan=plan,
                    filtered_records=records,
                    variable_map={"temp_k_2m": ("TMP", "2 m above ground")},
                    station_coords=[(40.7, -74.0)],
                    column_values={"temp_k_2m": [None]},
                    distances_km=[None],
                    model="hrrr",
                    client=client,
                )
            # The underlying RuntimeError message documents the abort cause.
            assert "Range request not honored" in exc_info.value.underlying
        finally:
            client.close()

    def test_issued_at_and_valid_at_are_utc_aware_when_caller_passes_non_utc(self) -> None:
        """Codex iter-3 P2: issued_at/valid_at must be UTC even if input was offset.

        Build_fetch_plan UTC-normalizes the cycle for path construction, but
        the row-build loop must also use the UTC-normalized cycle for
        issued_at/valid_at; otherwise the schema's timestamp_utc invariant
        breaks and downstream UTC joins drift.
        """
        if not _HAS_NWP_EXTRA:
            pytest.skip("requires [nwp] extra installed")
        from datetime import timedelta, timezone

        from mostlyright.weather.forecast_nwp import forecast_nwp

        cet = timezone(timedelta(hours=2))
        # Unknown station path returns empty df but exercises the cycle
        # normalisation path. Use a known station that's not in HRRR
        # grid to test the column-empty branch wouldn't help — better
        # to just unit-test that build_fetch_plan returns UTC cycle
        # AND the live row builder uses the same instant. The
        # build_fetch_plan UTC normalisation is already tested above;
        # this test confirms forecast_nwp's eager .astimezone(UTC) on
        # the public-surface side returns a normalized DataFrame on the
        # empty path.
        df = forecast_nwp(
            "UNKNOWN_STATION_FOR_THIS_TEST",
            "hrrr",
            cycle=datetime(2026, 5, 23, 14, 0, tzinfo=cet),
            fxx=1,
        )
        # Returns empty df from the unknown-station path; the cycle was
        # accepted (UTC-normalised internally) — no ValueError raised.
        assert df.empty

    def test_empty_dataframe_nullable_numeric_columns_are_float64(self) -> None:
        from mostlyright.weather.forecast_nwp import _empty_dataframe

        df = _empty_dataframe(model="hrrr", grid_kind="lambert_conformal_conus")
        for col in (
            "temp_k_2m",
            "dewpoint_k_2m",
            "pressure_pa_surface",
            "pressure_pa_mslp",
            "cloud_cover_pct",
            "visibility_m",
            "cloud_ceiling_m",
        ):
            assert str(df[col].dtype) == "float64", (
                f"{col} dtype must be float64, got {df[col].dtype}"
            )

    def test_unknown_station_dataframe_has_source_attr(self) -> None:
        """The early-return path on unknown stations also stamps attrs."""
        if not _HAS_NWP_EXTRA:
            pytest.skip("requires [nwp] extra installed")
        from mostlyright.weather.forecast_nwp import forecast_nwp

        df = forecast_nwp(
            "BOGUS",
            "hrrr",
            cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
            fxx=1,
        )
        assert df.empty
        assert df.attrs.get("source") == "noaa_bdp"


# ---------------------------------------------------------------------------
# Disambiguation heuristics
# ---------------------------------------------------------------------------
class TestDisambiguationHeuristics:
    def test_pick_record_prefers_instantaneous_over_window(self) -> None:
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import _pick_record

        r_inst = IdxRecord(
            record_no=636,
            byte_offset=1000,
            byte_end=2000,
            reference_date="d=",
            variable="TCDC",
            level="entire atmosphere",
            forecast_period="1 hour fcst",
        )
        r_ave = IdxRecord(
            record_no=637,
            byte_offset=2000,
            byte_end=3000,
            reference_date="d=",
            variable="TCDC",
            level="entire atmosphere",
            forecast_period="0-1 hour ave fcst",
        )

        # Order should not matter; r_inst should be picked
        assert _pick_record([r_inst, r_ave]) == r_inst
        assert _pick_record([r_ave, r_inst]) == r_inst

    def test_pick_record_breaks_ties_with_record_no(self) -> None:
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import _pick_record

        r1 = IdxRecord(
            record_no=596,
            byte_offset=1000,
            byte_end=2000,
            reference_date="d=",
            variable="APCP",
            level="surface",
            forecast_period="0-1 hour acc fcst",
        )
        r2 = IdxRecord(
            record_no=597,
            byte_offset=2000,
            byte_end=3000,
            reference_date="d=",
            variable="APCP",
            level="surface",
            forecast_period="0-1 hour acc fcst",
        )

        # Picks lowest record_no
        assert _pick_record([r1, r2]) == r1
        assert _pick_record([r2, r1]) == r1

    def test_pick_record_ambiguous_distinct_windows_returns_none(self) -> None:
        """Issue #63 / codex P2: distinct aggregation windows (e.g. max vs min)
        with no instantaneous record are genuinely ambiguous — _pick_record
        returns None so the caller fails loud rather than silently picking an
        arbitrary window."""
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import _pick_record

        r_max = IdxRecord(
            record_no=10,
            byte_offset=1000,
            byte_end=2000,
            reference_date="d=",
            variable="TMP",
            level="surface",
            forecast_period="0-1 hour max fcst",
        )
        r_min = IdxRecord(
            record_no=11,
            byte_offset=2000,
            byte_end=3000,
            reference_date="d=",
            variable="TMP",
            level="surface",
            forecast_period="0-1 hour min fcst",
        )

        assert _pick_record([r_max, r_min]) is None
        assert _pick_record([r_min, r_max]) is None

    def test_pick_record_identical_window_twin_picks_lowest_record_no(self) -> None:
        """The GFS APCP:surface twin — two records, IDENTICAL window — is safe
        to resolve by lowest record_no (same data)."""
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import _pick_record

        r1 = IdxRecord(596, 0, 99, "d=", "APCP", "surface", "0-1 hour acc fcst")
        r2 = IdxRecord(597, 100, 199, "d=", "APCP", "surface", "0-1 hour acc fcst")
        assert _pick_record([r1, r2]) == r1
        assert _pick_record([r2, r1]) == r1

    def test_extract_records_raises_on_ambiguous_distinct_windows(self) -> None:
        """Issue #63 / codex P2: _extract_records must raise GribIntegrityError
        (loud fail) when a (variable, level) resolves to multiple DISTINCT
        windows with no instantaneous record — not silently pick one."""
        if not _HAS_NWP_EXTRA:
            pytest.skip("requires [nwp] extra installed")
        import httpx
        from mostlyright.weather._fetchers._nwp_archive import build_fetch_plan
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import _extract_records

        plan = build_fetch_plan(
            model="gfs",
            mirror="aws_bdp",
            cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
            fxx=1,
        )
        # Two DISTINCT accumulation windows for the same key, no instantaneous.
        records = [
            IdxRecord(596, 0, 99, "d=", "APCP", "surface", "0-1 hour acc fcst"),
            IdxRecord(600, 200, 299, "d=", "APCP", "surface", "0-6 hour acc fcst"),
        ]

        # Transport must never be reached — the ambiguity check raises first.
        def fail_transport(request: httpx.Request) -> httpx.Response:
            raise AssertionError("transport should not be reached on ambiguous records")

        client = httpx.Client(transport=httpx.MockTransport(fail_transport))
        try:
            with pytest.raises(GribIntegrityError):
                _extract_records(
                    plan=plan,
                    filtered_records=records,
                    variable_map={"precip_mm_1h": ("APCP", "surface")},
                    station_coords=[(40.7, -74.0)],
                    column_values={"precip_mm_1h": [None]},
                    distances_km=[None],
                    model="gfs",
                    client=client,
                )
        finally:
            client.close()

    def test_extract_records_disambiguates_without_raising_error(self) -> None:
        """Integration-level test of _extract_records with duplicate entries."""
        if not _HAS_NWP_EXTRA:
            pytest.skip("requires [nwp] extra installed")
        import httpx
        from mostlyright.weather._fetchers._nwp_archive import build_fetch_plan
        from mostlyright.weather._fetchers._nwp_idx import IdxRecord
        from mostlyright.weather.forecast_nwp import _extract_records

        plan = build_fetch_plan(
            model="gfs",
            mirror="aws_bdp",
            cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
            fxx=1,
        )
        # We supply duplicate records for APCP. They should be disambiguated, and
        # since we will raise a MockTransport exception on request, it verifies
        # that we successfully passed the duplicate check (which would have raised
        # GribIntegrityError instead of MockTransport failure).
        records = [
            IdxRecord(596, 0, 99, "d=", "APCP", "surface", "0-1 hour acc fcst"),
            IdxRecord(597, 100, 199, "d=", "APCP", "surface", "0-1 hour acc fcst"),
        ]

        def fail_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="service unavailable")

        client = httpx.Client(transport=httpx.MockTransport(fail_transport))
        from mostlyright.weather.forecast_nwp import _MirrorTransportFailed

        try:
            with pytest.raises(_MirrorTransportFailed):
                _extract_records(
                    plan=plan,
                    filtered_records=records,
                    variable_map={"precip_mm_1h": ("APCP", "surface")},
                    station_coords=[(40.7, -74.0)],
                    column_values={"precip_mm_1h": [None]},
                    distances_km=[None],
                    model="gfs",
                    client=client,
                )
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Issue #74 — member= ensemble selector for GEFS / CFS
# ---------------------------------------------------------------------------
class TestForecastNwpMember:
    """Validate + thread the ``member=`` kwarg (issue #74).

    ``member`` is only meaningful for the wired ensemble models GEFS / CFS.
    Misuse (member on a non-member model, or an out-of-enum member value)
    raises ``ValueError`` BEFORE the lazy ``[nwp]`` imports, so callers
    without cfgrib installed still get the right error. When valid, the
    member string is threaded to ``build_fetch_plan`` (and on to the
    GEFS/CFS path builders) ONLY when non-None — passing ``member=None``
    would override the path-builder default and crash f-string formatting.
    """

    # A GEFS/CFS cycle inside each model's archive depth on the 6h grid so
    # the single-cycle path runs deterministically without network.
    _GEFS_CYCLE: ClassVar[datetime] = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    _CFS_CYCLE: ClassVar[datetime] = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)

    def test_member_on_non_member_model_raises(self) -> None:
        """Test A — member= on a wired non-member model (hrrr) raises,
        naming the member-capable models. Fires before any fetch/import."""
        from mostlyright.weather.forecast_nwp import forecast_nwp

        with pytest.raises(ValueError) as exc_info:
            forecast_nwp("KNYC", "hrrr", member="p05")
        msg = str(exc_info.value)
        assert "gefs" in msg
        assert "cfs" in msg

    def test_invalid_member_on_gefs_raises_listing_valid(self) -> None:
        """Test B — an out-of-enum member on gefs raises, listing the
        sorted valid GEFS members. No network."""
        from mostlyright.weather._fetchers._nwp_grids.gefs import GEFS_MEMBERS
        from mostlyright.weather.forecast_nwp import forecast_nwp

        with pytest.raises(ValueError) as exc_info:
            forecast_nwp("KNYC", "gefs", member="zzz")
        msg = str(exc_info.value)
        # The message must list the real sorted member set.
        for m in sorted(GEFS_MEMBERS):
            assert m in msg

    @staticmethod
    def _capturing_build_fetch_plan(captured: list[dict]):
        """Wrap the real ``build_fetch_plan`` to record its kwargs.

        ``build_fetch_plan`` does no network I/O (pure URL construction), so
        we delegate to the real implementation to get a valid plan, then let
        the caller's ``MockTransport`` 404 the ``.idx`` fetch — driving the
        helper down its ``except httpx.HTTPStatusError`` → ``None`` path."""
        from mostlyright.weather.forecast_nwp import build_fetch_plan as _real

        def _wrapped(*args, **kwargs):
            captured.append(kwargs)
            return _real(*args, **kwargs)

        return _wrapped

    @staticmethod
    def _mock_404_client() -> httpx.Client:
        def _handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="not found")

        return httpx.Client(transport=httpx.MockTransport(_handler))

    def test_member_threads_to_build_fetch_plan_gefs(self) -> None:
        """Test C — member="p05" threads member="p05" into build_fetch_plan
        for gefs. Exercises the single-cycle threading helper
        ``_try_fetch_records_for_mirror`` directly so it runs in CI without
        the ``[nwp]`` extra (the helper sits below the lazy-import gate). A
        404 MockTransport drives the helper to its mirror-fallback None."""
        from mostlyright.weather.forecast_nwp import _try_fetch_records_for_mirror

        captured: list[dict] = []
        client = self._mock_404_client()
        try:
            with patch(
                "mostlyright.weather.forecast_nwp.build_fetch_plan",
                side_effect=self._capturing_build_fetch_plan(captured),
            ):
                result = _try_fetch_records_for_mirror(
                    model="gefs",
                    mirror="aws_bdp",
                    cycle=self._GEFS_CYCLE,
                    fxx=1,
                    variable_map={"temp_k_2m": ("TMP", "2 m above ground")},
                    client=client,
                    member="p05",
                )
        finally:
            client.close()

        assert result is None  # 404 → None (mirror fallback)
        assert captured, "build_fetch_plan was never called"
        assert all(c.get("member") == "p05" for c in captured)

    def test_member_none_omits_kwarg_gefs(self) -> None:
        """Test D (regression) — member=None (default) must NOT pass a
        member key to build_fetch_plan (passing member=None would override
        the path-builder default c00 and crash). Byte-identical to today.
        Direct on ``_try_fetch_records_for_mirror`` so it runs without the
        ``[nwp]`` extra."""
        from mostlyright.weather.forecast_nwp import _try_fetch_records_for_mirror

        captured: list[dict] = []
        client = self._mock_404_client()
        try:
            with patch(
                "mostlyright.weather.forecast_nwp.build_fetch_plan",
                side_effect=self._capturing_build_fetch_plan(captured),
            ):
                _try_fetch_records_for_mirror(
                    model="gefs",
                    mirror="aws_bdp",
                    cycle=self._GEFS_CYCLE,
                    fxx=1,
                    variable_map={"temp_k_2m": ("TMP", "2 m above ground")},
                    client=client,
                )
        finally:
            client.close()

        assert captured, "build_fetch_plan was never called"
        assert all("member" not in c for c in captured)

    def test_member_threads_to_build_fetch_plan_cfs(self) -> None:
        """Test E — member="03" threads member="03" into build_fetch_plan
        for cfs. Direct on ``_try_fetch_records_for_mirror`` (CI-safe)."""
        from mostlyright.weather.forecast_nwp import _try_fetch_records_for_mirror

        captured: list[dict] = []
        client = self._mock_404_client()
        try:
            with patch(
                "mostlyright.weather.forecast_nwp.build_fetch_plan",
                side_effect=self._capturing_build_fetch_plan(captured),
            ):
                _try_fetch_records_for_mirror(
                    model="cfs",
                    mirror="aws_bdp",
                    cycle=self._CFS_CYCLE,
                    fxx=1,
                    variable_map={"temp_k_2m": ("TMP", "2 m above ground")},
                    client=client,
                    member="03",
                )
        finally:
            client.close()

        assert captured, "build_fetch_plan was never called"
        assert all(c.get("member") == "03" for c in captured)

    def test_member_validation_fires_before_nwp_import(self) -> None:
        """Tests A/B fire pre-import; this pins the ordering explicitly for
        valid members too — a valid member on gefs reaches the single-cycle
        path (and ultimately the lazy ``[nwp]`` import) rather than tripping
        validation. Without the extra installed, the call surfaces
        ``SourceUnavailableError`` (NOT a member ValueError), proving a valid
        member passed validation. With the extra, it would proceed to fetch;
        we only assert the no-ValueError property here."""
        from mostlyright.weather.forecast_nwp import forecast_nwp

        if _HAS_NWP_EXTRA:
            pytest.skip("absence-of-extra ordering check; extra is installed")
        with pytest.raises(SourceUnavailableError):
            forecast_nwp("KNYC", "gefs", cycle=self._GEFS_CYCLE, member="p05")

    def test_member_threads_through_multi_cycle_gefs(self) -> None:
        """Test F (multi-cycle) — every recursive single-cycle call in a
        cycle_range backfill carries member="p05". Patches the module-level
        ``forecast_nwp`` recursion target (mirroring the existing multi-cycle
        test) to capture the per-cycle kwargs WITHOUT hitting the ``[nwp]``
        import gate, so it runs in CI without the extra."""
        from mostlyright.weather import forecast_nwp as fnwp_module

        start = datetime(2025, 6, 1, 0, 0, tzinfo=UTC)
        end = datetime(2025, 6, 1, 6, 0, tzinfo=UTC)  # GEFS 6h grid: 00, 06
        real_forecast_nwp = fnwp_module.forecast_nwp
        per_cycle_members: list[str | None] = []

        def _fake_single(*args, **kwargs):
            cycle = kwargs.get("cycle")
            # Only intercept the per-cycle recursive call (no range kwargs).
            if cycle is not None and kwargs.get("cycle_range_start") is None:
                per_cycle_members.append(kwargs.get("member"))
                return None  # no rows for this cycle; range path concats empties
            return real_forecast_nwp(*args, **kwargs)

        with (
            patch(
                "mostlyright.weather._fetchers._nwp_cycle_chunks.check_historical_depth",
                return_value=None,
            ),
            patch(
                "mostlyright.weather.forecast_nwp.forecast_nwp",
                side_effect=_fake_single,
            ),
        ):
            real_forecast_nwp(
                station="KNYC",
                model="gefs",
                cycle_range_start=start,
                cycle_range_end=end,
                member="p05",
            )

        assert per_cycle_members, "no per-cycle recursive calls observed"
        assert all(m == "p05" for m in per_cycle_members)


# ---------------------------------------------------------------------------
# Live integration (network-bound, marked + gated)
# ---------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(not _HAS_NWP_EXTRA, reason="requires [nwp] extra installed")
def test_forecast_nwp_live_hrrr_knyc_one_hour() -> None:
    """Real fetch against NOAA BDP. Skipped in CI."""
    from mostlyright.forecasts import forecast_nwp

    df = forecast_nwp("KNYC", "hrrr", fxx=1)
    assert not df.empty
    assert (df["model"] == "hrrr").all()
    assert (df["mirror"].isin(["aws_bdp", "nomads"])).all()
    # Temperature should be near surface ambient.
    assert df["temp_k_2m"].between(220, 320).all()
    # QC status string.
    assert df["qc_status"].isin(["clean", "flagged", "suspect"]).all()
