"""Phase 3 — Mode 2 source-explicit dispatch for ``research()``.

Mode 1 (the v0.14.1 parity baseline shipped in Phase 1) uses an
internal AWC > IEM > GHCNh priority. Mode 2 lets the caller pin
observations to a single named source — the workflow Vojtech wanted for
strategies that need source-identified training pairs that backtest the
same way they trade.

Surface:

- :func:`research_by_source(station, source, from_date, to_date)` —
  Mode 2 entry point. Returns a DataFrame where every row's
  ``observations`` source is the supplied ``source`` ID.
- :class:`SourceMismatchError` raised when the cache contains rows from
  a different source than the caller asked for (loud failure — never
  silently mixes sources).

See ``.planning/phases/03-mode-2-integration-migration-gate/`` for the
plan that drives the contract; see ``docs/design.md`` §R for the
source-identity invariant Mode 2 enforces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tradewinds.core.exceptions import SourceMismatchError
from tradewinds.weather.catalog import get_adapter

if TYPE_CHECKING:
    import pandas as pd


__all__ = ["research_by_source"]


#: Mode 2 supported sources. Climate and forecast follow in Phase 3.2.
_VALID_OBSERVATION_SOURCES = frozenset({"iem.archive", "iem.live", "awc.live", "ghcnh.archive"})


def research_by_source(
    station: str,
    source: str,
    from_date: str,
    to_date: str,
    *,
    as_dataframe: bool = True,
) -> pd.DataFrame:
    """Return source-explicit Mode 2 research pairs.

    Phase 3 v0.1.0 scope: this function is the dispatch seam — it
    resolves the catalog adapter for ``source``, validates the
    DataFrame's per-row source matches the caller's request, and
    returns the result.

    Phase 3.x extensions will:
    - Wire to the cache enhancements (filelock + LST-skip).
    - Add ``obs_source_tmin`` / ``obs_source_tmax`` columns to the gold
      output so each settlement-date row carries the contributing
      source per role.
    - Surface the v0.14.1 ``research()`` join with Mode 2 dispatch.

    Args:
        station: 3- or 4-letter station code.
        source: One of ``"iem.archive"``, ``"iem.live"``, ``"awc.live"``,
            ``"ghcnh.archive"``.
        from_date: ``YYYY-MM-DD`` inclusive.
        to_date: ``YYYY-MM-DD`` inclusive.
        as_dataframe: Reserved — matches Mode 1's signature.

    Returns:
        DataFrame with per-row source pinned to ``source``.

    Raises:
        ValueError: ``source`` is not in the supported set.
        SourceMismatchError: cache returned rows from a different source.
        NotImplementedError: Phase 3 fetch wiring lands in 3.1/3.2.
    """
    if source not in _VALID_OBSERVATION_SOURCES:
        raise ValueError(
            f"Mode 2 source must be one of {sorted(_VALID_OBSERVATION_SOURCES)}; " f"got {source!r}"
        )

    # Resolve the catalog adapter — fail loud if the source is unregistered.
    # (get_adapter raises SourceUnavailableError for unknown source IDs.)
    adapter = get_adapter(source)
    # Phase 3.1 + 3.2 will wire fetch_observations to live + cache paths.
    # v0.1.0 raises NotImplementedError; the validation surface and
    # adapter-dispatch contract are what Phase 3 ships.
    return adapter.fetch_observations(source, station, from_date, to_date)


def assert_source_identity(df: pd.DataFrame, expected_source: str) -> None:
    """Raise :class:`SourceMismatchError` if any row's source != expected.

    Mirrors the per-row check in :func:`tradewinds.core.validator.validate_dataframe`
    but at the Mode 2 dispatch layer so callers get a Mode-2-flavored
    error message naming the role.
    """
    if "source" not in df.columns:
        return  # Nothing to verify — let Validator handle the missing-column case.
    bad = df[df["source"] != expected_source]
    if not bad.empty:
        distinct = sorted(set(bad["source"].dropna().astype(str).tolist()))
        raise SourceMismatchError(
            f"Mode 2 dispatch requested {expected_source!r} but DataFrame "
            f"contains {len(bad)} row(s) with other sources: {distinct}",
            schema_source=expected_source,
            data_source=distinct[0] if distinct else "<unknown>",
            role="observations",
            catalog_warning=None,
        )
