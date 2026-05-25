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
#:
#: Production parsers emit BARE source tags (`iem`, `awc`, `ghcnh`) per
#: ``_iem.py:230``, ``_awc.py:320``, ``_ghcnh.py:306``. The dotted
#: forms (`iem.archive`, `iem.live`, `awc.live`, `ghcnh.archive`) are
#: tradewinds' canonical source-identity vocabulary documented in
#: ``docs/design.md`` §R and used by every schema's ``_registered_source``.
#: Mode 2 accepts BOTH at the input boundary and uses
#: :data:`_SOURCE_ALIASES` to map each request to the parser tags that
#: satisfy it — without this, a Mode 2 request for "iem.archive" would
#: find zero rows in production (parser emits bare "iem"). The
#: per-row source overlay column is the parser-emitted tag, NOT a
#: rewrite to the requested form, so downstream Validator schemas see
#: the truthful provenance.
_VALID_OBSERVATION_SOURCES = frozenset(
    {"iem", "iem.archive", "iem.live", "awc", "awc.live", "ghcnh", "ghcnh.archive"}
)


_SOURCE_ALIASES: dict[str, frozenset[str]] = {
    "iem": frozenset({"iem", "iem.archive", "iem.live"}),
    "iem.archive": frozenset({"iem", "iem.archive"}),
    "iem.live": frozenset({"iem", "iem.live"}),
    "awc": frozenset({"awc", "awc.live"}),
    "awc.live": frozenset({"awc", "awc.live"}),
    "ghcnh": frozenset({"ghcnh", "ghcnh.archive"}),
    "ghcnh.archive": frozenset({"ghcnh", "ghcnh.archive"}),
}


def research_by_source(
    station: str,
    source: str,
    from_date: str,
    to_date: str,
    *,
    as_dataframe: bool = True,
    backend: str = "pandas",
    return_type: str = "dataframe",
) -> pd.DataFrame | list[dict[str, Any]]:
    """Return source-explicit Mode 2 raw observations.

    Calls the existing observation fetcher (the same one Mode 1
    aggregates into pairs) and filters rows to the requested source.
    Result carries ``df.attrs["source"] = source`` +
    ``df.attrs["retrieved_at"]`` + a per-row ``source`` overlay column —
    the canonical validator contract used by all of tradewinds' Mode 2
    surfaces.

    **v0.1.0 limitation (codex iter-1 P1):** ``_fetch_observations_range``
    applies the Mode 1 merge policy (AWC > IEM > GHCNh on key collision)
    BEFORE returning rows. A Mode 2 caller asking for ``iem.archive``
    over a window where AWC also has data therefore sees only the IEM
    rows AWC did NOT supersede — not the full IEM coverage of the
    upstream feed. v0.2 will add a pre-merge source-isolated path; v0.1
    callers who need that today should call the per-source fetchers
    in ``tradewinds.weather._fetchers`` directly and skip the catalog
    layer.

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
            f"Mode 2 source must be one of {sorted(_VALID_OBSERVATION_SOURCES)}; got {source!r}"
        )

    # Codex iter-4 P2 fix: validate backend/return_type BEFORE any
    # network fetch or cache write so a typo doesn't trigger live
    # API calls + cache mutations before raising.
    from tradewinds.core._backend_dispatch import validate_backend_kwargs

    validate_backend_kwargs(backend, return_type)  # type: ignore[arg-type]

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

    # Filter to the parser tags that satisfy the requested source
    # (architect-CRITICAL fix: parsers emit bare `iem`/`awc`/`ghcnh`,
    # tradewinds' canonical vocab is dotted; the alias table bridges
    # both at the boundary without rewriting the per-row source —
    # downstream Validator sees the truthful parser-emitted tag).
    accepted_sources = _SOURCE_ALIASES.get(source, {source})
    filtered = [r for r in raw_obs if r.get("source") in accepted_sources]

    if not as_dataframe:
        return filtered

    import pandas as pd

    if not filtered:
        df = pd.DataFrame()
        retrieved_at = datetime.now(UTC)
        df.attrs["source"] = source
        df.attrs["retrieved_at"] = retrieved_at
        # Phase 6 W3-T2: dispatch even on the empty path.
        from tradewinds.core._backend_dispatch import (
            validate_backend_kwargs,
            wrap_result,
        )

        validate_backend_kwargs(backend, return_type)  # type: ignore[arg-type]
        if backend == "pandas" and return_type == "dataframe":
            return df
        return wrap_result(
            df,
            backend=backend,  # type: ignore[arg-type]
            return_type=return_type,  # type: ignore[arg-type]
            source=source,
            retrieved_at=retrieved_at,
        )

    df = pd.DataFrame(filtered)
    # Architect HIGH (silent rewrite): DO NOT overwrite per-row source —
    # the parser-emitted tag IS the truthful provenance. Downstream
    # Validator schemas reference the bare form; rewriting to a dotted
    # alias here would silently break source-identity invariants.
    # The aliasing table is INPUT-ONLY: it accepts both forms at the
    # boundary, but the returned DataFrame carries what the parser said.
    retrieved_at = datetime.now(UTC)
    df.attrs["source"] = source
    df.attrs["retrieved_at"] = retrieved_at
    df.attrs["accepted_sources"] = sorted(accepted_sources)

    # Phase 6 W3-T2: backend / return_type dispatch.
    from tradewinds.core._backend_dispatch import (
        validate_backend_kwargs,
        wrap_result,
    )

    validate_backend_kwargs(backend, return_type)  # type: ignore[arg-type]
    if backend == "pandas" and return_type == "dataframe":
        return df
    return wrap_result(
        df,
        backend=backend,  # type: ignore[arg-type]
        return_type=return_type,  # type: ignore[arg-type]
        source=source,
        retrieved_at=retrieved_at,
    )


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
