"""Phase 17 FORECAST-01: schema.forecast_nwp.v1 enum extension (additive).

INVARIANT: ``schema_id`` MUST NOT change. Adding model values is additive
per the predeclared-doctrine (Phase 3.2 decision #4): every model name
mostlyright will ever serve goes into ``NWP_MODEL_VALUES`` day-one so the
public enum survives every catalog expansion without bumping schema_id.

PLAN-03 ships the NCEP family (8 models). PLAN-01 already predeclared
the rest of Phase 17 catalog expansion (PLAN-04 ECMWF + PLAN-05 MSC +
PLAN-06 HAFS/legacy), so the tuple length is 24 after PLAN-01 already
and PLAN-03 verifies the 8 NCEP entries are present + invariants hold.
"""

from __future__ import annotations

from mostlyright.core.schemas.forecast_nwp import (
    NWP_MODEL_VALUES,
    NwpForecastSchema,
)


def test_nwp_model_values_includes_8_new_ncep_family() -> None:
    """PLAN-03 — the 8 NCEP family models all appear in NWP_MODEL_VALUES."""
    expected_new = {
        "hrrrak",
        "gefs",
        "gdas",
        "rap",
        "rrfs",
        "rtma",
        "urma",
        "cfs",
    }
    missing = expected_new - set(NWP_MODEL_VALUES)
    assert not missing, f"missing PLAN-03 NCEP model values: {missing}"


def test_nwp_model_values_preserves_existing_7() -> None:
    """The pre-Phase-17 7 entries (HRRR + GFS + NBM + 4 ECMWF) survive."""
    expected_existing = {
        "hrrr",
        "gfs",
        "nbm",
        "ecmwf_ifs_hres",
        "ecmwf_ifs_ens",
        "ecmwf_aifs_single",
        "ecmwf_aifs_ens",
    }
    missing = expected_existing - set(NWP_MODEL_VALUES)
    assert not missing, f"missing pre-Phase-17 NWP model values: {missing}"


def test_nwp_model_values_length_after_phase17_full_predeclare() -> None:
    """PLAN-01 already predeclared all 24 Phase-17 entries up-front.

    PLAN-03 verifies the tuple is at least 15 (3 v0.1.0 + 4 ECMWF + 8
    NCEP), AND that it equals 24 (the post-PLAN-01 state where PLAN-04
    ECMWF + PLAN-05 MSC + PLAN-06 HAFS/legacy were all reserved day-one
    so ``schema_id`` survives every Wave-2 plan).
    """
    assert len(NWP_MODEL_VALUES) >= 15, (
        f"expected at least 15 entries (v0.1.0 7 + PLAN-03 NCEP 8); got {len(NWP_MODEL_VALUES)}"
    )
    assert len(NWP_MODEL_VALUES) == 24, (
        f"PLAN-01 reserved all 24 Phase-17 entries day-one; got {len(NWP_MODEL_VALUES)}"
    )


def test_schema_id_unchanged_invariant() -> None:
    """Phase 17 invariant — ``schema_id`` MUST stay ``schema.forecast_nwp.v1``.

    Adding model values is additive (predeclared doctrine, Phase 3.2 #4).
    Any drift here invalidates every historical NWP row mostlyright has
    written under v1.
    """
    assert NwpForecastSchema.schema_id == "schema.forecast_nwp.v1"


def test_model_column_enum_values_match_module_constant() -> None:
    """The ``model`` ColumnSpec.enum_values points at NWP_MODEL_VALUES."""
    model_col = next(c for c in NwpForecastSchema.COLUMNS if c.name == "model")
    assert model_col.dtype == "enum"
    assert model_col.enum_values == NWP_MODEL_VALUES
