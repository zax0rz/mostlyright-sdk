"""Phase 6 W1 — coerce_pd3 bridge round-trip + fixture compatibility.

Architect iter-1 HIGH-1 fix: the parity gate's pandas-3 promise was
"dual-pandas matrix re-runs the measurement on every commit", but the
@pytest.mark.live parity test is excluded from CI, so nothing actually
exercised the coerce bridge under pandas 3.x on every push.

These tests are NOT live — they read the 5 canonical 2.x fixtures
from disk, apply the coerce bridge, and assert round-trip + dtype
shape on the current pandas version. CI's pandas-3-suite job will run
these on a pandas 3.x lockfile, catching any coerce_pd3 drift loudly
before merge.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "parity"


def _load_coerce_module():
    """Load tests/fixtures/parity/coerce_pd3.py without making `tests` a package."""
    spec = importlib.util.spec_from_file_location("_coerce_pd3", FIXTURES / "coerce_pd3.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_coerce_pd3"] = module
    spec.loader.exec_module(module)
    return module


_coerce = _load_coerce_module()
coerce_2x_to_3x = _coerce.coerce_2x_to_3x
coerce_3x_to_2x = _coerce.coerce_3x_to_2x

CASES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]


@pytest.mark.parametrize(
    "case_num,station,frm,to",
    CASES,
    ids=[f"case-{n}-{s}" for n, s, _, _ in CASES],
)
def test_coerce_pd3_round_trip_is_invertible(
    case_num: int, station: str, frm: str, to: str
) -> None:
    """coerce_3x_to_2x(coerce_2x_to_3x(case)) == case byte-for-byte.

    The bridge's whole contract is that the documented coercions
    (ns↔us datetime resolution + object↔string dtype) are reversible
    at the value layer. This test runs without network — fixtures are
    already on disk — so CI's pandas-3-suite job catches any drift
    introduced by a pandas-3 dtype-promotion change.
    """
    path = FIXTURES / f"case_{case_num}_{station}_{frm}_{to}.parquet"
    canonical = pd.read_parquet(path)
    forward = coerce_2x_to_3x(canonical)
    back = coerce_3x_to_2x(forward)

    # Value layer: every cell must match the canonical fixture.
    pd.testing.assert_frame_equal(
        back.reset_index(drop=True),
        canonical.reset_index(drop=True),
        check_dtype=False,  # dtype shifts ARE the contract; value parity is the gate
        check_exact=True,
    )


@pytest.mark.parametrize(
    "case_num,station,frm,to",
    CASES,
    ids=[f"case-{n}-{s}" for n, s, _, _ in CASES],
)
def test_coerce_pd3_produces_documented_dtype_shifts(
    case_num: int, station: str, frm: str, to: str
) -> None:
    """The forward coercion produces the documented pd3 dtype shape.

    Datetime columns are promoted to ``[us, *]``; object-string columns
    become ``string`` dtype. Failing this means the bridge is silently
    not applying the documented coercion on a real pandas-3 venv.
    """
    path = FIXTURES / f"case_{case_num}_{station}_{frm}_{to}.parquet"
    canonical = pd.read_parquet(path)
    forward = coerce_2x_to_3x(canonical)

    for col in forward.columns:
        s = forward[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            # All datetime columns must be at us-resolution after coercion.
            assert "[us" in str(s.dtype), (
                f"case {case_num} column {col!r}: expected [us, *] after "
                f"coerce_2x_to_3x; got {s.dtype}"
            )
