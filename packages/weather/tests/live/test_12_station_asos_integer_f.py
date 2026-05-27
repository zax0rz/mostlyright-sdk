"""Phase 18 PREC-05: 12-station live anti-regression test for ASOS Tgroup
integer-°F lattice.

Pulls fresh METARs via AWC for the 12 canonical U.S. ASOS stations and asserts
every Tgroup-derived ``temp_c`` round-trips from an integer °F. This catches
any regression where the parser drifts off the integer-°F lattice — the
empirical invariant for U.S. ASOS observation Tgroups (Phase 18 CONTEXT.md).

Marked ``@pytest.mark.live``: excluded from CI fast runs
(``pytest -m "not live"``). Run manually before each publish:

    uv run pytest -m live packages/weather/tests/live/test_12_station_asos_integer_f.py -v
"""

from __future__ import annotations

import pytest
from mostlyright.weather._fetchers.awc import fetch_awc_metars
from mostlyright.weather._internal.tgroup import parse_tgroup

STATIONS = [
    "KLGA",
    "KJFK",
    "KEWR",
    "KBOS",
    "KORD",
    "KDFW",
    "KLAX",
    "KMIA",
    "KDEN",
    "KSEA",
    "KATL",
    "KPHX",
]


@pytest.mark.live
@pytest.mark.parametrize("station", STATIONS)
def test_12_station_tgroup_round_trips_from_integer_f(station: str) -> None:
    """Every Tgroup tenth-°C parsed from a station's last 168h of METARs must
    round-trip from an integer °F (the empirical ASOS invariant).

    The integer-°F lattice ``{round((f - 32) * 5 / 9, 1) for f in range(-50, 140)}``
    covers the realistic surface-temperature range. Any observed Tgroup value
    not on this lattice signals a parser drift or upstream data shift.
    """
    metars = fetch_awc_metars([station], hours=168)
    observed: list[float] = []
    for m in metars:
        tc, td = parse_tgroup(m.get("rawOb") or "")
        if tc is not None:
            observed.append(tc)
        if td is not None:
            observed.append(td)

    # Every observed Tgroup tenth-°C must round-trip from an integer °F.
    implied_c = {round((f - 32) * 5 / 9, 1) for f in range(-50, 140)}
    mismatches = [c for c in observed if c not in implied_c]
    assert not mismatches, (
        f"{station}: {len(mismatches)} Tgroup values not on integer-°F lattice: "
        f"{sorted(set(mismatches))[:10]}"
    )
    assert len(observed) > 0, f"{station}: no Tgroup readings in last 168h (test data sparse)"
