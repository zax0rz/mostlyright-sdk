"""Phase 18 PREC-05: cross-source consistency tests.

Same raw METAR through AWC and IEM parsers MUST yield identical temp_c.
This is the key Phase 18 guarantee -- Tgroup re-parsing in both paths
means same source data -> same temp_c value, regardless of which fetcher
produced the row. Also verifies integer-degF recovery for AWC ASOS rows
and float fallback for international (non-Tgroup) AWC rows.
"""

from __future__ import annotations

import pytest
from mostlyright.weather._awc import awc_to_observation
from mostlyright.weather._iem import iem_to_observation


def _make_iem_row(**overrides: str) -> dict[str, str]:
    """Build a minimal IEM CSV row dict that iem_to_observation accepts.

    Matches the shape used by tests/_iem/test_iem_tgroup_consistency.py so
    cross-source assertions exercise the same code path the IEM Tgroup tests
    exercise.
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


# 12 US ASOS METAR fixtures with Tgroup remarks. Each Tgroup encodes the
# integer-degF tmpf/dwpf below: temp_c = round((tmpf-32)*5/9, 1) and
# round(temp_c*9/5+32) == tmpf (and same for dwpf). The tmpf values were
# regenerated from each Tgroup so the AWC integer-degF recovery
# (round(temp_c*9/5+32)) matches the input integer exactly -- the
# cross-source consistency invariant being tested.
US_ASOS_METARS: list[tuple[str, str, float, float, float, float]] = [
    # (station, raw_metar, tmpf, dwpf, expected_temp_c, expected_dewp_c)
    (
        "KLGA",
        "KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 RMK AO2 SLP201 T02670111",
        80.0,
        52.0,
        26.7,
        11.1,
    ),
    (
        "KJFK",
        "KJFK 251151Z 18012KT 10SM FEW040 22/14 A3010 RMK AO2 SLP198 T02220139",
        72.0,
        57.0,
        22.2,
        13.9,
    ),
    (
        "KEWR",
        "KEWR 251151Z 27008KT 10SM CLR 24/12 A3011 RMK AO2 SLP200 T02440117",
        76.0,
        53.0,
        24.4,
        11.7,
    ),
    (
        "KBOS",
        "KBOS 251151Z 25010KT 10SM CLR 19/09 A3013 RMK AO2 SLP205 T01890089",
        66.0,
        48.0,
        18.9,
        8.9,
    ),
    (
        "KORD",
        "KORD 251151Z 22015KT 10SM SCT040 26/15 A3008 RMK AO2 SLP192 T02560150",
        # Tgroup 25.6 degC -> round(25.6*9/5+32) = 78 degF (not 79).
        78.0,
        59.0,
        25.6,
        15.0,
    ),
    (
        "KDFW",
        "KDFW 251151Z 18010KT 10SM CLR 31/18 A3005 RMK AO2 SLP180 T03110178",
        88.0,
        64.0,
        31.1,
        17.8,
    ),
    (
        "KLAX",
        "KLAX 251151Z 25008KT 10SM CLR 22/12 A2998 RMK AO2 SLP155 T02170117",
        # Tgroup 21.7 degC -> round(21.7*9/5+32) = 71 degF (not 72).
        71.0,
        53.0,
        21.7,
        11.7,
    ),
    (
        "KMIA",
        "KMIA 251151Z 09012KT 10SM SCT050 29/22 A3002 RMK AO2 SLP170 T02890222",
        84.0,
        72.0,
        28.9,
        22.2,
    ),
    (
        "KDEN",
        # Tgroup T01501022 -> +15.0 / -2.2 degC. Cold-dewpoint sign-bit case.
        "KDEN 251151Z 18006KT 10SM CLR 15/M02 A3030 RMK AO2 SLP265 T01501022",
        59.0,
        28.0,
        15.0,
        -2.2,
    ),
    (
        "KSEA",
        "KSEA 251151Z 18008KT 10SM OVC020 13/11 A3015 RMK AO2 SLP210 T01330106",
        56.0,
        51.0,
        13.3,
        10.6,
    ),
    (
        "KATL",
        "KATL 251151Z 25006KT 10SM SCT040 24/16 A3005 RMK AO2 SLP180 T02440161",
        76.0,
        61.0,
        24.4,
        16.1,
    ),
    (
        "KPHX",
        "KPHX 251151Z 27010KT 10SM CLR 36/11 A2995 RMK AO2 SLP145 T03560111",
        96.0,
        52.0,
        35.6,
        11.1,
    ),
]


@pytest.mark.parametrize(
    "station, raw_metar, tmpf, dwpf, expected_temp_c, expected_dewp_c",
    US_ASOS_METARS,
    ids=[m[0] for m in US_ASOS_METARS],
)
def test_awc_iem_same_temp_c_for_same_metar(
    station: str,
    raw_metar: str,
    tmpf: float,
    dwpf: float,
    expected_temp_c: float,
    expected_dewp_c: float,
) -> None:
    """AWC and IEM produce identical temp_c / dewpoint_c for the same raw METAR.

    Also verifies AWC's Phase 18 integer-degF recovery path (temp_f is a
    float-valued integer when Tgroup is present) and IEM's raw-tmpf
    passthrough (temp_f equals the input tmpf, unchanged).
    """
    # AWC path -- body-group temp/dewp will be overridden by Tgroup parse
    awc_dict = {
        "icaoId": station,
        "obsTime": 1730000000,
        "metarType": "METAR",
        "temp": round((tmpf - 32) * 5 / 9, 0),  # body-group whole-degC (overridden by Tgroup)
        "dewp": round((dwpf - 32) * 5 / 9, 0),
        "rawOb": raw_metar,
    }
    awc_obs = awc_to_observation(awc_dict)
    assert awc_obs is not None
    assert awc_obs["temp_c"] == expected_temp_c
    assert awc_obs["dewpoint_c"] == expected_dewp_c
    # AWC produces integer-valued float for temp_f / dewpoint_f (Phase 18 PREC-01)
    assert awc_obs["temp_f"] == float(int(awc_obs["temp_f"]))
    assert awc_obs["dewpoint_f"] == float(int(awc_obs["dewpoint_f"]))
    # And the recovered integer degF matches the source tmpf:
    assert int(awc_obs["temp_f"]) == int(tmpf)
    assert int(awc_obs["dewpoint_f"]) == int(dwpf)

    # IEM path
    iem_row = _make_iem_row(
        station=station.lstrip("K"),  # IEM uses non-K-prefixed station code
        valid="2024-10-25 11:51",
        tmpf=str(tmpf),
        dwpf=str(dwpf),
        metar=raw_metar,
    )
    iem_obs = iem_to_observation(iem_row)
    assert iem_obs is not None
    assert iem_obs["temp_c"] == expected_temp_c
    assert iem_obs["dewpoint_c"] == expected_dewp_c
    # IEM preserves raw_temp_f (NOT derived from temp_c)
    assert iem_obs["temp_f"] == tmpf
    assert iem_obs["dewpoint_f"] == dwpf

    # Cross-source: AWC + IEM temp_c MUST be identical
    assert awc_obs["temp_c"] == iem_obs["temp_c"], (
        f"AWC + IEM disagree on temp_c for {station}: "
        f"awc={awc_obs['temp_c']}, iem={iem_obs['temp_c']}"
    )
    assert awc_obs["dewpoint_c"] == iem_obs["dewpoint_c"]
    # Both round to the same integer degF (different coded views of the
    # same integer-degF sensor reading -- AWC float-valued int vs IEM
    # raw-tmpf passthrough -- but they agree on the rounded integer).
    assert round(awc_obs["temp_f"]) == round(iem_obs["temp_f"]) == int(tmpf)


def test_awc_non_tgroup_keeps_float_temp_f() -> None:
    """International AWC METAR (no Tgroup) keeps float temp_f via celsius_to_fahrenheit.

    Anchors the branch-aware behaviour: when parse_tgroup returns
    (None, None) the AWC parser falls back to the legacy
    celsius_to_fahrenheit float path. This is the contract for non-ASOS
    (international, e.g. EGLL) stations that do not emit Tgroup remarks.
    """
    # Synthetic EGLL-style METAR with no RMK section -> no Tgroup
    awc_dict = {
        "icaoId": "EGLL",
        "obsTime": 1730000000,
        "metarType": "METAR",
        "temp": 18.0,  # whole-degC body group
        "dewp": 10.0,
        "rawOb": "EGLL 251150Z AUTO 27008KT 9999 NCD 18/10 Q1015",
    }
    obs = awc_to_observation(awc_dict)
    assert obs is not None
    assert obs["temp_c"] == 18.0
    # No Tgroup -> uses celsius_to_fahrenheit -> 64.4 degF (NOT integer)
    assert obs["temp_f"] == pytest.approx(64.4, abs=0.01)
    # Confirm it is NOT integer-valued (would be the wrong code path if so)
    assert obs["temp_f"] != float(int(obs["temp_f"]))


def test_awc_iem_disagreement_would_fail() -> None:
    """Anti-test: locks the canonical KLGA temp_c at 26.7 for both sources.

    If a future regression breaks AWC or IEM such that one produces
    26.666... (back-derived float) and the other produces 26.7 (Tgroup),
    this test catches it immediately. This is documentation of the
    inversion that the parametrized cross-source test asserts as a
    matrix.
    """
    raw_metar = "KLGA 251151Z 25008KT 10SM CLR 27/11 A3012 RMK AO2 SLP201 T02670111"
    awc_obs = awc_to_observation(
        {
            "icaoId": "KLGA",
            "obsTime": 1730000000,
            "metarType": "METAR",
            "temp": 27.0,
            "dewp": 11.0,
            "rawOb": raw_metar,
        }
    )
    iem_obs = iem_to_observation(
        _make_iem_row(
            station="LGA",
            valid="2024-10-25 11:51",
            tmpf="80.0",
            dwpf="52.0",
            metar=raw_metar,
        )
    )
    # Both MUST be 26.7. If either is 26.666..., Phase 18 has regressed.
    assert awc_obs is not None
    assert iem_obs is not None
    assert awc_obs["temp_c"] == 26.7
    assert iem_obs["temp_c"] == 26.7
    assert awc_obs["temp_c"] == iem_obs["temp_c"]
