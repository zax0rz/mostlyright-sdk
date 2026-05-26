"""Phase 18 PREC-02 — unit tests for the shared Tgroup parser extracted from _awc.py.

RED step lands first; GREEN follows in Task 2.

The Tgroup is the canonical tenths-°C encoding of the integer-°F ASOS reading
embedded in METAR remarks (after the literal token ``RMK``). Format:
``T{s}{SSS}{s}{DDD}`` where ``s=0`` is positive, ``s=1`` is negative, ``SSS`` is
temperature tenths-°C, ``DDD`` is dewpoint tenths-°C.

These tests pin the public contract of ``parse_tgroup`` so AWC and IEM parsers
share a single source of truth (plans 18-01/02/03 of the precision fix).
"""

from __future__ import annotations

import pytest
from mostlyright.weather._internal.tgroup import parse_tgroup


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("METAR KLGA RMK T02670111", (26.7, 11.1)),
        ("METAR KORD RMK T10390061", (-3.9, 6.1)),
        ("METAR KMSP RMK T11250089", (-12.5, 8.9)),
        ("METAR RMK T00200067", (2.0, 6.7)),
    ],
)
def test_parses_tenths_celsius_signed(raw: str, expected: tuple[float, float]) -> None:
    """Tgroup decodes correctly when present in METAR remarks (happy path matrix)."""
    assert parse_tgroup(raw) == expected


def test_positive_temp_positive_dewpoint() -> None:
    """T02670111 -> 26.7C / 11.1C."""
    assert parse_tgroup("METAR KLGA RMK T02670111") == (26.7, 11.1)


def test_negative_temp_positive_dewpoint() -> None:
    """T10390061 -> -3.9C / 6.1C (s=1 on first sign group)."""
    assert parse_tgroup("METAR KORD RMK T10390061") == (-3.9, 6.1)


def test_negative_temp_negative_dewpoint() -> None:
    """T11251089 -> -12.5C / -8.9C (s=1 on both sign groups)."""
    assert parse_tgroup("METAR KMSP RMK T11251089") == (-12.5, -8.9)


def test_no_rmk_section_returns_none() -> None:
    """No RMK token in the raw METAR => no Tgroup search => (None, None)."""
    assert parse_tgroup("METAR KLGA") == (None, None)


def test_tgroup_in_body_without_rmk_returns_none() -> None:
    """Tgroup-like pattern in body without RMK marker must NOT match.

    The contract is remarks-only: the parser searches the slice AFTER the
    literal ``RMK`` to avoid false positives on body group patterns.
    """
    assert parse_tgroup("METAR KLGA T02670111") == (None, None)


def test_rmk_present_but_no_tgroup_returns_none() -> None:
    """RMK section exists but does not contain a Tgroup => (None, None)."""
    assert parse_tgroup("METAR KLGA RMK AO2") == (None, None)


def test_empty_string_returns_none() -> None:
    """Empty string => (None, None)."""
    assert parse_tgroup("") == (None, None)


def test_none_input_returns_none() -> None:
    """``None`` input => (None, None) — defensive against missing rawOb."""
    assert parse_tgroup(None) == (None, None)
