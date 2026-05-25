"""Tests for mostlyright._internal.models._base — DictLikeMixin.

The mixin is exercised indirectly through Observation tests (getitem, to_dict,
to_storage_dict). This file adds dedicated coverage for the mixin's behavior
in isolation — particularly the ``__contains__``, ``get``, and computed-field
filtering surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class _SampleModel:
    """Minimal frozen dataclass mixing DictLikeMixin for isolated tests."""

    a: int
    b: str
    c: float | None


def _make_sample_with_mixin():
    """Build a class with DictLikeMixin at test time to avoid import-order issues."""
    from mostlyright._internal.models._base import DictLikeMixin

    @dataclass(frozen=True)
    class Sample(DictLikeMixin):
        _COMPUTED_FIELDS: ClassVar[frozenset[str]] = frozenset({"derived"})

        a: int
        b: str
        c: float | None
        derived: int = 0

    return Sample


def test_dict_like_getitem():
    Sample = _make_sample_with_mixin()
    s = Sample(a=1, b="hello", c=None)
    assert s["a"] == 1
    assert s["b"] == "hello"
    assert s["c"] is None


def test_dict_like_contains_str_key_present():
    Sample = _make_sample_with_mixin()
    s = Sample(a=1, b="hello", c=3.14)
    assert "a" in s
    assert "b" in s


def test_dict_like_contains_str_key_absent():
    Sample = _make_sample_with_mixin()
    s = Sample(a=1, b="hello", c=3.14)
    assert "z" not in s


def test_dict_like_contains_non_str_key_returns_false():
    Sample = _make_sample_with_mixin()
    s = Sample(a=1, b="hello", c=3.14)
    assert 0 not in s
    assert None not in s


def test_dict_like_get_with_default():
    Sample = _make_sample_with_mixin()
    s = Sample(a=1, b="hello", c=None)
    assert s.get("a") == 1
    assert s.get("z") is None
    assert s.get("z", "fallback") == "fallback"


def test_to_dict_includes_all_fields():
    Sample = _make_sample_with_mixin()
    s = Sample(a=1, b="hello", c=3.14, derived=42)
    d = s.to_dict()
    assert d == {"a": 1, "b": "hello", "c": 3.14, "derived": 42}


def test_to_storage_dict_excludes_computed():
    Sample = _make_sample_with_mixin()
    s = Sample(a=1, b="hello", c=3.14, derived=42)
    sd = s.to_storage_dict()
    assert sd == {"a": 1, "b": "hello", "c": 3.14}
    assert "derived" not in sd
