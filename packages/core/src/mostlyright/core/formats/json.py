"""JSON format — records-oriented serialization via pandas.

``dumps`` emits ``orient='records'`` with ISO-8601 timestamps; ``loads``
parses that shape back. Convenient for wire transport and human
inspection, but **lossy**:

- ``Int64`` (nullable integer) → ``float64`` on roundtrip (pandas
  ``read_json`` does not infer ``Int64``).
- ``Categorical`` dtype → ``object`` (string values, no category list).
- Timezone-aware timestamps may roundtrip as UTC-naive depending on
  pandas version; callers that need tz fidelity should use parquet or
  TOON.
- ``NaN`` and ``None`` are both serialized as JSON ``null`` and read
  back as ``NaN`` (for numeric columns) or ``None`` (for object
  columns). The distinction is not preserved.

**Empty-frame envelope:** an empty DataFrame is emitted as a JSON
envelope of the form ``{"columns": [...], "data": []}`` so column names
survive the roundtrip. ``orient='records'`` alone would degrade to the
literal ``"[]"`` and lose every column. Non-empty frames still use the
records form. The loader detects which form it received and dispatches
accordingly.

For lossless transport prefer parquet. For LLM-friendly tabular
transport prefer TOON.
"""

from __future__ import annotations

import json as _json
from io import StringIO

import pandas as pd

__all__ = ["dumps", "loads"]


def dumps(df: pd.DataFrame) -> str:
    """Serialize a DataFrame to JSON records.

    Non-empty frames are encoded with ``orient='records'`` and
    ``date_format='iso'`` so timestamps survive as ISO-8601 strings.
    Empty frames are encoded as a ``{"columns": [...], "data": []}``
    envelope so column names roundtrip — ``orient='records'`` on a
    zero-row frame would otherwise collapse to ``"[]"``.

    Phase 6 W2-T6: accepts pandas OR polars input; polars frames are
    converted to pandas before serialization (output bytes are identical
    for the same row content).
    """
    from tradewinds.core._narwhals_compat import to_pandas_if_polars

    df, _ = to_pandas_if_polars(df)
    if len(df) == 0:
        # Envelope form: columns survive the roundtrip even with zero rows.
        return _json.dumps({"columns": list(map(str, df.columns)), "data": []})
    return df.to_json(orient="records", date_format="iso")


def loads(data: str) -> pd.DataFrame:
    """Parse a JSON string back into a DataFrame.

    Accepts both the records form (list of row dicts) and the empty-frame
    envelope (``{"columns": [...], "data": []}``). Dtype inference for
    the records form is whatever pandas decides from the JSON values —
    the caller is responsible for casting if a specific dtype is
    required. See module docstring for the documented loss cases.
    """
    stripped = data.lstrip()
    # Envelope-form short-circuit. A non-list payload is the envelope
    # shape; parse it directly with ``json.loads`` rather than handing it
    # to ``pd.read_json`` (which would reject it).
    if stripped.startswith("{"):
        payload = _json.loads(data)
        if isinstance(payload, dict) and "columns" in payload and "data" in payload:
            cols = list(payload["columns"])
            rows = payload["data"]
            if not rows:
                return pd.DataFrame({c: [] for c in cols})
            # Defensive: if a caller hand-built the envelope with rows,
            # treat them as records keyed by ``cols``.
            return pd.DataFrame(rows, columns=cols)
    return pd.read_json(StringIO(data), orient="records")
