"""Phase 3.6 — Discovery API + public settlement + DataVersion.

Phase 3.6 v0.1.0 scope: ergonomic surface quants hit on day one.

- :func:`availability(station)` — "what do I have for KNYC?"
- :func:`climate_gaps(station, from_date, to_date)` — missing-CLI-date scan.
- :func:`describe(schema_id)` — pretty-print a registered schema.
- :func:`feature_catalog()` — list every available transform.
- :func:`settlement_date_for(station, contract_id, ts)` — top-level wrapper.
- :func:`settlement_window_utc(station, settlement_date)` — top-level wrapper.
- :class:`DataVersion` — reproducibility token stamping every research() call.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


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
    code_sha: str  # current git SHA of tradewinds itself
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


def availability(station: str) -> dict:
    """Return a summary of what tradewinds has cached for ``station``."""
    from pathlib import Path

    cache_root = Path.home() / ".tradewinds" / "cache" / "v1" / "observations" / station
    if not cache_root.exists():
        return {"station": station, "months_cached": 0, "first_month": None, "last_month": None}
    months = sorted(p.name for p in cache_root.rglob("*.parquet"))
    return {
        "station": station,
        "months_cached": len(months),
        "first_month": months[0] if months else None,
        "last_month": months[-1] if months else None,
    }


def climate_gaps(station: str, from_date: str, to_date: str) -> list[str]:
    """Return ISO-8601 dates in [from_date, to_date] with no CLI cache.

    Returns:
        List of date strings (``YYYY-MM-DD``) for which no CLI parquet
        cache file exists. Empty list when the range is fully cached.
    """
    raise NotImplementedError(
        "climate_gaps lands when the climate cache layout is finalized "
        "(Phase 3.6 alpha — pending Phase 3 cache enhancements)."
    )


def describe(schema_id: str) -> str:
    """Return a human-readable description of a registered schema."""
    from tradewinds.core.validator import _SCHEMA_REGISTRY

    cls = _SCHEMA_REGISTRY.get(schema_id)
    if cls is None:
        raise ValueError(f"Unknown schema_id {schema_id!r}; " f"known: {sorted(_SCHEMA_REGISTRY)}")
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
    """List every available transform in ``tradewinds.transforms``."""
    from tradewinds import transforms

    return [name for name in transforms.__all__]


def settlement_date_for(station: str, contract_id: str, ts: datetime) -> str:
    """Top-level wrapper around :func:`tradewinds.snapshot.settlement_date_for`."""
    from tradewinds.snapshot import settlement_date_for as _impl

    return _impl(station, ts)


def settlement_window_utc(station: str, settlement_date: str) -> tuple[datetime, datetime]:
    """Top-level wrapper around the settlement-window math in ``snapshot``."""
    raise NotImplementedError(
        "settlement_window_utc top-level wrapper lands when the cached "
        "settlement-window helper exposes a stable signature (Phase 3.6 alpha)."
    )
