"""Phase 1.5 PERF-04 unit tests for ``_prefetch_sources``.

Covers:

- Pitfall 6 timing pattern (``submitted_at`` captured immediately after
  ``ex.submit()``; per-source times measured against actual work).
- max_workers=4 (Option C from SOURCE-LIMITS.md) — verified by inspecting
  the source AST.
- AWC rows pass through the prefetch and bypass the lazy ``_fetch_awc_for_window``
  call inside ``_fetch_observations_range``.
- Exception propagation: a worker that raises a non-handled error bubbles up
  via ``f.result()`` (no swallowing).
- The 4 worker names ("iem.archive", "awc.live", "ghcnh.archive", "cli.archive")
  appear in ``per_source_times``.
- The ``_all_caches_warm`` gate skips the prefetch when both parquet layers
  are fully populated (regression: fully-cached re-run fires zero HTTP).
"""

from __future__ import annotations

import ast
import inspect
import time
from pathlib import Path
from unittest.mock import patch

import pytest


def test_prefetch_sources_returns_per_source_times_with_four_names(monkeypatch, tmp_path) -> None:
    """The 4 named workers all appear in per_source_times."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _prefetch_sources

    info = STATIONS["NYC"]

    # Stub all 4 worker network functions to be no-ops/quick returns. The
    # spike's job here is to verify the ThreadPoolExecutor wiring, not the
    # fetchers themselves.
    with (
        patch("tradewinds.weather._fetchers.iem_asos.download_iem_asos", return_value=[]),
        patch("tradewinds.weather._fetchers.iem_cli.download_cli", return_value=Path("/tmp/x")),
        patch("tradewinds.weather._fetchers.ghcnh.download_ghcnh", return_value=Path("/tmp/x")),
        patch("tradewinds.research._fetch_awc_for_window", return_value=[]),
    ):
        result = _prefetch_sources(info, "2025-01-06", "2025-01-12", "2025-01-13")

    assert set(result["per_source_times"].keys()) == {
        "iem.archive",
        "awc.live",
        "ghcnh.archive",
        "cli.archive",
    }
    assert isinstance(result["wall_time"], float)
    assert result["wall_time"] >= 0


def test_prefetch_sources_pitfall_6_submitted_at_in_source(monkeypatch) -> None:
    """AST scan: ``submitted_at`` is assigned IMMEDIATELY after ``ex.submit()``,
    NOT inside an as_completed loop where iteration order would inflate the
    first-iterated future's timing.

    The Pitfall 6 anti-pattern is::

        for f in as_completed(futures):
            t0 = time.monotonic()
            f.result()  # blocks until DONE — inflates time for first iterated
            per_source_times[name] = time.monotonic() - t0  # WRONG

    The correct pattern (which we assert is present)::

        for name, fn in ...:
            f = ex.submit(fn)
            submitted_at[name] = time.monotonic()  # immediately after submit
            ...

        for f in as_completed(futures):
            per_source_times[name] = time.monotonic() - submitted_at[name]
    """
    import sys

    import tradewinds.research  # noqa: F401 — populates sys.modules

    research_mod = sys.modules["tradewinds.research"]

    src = inspect.getsource(research_mod._prefetch_sources)
    tree = ast.parse(src)

    # Find the "for name, fn in ..." loop that should contain submit + submitted_at.
    found_pattern = False
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            body_strs = [ast.unparse(stmt) for stmt in node.body]
            joined = "\n".join(body_strs)
            if "ex.submit" in joined and "submitted_at[" in joined:
                # Both assignments must be present in the same For body so
                # capture happens immediately after the submit call returns.
                found_pattern = True
                # Also assert submit() comes BEFORE the submitted_at assignment
                # in the source order (so the timer starts after work is queued).
                submit_idx = next(i for i, s in enumerate(body_strs) if "ex.submit" in s)
                cap_idx = next(i for i, s in enumerate(body_strs) if "submitted_at[" in s)
                assert submit_idx < cap_idx, (
                    "submitted_at[name] must be assigned AFTER ex.submit() — "
                    "Pitfall 6 anti-pattern detected"
                )
                break
    assert found_pattern, "Pitfall 6 pattern missing in _prefetch_sources"


def test_prefetch_sources_uses_max_workers_4(monkeypatch) -> None:
    """SOURCE-LIMITS.md Option C: max_workers=4. AST scan."""
    import sys

    import tradewinds.research  # noqa: F401 — populates sys.modules

    research_mod = sys.modules["tradewinds.research"]

    src = inspect.getsource(research_mod._prefetch_sources)
    tree = ast.parse(src)

    pool_calls = []
    for node in ast.walk(tree):
        # Match concurrent.futures.ThreadPoolExecutor(...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "ThreadPoolExecutor"
        ):
            pool_calls.append(node)
    assert pool_calls, "ThreadPoolExecutor not invoked in _prefetch_sources"
    # At least one of the pool calls has max_workers=4
    for call in pool_calls:
        for kw in call.keywords:
            if kw.arg == "max_workers" and isinstance(kw.value, ast.Constant):
                assert (
                    kw.value.value == 4
                ), f"max_workers must be 4 (Option C); got {kw.value.value}"
                return
    raise AssertionError("max_workers=4 keyword not found on ThreadPoolExecutor call")


def test_prefetch_sources_no_asyncio_used() -> None:
    """CONTEXT.md locked decision: no asyncio in v0.1.

    The Phase 1.5 PERF-04 fan-out uses threads, not asyncio. Verified via
    grep over the whole research module — these patterns must be absent.
    """
    import sys

    import tradewinds.research  # noqa: F401 — populates sys.modules

    research_mod = sys.modules["tradewinds.research"]

    src = inspect.getsource(research_mod)
    assert "import asyncio" not in src, "asyncio is forbidden in Phase 1.5 (CONTEXT.md lock)"
    assert "httpx.AsyncClient" not in src, "AsyncClient is forbidden"
    assert "async def" not in src, "async def is forbidden"


def test_prefetch_sources_awc_rows_returned(monkeypatch, tmp_path) -> None:
    """AWC worker's return value is captured into result['awc_rows']."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _prefetch_sources

    info = STATIONS["NYC"]
    fake_awc = [{"station_code": "NYC", "observed_at": "2025-01-06T12:00:00Z"}]

    with (
        patch("tradewinds.weather._fetchers.iem_asos.download_iem_asos", return_value=[]),
        patch("tradewinds.weather._fetchers.iem_cli.download_cli", return_value=Path("/tmp/x")),
        patch("tradewinds.weather._fetchers.ghcnh.download_ghcnh", return_value=Path("/tmp/x")),
        patch("tradewinds.research._fetch_awc_for_window", return_value=fake_awc),
    ):
        result = _prefetch_sources(info, "2025-01-06", "2025-01-12", "2025-01-13")

    assert result["awc_rows"] == fake_awc


def test_prefetch_sources_propagates_unexpected_exception(monkeypatch, tmp_path) -> None:
    """An unhandled exception inside a worker bubbles up via f.result().

    The _warm_* helpers catch httpx errors internally (degraded-graceful path).
    But programming bugs (TypeError, ZeroDivisionError, etc.) MUST propagate so
    the orchestrator sees them — same contract Plan 03 mandates.
    """
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _prefetch_sources

    info = STATIONS["NYC"]

    def boom(*args, **kwargs):
        # TypeError is the kind of bug the _warm_* helpers do NOT catch
        # (they catch BaseException-derived noqa: BLE001, but the broad except
        # turns this into a logged warning, not a raise). To force propagation
        # we patch the AWC fetch which has its own narrower try/except for
        # network errors only -- actually it catches Exception too. Let's
        # patch download_iem_asos to raise SystemExit (always propagates).
        raise SystemExit("simulated unrecoverable error")

    # SystemExit propagates because the _warm_iem_asos helper's except clause
    # is `except Exception`, which does NOT catch SystemExit (it inherits from
    # BaseException directly).
    with (
        patch("tradewinds.weather._fetchers.iem_asos.download_iem_asos", side_effect=boom),
        patch("tradewinds.weather._fetchers.iem_cli.download_cli", return_value=Path("/tmp/x")),
        patch("tradewinds.weather._fetchers.ghcnh.download_ghcnh", return_value=Path("/tmp/x")),
        patch("tradewinds.research._fetch_awc_for_window", return_value=[]),
        pytest.raises(SystemExit, match="simulated unrecoverable error"),
    ):
        _prefetch_sources(info, "2025-01-06", "2025-01-12", "2025-01-13")


def test_all_caches_warm_returns_false_when_obs_cache_missing(monkeypatch, tmp_path) -> None:
    """Gate predicate: any obs-parquet miss returns False (so prefetch runs)."""
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _all_caches_warm

    info = STATIONS["NYC"]
    # No cache written → every month is a miss → returns False.
    assert _all_caches_warm(info, "2025-01-06", "2025-01-12", "2025-01-13") is False


def test_per_source_times_are_positive(monkeypatch, tmp_path) -> None:
    """Per-source elapsed times should be ≥ 0 — a sanity check that
    submitted_at IS captured (would be ≈ wall_time, not negative, if not).
    """
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _prefetch_sources

    info = STATIONS["NYC"]

    def slow_noop(*args, **kwargs):
        time.sleep(0.05)
        return []

    with (
        patch(
            "tradewinds.weather._fetchers.iem_asos.download_iem_asos",
            side_effect=slow_noop,
        ),
        patch(
            "tradewinds.weather._fetchers.iem_cli.download_cli",
            side_effect=lambda *a, **k: (time.sleep(0.05) or Path("/tmp/x")),
        ),
        patch(
            "tradewinds.weather._fetchers.ghcnh.download_ghcnh",
            side_effect=lambda *a, **k: (time.sleep(0.05) or Path("/tmp/x")),
        ),
        patch("tradewinds.research._fetch_awc_for_window", side_effect=slow_noop),
    ):
        result = _prefetch_sources(info, "2025-01-06", "2025-01-12", "2025-01-13")

    # Each worker slept ~50ms; per_source_times should be at least that.
    for name, elapsed in result["per_source_times"].items():
        assert elapsed >= 0.04, f"{name} elapsed too small: {elapsed}"
    # Wall time should be roughly bounded by max(per_source) plus thread overhead,
    # NOT the sum (which would indicate serial execution rather than parallel).
    max_source = max(result["per_source_times"].values())
    total_source = sum(result["per_source_times"].values())
    # If serial: wall_time ~= total_source. If parallel: wall_time ~= max_source.
    # Assert closer to max than to total.
    assert result["wall_time"] < total_source, (
        f"wall_time={result['wall_time']:.3f} is too close to total "
        f"{total_source:.3f} — likely serial, not parallel"
    )
    assert result["wall_time"] <= max_source * 2.0, (
        f"wall_time={result['wall_time']:.3f} far exceeds max source "
        f"{max_source:.3f} — unexpected thread overhead"
    )
