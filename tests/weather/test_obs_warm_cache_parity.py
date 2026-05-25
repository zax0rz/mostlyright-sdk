"""Byte-equivalence parity: obs(strategy='warm_cache') obs aggregates ==
v0.14.1 research() Mode-1 obs columns, for all 5 Phase 1 parity fixtures.

This re-uses Phase 1's HARD gate fixtures to prove warm_cache preserves
the v0.14.1 contract for the obs subset of research()'s output.

Cache isolation per fixture mirrors tests/test_parity.py's `_isolated_cache`
fixture — without it the user's persistent cache could mask regressions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "parity"

# Pattern: case_<N>_<STATION>_<FROM>_<TO>.parquet
_NAME_RE = re.compile(r"^case_(\d+)_([A-Z]+)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.parquet$")


def _discover_cases() -> list[tuple[int, str, str, str, Path]]:
    cases: list[tuple[int, str, str, str, Path]] = []
    for fp in sorted(FIXTURE_DIR.glob("case_*.parquet")):
        m = _NAME_RE.match(fp.name)
        if not m:
            continue
        n, station, frm, to = m.groups()
        cases.append((int(n), station, frm, to, fp))
    return cases


CASES = _discover_cases()

# Obs aggregates that obs(strategy='warm_cache') and research() Mode-1 share.
OBS_AGG_COLUMNS = [
    "obs_high_f",
    "obs_low_f",
    "obs_mean_f",
    "obs_mean_dewpoint_f",
    "obs_max_wind_kt",
    "obs_max_gust_kt",
    "obs_total_precip_in",
    "obs_count",
]


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Per-test TRADEWINDS_CACHE_DIR — mirrors tests/test_parity.py."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))


@pytest.mark.live  # research()/obs() hit live IEM/AWC/GHCNh
@pytest.mark.parametrize(
    "case_num,station,frm,to,fixture_path",
    CASES,
    ids=[f"case-{n}-{s}-{f}-{t}" for n, s, f, t, _ in CASES],
)
def test_obs_warm_cache_byte_equiv_to_research_obs_columns(
    case_num: int, station: str, frm: str, to: str, fixture_path: Path
) -> None:
    """obs(strategy='warm_cache') obs aggregates byte-match the fixture's
    obs_* columns at the Rung 3 tolerance (atol=1e-12)."""
    from mostlyright.weather import obs

    expected = pd.read_parquet(fixture_path)
    expected = expected.reset_index() if expected.index.name else expected
    if "index" in expected.columns and "date" in expected.columns:
        expected = expected.drop(columns=["index"])

    obs_cols_present = [c for c in OBS_AGG_COLUMNS if c in expected.columns]
    if not obs_cols_present:
        pytest.skip(
            f"fixture {fixture_path.name} has no obs_* columns "
            "(climate-only); not applicable to warm_cache parity."
        )

    actual = obs(
        station,
        frm,
        to,
        source=None,
        strategy="warm_cache",
        as_dataframe=True,
    )

    expected_cmp = (
        expected[["date", "station", *obs_cols_present]]
        .sort_values(["date", "station"])
        .reset_index(drop=True)
    )
    actual_cmp = (
        actual[["date", "station", *obs_cols_present]]
        .sort_values(["date", "station"])
        .reset_index(drop=True)
    )

    # Rung 3 tolerance per tests/test_parity.py (R2 float-order drift, ~1 ULP).
    assert_frame_equal(
        actual_cmp,
        expected_cmp,
        check_dtype=True,
        check_exact=False,
        rtol=0,
        atol=1e-12,
    )
