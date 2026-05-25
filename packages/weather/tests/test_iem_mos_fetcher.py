"""Phase 17 PLAN-08: IEM MOS fetcher (_iem_mos.fetch_iem_mos)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest

from mostlyright.weather._fetchers._iem_mos import (
    SUPPORTED_MOS_MODELS,
    _parse_mos_row,
    fetch_iem_mos,
)


def _make_mock_client(payload: dict | None, status: int = 200) -> MagicMock:
    """Return a MagicMock httpx.Client that always returns ``payload``."""
    mock = MagicMock()

    def _get(_url: str, params: dict | None = None) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        if status == 200:
            resp.json = MagicMock(return_value=payload or {"data": []})
            resp.raise_for_status = MagicMock()
        else:
            resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    f"{status}", request=None, response=None  # type: ignore[arg-type]
                )
            )
        return resp

    mock.get = MagicMock(side_effect=_get)
    return mock


_SAMPLE_ROW = {
    "runtime": "2026-05-01T00:00:00Z",
    "ftime": "2026-05-01T06:00:00Z",
    "station": "KNYC",
    "tmp": 68.0,  # F → 20°C
    "dpt": 50.0,
    "wsp": 10.0,  # 10 kt
    "wdr": 270,
    "pop12": 25.0,  # 25 %
}


def test_supported_mos_models_set() -> None:
    assert SUPPORTED_MOS_MODELS == frozenset({"nbe", "gfs", "lav", "met", "ecm"})


def test_fetch_iem_mos_returns_dataframe() -> None:
    payload = {"data": [_SAMPLE_ROW]}
    client = _make_mock_client(payload)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_fetch_iem_mos_canonical_columns_present() -> None:
    df = fetch_iem_mos(
        "KNYC", "2026-05-01", "2026-05-01", model="nbe", client=_make_mock_client(None)
    )
    expected = {
        "station", "issued_at", "valid_at", "forecast_hour", "model",
        "temp_c", "dew_point_c", "wind_speed_ms", "wind_dir_deg",
        "precip_probability", "sky_cover_pct", "source", "retrieved_at",
    }
    assert expected.issubset(set(df.columns))


def test_fetch_iem_mos_f_to_c_conversion() -> None:
    """tmp=68F → temp_c≈20.0; tmp=32F → temp_c≈0.0."""
    payload = {"data": [_SAMPLE_ROW]}
    client = _make_mock_client(payload)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert df["temp_c"].iloc[0] == pytest.approx(20.0, abs=0.001)


def test_fetch_iem_mos_kt_to_ms_conversion() -> None:
    """wsp=10kt → wind_speed_ms ≈ 5.144."""
    payload = {"data": [_SAMPLE_ROW]}
    client = _make_mock_client(payload)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert df["wind_speed_ms"].iloc[0] == pytest.approx(5.144, abs=0.01)


def test_fetch_iem_mos_pct_to_unit_conversion() -> None:
    """pop12=25 → precip_probability=0.25."""
    payload = {"data": [_SAMPLE_ROW]}
    client = _make_mock_client(payload)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert df["precip_probability"].iloc[0] == pytest.approx(0.25, abs=0.001)


def test_fetch_iem_mos_source_per_row_is_iem_archive() -> None:
    payload = {"data": [_SAMPLE_ROW]}
    client = _make_mock_client(payload)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert (df["source"] == "iem.archive").all()


def test_fetch_iem_mos_model_column_uppercase() -> None:
    payload = {"data": [_SAMPLE_ROW]}
    client = _make_mock_client(payload)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert (df["model"] == "NBE").all()


def test_fetch_iem_mos_forecast_hour_derived() -> None:
    """runtime=00Z, ftime=06Z → forecast_hour=6."""
    payload = {"data": [_SAMPLE_ROW]}
    client = _make_mock_client(payload)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert df["forecast_hour"].iloc[0] == 6


def test_fetch_iem_mos_empty_response_returns_empty_dataframe() -> None:
    client = _make_mock_client(None)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert df.empty
    assert "temp_c" in df.columns


def test_fetch_iem_mos_unknown_model_rejected() -> None:
    with pytest.raises(ValueError, match="model must be one of"):
        fetch_iem_mos(
            "KNYC",
            "2026-05-01",
            "2026-05-01",
            model="bogus",
            client=_make_mock_client(None),
        )


def test_fetch_iem_mos_404_skipped_silently() -> None:
    """404 from IEM (no data for runtime) is a normal expected case."""
    client = MagicMock()
    resp_404 = MagicMock()
    resp_404.status_code = 404
    resp_404.raise_for_status = MagicMock()
    client.get = MagicMock(return_value=resp_404)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert df.empty


def test_fetch_iem_mos_missing_field_yields_none() -> None:
    """IEM ``M`` / blank sentinels in numeric fields become Python None."""
    row = dict(_SAMPLE_ROW)
    row["tmp"] = "M"
    row["wsp"] = ""
    client = _make_mock_client({"data": [row]})
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert pd.isna(df["temp_c"].iloc[0])
    assert pd.isna(df["wind_speed_ms"].iloc[0])


def test_fetch_iem_mos_invalid_date_format_rejected() -> None:
    with pytest.raises(ValueError, match="ISO YYYY-MM-DD"):
        fetch_iem_mos(
            "KNYC", "not-a-date", "2026-05-01", client=_make_mock_client(None)
        )


def test_parse_mos_row_missing_runtime_returns_none() -> None:
    """Structurally invalid rows (no runtime / ftime) skip rather than corrupt."""
    from datetime import UTC, datetime

    result = _parse_mos_row(
        {"runtime": None, "ftime": None},
        station="KNYC",
        model="nbe",
        retrieved_at=datetime.now(UTC),
    )
    assert result is None
