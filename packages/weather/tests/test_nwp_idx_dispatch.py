"""Phase 17 FORECAST-04: ``parse_idx`` dispatch over wgrib2/eccodes styles."""

from __future__ import annotations

import pytest
from mostlyright.weather._fetchers._nwp_idx import parse_idx

WGRIB2_SAMPLE = """\
1:0:d=2026052412:TMP:2 m above ground:6 hour fcst:
2:100000:d=2026052412:DPT:2 m above ground:6 hour fcst:
3:200000:d=2026052412:UGRD:10 m above ground:6 hour fcst:
"""


def test_parse_idx_default_style_is_wgrib2_backward_compat() -> None:
    records_default = parse_idx(WGRIB2_SAMPLE)
    records_explicit = parse_idx(WGRIB2_SAMPLE, style="wgrib2")
    assert records_default == records_explicit
    assert len(records_default) == 3
    assert records_default[0].variable == "TMP"
    assert records_default[0].level == "2 m above ground"


def test_parse_idx_eccodes_style_raises_not_implemented_in_wave1() -> None:
    """eccodes body lands in Phase 17 PLAN-04."""
    with pytest.raises(NotImplementedError, match="PLAN-04"):
        parse_idx("anything", style="eccodes")


def test_parse_idx_invalid_style_raises_value_error() -> None:
    with pytest.raises(ValueError, match="style must be one of"):
        parse_idx("anything", style="invalid")  # type: ignore[arg-type]
