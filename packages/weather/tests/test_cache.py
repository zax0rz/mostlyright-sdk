"""Tests for tradewinds.weather.cache.

Covers Task 1.4 acceptance criteria (CACHE-01, CACHE-07):

Path layout:
    - `cache_path` returns the spec'd directory structure (v1/observations/...)
    - `climate_cache_path` returns the annual layout (v1/climate/...)
    - `TRADEWINDS_CACHE_DIR` env var overrides the root

Atomic + concurrent safety:
    - `write_cache` followed by `read_cache` round-trips identically
    - Two multiprocess workers writing the same path produce a valid parquet
      (no truncation, no partial bytes) — only one set of rows wins
    - The `.tmp` sibling does not leak after a successful write

LST-current-month/year skip:
    - `write_cache` for the current LST month is a no-op (no parquet emitted)
    - `read_cache` returns `None` for the current LST month even if a file
      exists on disk (stale-read defense)
    - Same rules at year granularity for climate cache

Live-endpoint skip:
    - `write_cache(..., source="iem.live")` is a no-op
    - `write_climate_cache(..., source="cli.live")` is a no-op

Parquet options:
    - Written file has parquet version 2.6 metadata
    - Timestamp columns are coerced to microsecond precision (us)

Invalidate:
    - `invalidate` removes the file and returns True
    - Returns False when the file is absent

The tests do NOT depend on Task 1.1 / 1.2 — the cache module ships shimmed
fallbacks for `_lst_offset` and the pyarrow schemas, so this branch can be
developed and verified independently of its sibling Wave 1 sub-branches.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from tradewinds.weather import cache as cache_module
from tradewinds.weather.cache import (
    CACHE_VERSION,
    DEFAULT_ROOT,
    cache_path,
    climate_cache_path,
    invalidate,
    invalidate_climate,
    read_cache,
    read_climate_cache,
    write_cache,
    write_climate_cache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point TRADEWINDS_CACHE_DIR at an isolated tmp directory per test."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def freeze_to_past(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze `_now_lst` to a fixed past date so (2025, 1) is NOT current.

    Returns the UTC anchor so individual tests can assert their (year, month)
    arguments relative to it.
    """
    # Pick 2025-07-15 12:00 UTC. KNYC LST = UTC-5, so LST is 2025-07-15 07:00.
    # The (year=2025, month=1) test parameter is 6 months in the past — safely
    # NOT the current LST month for any of the test stations.
    fixed_utc = datetime(2025, 7, 15, 12, 0, tzinfo=UTC)

    def _fake_now(_station: str) -> datetime:
        # Replicate cache._now_lst behaviour but with a fixed UTC anchor.
        return fixed_utc + cache_module._lst_offset(_station)

    monkeypatch.setattr(cache_module, "_now_lst", _fake_now)
    return fixed_utc


def _sample_rows() -> list[dict[str, Any]]:
    """Three rows of observation-shaped data.

    `observed_at` is an ISO 8601 string per OBSERVATION_SCHEMA (which uses
    `pa.string()`, matching v0.14.1's storage format — strings, not native
    timestamps). The cache layer enforces this schema at write time, so
    fixtures must produce strings rather than datetime objects.
    """
    return [
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T12:00:00+00:00",
            "observation_type": "metar",
            "source": "iem.asos",
            "temp_f": 32.5,
            "wind_speed_kt": 8,
        },
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T13:00:00+00:00",
            "observation_type": "metar",
            "source": "iem.asos",
            "temp_f": 33.1,
            "wind_speed_kt": 10,
        },
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T14:00:00+00:00",
            "observation_type": "metar",
            "source": "awc.metar",
            "temp_f": 33.8,
            "wind_speed_kt": 12,
        },
    ]


# ---------------------------------------------------------------------------
# Path layout (CACHE-01)
# ---------------------------------------------------------------------------
class TestPathLayout:
    def test_observation_path_layout(self, tmp_cache_dir: Path) -> None:
        path = cache_path("KNYC", 2025, 1)
        # The tail of the path must follow v1/observations/<station>/<year>/<MM>.parquet
        assert path.parts[-5:] == (
            CACHE_VERSION,
            "observations",
            "KNYC",
            "2025",
            "01.parquet",
        )

    def test_observation_path_under_env_root(self, tmp_cache_dir: Path) -> None:
        path = cache_path("KNYC", 2025, 1)
        # The env var must control the root.
        assert path.is_relative_to(tmp_cache_dir)

    def test_climate_path_layout(self, tmp_cache_dir: Path) -> None:
        path = climate_cache_path("KNYC", 2025)
        assert path.parts[-4:] == (
            CACHE_VERSION,
            "climate",
            "KNYC",
            "2025.parquet",
        )

    def test_month_is_zero_padded(self, tmp_cache_dir: Path) -> None:
        # Month 1 -> "01.parquet", not "1.parquet"
        assert cache_path("KNYC", 2025, 1).name == "01.parquet"
        assert cache_path("KNYC", 2025, 12).name == "12.parquet"

    def test_year_is_four_digits(self, tmp_cache_dir: Path) -> None:
        # Year 2025 directory must be exactly "2025"
        assert "2025" in cache_path("KNYC", 2025, 1).parts
        # Climate file is "<year>.parquet"
        assert climate_cache_path("KNYC", 2025).name == "2025.parquet"


# ---------------------------------------------------------------------------
# Env var override
# ---------------------------------------------------------------------------
class TestEnvVarOverride:
    def test_env_var_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        path = cache_path("KNYC", 2025, 1)
        assert path.is_relative_to(tmp_path)
        # Tail layout unchanged.
        assert path.parts[-5:] == (
            CACHE_VERSION,
            "observations",
            "KNYC",
            "2025",
            "01.parquet",
        )

    def test_default_root_when_env_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TRADEWINDS_CACHE_DIR", raising=False)
        path = cache_path("KNYC", 2025, 1)
        # Should fall under $HOME/.tradewinds/cache/
        assert path.is_relative_to(DEFAULT_ROOT)

    def test_env_var_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Tilde expansion: ~/foo -> /home/.../foo
        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", "~/tw-cache-test")
        path = cache_path("KNYC", 2025, 1)
        assert "~" not in str(path)


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------
class TestRoundtrip:
    def test_observation_roundtrip(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows)
        out = read_cache("KNYC", 2025, 1)

        assert out is not None
        assert len(out) == len(rows)
        # Verify row identity (station_code, observed_at, source, temp_f).
        for orig, got in zip(rows, out, strict=True):
            assert got["station_code"] == orig["station_code"]
            assert got["observation_type"] == orig["observation_type"]
            assert got["source"] == orig["source"]
            assert got["temp_f"] == orig["temp_f"]
            assert got["wind_speed_kt"] == orig["wind_speed_kt"]

    def test_read_missing_returns_none(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # File never written -> read returns None.
        assert read_cache("KNYC", 2025, 1) is None

    def test_read_climate_missing_returns_none(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # Climate cache file never written -> read returns None.
        assert read_climate_cache("KNYC", 2024) is None

    def test_now_lst_uses_real_clock(self, tmp_cache_dir: Path) -> None:
        # Cover the un-stubbed `_now_lst` path (real-clock branch). Sanity
        # check: now_lst should be within ~10s of wall-clock + offset.
        from tradewinds.weather.cache import _now_lst

        before = datetime.now(UTC) + cache_module._lst_offset("KNYC")
        result = _now_lst("KNYC")
        after = datetime.now(UTC) + cache_module._lst_offset("KNYC")
        assert before <= result <= after

    def test_climate_roundtrip(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # freeze_to_past anchors `now` to 2025-07-15, so 2025 is the *current*
        # LST year and would be skipped. Use 2024 for a past-year roundtrip.
        rows = [
            {
                "station_code": "KNYC",
                "observation_date": "2024-01-06",
                "high_f": 38,
                "low_f": 22,
                "report_type": "final",
            },
            {
                "station_code": "KNYC",
                "observation_date": "2024-01-07",
                "high_f": 41,
                "low_f": 25,
                "report_type": "final",
            },
        ]
        write_climate_cache("KNYC", 2024, rows)
        out = read_climate_cache("KNYC", 2024)

        assert out is not None
        assert len(out) == 2
        assert out[0]["station_code"] == "KNYC"
        assert out[0]["high_f"] == 38

    def test_table_equals_after_roundtrip(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # Cache enforces OBSERVATION_SCHEMA (30+ columns from v0.14.1); fixtures
        # may provide a subset, and missing columns come back as null. Assert
        # input columns are PRESENT (not full equality) and row count matches.
        rows = _sample_rows()
        original = pa.Table.from_pylist(rows)
        write_cache("KNYC", 2025, 1, rows)
        path = cache_path("KNYC", 2025, 1)
        read_back = pq.read_table(path)
        assert read_back.num_rows == original.num_rows
        # Every column the test provided must round-trip back.
        assert set(original.column_names).issubset(set(read_back.column_names))
        # Values for the provided columns must match.
        for col in original.column_names:
            assert read_back.column(col).to_pylist() == original.column(col).to_pylist(), (
                f"column {col!r} did not round-trip equal"
            )


# ---------------------------------------------------------------------------
# Current-LST-month skip (CACHE-01)
# ---------------------------------------------------------------------------
class TestCurrentMonthSkip:
    @pytest.fixture
    def freeze_to_2025_06(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Freeze LST to (2025, 6) for any station."""
        # 2025-06-15 12:00 UTC -> LST for any US station is still in June.
        fixed_utc = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)

        def _fake_now(station: str) -> datetime:
            return fixed_utc + cache_module._lst_offset(station)

        monkeypatch.setattr(cache_module, "_now_lst", _fake_now)

    def test_write_skips_current_month(self, tmp_cache_dir: Path, freeze_to_2025_06: None) -> None:
        rows = _sample_rows()
        # Current LST month is (2025, 6) — write should be a no-op.
        write_cache("KNYC", 2025, 6, rows)
        path = cache_path("KNYC", 2025, 6)
        assert not path.exists(), "current-LST-month write should be a no-op"

    def test_read_skips_current_month(self, tmp_cache_dir: Path, freeze_to_2025_06: None) -> None:
        # Even if a parquet exists at the path, read_cache must return None
        # for the current LST month (stale-read defense).
        rows = _sample_rows()
        path = cache_path("KNYC", 2025, 6)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Bypass write_cache (it would skip); use raw pyarrow.
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, path, version="2.6", coerce_timestamps="us")
        assert path.exists()

        # read_cache must still return None.
        assert read_cache("KNYC", 2025, 6) is None

    def test_write_allows_past_month(self, tmp_cache_dir: Path, freeze_to_2025_06: None) -> None:
        # (2025, 1) is in the past — write should land.
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows)
        assert cache_path("KNYC", 2025, 1).exists()

    def test_west_coast_dst_boundary_no_shift(
        self, tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # LST uses standard offset (no DST). KLAX LST = UTC-8 year-round.
        # 2025-03-09 06:30 UTC -> LST for KLAX = 2025-03-08 22:30 (still March).
        fixed_utc = datetime(2025, 3, 9, 6, 30, tzinfo=UTC)

        def _fake_now(station: str) -> datetime:
            return fixed_utc + cache_module._lst_offset(station)

        monkeypatch.setattr(cache_module, "_now_lst", _fake_now)
        # Write to a different (year, month) — (2024, 12). Should land.
        rows = _sample_rows()
        write_cache("KLAX", 2024, 12, rows)
        assert cache_path("KLAX", 2024, 12).exists()


# ---------------------------------------------------------------------------
# Current-LST-year skip (climate cache)
# ---------------------------------------------------------------------------
class TestCurrentYearSkip:
    def test_climate_write_skips_current_year(
        self, tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Freeze to 2025.
        fixed_utc = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)

        def _fake_now(station: str) -> datetime:
            return fixed_utc + cache_module._lst_offset(station)

        monkeypatch.setattr(cache_module, "_now_lst", _fake_now)

        rows = [{"station_code": "KNYC", "observation_date": "2025-06-15"}]
        write_climate_cache("KNYC", 2025, rows)
        assert not climate_cache_path("KNYC", 2025).exists()

    def test_climate_read_skips_current_year(
        self, tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Freeze to 2025; pre-write a stale file via raw pyarrow.
        fixed_utc = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)

        def _fake_now(station: str) -> datetime:
            return fixed_utc + cache_module._lst_offset(station)

        monkeypatch.setattr(cache_module, "_now_lst", _fake_now)

        path = climate_cache_path("KNYC", 2025)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            pa.Table.from_pylist([{"station_code": "KNYC", "x": 1}]),
            path,
            version="2.6",
            coerce_timestamps="us",
        )
        assert path.exists()
        # Read must still return None.
        assert read_climate_cache("KNYC", 2025) is None


# ---------------------------------------------------------------------------
# Live-endpoint skip
# ---------------------------------------------------------------------------
class TestLiveEndpointSkip:
    def test_write_skips_live_source(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows, source="iem.live")
        assert not cache_path("KNYC", 2025, 1).exists()

    def test_write_skips_awc_live(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows, source="awc.live")
        assert not cache_path("KNYC", 2025, 1).exists()

    def test_climate_write_skips_live_source(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        rows = [{"station_code": "KNYC", "observation_date": "2025-01-06"}]
        write_climate_cache("KNYC", 2024, rows, source="cli.live")
        assert not climate_cache_path("KNYC", 2024).exists()

    def test_write_allows_archive_source(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # Non-live source -> normal write path.
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows, source="iem.asos")
        assert cache_path("KNYC", 2025, 1).exists()

    def test_write_no_source_kwarg_allows(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # source=None (default) is treated as not-live.
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows)
        assert cache_path("KNYC", 2025, 1).exists()


# ---------------------------------------------------------------------------
# Parquet options (CACHE-01)
# ---------------------------------------------------------------------------
class TestParquetOptions:
    def test_parquet_version_is_2_6(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows)
        path = cache_path("KNYC", 2025, 1)
        meta = pq.read_metadata(path)
        # Format version metadata starts with "2.6" — pyarrow may extend it.
        assert str(meta.format_version).startswith("2.6"), (
            f"expected parquet format_version to start with '2.6', got {meta.format_version!r}"
        )

    def test_observed_at_is_iso_string(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        """observed_at uses pa.string() per OBSERVATION_SCHEMA (v0.14.1 storage
        format). Earlier draft of this test expected timestamp[us] inferred by
        pyarrow; the merged schema overrides that with strings."""
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows)
        path = cache_path("KNYC", 2025, 1)
        table = pq.read_table(path)
        observed_at = table.schema.field("observed_at")
        ts_type = observed_at.type
        assert pa.types.is_string(ts_type), f"expected string, got {ts_type}"
        # Verify values are well-formed ISO-8601 with timezone
        first = table.column("observed_at")[0].as_py()
        assert first.startswith("2025-01-06T12:00:00"), f"unexpected ISO value: {first!r}"


# ---------------------------------------------------------------------------
# Atomic write + concurrent safety (CACHE-07)
# ---------------------------------------------------------------------------
def _writer_worker(
    cache_dir: str,
    station: str,
    year: int,
    month: int,
    rows: list[dict[str, Any]],
    fixed_utc_iso: str,
) -> None:
    """Module-level worker so multiprocessing can pickle it.

    Sets the cache dir env var inside the child process, then re-stubs
    `_now_lst` so the LST-current-month check passes regardless of wall clock.
    """
    os.environ["TRADEWINDS_CACHE_DIR"] = cache_dir
    # Re-import fresh inside the child.
    from tradewinds.weather import cache as child_cache

    fixed_utc = datetime.fromisoformat(fixed_utc_iso)

    def _fake_now(s: str) -> datetime:
        return fixed_utc + child_cache._lst_offset(s)

    child_cache._now_lst = _fake_now  # type: ignore[assignment]
    child_cache.write_cache(station, year, month, rows)


class TestConcurrentWriters:
    def test_two_workers_no_corruption(
        self, tmp_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Fixed UTC anchor; 2024-09 is in the past for any station.
        fixed_utc = datetime(2025, 7, 15, 12, 0, tzinfo=UTC)
        fixed_iso = fixed_utc.isoformat()

        rows_a = [
            {
                "station_code": "KMSY",
                "observed_at": f"2024-09-01T{i:02d}:00:00+00:00",
                "observation_type": "metar",
                "source": "worker_a",
                "temp_f": 75.0 + i,
            }
            for i in range(5)
        ]
        rows_b = [
            {
                "station_code": "KMSY",
                "observed_at": f"2024-09-01T{i:02d}:00:00+00:00",
                "observation_type": "metar",
                "source": "worker_b",
                "temp_f": 80.0 + i,
            }
            for i in range(5)
        ]

        # `spawn` start-method on macOS prevents the child from inheriting
        # monkeypatched module state. Use `spawn` and re-set state in worker.
        ctx = mp.get_context("spawn")
        p1 = ctx.Process(
            target=_writer_worker,
            args=(str(tmp_cache_dir), "KMSY", 2024, 9, rows_a, fixed_iso),
        )
        p2 = ctx.Process(
            target=_writer_worker,
            args=(str(tmp_cache_dir), "KMSY", 2024, 9, rows_b, fixed_iso),
        )
        p1.start()
        p2.start()
        p1.join(timeout=15)
        p2.join(timeout=15)

        # Both processes must terminate cleanly (no deadlock, no crash).
        assert not p1.is_alive(), "writer A did not finish within 15s"
        assert not p2.is_alive(), "writer B did not finish within 15s"
        assert p1.exitcode == 0, f"writer A failed with exitcode {p1.exitcode}"
        assert p2.exitcode == 0, f"writer B failed with exitcode {p2.exitcode}"

        # The destination file must exist and parse cleanly.
        path = cache_path("KMSY", 2024, 9)
        assert path.exists()
        # Re-stub for the parent's read.
        monkeypatch.setattr(
            cache_module,
            "_now_lst",
            lambda s: fixed_utc + cache_module._lst_offset(s),
        )
        out = read_cache("KMSY", 2024, 9)
        assert out is not None
        assert len(out) == 5
        # The winner must be entirely worker_a or entirely worker_b (no
        # interleaving / no partial bytes).
        sources = {row["source"] for row in out}
        assert sources == {"worker_a"} or sources == {"worker_b"}, (
            f"expected one writer to win cleanly; got mixed sources {sources}"
        )

        # No leftover .tmp sibling — atomic rename completed.
        tmp = path.with_suffix(".tmp")
        assert not tmp.exists(), f"leftover .tmp at {tmp}"


# ---------------------------------------------------------------------------
# Invalidate
# ---------------------------------------------------------------------------
class TestInvalidate:
    def test_invalidate_removes_file(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        write_cache("KNYC", 2025, 1, _sample_rows())
        path = cache_path("KNYC", 2025, 1)
        assert path.exists()

        assert invalidate("KNYC", 2025, 1) is True
        assert not path.exists()

    def test_invalidate_missing_returns_false(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        assert invalidate("KNYC", 2025, 1) is False

    def test_invalidate_climate_removes_file(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        rows = [{"station_code": "KNYC", "observation_date": "2024-01-06"}]
        write_climate_cache("KNYC", 2024, rows)
        path = climate_cache_path("KNYC", 2024)
        assert path.exists()

        assert invalidate_climate("KNYC", 2024) is True
        assert not path.exists()

    def test_invalidate_climate_missing_returns_false(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        assert invalidate_climate("KNYC", 2024) is False


# ---------------------------------------------------------------------------
# _lst_offset fallback (only relevant until Task 1.1 lands)
# ---------------------------------------------------------------------------
class TestLstOffsetFallback:
    def test_knyc_offset_is_minus_5(self) -> None:
        # EST is UTC-5 (no DST in LST).
        assert cache_module._lst_offset("KNYC") == timedelta(hours=-5)

    def test_klax_offset_is_minus_8(self) -> None:
        # PST is UTC-8 (no DST in LST).
        assert cache_module._lst_offset("KLAX") == timedelta(hours=-8)

    def test_unknown_station_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown station"):
            cache_module._lst_offset("KZZZ")


# ---------------------------------------------------------------------------
# Atomic write under sequential same-process race
# ---------------------------------------------------------------------------
class TestAtomicWrite:
    def test_no_tmp_leftover_after_write(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # After a successful write, the .tmp sibling must not remain.
        rows = _sample_rows()
        write_cache("KNYC", 2025, 1, rows)
        path = cache_path("KNYC", 2025, 1)
        tmp = path.with_suffix(".tmp")
        assert path.exists()
        assert not tmp.exists()

    def test_overwrite_replaces_existing(
        self,
        tmp_cache_dir: Path,
        freeze_to_past: datetime,
    ) -> None:
        # Writing twice must leave the second write's content.
        rows_a = _sample_rows()
        rows_b = [
            {
                "station_code": "KNYC",
                "observed_at": "2025-01-06T15:00:00+00:00",
                "observation_type": "metar",
                "source": "second",
                "temp_f": 99.9,
                "wind_speed_kt": 1,
            }
        ]
        write_cache("KNYC", 2025, 1, rows_a)
        write_cache("KNYC", 2025, 1, rows_b)
        out = read_cache("KNYC", 2025, 1)
        assert out is not None
        assert len(out) == 1
        assert out[0]["source"] == "second"
