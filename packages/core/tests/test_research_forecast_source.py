"""Phase 20 PLAN-06: research(forecast_source=...) wiring."""

from __future__ import annotations

import pytest

from mostlyright.research import _FORECAST_SOURCES_ALLOWED, _normalize_forecast_source


def test_forecast_sources_allowed_set() -> None:
    assert _FORECAST_SOURCES_ALLOWED == frozenset({"iem_mos", "open_meteo"})


def test_normalize_default_iem_mos() -> None:
    assert _normalize_forecast_source(None) == ("iem_mos",)


def test_normalize_string_form() -> None:
    assert _normalize_forecast_source("open_meteo") == ("open_meteo",)


def test_normalize_list_form() -> None:
    assert _normalize_forecast_source(["iem_mos", "open_meteo"]) == (
        "iem_mos",
        "open_meteo",
    )


def test_normalize_tuple_form() -> None:
    assert _normalize_forecast_source(("open_meteo",)) == ("open_meteo",)


def test_normalize_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown value"):
        _normalize_forecast_source("twc")


def test_normalize_rejects_unknown_in_list() -> None:
    with pytest.raises(ValueError, match="unknown value"):
        _normalize_forecast_source(["iem_mos", "bogus"])
