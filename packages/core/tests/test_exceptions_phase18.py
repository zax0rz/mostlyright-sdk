"""Phase 20 OM-04: IssuedAtMissingError + OpenMeteoSeamlessLeakageError."""

from __future__ import annotations

from mostlyright.core.exceptions import (
    IssuedAtMissingError,
    LeakageError,
    OpenMeteoSeamlessLeakageError,
    SchemaValidationError,
    TradewindsError,
)


def test_issued_at_missing_error_is_schema_validation_subclass() -> None:
    exc = IssuedAtMissingError()
    assert isinstance(exc, SchemaValidationError)
    assert isinstance(exc, TradewindsError)


def test_issued_at_missing_error_default_error_code() -> None:
    assert IssuedAtMissingError.default_error_code == "ISSUED_AT_MISSING"


def test_issued_at_missing_error_to_dict_populated() -> None:
    exc = IssuedAtMissingError(
        "3 rows missing issued_at",
        source="open_meteo.live",
        violating_count=3,
        sample_violations=[{"row_idx": 0}, {"row_idx": 5}],
    )
    d = exc.to_dict()
    assert d["name"] == "IssuedAtMissingError"
    assert d["error_code"] == "ISSUED_AT_MISSING"
    assert d["source"] == "open_meteo.live"
    assert d["violating_count"] == 3
    assert d["sample_violations"] == [{"row_idx": 0}, {"row_idx": 5}]
    assert d["origin_issue"] == "Tarabcak/mostlyright#70"


def test_issued_at_missing_error_constructible_with_no_args() -> None:
    exc = IssuedAtMissingError()
    d = exc.to_dict()
    assert d["violating_count"] == 0
    assert d["sample_violations"] == []
    assert d["source"] is None


def test_open_meteo_seamless_leakage_error_is_leakage_subclass() -> None:
    exc = OpenMeteoSeamlessLeakageError(
        model="gfs_seamless",
        endpoint_url="https://historical-forecast-api.open-meteo.com/v1/forecast",
    )
    assert isinstance(exc, LeakageError)
    assert isinstance(exc, TradewindsError)


def test_open_meteo_seamless_leakage_error_default_error_code() -> None:
    assert OpenMeteoSeamlessLeakageError.default_error_code == "OPEN_METEO_SEAMLESS_LEAKAGE"


def test_open_meteo_seamless_leakage_error_to_dict_populated() -> None:
    exc = OpenMeteoSeamlessLeakageError(
        "seamless endpoint banned for training",
        model="gfs_seamless",
        endpoint_url="https://historical-forecast-api.open-meteo.com/v1/forecast",
    )
    d = exc.to_dict()
    assert d["name"] == "OpenMeteoSeamlessLeakageError"
    assert d["error_code"] == "OPEN_METEO_SEAMLESS_LEAKAGE"
    assert d["model"] == "gfs_seamless"
    assert d["endpoint_url"] == "https://historical-forecast-api.open-meteo.com/v1/forecast"
    assert d["origin_issue"] == "Tarabcak/mostlyright#70"


def test_new_exceptions_exported_via_dunder_all() -> None:
    import mostlyright.core.exceptions as exc_mod

    assert "IssuedAtMissingError" in exc_mod.__all__
    assert "OpenMeteoSeamlessLeakageError" in exc_mod.__all__
