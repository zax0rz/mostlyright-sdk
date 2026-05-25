"""Tests for the GRIB2 .idx parser (Phase 3.2)."""

from __future__ import annotations

import pytest
from mostlyright.weather._fetchers._nwp_idx import (
    IdxRecord,
    compute_byte_end,
    filter_records,
    parse_idx,
)

SAMPLE_IDX = """1:0:d=2026010100:TMP:2 m above ground:1 hour fcst:
2:120000:d=2026010100:DPT:2 m above ground:1 hour fcst:
3:240000:d=2026010100:UGRD:10 m above ground:1 hour fcst:
4:360000:d=2026010100:VGRD:10 m above ground:1 hour fcst:
"""


def test_parse_idx_returns_records_in_source_order() -> None:
    records = parse_idx(SAMPLE_IDX)
    assert len(records) == 4
    assert [r.variable for r in records] == ["TMP", "DPT", "UGRD", "VGRD"]
    assert [r.record_no for r in records] == [1, 2, 3, 4]
    assert [r.byte_offset for r in records] == [0, 120000, 240000, 360000]
    assert all(r.byte_end is None for r in records)


def test_parse_idx_blank_lines_skipped() -> None:
    text = "\n\n" + SAMPLE_IDX + "\n\n"
    assert len(parse_idx(text)) == 4


def test_parse_idx_no_forecast_period_ok() -> None:
    """Some products emit no sixth field; record still parses."""
    text = "1:0:d=2026010100:TMP:2 m above ground"
    records = parse_idx(text)
    assert len(records) == 1
    assert records[0].forecast_period == ""


def test_parse_idx_too_few_fields_raises_loudly() -> None:
    """Per RESEARCH §"Anti-Patterns" — silent skip masks upstream changes."""
    with pytest.raises(ValueError, match=r"Malformed \.idx line"):
        parse_idx("1:0:d=2026010100:TMP")  # only 4 fields


def test_parse_idx_non_integer_byte_offset_raises() -> None:
    with pytest.raises(ValueError, match="not int"):
        parse_idx("1:notanumber:d=2026010100:TMP:2 m above ground:")


def test_compute_byte_end_chains_non_last_to_next_offset_minus_one() -> None:
    records = parse_idx(SAMPLE_IDX)
    out = compute_byte_end(records, content_length=480000)
    assert out[0].byte_end == 119999  # 120000 - 1
    assert out[1].byte_end == 239999
    assert out[2].byte_end == 359999
    assert out[3].byte_end == 479999  # content_length - 1


def test_compute_byte_end_last_record_none_when_no_content_length() -> None:
    """Caller forgot to HEAD the GRIB2 file → last record stays unbounded."""
    records = parse_idx(SAMPLE_IDX)
    out = compute_byte_end(records, content_length=None)
    assert out[3].byte_end is None
    assert out[2].byte_end == 359999  # non-last still resolved


def test_compute_byte_end_does_not_mutate_input() -> None:
    records = parse_idx(SAMPLE_IDX)
    snapshot = [r.byte_end for r in records]
    _ = compute_byte_end(records, content_length=480000)
    assert [r.byte_end for r in records] == snapshot


def test_compute_byte_end_empty_returns_empty() -> None:
    assert compute_byte_end([], content_length=100) == []


def test_filter_records_keeps_only_mapped_pairs() -> None:
    records = parse_idx(SAMPLE_IDX)
    variable_map = {
        "temp_k_2m": ("TMP", "2 m above ground"),
        "wind_u_ms_10m": ("UGRD", "10 m above ground"),
    }
    filtered = filter_records(records, variable_map)
    assert {(r.variable, r.level) for r in filtered} == set(variable_map.values())
    assert len(filtered) == 2


def test_filter_records_dedups_duplicate_record_no() -> None:
    """Two map entries pointing at the same (variable, level) keep one row."""
    records = [
        IdxRecord(1, 0, None, "d=", "TMP", "2 m above ground", ""),
        IdxRecord(2, 100, None, "d=", "TMP", "2 m above ground", ""),
    ]
    variable_map = {"temp_k_2m": ("TMP", "2 m above ground")}
    filtered = filter_records(records, variable_map)
    # Two records match (variable, level) — both kept (different record_no).
    assert len(filtered) == 2
    # But each is kept exactly once (no double-count).
    assert {r.record_no for r in filtered} == {1, 2}
