"""Phase 24-01 Task 3: skip the Content-Length HEAD when it isn't needed.

``compute_byte_end`` already derives every non-last record's ``byte_end``
from the next record's offset; only the file's final record needs the
GRIB2 ``Content-Length`` (a HEAD request). HRRR's 9 variables are
mid-file, so the HEAD is pure waste on the common path.

These tests drive ``_try_fetch_records_for_mirror`` with a faked
``.idx`` text and a spy on ``fetch_grib2_content_length`` to assert the
HEAD fires only when a *filtered* record is the file's last one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from mostlyright.weather.forecast_nwp import _try_fetch_records_for_mirror

_IDX_TEXT = (
    "1:0:d=2026010100:TMP:2 m above ground:1 hour fcst:\n"
    "2:100:d=2026010100:DPT:2 m above ground:1 hour fcst:\n"
    "3:200:d=2026010100:LASTVAR:surface:1 hour fcst:\n"
)


def _patch_idx(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Fake fetch_idx_text + spy fetch_grib2_content_length. Returns the spy
    counter dict ``{"head_calls": N}``."""
    counter = {"head_calls": 0}

    def fake_idx(plan: Any, *, client: Any) -> str:
        return _IDX_TEXT

    def spy_content_length(plan: Any, *, client: Any) -> int:
        counter["head_calls"] += 1
        return 300

    monkeypatch.setattr("mostlyright.weather.forecast_nwp.fetch_idx_text", fake_idx)
    monkeypatch.setattr(
        "mostlyright.weather.forecast_nwp.fetch_grib2_content_length", spy_content_length
    )
    return counter


def _call(variable_map: dict[str, tuple[str, str]]) -> Any:
    return _try_fetch_records_for_mirror(
        model="hrrr",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 23, 12, tzinfo=UTC),
        fxx=1,
        variable_map=variable_map,
        client=None,  # unused — fetch_idx_text + HEAD are faked
    )


def test_no_head_when_filtered_records_are_all_mid_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _patch_idx(monkeypatch)
    # TMP + DPT are records 1+2 of 3 — both mid-file, byte_end derivable.
    result = _call(
        {
            "temp_k_2m": ("TMP", "2 m above ground"),
            "dewpoint_k_2m": ("DPT", "2 m above ground"),
        }
    )
    assert counter["head_calls"] == 0, "HEAD issued for mid-file-only variables"
    assert result is not None
    _plan, filtered, _content_length = result
    assert {r.variable for r in filtered} == {"TMP", "DPT"}
    assert all(r.byte_end is not None for r in filtered)


def test_head_issued_when_filtered_set_includes_final_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter = _patch_idx(monkeypatch)
    # LASTVAR is the file's final record — its byte_end is only knowable from
    # Content-Length, so the HEAD must fire and the record must end up bounded.
    result = _call({"x": ("LASTVAR", "surface")})
    assert counter["head_calls"] == 1, "HEAD not issued for final-record variable"
    assert result is not None
    _plan, filtered, _content_length = result
    assert [r.variable for r in filtered] == ["LASTVAR"]
    assert filtered[0].byte_end == 299  # content_length(300) - 1
