"""Phase 17 PLAN-03 — NCEP family wiring (8 models on top of PLAN-01).

Adds HRRRAK, GEFS, GDAS, RAP, RRFS, RTMA, URMA, CFS to the dispatch
tables in ``_nwp_archive`` + per-model variable maps in ``_nwp_grids/``.
All wgrib2 idx style. Per-model kwargs (``member``, ``product``,
``kind``, ``valid_date``, ...) flow through ``build_fetch_plan`` to the
matching path builder so callers can disambiguate GEFS ensemble members,
RAP product nests, RTMA/URMA guesses, CFS member runs, etc.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mostlyright.weather._fetchers._nwp_archive import (
    IDX_STYLE_BY_MODEL,
    IDX_SUFFIX_BY_MODEL,
    SOURCES_BY_MODEL,
    SUPPORTED_NWP_MODELS,
    build_fetch_plan,
)

# ---------------------------------------------------------------------------
# URL-builder regressions — one per NCEP model.
# ---------------------------------------------------------------------------


def test_hrrrak_url_builder_alaska_polar_stereo() -> None:
    """HRRRAK (Alaska polar stereo) lives under ``/hrrr.{YYYYMMDD}/alaska/``."""
    plan = build_fetch_plan(
        model="hrrrak",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=6,
    )
    assert plan.grib2_url == (
        "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20260524/"
        "alaska/hrrr.t12z.wrfsfcf06.ak.grib2"
    )
    assert plan.idx_url == plan.grib2_url + ".idx"


def test_gefs_url_builder_post_2020_layout_member_c00() -> None:
    """GEFS post-2020 path: ``atmos/pgrb2ap5/ge{member}.t{HH}z.pgrb2a.0p50.f{fxx:03d}``."""
    plan = build_fetch_plan(
        model="gefs",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=6,
        member="c00",
    )
    # Just assert the member-specific filename pattern lands in the URL —
    # the bucket-root prefix is asserted by other tests.
    assert "gec00.t12z.pgrb2a.0p50.f006" in plan.grib2_url
    assert "/gefs.20260524/12/atmos/pgrb2ap5/" in plan.grib2_url


def test_gdas_url_builder_shares_gfs_bucket() -> None:
    """GDAS shares the GFS BDP bucket + post-v16 ``/atmos/`` layout."""
    plan = build_fetch_plan(
        model="gdas",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=6,
    )
    assert plan.grib2_url == (
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gdas.20260524/12/atmos/gdas.t12z.pgrb2.0p25.f006"
    )


def test_rap_url_builder_default_product_awp130pgrb() -> None:
    """RAP default product is ``awp130pgrb`` (13-km CONUS)."""
    plan = build_fetch_plan(
        model="rap",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=6,
    )
    assert (
        "noaa-rap-pds.s3.amazonaws.com/rap.20260524/rap.t12z.awp130pgrbf06.grib2" in plan.grib2_url
    )


def test_rrfs_url_builder_aws_only_with_subdir() -> None:
    """RRFS lives under ``/rrfs_a/rrfs.{YYYYMMDD}/`` on noaa-rrfs-pds."""
    plan = build_fetch_plan(
        model="rrfs",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=6,
    )
    assert "noaa-rrfs-pds.s3.amazonaws.com/rrfs_a/rrfs.20260524" in plan.grib2_url


def test_rtma_url_builder_2p5km_analysis() -> None:
    """RTMA 2.5-km analysis lives under ``/rtma2p5.{YYYYMMDD}/`` on noaa-rtma-pds."""
    plan = build_fetch_plan(
        model="rtma",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=0,
    )
    assert "noaa-rtma-pds.s3.amazonaws.com/rtma2p5.20260524" in plan.grib2_url


def test_urma_url_builder_2p5km_analysis() -> None:
    """URMA 2.5-km analysis lives under ``/urma2p5.{YYYYMMDD}/`` on noaa-urma-pds."""
    plan = build_fetch_plan(
        model="urma",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=0,
    )
    assert "noaa-urma-pds.s3.amazonaws.com/urma2p5.20260524" in plan.grib2_url


@pytest.mark.parametrize("model", ["rtma", "urma"])
def test_analysis_models_reject_nonzero_fxx(model: str) -> None:
    """Phase 17 Wave-2 iter-1 review: RTMA / URMA are analysis products
    (single time). ``build_fetch_plan`` must reject nonzero ``fxx`` so
    callers don't silently get rows whose ``valid_at`` is shifted while
    the GRIB bytes remain the analysis cycle.
    """
    with pytest.raises(ValueError, match="analysis product"):
        build_fetch_plan(
            model=model,
            mirror="aws_bdp",
            cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
            fxx=1,
        )


@pytest.mark.parametrize("model", ["rtma", "urma"])
def test_analysis_models_accept_fxx_zero(model: str) -> None:
    """Phase 17 Wave-2 iter-1 review: the legal ``fxx=0`` path still works."""
    plan = build_fetch_plan(
        model=model,
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=0,
    )
    assert plan.fxx == 0
    assert plan.model == model


def test_cfs_url_builder_member_kind_valid_date_kwargs() -> None:
    """CFS path encodes member + kind + valid_date as required kwargs."""
    plan = build_fetch_plan(
        model="cfs",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 0, tzinfo=UTC),
        fxx=6,
        member="01",
        kind="flxf",
        valid_date="20260524",
    )
    assert "noaa-cfs-pds.s3.amazonaws.com/cfs.20260524/00/6hrly_grib_01" in plan.grib2_url


# ---------------------------------------------------------------------------
# Per-model dispatch table wiring
# ---------------------------------------------------------------------------


def test_sources_by_model_for_ncep_family() -> None:
    """SOURCES_BY_MODEL has the 8 NCEP entries; RRFS is AWS-only."""
    assert SOURCES_BY_MODEL["hrrrak"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["gefs"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["gdas"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["rap"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["rrfs"] == ("aws_bdp",)  # AWS-only
    assert SOURCES_BY_MODEL["rtma"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["urma"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["cfs"] == ("aws_bdp", "nomads")


def test_idx_suffix_and_style_all_wgrib2_for_ncep() -> None:
    """All 8 NCEP models use the wgrib2 colon-text ``.idx`` companion."""
    for model in ("hrrrak", "gefs", "gdas", "rap", "rrfs", "rtma", "urma", "cfs"):
        assert IDX_SUFFIX_BY_MODEL[model] == (".idx",), model
        assert IDX_STYLE_BY_MODEL[model] == "wgrib2", model


# ---------------------------------------------------------------------------
# Per-model member enums
# ---------------------------------------------------------------------------


def test_gefs_members_frozenset_has_33_values() -> None:
    """GEFS ensemble has 30 perturbed + 1 control + 2 stats (avg, spread) = 33."""
    from mostlyright.weather._fetchers._nwp_grids.gefs import GEFS_MEMBERS

    expected = frozenset({"c00", "avg", "spr"} | {f"p{i:02d}" for i in range(1, 31)})
    assert expected == GEFS_MEMBERS
    assert len(GEFS_MEMBERS) == 33


def test_cfs_members_frozenset_has_4_values() -> None:
    """CFS ensemble has 4 members 01..04 (one per 6h cycle of the day)."""
    from mostlyright.weather._fetchers._nwp_grids.cfs import CFS_MEMBERS

    assert frozenset({"01", "02", "03", "04"}) == CFS_MEMBERS


def test_rrfs_ensemble_members_frozenset_has_5_values() -> None:
    """RRFS ensemble has 5 members m001..m005."""
    from mostlyright.weather._fetchers._nwp_grids.rrfs import RRFS_ENSEMBLE_MEMBERS

    assert frozenset({"m001", "m002", "m003", "m004", "m005"}) == RRFS_ENSEMBLE_MEMBERS


# ---------------------------------------------------------------------------
# Public surface — SUPPORTED_NWP_MODELS extension
# ---------------------------------------------------------------------------


def test_supported_nwp_models_includes_ncep_family() -> None:
    """The closed allow-list in _nwp_archive includes the 8 NCEP models."""
    for model in ("hrrrak", "gefs", "gdas", "rap", "rrfs", "rtma", "urma", "cfs"):
        assert model in SUPPORTED_NWP_MODELS, model


def test_public_supported_nwp_models_includes_ncep_family() -> None:
    """PLAN-03 — public ``mostlyright.forecasts.SUPPORTED_NWP_MODELS``
    surface includes the 8 NCEP family entries.

    The schema enum :data:`NWP_MODEL_VALUES` predeclares all 24 Phase-17
    model ids day-one so ``schema_id`` survives the catalog growth
    (additive doctrine). The public-surface set tracks the predeclared
    enum — PLAN-04 / -05 / -06 wire the additional families end-to-end
    one plan at a time.
    """
    from mostlyright.forecasts import SUPPORTED_NWP_MODELS as PUBLIC

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
    missing = expected_ncep - set(PUBLIC)
    assert not missing, f"missing NCEP entries in public surface: {missing}"
    # v0.1.0 (Phase 3.2) entries survive.
    assert {"hrrr", "gfs", "nbm"} <= set(PUBLIC)


# ---------------------------------------------------------------------------
# get_variable_map / get_grid_kind dispatch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    ["hrrrak", "gefs", "gdas", "rap", "rrfs", "rtma", "urma", "cfs"],
)
def test_get_variable_map_for_ncep_model(model: str) -> None:
    """``_nwp_grids.get_variable_map(model)`` returns a non-empty dict."""
    from mostlyright.weather._fetchers._nwp_grids import (
        get_grid_kind,
        get_variable_map,
    )

    vm = get_variable_map(model)
    assert isinstance(vm, dict)
    assert vm, f"variable map for {model} should not be empty"
    # Every entry is (variable, level) — both non-empty strings.
    for col, (var, level) in vm.items():
        assert isinstance(col, str) and col
        assert isinstance(var, str) and var
        assert isinstance(level, str) and level
    # GRID_KIND is a non-empty label.
    gk = get_grid_kind(model)
    assert isinstance(gk, str) and gk


# ---------------------------------------------------------------------------
# Phase 17 Wave-2 iter-1 review hardening.
# ---------------------------------------------------------------------------


def test_cfs_path_derives_valid_date_from_cycle_plus_fxx() -> None:
    """``forecast_nwp("KNYC", "cfs")`` calls build_fetch_plan with no
    per-model kwargs — ``_cfs_path`` must compute ``valid_date`` from
    ``cycle + fxx`` so the URL doesn't contain an empty placeholder.
    """
    plan = build_fetch_plan(
        model="cfs",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 0, tzinfo=UTC),
        fxx=24,  # 24 hours forward → valid date 2026-05-25
    )
    assert "flxf20260525.01.2026052400.grb2" in plan.grib2_url


def test_default_cycle_for_gefs_is_6_hourly() -> None:
    """Phase 17 iter-1: GEFS / GDAS / CFS are 6-hourly (synoptic-scale).

    Before iter-1 only GFS was treated as 6-hourly; GEFS/GDAS/CFS would
    floor to invalid hourly cycles. _CYCLE_FREQUENCY_HOURS registry
    fixes the dispatch.
    """
    from mostlyright.weather.forecast_nwp import (
        _CYCLE_FREQUENCY_HOURS,
        _default_cycle_for,
    )

    assert _CYCLE_FREQUENCY_HOURS["gefs"] == 6
    assert _CYCLE_FREQUENCY_HOURS["gdas"] == 6
    assert _CYCLE_FREQUENCY_HOURS["cfs"] == 6
    # Deterministic: now = 2026-05-24 12:00 UTC, fxx=1 → upper bound
    # = 10:30, floored to 6-hourly grid → 06:00.
    now = datetime(2026, 5, 24, 12, tzinfo=UTC)
    cycle = _default_cycle_for("gefs", fxx=1, now=now)
    assert cycle.hour == 6
    assert cycle.minute == 0


def test_default_cycle_for_hrrrak_is_3_hourly() -> None:
    """HRRRAK runs every 3 hours (Phase 17 RESEARCH §10)."""
    from mostlyright.weather.forecast_nwp import _CYCLE_FREQUENCY_HOURS

    assert _CYCLE_FREQUENCY_HOURS["hrrrak"] == 3


def test_default_cycle_for_gdps_is_12_hourly() -> None:
    """GDPS / GEPS / HiResW run twice per day (00 / 12 Z only)."""
    from mostlyright.weather.forecast_nwp import _CYCLE_FREQUENCY_HOURS

    assert _CYCLE_FREQUENCY_HOURS["gdps"] == 12
    assert _CYCLE_FREQUENCY_HOURS["geps"] == 12
    assert _CYCLE_FREQUENCY_HOURS["hiresw"] == 12
