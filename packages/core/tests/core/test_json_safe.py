"""Unit + property tests for :func:`tradewinds._v02._json_safe.to_json_safe`."""

from __future__ import annotations

import datetime as dt
import json
import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st
from tradewinds._v02._json_safe import to_json_safe


# ---------------------------------------------------------------------------
# Primitive pass-through
# ---------------------------------------------------------------------------
def test_none_passes_through():
    assert to_json_safe(None) is None


def test_bool_pass_through():
    assert to_json_safe(True) is True
    assert to_json_safe(False) is False


def test_int_pass_through():
    assert to_json_safe(42) == 42
    assert to_json_safe(-7) == -7
    assert to_json_safe(0) == 0


def test_str_pass_through():
    assert to_json_safe("hello") == "hello"
    assert to_json_safe("") == ""


def test_float_pass_through():
    assert to_json_safe(3.14) == 3.14
    assert to_json_safe(-1.5) == -1.5


def test_nan_float_becomes_none():
    assert to_json_safe(float("nan")) is None
    assert to_json_safe(math.nan) is None


def test_inf_float_becomes_none():
    assert to_json_safe(float("inf")) is None
    assert to_json_safe(float("-inf")) is None
    assert to_json_safe(math.inf) is None
    assert to_json_safe(-math.inf) is None


def test_inf_in_container_serializes_without_infinity_token():
    out = to_json_safe({"x": float("inf"), "y": float("-inf"), "z": 1.0})
    encoded = json.dumps(out)
    # Standard JSON has no Infinity token — verify neither leaked through.
    assert "Infinity" not in encoded
    assert "-Infinity" not in encoded
    assert out == {"x": None, "y": None, "z": 1.0}


def test_numpy_inf_becomes_none():
    assert to_json_safe(np.float64("inf")) is None
    assert to_json_safe(np.float64("-inf")) is None


# ---------------------------------------------------------------------------
# Pandas / numpy sentinels
# ---------------------------------------------------------------------------
def test_nat_becomes_none():
    assert to_json_safe(pd.NaT) is None


def test_pd_na_becomes_none():
    assert to_json_safe(pd.NA) is None


# ---------------------------------------------------------------------------
# Timestamps and datetimes
# ---------------------------------------------------------------------------
def test_aware_timestamp_iso():
    ts = pd.Timestamp("2026-05-21T12:30:00", tz="UTC")
    out = to_json_safe(ts)
    assert isinstance(out, str)
    assert out.startswith("2026-05-21T12:30:00")
    assert out.endswith("+00:00")


def test_aware_timestamp_other_tz_normalized_to_utc():
    ts = pd.Timestamp("2026-05-21T12:00:00", tz="America/Chicago")
    out = to_json_safe(ts)
    assert out.endswith("+00:00")
    # 12:00 Chicago in May (CDT, -5) → 17:00 UTC.
    assert "T17:00:00" in out


def test_naive_timestamp_wrapped_in_repr_marker():
    # Policy: the encoder is also the serializer for error payloads that
    # *report* naive-ts violations, so it cannot raise on them. Naive values
    # are wrapped in a _repr_only marker that preserves the value and
    # surfaces the naive-ness.
    ts = pd.Timestamp("2026-05-21T12:00:00")
    out = to_json_safe(ts)
    assert isinstance(out, dict)
    assert out["_repr_only"] is True
    assert "naive" in out["value"]
    assert "2026-05-21T12:00:00" in out["value"]
    json.dumps(out)


def test_aware_datetime_iso():
    d = dt.datetime(2026, 5, 21, 12, 0, 0, tzinfo=dt.UTC)
    out = to_json_safe(d)
    assert out.startswith("2026-05-21T12:00:00")
    assert "+00:00" in out


def test_aware_non_utc_datetime_normalized():
    tz = dt.timezone(dt.timedelta(hours=-5))
    d = dt.datetime(2026, 5, 21, 12, 0, 0, tzinfo=tz)
    out = to_json_safe(d)
    # 12:00 at -5 → 17:00 UTC.
    assert "T17:00:00" in out
    assert "+00:00" in out


def test_naive_datetime_wrapped_in_repr_marker():
    d = dt.datetime(2026, 5, 21, 12, 0, 0)
    out = to_json_safe(d)
    assert isinstance(out, dict)
    assert out["_repr_only"] is True
    assert "naive" in out["value"]
    assert "2026-05-21T12:00:00" in out["value"]
    json.dumps(out)


def test_naive_timestamp_in_violation_payload_serializes():
    # The motivating case: SchemaValidationError reports a violation that
    # includes the offending naive timestamp. The error's to_dict() must not
    # raise — the whole point of the encoder is to round-trip such payloads.
    from tradewinds._v02.exceptions import SchemaValidationError

    err = SchemaValidationError(
        "naive event_time on row 0",
        schema_id="iem.archive.observations",
        violations=[{"row_idx": 0, "column": "event_time", "value": dt.datetime(2026, 5, 21, 14)}],
    )
    payload = err.to_dict()
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    # The naive datetime survives as a repr-only marker.
    naive_val = decoded["violations"][0]["value"]
    assert isinstance(naive_val, dict)
    assert naive_val["_repr_only"] is True
    assert "naive" in naive_val["value"]


def test_plain_date_iso():
    d = dt.date(2026, 5, 21)
    assert to_json_safe(d) == "2026-05-21"


def test_np_datetime64_passes_through_to_iso():
    # numpy datetime64 has no tz slot — encoder treats it as UTC by convention.
    val = np.datetime64("2026-05-21T14:30")
    out = to_json_safe(val)
    assert isinstance(out, str)
    assert out.startswith("2026-05-21T14:30:00")
    assert out.endswith("+00:00")
    json.dumps(out)


def test_np_datetime64_nat_becomes_none():
    val = np.datetime64("NaT")
    assert to_json_safe(val) is None


def test_np_datetime64_in_container():
    data = {"event_time": np.datetime64("2026-05-21T14:30:00")}
    out = to_json_safe(data)
    assert out["event_time"].startswith("2026-05-21T14:30:00")
    assert out["event_time"].endswith("+00:00")
    json.dumps(out)


# ---------------------------------------------------------------------------
# numpy scalars
# ---------------------------------------------------------------------------
def test_numpy_int_to_python_int():
    out = to_json_safe(np.int64(42))
    assert out == 42
    assert isinstance(out, int)
    assert not isinstance(out, np.integer)


def test_numpy_float_to_python_float():
    out = to_json_safe(np.float64(2.5))
    assert out == 2.5
    assert isinstance(out, float)
    assert not isinstance(out, np.floating)


def test_numpy_float_nan_becomes_none():
    assert to_json_safe(np.float64("nan")) is None


def test_numpy_bool_to_python_bool():
    out = to_json_safe(np.bool_(True))
    assert out is True
    assert isinstance(out, bool)


# ---------------------------------------------------------------------------
# Arrays and containers
# ---------------------------------------------------------------------------
def test_ndarray_becomes_list():
    arr = np.array([1, 2, 3])
    out = to_json_safe(arr)
    assert out == [1, 2, 3]
    assert isinstance(out, list)


def test_ndarray_with_nan():
    arr = np.array([1.0, float("nan"), 3.0])
    out = to_json_safe(arr)
    assert out == [1.0, None, 3.0]


def test_ndarray_2d_recurses():
    arr = np.array([[1, 2], [3, 4]])
    out = to_json_safe(arr)
    assert out == [[1, 2], [3, 4]]


def test_dict_recurses():
    data = {"a": 1, "b": pd.NaT, "c": np.int32(5)}
    out = to_json_safe(data)
    assert out == {"a": 1, "b": None, "c": 5}


def test_dict_with_int_key_raises():
    with pytest.raises(TypeError, match="dict keys must be str"):
        to_json_safe({1: "a"})


def test_dict_with_tuple_key_raises():
    with pytest.raises(TypeError, match="dict keys must be str"):
        to_json_safe({("x", "y"): "a"})


def test_dict_with_mixed_keys_raises_on_first_non_str():
    # Even one non-str key trips the check (silent stringification would have
    # collapsed `1` and `"1"` into the same entry).
    with pytest.raises(TypeError, match="dict keys must be str"):
        to_json_safe({"valid": 1, 2: "b"})


def test_nested_dict_with_int_key_raises():
    with pytest.raises(TypeError, match="dict keys must be str"):
        to_json_safe({"outer": {1: "inner"}})


def test_list_recurses():
    data = [1, pd.NaT, np.int32(5), "hi"]
    out = to_json_safe(data)
    assert out == [1, None, 5, "hi"]


def test_tuple_becomes_list():
    out = to_json_safe((1, 2, 3))
    assert out == [1, 2, 3]
    assert isinstance(out, list)


def test_nested_dict_with_pandas_types():
    ts = pd.Timestamp("2026-05-21", tz="UTC")
    data = {
        "row_idx": np.int64(7),
        "event_time": ts,
        "value": np.float64("nan"),
        "nested": {"deep": [pd.NaT, 1, 2]},
    }
    out = to_json_safe(data)
    assert out["row_idx"] == 7
    assert out["event_time"].startswith("2026-05-21T00:00:00")
    assert out["value"] is None
    assert out["nested"] == {"deep": [None, 1, 2]}
    # And it survives a json.dumps round trip.
    assert json.loads(json.dumps(out)) == out


# ---------------------------------------------------------------------------
# Fallback: unencodable types
# ---------------------------------------------------------------------------
class _Weird:
    def __repr__(self) -> str:
        return "<Weird sentinel>"


def test_unknown_type_becomes_repr_marker():
    out = to_json_safe(_Weird())
    assert out == {"_repr_only": True, "value": "<Weird sentinel>"}
    # And serializable.
    assert json.loads(json.dumps(out)) == out


def test_set_becomes_repr_marker():
    # sets are not in the supported container list — fallback path.
    out = to_json_safe({1, 2, 3})
    assert isinstance(out, dict)
    assert out["_repr_only"] is True
    assert "value" in out


# ---------------------------------------------------------------------------
# Recursive cycles
# ---------------------------------------------------------------------------
def test_self_referential_dict_short_circuits():
    d: dict = {}
    d["self"] = d
    out = to_json_safe(d)
    # The outer dict survives; the recursive slot becomes a cycle marker.
    assert isinstance(out, dict)
    assert "self" in out
    assert out["self"] == {"_cycle": True, "value": repr(d)}
    # And the whole thing serializes.
    assert json.loads(json.dumps(out)) == out


def test_self_referential_list_short_circuits():
    lst: list = []
    lst.append(lst)
    out = to_json_safe(lst)
    assert isinstance(out, list)
    assert out[0] == {"_cycle": True, "value": repr(lst)}
    json.dumps(out)


def test_mutual_cycle_short_circuits():
    a: dict = {}
    b: dict = {}
    a["b"] = b
    b["a"] = a
    out = to_json_safe(a)
    assert out["b"]["a"] == {"_cycle": True, "value": repr(a)}
    json.dumps(out)


def test_repeated_non_cycle_reference_is_not_flagged():
    # The same dict reused in sibling positions is NOT a cycle — it's just
    # shared structure. Both copies should fully serialize.
    shared = {"x": 1}
    parent = {"a": shared, "b": shared}
    out = to_json_safe(parent)
    assert out == {"a": {"x": 1}, "b": {"x": 1}}


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------
# A JSON-clean strategy: nested dict / list of JSON primitives (no NaN floats —
# those are spec'd to coerce to None, which would make round-trip checks
# non-trivial; we cover NaN explicitly above).
_json_primitive = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(),
)
_json_nested = st.recursive(
    _json_primitive,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=0, max_size=10), children, max_size=5),
    ),
    max_leaves=20,
)


@given(_json_nested)
def test_property_clean_json_passes_through(value):
    """Any nested structure of JSON primitives is unchanged AND json.dumps-able."""
    out = to_json_safe(value)
    # tuples are not generated here; the structure should compare equal.
    assert out == value
    # And serializable.
    json.dumps(out)


@given(st.builds(_Weird))
def test_property_unencodable_yields_repr_marker(value):
    out = to_json_safe(value)
    assert out == {"_repr_only": True, "value": repr(value)}
    json.dumps(out)


@given(_json_nested)
def test_property_output_always_json_dumpsable(value):
    """No matter the input (within the clean strategy), output is JSON-serializable."""
    json.dumps(to_json_safe(value))


# A mixed strategy that includes a few unencodable values inside containers.
_mixed_nested = st.recursive(
    st.one_of(_json_primitive, st.builds(_Weird)),
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=0, max_size=10), children, max_size=5),
    ),
    max_leaves=20,
)


@given(_mixed_nested)
def test_property_mixed_unencodable_always_dumpsable(value):
    """Containers holding unencodable values still round-trip through json.dumps."""
    json.dumps(to_json_safe(value))
