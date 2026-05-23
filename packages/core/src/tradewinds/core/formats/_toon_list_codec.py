"""TOON list-cell codec — primitive-only serialization for list cells.

The TOON encoder (``mostlyright._toon.encode_tabular``) requires uniform
rows with identical keys and PRIMITIVE-typed cells (no nested lists or
mappings — see ``_is_tabular`` at ``_toon.py:172``). Wire-format dicts
that the SDK and FastAPI route layer hand to ``encode_tabular`` may
carry list-typed fields like ``qc_flags: list[str]`` (Sprint 2o-s4
QC engine alpha) or future ``parsers: list[str]`` (Sprint 2o-s5
dual-parser ledger view).

This module is the registered extension point for "transform a list-
typed cell to a TOON-compatible primitive before the encoder sees it."
A single helper — ``flatten_lists_for_toon`` — looks up the field in
``TOON_LIST_CODECS`` and applies the registered codec; rows whose
fields aren't in the table pass through unchanged.

**Why a registry, not per-field helpers** (Vu R3 / round-3-fix-2
architect HIGH-1):
- Sprint 2o-s4 introduces ``qc_flags`` (this PR).
- Sprint 2o-s5 will introduce ``parsers`` on the ledger view.
- Sprint 2o-s7 spec mentions ``qc_field`` arrays on the materialize
  path.
- Sprints 2p / 2q add forecast-array fields (``valid_times``,
  ``ensemble_members``).

Adding a per-field helper for each (`_flatten_qc_flags_for_toon`,
`_flatten_parsers_for_toon`, …) duplicates the "list → joined
string" transformation N times with potentially-different
separators. A codec table makes the contract structural: future
sprints add an entry to the dict instead of a new helper at a new
call site.

**Why ``client.py`` is the wrong layer** (architect HIGH-1):
``client.py`` is the migration-compat facade (``MostlyRightClient``
maps therminal-py method signatures); it should not own
TOON-format-specific cell coercion logic. This module sits next to
the encoder it serves.

**Separator choice**:
- ``qc_flags``: ``"|"``. Flag names are snake_case identifiers
  (``[a-z][a-z0-9_]*``) emitted by ``MOSTLYRIGHT_V1_ENGINE.run`` and
  cannot contain pipes — the join is unambiguous and lossless. Pipe
  is also outside ``_toon.py``'s ``_NEEDS_QUOTE_CHARS_RE`` so the
  cell encodes bare on the wire.
- Future fields add their own separators with the same constraint:
  the codec must encode bijectively (decoder can recover the original
  list) AND the separator must not appear in any element value.

**Codec signature** (round-3-fix-2 round-2 architect MED-2):
``Callable[[list[Any], Mapping[str, Any]], Any]`` — codecs receive
the full row as the second argument so future codecs that need
sibling-row context (e.g. 2o-s5 ``parsers`` ordered by
``parser_priority`` from a sibling cell, 2p ``valid_times``
validated against ``forecast_known_at``) can implement those
constraints without a future-breaking signature change. The current
``_encode_qc_flags`` ignores the row argument; the unused parameter
is the sanctioned extension hook.

**Idempotency** (round-3-fix-2 round-2 architect LOW-1):
- For VALID inputs the helper is idempotent:
  ``flatten_lists_for_toon(flatten_lists_for_toon(row)) ==
  flatten_lists_for_toon(row)``.
- For TAMPERED inputs (e.g. ``qc_flags`` is a tuple, an int, or a
  custom object), the helper passes the cell through unchanged and
  the encoder error surfaces from ``encode_tabular`` with full row
  context. Idempotency is preserved at the function level (two
  applications agree) but the encoded output is NOT TOON-valid.
- ``None`` and empty list both flatten to ``""`` so the TOON column
  type is uniform across rows. A mixed ``str`` / ``None`` column
  would still trip ``_is_tabular``'s primitive-only check.

Lifted verbatim from mostlyright v0.15.0 → mostlyright-mcp wave-1-core →
tradewinds.core per design doc §F.
"""

from __future__ import annotations

import types
from collections.abc import Callable, Mapping
from typing import Any, Final, TypeAlias

__all__ = [
    "QC_FLAGS_TOON_SEPARATOR",
    "TOON_LIST_CODECS",
    "flatten_lists_for_toon",
]


QC_FLAGS_TOON_SEPARATOR: Final[str] = "|"


def _encode_qc_flags(flags: list[Any], _row: Mapping[str, Any]) -> str:
    """Join a ``qc_flags`` list with the canonical pipe separator.

    Empty lists collapse to ``""`` (the helper itself receives only
    list inputs; ``None`` is intercepted upstream by the falsy-check
    in ``flatten_lists_for_toon``). Each flag is coerced via
    ``str(...)`` so a future ``QCFlag`` enum / dataclass that
    auto-stringifies still serializes safely.

    The ``_row`` parameter is ignored today; future codecs that need
    sibling-row context (e.g. ordering by a priority cell) consume it.
    The unused-arg pattern is the sanctioned extension hook —
    architect MED-2 sized the signature for forward compatibility.
    """
    if not flags:
        return ""
    return QC_FLAGS_TOON_SEPARATOR.join(str(f) for f in flags)


_TOONListCodec: TypeAlias = Callable[[list[Any], Mapping[str, Any]], Any]
"""Type alias for a codec callable.

Round-3-fix-2 round-3 python LOW + round-4 python MED: explicit
``TypeAlias`` annotation (NOT a bare assignment) so future codec
authors have a named type to target instead of repeating the raw
``Callable[...]`` form. Pre-fix the bare assignment was inferred
as a type alias by pyright but pre-emptively flagged by mypy strict
as an untyped class assignment. The return type is intentionally
``Any`` so codecs can emit any TOON-compatible primitive (str /
int / float / bool / None) — narrowing further would invalidate
future numeric-aggregation codecs (e.g. ``ensemble_member_count:
int`` for 2q).
"""


# Registered codec table. Keys are field names; values are functions
# that take a ``(list[Any], Mapping[str, Any])`` pair (cell value +
# full row, for sibling-context-aware codecs) and return a TOON-
# compatible primitive (``str`` today; future codecs may emit ``int``
# / ``float`` if a numeric aggregation makes sense for that field).
#
# Adding a new entry is the canonical extension path for a new
# list-typed field. The codec function MUST:
# - Accept ``(non_empty_list, row_mapping)`` (empty lists are
#   intercepted upstream by ``flatten_lists_for_toon``).
# - Return a TOON-compatible primitive (``str``, ``int``, ``float``,
#   ``bool``, or ``None``).
# - Be deterministic (same input → identical output).
# - Be lossless (downstream consumers can recover the original list
#   given knowledge of the codec).
# - Be PURE — same ``(cell_value, row_subset_consumed)`` produces
#   same output. A codec that mutates state across rows breaks the
#   per-row encoding invariant and produces nondeterministic TOON
#   output (round-3-fix-2 round-2 architect LOW-2).
#
# Round-3-fix-2 round-3 security MED: the registry is wrapped in
# ``types.MappingProxyType`` so any external mutation attempt
# (``TOON_LIST_CODECS["evil"] = ...``) raises ``TypeError`` at
# runtime. Pre-fix the ``Final[Mapping]`` annotation only prevented
# rebinding the name; the underlying ``dict`` was still mutable.
# Sprint authors adding a new codec extend the literal dict below
# (the source-side construction), NOT the read-only proxy at runtime.
TOON_LIST_CODECS: Final[Mapping[str, _TOONListCodec]] = types.MappingProxyType(
    {
        "qc_flags": _encode_qc_flags,
    }
)


def flatten_lists_for_toon(row: Mapping[str, Any]) -> dict[str, Any]:
    """Apply registered codecs to list-typed cells in ``row``.

    Returns a NEW dict (immutability rule); the input is unchanged.
    Rows whose fields aren't in ``TOON_LIST_CODECS`` are returned with
    a shallow copy (still a new dict, for caller-safety).

    Per-field semantics:
    - Field present + value is a non-empty ``list``: codec applied
      with ``(value, row)``.
    - Field present + value is ``None`` or empty list: cell becomes
      ``""`` so the TOON column type is uniform (a ``None``
      alongside a string would still trip ``_is_tabular``).
    - Field present + value is already a primitive (e.g.
      pre-flattened upstream): pass through unchanged.
    - Field absent: pass through unchanged.

    Idempotent for VALID inputs; tampered inputs (non-list non-None
    cells under a registered field) pass through unchanged and
    surface as encoder errors with full row context. See module
    docstring for the full idempotency contract.
    """
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k not in TOON_LIST_CODECS:
            out[k] = v
            continue
        # Round-3-fix-2 round-4 codex MED-1 + python MED-1: ORDER
        # MATTERS. The empty-collapse check below is restricted to
        # ``None`` and empty-list explicitly so falsy primitives
        # (``0``, ``False``, ``0.0``, ``""``) pass through to the
        # ``isinstance(v, list)`` guard unchanged. Pre-fix the
        # broader ``not v`` check rewrote those primitives to
        # ``""``, silently corrupting any future codec field that
        # legitimately holds them (e.g. 2q ``ensemble_member_count:
        # int = 0``). The fix preserves idempotency for current
        # callers (``None`` and ``[]`` still flatten to ``""``)
        # and closes the latent forward-compat gap before s5.
        if v is None or v == []:
            out[k] = ""
            continue
        if not isinstance(v, list):
            # Already a primitive (e.g. pre-flattened string, a
            # numeric ``0``, or a ``False`` bool). Pass through
            # unchanged. Do not raise — TOON encoding errors should
            # surface from ``encode_tabular`` with full row
            # context, and a non-list non-None value is the
            # "already flattened upstream" case which is a valid
            # call shape.
            out[k] = v
            continue
        out[k] = TOON_LIST_CODECS[k](v, row)
    return out
