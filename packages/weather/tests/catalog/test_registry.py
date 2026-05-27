"""Unit tests for the WeatherAdapter registry + Protocol."""

from __future__ import annotations

# Importing the catalog package triggers eager registration of all
# 4 canonical adapters.
import mostlyright.weather.catalog as catalog
import pytest
from mostlyright.core.exceptions import (
    DataAvailabilityError,
    SourceUnavailableError,
    TradewindsError,
)
from mostlyright.weather.catalog import (
    get_adapter,
    list_sources,
    register_adapter,
)


def test_canonical_sources_registered():
    sources = set(list_sources())
    # IEM has two source IDs.
    assert {"iem.archive", "iem.live"}.issubset(sources)
    assert "awc.live" in sources
    assert {"cli.archive", "cli.live"}.issubset(sources)
    assert "ghcnh.archive" in sources


def test_get_adapter_returns_instance():
    a = get_adapter("iem.archive")
    assert hasattr(a, "SUPPORTED_SOURCES")
    assert "iem.archive" in a.SUPPORTED_SOURCES


def test_get_adapter_unknown_raises():
    """Phase 21 21-09: migrated to DataAvailabilityError(reason='model_unavailable').

    Back-compat catch via the TradewindsError base class still works for code
    that hasn't been updated. We assert both the new structural exception type
    AND the historical SourceUnavailableError path (which no longer catches
    this specific raise, but is still importable for other call sites).
    """
    with pytest.raises(DataAvailabilityError) as exc:
        get_adapter("bogus.source")
    assert exc.value.source == "bogus.source"
    assert exc.value.reason == "model_unavailable"
    # Catchable via the base class (back-compat for existing handler code).
    with pytest.raises(TradewindsError):
        get_adapter("bogus.source")
    # SourceUnavailableError is still importable but no longer catches this site.
    assert SourceUnavailableError is not DataAvailabilityError


def test_register_adapter_conflict_raises():
    """Re-registering a different class to an existing source raises."""
    from typing import ClassVar

    class Fake:
        SUPPORTED_SOURCES: ClassVar[list[str]] = ["iem.archive"]

    with pytest.raises(ValueError, match="already registered"):
        register_adapter("iem.archive", Fake)


def test_register_adapter_idempotent():
    """Re-registering the same class is a no-op."""
    iem_cls = catalog._REGISTRY["iem.archive"]
    register_adapter("iem.archive", iem_cls)
    assert catalog._REGISTRY["iem.archive"] is iem_cls


def test_protocol_runtime_attr():
    """Every registered adapter declares ``SUPPORTED_SOURCES`` at class level."""
    for source_id in list_sources():
        cls = catalog._REGISTRY[source_id]
        assert hasattr(cls, "SUPPORTED_SOURCES")
        assert source_id in cls.SUPPORTED_SOURCES


def test_get_adapter_returns_fresh_instance():
    a = get_adapter("awc.live")
    b = get_adapter("awc.live")
    assert a is not b  # fresh instance each call
    assert type(a) is type(b)
