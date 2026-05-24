"""CSV format — pandas-native serialization.

``dumps`` emits standard CSV without the index column. ``loads`` parses
via ``pd.read_csv`` with pandas' default dtype inference. Useful for
spreadsheet interchange and shell-level inspection, but **lossy**:

- All dtype information is lost on the wire; pandas re-infers on read.
  ``Int64`` becomes ``int64`` or ``float64`` (depending on whether the
  column has nulls); ``Categorical`` becomes ``object`` (strings);
  ``boolean`` becomes ``object`` if it contained nulls.
- ``NaN`` and ``None`` and empty cells are all written as the empty
  string and all read back as ``NaN``. The distinction between
  "missing numeric" and "missing string" is not preserved.
- Timezone-aware timestamps serialize as their ISO-8601 representation
  with offset, and ``pd.read_csv`` parses them back as object strings
  unless the caller explicitly asks for ``parse_dates``.
- Floating-point round-trip is subject to CSV's lossy decimal
  representation — pandas uses repr() formatting by default which is
  generally exact for IEEE-754, but precision-critical callers should
  prefer parquet.

For lossless transport prefer parquet. For LLM-friendly tabular
transport prefer TOON.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd

__all__ = ["dumps", "loads"]


def dumps(df: pd.DataFrame) -> str:
    """Serialize a DataFrame to a CSV string.

    Drops the index (``index=False``) to match the wire shape the
    catalog adapters emit. Column order is preserved.

    Phase 6 W2-T6: accepts pandas OR polars input; polars frames are
    converted to pandas at the boundary so the wire bytes stay
    identical regardless of caller backend.
    """
    from tradewinds.core._narwhals_compat import to_pandas_if_polars

    df, _ = to_pandas_if_polars(df)
    return df.to_csv(index=False)


def loads(data: str) -> pd.DataFrame:
    """Parse a CSV string back into a DataFrame.

    Uses pandas' default dtype inference — see module docstring for the
    loss cases callers must be aware of.
    """
    return pd.read_csv(StringIO(data))
