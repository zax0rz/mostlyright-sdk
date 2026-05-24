"""Pandas-2.x → pandas-3.x parity-fixture coercion bridge (Phase 6 W1-T5).

The v0.1.0 parity contract is byte-equivalent to ``mostlyright==0.14.1`` —
a single, immutable set of bytes per CLAUDE.md "Data + parity rules".
Capturing a *second* set of fixtures from tradewinds' own pandas-3 output
would be circular: it would prove tradewinds-2.x == tradewinds-3.x, NOT
that pandas-3-tradewinds matches mostlyright-0.14.1.

This module defines a documented, invertible transform from the 2.x
parquet bytes to the pandas-3 representation. The dual-pandas CI matrix
reads the canonical 2.x fixtures, applies ``coerce_2x_to_3x``, and
compares against the live ``research()`` output running under pandas 3.x.

Two coercions are accepted as pandas-3-equivalent:

1. **Datetime resolution** ``ns → us`` — pandas 3.0 shifts default
   resolution inference for naive string parsing from nanoseconds to
   microseconds. Lossless at second-resolution timestamps (the only
   resolution the v0.1.0 contract cares about).
2. **String dtype** ``object → string`` (PyArrow-backed) — pandas 3.0
   shifts default string storage. Metadata only; element-wise values
   are identical.

Both transforms are invertible: ``coerce_3x_to_2x(coerce_2x_to_3x(case))
== case`` byte-for-byte. The round-trip test in ``test_parity.py``
covers this.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__ = ["coerce_2x_to_3x", "coerce_3x_to_2x"]


def _is_object_str_column(s: pd.Series) -> bool:
    if s.dtype != "object":
        return False
    non_null = s.dropna()
    if non_null.empty:
        return False
    sample = non_null.head(5)
    return all(isinstance(v, str) for v in sample)


def coerce_2x_to_3x(parquet_or_df: Path | pd.DataFrame) -> pd.DataFrame:
    """Coerce a pandas-2.x parity fixture to its pandas-3.x equivalent.

    Applies:
    - ``datetime64[ns, *]`` → ``datetime64[us, *]`` on any timezone.
    - ``object`` string columns → ``string`` (PyArrow-backed if pyarrow
      is installed; the storage backend does not affect the value layer).

    Args:
        parquet_or_df: Path to a ``.parquet`` file produced by
            ``capture_fixtures.py`` (pandas 2.x output) OR a DataFrame
            already loaded.

    Returns:
        A new DataFrame with the coerced dtypes. Element-wise values
        are byte-identical to the input modulo the documented
        resolution + storage shifts.
    """
    if isinstance(parquet_or_df, Path):
        df = pd.read_parquet(parquet_or_df)
    else:
        df = parquet_or_df.copy()

    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            # Walk the dtype string from "datetime64[ns, UTC]" to
            # "datetime64[us, UTC]" — this is the only documented shift.
            dtype_str = str(s.dtype)
            if "[ns" in dtype_str:
                new_dtype = dtype_str.replace("[ns", "[us", 1)
                df[col] = s.astype(new_dtype)
        elif _is_object_str_column(s):
            df[col] = s.astype("string")

    return df


def coerce_3x_to_2x(df: pd.DataFrame) -> pd.DataFrame:
    """Inverse of :func:`coerce_2x_to_3x`.

    Coerces ``us`` resolution back to ``ns`` and PyArrow-backed strings
    back to ``object``. Byte-for-byte invertible at second-resolution
    timestamps (the only resolution v0.1.0 cares about).
    """
    out = df.copy()
    for col in out.columns:
        s = out[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            dtype_str = str(s.dtype)
            if "[us" in dtype_str:
                new_dtype = dtype_str.replace("[us", "[ns", 1)
                out[col] = s.astype(new_dtype)
        elif isinstance(s.dtype, pd.StringDtype) or str(s.dtype) == "string":
            # object→string→object: pandas' string dtype represents missing
            # as pd.NA; on the way back we restore Python None so the round-
            # trip is observationally identical to the canonical object-storage
            # column (where missing values are Python None / np.nan).
            converted = s.astype("object")
            out[col] = converted.where(~s.isna(), None)
    return out
