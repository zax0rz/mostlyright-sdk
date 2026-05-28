"""Phase 18 PREC-04: cache schema-version embedding + auto-invalidate tests.

Verifies that parquet cache files embed a ``_cache_schema_version`` metadata
field and that reads auto-invalidate when the embedded version does not match
the current canonical version. Existing pre-Phase-18 user caches (no version
metadata) are silently treated as cache-miss; the orchestrator re-fetches and
the next write embeds the current version.

The mechanism is distinct from ``CACHE_VERSION`` (the path-level version,
which is ``"v1"`` and does NOT change for Phase 18). ``_CACHE_SCHEMA_VERSION``
is the data-shape version that changes when row semantics shift — Phase 18
changed ``temp_c`` / ``temp_f`` precision rules for AWC + IEM, so existing
caches contain stale rows (e.g. ``temp_f=80.06`` where the corrected value is
``80.0``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from mostlyright.weather import cache as cache_module
from mostlyright.weather.cache import (
    cache_path,
    read_cache,
    write_cache,
)


@pytest.fixture
def tmp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point MOSTLYRIGHT_CACHE_DIR at an isolated tmp directory per test."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def freeze_to_past(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze ``_now_lst`` so (2020, 1..12) is NOT current.

    Pick 2025-07-15 12:00 UTC. All (2020, *) test parameters are 4+ years
    in the past — safely NOT the current LST month for any station.
    """
    fixed_utc = datetime(2025, 7, 15, 12, 0, tzinfo=UTC)

    def _fake_now(_station: str) -> datetime:
        return fixed_utc + cache_module._lst_offset(_station)

    monkeypatch.setattr(cache_module, "_now_lst", _fake_now)
    return fixed_utc


def _sample_rows() -> list[dict[str, Any]]:
    """Phase-18-shaped observation rows.

    The schema fields here follow OBSERVATION_SCHEMA used by the cache
    (string ``observed_at`` per v0.14.1 contract).
    """
    return [
        {
            "station_code": "KLGA",
            "observed_at": "2020-01-15T12:00:00+00:00",
            "observation_type": "metar",
            "source": "awc",
            "temp_f": 80.0,  # Phase 18: integer-valued
            "wind_speed_kt": 8,
        },
    ]


# ---------------------------------------------------------------------------
# Test A: write embeds the current schema version
# ---------------------------------------------------------------------------
def test_write_embeds_current_schema_version(tmp_cache_dir: Path, freeze_to_past: datetime) -> None:
    """write_cache produces a parquet file with _cache_schema_version metadata."""
    write_cache("KLGA", 2020, 1, _sample_rows())
    path = cache_path("KLGA", 2020, 1)
    assert path.exists()
    table = pq.read_table(path)
    metadata = table.schema.metadata or {}
    from mostlyright.weather.cache import (
        _CACHE_SCHEMA_VERSION,
        _CACHE_SCHEMA_VERSION_KEY,
    )

    version = metadata.get(_CACHE_SCHEMA_VERSION_KEY, b"").decode("utf-8")
    assert version, f"No _cache_schema_version metadata in {path}; metadata={metadata!r}"
    assert version == _CACHE_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Test B: read returns rows for matching version
# ---------------------------------------------------------------------------
def test_read_returns_rows_for_matching_version(
    tmp_cache_dir: Path, freeze_to_past: datetime
) -> None:
    """When written + read with the current version, rows roundtrip."""
    write_cache("KLGA", 2020, 1, _sample_rows())
    out = read_cache("KLGA", 2020, 1)
    assert out is not None
    assert len(out) == 1
    assert out[0]["temp_f"] == 80.0
    assert out[0]["station_code"] == "KLGA"


# ---------------------------------------------------------------------------
# Test C: missing-version cache invalidates on read + logs warning
# ---------------------------------------------------------------------------
def test_read_returns_none_for_missing_version_metadata(
    tmp_cache_dir: Path,
    freeze_to_past: datetime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pre-Phase-18 cache files have no _cache_schema_version → cache-miss + warning."""
    path = cache_path("KLGA", 2020, 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(_sample_rows())  # no metadata
    pq.write_table(table, path, version="2.6", coerce_timestamps="us")

    with caplog.at_level(logging.WARNING):
        out = read_cache("KLGA", 2020, 2)
    assert out is None, "missing-version cache should be treated as cache-miss"
    warning_text = " ".join(r.message for r in caplog.records)
    assert "schema version" in warning_text.lower() or "stale cache" in warning_text.lower(), (
        f"expected a stale-cache warning; got: {warning_text!r}"
    )


# ---------------------------------------------------------------------------
# Test D: mismatched-version cache invalidates on read + logs warning
# ---------------------------------------------------------------------------
def test_read_returns_none_for_mismatched_version(
    tmp_cache_dir: Path,
    freeze_to_past: datetime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """v1-pre-phase18 cache files are auto-invalidated on read."""
    path = cache_path("KLGA", 2020, 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(_sample_rows())
    table_with_md = table.replace_schema_metadata({b"_cache_schema_version": b"v1-pre-phase18"})
    pq.write_table(table_with_md, path, version="2.6", coerce_timestamps="us")

    with caplog.at_level(logging.WARNING):
        out = read_cache("KLGA", 2020, 3)
    assert out is None
    warning_text = " ".join(r.message for r in caplog.records)
    assert "schema version" in warning_text.lower() or "v1-pre-phase18" in warning_text.lower(), (
        f"expected version-mismatch warning; got: {warning_text!r}"
    )


# ---------------------------------------------------------------------------
# Test E: after mismatch invalidation, next write embeds current version
# ---------------------------------------------------------------------------
def test_invalidated_cache_overwritten_by_next_write(
    tmp_cache_dir: Path, freeze_to_past: datetime
) -> None:
    """After mismatch-invalidation, the next write embeds the current version."""
    path = cache_path("KLGA", 2020, 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(_sample_rows())
    table_with_md = table.replace_schema_metadata({b"_cache_schema_version": b"v0-ancient"})
    pq.write_table(table_with_md, path, version="2.6", coerce_timestamps="us")

    # Read once — invalidated
    assert read_cache("KLGA", 2020, 4) is None
    # Now write fresh
    write_cache("KLGA", 2020, 4, _sample_rows())
    # Re-read should now succeed
    out = read_cache("KLGA", 2020, 4)
    assert out is not None
    assert out[0]["temp_f"] == 80.0


# ---------------------------------------------------------------------------
# Test F: Issue 16 — a cache tagged with the PRIOR version
# (``v2-phase18-integer-f``) must invalidate on read, so GHCNh US ASOS rows
# re-parse with integer-°F recovery instead of serving stale back-converted
# temp_f (e.g. ``51.08`` where the corrected value is ``51.0``). The GHCNh fix
# changes row semantics without changing the parquet shape, so the schema
# version is the only signal that forces a re-parse. If the version bump is
# reverted, this test fails.
# ---------------------------------------------------------------------------
def test_read_invalidates_prior_v2_phase18_cache(
    tmp_cache_dir: Path,
    freeze_to_past: datetime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pre-Issue-16 (``v2-phase18-integer-f``) caches auto-invalidate on read."""
    path = cache_path("KLGA", 2020, 5)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(_sample_rows())
    table_with_md = table.replace_schema_metadata(
        {b"_cache_schema_version": b"v2-phase18-integer-f"}
    )
    pq.write_table(table_with_md, path, version="2.6", coerce_timestamps="us")

    with caplog.at_level(logging.WARNING):
        out = read_cache("KLGA", 2020, 5)
    assert out is None, "prior v2-phase18-integer-f cache must invalidate after the Issue 16 bump"
    warning_text = " ".join(r.message for r in caplog.records)
    assert "schema version" in warning_text.lower() or "stale cache" in warning_text.lower(), (
        f"expected a stale-cache warning; got: {warning_text!r}"
    )
