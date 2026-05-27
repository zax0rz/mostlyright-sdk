"""Phase 17 PLAN-08: IEM MOS fetcher (_iem_mos.fetch_iem_mos)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pandas as pd
import pytest
from mostlyright.weather._fetchers._iem_mos import (
    SUPPORTED_MOS_MODELS,
    _parse_mos_row,
    _runtime_hours_for,
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
                    f"{status}",
                    request=None,
                    response=None,  # type: ignore[arg-type]
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
    assert frozenset({"nbe", "gfs", "lav", "met", "ecm"}) == SUPPORTED_MOS_MODELS


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
        "station",
        "issued_at",
        "valid_at",
        "forecast_hour",
        "model",
        "temp_c",
        "dew_point_c",
        "wind_speed_ms",
        "wind_dir_deg",
        "precip_probability",
        "sky_cover_pct",
        "source",
        "retrieved_at",
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
        fetch_iem_mos("KNYC", "not-a-date", "2026-05-01", client=_make_mock_client(None))


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


# ---------------------------------------------------------------------------
# Phase 17 Wave 3 iter-5 review: canonical-dtype regression coverage.
#
# ``fetch_iem_mos`` MUST coerce every canonical column to its schema dtype
# on BOTH return paths (empty and populated) so ``validate_dataframe(...,
# "schema.forecast.iem_mos.v1")`` succeeds in the documented no-data case
# and on populated frames where every numeric field is ``None`` (IEM ``M``
# sentinel). Without coercion pandas infers ``object`` and the validator
# would surface ``dtype_mismatch`` violations for callers exercising the
# documented schema contract.
# ---------------------------------------------------------------------------


def test_fetch_iem_mos_empty_dataframe_validates_against_schema() -> None:
    """Empty DataFrame (404 chain / no-data) must pass ``validate_dataframe``.

    Regression for codex iter-5 HIGH: prior to iter-2's
    ``_coerce_canonical_dtypes`` helper, the empty path returned columns
    of dtype ``object`` and the validator raised ``dtype_mismatch`` for
    every timestamp / numeric column.
    """
    from mostlyright.core import validate_dataframe

    client = _make_mock_client(None)
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert df.empty
    # Spot-check the dtypes the validator dispatches on.
    assert str(df["issued_at"].dtype) == "datetime64[ns, UTC]"
    assert str(df["valid_at"].dtype) == "datetime64[ns, UTC]"
    assert str(df["retrieved_at"].dtype) == "datetime64[ns, UTC]"
    assert str(df["forecast_hour"].dtype) == "Int64"
    assert str(df["wind_dir_deg"].dtype) == "Int64"
    assert str(df["sky_cover_pct"].dtype) == "Int64"
    assert str(df["temp_c"].dtype) == "Float64"
    assert str(df["dew_point_c"].dtype) == "Float64"
    assert str(df["wind_speed_ms"].dtype) == "Float64"
    assert str(df["precip_probability"].dtype) == "Float64"
    # Validator must accept the empty frame.
    reg = validate_dataframe(df, "schema.forecast.iem_mos.v1")
    assert reg.rows == 0
    assert reg.source == "iem.archive"


def test_fetch_iem_mos_all_missing_numeric_validates_against_schema() -> None:
    """Populated DataFrame where every numeric field is ``M`` must also
    validate — without coercion, all-null nullable numeric columns infer
    ``object`` dtype and the validator rejects them.
    """
    from mostlyright.core import validate_dataframe

    row = dict(_SAMPLE_ROW)
    row["tmp"] = "M"
    row["dpt"] = "M"
    row["wsp"] = "M"
    row["wdr"] = "M"
    row["pop12"] = "M"
    client = _make_mock_client({"data": [row]})
    df = fetch_iem_mos("KNYC", "2026-05-01", "2026-05-01", model="nbe", client=client)
    assert len(df) > 0
    # All numeric columns null, but their dtype must still be
    # nullable-numeric (not ``object``).
    assert str(df["temp_c"].dtype) == "Float64"
    assert str(df["wind_dir_deg"].dtype) == "Int64"
    # Validator must accept the all-null populated frame.
    reg = validate_dataframe(df, "schema.forecast.iem_mos.v1")
    assert reg.rows == len(df)
    assert reg.source == "iem.archive"


# Phase 17 Wave 3 iter-4 review hardening: NBE runtime-hour cutover.


def test_runtime_hours_for_nbe_post_cutover() -> None:
    """Post-2026-05-05: NBE on canonical 6-hourly grid {00,06,12,18}Z."""
    post = datetime(2026, 5, 10, tzinfo=UTC)
    assert _runtime_hours_for("nbe", post, post) == (0, 6, 12, 18)


def test_runtime_hours_for_nbe_pre_cutover() -> None:
    """Pre-2026-05-05: NBE on legacy {01,07,13,19}Z grid."""
    pre = datetime(2026, 5, 1, tzinfo=UTC)
    assert _runtime_hours_for("nbe", pre, pre) == (1, 7, 13, 19)


def test_runtime_hours_for_nbe_spanning_cutover() -> None:
    """Span the cutover → union of both hour sets (8 hours)."""
    pre = datetime(2026, 5, 1, tzinfo=UTC)
    post = datetime(2026, 5, 10, tzinfo=UTC)
    assert _runtime_hours_for("nbe", pre, post) == (0, 1, 6, 7, 12, 13, 18, 19)


def test_runtime_hours_for_gfs_always_canonical() -> None:
    """Non-NBE models always use {00,06,12,18}Z regardless of date range."""
    pre = datetime(2025, 1, 1, tzinfo=UTC)
    post = datetime(2026, 12, 31, tzinfo=UTC)
    for model in ("gfs", "lav", "met", "ecm"):
        assert _runtime_hours_for(model, pre, post) == (0, 6, 12, 18)


# ---------------------------------------------------------------------------
# Issue #17 regression: IEM MOS request contract — model param MUST be
# UPPERCASE. The IEM JSON endpoint at /api/1/mos.json validates ``model``
# against the regex ``^(AVN|GFS|ETA|NAM|NBS|NBE|ECM|LAV|MEX)$`` and returns
# HTTP 422 for any lowercase value. The unit-level coverage above all uses
# MagicMock and lets ``params=`` flow through opaquely, so this bug class
# was invisible to the existing suite. The ``httpx.MockTransport`` path
# exercises httpx's real URL builder, so ``request.url.params`` reflects
# what would actually hit the wire.
# ---------------------------------------------------------------------------


def test_fetch_iem_mos_sends_uppercase_model_param() -> None:
    """The model query param MUST be uppercase (IEM regex contract)."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    # Window AFTER the NBE 2026-05-05 cutover → canonical (0,6,12,18)Z = 4 GETs.
    with httpx.Client(transport=transport) as client:
        fetch_iem_mos("KNYC", "2026-05-10", "2026-05-10", model="nbe", client=client)

    assert len(captured_requests) > 0, "fetcher must have issued at least one GET"
    for req in captured_requests:
        got = req.url.params.get("model")
        assert got == "NBE", (
            f"IEM /api/1/mos.json regex ^(AVN|GFS|...|NBE|...)$ requires "
            f"uppercase model; got {got!r}. See issue #17."
        )


# ---------------------------------------------------------------------------
# Issue #17 live coverage: a @pytest.mark.live test that hits the REAL
# IEM endpoint end-to-end. Skipped in CI per the project testing playbook
# (CLAUDE.md: ``pytest -m "not live"`` is the CI default; live tests run
# manually before each publish). The unit-level MockTransport coverage
# above is the deterministic regression gate; this test is the empirical
# confirmation that the IEM contract still holds.
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_fetch_iem_mos_live_against_iem_api() -> None:
    """End-to-end live fetch against the real IEM MOS endpoint.

    Fixture: KNYC / NBE / 2024-01-15 (pre-cutover NBE hours
    ``{01,07,13,19}Z``). User-verified known-good — runtime
    ``2024-01-15T01:00:00+00:00`` returns HTTP 200 with ~21 rows.
    Asserts non-empty DataFrame with populated ``temp_c``,
    ``dew_point_c``, ``forecast_hour``.

    Run manually pre-publish:
    ``uv run pytest packages/weather/tests/test_iem_mos_fetcher.py::test_fetch_iem_mos_live_against_iem_api -v``.
    """
    df = fetch_iem_mos("KNYC", "2024-01-15", "2024-01-15", model="nbe")
    assert (
        not df.empty
    ), "live IEM MOS returned empty DataFrame; endpoint or fixture may have shifted"
    assert df["temp_c"].notna().any(), "no populated temp_c rows in live response"
    assert df["dew_point_c"].notna().any(), "no populated dew_point_c rows in live response"
    assert df["forecast_hour"].notna().any(), "no populated forecast_hour rows in live response"
    # Sanity: the model column reflects the uppercase contract.
    assert (df["model"] == "NBE").all()
