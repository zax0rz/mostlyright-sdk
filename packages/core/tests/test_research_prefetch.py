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
    """The 4 named workers all appear in per_source_times.

    Uses a query window inside the 168h AWC lookback (relative to fake ``now``)
    so the AWC worker fires. Past-year IEM/CLI/GHCNh fire because the
    current-UTC-year skip (post iter-1 fix) only activates for year >= now.year.
    """
    from datetime import UTC, datetime

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _prefetch_sources

    info = STATIONS["NYC"]
    # Fake now = 2024-01-15; query 2024-01-08..2024-01-15 is well inside 168h.
    fake_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

    # Stub all 4 worker network functions to be no-ops/quick returns. The
    # spike's job here is to verify the ThreadPoolExecutor wiring, not the
    # fetchers themselves.
    with (
        patch("tradewinds.weather._fetchers.iem_asos.download_iem_asos", return_value=[]),
        patch("tradewinds.weather._fetchers.iem_cli.download_cli", return_value=Path("/tmp/x")),
        patch("tradewinds.weather._fetchers.ghcnh.download_ghcnh", return_value=Path("/tmp/x")),
        patch("tradewinds.research._fetch_awc_for_window", return_value=[]),
    ):
        result = _prefetch_sources(info, "2023-12-25", "2024-01-05", "2024-01-06", now=fake_now)

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
    and the ``as_completed`` body uses ``submitted_at[name]`` (NOT a freshly
    captured t0) for per-source timing.

    The Pitfall 6 anti-pattern is::

        for f in as_completed(futures):
            t0 = time.monotonic()
            f.result()  # blocks until DONE — inflates time for first iterated
            per_source_times[name] = time.monotonic() - t0  # WRONG

    The correct pattern (which we assert is present + absent for the bug)::

        for name, fn in ...:
            f = ex.submit(fn)
            submitted_at[name] = time.monotonic()  # immediately after submit
            ...

        for f in as_completed(futures):
            per_source_times[name] = time.monotonic() - submitted_at[name]

    Strengthens iter-1 review (codex HIGH-3 / architect HIGH-6): the original
    AST scan accepted ANY ``For`` body where ``ex.submit`` and ``submitted_at``
    coexisted, breaking on the first match. This version requires (a) the
    correct submission shape AND (b) absence of the t0/result/elapsed
    anti-pattern inside any ``as_completed`` loop body AND (c) the
    as_completed body references ``submitted_at[`` for its timing.
    """
    import sys

    import tradewinds.research  # noqa: F401 — populates sys.modules

    research_mod = sys.modules["tradewinds.research"]

    src = inspect.getsource(research_mod._prefetch_sources)
    tree = ast.parse(src)

    # (a) Locate the submit loop and assert submit-then-capture adjacency in
    # every For body that contains an ex.submit call (defends against the
    # "second broken loop bypasses the test" weakness).
    submit_loops_found = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            body_strs = [ast.unparse(stmt) for stmt in node.body]
            joined = "\n".join(body_strs)
            if "ex.submit" not in joined:
                continue
            submit_loops_found += 1
            # Same body MUST also have submitted_at[ assignment, immediately
            # after submit() returns.
            assert (
                "submitted_at[" in joined
            ), "submit loop missing submitted_at[name] capture — Pitfall 6 anti-pattern"
            submit_idx = next(i for i, s in enumerate(body_strs) if "ex.submit" in s)
            cap_idx = next(i for i, s in enumerate(body_strs) if "submitted_at[" in s)
            assert submit_idx < cap_idx, (
                "submitted_at[name] must be assigned AFTER ex.submit() — "
                "Pitfall 6 anti-pattern detected"
            )
    assert submit_loops_found >= 1, "no ex.submit loop found in _prefetch_sources"

    # (b)+(c) Walk every "for ... in as_completed(...)" body and assert:
    #   - NO ``t0 = time.monotonic()`` immediately followed by ``f.result()``
    #     and then ``per_source_times[...] = time.monotonic() - t0``
    #   - per_source_times[...] timing references submitted_at[...]
    as_completed_loops_found = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        iter_src = ast.unparse(node.iter)
        if "as_completed" not in iter_src:
            continue
        as_completed_loops_found += 1
        body_strs = [ast.unparse(stmt) for stmt in node.body]
        joined = "\n".join(body_strs)
        # Defends against the bug-preserving refactor codex flagged: a t0
        # captured inside the as_completed loop measures wrong wall time.
        assert (
            "t0 = time.monotonic()" not in joined
        ), "Pitfall 6 anti-pattern detected: t0 captured inside as_completed body"
        # Defends against the architect's HIGH-6 weakness: ensure the timing
        # arithmetic actually reads submitted_at (not a local var).
        assert "submitted_at[" in joined, (
            "as_completed body does not reference submitted_at[name] for timing — "
            "Pitfall 6 fix incomplete"
        )
        # The per_source_times assignment must use submitted_at directly.
        per_source_lines = [s for s in body_strs if "per_source_times[" in s]
        assert per_source_lines, "per_source_times[name] not assigned in as_completed body"
        assert any(
            "submitted_at[" in s for s in per_source_lines
        ), "per_source_times[name] assignment does not use submitted_at[name]"
    assert as_completed_loops_found >= 1, "no as_completed loop found in _prefetch_sources"


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
    from datetime import UTC, datetime

    fake_awc = [{"station_code": "NYC", "observed_at": "2024-01-06T12:00:00Z"}]
    # Fake now inside the AWC 168h lookback so the AWC worker fires.
    fake_now = datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC)

    with (
        patch("tradewinds.weather._fetchers.iem_asos.download_iem_asos", return_value=[]),
        patch("tradewinds.weather._fetchers.iem_cli.download_cli", return_value=Path("/tmp/x")),
        patch("tradewinds.weather._fetchers.ghcnh.download_ghcnh", return_value=Path("/tmp/x")),
        patch("tradewinds.research._fetch_awc_for_window", return_value=fake_awc),
    ):
        result = _prefetch_sources(info, "2023-12-25", "2024-01-05", "2024-01-06", now=fake_now)

    assert result["awc_rows"] == fake_awc


def test_prefetch_sources_propagates_unexpected_exception(monkeypatch, tmp_path) -> None:
    """A non-network exception inside a worker bubbles up via f.result().

    The _warm_* helpers catch only the recoverable network/disk exception
    tuple ``(httpx.HTTPStatusError, httpx.RequestError, OSError)``. Plain
    ``RuntimeError`` (a programming bug) MUST propagate — codex/architect
    iter-1 HIGH-1/2.

    Critically: we use ``RuntimeError`` here, NOT ``SystemExit`` (which
    propagates regardless of ``except Exception:`` because it derives from
    ``BaseException``). A regression that broadens the except clause back to
    ``Exception`` MUST cause this test to fail.

    Uses ``from_date=2024-01-01, to_date=2024-12-31`` (a year strictly past
    UTC given today=2026-05-23) so the _warm_iem_asos worker actually invokes
    its inner ``download_iem_asos`` — the post-iter-1 fix skips the prefetch
    for the current UTC year, which would otherwise mask the test.
    """
    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _prefetch_sources

    info = STATIONS["NYC"]

    def boom(*args, **kwargs):
        raise RuntimeError("simulated programming bug")

    with (
        patch("tradewinds.weather._fetchers.iem_asos.download_iem_asos", side_effect=boom),
        patch("tradewinds.weather._fetchers.iem_cli.download_cli", return_value=Path("/tmp/x")),
        patch("tradewinds.weather._fetchers.ghcnh.download_ghcnh", return_value=Path("/tmp/x")),
        patch("tradewinds.research._fetch_awc_for_window", return_value=[]),
        pytest.raises(RuntimeError, match="simulated programming bug"),
    ):
        _prefetch_sources(info, "2024-01-01", "2024-12-31", "2025-01-01")


def test_prefetch_sources_swallows_network_errors(monkeypatch, tmp_path) -> None:
    """The _warm_* helpers catch the recoverable network tuple
    ``(httpx.HTTPStatusError, httpx.RequestError, OSError)`` and degrade
    gracefully — the lazy sequential path retries per its own predicate.

    Counterpart to test_prefetch_sources_propagates_unexpected_exception:
    together they pin down the EXACT exception-catch contract.
    """
    import httpx

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path / "cache"))
    from tradewinds._internal._stations import STATIONS
    from tradewinds.research import _prefetch_sources

    info = STATIONS["NYC"]

    def http_500(*args, **kwargs):
        # Mimic the wrapped HTTPStatusError that the fetchers re-raise.
        request = httpx.Request("GET", "https://example.test/x")
        response = httpx.Response(500, text="upstream flaked", request=request)
        raise httpx.HTTPStatusError("upstream flaked", request=request, response=response)

    with (
        patch("tradewinds.weather._fetchers.iem_asos.download_iem_asos", side_effect=http_500),
        patch("tradewinds.weather._fetchers.iem_cli.download_cli", return_value=Path("/tmp/x")),
        patch("tradewinds.weather._fetchers.ghcnh.download_ghcnh", return_value=Path("/tmp/x")),
        patch("tradewinds.research._fetch_awc_for_window", return_value=[]),
    ):
        # HTTPStatusError IS caught and logged; the call returns normally.
        result = _prefetch_sources(info, "2024-01-01", "2024-12-31", "2025-01-01")
    assert set(result["per_source_times"].keys()) == {
        "iem.archive",
        "awc.live",
        "ghcnh.archive",
        "cli.archive",
    }


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
            side_effect=lambda *a, **k: time.sleep(0.05) or Path("/tmp/x"),
        ),
        patch(
            "tradewinds.weather._fetchers.ghcnh.download_ghcnh",
            side_effect=lambda *a, **k: time.sleep(0.05) or Path("/tmp/x"),
        ),
        patch("tradewinds.research._fetch_awc_for_window", side_effect=slow_noop),
    ):
        from datetime import UTC, datetime

        # Fake now inside the AWC 168h lookback so all 4 workers fire and
        # the per-source timings sum to ~0.2s (4 x 50ms) serially or ~0.05s
        # in parallel.
        fake_now = datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC)
        result = _prefetch_sources(info, "2023-12-25", "2024-01-05", "2024-01-06", now=fake_now)

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
