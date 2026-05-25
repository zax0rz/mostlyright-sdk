"""Phase 17 PLAN-05: MSC Canadian family — per-variable URLs + retention guard."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mostlyright.core.exceptions import HistoricalDepthError
from mostlyright.core.schemas.forecast_nwp import NWP_MODEL_VALUES
from mostlyright.weather._fetchers._msc_archive import (
    MSC_MODELS,
    MscFetchPlan,
    build_msc_fetch_plan,
    raise_msc_historical_depth,
)
from mostlyright.weather._fetchers._nwp_grids import (
    geps,
    hrdps,
    reps,
)

CYCLE = datetime(2026, 5, 24, 12, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Schema + registry
# ---------------------------------------------------------------------------


def test_nwp_model_values_includes_5_msc() -> None:
    for m in ("hrdps", "rdps", "gdps", "geps", "reps"):
        assert m in NWP_MODEL_VALUES


def test_msc_models_frozenset() -> None:
    assert frozenset({"hrdps", "rdps", "gdps", "geps", "reps"}) == MSC_MODELS


def test_msc_fetch_plan_is_frozen_dataclass() -> None:
    from dataclasses import FrozenInstanceError

    plan = MscFetchPlan(model="hrdps", cycle=CYCLE, fxx=6, variable_urls={})
    with pytest.raises(FrozenInstanceError):
        plan.fxx = 7  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Per-model URL builders — verbatim against RESEARCH.md §1
# ---------------------------------------------------------------------------


def test_build_msc_fetch_plan_hrdps_url() -> None:
    plan = build_msc_fetch_plan(model="hrdps", cycle=CYCLE, fxx=6, variables=["temp_k_2m"])
    assert plan.variable_urls["temp_k_2m"] == (
        "https://dd.weather.gc.ca/20260524/WXO-DD/model_hrdps/continental/2.5km/"
        "12/006/20260524T12Z_MSC_HRDPS_TMP_TGL_2_RLatLon0.0225_PT006H.grib2"
    )


def test_build_msc_fetch_plan_rdps_url() -> None:
    plan = build_msc_fetch_plan(model="rdps", cycle=CYCLE, fxx=6, variables=["temp_k_2m"])
    url = plan.variable_urls["temp_k_2m"]
    assert "model_rdps/10km/12/006" in url
    assert "MSC_RDPS_TMP_TGL_2_RLatLon0.09_PT006H.grib2" in url


def test_build_msc_fetch_plan_gdps_url() -> None:
    plan = build_msc_fetch_plan(model="gdps", cycle=CYCLE, fxx=6, variables=["temp_k_2m"])
    url = plan.variable_urls["temp_k_2m"]
    assert "model_gem_global/15km/grib2/lat_lon/12/006" in url
    assert "CMC_glb_TMP_TGL_2_latlon.15x.15_2026052412_P006.grib2" in url


def test_build_msc_fetch_plan_geps_allmbrs_url() -> None:
    plan = build_msc_fetch_plan(
        model="geps", cycle=CYCLE, fxx=6, variables=["temp_k_2m"], member="allmbrs"
    )
    url = plan.variable_urls["temp_k_2m"]
    assert "ensemble/geps/grib2/raw/12/006" in url
    assert "CMC_geps-raw_TMP_TGL_2" in url


def test_build_msc_fetch_plan_geps_prod_url() -> None:
    plan = build_msc_fetch_plan(
        model="geps", cycle=CYCLE, fxx=6, variables=["temp_k_2m"], member="prod"
    )
    url = plan.variable_urls["temp_k_2m"]
    assert "ensemble/geps/grib2/products" in url
    assert "CMC_geps-prod_TMP_TGL_2" in url


def test_build_msc_fetch_plan_reps_member_url() -> None:
    plan = build_msc_fetch_plan(
        model="reps", cycle=CYCLE, fxx=6, variables=["temp_k_2m"], member="m001"
    )
    url = plan.variable_urls["temp_k_2m"]
    assert "ensemble/reps/10km/grib2/12/006" in url
    assert "MSC_REPS_TMP_TGL_2" in url
    assert "_m001.grib2" in url


# ---------------------------------------------------------------------------
# Member enums
# ---------------------------------------------------------------------------


def test_geps_members_includes_aggregates() -> None:
    assert {"allmbrs", "raw", "prod"} <= geps.GEPS_MEMBERS


def test_reps_members_has_21_entries() -> None:
    assert frozenset({f"m{i:03d}" for i in range(1, 22)}) == reps.REPS_MEMBERS
    assert len(reps.REPS_MEMBERS) == 21


# ---------------------------------------------------------------------------
# Variable map sanity
# ---------------------------------------------------------------------------


def test_variable_map_hrdps_msc_naming() -> None:
    assert hrdps.VARIABLE_MAP["temp_k_2m"] == ("TMP", "TGL_2")
    assert hrdps.VARIABLE_MAP["wind_u_ms_10m"] == ("UGRD", "TGL_10")


# ---------------------------------------------------------------------------
# Historical depth + validation errors
# ---------------------------------------------------------------------------


def test_raise_msc_historical_depth_raises_with_archive_depth_none() -> None:
    with pytest.raises(HistoricalDepthError) as exc_info:
        raise_msc_historical_depth("hrdps", CYCLE)
    err = exc_info.value
    assert err.model == "hrdps"
    assert err.archive_depth is None
    assert "24h retention" in str(err)


def test_build_msc_fetch_plan_unknown_model_raises_value_error() -> None:
    with pytest.raises(ValueError, match="model must be one of"):
        build_msc_fetch_plan(model="not_msc", cycle=CYCLE, fxx=6, variables=["temp_k_2m"])


def test_build_msc_fetch_plan_unknown_variable_raises_key_error() -> None:
    with pytest.raises(KeyError, match=r"variable.*not in MSC"):
        build_msc_fetch_plan(model="hrdps", cycle=CYCLE, fxx=6, variables=["not_a_variable"])


def test_build_msc_fetch_plan_naive_cycle_raises_value_error() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_msc_fetch_plan(
            model="hrdps",
            cycle=datetime(2026, 5, 24, 12),  # naive
            fxx=6,
            variables=["temp_k_2m"],
        )
