"""Phase 20 OM-08: 5-fixture leakage regression suite.

The headline test reproduces Tarabcak/mostlyright#70 — the NYC 2024-06-01
h13 EDT (17:00 UTC) snapshot training row must contain ONLY forecasts
with ``issued_at <= 17:00 UTC``. Phase 20's conservative-floor formula
(``issued_at = floor_to_cycle(valid_at - 24h, cycles)``) makes this
provably true.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest

from mostlyright.core.temporal.leakage import (
    LeakageDetector,
    assert_issued_at_populated,
)
from mostlyright.core.temporal.timepoint import TimePoint
from mostlyright.weather._fetchers._open_meteo import fetch_open_meteo

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "openmeteo"


CASES = [
    ("KNYC", "2024-06-01", "2024-06-01T17:00:00Z",
     "case_1_KNYC_2024-06-01_h13.json",
     "Tarabcak/mostlyright#70 reproduction"),
    ("KMDW", "2024-07-15", "2024-07-15T12:00:00Z",
     "case_2_KORD_2024-07-15_h07.json", "Pre-noon snapshot"),
    ("KDEN", "2024-08-22", "2024-08-22T22:00:00Z",
     "case_3_KDEN_2024-08-22_h16.json", "Post-cycle-publish snapshot"),
    ("KMIA", "2024-09-10", "2024-09-10T00:00:00Z",
     "case_4_KMIA_2024-09-10_midnight.json", "Midnight UTC boundary"),
    ("KSEA", "2024-10-05", "2024-10-05T20:00:00Z",
     "case_5_KSEA_2024-10-05_h13.json", "Pacific timezone"),
]


def _make_mock_client(payload: dict) -> MagicMock:
    client = MagicMock(spec=httpx.Client)
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client.get.return_value = response
    return client


@pytest.mark.parametrize("station,date_iso,as_of_iso,fixture_name,comment", CASES)
def test_no_leakage_per_fixture(
    station: str,
    date_iso: str,
    as_of_iso: str,
    fixture_name: str,
    comment: str,
) -> None:
    """Each fixture: every row's issued_at must be <= as_of."""
    fixture_path = FIXTURES_DIR / fixture_name
    assert fixture_path.exists(), f"missing fixture: {fixture_path}"
    payload = json.loads(fixture_path.read_text())

    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        station,
        date_iso,
        date_iso,
        model="gfs_global",
        mode="training",
        client=client,
    )

    if len(df) == 0:
        pytest.skip(f"{comment}: empty DataFrame (synthesized fixture)")

    as_of = pd.Timestamp(as_of_iso)
    issued_ats = df["issued_at"].dropna()
    assert (issued_ats <= as_of).all(), (
        f"{comment}: row(s) with issued_at > as_of detected; "
        f"max issued_at={issued_ats.max()}, as_of={as_of}"
    )

    # LeakageDetector.check_issued_at + assert_issued_at_populated should not raise
    detector = LeakageDetector(as_of=TimePoint(as_of_iso))
    detector.check_issued_at(df)
    assert_issued_at_populated(df)

    if "source" in df.columns and len(df) > 0:
        assert "open_meteo.seamless" not in df["source"].unique()


def test_case_1_exact_70_reproduction() -> None:
    """The 23:00 UTC valid_at row in case_1 must have
    issued_at == 2024-05-31T18:00Z.

    This is the exact corner case Tarabcak/mostlyright#70 broke — the
    conservative-floor formula in PLAN-03's issued_at_from_previous_day
    makes the legacy bug impossible to recur.
    """
    fixture_path = FIXTURES_DIR / "case_1_KNYC_2024-06-01_h13.json"
    payload = json.loads(fixture_path.read_text())

    client = _make_mock_client(payload)
    df = fetch_open_meteo(
        "KNYC",
        "2024-06-01",
        "2024-06-01",
        model="gfs_global",
        mode="training",
        client=client,
    )

    h23 = df[df["valid_at"] == pd.Timestamp("2024-06-01T23:00:00Z")]
    assert len(h23) == 1, f"expected 1 h23 row, got {len(h23)}"

    expected_issued_at = pd.Timestamp("2024-05-31T18:00:00Z")
    actual_issued_at = h23["issued_at"].iloc[0]
    assert actual_issued_at == expected_issued_at, (
        f"#70 reproduction failed: expected issued_at={expected_issued_at}, "
        f"got {actual_issued_at}. The conservative floor formula must "
        f"return 2024-05-31T18:00Z for valid_at=2024-06-01T23:00Z + GFS cycles."
    )

    as_of_h13 = pd.Timestamp("2024-06-01T17:00:00Z")
    assert actual_issued_at < as_of_h13, (
        f"#70 reproduction would have leaked: "
        f"issued_at={actual_issued_at} >= as_of={as_of_h13}"
    )
