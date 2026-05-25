"""Phase 3.6 — Discovery API + public settlement + DataVersion.

Phase 3.6 v0.1.0 scope: ergonomic surface quants hit on day one.

- :func:`availability(station)` — "what do I have for KNYC?"
- :func:`climate_gaps(station, from_date, to_date)` — missing-CLI-date scan.
- :func:`describe(schema_id)` — pretty-print a registered schema.
- :func:`feature_catalog()` — list every available transform.
- :func:`settlement_date_for(station, ts)` — top-level wrapper.
- :func:`settlement_window_utc(station, settlement_date)` — top-level wrapper.
- :class:`DataVersion` — reproducibility token stamping every research() call.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path

__all__ = [
    "DataVersion",
    "availability",
    "climate_gaps",
    "describe",
    "feature_catalog",
    "settlement_date_for",
    "settlement_window_utc",
]


@dataclass(frozen=True)
class DataVersion:
    """Reproducibility token stamping a research() call.

    Carries enough metadata to re-run the same query against the same
    code + same data and get byte-identical output. ``token`` is a
    deterministic SHA-256 hash; ``components`` keeps the inputs for
    debugging.
    """

    sdk_version: str
    schema_ids: tuple[str, ...]
    sources: tuple[str, ...]
    code_sha: str  # current git SHA of mostlyright itself
    data_sha: str  # SHA of relevant cache files
    token: str  # SHA-256 hex of the canonical concatenation

    @classmethod
    def from_components(
        cls,
        *,
        sdk_version: str,
        schema_ids: tuple[str, ...],
        sources: tuple[str, ...],
        code_sha: str,
        data_sha: str,
    ) -> DataVersion:
        canonical = "|".join(
            [
                sdk_version,
                ",".join(sorted(schema_ids)),
                ",".join(sorted(sources)),
                code_sha,
                data_sha,
            ]
        )
        token = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            sdk_version=sdk_version,
            schema_ids=schema_ids,
            sources=sources,
            code_sha=code_sha,
            data_sha=data_sha,
            token=token,
        )

    @classmethod
    def for_research(
        cls,
        *,
        station: str,
        from_date: str,
        to_date: str,
        sdk_version: str | None = None,
    ) -> DataVersion:
        """Build a DataVersion for a research() call.

        Hashes the current SDK version + the (station, from_date, to_date)
        triple + a deterministic data-cache fingerprint so two callers
        running the same query against the same cache get the same token.

        Note: the ``sources`` tuple is the SDK's source-priority contract,
        not the per-call subset that actually returned rows. v0.1.0 has
        no source-filter kwarg, so the contract matches reality; v0.2
        with explicit source toggles should narrow this to the actually-
        consulted set.
        """
        if sdk_version is None:
            from mostlyright import __version__ as _sdk_version

            sdk_version = _sdk_version
        data_sha = _hash_cache_files(station)
        return cls.from_components(
            sdk_version=sdk_version,
            schema_ids=(
                "schema.observation.v1",
                "schema.forecast.iem_mos.v1",
                "schema.settlement.cli.v1",
            ),
            sources=("iem.archive", "iem.live", "awc.live", "ghcnh", "nws.cli"),
            code_sha=f"research:{station}:{from_date}:{to_date}",
            data_sha=data_sha,
        )


def _cache_root() -> Path:
    """Cache root resolver — local to avoid importing mostlyright.weather.

    Returns the cache ROOT (without ``/v1``). Callers append ``/v1/{subdir}/...``
    themselves. Delegates to :func:`mostlyright._internal._cache_dir.resolve_cache_root_without_v1`
    (Phase 12 W4 + review-iter1 refactor) — single source of truth for the
    resolution order + deprecation warning across all 3 legacy ``_cache_root()``
    helpers.

    The :func:`mostlyright._internal._cache_dir.resolve_cache_dir` helper is the
    canonical shim for *new* callers that want the full cache directory
    (``~/.mostlyright/cache/v1``).
    """
    from mostlyright._internal._cache_dir import resolve_cache_root_without_v1

    return resolve_cache_root_without_v1()


def _hash_cache_files(station: str) -> str:
    """Return a SHA-256 of the on-disk cache files relevant to ``station``.

    Walks ``$MOSTLYRIGHT_CACHE_DIR/v1/{observations,climate}/{station}/``
    and hashes the concatenated (path, size, mtime) tuples — content
    hashing would be more rigorous but is too slow for an interactive
    "stamp my DataFrame" call. Path+size+mtime catches every realistic
    cache mutation (writes touch mtime; partial writes change size).
    """
    root = _cache_root()
    sha = hashlib.sha256()
    obs_dir = root / "v1" / "observations" / station
    cli_dir = root / "v1" / "climate" / station
    found = False
    for parent in (obs_dir, cli_dir):
        if not parent.exists():
            continue
        for path in sorted(parent.rglob("*.parquet")):
            try:
                stat = path.stat()
                sha.update(str(path).encode("utf-8"))
                sha.update(str(stat.st_size).encode("utf-8"))
                sha.update(str(int(stat.st_mtime)).encode("utf-8"))
                found = True
            except OSError:
                continue
    if not found:
        sha.update(b"<no-cache>")
    return sha.hexdigest()


def availability(station: str) -> dict:
    """Return a summary of what mostlyright has cached for ``station``."""
    root = _cache_root() / "v1"
    obs_dir = root / "observations" / station
    cli_dir = root / "climate" / station
    qc_dir = root / "observations_qc" / station

    obs_months = sorted(p.name for p in obs_dir.rglob("*.parquet")) if obs_dir.exists() else []
    cli_files = sorted(cli_dir.rglob("*.parquet")) if cli_dir.exists() else []
    qc_files = sorted(qc_dir.rglob("*.parquet")) if qc_dir.exists() else []

    climate_years = sorted(p.stem for p in cli_files)
    return {
        "station": station,
        "months_cached": len(obs_months),
        "first_month": obs_months[0] if obs_months else None,
        "last_month": obs_months[-1] if obs_months else None,
        "climate_years": len(climate_years),
        "first_climate_year": climate_years[0] if climate_years else None,
        "last_climate_year": climate_years[-1] if climate_years else None,
        "qc_sidecars": len(qc_files),
    }


def climate_gaps(station: str, from_date: str, to_date: str) -> list[str]:
    """Return ISO-8601 dates in ``[from_date, to_date]`` with no CLI cache.

    Coarse signal: iterates every calendar day in the inclusive range
    and checks whether the climate-year parquet for that date's year
    exists. A year being cached does NOT prove every day within it was
    actually in the upstream response. For row-level gap detection,
    read the parquet directly and diff against the date range.
    """
    from_d = _date.fromisoformat(from_date)
    to_d = _date.fromisoformat(to_date)
    if from_d > to_d:
        return []

    root = _cache_root() / "v1" / "climate" / station
    if not root.exists():
        return [(from_d + timedelta(days=i)).isoformat() for i in range((to_d - from_d).days + 1)]
    cached_years: set[str] = {p.stem for p in root.rglob("*.parquet")}
    gaps: list[str] = []
    d = from_d
    while d <= to_d:
        if f"{d.year:04d}" not in cached_years:
            gaps.append(d.isoformat())
        d += timedelta(days=1)
    return gaps


def describe(schema_id: str) -> str:
    """Return a human-readable description of a registered schema."""
    from mostlyright.core.validator import _SCHEMA_REGISTRY

    cls = _SCHEMA_REGISTRY.get(schema_id)
    if cls is None:
        raise ValueError(f"Unknown schema_id {schema_id!r}; known: {sorted(_SCHEMA_REGISTRY)}")
    lines = [f"Schema: {schema_id}"]
    lines.append(f"  Class: {cls.__name__}")
    if getattr(cls, "_registered_source", None):
        lines.append(f"  Canonical source: {cls._registered_source}")
    lines.append(f"  Columns: {len(cls.COLUMNS)}")
    for col in cls.COLUMNS:
        nullable = "?" if col.nullable else ""
        units = f" {col.units}" if col.units else ""
        lines.append(f"    - {col.name}{nullable}: {col.dtype}{units}")
    return "\n".join(lines)


def feature_catalog() -> list[str]:
    """List every available transform in ``mostlyright.transforms``."""
    from mostlyright import transforms

    return list(transforms.__all__)


def settlement_date_for(station: str, ts: datetime) -> str:
    """Top-level wrapper around :func:`mostlyright.snapshot.settlement_date_for`.

    Args:
        station: ICAO or NWS code.
        ts: A timezone-aware datetime (UTC or any aware tz; converted
            via the station's LST offset by the snapshot layer).

    Returns:
        ``YYYY-MM-DD`` station-local settlement date.
    """
    from mostlyright.snapshot import settlement_date_for as _impl

    iso = ts.isoformat() if isinstance(ts, datetime) else str(ts)
    return _impl(iso, station)


def settlement_window_utc(station: str, settlement_date: str) -> tuple[datetime, datetime]:
    """Top-level wrapper around :func:`mostlyright.snapshot.settlement_window_utc`.

    Args:
        station: ICAO or NWS code.
        settlement_date: ``YYYY-MM-DD`` in LST.

    Returns:
        ``(window_start_utc, window_end_utc)`` aware UTC datetimes.
    """
    from mostlyright.snapshot import settlement_window_utc as _impl

    return _impl(settlement_date, station)
