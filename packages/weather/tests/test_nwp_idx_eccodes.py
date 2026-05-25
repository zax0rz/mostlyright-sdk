"""Phase 17 PLAN-04: ECMWF eccodes JSON-lines .index parser."""

from __future__ import annotations

import pytest
from mostlyright.weather._fetchers._nwp_idx import parse_idx

# Verified against real ECMWF data 2026-05-25 (5 lines from
# https://data.ecmwf.int/forecasts/20260524/00z/ifs/0p25/oper/
# 20260524000000-0h-oper-fc.index).
SAMPLE_ECCODES_TEXT = """\
{"domain": "g", "date": "20260524", "time": "0000", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "levtype": "sfc", "step": "0", "param": "nsss", "_offset": 0, "_length": 224}
{"domain": "g", "date": "20260524", "time": "0000", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "step": "0", "levtype": "sfc", "param": "z", "_offset": 224, "_length": 896851}
{"domain": "g", "date": "20260524", "time": "0000", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "step": "0", "levtype": "sfc", "param": "msl", "_offset": 897075, "_length": 523506}
{"domain": "g", "date": "20260524", "time": "0000", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "step": "0", "levtype": "sfc", "param": "sp", "_offset": 1420581, "_length": 542359}
{"domain": "g", "date": "20260524", "time": "0000", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "step": "0", "levelist": "3", "levtype": "sol", "param": "sot", "_offset": 1962940, "_length": 631815}
"""


def test_parse_idx_eccodes_returns_5_records_from_real_sample() -> None:
    records = parse_idx(SAMPLE_ECCODES_TEXT, style="eccodes")
    assert len(records) == 5


def test_parse_idx_eccodes_first_record_byte_offsets() -> None:
    records = parse_idx(SAMPLE_ECCODES_TEXT, style="eccodes")
    assert records[0].byte_offset == 0
    assert records[0].byte_end == 223  # 0 + 224 - 1


def test_parse_idx_eccodes_second_record_byte_offsets() -> None:
    records = parse_idx(SAMPLE_ECCODES_TEXT, style="eccodes")
    assert records[1].byte_offset == 224
    assert records[1].byte_end == 897074  # 224 + 896851 - 1


def test_parse_idx_eccodes_param_becomes_variable() -> None:
    records = parse_idx(SAMPLE_ECCODES_TEXT, style="eccodes")
    assert records[0].variable == "nsss"
    assert records[2].variable == "msl"


def test_parse_idx_eccodes_levtype_becomes_level_for_sfc() -> None:
    records = parse_idx(SAMPLE_ECCODES_TEXT, style="eccodes")
    assert records[0].level == "sfc"


def test_parse_idx_eccodes_levelist_combined_with_levtype() -> None:
    records = parse_idx(SAMPLE_ECCODES_TEXT, style="eccodes")
    # 5th record has levtype="sol" + levelist="3" → level should be "sol:3"
    assert records[4].level == "sol:3"


def test_parse_idx_eccodes_blank_lines_skipped() -> None:
    text_with_blanks = "\n\n" + SAMPLE_ECCODES_TEXT + "\n\n"
    records = parse_idx(text_with_blanks, style="eccodes")
    assert len(records) == 5


def test_parse_idx_eccodes_empty_text_returns_empty() -> None:
    assert parse_idx("", style="eccodes") == []
    assert parse_idx("\n\n", style="eccodes") == []


def test_parse_idx_eccodes_malformed_json_raises_value_error() -> None:
    with pytest.raises(ValueError, match=r"Malformed \.index JSON"):
        parse_idx('{"_offset": 0, "_length": 100, "incomplete":', style="eccodes")


def test_parse_idx_eccodes_missing_offset_raises_value_error() -> None:
    with pytest.raises(ValueError, match="missing _offset"):
        parse_idx('{"param": "2t", "levtype": "sfc"}', style="eccodes")


# Phase 17 Wave-2 iter-1 review hardening: strict type / range checks.


def test_parse_idx_eccodes_float_offset_rejected() -> None:
    """JSON floats must NOT be silently truncated to int."""
    with pytest.raises(ValueError, match="missing _offset"):
        parse_idx(
            '{"_offset": 0.5, "_length": 100, "param": "2t", "levtype": "sfc"}',
            style="eccodes",
        )


def test_parse_idx_eccodes_negative_offset_rejected() -> None:
    with pytest.raises(ValueError, match="negative _offset"):
        parse_idx(
            '{"_offset": -1, "_length": 100, "param": "2t", "levtype": "sfc"}',
            style="eccodes",
        )


def test_parse_idx_eccodes_zero_length_rejected() -> None:
    with pytest.raises(ValueError, match="non-positive _length"):
        parse_idx(
            '{"_offset": 0, "_length": 0, "param": "2t", "levtype": "sfc"}',
            style="eccodes",
        )


def test_parse_idx_eccodes_missing_param_rejected() -> None:
    with pytest.raises(ValueError, match=r"missing or empty 'param'"):
        parse_idx(
            '{"_offset": 0, "_length": 100, "levtype": "sfc"}',
            style="eccodes",
        )


def test_parse_idx_eccodes_empty_levtype_rejected() -> None:
    with pytest.raises(ValueError, match=r"missing or empty 'levtype'"):
        parse_idx(
            '{"_offset": 0, "_length": 100, "param": "2t", "levtype": ""}',
            style="eccodes",
        )


def test_parse_idx_eccodes_top_level_array_rejected() -> None:
    """A JSON array at the line level is not a record object."""
    with pytest.raises(ValueError, match="not a JSON object"):
        parse_idx("[1, 2, 3]", style="eccodes")


def test_parse_idx_eccodes_record_numbering_sequential() -> None:
    records = parse_idx(SAMPLE_ECCODES_TEXT, style="eccodes")
    assert [r.record_no for r in records] == [1, 2, 3, 4, 5]
