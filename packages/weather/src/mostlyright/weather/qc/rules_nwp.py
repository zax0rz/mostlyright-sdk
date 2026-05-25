"""Per-model NWP QC physics-bounds rule registry (Phase 17 PLAN-10, FORECAST-19).

Replaces the Phase 3.2 inline ``_qc_status_for_row`` (HRRR/GFS/NBM uniform)
with a per-model registry. Per-family inheritance:

- ``RULES_NWP_NCEP`` — 7 baseline rules (temp / dewpoint / RH / gust /
  precip mm/h / surface pressure / MSLP).
- ``RULES_NWP_ECMWF`` — NCEP base + ``precip_m_total`` rule (ECMWF tp is
  METERS, not mm — > 0.305 m/h flagged; < 0 suspect).
- ``RULES_NWP_GEFS`` — NCEP base + ensemble-dispersion placeholder
  (full member-aware aggregation lands in v1.1).
- ``RULES_NWP_HAFS`` — NCEP base + storm-basin-latitude sanity
  (HAFS basins are 0..60 N; outside is sensor error).
- ``RULES_NWP_MSC_HRDPS`` — NCEP base + regional-grid bounds
  (HRDPS continental covers N. America; ``grid_dist_km > 50`` likely
  outside domain).

Worst-case: ``suspect`` > ``flagged`` > ``clean``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

QCStatus = Literal["clean", "flagged", "suspect"]


@dataclass(frozen=True)
class QCRule:
    """A single physics-bounds rule.

    Attributes:
        name: Stable identifier for telemetry / rule-fired counters.
        column: Canonical column the rule reads (for documentation).
        predicate: ``row -> "clean" | "flagged" | "suspect"``.
        rationale: Human-readable why-this-rule-exists.
    """

    name: str
    column: str
    predicate: Callable[[dict[str, Any]], QCStatus]
    rationale: str


def _worst(statuses: list[QCStatus]) -> QCStatus:
    if "suspect" in statuses:
        return "suspect"
    if "flagged" in statuses:
        return "flagged"
    return "clean"


def apply_rules(rules: list[QCRule], row: dict[str, Any]) -> QCStatus:
    """Apply ``rules`` to ``row`` and return the worst-case status."""
    return _worst([rule.predicate(row) for rule in rules])


# ---------------------------------------------------------------------------
# NCEP base predicates — lifted verbatim from Phase 3.2 forecast_nwp inline.
# ---------------------------------------------------------------------------


def _temp_k_2m_rule(row: dict[str, Any]) -> QCStatus:
    t = row.get("temp_k_2m")
    if t is None:
        return "clean"
    try:
        t = float(t)
    except (TypeError, ValueError):
        return "clean"
    if t <= 0 or t >= 400:
        return "suspect"
    if t < 180 or t > 340:
        return "flagged"
    return "clean"


def _dewpoint_vs_temp_rule(row: dict[str, Any]) -> QCStatus:
    """Phase 3.2 baseline: dewpoint <= 0 K or >= 400 K is non-physical
    (suspect); dewpoint > temperature + 1 is impossible at the same point
    (flagged). Both checks collapse into the worst per-rule verdict."""
    dp = row.get("dewpoint_k_2m")
    t = row.get("temp_k_2m")
    if dp is None:
        return "clean"
    try:
        dp_f = float(dp)
    except (TypeError, ValueError):
        return "clean"
    if dp_f <= 0 or dp_f >= 400:
        return "suspect"
    if t is None:
        return "clean"
    try:
        if dp_f > float(t) + 1:
            return "flagged"
    except (TypeError, ValueError):
        pass
    return "clean"


def _rh_rule(row: dict[str, Any]) -> QCStatus:
    """Phase 3.2 baseline: RH outside [-5, 110] is suspect; outside
    [0, 105] is flagged. Both checks fire so the worst-case status is
    returned by the row, but a single rule must collapse them into
    one verdict — use suspect if it triggers, otherwise flagged.
    """
    rh = row.get("relative_humidity_pct_2m")
    if rh is None:
        return "clean"
    try:
        rh = float(rh)
    except (TypeError, ValueError):
        return "clean"
    if rh < -5 or rh > 110:
        return "suspect"
    if rh < 0 or rh > 105:
        return "flagged"
    return "clean"


def _wind_gust_rule(row: dict[str, Any]) -> QCStatus:
    """Phase 3.2 baseline: negative gust is non-physical (suspect);
    gust > 90 m/s (~ 200 mph) is flagged but plausible (Hurricane Patricia
    peak gust was ~95 m/s)."""
    g = row.get("wind_gust_ms")
    if g is None:
        return "clean"
    try:
        g = float(g)
    except (TypeError, ValueError):
        return "clean"
    if g < 0:
        return "suspect"
    if g > 90:
        return "flagged"
    return "clean"


def _precip_mm_1h_rule(row: dict[str, Any]) -> QCStatus:
    """Phase 3.2 baseline: negative precip is non-physical (suspect);
    > 305 mm/h exceeds world hourly record (flagged)."""
    p = row.get("precip_mm_1h")
    if p is None:
        return "clean"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "clean"
    if p < 0:
        return "suspect"
    if p > 305:
        return "flagged"
    return "clean"


def _pres_sfc_rule(row: dict[str, Any]) -> QCStatus:
    """Phase 3.2 baseline: surface P <= 0 is non-physical (suspect);
    outside [50000, 110000] Pa is sensor error (flagged)."""
    p = row.get("pressure_pa_surface")
    if p is None:
        return "clean"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "clean"
    if p <= 0:
        return "suspect"
    if p < 50_000 or p > 110_000:
        return "flagged"
    return "clean"


def _mslp_rule(row: dict[str, Any]) -> QCStatus:
    """Phase 3.2 baseline: MSLP <= 0 is non-physical (suspect);
    outside [87000, 108500] Pa is sensor error (flagged)."""
    p = row.get("pressure_pa_mslp")
    if p is None:
        return "clean"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "clean"
    if p <= 0:
        return "suspect"
    if p < 87_000 or p > 108_500:
        return "flagged"
    return "clean"


RULES_NWP_NCEP: list[QCRule] = [
    QCRule(
        "temp_k_2m_extreme",
        "temp_k_2m",
        _temp_k_2m_rule,
        "World extremes 184-330K; absolute zero 0K; flagged [180,340]",
    ),
    QCRule(
        "dewpoint_vs_temp",
        "dewpoint_k_2m",
        _dewpoint_vs_temp_rule,
        "Dewpoint > air temp + 1°C is physically impossible",
    ),
    QCRule(
        "rh_range",
        "relative_humidity_pct_2m",
        _rh_rule,
        "RH < -5% or > 110% is sensor error",
    ),
    QCRule(
        "wind_gust_max",
        "wind_gust_ms",
        _wind_gust_rule,
        "Wind gust > 90 m/s exceeds Hurricane Patricia peak",
    ),
    QCRule(
        "precip_mm_1h_max",
        "precip_mm_1h",
        _precip_mm_1h_rule,
        "Precip > 305 mm/h exceeds world hourly record",
    ),
    QCRule(
        "pressure_sfc_range",
        "pressure_pa_surface",
        _pres_sfc_rule,
        "Surface P outside [50000, 110000] Pa is sensor error",
    ),
    QCRule(
        "mslp_range",
        "pressure_pa_mslp",
        _mslp_rule,
        "MSLP outside [87000, 108500] Pa is sensor error",
    ),
]


# ---------------------------------------------------------------------------
# ECMWF — NCEP base + tp-meters rule.
# ---------------------------------------------------------------------------


def _ecmwf_precip_m_rule(row: dict[str, Any]) -> QCStatus:
    """ECMWF tp is METERS. > 0.305 m/h = world record flagged; < 0 = suspect."""
    p = row.get("precip_m_total")
    if p is None:
        return "clean"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "clean"
    if p < 0:
        return "suspect"
    if p > 0.305:
        return "flagged"
    return "clean"


RULES_NWP_ECMWF: list[QCRule] = [
    *RULES_NWP_NCEP,
    QCRule(
        "precip_m_total_max",
        "precip_m_total",
        _ecmwf_precip_m_rule,
        "ECMWF tp is meters; >0.305 m/h exceeds world hourly record",
    ),
]


# ---------------------------------------------------------------------------
# GEFS / HREF / REPS — NCEP base + ensemble-dispersion placeholder.
# ---------------------------------------------------------------------------


def _gefs_ensemble_dispersion_rule(row: dict[str, Any]) -> QCStatus:
    """Placeholder. Full cross-member aggregation lands in v1.1."""
    return "clean"


RULES_NWP_GEFS: list[QCRule] = [
    *RULES_NWP_NCEP,
    QCRule(
        "ensemble_dispersion",
        "temp_k_2m",
        _gefs_ensemble_dispersion_rule,
        "Cross-member temp spread > 40K signals broken member (v1.1)",
    ),
]


# ---------------------------------------------------------------------------
# HAFS — NCEP base + basin-position sanity.
# ---------------------------------------------------------------------------


def _hafs_basin_lat_rule(row: dict[str, Any]) -> QCStatus:
    lat = row.get("storm_lat_deg")
    if lat is None:
        return "clean"
    try:
        lat = float(lat)
    except (TypeError, ValueError):
        return "clean"
    if lat < 0 or lat > 60:
        return "suspect"
    return "clean"


RULES_NWP_HAFS: list[QCRule] = [
    *RULES_NWP_NCEP,
    QCRule(
        "storm_lat_in_basin",
        "storm_lat_deg",
        _hafs_basin_lat_rule,
        "HAFS basins are 0-60 N; outside is sensor error",
    ),
]


# ---------------------------------------------------------------------------
# MSC HRDPS — NCEP base + regional grid bounds.
# ---------------------------------------------------------------------------


def _hrdps_domain_rule(row: dict[str, Any]) -> QCStatus:
    d = row.get("grid_dist_km")
    if d is None:
        return "clean"
    try:
        d = float(d)
    except (TypeError, ValueError):
        return "clean"
    if d > 50:
        return "suspect"
    return "clean"


RULES_NWP_MSC_HRDPS: list[QCRule] = [
    *RULES_NWP_NCEP,
    QCRule(
        "hrdps_continental_domain",
        "grid_dist_km",
        _hrdps_domain_rule,
        "HRDPS continental covers N. America; >50km from grid likely outside domain",
    ),
]


# ---------------------------------------------------------------------------
# Per-model registry — all 24 Phase 17 NWP models.
# ---------------------------------------------------------------------------


QC_RULES_NWP: dict[str, list[QCRule]] = {
    # v0.1.0 NCEP
    "hrrr": RULES_NWP_NCEP,
    "gfs": RULES_NWP_NCEP,
    "nbm": RULES_NWP_NCEP,
    # Phase 17 PLAN-03 NCEP family
    "hrrrak": RULES_NWP_NCEP,
    "gdas": RULES_NWP_NCEP,
    "rap": RULES_NWP_NCEP,
    "rrfs": RULES_NWP_NCEP,
    "rtma": RULES_NWP_NCEP,
    "urma": RULES_NWP_NCEP,
    "cfs": RULES_NWP_NCEP,
    "gefs": RULES_NWP_GEFS,
    # Phase 17 PLAN-04 ECMWF
    "ecmwf_ifs_hres": RULES_NWP_ECMWF,
    "ecmwf_ifs_ens": RULES_NWP_ECMWF,
    "ecmwf_aifs_single": RULES_NWP_ECMWF,
    "ecmwf_aifs_ens": RULES_NWP_ECMWF,
    # Phase 17 PLAN-05 MSC Canadian
    "hrdps": RULES_NWP_MSC_HRDPS,
    "rdps": RULES_NWP_NCEP,
    "gdps": RULES_NWP_NCEP,
    "geps": RULES_NWP_GEFS,
    "reps": RULES_NWP_GEFS,
    # Phase 17 PLAN-06 HAFS + legacy
    "hafs": RULES_NWP_HAFS,
    "nam": RULES_NWP_NCEP,
    "href": RULES_NWP_GEFS,
    "hiresw": RULES_NWP_NCEP,
}


__all__ = [
    "QC_RULES_NWP",
    "RULES_NWP_ECMWF",
    "RULES_NWP_GEFS",
    "RULES_NWP_HAFS",
    "RULES_NWP_MSC_HRDPS",
    "RULES_NWP_NCEP",
    "QCRule",
    "QCStatus",
    "apply_rules",
]
