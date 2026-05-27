"""Day 3 HARD GATE - 5-fixture byte-equivalent parity vs mostlyright==0.14.1.

This test IS the Sprint 0 parity gate. Sprint 0 ships only if all 5
parametrized cases pass against the captured ``case_*.parquet`` fixtures.
Each case calls ``mostlyright.research(station, frm, to)`` against the
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

import mostlyright
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

FIXTURES = Path(__file__).parent / "fixtures" / "parity"
EXPECTED_DTYPES: dict[str, dict[str, str]] = json.loads(
    (FIXTURES / "expected_dtypes.json").read_text()
)

# Phase 6 W1-T5 + W1 merge gate: ULP drift artifact is required to exist.
# CI's `pandas-resolution: highest` job re-runs measure_ulp_drift.py to
# refresh per_column_max_abs_drift against pandas 3.x; a missing artifact
# blocks the merge. The artifact is loaded at import so an absent file
# fails the entire parity module collection (loudest possible signal).
_ULP_PATH = FIXTURES / "ulp_drift_pd3.json"
if not _ULP_PATH.exists():
    raise RuntimeError(
        "tests/fixtures/parity/ulp_drift_pd3.json missing; required by "
        "Phase 6 W1 merge gate. Run "
        "`uv run python tests/fixtures/parity/measure_ulp_drift.py`."
    )
ULP_DRIFT: dict[str, object] = json.loads(_ULP_PATH.read_text())
PARITY_ATOL: float = float(ULP_DRIFT.get("tolerance_used", 1e-12))


def test_ulp_drift_artifact_under_tolerance() -> None:
    """Per-column max-abs-drift never exceeds the artifact-declared tolerance.

    The artifact's ``tolerance_used`` is the contract the parity test runs
    under; if any per-column max-abs drift > tolerance the script writes
    a looser tolerance and CI flags the promotion. This test fails loudly
    if the artifact is malformed (drift > tolerance is a measurement bug).
    """
    drift = ULP_DRIFT.get("per_column_max_abs_drift", {})
    assert isinstance(drift, dict)
    bad = {col: v for col, v in drift.items() if float(v) > PARITY_ATOL}
    assert not bad, (
        f"ulp_drift_pd3.json declares tolerance_used={PARITY_ATOL} but the "
        f"following per-column drifts exceed it: {bad}. Re-run "
        "tests/fixtures/parity/measure_ulp_drift.py to refresh the artifact."
    )


# (case_num, station_icao, from_date, to_date) - inclusive bounds.
CASES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a fresh, per-test ``MOSTLYRIGHT_CACHE_DIR`` for the parity gate.

    Without this, ``mostlyright.research()`` reads and writes the user's
    persistent ``~/.mostlyright/cache``: a populated cache from an earlier
    (potentially buggy) build can let the gate go green by serving stale
    rows, hiding a fetcher/parser regression - exactly the "leaked state"
    HIGH-severity failure mode that REVIEW-DISCIPLINE.md calls out, and
    the second-order pollution of the developer's real cache.

    ``_cache_root()`` and ``_sources_root()`` both re-read this env var on
    every call (no module-level memoization), so monkeypatching at fixture
    scope cleanly isolates both the parquet observation cache and the
    raw IEM/AWC/GHCNh/CLI source caches under the same tmp_path.

    Codex iter-2 P2 on wave-3, escalated to HIGH per REVIEW-DISCIPLINE's
    leaked-state calibration. Applies to ``test_dtypes_match_ground_truth``
    too (no-op there - it never touches the cache).
    """
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))


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


# pandas 3 ships the new builtin `str` dtype as the default for object-string
# columns read from parquet. The v0.14.1 parity fixtures + expected_dtypes.json
# were captured under pandas 2 (which serializes those columns as `object`).
# Per `tests/fixtures/parity/coerce_pd3.py`, the documented pd2 → pd3 shift on
# string columns is metadata-only (values are byte-identical), so this helper
# rewrites the expected map to the pd3 storage layer when running under pd3.
_PD3 = pd.__version__.split(".", 1)[0] == "3"


def _pd3_translate_expected(expected: dict[str, str], df: pd.DataFrame) -> dict[str, str]:
    if not _PD3:
        return expected
    out = dict(expected)
    for col, dtype_str in expected.items():
        if dtype_str != "object" or col not in df.columns:
            continue
        non_null = df[col].dropna().head(5)
        if not non_null.empty and all(isinstance(v, str) for v in non_null):
            out[col] = "str"
    return out


@pytest.mark.live
@pytest.mark.parametrize(
    "case_num,station,frm,to",
    CASES,
    ids=[f"case-{n}-{s}-{f}-{t}" for n, s, f, t in CASES],
)
def test_parity_case(case_num: int, station: str, frm: str, to: str) -> None:
    """PARITY-01 + PARITY-02: byte-equivalent vs v0.14.1 client.pairs()."""
    expected = pd.read_parquet(FIXTURES / f"case_{case_num}_{station}_{frm}_{to}.parquet")
    actual = mostlyright.research(station, frm, to)

    actual_c = _canon(actual)
    expected_c = _canon(expected)

    # PARITY-03: dtype ground truth.
    actual_dtypes = {col: str(dtype) for col, dtype in actual_c.dtypes.items()}
    expected_dtypes = _pd3_translate_expected(EXPECTED_DTYPES[f"case_{case_num}"], actual_c)
    assert actual_dtypes == expected_dtypes, (
        f"dtype mismatch case {case_num}\nactual:   {actual_dtypes}\nexpected: {expected_dtypes}"
    )

    # PARITY-02: value + dtype equivalence (Rung 3 - see module docstring).
    # `PARITY_ATOL` is loaded from `ulp_drift_pd3.json` so the artifact's
    # `tolerance_used` is the source of truth (codex iter-2 P2 fix —
    # previously hardcoded at 1e-12 which contradicted the artifact when
    # measure_ulp_drift.py promoted to 1e-10). Default seed is 1e-12,
    # which accepts ~1-ULP float-associativity drift in sum-aggregate
    # columns while catching any genuine value regression. Integers/
    # objects/datetimes still require strict equality.
    assert_frame_equal(
        actual_c, expected_c, check_dtype=True, check_exact=False, rtol=0, atol=PARITY_ATOL
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
        expected = _pd3_translate_expected(EXPECTED_DTYPES[f"case_{case_num}"], df)
        assert actual == expected, (
            f"expected_dtypes.json is stale for case_{case_num}; "
            "re-run scripts/capture_expected_dtypes.py"
        )
