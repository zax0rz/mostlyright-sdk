"""TOON v3.0 encoder — Token-Oriented Object Notation.

Encodes JSON-compatible Python values to TOON format for LLM/AI agent
consumers. Reduces token count ~60-70% vs JSON for tabular weather data.

Encoder-only. No decoder. Pure Python, no external dependencies.
Deterministic: same input always produces identical output.

Spec: https://github.com/toon-format/spec (v3.0 Working Draft)

Lifted verbatim from mostlyright v0.15.0 → mostlyright-mcp wave-1-core →
tradewinds._v02 per design doc §F.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

__all__ = ["encode", "encode_tabular"]

# Key quoting: unquoted if matches this pattern.
_SAFE_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

# String quoting triggers: colon, quote, backslash, brackets, braces, control chars.
_NEEDS_QUOTE_CHARS_RE = re.compile(r'[:\\"\'\[\]\{\}\x00-\x1f\x7f\x85\u2028\u2029]')

# Numeric-like pattern (could be parsed as a number).
_NUMERIC_LIKE_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")

_INDENT = "  "  # 2 spaces per spec


# ---------------------------------------------------------------------------
# Number canonicalization
# ---------------------------------------------------------------------------


def _format_number(n: int | float) -> str:
    """Format number per TOON canonical rules.

    - NaN/Infinity → "null"
    - -0 → "0"
    - Integer form when fractional part is zero (1.0 → "1")
    - No trailing fractional zeros (1.50 → "1.5")
    - No exponent notation (1e6 → "1000000")
    """
    if isinstance(n, float):
        if math.isnan(n) or math.isinf(n):
            return "null"
        if n == 0.0:
            return "0"
        if n == int(n) and abs(n) <= 2**53:
            return str(int(n))
        s = repr(n)
        if "e" in s or "E" in s:
            # Expand scientific notation via Decimal for full precision.
            # Extreme values (1e308, 5e-324) produce 300+ chars — intentional.
            # Correctness over brevity: settlement data must round-trip exactly.
            d = Decimal(s)
            s = format(d, "f")
            # Strip trailing zeros after decimal point.
            if "." in s:
                s = s.rstrip("0").rstrip(".")
        return s
    # int
    return str(n)


# ---------------------------------------------------------------------------
# String quoting and escaping
# ---------------------------------------------------------------------------


def _needs_quoting(s: str, delimiter: str) -> bool:
    """Check if string value needs quoting per TOON v3.0 rules."""
    if not s:
        return True
    if s[0] in (" ", "\t") or s[-1] in (" ", "\t"):
        return True
    if s in ("true", "false", "null"):
        return True
    if s[0] in ("-", "+"):
        return True
    if s[0].isdigit():
        return True
    if _NUMERIC_LIKE_RE.match(s):
        return True
    if delimiter in s:
        return True
    if _NEEDS_QUOTE_CHARS_RE.search(s):  # noqa: SIM103 — lifted verbatim
        return True
    return False


# Control chars that have no TOON escape sequence — stripped on output.
_UNSUPPORTED_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x85\u2028\u2029]")


def _quote_string(s: str) -> str:
    """Quote and escape a string. Only 5 escape sequences per spec.

    Control characters without a defined escape (everything except
    \\n, \\r, \\t) are stripped to stay within the TOON character model.
    """
    # Strip unsupported control chars first.
    s = _UNSUPPORTED_CTRL_RE.sub("", s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return f'"{s}"'


# ---------------------------------------------------------------------------
# Key formatting
# ---------------------------------------------------------------------------


def _format_key(key: str) -> str:
    """Format object key — unquoted if safe, quoted otherwise."""
    if not isinstance(key, str):
        raise TypeError(f"TOON keys must be strings, got {type(key).__name__}: {key!r}")
    if _SAFE_KEY_RE.match(key):
        return key
    return _quote_string(key)


# ---------------------------------------------------------------------------
# Scalar encoding
# ---------------------------------------------------------------------------


def _encode_scalar(value: Any, delimiter: str) -> str:
    """Encode a scalar value (primitive) to TOON string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return _format_number(value)
    if isinstance(value, str):
        if _needs_quoting(value, delimiter):
            return _quote_string(value)
        return value
    # Fallback: convert to string and quote.
    return _quote_string(str(value))


# ---------------------------------------------------------------------------
# Tabular detection
# ---------------------------------------------------------------------------


def _is_tabular(items: list[Any]) -> bool:
    """Check if list qualifies for tabular encoding.

    Tabular when: all elements are dicts/Mappings, all have identical keys
    (same set and order), all values are primitives.
    """
    if not items:
        return False
    if not all(isinstance(item, Mapping) for item in items):
        return False
    key_set = set(items[0].keys())
    if not key_set:
        return False
    for item in items[1:]:
        if set(item.keys()) != key_set:
            return False
    for item in items:
        for v in item.values():
            if v is not None and not isinstance(v, str | int | float | bool):
                return False
    return True


# ---------------------------------------------------------------------------
# Object encoding
# ---------------------------------------------------------------------------


def _encode_object(obj: Mapping[str, Any], indent: int) -> str:
    """Encode a dict/Mapping as TOON object at given indent level."""
    prefix = _INDENT * indent
    lines: list[str] = []
    for key, value in obj.items():
        fkey = _format_key(key)
        if isinstance(value, Mapping):
            lines.append(f"{prefix}{fkey}:")
            lines.append(_encode_object(value, indent + 1))
        elif isinstance(value, list):
            lines.append(_encode_array_field(value, fkey, indent))
        else:
            lines.append(f"{prefix}{fkey}: {_encode_scalar(value, ',')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Array encoding
# ---------------------------------------------------------------------------


def _encode_tabular_rows(items: list[Any], key: str, indent: int) -> str:
    """Encode tabular array: key[N]{col1,col2,...}: with CSV-like rows.

    Critical: column order comes from first row's keys. Every subsequent
    row is indexed by those column names — never row.values().
    """
    columns = list(items[0].keys())
    prefix = _INDENT * indent
    row_prefix = _INDENT * (indent + 1)

    # Header with field names.
    col_header = ",".join(_format_key(c) for c in columns)
    header = f"{prefix}{key}[{len(items)}]{{{col_header}}}:"

    # Data rows — iterate columns[i] for every row.
    rows: list[str] = []
    for item in items:
        vals = [_encode_scalar(item[col], ",") for col in columns]
        rows.append(f"{row_prefix}{','.join(vals)}")

    return header + "\n" + "\n".join(rows)


def _encode_primitive_array(items: list[Any], key: str, indent: int) -> str:
    """Encode inline primitive array: key[N]: v1,v2,v3."""
    prefix = _INDENT * indent
    if not items:
        return f"{prefix}{key}[0]:"
    vals = [_encode_scalar(v, ",") for v in items]
    return f"{prefix}{key}[{len(items)}]: {','.join(vals)}"


def _encode_expanded_list(items: list[Any], key: str, indent: int) -> str:
    """Encode expanded list form for mixed/non-uniform arrays."""
    prefix = _INDENT * indent
    item_prefix = _INDENT * (indent + 1)
    header = f"{prefix}{key}[{len(items)}]:"
    lines: list[str] = [header]
    for item in items:
        if isinstance(item, Mapping):
            if not item:
                # Empty mapping: bare hyphen list item.
                lines.append(f"{item_prefix}-")
                continue
            keys = list(item.keys())
            first_key = keys[0]
            fk = _format_key(first_key)
            fv = item[first_key]
            if isinstance(fv, Mapping):
                lines.append(f"{item_prefix}- {fk}:")
                lines.append(_encode_object(fv, indent + 3))
            elif isinstance(fv, list):
                # Encode at indent 0 to get raw content, then prepend "- ".
                # For multi-line output (tabular sublists), re-indent
                # continuation lines to align under the first field.
                raw = _encode_array_field(fv, fk, 0)
                raw_lines = raw.split("\n")
                lines.append(f"{item_prefix}- {raw_lines[0]}")
                cont_prefix = _INDENT * (indent + 2)
                for rl in raw_lines[1:]:
                    lines.append(f"{cont_prefix}{rl.lstrip()}")
            else:
                lines.append(f"{item_prefix}- {fk}: {_encode_scalar(fv, ',')}")
            # Remaining keys at indent+2 — always emitted regardless of
            # first key's type.
            for rk in keys[1:]:
                rv = item[rk]
                frk = _format_key(rk)
                if isinstance(rv, Mapping):
                    lines.append(f"{_INDENT * (indent + 2)}{frk}:")
                    lines.append(_encode_object(rv, indent + 3))
                elif isinstance(rv, list):
                    lines.append(_encode_array_field(rv, frk, indent + 2))
                else:
                    lines.append(f"{_INDENT * (indent + 2)}{frk}: {_encode_scalar(rv, ',')}")
        else:
            lines.append(f"{item_prefix}- {_encode_scalar(item, ',')}")
    return "\n".join(lines)


def _encode_array_field(items: list[Any], key: str, indent: int) -> str:
    """Encode an array that is a field value in an object."""
    if not items:
        return f"{_INDENT * indent}{key}[0]:"
    # Check if all items are primitives (not dicts/lists).
    all_primitive = all(not isinstance(v, Mapping | list) for v in items)
    if all_primitive:
        return _encode_primitive_array(items, key, indent)
    if _is_tabular(items):
        return _encode_tabular_rows(items, key, indent)
    return _encode_expanded_list(items, key, indent)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def encode(value: Any) -> str:
    """Encode any JSON-compatible Python value to TOON v3.0 string.

    - dict/Mapping → TOON object
    - list of uniform dicts → tabular TOON with default name "rows"
    - list of primitives → inline array (root)
    - scalar → scalar string
    """
    if isinstance(value, Mapping):
        return _encode_object(value, 0)
    if isinstance(value, list):
        if not value:
            return "rows[0]:"
        if _is_tabular(value):
            return _encode_tabular_rows(value, "rows", 0)
        # All-primitive root list.
        all_primitive = all(not isinstance(v, Mapping | list) for v in value)
        if all_primitive:
            return _encode_primitive_array(value, "rows", 0)
        return _encode_expanded_list(value, "rows", 0)
    return _encode_scalar(value, ",")


def encode_tabular(rows: Sequence[Mapping[str, Any]], name: str = "rows") -> str:
    """Encode a sequence of flat dicts as tabular TOON.

    Accepts plain dicts (from parsers), Observation.to_storage_dict(),
    or any Mapping[str, Any]. This matches the dominant representation
    in the pipeline — producers emit dict[str, Any], not model instances.
    """
    items = list(rows)
    if not items:
        return f"{name}[0]:"
    if not _is_tabular(items):
        raise ValueError(
            f"encode_tabular requires uniform rows with identical keys and "
            f"primitive values; got {len(items)} rows that are not valid tabular data"
        )
    return _encode_tabular_rows(items, name, 0)
