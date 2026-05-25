"""Phase 17 PLAN-04: ECMWF URL builders + registry entries + 4 mirrors."""

from __future__ import annotations

from datetime import UTC, datetime

from mostlyright.weather._fetchers._nwp_archive import (
    IDX_STYLE_BY_MODEL,
    IDX_SUFFIX_BY_MODEL,
    SOURCES_BY_MODEL,
    SUPPORTED_NWP_MODELS,
    build_fetch_plan,
)
from mostlyright.weather._fetchers._nwp_grids import ecmwf_aifs, ecmwf_ifs

# ---------------------------------------------------------------------------
# IFS URL builder — handles path + resolution transitions
# ---------------------------------------------------------------------------


def test_ecmwf_ifs_post_2024_path_and_resolution() -> None:
    plan = build_fetch_plan(
        model="ecmwf_ifs_hres",
        mirror="ecmwf_data_portal",
        cycle=datetime(2026, 5, 24, 0, tzinfo=UTC),
        fxx=0,
        product="oper",
        ftype="fc",
    )
    assert plan.grib2_url == (
        "https://data.ecmwf.int/forecasts/20260524/00z/ifs/0p25/oper/"
        "20260524000000-0h-oper-fc.grib2"
    )
    assert plan.idx_url.endswith(".grib2.index")


def test_ecmwf_ifs_pre_resolution_transition_uses_0p4_beta() -> None:
    plan = build_fetch_plan(
        model="ecmwf_ifs_hres",
        mirror="ecmwf_data_portal",
        cycle=datetime(2024, 2, 28, 6, tzinfo=UTC),
        fxx=0,
        product="oper",
        ftype="fc",
    )
    assert "/ifs/0p4-beta/" in plan.grib2_url


def test_ecmwf_ifs_pre_path_transition_has_no_ifs_segment() -> None:
    plan = build_fetch_plan(
        model="ecmwf_ifs_hres",
        mirror="ecmwf_data_portal",
        cycle=datetime(2024, 2, 28, 0, tzinfo=UTC),  # pre 06Z cutover
        fxx=0,
        product="oper",
        ftype="fc",
    )
    assert "/ifs/" not in plan.grib2_url
    assert "/0p4-beta/oper/" in plan.grib2_url


# ---------------------------------------------------------------------------
# AIFS URL builder — 3-phase transitions
# ---------------------------------------------------------------------------


def test_ecmwf_aifs_post_operational_uses_aifs_single() -> None:
    plan = build_fetch_plan(
        model="ecmwf_aifs_single",
        mirror="ecmwf_data_portal",
        cycle=datetime(2026, 5, 24, 0, tzinfo=UTC),
        fxx=0,
        product="oper",
        ftype="fc",
    )
    assert "/aifs-single/0p25/oper/" in plan.grib2_url


def test_ecmwf_aifs_experimental_phase_has_experimental_segment() -> None:
    plan = build_fetch_plan(
        model="ecmwf_aifs_single",
        mirror="ecmwf_data_portal",
        cycle=datetime(2025, 2, 15, 0, tzinfo=UTC),
        fxx=0,
        product="oper",
        ftype="fc",
    )
    assert "/aifs-single/0p25/experimental/" in plan.grib2_url


def test_ecmwf_aifs_pre_experimental_uses_aifs_not_aifs_single() -> None:
    plan = build_fetch_plan(
        model="ecmwf_aifs_single",
        mirror="ecmwf_data_portal",
        cycle=datetime(2025, 1, 1, 0, tzinfo=UTC),
        fxx=0,
        product="oper",
        ftype="fc",
    )
    assert "/aifs/0p25/" in plan.grib2_url
    assert "/aifs-single/" not in plan.grib2_url


def test_ecmwf_aifs_ens_always_aifs_ens_segment() -> None:
    plan = build_fetch_plan(
        model="ecmwf_aifs_ens",
        mirror="ecmwf_data_portal",
        cycle=datetime(2026, 5, 24, 0, tzinfo=UTC),
        fxx=0,
        product="enfo",
        ftype="ef",
    )
    assert "/aifs-ens/0p25/" in plan.grib2_url


# ---------------------------------------------------------------------------
# Registry entries
# ---------------------------------------------------------------------------


def test_sources_by_model_ecmwf_4_mirrors() -> None:
    expected = ("ecmwf_gcp", "ecmwf_aws", "ecmwf_data_portal", "ecmwf_azure")
    for m in ("ecmwf_ifs_hres", "ecmwf_ifs_ens", "ecmwf_aifs_single", "ecmwf_aifs_ens"):
        assert SOURCES_BY_MODEL[m] == expected


def test_ecmwf_idx_suffix_is_dot_index() -> None:
    for m in ("ecmwf_ifs_hres", "ecmwf_ifs_ens", "ecmwf_aifs_single", "ecmwf_aifs_ens"):
        assert IDX_SUFFIX_BY_MODEL[m] == (".index",)


def test_ecmwf_idx_style_is_eccodes() -> None:
    for m in ("ecmwf_ifs_hres", "ecmwf_ifs_ens", "ecmwf_aifs_single", "ecmwf_aifs_ens"):
        assert IDX_STYLE_BY_MODEL[m] == "eccodes"


def test_supported_nwp_models_includes_4_ecmwf() -> None:
    for m in ("ecmwf_ifs_hres", "ecmwf_ifs_ens", "ecmwf_aifs_single", "ecmwf_aifs_ens"):
        assert m in SUPPORTED_NWP_MODELS


def test_variable_map_ecmwf_ifs_uses_eccodes_param_keys() -> None:
    assert ecmwf_ifs.VARIABLE_MAP["temp_k_2m"] == ("2t", "sfc")
    assert ecmwf_ifs.VARIABLE_MAP["precip_mm_1h"] == ("tp", "sfc")
    assert ecmwf_ifs.VARIABLE_MAP["pressure_pa_mslp"] == ("msl", "sfc")


def test_variable_map_ecmwf_aifs_omits_wind_gust() -> None:
    # AIFS does not publish 10fg surface gust.
    assert "wind_gust_ms" not in ecmwf_aifs.VARIABLE_MAP
    assert ecmwf_aifs.VARIABLE_MAP["temp_k_2m"] == ("2t", "sfc")
