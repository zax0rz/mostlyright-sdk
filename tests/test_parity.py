"""Day 3 HARD GATE - 5-fixture byte-equivalent parity vs mostlyright==0.14.1.

This test IS the Sprint 0 parity gate. Sprint 0 ships only if all 5
parametrized cases pass against the captured ``case_*.parquet`` fixtures.
Each case calls ``tradewinds.research(station, frm, to)`` against the
real public APIs (IEM ASOS, IEM CLI, GHCNh) and compares the returned
DataFrame to the v0.14.1 ``client.pairs()`` output.

Marked ``@pytest.mark.live`` per CLAUDE.md testing playbook - the default
``-m "not live"`` pytest invocation skips this; run explicitly with::

    uv run pytest tests/test_parity.py -m live -v

Tolerance ladder (RESEARCH.md Open Q3):
    - Rung 1: ``check_dtype=True, check_exact=True``.
    - Rung 2: ``check_exact=False, rtol=0, atol=0``.
    - Rung 3 (current): ``check_dtype=True, check_exact=False, rtol=0,
      atol=1e-12``.
    - Rung 4: ``check_exact=False, rtol=0, atol=1e-9`` (last resort).

**Chosen rung: Rung 3.** ``research.py`` pre-sorts observations by
``observed_at`` before averaging (R2 mitigation, ``research.py:462``),
but the v0.14.1 hosted-API parquet store iterated rows in a storage
order that is not recoverable from the public IEM/AWC/GHCNh feeds, so
``sum(temps)/len(temps)`` in ``_obs_aggregates`` accumulates the same
inputs in a slightly different order than v0.14.1's hosted code did.
The numeric result is identical to within ~1 ULP; measured worst case
across the 5 fixtures is ``2.84e-14`` (case 4 KMIA, ``obs_mean_f``).
Three float columns drift: ``obs_mean_f``, ``obs_mean_dewpoint_f``,
``obs_total_precip_in`` (all sum-then-divide aggregates). All other
columns - including ints, datetimes, objects, and the min/max float
columns ``obs_high_f``/``obs_low_f`` - match exactly. ``atol=1e-12``
gives ~35,000x headroom over the worst measured drift while still
catching any genuine value regression. Integer columns (``cli_high_f``,
``obs_count``, etc.) still require strict equality because
``assert_frame_equal`` applies the float tolerance only to float
arrays - any int regression remains a hard fail.

PARITY-03: ``expected_dtypes.json`` (captured by
``scripts/capture_expected_dtypes.py``) is the dtype ground truth for
all 5 cases. Drift in dtypes is a HARD failure separate from value drift.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import tradewinds
from pandas.testing import assert_frame_equal

FIXTURES = Path(__file__).parent / "fixtures" / "parity"
EXPECTED_DTYPES: dict[str, dict[str, str]] = json.loads(
    (FIXTURES / "expected_dtypes.json").read_text()
)

# (case_num, station_icao, from_date, to_date) - inclusive bounds.
CASES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]


def _canon(df: pd.DataFrame) -> pd.DataFrame:
    """Promote ``date`` to a column, drop any spurious ``index``, sort.

    Both the v0.14.1 fixture (when loaded via ``pd.read_parquet``) and
    ``research()`` output use ``date`` as the index. The parity comparator
    needs them as a column so ``assert_frame_equal`` treats the date
    identically across sides; subsequent sort keys ensure deterministic
    row order regardless of iteration order in the orchestrator.
    """
    out = df.reset_index() if df.index.name else df.reset_index(drop=True)
    if "index" in out.columns and "date" in out.columns:
        out = out.drop(columns=["index"])
    return out.sort_values(["date", "station"]).reset_index(drop=True)


@pytest.mark.live
@pytest.mark.parametrize(
    "case_num,station,frm,to",
    CASES,
    ids=[f"case-{n}-{s}-{f}-{t}" for n, s, f, t in CASES],
)
def test_parity_case(case_num: int, station: str, frm: str, to: str) -> None:
    """PARITY-01 + PARITY-02: byte-equivalent vs v0.14.1 client.pairs()."""
    expected = pd.read_parquet(FIXTURES / f"case_{case_num}_{station}_{frm}_{to}.parquet")
    actual = tradewinds.research(station, frm, to)

    actual_c = _canon(actual)
    expected_c = _canon(expected)

    # PARITY-03: dtype ground truth.
    actual_dtypes = {col: str(dtype) for col, dtype in actual_c.dtypes.items()}
    assert actual_dtypes == EXPECTED_DTYPES[f"case_{case_num}"], (
        f"dtype mismatch case {case_num}\n"
        f"actual:   {actual_dtypes}\n"
        f"expected: {EXPECTED_DTYPES[f'case_{case_num}']}"
    )

    # PARITY-02: value + dtype equivalence (Rung 3 - see module docstring).
    # `atol=1e-12` accepts ~1-ULP float-associativity drift in sum-aggregate
    # columns while still catching any genuine value regression (~35,000x
    # headroom over the worst measured drift of 2.84e-14 on case 4 KMIA).
    # Integers/objects/datetimes still require strict equality.
    assert_frame_equal(
        actual_c, expected_c, check_dtype=True, check_exact=False, rtol=0, atol=1e-12
    )


def test_dtypes_match_ground_truth() -> None:
    """PARITY-03: ``expected_dtypes.json`` matches the fixture parquets.

    This is a tautology against the capture script - it locks the JSON to
    the parquet files so a regenerated fixture cannot silently drift the
    dtype contract.
    """
    for case_num, station, frm, to in CASES:
        df = pd.read_parquet(FIXTURES / f"case_{case_num}_{station}_{frm}_{to}.parquet")
        df = df.reset_index() if df.index.name else df
        actual = {col: str(dtype) for col, dtype in df.dtypes.items()}
        assert actual == EXPECTED_DTYPES[f"case_{case_num}"], (
            f"expected_dtypes.json is stale for case_{case_num}; "
            "re-run scripts/capture_expected_dtypes.py"
        )
