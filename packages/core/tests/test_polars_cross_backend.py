"""Phase 6 W2-T7: cross-backend tests for narwhals-migrated modules.

Per-backend test matrix for the 5 modules W2 wired up to accept polars
input via the narwhals-compat boundary shim. Each test parametrizes
over [pandas, polars] input and asserts identical output via
``polars_out.to_pandas().equals(pandas_out)``.

Gated on ``@pytest.mark.polars`` so pandas-only environments skip
cleanly via ``pytest.importorskip("polars")`` at module load.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pl = pytest.importorskip("polars")
pytestmark = pytest.mark.polars

from datetime import UTC  # noqa: E402

from tradewinds import preprocessing, qc, transforms  # noqa: E402
from tradewinds.core.formats import csv as csv_fmt  # noqa: E402
from tradewinds.core.formats import json as json_fmt  # noqa: E402
from tradewinds.core.formats import toon as toon_fmt  # noqa: E402


def _series_equal_nansafe(a_vals: list, b_vals: list) -> bool:
    """Compare two value lists treating NaN positions as equal."""
    if len(a_vals) != len(b_vals):
        return False
    for a, b in zip(a_vals, b_vals, strict=True):
        a_nan = a is None or (isinstance(a, float) and np.isnan(a))
        b_nan = b is None or (isinstance(b, float) and np.isnan(b))
        if a_nan and b_nan:
            continue
        if a_nan or b_nan:
            return False
        if a != b:
            return False
    return True


@pytest.fixture
def sample_pdf() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=10, freq="D", tz="UTC"),
            "temp_f": [40.0, 42.0, 41.0, 45.0, 50.0, 55.0, 60.0, 58.0, 56.0, 52.0],
            "wind_mph": [5.0, 10.0, 15.0, 20.0, 8.0, 12.0, 3.0, 7.0, 11.0, 14.0],
        }
    )


@pytest.fixture
def sample_pldf(sample_pdf: pd.DataFrame) -> pl.DataFrame:
    return pl.from_pandas(sample_pdf)


# ----------------------- transforms -----------------------


def test_lag_backend_equivalence(sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame) -> None:
    pandas_out = transforms.lag(sample_pdf, "temp_f", periods=2)
    polars_out = transforms.lag(sample_pldf, "temp_f", periods=2)
    # polars→pandas conversion preserves values and null positions.
    assert isinstance(polars_out, pl.Series)
    assert _series_equal_nansafe(polars_out.to_pandas().tolist(), pandas_out.tolist())


def test_diff_backend_equivalence(sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame) -> None:
    pandas_out = transforms.diff(sample_pdf, "temp_f")
    polars_out = transforms.diff(sample_pldf, "temp_f")
    assert isinstance(polars_out, pl.Series)
    assert _series_equal_nansafe(polars_out.to_pandas().tolist(), pandas_out.tolist())


def test_diff2_backend_equivalence(sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame) -> None:
    pandas_out = transforms.diff2(sample_pdf, "temp_f")
    polars_out = transforms.diff2(sample_pldf, "temp_f")
    assert isinstance(polars_out, pl.Series)
    assert _series_equal_nansafe(polars_out.to_pandas().tolist(), pandas_out.tolist())


def test_rolling_backend_equivalence(sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame) -> None:
    pandas_out = transforms.rolling(sample_pdf, "temp_f", window=3, fn="mean")
    polars_out = transforms.rolling(sample_pldf, "temp_f", window=3, fn="mean")
    assert isinstance(polars_out, pl.Series)
    assert _series_equal_nansafe(polars_out.to_pandas().tolist(), pandas_out.tolist())


def test_calendar_features_backend_equivalence(
    sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame
) -> None:
    pandas_out = transforms.calendar_features(sample_pdf, "date")
    polars_out = transforms.calendar_features(sample_pldf, "date")
    assert isinstance(polars_out, pl.DataFrame)
    # polars frame round-trip preserves added columns.
    pl_as_pd = polars_out.to_pandas()
    for col in ("month_sin", "month_cos", "dow_sin", "dow_cos", "hour_sin", "hour_cos"):
        assert col in pl_as_pd.columns
        assert pl_as_pd[col].tolist() == pandas_out[col].tolist()


def test_spread_backend_equivalence(sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame) -> None:
    pandas_out = transforms.spread(sample_pdf, "temp_f", "wind_mph")
    polars_out = transforms.spread(sample_pldf, "temp_f", "wind_mph")
    assert isinstance(polars_out, pl.Series)
    assert polars_out.to_pandas().tolist() == pandas_out.tolist()


def test_clip_outliers_backend_equivalence(
    sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame
) -> None:
    pandas_out = transforms.clip_outliers(sample_pdf, "temp_f", std=2.0)
    polars_out = transforms.clip_outliers(sample_pldf, "temp_f", std=2.0)
    assert isinstance(polars_out, pl.Series)
    assert polars_out.to_pandas().tolist() == pandas_out.tolist()


# ----------------------- preprocessing -----------------------


def test_preprocessing_clip_outliers_backend_equivalence(
    sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame
) -> None:
    pandas_out = preprocessing.clip_outliers(sample_pdf, "temp_f", bounds=(45.0, 55.0))
    polars_out = preprocessing.clip_outliers(sample_pldf, "temp_f", bounds=(45.0, 55.0))
    assert isinstance(polars_out, pl.Series)
    assert polars_out.to_pandas().tolist() == pandas_out.tolist()


# ----------------------- qc.crosscheck_iem_ghcnh -----------------------


def _make_crosscheck_frames(
    backend: str,
) -> tuple[pd.DataFrame | pl.DataFrame, pd.DataFrame | pl.DataFrame]:
    iem_pdf = pd.DataFrame(
        {
            "station": ["KNYC", "KNYC", "KNYC"],
            "event_time": pd.to_datetime(
                ["2025-01-01T00:00Z", "2025-01-01T01:00Z", "2025-01-01T02:00Z"],
                utc=True,
            ),
            "temp_c": [10.0, 11.0, 12.0],
        }
    )
    ghcnh_pdf = pd.DataFrame(
        {
            "station": ["KNYC", "KNYC", "KNYC"],
            "event_time": pd.to_datetime(
                ["2025-01-01T00:00Z", "2025-01-01T01:00Z", "2025-01-01T02:00Z"],
                utc=True,
            ),
            "temp_c": [10.5, 14.0, 12.1],
        }
    )
    if backend == "polars":
        return pl.from_pandas(iem_pdf), pl.from_pandas(ghcnh_pdf)
    return iem_pdf, ghcnh_pdf


def test_qc_crosscheck_backend_equivalence() -> None:
    iem_pdf, ghcnh_pdf = _make_crosscheck_frames("pandas")
    iem_pldf, ghcnh_pldf = _make_crosscheck_frames("polars")
    pandas_out = qc.crosscheck_iem_ghcnh(iem_pdf, ghcnh_pdf, tol_c=2.0)
    polars_out = qc.crosscheck_iem_ghcnh(iem_pldf, ghcnh_pldf, tol_c=2.0)
    assert isinstance(polars_out, pl.DataFrame)
    # Both should detect the one disagreement (delta = 3.0 °C at row 1).
    assert len(pandas_out) == 1
    assert len(polars_out) == 1
    polars_as_pandas = polars_out.to_pandas()
    assert polars_as_pandas["delta_c"].tolist() == pandas_out["delta_c"].tolist()


# ----------------------- formats -----------------------


def test_json_dumps_backend_equivalence(
    sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame
) -> None:
    # JSON output bytes must be identical regardless of caller backend.
    assert json_fmt.dumps(sample_pdf) == json_fmt.dumps(sample_pldf)


def test_csv_dumps_backend_equivalence(sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame) -> None:
    assert csv_fmt.dumps(sample_pdf) == csv_fmt.dumps(sample_pldf)


def test_toon_dumps_backend_equivalence(
    sample_pdf: pd.DataFrame, sample_pldf: pl.DataFrame
) -> None:
    assert toon_fmt.dumps(sample_pdf) == toon_fmt.dumps(sample_pldf)


# ----------------------- KnowledgeView (already covered by W0 test_result) -----------------------


def test_knowledge_view_accepts_polars_via_wrapper() -> None:
    """KV via TradewindsResult wrapper handles polars frames (W0 path)."""
    from datetime import datetime

    from tradewinds.core import KnowledgeView, TimePoint, TradewindsResult

    pdf = pd.DataFrame(
        {
            "knowledge_time": pd.to_datetime(
                ["2025-01-01T00:00:00Z", "2025-01-03T00:00:00Z"], utc=True
            ),
            "value": [1, 2],
        }
    )
    pldf = pl.from_pandas(pdf)
    result = TradewindsResult(
        frame=pldf,
        source="iem.live",
        retrieved_at=datetime(2025, 1, 4, tzinfo=UTC),
    )
    view = KnowledgeView(result, TimePoint("2025-01-02T00:00:00Z"))
    out = view.dataframe()
    assert len(out) == 1
