"""JSON-safe coercion for SDK exception payloads.

The SDK raises structured exceptions whose ``violations`` / ``sample_violations``
attributes often contain pandas types (``Timestamp``, ``NaT``, numpy floats with
``NaN``, ``Int64`` with ``<NA>``). Those values are not JSON-serializable by
default, but MCP carries them across a JSON-RPC boundary via ``error.data``.

This module exposes a single public function, :func:`to_json_safe`, that
recursively coerces an arbitrary object into a structure that ``json.dumps``
can encode without further customization. See ``docs/design.md`` §S for the
authoritative contract.

Naive-timestamp policy
----------------------
The encoder is the serializer for error payloads, including the very payloads
that *report* naive-timestamp violations (e.g. ``SchemaValidationError``
naming the offending row). Raising on naive timestamps inside the serializer
would prevent the SDK from telling the caller what went wrong. So a naive
``pd.Timestamp`` / ``datetime.datetime`` reaching the encoder is wrapped in a
``{"_repr_only": True, "value": "<naive iso>"}`` marker — preserving the
value, surfacing the naive-ness, and keeping the payload serializable. The
tz-awareness invariant is enforced at the schema boundary, not here.
"""

from __future__ import annotations

import datetime as _dt
import math
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["to_json_safe"]


def _coerce_timestamp(ts: pd.Timestamp | _dt.datetime) -> Any:
    """Convert a Timestamp / datetime to an ISO 8601 string in UTC.

    Naive timestamps are wrapped in a ``_repr_only`` marker rather than raising
    — see the module docstring's "Naive-timestamp policy" section for the
    rationale (the encoder is also the error-payload serializer).
    """
    if isinstance(ts, pd.Timestamp):
        if ts.tz is None:
            return {
                "_repr_only": True,
                "value": f"{ts.isoformat()} (naive)",
            }
        return ts.tz_convert("UTC").isoformat()
    if ts.tzinfo is None:
        return {
            "_repr_only": True,
            "value": f"{ts.isoformat()} (naive)",
        }
    return ts.astimezone(_dt.UTC).isoformat()


def to_json_safe(obj: Any, seen: set[int] | None = None) -> Any:
    """Recursively coerce ``obj`` into a JSON-serializable structure.

    Coercion rules (see design.md §S):

    * ``pd.Timestamp`` / ``datetime.datetime`` → ISO 8601 UTC string. Naive
      timestamps are wrapped in ``{"_repr_only": True, "value": "<iso>
      (naive)"}`` rather than raising — see the module docstring for why.
    * ``float('nan')``, ``float('inf')``, ``float('-inf')``, ``pd.NaT``,
      ``pd.NA``, ``None`` → ``None`` (becomes JSON ``null``). ``inf`` /
      ``-inf`` would otherwise emit the non-standard ``Infinity`` /
      ``-Infinity`` tokens that ``json.dumps`` writes by default.
    * numpy scalar types → native Python ``int`` / ``float`` / ``bool``.
    * ``np.ndarray`` → ``list`` (recursive).
    * ``dict`` / ``list`` / ``tuple`` → recursive (tuples become lists).
    * ``str`` / ``int`` / ``float`` / ``bool`` / ``None`` → pass through
      (with ``NaN`` floats coerced to ``None``).
    * Recursive cycles (a container that contains itself, directly or
      transitively) → ``{"_cycle": True, "value": repr(obj)}`` at the
      revisit point.
    * Anything else → ``{"_repr_only": True, "value": repr(obj)}``.

    Dict keys MUST be strings — JSON only admits string-keyed objects, and
    silently stringifying non-str keys (e.g. ``{1: "a", "1": "b"}``) would
    collapse two distinct entries into one. Non-string keys raise
    :class:`TypeError`.

    ``seen`` is an internal parameter used to detect cycles across recursive
    calls; callers pass ``None`` (the default) and a fresh set is allocated at
    the top of the call tree.
    """
    if seen is None:
        seen = set()

    # None / NaT / NA — note: pd.NA's truthiness raises, so use `is` first.
    if obj is None:
        return None
    if obj is pd.NaT:
        return None
    try:
        if obj is pd.NA:
            return None
    except TypeError:  # pragma: no cover - pd.NA identity comparison is safe
        pass

    # bool MUST come before int (bool is a subclass of int in Python).
    if isinstance(obj, bool):
        return obj

    # Plain int / str pass through. (bool already handled above.)
    if isinstance(obj, int) and not isinstance(obj, np.integer):
        return obj
    if isinstance(obj, str):
        return obj

    # Plain float — coerce NaN / inf / -inf to None; otherwise pass through.
    # (json.dumps writes inf as the non-standard "Infinity" token by default,
    # which non-Python JSON parsers reject. Treating it like NaN matches the
    # rest of the encoder's "non-finite → null" policy.)
    if isinstance(obj, float) and not isinstance(obj, np.floating):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # Timestamps / datetimes.
    if isinstance(obj, pd.Timestamp):
        return _coerce_timestamp(obj)
    if isinstance(obj, _dt.datetime):
        return _coerce_timestamp(obj)
    if isinstance(obj, np.datetime64):
        # numpy's datetime64 has no timezone slot — by convention we treat the
        # wall-clock value as UTC (matches how the rest of the stack stores
        # event_time / knowledge_time on the wire). NaT values are surfaced as
        # None to match the pd.NaT branch above.
        ts = pd.Timestamp(obj)
        if ts is pd.NaT:
            return None
        return _coerce_timestamp(ts.tz_localize("UTC"))
    if isinstance(obj, _dt.date):
        # plain date (no time) — ISO format is timezone-agnostic by definition.
        return obj.isoformat()

    # numpy scalars.
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        f = float(obj)
        if math.isnan(f) or math.isinf(f):
            return None
        return f

    # numpy arrays. (ndarrays don't form cycles in practice, but tolist()
    # materializes them into Python lists so recursion is bounded by depth.)
    if isinstance(obj, np.ndarray):
        return [to_json_safe(x, seen) for x in obj.tolist()]

    # Containers — track identity to short-circuit cycles.
    if isinstance(obj, dict | list | tuple):
        obj_id = id(obj)
        if obj_id in seen:
            return {"_cycle": True, "value": repr(obj)}
        seen.add(obj_id)
        try:
            if isinstance(obj, dict):
                for k in obj:
                    if not isinstance(k, str):
                        raise TypeError(
                            f"to_json_safe dict keys must be str; got {type(k).__name__}"
                        )
                return {k: to_json_safe(v, seen) for k, v in obj.items()}
            # list / tuple
            return [to_json_safe(x, seen) for x in obj]
        finally:
            seen.discard(obj_id)

    # Fallback — anything not JSON-encodable becomes a repr-only marker.
    return {"_repr_only": True, "value": repr(obj)}
