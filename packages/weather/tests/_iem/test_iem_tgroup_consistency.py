"""Phase 18 PREC-02 — RED tests for IEM Tgroup-override of temp_c + cross-source consistency with AWC.

Implementation lands in Task 2.

Locked behaviour under test (per 18-03-PLAN.md and 18-CONTEXT.md §"Locked scope" point 2):

1. When an IEM CSV row's ``metar`` column carries a Tgroup remark, IEM must emit
   ``temp_c`` / ``dewpoint_c`` equal to the tenths-°C Tgroup values — NOT the
   back-derived ``(tmpf - 32) * 5/9`` that arises from IEM's pre-rounded integer
   ``tmpf`` field.
2. When the raw METAR has no Tgroup (international stations, malformed/empty
   metar string), IEM falls back to the existing ``fahrenheit_to_celsius``
   derivation — backward compatible for non-ASOS rows.
3. ``temp_f`` MUST remain the raw ``tmpf`` passthrough (``raw_temp_f``). DO NOT
   introduce a ``temp_c * 9/5 + 32 == temp_f`` invariant. The two fields are
   different coded views of the same integer-°F sensor reading.
4. For the same raw METAR processed through AWC and IEM, both yield identical
   ``temp_c`` — the Tgroup tenths-°C value. This is the cross-source consistency
   guarantee (Codex explicitly verified this in issue #16 comment 4548783363).
"""

from __future__ import annotations

import pytest


def _make_iem_row(**overrides: str) -> dict[str, str]:
    """Build a minimal IEM CSV row dict that ``iem_to_observation`` accepts.

    Defaults intentionally use a raw METAR that contains a Tgroup remark
    (T02670111 -> 26.7°C / 11.1°C) plus tmpf=80.00 / dwpf=52.00 — the canonical
    Tgroup-present ASOS shape we are testing.
    """
    base: dict[str, str] = {
        "station": "LGA",
        "valid": "2024-10-25 11:51",
        "tmpf": "80.00",
        "dwpf": "52.00",
        "relh": "M",
        "drct": "M",
        "sknt": "M",
        "p01i": "M",
        "alti": "M",
        "mslp": "1015.00",
        "vsby": "M",
        "gust": "M",
        "skyc1": "M",
        "skyc2": "M",
        "skyc3": "M",
        "skyc4": "M",
        "skyl1": "M",
        "skyl2": "M",
        "skyl3": "M",
        "skyl4": "M",
        "wxcodes": "M",
        "ice_accretion_1hr": "M",
        "ice_accretion_3hr": "M",
        "ice_accretion_6hr": "M",
        "peak_wind_gust": "M",
        "peak_wind_drct": "M",
        "peak_wind_time": "M",
        "feel": "M",
        "metar": (
            "KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 " "RMK AO2 SLP201 T02670111 10272 20217"
        ),
        "snowdepth": "M",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test A — Tgroup override of temp_c / dewpoint_c; temp_f / dewpoint_f preserved
# ---------------------------------------------------------------------------
class TestTgroupOverridesTempC:
    """When raw METAR has a Tgroup, IEM uses tenths-°C from Tgroup, not the
    back-derivation of integer tmpf."""

    def test_temp_c_from_tgroup_not_back_derived(self) -> None:
        """tmpf=80.0 + Tgroup T02670111 → temp_c == 26.7 (NOT 26.666…)."""
        from mostlyright.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_iem_row())
        assert obs is not None
        # Tgroup tenths-°C wins. 26.666... is the back-derived (wrong) value.
        assert obs["temp_c"] == 26.7

    def test_dewpoint_c_from_tgroup_not_back_derived(self) -> None:
        """dwpf=52.0 + Tgroup T02670111 → dewpoint_c == 11.1 (NOT 11.111…)."""
        from mostlyright.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_iem_row())
        assert obs is not None
        assert obs["dewpoint_c"] == 11.1

    def test_temp_f_remains_raw_tmpf(self) -> None:
        """temp_f stays at raw tmpf (80.0). NOT derived from temp_c.

        Codex explicitly warned against introducing a ``temp_c * 9/5 + 32 ==
        temp_f`` invariant — temp_c (tenths-°C) and temp_f (integer-°F) are
        different coded views of the same underlying integer-°F sensor reading.
        """
        from mostlyright.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_iem_row())
        assert obs is not None
        assert obs["temp_f"] == 80.0

    def test_dewpoint_f_remains_raw_dwpf(self) -> None:
        """dewpoint_f stays at raw dwpf (52.0). NOT derived from dewpoint_c."""
        from mostlyright.weather._iem import iem_to_observation

        obs = iem_to_observation(_make_iem_row())
        assert obs is not None
        assert obs["dewpoint_f"] == 52.0


# ---------------------------------------------------------------------------
# Test B — no Tgroup, integer-°C-native international station
# ---------------------------------------------------------------------------
class TestNoTgroupInternationalFallback:
    """International stations (LFPG, EGLL, EDDF, ...) do NOT emit Tgroup in
    METAR remarks per ICAO — they report integer-°C natively in the body group.

    For these rows the IEM ``metar`` column has no ``RMK ... T0XXX...`` segment
    and IEM must fall back to ``fahrenheit_to_celsius(raw_temp_f)``.
    """

    def test_lfpg_no_tgroup_uses_legacy_derivation(self) -> None:
        """64.4°F → 18.0°C exactly (legacy path, no Tgroup)."""
        from mostlyright.weather._iem import iem_to_observation

        row = _make_iem_row(
            station="LFPG",
            tmpf="64.4",
            dwpf="50.0",
            metar="LFPG 251200Z 23008KT 9999 SCT040 18/10 Q1016 NOSIG",
        )
        obs = iem_to_observation(row)
        assert obs is not None
        # fahrenheit_to_celsius(64.4) = (64.4 - 32) * 5/9 = 18.0 exactly.
        assert obs["temp_c"] == 18.0
        assert obs["temp_f"] == 64.4

    def test_no_rmk_section_uses_legacy_derivation(self) -> None:
        """METAR body-only, no RMK at all → legacy fahrenheit_to_celsius path."""
        from mostlyright.weather._iem import iem_to_observation

        row = _make_iem_row(
            tmpf="50.0",
            dwpf="32.0",
            metar="EGLL 251200Z 27010KT 9999 SCT035 10/00 Q1013 NOSIG",
        )
        obs = iem_to_observation(row)
        assert obs is not None
        assert obs["temp_c"] == 10.0  # (50-32)*5/9 = 10.0 exactly
        assert obs["temp_f"] == 50.0


# ---------------------------------------------------------------------------
# Test C — no Tgroup, empty metar string
# ---------------------------------------------------------------------------
class TestNoMetarStringUsesLegacy:
    """Empty/missing ``metar`` field still allows IEM to emit a row — and
    temp_c then falls back to the legacy back-derivation.

    This pins the fallback contract explicitly: parse_tgroup("") → (None, None),
    so IEM uses fahrenheit_to_celsius. The back-derivation produces 26.666… for
    integer tmpf=80; this is intentional documentation of the legacy path.
    """

    def test_empty_metar_string_falls_back_to_back_derivation(self) -> None:
        from mostlyright.weather._iem import iem_to_observation

        row = _make_iem_row(tmpf="80.0", dwpf="52.0", metar="")
        obs = iem_to_observation(row)
        assert obs is not None
        # Legacy fallback: fahrenheit_to_celsius(80.0) = 26.666...
        assert obs["temp_c"] is not None
        assert abs(obs["temp_c"] - 26.6666666667) < 0.01
        assert obs["temp_f"] == 80.0


# ---------------------------------------------------------------------------
# Test D — negative Tgroup (cold)
# ---------------------------------------------------------------------------
class TestNegativeTgroup:
    """Cold-weather METAR with Tgroup like T10390061 → -3.9°C / 6.1°C.

    The first sign digit (1) means negative temperature; the second sign digit
    (0) means positive dewpoint. ``temp_f = raw_temp_f`` regardless.
    """

    def test_negative_temp_tgroup(self) -> None:
        from mostlyright.weather._iem import iem_to_observation

        row = _make_iem_row(
            tmpf="25.0",
            dwpf="43.0",
            metar="KORD 011251Z 27010KT 10SM CLR M04/06 A2992 RMK AO2 SLP132 T10390061",
        )
        obs = iem_to_observation(row)
        assert obs is not None
        assert obs["temp_c"] == -3.9
        assert obs["dewpoint_c"] == 6.1
        # temp_f preserved (raw_temp_f passthrough — NOT derived from -3.9°C).
        assert obs["temp_f"] == 25.0
        assert obs["dewpoint_f"] == 43.0


# ---------------------------------------------------------------------------
# Test E — cross-source consistency: AWC ≡ IEM temp_c on same raw METAR
# ---------------------------------------------------------------------------
class TestCrossSourceConsistency:
    """The acceptance criterion from 18-CONTEXT.md:

        "For every Tgroup-sourced observation, AWC and IEM paths produce
        identical temp_c for the same raw METAR."

    This is the key invariant Codex flagged in the issue-#16 verification. The
    merge layer (AWC > IEM > GHCNh) only matters for missing-source fallback;
    when both sources see the same observation they must agree on temp_c.
    """

    def test_awc_and_iem_yield_identical_temp_c(self) -> None:
        from mostlyright.weather._awc import awc_to_observation
        from mostlyright.weather._iem import iem_to_observation

        raw_metar = (
            "KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 " "RMK AO2 SLP201 T02670111 10272 20217"
        )

        awc_obs = awc_to_observation(
            {
                "icaoId": "KLGA",
                "obsTime": 1729857060,  # 2024-10-25T11:51:00Z
                "metarType": "METAR",
                "temp": 27.0,
                "dewp": 11.0,
                "wdir": 250,
                "wspd": 8,
                "wgst": None,
                "altim": 1020.0,
                "slp": 1020.1,
                "visib": "10",
                "wxString": None,
                "clouds": [{"cover": "CLR", "base": None}],
                "precip": None,
                "rawOb": raw_metar,
                "qcField": 6,
            }
        )
        iem_obs = iem_to_observation(
            _make_iem_row(
                station="KLGA",
                valid="2024-10-25 11:51",
                tmpf="80.0",
                dwpf="52.0",
                metar=raw_metar,
            )
        )

        assert awc_obs is not None
        assert iem_obs is not None
        # The headline cross-source invariant.
        assert awc_obs["temp_c"] == iem_obs["temp_c"] == 26.7
        assert awc_obs["dewpoint_c"] == iem_obs["dewpoint_c"] == 11.1

    def test_temp_f_coded_views_both_round_to_same_integer(self) -> None:
        """AWC and IEM temp_f are different coded views (integer °F vs float
        passthrough) of the same underlying reading. They round to the same
        integer °F. Asserted separately because the types diverge by design.

        Note: in the current Phase 18 staging, AWC temp_f is still
        ``celsius_to_fahrenheit(temp_c)`` (80.06°F-style); plan 18-02 fixes
        that to integer-°F. Both values round to 80, so this test is
        forward-compatible with 18-02 landing.
        """
        from mostlyright.weather._awc import awc_to_observation
        from mostlyright.weather._iem import iem_to_observation

        raw_metar = (
            "KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 " "RMK AO2 SLP201 T02670111 10272 20217"
        )
        awc_obs = awc_to_observation(
            {
                "icaoId": "KLGA",
                "obsTime": 1729857060,
                "metarType": "METAR",
                "temp": 27.0,
                "dewp": 11.0,
                "wdir": 250,
                "wspd": 8,
                "wgst": None,
                "altim": 1020.0,
                "slp": 1020.1,
                "visib": "10",
                "wxString": None,
                "clouds": [{"cover": "CLR", "base": None}],
                "precip": None,
                "rawOb": raw_metar,
                "qcField": 6,
            }
        )
        iem_obs = iem_to_observation(
            _make_iem_row(
                station="KLGA",
                valid="2024-10-25 11:51",
                tmpf="80.0",
                dwpf="52.0",
                metar=raw_metar,
            )
        )
        assert awc_obs is not None
        assert iem_obs is not None
        # IEM temp_f is the raw integer-°F float passthrough (80.0).
        assert iem_obs["temp_f"] == 80.0
        # AWC temp_f rounds to the same integer °F (whether 80 int or 80.06 float).
        assert round(awc_obs["temp_f"]) == 80


# ---------------------------------------------------------------------------
# Test F — Tgroup outside bounds → bounded_float nulls; consistency guard nulls temp_f
# ---------------------------------------------------------------------------
class TestTgroupBoundedOut:
    """If the Tgroup value lands outside ``[TEMP_MIN_C, TEMP_MAX_C]``, the
    existing ``bounded_float`` consistency guard at _iem.py kicks in: both
    ``temp_c`` and ``temp_f`` are nulled. This proves the override doesn't
    bypass schema bounds.
    """

    def test_tgroup_above_max_nulls_both(self) -> None:
        from mostlyright.weather._iem import iem_to_observation

        # T0555 = 55.5°C. TEMP_MAX_C in _bounds is 60, so 55.5 is bounded IN
        # by the schema. We need a value above the cap — use T08881111 = 88.8°C.
        row = _make_iem_row(
            tmpf="200.0",  # bogus reading; bounded out by TEMP_MAX_C in the F→C path too
            dwpf="50.0",
            metar="KXXX 011251Z RMK T08880000",
        )
        obs = iem_to_observation(row)
        assert obs is not None
        # Tgroup 88.8°C is above TEMP_MAX_C → temp_c is None.
        assert obs["temp_c"] is None
        # Consistency: raw °F is also nulled.
        assert obs["temp_f"] is None


# ---------------------------------------------------------------------------
# Test G — Tgroup encodes BOTH temp and dewp; the body group dwpf is overridden
# ---------------------------------------------------------------------------
class TestTgroupOverridesBothFields:
    """The Tgroup carries both temp and dewp tenths-°C. Even if the IEM ``dwpf``
    column says a value that back-derives differently, the Tgroup wins for
    ``dewpoint_c``."""

    def test_dewp_overridden_when_tgroup_present(self) -> None:
        from mostlyright.weather._iem import iem_to_observation

        # dwpf=51.0 would back-derive to 10.555... °C. Tgroup says 11.1.
        row = _make_iem_row(
            tmpf="80.0",
            dwpf="51.0",
            metar=("KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 " "RMK AO2 SLP201 T02670111"),
        )
        obs = iem_to_observation(row)
        assert obs is not None
        # Tgroup wins for both.
        assert obs["temp_c"] == 26.7
        assert obs["dewpoint_c"] == 11.1
        # But raw °F columns stay raw (51.0 NOT 52.0).
        assert obs["temp_f"] == 80.0
        assert obs["dewpoint_f"] == 51.0


# ---------------------------------------------------------------------------
# Sanity: parametric matrix mirroring the AWC tgroup test suite
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("tgroup_text", "expected_temp_c", "expected_dewp_c"),
    [
        ("T02670111", 26.7, 11.1),
        ("T10390061", -3.9, 6.1),
        ("T00200067", 2.0, 6.7),
        ("T11251089", -12.5, -8.9),
    ],
)
def test_iem_tgroup_matrix(
    tgroup_text: str, expected_temp_c: float, expected_dewp_c: float
) -> None:
    """Tenths-°C matrix mirroring tests/_internal/test_tgroup.py — verifies the
    IEM caller passes through the shared parser results unchanged."""
    from mostlyright.weather._iem import iem_to_observation

    # tmpf below TEMP_MAX_C lattice in °F: pick something inside bounds for each.
    # Use generic 60°F / 30°F for all; we only care that the Tgroup override wins.
    row = _make_iem_row(
        tmpf="60.0",
        dwpf="30.0",
        metar=f"KXXX 011251Z 27010KT 10SM CLR 15/M01 A2992 RMK AO2 {tgroup_text}",
    )
    obs = iem_to_observation(row)
    assert obs is not None
    assert obs["temp_c"] == expected_temp_c
    assert obs["dewpoint_c"] == expected_dewp_c
    # Raw °F passthrough regardless of Tgroup value.
    assert obs["temp_f"] == 60.0
    assert obs["dewpoint_f"] == 30.0
