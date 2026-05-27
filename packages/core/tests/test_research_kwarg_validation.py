"""Phase 21 21-01: tighter kwarg validation on `research()`.

Asserts that mutually-exclusive misuses and silent-no-op cases raise
`TypeError` BEFORE any network fetch. Matches the TS `ResearchOptions`
runtime checks lockstep — cross-SDK consumers see the same shape on
either side.
"""

from __future__ import annotations

import pytest
from mostlyright import research


def test_sources_and_source_mutually_exclusive() -> None:
    with pytest.raises(TypeError, match="mutually exclusive"):
        research(
            "KNYC",
            "2025-01-06",
            "2025-01-12",
            sources=["awc"],
            source="iem",
        )


def test_forecast_model_and_forecast_models_mutually_exclusive() -> None:
    with pytest.raises(TypeError, match="mutually exclusive"):
        research(
            "KNYC",
            "2025-01-06",
            "2025-01-12",
            include_forecast=True,
            forecast_model="gfs",
            forecast_models=["gfs", "nbm"],
        )


def test_forecast_model_requires_include_forecast() -> None:
    with pytest.raises(TypeError, match="include_forecast=True"):
        research(
            "KNYC",
            "2025-01-06",
            "2025-01-12",
            forecast_model="gfs",
        )


def test_forecast_models_requires_include_forecast() -> None:
    with pytest.raises(TypeError, match="include_forecast=True"):
        research(
            "KNYC",
            "2025-01-06",
            "2025-01-12",
            forecast_models=["gfs"],
        )


def test_validator_fires_before_network_fetch(monkeypatch) -> None:
    """The validator must run BEFORE any HTTP or cache I/O — a typo in
    kwargs should not first hit AWC / IEM / GHCNh.

    We assert this by stubbing the backend-dispatch validator to raise a
    sentinel exception. If the kwarg validator runs first, we see TypeError;
    if it runs after the backend validator, we see RuntimeError.
    """

    def _sentinel(_backend, _return_type):
        raise RuntimeError("backend validator ran too early")

    monkeypatch.setattr(
        "mostlyright.core._backend_dispatch.validate_backend_kwargs",
        _sentinel,
    )
    with pytest.raises(TypeError):
        research(
            "KNYC",
            "2025-01-06",
            "2025-01-12",
            sources=["awc"],
            source="iem",
        )
