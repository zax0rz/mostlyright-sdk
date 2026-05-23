"""Unit tests for Phase 2.1 query_time_merge."""

from __future__ import annotations

import pandas as pd
import pytest
from tradewinds.core.merge import (
    LIVE_V1,
    ObservationMergePolicy,
    query_time_merge,
)


def _row(**overrides):
    base = {
        "station_code": "KNYC",
        "observed_at": "2025-01-01T12:00:00Z",
        "source": "iem",
        "temp_c": 1.0,
        "source_received_at": "2025-01-01T12:00:01.000000Z",
        "ingestion_id": "ing-1",
        "parser_name": "iem",
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------
# Policy basics
# ----------------------------------------------------------------------
def test_live_v1_priority_order():
    """AWC > IEM > GHCNh; ncei reserved at 0."""
    assert LIVE_V1.source_priority["awc"] == 3
    assert LIVE_V1.source_priority["iem"] == 2
    assert LIVE_V1.source_priority["ghcnh"] == 1
    assert LIVE_V1.source_priority["ncei"] == 0


def test_policy_secondary_key():
    assert LIVE_V1.secondary_key == ("source_received_at", "ingestion_id")


# ----------------------------------------------------------------------
# Merge correctness
# ----------------------------------------------------------------------
def test_single_row_passthrough():
    silver = pd.DataFrame([_row()])
    gold = query_time_merge(silver)
    assert len(gold) == 1
    assert gold["source"].iloc[0] == "iem"


def test_awc_beats_iem_at_same_key():
    silver = pd.DataFrame(
        [
            _row(source="iem", temp_c=1.0),
            _row(source="awc", temp_c=2.0),
        ]
    )
    gold = query_time_merge(silver)
    assert len(gold) == 1
    assert gold["source"].iloc[0] == "awc"
    assert gold["temp_c"].iloc[0] == 2.0


def test_iem_beats_ghcnh():
    silver = pd.DataFrame(
        [
            _row(source="ghcnh"),
            _row(source="iem"),
        ]
    )
    gold = query_time_merge(silver)
    assert gold["source"].iloc[0] == "iem"


def test_per_station_dedup():
    silver = pd.DataFrame(
        [
            _row(station_code="KNYC", source="iem"),
            _row(station_code="KORD", source="ghcnh"),
        ]
    )
    gold = query_time_merge(silver)
    assert len(gold) == 2
    assert set(gold["station_code"]) == {"KNYC", "KORD"}


def test_per_observed_at_dedup():
    silver = pd.DataFrame(
        [
            _row(observed_at="2025-01-01T12:00:00Z", source="iem"),
            _row(observed_at="2025-01-01T13:00:00Z", source="iem"),
        ]
    )
    gold = query_time_merge(silver)
    assert len(gold) == 2


def test_secondary_key_tiebreak():
    """Two AWC rows for same (station, observed_at): earliest source_received_at wins."""
    silver = pd.DataFrame(
        [
            _row(
                source="awc",
                source_received_at="2025-01-01T12:00:02.000000Z",
                ingestion_id="ing-late",
                temp_c=2.0,
            ),
            _row(
                source="awc",
                source_received_at="2025-01-01T12:00:01.000000Z",
                ingestion_id="ing-early",
                temp_c=1.0,
            ),
        ]
    )
    gold = query_time_merge(silver)
    assert len(gold) == 1
    assert gold["ingestion_id"].iloc[0] == "ing-early"
    assert gold["temp_c"].iloc[0] == 1.0


def test_idempotent():
    silver = pd.DataFrame(
        [
            _row(source="iem"),
            _row(source="awc"),
            _row(source="ghcnh"),
        ]
    )
    gold1 = query_time_merge(silver)
    gold2 = query_time_merge(silver)
    pd.testing.assert_frame_equal(gold1, gold2)


def test_row_shuffle_invariant():
    """Same silver_df produces same gold_df across row-shuffle permutations."""
    rows = [
        _row(source="iem", observed_at="2025-01-01T12:00:00Z"),
        _row(source="awc", observed_at="2025-01-01T12:00:00Z"),
        _row(source="ghcnh", observed_at="2025-01-01T13:00:00Z"),
    ]
    silver_a = pd.DataFrame(rows)
    silver_b = pd.DataFrame(rows[::-1])
    gold_a = query_time_merge(silver_a)
    gold_b = query_time_merge(silver_b).sort_values(["observed_at"]).reset_index(drop=True)
    gold_a = gold_a.sort_values(["observed_at"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(gold_a, gold_b, check_like=True)


def test_empty_passthrough():
    silver = pd.DataFrame({"station_code": [], "observed_at": [], "source": []})
    gold = query_time_merge(silver)
    assert gold.empty


def test_missing_required_column_raises():
    silver = pd.DataFrame([{"station_code": "KNYC", "source": "iem"}])
    with pytest.raises(ValueError, match="observed_at"):
        query_time_merge(silver)


def test_unknown_source_treated_as_lowest_priority():
    """Source not in policy.source_priority gets -1 (loses to everything)."""
    silver = pd.DataFrame(
        [
            _row(source="bogus", temp_c=99.0),
            _row(source="ghcnh", temp_c=1.0),
        ]
    )
    gold = query_time_merge(silver)
    assert gold["source"].iloc[0] == "ghcnh"


def test_policy_apply_alias():
    """ObservationMergePolicy.apply is equivalent to query_time_merge."""
    silver = pd.DataFrame([_row(source="iem"), _row(source="awc")])
    via_apply = LIVE_V1.apply(silver)
    via_fn = query_time_merge(silver, policy=LIVE_V1)
    pd.testing.assert_frame_equal(via_apply, via_fn)


def test_attrs_preserved():
    silver = pd.DataFrame([_row()])
    silver.attrs["pull_id"] = "test-123"
    gold = query_time_merge(silver)
    assert gold.attrs.get("pull_id") == "test-123"


# ----------------------------------------------------------------------
# Policy immutability (codex Phase 2.1 review HIGH fix)
# ----------------------------------------------------------------------
def test_live_v1_source_priority_immutable():
    """LIVE_V1.source_priority must reject mutation — otherwise a stray
    runtime mutation would globally change merge results.
    """
    with pytest.raises(TypeError):
        LIVE_V1.source_priority["awc"] = 99  # type: ignore[index]


def test_policy_dataclass_frozen():
    """Re-assigning a top-level field on ObservationMergePolicy raises."""
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        LIVE_V1.name = "other"  # type: ignore[misc]


def test_custom_policy_input_dict_wrapped():
    """A caller-supplied dict is wrapped in MappingProxyType too."""
    custom = ObservationMergePolicy(name="test", source_priority={"a": 1})
    with pytest.raises(TypeError):
        custom.source_priority["a"] = 99  # type: ignore[index]


# ----------------------------------------------------------------------
# Schema registration (codex Phase 2.1 review HIGH fix)
# ----------------------------------------------------------------------
def test_observation_ledger_schema_registered():
    """schema.observation_ledger.v1 is in the Validator registry."""
    import tradewinds.core.schemas  # noqa: F401 — triggers registration
    from tradewinds.core.validator import _SCHEMA_REGISTRY

    assert "schema.observation_ledger.v1" in _SCHEMA_REGISTRY


def test_observation_qc_schema_registered():
    """schema.observation_qc.v1 is in the Validator registry."""
    import tradewinds.core.schemas  # noqa: F401
    from tradewinds.core.validator import _SCHEMA_REGISTRY

    assert "schema.observation_qc.v1" in _SCHEMA_REGISTRY
