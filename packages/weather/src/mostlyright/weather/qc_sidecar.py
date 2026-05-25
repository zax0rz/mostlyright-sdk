"""Phase 3.4 — observation QC sidecar writer.

Writes per-(station, year, month) parquet sidecars produced by
``tradewinds.qc.QCEngine.build_sidecar_rows()`` to the canonical
location ``$HOME/.tradewinds/cache/v1/observations_qc/{station}/{YYYY}/
{MM}.parquet``. Best-effort: failures log + degrade silently so QC
never breaks the research pipeline.

Sibling of :mod:`tradewinds.weather.cache` — uses the same atomic-write
pattern + `_cache_root` + filelock guard so concurrent processes don't
clobber each other's sidecar files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tradewinds._internal._bounds import (
    assert_path_under,
    validate_icao_for_path,
)

from .cache import CACHE_VERSION as _CACHE_VERSION
from .cache import _atomic_write, _cache_root

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


def qc_sidecar_path(station: str, year: int, month: int) -> Path:
    """Return the QC sidecar parquet path for ``(station, year, month)``.

    Mirrors :func:`tradewinds.weather.cache.cache_path` layout but under
    the ``observations_qc/`` namespace established by Phase 2.1 LINEAGE-05.
    Path validation is identical (defense-in-depth against caller-controlled
    station strings).
    """
    validate_icao_for_path(station, field="station")
    root = _cache_root()
    raw = (
        root / _CACHE_VERSION / "observations_qc" / station / f"{year:04d}" / f"{month:02d}.parquet"
    )
    assert_path_under(raw, root, field="qc_sidecar_path")
    return raw


def write_qc_sidecar(
    sidecar_rows: list[dict[str, Any]],
    *,
    station: str,
    year: int,
    month: int,
) -> Path | None:
    """Persist QC sidecar rows for ``(station, year, month)``.

    Idempotent: writes via :func:`tradewinds.weather.cache._atomic_write`
    so partial writes don't leak. Returns the written path on success or
    ``None`` if the row list was empty (no rule fired → no sidecar to
    write, no I/O at all).

    Failures (filesystem errors, permissions) log at WARNING and return
    ``None`` rather than raising — QC is best-effort and must not break
    the wrapping ``research()`` call. The caller can audit by checking
    the returned path.
    """
    if not sidecar_rows:
        return None
    try:
        import pyarrow as pa
    except ImportError:  # pragma: no cover — pyarrow is a runtime dep
        log.warning("write_qc_sidecar: pyarrow not importable; skipping write")
        return None
    try:
        table = pa.Table.from_pylist(sidecar_rows)
    except Exception as exc:
        log.warning("write_qc_sidecar: table construction failed: %s", exc)
        return None
    try:
        path = qc_sidecar_path(station, year, month)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, table)
        return path
    except (OSError, ValueError) as exc:
        log.warning(
            "write_qc_sidecar: write failed for %s/%04d/%02d: %s",
            station,
            year,
            month,
            exc,
        )
        return None


__all__ = ["qc_sidecar_path", "write_qc_sidecar"]
