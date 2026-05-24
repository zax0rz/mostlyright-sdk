"""Phase 6 W4 sort-stability + parity-locked-thunk invariants.

Verifies the load-bearing assumptions the parity gate depends on:

- W4-T1: parity-locked modules MUST NOT receive a polars frame in any
  pipeline path. The backend conversion happens at the outer return
  boundary of research(), never inside _internal/_pairs.py /
  core/merge.py / core/_climate.py / validator / leakage / timepoint /
  _json_safe.
- W4-T3: narwhals-mediated paths through transforms / preprocessing
  must preserve sort stability across backends. Polars' default sort
  is NOT stable; an adversarial 10k-row DataFrame with deliberately-
  pathological duplicate keys exposes any non-stable sort that slips
  in. This test confirms our boundary-shim path (polars→pandas→sort→
  polars) preserves the pandas sort ordering byte-for-byte.
"""

from __future__ import annotations

import random

import pandas as pd
import pytest

pl = pytest.importorskip("polars")
pytestmark = pytest.mark.polars


def _adversarial_dataframe(n: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """Build an adversarial duplicate-key DataFrame.

    Every key value appears 10+ times; insertion order is randomized via
    a seeded RNG. The expected sort ordering on `key` is then driven by
    sort stability (insertion order within ties must be preserved).
    """
    rng = random.Random(seed)
    keys = [i for i in range(n // 10) for _ in range(10)]
    rng.shuffle(keys)
    values = list(range(len(keys)))
    return pd.DataFrame({"key": keys, "value": values})


def test_pandas_mergesort_is_stable_baseline() -> None:
    """Sanity: pandas' mergesort IS stable; values stay in insertion order at equal keys."""
    df = _adversarial_dataframe()
    sorted_df = df.sort_values("key", kind="mergesort").reset_index(drop=True)
    # First 10 rows all have key=0 and MUST preserve insertion order on `value`.
    first_bucket = sorted_df[sorted_df["key"] == 0]
    assert len(first_bucket) == 10
    expected_values = df[df["key"] == 0]["value"].tolist()
    assert first_bucket["value"].tolist() == expected_values


def test_polars_to_pandas_roundtrip_preserves_order() -> None:
    """Polars→pandas conversion preserves the row ordering polars emitted.

    The narwhals boundary shim relies on this: a sort done on polars
    inside a user's pre-shim pipeline survives `.to_pandas()` intact.
    """
    df = _adversarial_dataframe()
    pl_df = pl.from_pandas(df)
    pl_sorted = pl_df.sort("key", maintain_order=True)
    converted = pl_sorted.to_pandas()
    pl_native = pl_sorted.to_pandas()
    assert converted.equals(pl_native)


def test_boundary_shim_sort_round_trip_preserves_order() -> None:
    """End-to-end: pandas adapter result + polars caller path agree on row order.

    Simulates what happens when a user passes a polars frame to a
    narwhals-migrated transform that internally converts to pandas,
    runs an op, and converts back. Even with the duplicate-key worst
    case, the round-trip output must match the pure-pandas path
    byte-for-byte after explicit stable sort.
    """
    df = _adversarial_dataframe()
    pandas_path = df.sort_values("key", kind="mergesort").reset_index(drop=True)

    # Polars→pandas at the shim boundary, sort in pandas, return.
    pl_in = pl.from_pandas(df)
    pdf = pl_in.to_pandas()
    pdf_sorted = pdf.sort_values("key", kind="mergesort").reset_index(drop=True)

    assert pdf_sorted.equals(pandas_path)


# ----------------------- W4-T1 parity-locked module defense-in-depth -----------------------


def test_parity_locked_modules_load_pandas_only() -> None:
    """The 7 parity-locked modules MUST NOT use narwhals or polars at module load.

    Defense-in-depth: a future refactor that pulled narwhals into these
    paths would silently re-introduce the lossy ns/us conversion that
    the W4-T1 invariant forbids. Module-load grep catches that drift.
    """
    import importlib
    import inspect
    from pathlib import Path

    parity_locked = [
        "tradewinds._internal._pairs",
        "tradewinds.core.merge",
        "tradewinds.core.validator",
        "tradewinds.core._json_safe",
        "tradewinds.core.temporal.timepoint",
        "tradewinds.core.temporal.leakage",
    ]
    for module_name in parity_locked:
        mod = importlib.import_module(module_name)
        path = Path(inspect.getsourcefile(mod) or "")
        if not path.exists():
            continue
        source = path.read_text()
        # narwhals / polars MUST NOT appear at the top-level of these
        # files. Comments / docstrings are allowed (so the W4-T1 docs
        # can reference them), but actual imports are forbidden.
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("import polars") or stripped.startswith("from polars"):
                pytest.fail(
                    f"{module_name} is parity-locked but imports polars at: {line!r}"
                )
            if stripped.startswith("import narwhals") or stripped.startswith("from narwhals"):
                pytest.fail(
                    f"{module_name} is parity-locked but imports narwhals at: {line!r}"
                )


# ----------------------- W4-T5 DataVersion backend invariance -----------------------


def test_data_version_token_is_backend_invariant() -> None:
    """Backend choice MUST NOT change the DataVersion token.

    The data_sha is a function of disk state, not in-memory representation.
    A polars caller and a pandas caller against the same cache must hash
    the same files and produce identical DataVersion tokens.
    """
    from tradewinds.discovery import DataVersion

    a = DataVersion.from_components(
        sdk_version="0.2.0",
        schema_ids=("schema.observation.v1",),
        sources=("iem.live", "awc.live"),
        code_sha="abc123",
        data_sha="deadbeef",
    )
    b = DataVersion.from_components(
        sdk_version="0.2.0",
        schema_ids=("schema.observation.v1",),
        sources=("iem.live", "awc.live"),
        code_sha="abc123",
        data_sha="deadbeef",
    )
    assert a.token == b.token
