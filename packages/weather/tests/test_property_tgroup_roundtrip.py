"""Phase 18 PREC-05: property test for the Tgroup integer-degF round-trip.

The Tgroup encoding in METAR remarks is canonically defined as: integer degF ->
tenths-degC (via (F-32) * 5/9, rounded to 1 decimal place). This test asserts
the inverse holds for every integer degF in the realistic temperature range
[-50, +140]: encode to Tgroup, parse via the shared helper, recover degF via
round(temp_c * 9/5 + 32), and verify it matches the original integer degF.

Uses @pytest.mark.parametrize over the full range (hypothesis is not a
runtime/dev dep of mostlyrightmd-weather; parametrize covers the same ground
because the domain is finite and small: 191 integer values).
"""

from __future__ import annotations

import pytest
from mostlyright.weather._internal.tgroup import parse_tgroup


def _encode_tgroup(temp_c: float, dewp_c: float) -> str:
    """Build a Tgroup string T{s}{SSS}{s}{DDD} from tenths-degC values.

    Format: T followed by sign-bit (0=pos, 1=neg) and 3-digit zero-padded
    abs(value * 10). Example: temp_c=26.7, dewp_c=11.1 -> 'T02670111'.
    Example: temp_c=-3.9, dewp_c=6.1 -> 'T10390061'.
    """
    t_sign = "1" if temp_c < 0 else "0"
    d_sign = "1" if dewp_c < 0 else "0"
    t_abs = round(abs(temp_c) * 10)
    d_abs = round(abs(dewp_c) * 10)
    return f"T{t_sign}{t_abs:03d}{d_sign}{d_abs:03d}"


def _temp_c_for_integer_f(f: int) -> float:
    """Encode an integer degF as the canonical Tgroup tenths-degC value."""
    return round((f - 32) * 5 / 9, 1)


# Realistic temperature range for ASOS observations: [-50, 140] degF.
INTEGER_F_RANGE = list(range(-50, 141))


@pytest.mark.parametrize("f", INTEGER_F_RANGE)
def test_tgroup_roundtrip_temp(f: int) -> None:
    """For every integer degF in [-50, 140], Tgroup round-trip recovers it."""
    temp_c = _temp_c_for_integer_f(f)
    # Dewpoint = same value just so the Tgroup is well-formed
    tgroup = _encode_tgroup(temp_c, temp_c)
    raw_metar = f"METAR KTEST 010000Z 00000KT 10SM CLR M00/M00 A3000 RMK {tgroup}"
    recovered_temp_c, _ = parse_tgroup(raw_metar)
    assert recovered_temp_c is not None, f"parse_tgroup returned None for {tgroup}"
    # IEEE-754 epsilon: the parser may produce 26.700000000000003 from
    # (267 / 10.0); compare with explicit tolerance.
    assert recovered_temp_c == pytest.approx(temp_c, abs=1e-9), (
        f"Tenths-degC mismatch for f={f}: expected {temp_c}, got {recovered_temp_c}"
    )
    recovered_f = round(recovered_temp_c * 9 / 5 + 32)
    assert recovered_f == f, (
        f"Round-trip broken for f={f}: temp_c={temp_c}, tgroup={tgroup}, "
        f"recovered_temp_c={recovered_temp_c}, recovered_f={recovered_f}"
    )


@pytest.mark.parametrize("f", INTEGER_F_RANGE)
def test_tgroup_roundtrip_dewpoint(f: int) -> None:
    """Same property check for the dewpoint position in the Tgroup."""
    dewp_c = _temp_c_for_integer_f(f)
    # Temp position: fixed neutral value 0 degF -> -17.8 degC; not exercised here.
    tgroup = _encode_tgroup(_temp_c_for_integer_f(0), dewp_c)
    raw_metar = f"METAR KTEST 010000Z 00000KT 10SM CLR M00/M00 A3000 RMK {tgroup}"
    _, recovered_dewp_c = parse_tgroup(raw_metar)
    assert recovered_dewp_c is not None, f"parse_tgroup returned None for {tgroup}"
    assert recovered_dewp_c == pytest.approx(dewp_c, abs=1e-9)
    recovered_f = round(recovered_dewp_c * 9 / 5 + 32)
    assert recovered_f == f, (
        f"Dewpoint round-trip broken for f={f}: dewp_c={dewp_c}, "
        f"tgroup={tgroup}, recovered_dewp_c={recovered_dewp_c}, "
        f"recovered_f={recovered_f}"
    )
