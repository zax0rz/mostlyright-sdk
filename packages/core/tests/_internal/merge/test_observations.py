"""Tests for ``mostlyright._internal.merge.observations``.

Lifted from monorepo-v0.14.1/tests/test_parquet.py (TestMergeStaging cases
that exercise ``_dedup_rows`` via the parquet round-trip). Rewired to call
``merge_observations`` directly — purifying away the staging-file plumbing
since the Phase 1 cache layer (Task 1.4) owns parquet I/O separately.

Source SHA: 514fcdab227e845145ca32b989355647466231d9
Lift date: 2026-05-21

Lifted cases:
- ``test_dedup_by_key``                  -> ``test_dedup_first_reported_wins``
- ``test_source_priority_awc_over_iem``  -> kept verbatim
- ``test_source_priority_iem_over_ghcnh``-> kept verbatim
- ``test_different_observation_types_not_deduped`` -> kept verbatim
- ``test_unknown_source_loses_to_known`` -> kept verbatim
"""

from __future__ import annotations

from typing import Any

from mostlyright._internal.merge.observations import (
    SOURCE_PRIORITY,
    merge_observations,
)


def _make_obs(
    station_code: str = "JFK",
    observed_at: str = "2025-07-15T12:00:00Z",
    observation_type: str = "METAR",
    source: str = "awc",
    **overrides: object,
) -> dict[str, Any]:
    """Create a valid observation dict matching specs/observation.json.

    Lifted from monorepo-v0.14.1/tests/test_parquet.py::_make_obs (lines 18-59).
    """
    base: dict[str, Any] = {
        "station_code": station_code,
        "observed_at": observed_at,
        "observation_type": observation_type,
        "source": source,
        "temp_c": 25.6,
        "dewpoint_c": 12.8,
        "temp_f": 78.08,
        "dewpoint_f": 55.04,
        "wind_dir_degrees": 180,
        "wind_speed_kt": 10,
        "wind_gust_kt": None,
        "altimeter_inhg": 29.92,
        "sea_level_pressure_mb": 1013.2,
        "sky_cover_1": "FEW",
        "sky_base_1_ft": 5000,
        "sky_cover_2": None,
        "sky_base_2_ft": None,
        "sky_cover_3": None,
        "sky_base_3_ft": None,
        "sky_cover_4": None,
        "sky_base_4_ft": None,
        "visibility_miles": 10.0,
        "weather_codes": None,
        "precip_1hr_inches": None,
        "peak_wind_gust_kt": None,
        "peak_wind_dir": None,
        "peak_wind_time": None,
        "snow_depth_inches": None,
        "qc_field": 4,
        "raw_metar": "KJFK 151200Z 18010KT 10SM FEW050 26/13 A2992",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# SOURCE_PRIORITY constant — guard against accidental drift (parity critical)
# ---------------------------------------------------------------------------


def test_source_priority_exact_mapping() -> None:
    """SOURCE_PRIORITY must match v0.14.1 line 47-48 byte-identically."""
    assert SOURCE_PRIORITY == {"awc": 3, "iem": 2, "ghcnh": 1}


# ---------------------------------------------------------------------------
# Empty / boundary input
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_list() -> None:
    """No rows in -> no rows out."""
    assert merge_observations([]) == []


def test_single_row_passthrough() -> None:
    """A single row is returned unchanged (no dedup decision required)."""
    obs = _make_obs(source="iem", temp_c=20.0)
    result = merge_observations([obs])
    assert len(result) == 1
    assert result[0] is obs  # identity: same object returned


# ---------------------------------------------------------------------------
# Lifted from v0.14.1 test_parquet.py — dedup semantics
# ---------------------------------------------------------------------------


def test_dedup_first_reported_wins() -> None:
    """Same source, same key: first-reported wins (strict-`>` semantics).

    Lifted from v0.14.1 test_parquet.py::test_dedup_by_key (lines 301-317).
    """
    obs1 = _make_obs(source="awc", temp_c=25.6)
    obs2 = _make_obs(source="awc", temp_c=26.0)  # same dedup key, correction

    result = merge_observations([obs1, obs2])
    assert len(result) == 1
    assert result[0]["temp_c"] == 25.6, "First-reported must win"


def test_source_priority_awc_over_iem() -> None:
    """AWC(3) beats IEM(2) for same dedup key.

    Lifted from v0.14.1 test_parquet.py::test_source_priority_awc_over_iem
    (lines 319-332). Tests BOTH orderings to confirm priority — not insertion
    order — drives the dedup.
    """
    iem_obs = _make_obs(source="iem", temp_c=26.0)
    awc_obs = _make_obs(source="awc", temp_c=25.6)

    # IEM first, then AWC — AWC must overwrite (higher priority).
    result = merge_observations([iem_obs, awc_obs])
    assert len(result) == 1
    assert result[0]["source"] == "awc"
    assert result[0]["temp_c"] == 25.6

    # AWC first, then IEM — AWC must STAY (strict-`>` keeps incumbent).
    result = merge_observations([awc_obs, iem_obs])
    assert len(result) == 1
    assert result[0]["source"] == "awc"
    assert result[0]["temp_c"] == 25.6


def test_source_priority_iem_over_ghcnh() -> None:
    """IEM(2) beats GHCNh(1) for same dedup key.

    Lifted from v0.14.1 test_parquet.py::test_source_priority_iem_over_ghcnh
    (lines 334-346).
    """
    ghcnh_obs = _make_obs(source="ghcnh", temp_c=26.0)
    iem_obs = _make_obs(source="iem", temp_c=25.5)

    result = merge_observations([ghcnh_obs, iem_obs])
    assert len(result) == 1
    assert result[0]["source"] == "iem"


def test_different_observation_types_not_deduped() -> None:
    """METAR and SPECI for same station+time are separate observations.

    Lifted from v0.14.1 test_parquet.py::test_different_observation_types_not_deduped
    (lines 403-412). The dedup key includes ``observation_type``.
    """
    metar = _make_obs(observation_type="METAR")
    speci = _make_obs(observation_type="SPECI")

    result = merge_observations([metar, speci])
    assert len(result) == 2
    types = {r["observation_type"] for r in result}
    assert types == {"METAR", "SPECI"}


def test_unknown_source_loses_to_known() -> None:
    """Unknown source gets priority 0, loses to any known source.

    Lifted from v0.14.1 test_parquet.py::test_unknown_source_loses_to_known
    (lines 414-426). Uses ``"madis"`` (a real source that isn't in the
    SDK's priority table) so the dict-default-0 path is exercised honestly.
    """
    unknown = _make_obs(source="madis", temp_c=99.0)
    known = _make_obs(source="iem", temp_c=25.5)

    result = merge_observations([unknown, known])
    assert len(result) == 1
    assert result[0]["source"] == "iem"
    assert result[0]["temp_c"] == 25.5


def test_missing_source_key_treated_as_priority_zero() -> None:
    """A row with no ``source`` field at all loses to any priority-bearing row.

    Exercises the ``row.get("source", "")`` default path in the v0.14.1 lift
    (parquet.py:254). Not a v0.14.1 lifted test — added defensively because
    the next caller in Phase 1 (cache layer) may produce rows from
    partially-parsed sources during cache-miss recovery.
    """
    no_source = _make_obs(source="awc")
    del no_source["source"]
    iem_obs = _make_obs(source="iem", temp_c=30.0)

    result = merge_observations([no_source, iem_obs])
    assert len(result) == 1
    assert result[0]["source"] == "iem"


def test_distinct_keys_all_preserved() -> None:
    """Three distinct (station, time, type) triples all survive."""
    a = _make_obs(station_code="JFK", observed_at="2025-07-15T12:00:00Z")
    b = _make_obs(station_code="JFK", observed_at="2025-07-15T13:00:00Z")
    c = _make_obs(station_code="ATL", observed_at="2025-07-15T12:00:00Z")

    result = merge_observations([a, b, c])
    assert len(result) == 3


def test_insertion_order_preserved_for_distinct_keys() -> None:
    """Output order matches first-insertion order (dict-of-keys behavior).

    Important for downstream callers (cache layer, pair builder) that
    rely on stable ordering after merge.
    """
    a = _make_obs(observed_at="2025-07-15T10:00:00Z")
    b = _make_obs(observed_at="2025-07-15T11:00:00Z")
    c = _make_obs(observed_at="2025-07-15T12:00:00Z")

    result = merge_observations([c, a, b])
    times = [r["observed_at"] for r in result]
    assert times == [
        "2025-07-15T12:00:00Z",
        "2025-07-15T10:00:00Z",
        "2025-07-15T11:00:00Z",
    ]
