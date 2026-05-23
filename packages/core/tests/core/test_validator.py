"""Unit tests for the source-identity Validator."""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest

# Importing core.schemas triggers eager registration.
import tradewinds.core.schemas  # noqa: F401
from tradewinds.core.exceptions import (
    SchemaValidationError,
    SourceMismatchError,
)
from tradewinds.core.validator import (
    _SCHEMA_REGISTRY,
    register_schema,
    validate_dataframe,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
def _good_observation_df(source: str = "iem.archive") -> pd.DataFrame:
    """A minimal happy-path observation.v1 DataFrame matching ObservationSchema."""
    df = pd.DataFrame(
        {
            "station": ["KNYC", "KNYC"],
            "event_time": pd.to_datetime(
                ["2025-01-01T12:00:00Z", "2025-01-01T13:00:00Z"], utc=True
            ),
            "observation_type": ["METAR", "METAR"],
            "temp_c": [1.0, 2.0],
            "dew_point_c": [-1.0, 0.0],
            "wind_speed_ms": [3.0, 4.0],
            "wind_dir_deg": pd.array([180, 190], dtype="Int64"),
            "wind_gust_ms": pd.array([np.nan, 6.0], dtype="float64"),
            "slp_hpa": [1013.0, 1013.5],
            "visibility_m": [10000.0, 10000.0],
            "precip_mm_1h": [0.0, 0.0],
            "sky_cover_1": ["CLR", "CLR"],
            "sky_base_1_m": pd.array([np.nan, np.nan], dtype="float64"),
            "sky_cover_2": pd.Series([None, None], dtype="string"),
            "sky_base_2_m": pd.array([np.nan, np.nan], dtype="float64"),
            "sky_cover_3": pd.Series([None, None], dtype="string"),
            "sky_base_3_m": pd.array([np.nan, np.nan], dtype="float64"),
            "sky_cover_4": pd.Series([None, None], dtype="string"),
            "sky_base_4_m": pd.array([np.nan, np.nan], dtype="float64"),
            "metar_raw": ["METAR ...", "METAR ..."],
        }
    )
    df.attrs["source"] = source
    df.attrs["retrieved_at"] = datetime(2025, 1, 1, 13, tzinfo=UTC)
    return df


# ----------------------------------------------------------------------
# Schema registration
# ----------------------------------------------------------------------
def test_canonical_schemas_eagerly_registered():
    """Importing tradewinds.core.schemas registers all 3 canonical schemas."""
    assert "schema.observation.v1" in _SCHEMA_REGISTRY
    assert "schema.forecast.iem_mos.v1" in _SCHEMA_REGISTRY
    assert "schema.settlement.cli.v1" in _SCHEMA_REGISTRY


def test_canonical_schemas_have_registered_source():
    """Each canonical schema has a non-None ``_registered_source``."""
    from tradewinds.core.schemas import (
        ForecastSchema,
        ObservationSchema,
        SettlementSchema,
    )

    assert ObservationSchema._registered_source == "iem.archive"
    assert ForecastSchema._registered_source == "iem.archive"
    assert SettlementSchema._registered_source == "cli.archive"


def test_register_schema_idempotent():
    """Re-registering the same class is a no-op."""
    from tradewinds.core.schemas import ObservationSchema

    register_schema(ObservationSchema)
    register_schema(ObservationSchema)
    assert _SCHEMA_REGISTRY["schema.observation.v1"] is ObservationSchema


def test_register_schema_conflict_raises():
    """Registering a different class to an existing ID raises."""
    from tradewinds.core.schema import Schema

    class FakeObservation(Schema):
        schema_id = "schema.observation.v1"

    with pytest.raises(ValueError, match="already registered"):
        register_schema(FakeObservation)


def test_register_schema_empty_id_raises():
    from tradewinds.core.schema import Schema

    class Anon(Schema):
        schema_id = ""

    with pytest.raises(ValueError, match="schema_id is empty"):
        register_schema(Anon)


# ----------------------------------------------------------------------
# Source-identity invariant
# ----------------------------------------------------------------------
class TestSourceIdentity:
    def test_happy_path_iem_archive(self):
        df = _good_observation_df(source="iem.archive")
        reg = validate_dataframe(df, "schema.observation.v1")
        assert reg.source == "iem.archive"
        assert reg.rows == 2

    def test_source_mismatch_raises(self):
        df = _good_observation_df(source="awc.archive")
        with pytest.raises(SourceMismatchError) as exc:
            validate_dataframe(df, "schema.observation.v1")
        assert exc.value.schema_source == "iem.archive"
        assert exc.value.data_source == "awc.archive"

    def test_source_drift_allowed_no_raise(self):
        df = _good_observation_df(source="awc.archive")
        reg = validate_dataframe(
            df,
            "schema.observation.v1",
            allow_source_drift="parity backfill from AWC",
        )
        assert reg.source == "awc.archive"
        # Audit log carries both 'registered' (from Schema.register) and
        # 'source_drift_allowed' from the Validator.
        events = [e["event"] for e in reg.audit_log()]
        assert "source_drift_allowed" in events

    def test_missing_source_attr_raises_schema_error(self):
        df = _good_observation_df(source="iem.archive")
        df.attrs.pop("source")
        with pytest.raises(SchemaValidationError) as exc:
            validate_dataframe(df, "schema.observation.v1")
        assert "source" in str(exc.value).lower()

    def test_unknown_schema_id_raises(self):
        df = _good_observation_df()
        with pytest.raises(SchemaValidationError, match="Unknown schema_id"):
            validate_dataframe(df, "schema.nonexistent.v1")


# ----------------------------------------------------------------------
# Column / dtype / enum / null checks
# ----------------------------------------------------------------------
class TestColumnValidation:
    def test_missing_required_column_raises(self):
        df = _good_observation_df()
        df = df.drop(columns=["station"])
        df.attrs["source"] = "iem.archive"
        with pytest.raises(SchemaValidationError) as exc:
            validate_dataframe(df, "schema.observation.v1")
        violations = exc.value.violations
        assert any(
            v["column"] == "station" and v["rule"] == "required_column_missing" for v in violations
        )

    def test_dtype_mismatch_raises(self):
        df = _good_observation_df()
        # event_time should be timestamp_utc; replace with object strings.
        df["event_time"] = ["2025-01-01", "2025-01-02"]
        df.attrs["source"] = "iem.archive"
        with pytest.raises(SchemaValidationError) as exc:
            validate_dataframe(df, "schema.observation.v1")
        assert any(v.get("rule") == "dtype_mismatch" for v in exc.value.violations)

    def test_enum_value_violation_collected(self):
        df = _good_observation_df()
        df["observation_type"] = ["METAR", "NOPE"]
        df.attrs["source"] = "iem.archive"
        with pytest.raises(SchemaValidationError) as exc:
            validate_dataframe(df, "schema.observation.v1")
        v = next(v for v in exc.value.violations if v["rule"] == "enum_value_violation")
        assert v["count"] == 1
        assert v["sample"][0]["value"] == "NOPE"

    def test_non_nullable_null_raises(self):
        df = _good_observation_df()
        df.loc[0, "station"] = None
        df.attrs["source"] = "iem.archive"
        with pytest.raises(SchemaValidationError) as exc:
            validate_dataframe(df, "schema.observation.v1")
        v = next(
            v
            for v in exc.value.violations
            if v["rule"] == "non_nullable_has_nulls" and v["column"] == "station"
        )
        assert v["count"] == 1

    def test_nullable_column_with_nulls_ok(self):
        df = _good_observation_df()
        df["wind_gust_ms"] = pd.array([np.nan, np.nan], dtype="float64")
        df.attrs["source"] = "iem.archive"
        reg = validate_dataframe(df, "schema.observation.v1")
        assert reg.rows == 2

    def test_mixed_null_sentinels_flagged(self):
        """Pitfall 15 — pd.NA + np.nan in same object column flagged."""
        df = _good_observation_df()
        # Construct an object-dtype column containing both pd.NA and np.nan.
        df["metar_raw"] = pd.Series([np.nan, pd.NA], dtype="object")
        df.attrs["source"] = "iem.archive"
        # metar_raw is nullable — null-rule passes; mixed sentinels still flags.
        with pytest.raises(SchemaValidationError) as exc:
            validate_dataframe(df, "schema.observation.v1")
        assert any(v["rule"] == "mixed_null_sentinels" for v in exc.value.violations)


# ----------------------------------------------------------------------
# Settlement schema
# ----------------------------------------------------------------------
def _good_settlement_df(source: str = "cli.archive") -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "station": ["KNYC"],
            "station_tz": ["America/New_York"],
            "observation_date": [date(2025, 1, 1)],
            "event_time": pd.to_datetime(["2025-01-01T05:00:00Z"], utc=True),
            "product_release_time": pd.to_datetime(["2025-01-02T13:00:00Z"], utc=True),
            "report_type": ["final"],
            "temp_max_F": [35.0],
            "temp_min_F": [22.0],
            "precipitation_in": [0.0],
            "snowfall_in": [0.0],
            "cli_data_quality": ["clean"],
            "settlement_finality": ["final"],
        }
    )
    df.attrs["source"] = source
    df.attrs["retrieved_at"] = datetime(2025, 1, 2, 13, tzinfo=UTC)
    return df


def test_settlement_happy_path():
    df = _good_settlement_df()
    reg = validate_dataframe(df, "schema.settlement.cli.v1")
    assert reg.source == "cli.archive"
    assert reg.rows == 1


def test_settlement_finality_enum_violation():
    df = _good_settlement_df()
    df["settlement_finality"] = ["INVALID"]
    df.attrs["source"] = "cli.archive"
    with pytest.raises(SchemaValidationError) as exc:
        validate_dataframe(df, "schema.settlement.cli.v1")
    assert any(
        v["column"] == "settlement_finality" and v["rule"] == "enum_value_violation"
        for v in exc.value.violations
    )


def test_settlement_cli_data_quality_enum_violation():
    df = _good_settlement_df()
    df["cli_data_quality"] = ["bogus"]
    df.attrs["source"] = "cli.archive"
    with pytest.raises(SchemaValidationError) as exc:
        validate_dataframe(df, "schema.settlement.cli.v1")
    assert any(
        v["column"] == "cli_data_quality" and v["rule"] == "enum_value_violation"
        for v in exc.value.violations
    )


# ----------------------------------------------------------------------
# Audit log integration
# ----------------------------------------------------------------------
def test_registration_audit_log_includes_registered():
    df = _good_observation_df()
    reg = validate_dataframe(df, "schema.observation.v1")
    events = [e["event"] for e in reg.audit_log()]
    assert "registered" in events


def test_source_drift_audit_log_includes_reason():
    df = _good_observation_df(source="ghcnh.archive")
    reg = validate_dataframe(
        df,
        "schema.observation.v1",
        allow_source_drift="historical fill from GHCNh",
    )
    drift_events = [e for e in reg.audit_log() if e["event"] == "source_drift_allowed"]
    assert len(drift_events) == 1
    assert drift_events[0]["reason"] == "historical fill from GHCNh"
    assert drift_events[0]["schema_source"] == "iem.archive"
    assert drift_events[0]["data_source"] == "ghcnh.archive"


# ----------------------------------------------------------------------
# Retrieved_at provenance (codex iter-2 HIGH fix)
# ----------------------------------------------------------------------
def test_missing_retrieved_at_falls_back_to_column():
    """When attrs lack retrieved_at, the per-row 'retrieved_at' column wins."""
    df = _good_observation_df()
    df.attrs.pop("retrieved_at", None)
    # Add a per-row retrieved_at column (catalog adapters always populate this).
    df["retrieved_at"] = pd.to_datetime(["2025-01-01T13:00:00Z", "2025-01-01T13:00:00Z"], utc=True)
    reg = validate_dataframe(df, "schema.observation.v1")
    # Validator uses max() of the column as the registration timestamp.
    assert reg.retrieved_at_min == datetime(2025, 1, 1, 13, tzinfo=UTC)


def test_missing_retrieved_at_attrs_AND_column_raises():
    """Validator MUST NOT fabricate retrieved_at if neither source is present."""
    df = _good_observation_df()
    df.attrs.pop("retrieved_at", None)
    # No per-row retrieved_at column either.
    with pytest.raises(SchemaValidationError, match="provenance"):
        validate_dataframe(df, "schema.observation.v1")


# ----------------------------------------------------------------------
# Per-row source-column check (codex iter-2 HIGH fix)
# ----------------------------------------------------------------------
def test_per_row_source_mismatch_raises():
    """If df has a 'source' column with rows not matching df.attrs['source'],
    the validator raises SourceMismatchError listing the distinct bad values.
    """
    from tradewinds.core.exceptions import SourceMismatchError

    df = _good_observation_df(source="iem.archive")
    df["source"] = ["iem.archive", "awc.live"]  # second row mismatches.
    with pytest.raises(SourceMismatchError) as exc:
        validate_dataframe(df, "schema.observation.v1")
    assert "awc.live" in str(exc.value)


def test_per_row_source_all_match_passes():
    """All rows matching df.attrs['source'] is the happy path."""
    df = _good_observation_df(source="iem.archive")
    df["source"] = ["iem.archive", "iem.archive"]
    reg = validate_dataframe(df, "schema.observation.v1")
    assert reg.source == "iem.archive"
