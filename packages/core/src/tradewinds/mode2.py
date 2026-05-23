"""Phase 3 — Mode 2 source-explicit dispatch for ``research()``.

Mode 1 (the v0.14.1 parity baseline shipped in Phase 1) uses an
internal AWC > IEM > GHCNh priority. Mode 2 lets the caller pin
observations to a single named source — the workflow Vojtech wanted for
strategies that need source-identified training pairs that backtest the
same way they trade.

Surface:

- :func:`research_by_source(station, source, from_date, to_date)` —
  Mode 2 entry point. Returns a DataFrame where every row's
  ``source`` is the supplied ``source`` ID.
- :func:`assert_source_identity(df, expected_source)` — raise
  :class:`SourceMismatchError` if any row's source disagrees.

See ``docs/design.md`` §R for the source-identity invariant Mode 2
enforces.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as _date
from typing import TYPE_CHECKING, Any

from tradewinds.core.exceptions import SourceMismatchError

if TYPE_CHECKING:
    import pandas as pd


__all__ = ["assert_source_identity", "research_by_source"]


#: Mode 2 supported observation sources for v0.1.0.
_VALID_OBSERVATION_SOURCES = frozenset(
    {"iem.archive", "iem.live", "awc.live", "ghcnh", "ghcnh.archive"}
)


def research_by_source(
    station: str,
    source: str,
    from_date: str,
    to_date: str,
    *,
    as_dataframe: bool = True,
) -> pd.DataFrame | list[dict[str, Any]]:
    """Return source-explicit Mode 2 raw observations.

    Calls the existing observation fetcher (the same one Mode 1
    aggregates into pairs) and filters rows to the requested source.
    Result carries ``df.attrs["source"] = source`` +
    ``df.attrs["retrieved_at"]`` + a per-row ``source`` overlay column —
    the canonical validator contract used by all of tradewinds' Mode 2
    surfaces.

    Args:
        station: 3- or 4-letter station code (e.g. ``"NYC"``, ``"KNYC"``).
        source: One of :data:`_VALID_OBSERVATION_SOURCES`.
        from_date: ``YYYY-MM-DD`` inclusive.
        to_date: ``YYYY-MM-DD`` inclusive.
        as_dataframe: When True (default) return a pandas DataFrame;
            else return the raw ``list[dict]`` rows.

    Returns:
        DataFrame (or list[dict]) with one row per observation matching
        the requested source.

    Raises:
        ValueError: ``source`` not in the supported set.
        SourceMismatchError: filtered rows came back tagged with a
            different source than requested (defense-in-depth).
    """
    if source not in _VALID_OBSERVATION_SOURCES:
        raise ValueError(
            f"Mode 2 source must be one of {sorted(_VALID_OBSERVATION_SOURCES)}; " f"got {source!r}"
        )

    # Local import — research.py is heavy and we don't want mode2 to
    # pay the import cost on every package-level `from tradewinds`.
    from tradewinds.research import (
        _all_caches_warm,
        _fetch_observations_range,
        _prefetch_sources,
        _resolve_station,
    )

    info = _resolve_station(station)
    # Mirror research(): extend the fetch by one day so the last LST
    # day's pre-midnight UTC tail observations are captured.
    extended_to = (_date.fromisoformat(to_date) + timedelta(days=1)).isoformat()

    awc_rows: list[dict[str, Any]] | None = None
    if not _all_caches_warm(info, from_date, to_date, extended_to):
        prefetch = _prefetch_sources(info, from_date, to_date, extended_to)
        awc_rows = prefetch["awc_rows"]

    raw_obs = _fetch_observations_range(
        info,
        from_date,
        extended_to,
        prefetched_awc_rows=awc_rows,
    )

    # Filter to the requested source. Parsers emit rows tagged
    # `source` (e.g. `iem.archive`, `awc.live`, `ghcnh`). Treat
    # `ghcnh` and `ghcnh.archive` as aliases since the underlying
    # parser only emits the bare `ghcnh` form.
    accepted_sources = {source}
    if source in ("ghcnh", "ghcnh.archive"):
        accepted_sources = {"ghcnh", "ghcnh.archive"}
    filtered = [r for r in raw_obs if r.get("source") in accepted_sources]

    if not as_dataframe:
        return filtered

    import pandas as pd

    if not filtered:
        # Empty DataFrame still carries provenance attrs so callers
        # validating the result don't hit attrs-required errors.
        df = pd.DataFrame()
        df.attrs["source"] = source
        df.attrs["retrieved_at"] = datetime.now(UTC)
        return df

    df = pd.DataFrame(filtered)
    # Per-row source overlay column (validator contract — see
    # tradewinds.core.validator). Defensive: parsers emit `source` on
    # every row, so this is usually a no-op, but explicit assignment
    # ensures a Mode 2 caller always sees the column normalized.
    df["source"] = source

    # Defense-in-depth: confirm per-row source matches the request.
    assert_source_identity(df, source)

    df.attrs["source"] = source
    df.attrs["retrieved_at"] = datetime.now(UTC)
    return df


def assert_source_identity(df: pd.DataFrame, expected_source: str) -> None:
    """Raise :class:`SourceMismatchError` if any row's source != expected.

    Mirrors the per-row check in
    :func:`tradewinds.core.validator.validate_dataframe` but at the
    Mode 2 dispatch layer so callers get a Mode-2-flavored error
    message naming the role.
    """
    if "source" not in df.columns:
        return
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
