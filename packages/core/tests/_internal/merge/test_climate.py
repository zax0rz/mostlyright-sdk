"""Tests for ``mostlyright._internal.merge.climate``.

The v0.14.1 source ``_dedup_climate_rows`` (monorepo-v0.14.1/ingest/storage/
parquet.py:477-494) had no dedicated unit-test class — it was exercised
indirectly via ``merge_climate`` (the year-partition orchestrator) in
``tests/test_parquet.py``. Those tests are NOT lifted here because they
exercise parquet I/O, not the pure dedup policy.

This file pins the pure-policy contract directly so any future drift
in ``REPORT_TYPE_PRIORITY`` mapping or the strict-``>`` semantics
trips a fast unit test instead of a downstream integration failure.

Critical invariants (parity-load-bearing):
- Strict ``>`` (NOT ``>=``) on ``report_type_priority``.
- First-seen wins on ties: two ``final`` rows -> first kept.
- Missing ``report_type_priority`` -> 0.0 (cannot overwrite known).
- Empty input -> empty output.
- Key is ``(station_code, observation_date)``; same station + same
  date is the dedup unit.

The "two-final-rows-first-wins" test pins the overnight-final
preservation behaviour: the first final received IS the Kalshi
settlement value, and a later final with the same priority MUST NOT
overwrite it.
"""

from __future__ import annotations

from typing import Any

import pytest
from mostlyright._internal.merge.climate import REPORT_TYPE_PRIORITY, merge_climate


def _row(
    station_code: str,
    observation_date: str,
    report_type: str,
    *,
    high_temp_f: int | None = None,
    low_temp_f: int | None = None,
    product_id: str = "",
) -> dict[str, Any]:
    """Build a climate row with the priority float populated from the mapping.

    Mirrors how ``mostlyright.weather._climate.parse_cli_file`` populates
    ``report_type_priority`` before rows ever reach ``merge_climate``.
    """
    return {
        "station_code": station_code,
        "observation_date": observation_date,
        "report_type": report_type,
        "report_type_priority": REPORT_TYPE_PRIORITY[report_type],
        "high_temp_f": high_temp_f,
        "low_temp_f": low_temp_f,
        "product_id": product_id,
    }


class TestReportTypePriority:
    """The mapping itself — pinned against v0.14.1's _climate.py."""

    def test_final_is_three(self) -> None:
        assert REPORT_TYPE_PRIORITY["final"] == 3.0

    def test_ncei_final_is_two_point_five(self) -> None:
        assert REPORT_TYPE_PRIORITY["ncei_final"] == 2.5

    def test_correction_is_two(self) -> None:
        assert REPORT_TYPE_PRIORITY["correction"] == 2.0

    def test_preliminary_is_one(self) -> None:
        assert REPORT_TYPE_PRIORITY["preliminary"] == 1.0

    def test_estimated_is_zero(self) -> None:
        assert REPORT_TYPE_PRIORITY["estimated"] == 0.0

    def test_final_is_strictly_highest(self) -> None:
        """``final`` MUST be strictly greater than every other priority.

        Settlement integrity depends on no other report type tying or
        beating ``final``.
        """
        for report_type, priority in REPORT_TYPE_PRIORITY.items():
            if report_type == "final":
                continue
            assert REPORT_TYPE_PRIORITY["final"] > priority


class TestMergeClimateBasics:
    """Empty input, single row, and the no-collision case."""

    def test_empty_input_returns_empty(self) -> None:
        assert merge_climate([]) == []

    def test_single_row_passes_through(self) -> None:
        row = _row("ATL", "2025-01-15", "final", high_temp_f=55)
        assert merge_climate([row]) == [row]

    def test_distinct_keys_all_kept(self) -> None:
        rows = [
            _row("ATL", "2025-01-15", "final"),
            _row("ATL", "2025-01-16", "final"),
            _row("ORD", "2025-01-15", "final"),
        ]
        result = merge_climate(rows)
        assert len(result) == 3
        assert {(r["station_code"], r["observation_date"]) for r in result} == {
            ("ATL", "2025-01-15"),
            ("ATL", "2025-01-16"),
            ("ORD", "2025-01-15"),
        }


class TestMergeClimatePriority:
    """Strict-``>`` priority replacement semantics."""

    def test_final_replaces_preliminary(self) -> None:
        prelim = _row("ATL", "2025-01-15", "preliminary", high_temp_f=50)
        final = _row("ATL", "2025-01-15", "final", high_temp_f=55)
        result = merge_climate([prelim, final])
        assert len(result) == 1
        assert result[0]["report_type"] == "final"
        assert result[0]["high_temp_f"] == 55

    def test_final_replaces_correction(self) -> None:
        correction = _row("ATL", "2025-01-15", "correction", high_temp_f=53)
        final = _row("ATL", "2025-01-15", "final", high_temp_f=55)
        result = merge_climate([correction, final])
        assert len(result) == 1
        assert result[0]["report_type"] == "final"
        assert result[0]["high_temp_f"] == 55

    def test_correction_replaces_preliminary(self) -> None:
        prelim = _row("ATL", "2025-01-15", "preliminary", high_temp_f=50)
        correction = _row("ATL", "2025-01-15", "correction", high_temp_f=52)
        result = merge_climate([prelim, correction])
        assert len(result) == 1
        assert result[0]["report_type"] == "correction"
        assert result[0]["high_temp_f"] == 52

    def test_prelim_to_final_to_correction_ordering(self) -> None:
        """`prelim < final < correction` priority test (per task spec)."""
        # Note: in v0.14.1's mapping, correction (2.0) < final (3.0).
        # The task name "prelim < final < correction" is an ordering
        # rubric: receive prelim, then final, then a later correction.
        # The strict-``>`` rule means the later correction does NOT
        # overwrite the final (because 2.0 < 3.0). Final wins.
        prelim = _row("ATL", "2025-01-15", "preliminary", high_temp_f=50)
        final = _row("ATL", "2025-01-15", "final", high_temp_f=55)
        correction = _row("ATL", "2025-01-15", "correction", high_temp_f=53)
        result = merge_climate([prelim, final, correction])
        assert len(result) == 1
        assert result[0]["report_type"] == "final"
        assert result[0]["high_temp_f"] == 55

    def test_lower_priority_never_replaces_higher(self) -> None:
        final = _row("ATL", "2025-01-15", "final", high_temp_f=55)
        prelim = _row("ATL", "2025-01-15", "preliminary", high_temp_f=50)
        result = merge_climate([final, prelim])
        assert len(result) == 1
        assert result[0]["report_type"] == "final"
        assert result[0]["high_temp_f"] == 55


class TestMergeClimateStrictTie:
    """The strict-``>`` invariant: equal priority MUST NOT replace."""

    def test_two_final_rows_first_wins(self) -> None:
        """Strict-``>`` (NOT ``>=``): second ``final`` MUST NOT overwrite first.

        This pins the overnight-final preservation. The first ``final``
        received IS the Kalshi settlement; a later product issuance with
        the same ``final`` priority must NOT replace it.
        """
        first = _row("ATL", "2025-01-15", "final", high_temp_f=55, product_id="first")
        second = _row("ATL", "2025-01-15", "final", high_temp_f=60, product_id="second")
        result = merge_climate([first, second])
        assert len(result) == 1
        assert result[0]["product_id"] == "first"
        assert result[0]["high_temp_f"] == 55

    def test_two_correction_rows_first_wins(self) -> None:
        first = _row("ATL", "2025-01-15", "correction", high_temp_f=52, product_id="c1")
        second = _row("ATL", "2025-01-15", "correction", high_temp_f=58, product_id="c2")
        result = merge_climate([first, second])
        assert len(result) == 1
        assert result[0]["product_id"] == "c1"

    def test_two_preliminary_rows_first_wins(self) -> None:
        first = _row("ATL", "2025-01-15", "preliminary", high_temp_f=50, product_id="p1")
        second = _row("ATL", "2025-01-15", "preliminary", high_temp_f=60, product_id="p2")
        result = merge_climate([first, second])
        assert len(result) == 1
        assert result[0]["product_id"] == "p1"


class TestMergeClimateMissingPriority:
    """Rows without ``report_type_priority`` default to 0.0."""

    def test_missing_priority_treated_as_zero(self) -> None:
        without_prio = {
            "station_code": "ATL",
            "observation_date": "2025-01-15",
            "report_type": "unknown",
            # no report_type_priority key
            "high_temp_f": 99,
        }
        prelim = _row("ATL", "2025-01-15", "preliminary", high_temp_f=50)
        result = merge_climate([without_prio, prelim])
        assert len(result) == 1
        # prelim (1.0) > missing (0.0) -> prelim wins
        assert result[0]["report_type"] == "preliminary"
        assert result[0]["high_temp_f"] == 50

    def test_missing_priority_first_seen_does_not_overwrite_known(self) -> None:
        prelim = _row("ATL", "2025-01-15", "preliminary", high_temp_f=50)
        without_prio = {
            "station_code": "ATL",
            "observation_date": "2025-01-15",
            "report_type": "unknown",
            "high_temp_f": 99,
        }
        result = merge_climate([prelim, without_prio])
        assert len(result) == 1
        # prelim (1.0) > missing (0.0); first-seen prelim stays
        assert result[0]["report_type"] == "preliminary"
        assert result[0]["high_temp_f"] == 50

    def test_two_missing_priority_first_wins(self) -> None:
        first = {
            "station_code": "ATL",
            "observation_date": "2025-01-15",
            "product_id": "a",
        }
        second = {
            "station_code": "ATL",
            "observation_date": "2025-01-15",
            "product_id": "b",
        }
        result = merge_climate([first, second])
        assert len(result) == 1
        # both default to 0.0; strict-> means first stays
        assert result[0]["product_id"] == "a"


class TestMergeClimateOrderInsensitivity:
    """Result depends on priority + first-seen, not full input shuffle."""

    def test_full_settlement_lifecycle(self) -> None:
        """A realistic 1-day settlement: prelim @ same day, final overnight,
        late correction. Output must be the overnight final."""
        prelim = _row(
            "ATL",
            "2025-01-15",
            "preliminary",
            high_temp_f=50,
            product_id="prelim-202501151400",
        )
        final = _row(
            "ATL",
            "2025-01-15",
            "final",
            high_temp_f=55,
            product_id="final-202501160620",
        )
        correction = _row(
            "ATL",
            "2025-01-15",
            "correction",
            high_temp_f=53,
            product_id="correction-202501171100",
        )
        result = merge_climate([prelim, final, correction])
        assert len(result) == 1
        assert result[0]["product_id"] == "final-202501160620"

    def test_multi_station_multi_day(self) -> None:
        rows = [
            _row("ATL", "2025-01-15", "preliminary", high_temp_f=50),
            _row("ATL", "2025-01-15", "final", high_temp_f=55),
            _row("ATL", "2025-01-16", "final", high_temp_f=60),
            _row("ORD", "2025-01-15", "preliminary", high_temp_f=30),
            _row("ORD", "2025-01-15", "final", high_temp_f=35),
        ]
        result = merge_climate(rows)
        assert len(result) == 3
        by_key = {(r["station_code"], r["observation_date"]): r for r in result}
        assert by_key[("ATL", "2025-01-15")]["report_type"] == "final"
        assert by_key[("ATL", "2025-01-15")]["high_temp_f"] == 55
        assert by_key[("ATL", "2025-01-16")]["high_temp_f"] == 60
        assert by_key[("ORD", "2025-01-15")]["report_type"] == "final"
        assert by_key[("ORD", "2025-01-15")]["high_temp_f"] == 35


@pytest.mark.parametrize(
    "high_priority_type, low_priority_type",
    [
        ("final", "ncei_final"),
        ("final", "correction"),
        ("final", "preliminary"),
        ("final", "estimated"),
        ("ncei_final", "correction"),
        ("ncei_final", "preliminary"),
        ("correction", "preliminary"),
        ("correction", "estimated"),
        ("preliminary", "estimated"),
    ],
)
def test_priority_pair_replacement(high_priority_type: str, low_priority_type: str) -> None:
    """Strict-``>``: higher always replaces lower; lower never replaces higher."""
    low = _row("ATL", "2025-01-15", low_priority_type, high_temp_f=10)
    high = _row("ATL", "2025-01-15", high_priority_type, high_temp_f=20)

    # low arrives first, high arrives second -> high wins
    result1 = merge_climate([low, high])
    assert len(result1) == 1
    assert result1[0]["report_type"] == high_priority_type
    assert result1[0]["high_temp_f"] == 20

    # high arrives first, low arrives second -> high still wins
    result2 = merge_climate([high, low])
    assert len(result2) == 1
    assert result2[0]["report_type"] == high_priority_type
    assert result2[0]["high_temp_f"] == 20
