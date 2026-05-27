"""Phase 20 OM-03: 36-model registry — completeness + family-level invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mostlyright.weather._fetchers._open_meteo_models import (
    AVAILABILITY_FLOOR,
    CYCLE_HOURS,
    OPEN_METEO_MODELS,
    PUBLISH_LAG,
    asia_oceania,
    dwd,
    ecmwf,
    europe,
    gem,
    meteofrance,
    ncep,
)

EXPECTED_36_MODELS: frozenset[str] = frozenset(
    {
        # NCEP (8)
        "gfs_seamless",
        "gfs_global",
        "gfs_graphcast025",
        "aigfs025",
        "hgefs025",
        "ncep_hrrr_conus",
        "ncep_nbm_conus",
        "ncep_nam_conus",
        # ECMWF (3)
        "ecmwf_ifs025",
        "ecmwf_ifs_hres",
        "ecmwf_aifs025_single",
        # DWD (5)
        "dwd_icon_seamless",
        "dwd_icon_global",
        "dwd_icon_eu",
        "dwd_icon_d2",
        "dwd_icon_d2_15min",
        # Météo-France (6)
        "meteofrance_seamless",
        "meteofrance_arpege_world025",
        "meteofrance_arpege_europe",
        "meteofrance_arome_france0025",
        "meteofrance_arome_france_hd",
        "meteofrance_arome_france_hd_15min",
        # Asia / Oceania (8)
        "jma_seamless",
        "jma_gsm",
        "jma_msm",
        "kma_seamless",
        "kma_gdps",
        "kma_ldps",
        "cma_grapes_global",
        "bom_access_global",
        # Europe (3)
        "ukmo_global_deterministic_10km",
        "ukmo_uk_deterministic_2km",
        "metno_nordic_pp",
        # GEM Canada (3)
        "cmc_gem_gdps",
        "cmc_gem_rdps",
        "cmc_gem_hrdps",
    }
)


def test_open_meteo_models_total_count_is_36() -> None:
    """Phase 20 D-02: 36 models verified per open-meteo-data README."""
    assert len(OPEN_METEO_MODELS) == 36, (
        f"expected 36 models, got {len(OPEN_METEO_MODELS)}: {sorted(OPEN_METEO_MODELS)}"
    )


def test_open_meteo_models_exact_set_equality() -> None:
    """Python/TS lockstep — set equality, not just count equality."""
    assert OPEN_METEO_MODELS == EXPECTED_36_MODELS, (
        f"missing: {EXPECTED_36_MODELS - OPEN_METEO_MODELS}, "
        f"extra: {OPEN_METEO_MODELS - EXPECTED_36_MODELS}"
    )


def test_open_meteo_models_is_frozenset() -> None:
    assert isinstance(OPEN_METEO_MODELS, frozenset)


def test_every_model_has_cycle_hours_availability_publish_lag() -> None:
    missing_cycle = OPEN_METEO_MODELS - set(CYCLE_HOURS.keys())
    missing_avail = OPEN_METEO_MODELS - set(AVAILABILITY_FLOOR.keys())
    missing_lag = OPEN_METEO_MODELS - set(PUBLISH_LAG.keys())
    assert not missing_cycle, f"CYCLE_HOURS missing keys: {missing_cycle}"
    assert not missing_avail, f"AVAILABILITY_FLOOR missing keys: {missing_avail}"
    assert not missing_lag, f"PUBLISH_LAG missing keys: {missing_lag}"


def test_no_duplicate_keys_across_families() -> None:
    families = [
        ncep.MODELS,
        ecmwf.MODELS,
        dwd.MODELS,
        meteofrance.MODELS,
        asia_oceania.MODELS,
        europe.MODELS,
        gem.MODELS,
    ]
    seen: set[str] = set()
    for fam in families:
        overlap = seen & fam
        assert not overlap, f"models in multiple families: {overlap}"
        seen |= fam


def test_ncep_keys_prefix() -> None:
    for key in ncep.MODELS:
        assert key.startswith(("gfs_", "aigfs", "hgefs", "ncep_")), key


def test_ecmwf_keys_prefix() -> None:
    for key in ecmwf.MODELS:
        assert key.startswith("ecmwf_"), key


def test_dwd_keys_prefix() -> None:
    for key in dwd.MODELS:
        assert key.startswith("dwd_"), key


def test_meteofrance_keys_prefix() -> None:
    for key in meteofrance.MODELS:
        assert key.startswith("meteofrance_"), key


def test_gfs_family_cycle_hours_00_06_12_18() -> None:
    for key in (
        "gfs_global",
        "gfs_seamless",
        "gfs_graphcast025",
        "aigfs025",
        "hgefs025",
        "ncep_nam_conus",
    ):
        assert CYCLE_HOURS[key] == (0, 6, 12, 18), f"{key}: {CYCLE_HOURS[key]}"


def test_hrrr_cycle_hours_hourly() -> None:
    assert CYCLE_HOURS["ncep_hrrr_conus"] == tuple(range(24))


def test_ecmwf_ifs_hres_cycle_hours() -> None:
    cycles = CYCLE_HOURS["ecmwf_ifs_hres"]
    assert set(cycles).issuperset({0, 12}), f"missing core cycles: {cycles}"


def test_availability_floor_gfs_global_after_2024_01() -> None:
    assert AVAILABILITY_FLOOR["gfs_global"] >= datetime(2024, 1, 1, tzinfo=UTC)


def test_availability_floor_jma_models_2018_or_earlier() -> None:
    assert AVAILABILITY_FLOOR["jma_gsm"] <= datetime(2018, 12, 31, tzinfo=UTC)


def test_publish_lag_global_models_6h() -> None:
    for key in (
        "gfs_global",
        "ecmwf_ifs_hres",
        "jma_gsm",
        "kma_gdps",
        "cma_grapes_global",
        "bom_access_global",
        "cmc_gem_gdps",
    ):
        assert PUBLISH_LAG[key] == timedelta(hours=6), f"{key}: {PUBLISH_LAG[key]}"


def test_publish_lag_regional_2h() -> None:
    for key in ("ncep_hrrr_conus", "ncep_nbm_conus", "dwd_icon_d2"):
        assert PUBLISH_LAG[key] == timedelta(hours=2), f"{key}: {PUBLISH_LAG[key]}"


def test_publish_lag_midscale_4h() -> None:
    for key in ("dwd_icon_global", "dwd_icon_eu"):
        assert PUBLISH_LAG[key] == timedelta(hours=4), f"{key}: {PUBLISH_LAG[key]}"


def test_publish_lag_only_in_3_conservative_buckets() -> None:
    allowed = {
        timedelta(hours=2),
        timedelta(hours=4),
        timedelta(hours=6),
    }
    bad = {(k, v) for k, v in PUBLISH_LAG.items() if v not in allowed}
    assert not bad, f"publish_lag outside {{2h,4h,6h}}: {bad}"
