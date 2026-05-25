"""Phase 17 PLAN-10 — per-model NWP QC physics-bounds registry."""

from __future__ import annotations

import pytest
from mostlyright.weather.qc.rules_nwp import (
    QC_RULES_NWP,
    RULES_NWP_ECMWF,
    RULES_NWP_GEFS,
    RULES_NWP_HAFS,
    RULES_NWP_MSC_HRDPS,
    RULES_NWP_NCEP,
    QCRule,
    apply_rules,
)


def test_registry_has_24_entries() -> None:
    assert len(QC_RULES_NWP) == 24


def test_registry_includes_all_phase17_models() -> None:
    expected = {
        # v0.1.0
        "hrrr",
        "gfs",
        "nbm",
        # NCEP family (PLAN-03)
        "hrrrak",
        "gefs",
        "gdas",
        "rap",
        "rrfs",
        "rtma",
        "urma",
        "cfs",
        # ECMWF family (PLAN-04)
        "ecmwf_ifs_hres",
        "ecmwf_ifs_ens",
        "ecmwf_aifs_single",
        "ecmwf_aifs_ens",
        # MSC family (PLAN-05)
        "hrdps",
        "rdps",
        "gdps",
        "geps",
        "reps",
        # HAFS + legacy (PLAN-06)
        "hafs",
        "nam",
        "href",
        "hiresw",
    }
    assert set(QC_RULES_NWP.keys()) == expected


def test_ncep_base_has_7_rules() -> None:
    assert len(RULES_NWP_NCEP) == 7
    rule_names = {r.name for r in RULES_NWP_NCEP}
    assert {
        "temp_k_2m_extreme",
        "dewpoint_vs_temp",
        "rh_range",
        "wind_gust_max",
        "precip_mm_1h_max",
        "pressure_sfc_range",
        "mslp_range",
    } == rule_names


def test_ncep_temp_in_range_returns_clean() -> None:
    assert apply_rules(RULES_NWP_NCEP, {"temp_k_2m": 300.0}) == "clean"


def test_ncep_temp_flagged_outside_180_340() -> None:
    assert apply_rules(RULES_NWP_NCEP, {"temp_k_2m": 100.0}) == "flagged"


def test_ncep_temp_suspect_outside_0_400() -> None:
    assert apply_rules(RULES_NWP_NCEP, {"temp_k_2m": -10.0}) == "suspect"


def test_ncep_dewpoint_greater_than_temp_flagged() -> None:
    result = apply_rules(RULES_NWP_NCEP, {"temp_k_2m": 290.0, "dewpoint_k_2m": 295.0})
    assert result == "flagged"


def test_ncep_wind_gust_extreme_flagged() -> None:
    assert apply_rules(RULES_NWP_NCEP, {"wind_gust_ms": 100.0}) == "flagged"


def test_ecmwf_inherits_ncep_temp_rule() -> None:
    """ECMWF rule list is NCEP base + 1 extension."""
    assert len(RULES_NWP_ECMWF) == 8
    assert apply_rules(RULES_NWP_ECMWF, {"temp_k_2m": -10.0}) == "suspect"


def test_ecmwf_tp_meters_flagged_above_0_305() -> None:
    """ECMWF precip_m_total > 0.305 m/h → flagged (world hourly record)."""
    assert apply_rules(RULES_NWP_ECMWF, {"precip_m_total": 0.5}) == "flagged"


def test_ecmwf_tp_meters_negative_suspect() -> None:
    """Negative precip is a decode bug."""
    assert apply_rules(RULES_NWP_ECMWF, {"precip_m_total": -0.1}) == "suspect"


def test_gefs_inherits_ncep_plus_ensemble_dispersion() -> None:
    assert len(RULES_NWP_GEFS) == 8
    # NCEP rules still fire.
    assert apply_rules(RULES_NWP_GEFS, {"temp_k_2m": 100.0}) == "flagged"


def test_hafs_inherits_ncep_plus_basin_lat() -> None:
    assert len(RULES_NWP_HAFS) == 8
    # NCEP rules still fire.
    assert apply_rules(RULES_NWP_HAFS, {"temp_k_2m": -10.0}) == "suspect"


def test_hafs_storm_lat_outside_basin_suspect() -> None:
    """HAFS basins are 0..60 N; lat=75 is outside (sensor error)."""
    assert apply_rules(RULES_NWP_HAFS, {"storm_lat_deg": 75.0}) == "suspect"


def test_msc_hrdps_inherits_ncep_plus_domain() -> None:
    assert len(RULES_NWP_MSC_HRDPS) == 8


def test_msc_hrdps_grid_dist_outside_domain_suspect() -> None:
    """HRDPS continental covers N. America; >50km → suspect."""
    assert apply_rules(RULES_NWP_MSC_HRDPS, {"grid_dist_km": 100.0}) == "suspect"


def test_apply_rules_returns_worst_case() -> None:
    """suspect > flagged > clean."""
    # temp=100 (flagged) AND dewpoint>temp (flagged) → flagged
    flagged_only = apply_rules(RULES_NWP_NCEP, {"temp_k_2m": 100.0, "dewpoint_k_2m": 150.0})
    assert flagged_only == "flagged"
    # temp=-10 (suspect) wins even with flagged rules also firing
    mixed = apply_rules(RULES_NWP_NCEP, {"temp_k_2m": -10.0, "wind_gust_ms": 100.0})
    assert mixed == "suspect"


def test_apply_rules_empty_row_returns_clean() -> None:
    assert apply_rules(RULES_NWP_NCEP, {}) == "clean"


def test_qc_rule_is_frozen_dataclass() -> None:
    rule = RULES_NWP_NCEP[0]
    assert isinstance(rule, QCRule)
    with pytest.raises(Exception):
        rule.name = "mutated"  # type: ignore[misc]
