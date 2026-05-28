"""Phase 6 W3 tests for backend / return_type dispatch on public entry points.

Covers the strict validation order:
1. backend value in supported set (else ValueError).
2. backend='polars' + return_type='dataframe' rejected (else ValueError).
3. ONLY THEN: missing [polars] extra raises SourceUnavailableError.

Plus the wrap_result happy path: backend='pandas' + return_type='wrapper'
returns a MostlyRightResult wrapping the unchanged pandas frame, and
default kwargs preserve v0.1.0 zero-behaviour-change.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from mostlyright.core._backend_dispatch import (
    convert_to_backend,
    validate_backend_kwargs,
    wrap_result,
)
from mostlyright.core.result import MostlyRightResult

# ----------------------- validate_backend_kwargs -----------------------


def test_validate_accepts_default_pair() -> None:
    # Default: backend='pandas', return_type='dataframe'.
    validate_backend_kwargs("pandas", "dataframe")  # must not raise


def test_validate_accepts_wrapper_on_pandas() -> None:
    validate_backend_kwargs("pandas", "wrapper")  # must not raise


def test_validate_accepts_wrapper_on_polars() -> None:
    validate_backend_kwargs("polars", "wrapper")  # must not raise


def test_validate_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="backend must be one of"):
        validate_backend_kwargs("pyarrow", "dataframe")  # type: ignore[arg-type]


def test_validate_rejects_unknown_return_type() -> None:
    with pytest.raises(ValueError, match="return_type must be one of"):
        validate_backend_kwargs("pandas", "ndarray")  # type: ignore[arg-type]


def test_validate_rejects_polars_with_dataframe() -> None:
    # Architect iter-1 HIGH-1 + Codex iter-1 P2: this combination is
    # explicitly invalid because polars frames have no df.attrs.
    with pytest.raises(ValueError, match="backend='polars' requires return_type='wrapper'"):
        validate_backend_kwargs("polars", "dataframe")


# ----------------------- wrap_result -----------------------


def test_wrap_result_default_returns_unwrapped_dataframe() -> None:
    df = pd.DataFrame({"value": [1, 2]})
    out = wrap_result(
        df,
        backend="pandas",
        return_type="dataframe",
        source="iem.live",
    )
    assert out is df  # zero-overhead, v0.1.0 shape preserved


def test_wrap_result_pandas_wrapper() -> None:
    df = pd.DataFrame({"value": [1, 2]})
    ts = datetime(2025, 1, 1, tzinfo=UTC)
    out = wrap_result(
        df,
        backend="pandas",
        return_type="wrapper",
        source="iem.live",
        retrieved_at=ts,
    )
    assert isinstance(out, MostlyRightResult)
    assert out.frame is df
    assert out.source == "iem.live"
    assert out.retrieved_at == ts


def test_wrap_result_polars_wrapper() -> None:
    pl = pytest.importorskip("polars")
    df = pd.DataFrame({"value": [1, 2]})
    ts = datetime(2025, 1, 1, tzinfo=UTC)
    out = wrap_result(
        df,
        backend="polars",
        return_type="wrapper",
        source="iem.live",
        retrieved_at=ts,
    )
    assert isinstance(out, MostlyRightResult)
    assert isinstance(out.frame, pl.DataFrame)
    assert out.source == "iem.live"


# ----------------------- convert_to_backend -----------------------


def test_convert_to_pandas_is_noop() -> None:
    df = pd.DataFrame({"value": [1]})
    assert convert_to_backend(df, "pandas") is df


@pytest.mark.polars
def test_convert_to_polars_returns_polars() -> None:
    pl = pytest.importorskip("polars")
    df = pd.DataFrame({"value": [1, 2]})
    out = convert_to_backend(df, "polars")
    assert isinstance(out, pl.DataFrame)
    assert out.to_pandas().equals(df)


# ----------------------- entry-point integration smoke tests -----------------------


def test_mode2_research_by_source_invalid_backend_raises() -> None:
    from mostlyright.mode2 import research_by_source

    with pytest.raises(ValueError, match="backend must be one of"):
        # source kwarg is also invalid but we should hit the backend check first
        # — actually source is validated before backend in mode2. Use a valid source.
        research_by_source(
            "KNYC",
            "iem.archive",
            "2025-01-01",
            "2025-01-02",
            backend="pyarrow",  # type: ignore[arg-type]
        )


def test_mode2_research_by_source_polars_dataframe_combo_raises() -> None:
    from mostlyright.mode2 import research_by_source

    with pytest.raises(ValueError, match="requires return_type='wrapper'"):
        research_by_source(
            "KNYC",
            "iem.archive",
            "2025-01-01",
            "2025-01-02",
            backend="polars",
            return_type="dataframe",
        )


def test_daily_extremes_default_returns_list() -> None:
    """v0.1.0 zero-behaviour-change: default return type stays list[dict]."""
    from datetime import date

    from mostlyright.international import daily_extremes

    # Cache is empty → returns [] (the default behaviour preserves this).
    out = daily_extremes("EGLL", date(2025, 1, 1), date(2025, 1, 1))
    assert isinstance(out, list)
    assert out == []


def test_daily_extremes_polars_without_wrapper_raises() -> None:
    from datetime import date

    from mostlyright.international import daily_extremes

    with pytest.raises(ValueError, match="requires return_type='wrapper'"):
        daily_extremes(
            "EGLL",
            date(2025, 1, 1),
            date(2025, 1, 1),
            backend="polars",
            return_type="list",
        )
