"""Shared backend/return_type dispatch for Phase 6 W3 public entry points.

The 5 public DataFrame-returning entries (``research``,
``research_by_source``, ``polymarket_discover``, ``forecast_nwp``,
``daily_extremes``) all add the same opt-in kwargs in v0.2:

- ``backend: Literal["pandas","polars"]="pandas"`` — chooses the output
  frame type. Default stays pandas so the v0.1.0 zero-behaviour-change
  constraint holds.
- ``return_type: Literal["dataframe","wrapper"]="dataframe"`` — chooses
  between raw DataFrame (legacy v0.1.0 shape; ``df.attrs`` carries
  provenance) and :class:`TradewindsResult` (new v0.2 shape).

The validation order is strict (architect iter-3 P2 fix):

1. ``backend`` value is in the supported set (else :class:`ValueError`).
2. ``backend="polars"`` requires ``return_type="wrapper"`` (else
   :class:`ValueError` — polars frames have no ``df.attrs``).
3. ONLY after kwargs are coherent, the lazy ``_polars_compat`` helper
   fires :class:`SourceUnavailableError` if the ``[polars]`` extra is
   missing.

This module centralizes that logic so each entry point's body stays
focused on its existing pandas pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from tradewinds.core.result import TradewindsResult

if TYPE_CHECKING:
    import pandas as pd


__all__ = [
    "BackendT",
    "ReturnTypeT",
    "convert_to_backend",
    "validate_backend_kwargs",
    "wrap_result",
]

BackendT = Literal["pandas", "polars"]
ReturnTypeT = Literal["dataframe", "wrapper"]

_SUPPORTED_BACKENDS: tuple[BackendT, ...] = ("pandas", "polars")
_SUPPORTED_RETURN_TYPES: tuple[ReturnTypeT, ...] = ("dataframe", "wrapper")


def validate_backend_kwargs(
    backend: BackendT,
    return_type: ReturnTypeT,
) -> None:
    """Validate the ``backend`` / ``return_type`` pair (steps 1 + 2).

    Raises ``ValueError`` on either:
    - Unsupported value.
    - ``backend="polars" + return_type="dataframe"`` (polars frames have
      no ``df.attrs`` so provenance MUST travel on a :class:`TradewindsResult`).

    Does NOT check that the ``[polars]`` extra is installed — callers do
    that lazily by invoking :func:`convert_to_backend` only when they
    actually need to convert.
    """
    if backend not in _SUPPORTED_BACKENDS:
        raise ValueError(
            f"backend must be one of {_SUPPORTED_BACKENDS}; got {backend!r}"
        )
    if return_type not in _SUPPORTED_RETURN_TYPES:
        raise ValueError(
            f"return_type must be one of {_SUPPORTED_RETURN_TYPES}; "
            f"got {return_type!r}"
        )
    if backend == "polars" and return_type == "dataframe":
        raise ValueError(
            "backend='polars' requires return_type='wrapper' — polars "
            "frames have no df.attrs to carry source/retrieved_at "
            "provenance. Use: backend='polars', return_type='wrapper'. "
            "Migration: result = tw.research(..., backend='polars', "
            "return_type='wrapper'); polars_df = result.frame; "
            "source = result.source."
        )


def convert_to_backend(df: pd.DataFrame, backend: BackendT) -> Any:
    """Convert a pandas DataFrame to the requested backend.

    Raises ``SourceUnavailableError`` with the install hint when
    ``backend="polars"`` and the ``[polars]`` extra is not installed
    (step 3 of the validation order).
    """
    if backend == "pandas":
        return df
    # backend == "polars"
    from tradewinds.core._polars_compat import require_polars

    pl = require_polars()
    return pl.from_pandas(df)


def wrap_result(
    df: pd.DataFrame,
    *,
    backend: BackendT,
    return_type: ReturnTypeT,
    source: str,
    retrieved_at: datetime | None = None,
    schema_id: str | None = None,
    qc: dict[str, Any] | None = None,
    data_version: Any | None = None,
) -> Any:
    """Wrap a pandas adapter result into the caller-requested shape.

    Branches:

    - ``backend="pandas", return_type="dataframe"`` (default, v0.1.0
      compat): return ``df`` unchanged. ``df.attrs`` is presumed to be
      already-populated by the pandas pipeline.
    - ``backend="pandas", return_type="wrapper"``: wrap the pandas frame
      in a :class:`TradewindsResult` with the provenance fields the
      caller passed.
    - ``backend="polars", return_type="wrapper"``: convert the pandas
      frame to polars via :func:`convert_to_backend`, then wrap.

    The ``backend="polars" + return_type="dataframe"`` combination is
    rejected upstream by :func:`validate_backend_kwargs`.

    Called by every public entry point as the OUTERMOST step (architect
    iter-1 HIGH-5 fix): the entire parity-locked pipeline runs in
    pandas; polars conversion happens here, on the already-pandas
    DataFrame, never inside ``_internal/_pairs.py`` /
    ``core/merge.py`` / ``core/_climate.py`` / validator / leakage.
    """
    if return_type == "dataframe":
        # backend == "pandas" by validate_backend_kwargs.
        return df

    # return_type == "wrapper"
    frame = convert_to_backend(df, backend)
    return TradewindsResult(
        frame=frame,
        source=source,
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
        schema_id=schema_id,
        qc=qc,
        data_version=data_version,
    )


def gate_polars_availability(backend: BackendT) -> None:
    """Pre-check `backend='polars'` requires the [polars] extra.

    Useful when callers want to fail fast BEFORE running the pandas
    pipeline (e.g. when the pipeline is expensive). The default flow
    via :func:`wrap_result` already raises at conversion time; this
    helper is the eager variant.
    """
    if backend == "polars":
        from tradewinds.core._polars_compat import require_polars

        require_polars()  # raises SourceUnavailableError if absent
