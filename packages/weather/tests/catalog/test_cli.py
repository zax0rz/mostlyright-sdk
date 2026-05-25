"""Unit tests for CLIAdapter (NWS CLI settlement)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
import pytest
from mostlyright.weather.catalog import get_adapter
from mostlyright.weather.catalog.cli import CLIAdapter


def _rec(**overrides):
    """A synthetic CLI parser-output dict matching parse_cli_record() shape.

    Uses parser-native keys (high_temp_f, low_temp_f, issued_at) — the
    CLIAdapter projection maps them to canonical schema columns.
    """
    base = {
        "station_code": "KNYC",
        "observation_date": date(2025, 1, 1),
        "report_type": "final",
        "high_temp_f": 35.0,
        "low_temp_f": 22.0,
        "precipitation_in": 0.0,
        "snowfall_in": 0.0,
        "issued_at": "2025-01-02T13:00:00Z",
    }
    base.update(overrides)
    return base


def test_from_records_basic():
    df = CLIAdapter.from_records(
        [_rec()],
        source="cli.archive",
        station_tz="America/New_York",
    )
    assert df.attrs["source"] == "cli.archive"
    # 12-column settlement schema + overlay cols.
    assert "station" in df.columns
    assert "settlement_finality" in df.columns
    assert "cli_data_quality" in df.columns
    assert "knowledge_time" in df.columns
    # observation_date should remain a date object.
    assert isinstance(df["observation_date"].iloc[0], date)


def test_event_time_uses_station_tz():
    df = CLIAdapter.from_records([_rec()], source="cli.archive", station_tz="America/New_York")
    # Jan 1 2025 00:00 EST → 05:00 UTC.
    et = df["event_time"].iloc[0]
    assert et == pd.Timestamp("2025-01-01T05:00:00Z")


def test_dedup_keeps_highest_priority():
    """preliminary + correction + final for same (station, date) → keep final.

    v0.14.1 REPORT_TYPE_PRIORITY: final=3.0 > correction=2.0 > preliminary=1.0.
    """
    recs = [
        _rec(report_type="preliminary"),
        _rec(report_type="correction"),
        _rec(report_type="final"),
    ]
    df = CLIAdapter.from_records(recs, station_tz="America/New_York")
    assert len(df) == 1
    assert df["report_type"].iloc[0] == "final"


def test_dedup_first_seen_wins_at_equal_priority():
    """Two ``final`` rows for same date → first one wins."""
    recs = [
        _rec(report_type="final", high_temp_f=35.0),
        _rec(report_type="final", high_temp_f=99.0),
    ]
    df = CLIAdapter.from_records(recs, station_tz="America/New_York")
    assert len(df) == 1
    assert df["temp_max_F"].iloc[0] == 35.0


def test_dedup_per_station():
    """Different stations on same date → both rows kept."""
    recs = [
        _rec(station_code="KNYC"),
        _rec(station_code="KORD"),
    ]
    df = CLIAdapter.from_records(recs, station_tz="UTC")
    assert len(df) == 2
    assert set(df["station"]) == {"KNYC", "KORD"}


def test_settlement_finality_mapping():
    """``final``/``correction`` → ``final``; ``preliminary`` → ``provisional``."""
    recs = [
        _rec(station_code="A", report_type="preliminary"),
        _rec(station_code="B", report_type="final"),
        _rec(station_code="C", report_type="correction"),
    ]
    df = CLIAdapter.from_records(recs, station_tz="UTC")
    finality_by_station = dict(zip(df["station"], df["settlement_finality"], strict=False))
    assert finality_by_station["A"] == "provisional"
    assert finality_by_station["B"] == "final"
    assert finality_by_station["C"] == "final"


def test_invalid_source_raises():
    with pytest.raises(ValueError):
        CLIAdapter.from_records([_rec()], source="bogus")


def test_fetch_observations_not_implemented():
    a = CLIAdapter()
    with pytest.raises(NotImplementedError):
        a.fetch_observations("cli.archive", "KNYC", "2025-01-01", "2025-01-02")


def test_registered_in_catalog():
    a = get_adapter("cli.archive")
    assert isinstance(a, CLIAdapter)
    b = get_adapter("cli.live")
    assert isinstance(b, CLIAdapter)


def test_empty_records():
    df = CLIAdapter.from_records([])
    assert df.empty
    assert df.attrs["source"] == "cli.archive"


def test_empty_records_pass_validator():
    """codex iter-6 HIGH fix: zero-row CLI pulls must validate cleanly."""
    from mostlyright.core import validate_dataframe

    df = CLIAdapter.from_records(
        [], retrieved_at=datetime(2025, 1, 2, 13, tzinfo=UTC), station_tz="UTC"
    )
    reg = validate_dataframe(df, "schema.settlement.cli.v1")
    assert reg.rows == 0


def test_retrieved_at_propagates():
    when = datetime(2025, 1, 2, 13, tzinfo=UTC)
    df = CLIAdapter.from_records([_rec()], retrieved_at=when, station_tz="UTC")
    assert df.attrs["retrieved_at"] == when


# ----------------------------------------------------------------------
# Codex iter-2 HIGH fix: parser keys flow end-to-end (parse_cli_record
# output → CLIAdapter.from_records()) without dropping values.
# ----------------------------------------------------------------------
def test_cli_adapter_output_passes_validator():
    """codex iter-5 HIGH fix: full CLIAdapter -> validate_dataframe chain.

    parse_cli_record() emits int temperatures but the settlement schema
    declares float64. The adapter must coerce so adapter -> Validator
    integration succeeds.
    """
    from mostlyright.core import validate_dataframe

    parser_output_int = {
        "station_code": "KNYC",
        "observation_date": date(2025, 1, 1),
        "report_type": "final",
        "high_temp_f": 35,  # int from parser
        "low_temp_f": 22,  # int from parser
        "precipitation_in": 0,  # int
        "snowfall_in": 0,
        "issued_at": "2025-01-02T13:00:00Z",
    }
    df = CLIAdapter.from_records(
        [parser_output_int],
        source="cli.archive",
        station_tz="America/New_York",
        retrieved_at=datetime(2025, 1, 2, 13, tzinfo=UTC),
    )
    # Coerced to float64.
    assert df["temp_max_F"].dtype == "float64"
    assert df["temp_min_F"].dtype == "float64"
    # Validator must accept.
    reg = validate_dataframe(df, "schema.settlement.cli.v1")
    assert reg.source == "cli.archive"
    assert reg.rows == 1


def test_parser_keys_flow_into_canonical_columns():
    """Real parse_cli_record() output must populate canonical settlement columns.

    Prior to the iter-2 fix, the projection used max_temp_f/min_temp_f/
    product_release_time but the parser emits high_temp_f/low_temp_f/
    issued_at — adapter silently dropped settlement values.
    """
    parser_output = {
        "station_code": "KNYC",
        "observation_date": date(2025, 1, 1),
        "report_type": "final",
        "high_temp_f": 35.0,
        "low_temp_f": 22.0,
        "precipitation_in": 0.0,
        "snowfall_in": 0.0,
        "issued_at": "2025-01-02T13:00:00Z",
        # parse_cli_record also emits these — adapter ignores them harmlessly.
        "report_type_priority": 3.0,
        "source": "iem",
        "product_id": "CLINYC",
    }
    df = CLIAdapter.from_records([parser_output], station_tz="America/New_York")
    # Settlement values must flow through, not be null.
    assert df["temp_max_F"].iloc[0] == 35.0
    assert df["temp_min_F"].iloc[0] == 22.0
    assert pd.notna(df["product_release_time"].iloc[0])
    assert df["product_release_time"].iloc[0] == pd.Timestamp("2025-01-02T13:00:00Z")
