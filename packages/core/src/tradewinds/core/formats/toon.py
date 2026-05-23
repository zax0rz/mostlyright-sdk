"""TOON format — DataFrame ↔ TOON tabular string.

Wraps the lifted ``_toon`` encoder (``encode_tabular``) with a
DataFrame-aware coercion layer on the dumps side and a focused
tabular-form parser on the loads side. TOON is encoder-only in
mostlyright; this module adds the loader needed for roundtrip.

The wire form is exactly what ``encode_tabular`` produces — a TOON v3.0
tabular block of the form::

    rows[N]{col1,col2,col3}:
      v1,v2,v3
      ...

No metadata header is emitted. Loss cases are deterministic and
documented per design doc §I:

- pandas ``Categorical`` dtype → object (string values; category list dropped).
- ``Timestamp[ns, <tz>]`` cells are serialized as ISO-8601 strings at
  microsecond precision (nanoseconds are truncated). The loader does NOT
  auto-promote ISO-looking string columns back to ``datetime64``; this
  prevents user-supplied label columns whose values happen to match the
  ISO pattern from being silently mutated, and makes the roundtrip
  idempotent under repeat dumps/loads. **Callers who want a timestamp
  column back must call ``pd.to_datetime`` explicitly** (e.g.
  ``df["event_time"] = pd.to_datetime(df["event_time"], utc=True)``).
- Mixed-type ``object`` columns containing ``dict``/``list`` values:
  nested values are stringified deterministically — ``dict`` cells via
  ``json.dumps(value, sort_keys=True, default=str)`` (canonical, order-
  independent), other non-primitives via ``str(value)``.
- ``Int64`` nullable integer columns with nulls roundtrip as ``float64``
  with ``NaN`` for the missing slots (precision loss above 2**53).
- ``decimal.Decimal`` cells are coerced to ``float`` in the encoder to
  match TOON's numeric model (precision loss above 2**53).

For lossless transport prefer parquet.
"""

from __future__ import annotations

import json as _json
import math
import re
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from ._toon import _format_key, encode_tabular

__all__ = ["dumps", "loads"]


# ---------------------------------------------------------------------------
# DataFrame → TOON
# ---------------------------------------------------------------------------


def _coerce_cell(value: Any) -> Any:
    """Coerce a DataFrame cell to a TOON-encodable primitive.

    The TOON encoder accepts ``None | bool | int | float | str``. Anything
    else falls through ``str(value)`` so the column stays uniform (a mixed
    ``None`` / object column would otherwise trip ``_is_tabular``).

    NumPy scalar types (``np.bool_``, ``np.integer``, ``np.floating``) are
    NOT Python ``bool``/``int``/``float`` subclasses under NumPy 2 — they
    are checked explicitly before the Python-type ladder.
    """
    # NA-like values collapse to None.
    if value is None:
        return None
    # pd.NA and pd.NaT
    if value is pd.NA or value is pd.NaT:
        return None
    # NumPy bool first — NumPy 2 broke the bool-is-int identity, so this
    # must precede every numeric check (np.bool_ is also np.generic but
    # str(np.True_) == 'True', which would silently encode as the bare
    # token 'True' instead of the TOON literal `true`).
    if isinstance(value, np.bool_):
        return bool(value)
    # NumPy scalar NaN (np.float64 nan satisfies isinstance(_, float) on
    # most platforms but we keep this branch for the np.floating subset
    # that isn't a Python float — defensive against future NumPy changes).
    if isinstance(value, np.floating) and np.isnan(value):
        return None
    # NumPy/pandas scalar NaN
    if isinstance(value, float) and math.isnan(value):
        return None
    # pandas Timestamp → ISO-8601 string at microsecond precision.
    # str(ts) preserves nanoseconds; we explicitly truncate to µs per
    # design doc §I: "TOON serializes µs, not ns".
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        # Truncate nanoseconds explicitly so the documented loss is
        # deterministic. pd.Timestamp.floor('us') keeps the tz and drops
        # the sub-microsecond remainder without warning.
        truncated = value.floor("us")
        return truncated.isoformat()
    # Python bool (subclass of int in CPython, so check before int).
    if isinstance(value, bool):
        return value
    # Python int / NumPy integers.
    if isinstance(value, int | np.integer):
        return int(value)
    # Python float / NumPy floats — NaN already handled above.
    if isinstance(value, float | np.floating):
        return float(value)
    # Strings — passthrough.
    if isinstance(value, str):
        return value
    # Decimal → float to match TOON's numeric model (loss above 2**53,
    # documented in the module docstring's loss matrix).
    if isinstance(value, Decimal):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    # Dict cells → canonical JSON with sorted keys. ``str(value)`` would
    # be insertion-order-dependent — two logically-equal dicts with
    # different insertion orders would produce different TOON strings,
    # breaking determinism. ``default=str`` keeps the encoder lossy-but-
    # total on values json can't natively serialize.
    if isinstance(value, dict):
        return _json.dumps(value, sort_keys=True, default=str)
    # List / set / tuple / etc. — stringify deterministically.
    # Includes numpy types not caught above and anything exotic.
    return str(value)


def dumps(df: pd.DataFrame) -> str:
    """Serialize a DataFrame as a TOON v3.0 tabular string.

    Iterates the DataFrame column-by-column rather than row-by-row.
    ``df.iterrows()`` materializes each row as a ``Series``, which upcasts
    every cell to the row's common dtype — so an ``int64`` column with a
    value above 2**53 sharing a row with a ``float64`` cell would silently
    lose precision (``int(2**60)`` → ``float(2**60)``). Column-wise
    iteration preserves each column's native dtype before per-cell
    coercion. See module docstring for the full loss matrix.
    """
    if len(df) == 0:
        # encode_tabular wants non-empty rows; emit the canonical empty form
        # carrying column names so loads() can reconstruct an empty frame.
        # Quote each name the same way encode_tabular's non-empty path does
        # — bare ``,`` join would break for names containing commas, braces,
        # quotes, or other quote-trigger characters.
        cols = ",".join(_format_key(str(c)) for c in df.columns)
        return f"rows[0]{{{cols}}}:"

    columns = list(df.columns)
    # Pull each column once with .tolist() — pandas converts each column
    # using its own dtype, so int64 stays int64 and float64 stays float64
    # rather than being unified across the row.
    col_values: list[list[Any]] = [df[col].tolist() for col in columns]
    col_keys: list[str] = [str(col) for col in columns]
    n = len(df)
    records: list[dict[str, Any]] = []
    for i in range(n):
        rec: dict[str, Any] = {}
        for c_idx, key in enumerate(col_keys):
            rec[key] = _coerce_cell(col_values[c_idx][i])
        records.append(rec)
    return encode_tabular(records)


# ---------------------------------------------------------------------------
# TOON → DataFrame
# ---------------------------------------------------------------------------


# Matches the leading ``key[count]{`` portion of the tabular header. We
# parse the columns region by hand below so that a literal ``}`` inside a
# quoted column name does not terminate the header prematurely.
_HEADER_PREFIX_RE = re.compile(
    r"""
    ^
    (?P<key>[A-Za-z_][A-Za-z0-9_.]*)   # array key (always "rows" from dumps)
    \[ (?P<count>\d+) \]
    \{
    """,
    re.VERBOSE,
)


def _parse_header_line(line: str) -> tuple[int, str]:
    """Parse ``rows[N]{<cols>}:`` into ``(N, <cols>)``.

    Walks the line character by character after the opening brace,
    respecting quoted strings so a literal ``}`` inside a quoted column
    name does not terminate the columns region. Raises ``ValueError`` if
    the header is malformed (missing prefix, unbalanced quote, missing
    closing ``}:`` punctuation).
    """
    prefix = _HEADER_PREFIX_RE.match(line)
    if prefix is None:
        raise ValueError(f"TOON payload missing tabular header; got: {line!r}")
    declared_count = int(prefix.group("count"))
    i = prefix.end()
    n = len(line)
    # Scan to the closing brace at depth 0, honoring quoted strings.
    while i < n:
        ch = line[i]
        if ch == '"':
            # Quoted segment — skip to matching close quote.
            j = i + 1
            while j < n:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if line[j] == '"':
                    break
                j += 1
            if j >= n:
                raise ValueError(f"TOON header has unterminated quoted column name: {line!r}")
            i = j + 1
            continue
        if ch == "}":
            break
        i += 1
    if i >= n or line[i] != "}":
        raise ValueError(f"TOON header missing closing brace: {line!r}")
    cols = line[prefix.end() : i]
    # Expect ``:`` immediately after the closing brace (trailing whitespace ok).
    rest = line[i + 1 :].rstrip()
    if rest != ":":
        raise ValueError(f"TOON header missing colon terminator: {line!r}")
    return declared_count, cols


def _split_columns(col_header: str) -> list[str]:
    """Split the comma-separated column-header content.

    Column names may themselves be quoted (per ``_format_key``: non-safe
    names are emitted via ``_quote_string``). Reuses the row tokenizer
    since the syntax is identical.
    """
    return [_unquote_if_quoted(tok) for tok in _split_csv_row(col_header)]


def _unquote_if_quoted(token: str) -> str:
    """Unwrap a TOON-quoted string token if present; else return as-is."""
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return _decode_quoted(token)
    return token


def _decode_quoted(token: str) -> str:
    """Decode a TOON quoted string (already including the outer quotes).

    Inverse of ``_quote_string`` in the lifted encoder: handles ``\\\\``,
    ``\\"``, ``\\n``, ``\\r``, ``\\t``. Any other backslash sequence is
    treated as a literal backslash followed by the next character — the
    encoder never emits those, so this is defensive only.
    """
    inner = token[1:-1]
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            if nxt == "\\":
                out.append("\\")
            elif nxt == '"':
                out.append('"')
            elif nxt == "n":
                out.append("\n")
            elif nxt == "r":
                out.append("\r")
            elif nxt == "t":
                out.append("\t")
            else:
                # Unknown escape — defensive passthrough.
                out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_csv_row(line: str) -> list[str]:
    """Split a TOON tabular row into comma-separated tokens.

    Tokens may be bare or quoted (``"..."``). A comma inside a quoted
    token is part of the value, not a separator. Escapes inside quotes
    follow the lifted encoder's set: ``\\\\``, ``\\"``, ``\\n``, ``\\r``,
    ``\\t``.
    """
    tokens: list[str] = []
    i = 0
    n = len(line)
    if n == 0:
        return tokens
    while True:
        # Skip leading whitespace inside the field (TOON does not emit
        # padding, so this is defensive).
        while i < n and line[i] == " ":
            i += 1
        if i >= n:
            # End-of-line reached. If the previous separator was a comma
            # we are at a trailing empty field; otherwise the previous
            # token already consumed the tail and we are done.
            tokens.append("")
            break
        if line[i] == '"':
            # Quoted token. Scan to the closing quote, honoring escapes.
            j = i + 1
            while j < n:
                if line[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if line[j] == '"':
                    break
                j += 1
            # j now points at closing quote (or n if malformed).
            tokens.append(line[i : j + 1])
            i = j + 1
            # Expect a comma or end-of-line.
            if i >= n:
                break
            if line[i] == ",":
                i += 1
                continue
            # Trailing junk after closing quote — defensive, skip to comma.
            while i < n and line[i] != ",":
                i += 1
            if i >= n:
                break
            i += 1
        else:
            # Bare token — read until next comma.
            j = i
            while j < n and line[j] != ",":
                j += 1
            tokens.append(line[i:j])
            i = j
            if i >= n:
                break
            # line[i] == ',' — consume and continue to the next field.
            i += 1
    return tokens


def _decode_value(token: str) -> Any:
    """Decode a single TOON cell token to a Python value.

    Distinguishes the literal forms ``null`` / ``true`` / ``false`` from
    quoted strings carrying those words. Numeric tokens become ``int``
    when integral and ``float`` otherwise.
    """
    if not token:
        # Empty bare token — TOON encoder never emits these; treat as None.
        return None
    if token[0] == '"' and token[-1] == '"' and len(token) >= 2:
        return _decode_quoted(token)
    if token == "null":
        return None
    if token == "true":
        return True
    if token == "false":
        return False
    # Numeric attempt.
    try:
        # Integer first.
        if "." not in token and "e" not in token and "E" not in token:
            return int(token)
        return float(token)
    except ValueError:
        # Bare unquoted string — TOON allows this when no quote triggers fire.
        return token


def loads(data: str) -> pd.DataFrame:
    """Parse a TOON v3.0 tabular string back into a DataFrame.

    Accepts only the tabular form ``dumps`` produces. Other TOON
    constructs (nested objects, expanded lists) are not supported here —
    the format module's wire shape is strictly the tabular block.
    """
    lines = data.splitlines()
    # Skip leading blanks (defensive against editor reflow).
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        raise ValueError("empty TOON payload")

    declared_count, cols_region = _parse_header_line(lines[idx])
    columns = _split_columns(cols_region)

    raw_rows: list[list[Any]] = []
    for raw_line in lines[idx + 1 :]:
        line = raw_line.rstrip()
        if not line.strip():
            continue
        # Each row is two-space indented by the encoder; strip leading
        # whitespace defensively rather than asserting exact prefix.
        stripped = line.lstrip(" ")
        tokens = _split_csv_row(stripped)
        if len(tokens) != len(columns):
            raise ValueError(
                f"TOON row column count mismatch: expected {len(columns)}, "
                f"got {len(tokens)}: {stripped!r}"
            )
        raw_rows.append([_decode_value(tok) for tok in tokens])

    if declared_count != len(raw_rows):
        raise ValueError(f"TOON declared row count {declared_count} != actual {len(raw_rows)}")

    # Empty-frame fast path: reconstruct columns but with no data.
    if not raw_rows:
        return pd.DataFrame({c: [] for c in columns})

    # Build column-wise. We deliberately do NOT auto-promote ISO-string
    # columns to ``datetime64`` here — that heuristic would silently mutate
    # user-supplied label columns whose values happen to match the ISO
    # pattern (e.g. ``["2020-01-01", "2020-01-02"]``) and break idempotence
    # under repeat dumps/loads. ISO strings stay as ``object`` strings;
    # callers reconstruct timestamps with ``pd.to_datetime`` if desired.
    data_cols: dict[str, Any] = {}
    for col_idx, col_name in enumerate(columns):
        data_cols[col_name] = [row[col_idx] for row in raw_rows]
    return pd.DataFrame(data_cols)
