"""Tests for mostlyright._internal._cache_dir.resolve_cache_dir.

Phase 12 W4 back-compat shim:
- MOSTLYRIGHT_CACHE_DIR (canonical) wins when both set; no warning.
- TRADEWINDS_CACHE_DIR (legacy) alone emits DeprecationWarning, returns its value.
- Neither set → defaults to ``~/.mostlyright/cache/v1/``; no warning.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest


def test_canonical_wins_when_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", "/tmp/x")
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", "/tmp/y")
    from mostlyright._internal._cache_dir import resolve_cache_dir

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = resolve_cache_dir()

    assert result == Path("/tmp/x")
    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]


def test_legacy_only_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOSTLYRIGHT_CACHE_DIR", raising=False)
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", "/tmp/y")
    from mostlyright._internal._cache_dir import resolve_cache_dir

    with pytest.warns(DeprecationWarning, match=r"TRADEWINDS_CACHE_DIR is deprecated"):
        result = resolve_cache_dir()
    assert result == Path("/tmp/y")


def test_default_when_neither_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOSTLYRIGHT_CACHE_DIR", raising=False)
    monkeypatch.delenv("TRADEWINDS_CACHE_DIR", raising=False)
    from mostlyright._internal._cache_dir import resolve_cache_dir

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = resolve_cache_dir()

    assert result == Path.home() / ".mostlyright" / "cache" / "v1"
    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]
