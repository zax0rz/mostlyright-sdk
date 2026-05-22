---
phase: 01-5-fetcher-optimization-cross-source-parallelism
plan: 02
type: execute
wave: 1
duration: Day 4.5–5 (~3-4h Claude execution + ~50 min live spike wall time)
waves: 1
depends_on: []      # Independent of Plan 01 (different files: spike/ + .planning/research/). Same wave: both run after Phase 1 merge.
branch_strategy: per-wave; one sub-branch off `merged-vision` (`phase-1-5/wave-1/source-limits-spike`); 3-reviewer panel (codex high + python-architect + security); merges to `merged-vision` independently of Plan 01 because there is zero file-overlap; SOURCE-LIMITS.md output becomes prerequisite reading for Plan 03
requirements:
  - PERF-05
autonomous: false   # The actual spike run hits live APIs — `@pytest.mark.live` semantics — Claude executes the scripts but the user reviews SOURCE-LIMITS.md before merging
files_modified:
  - spike/source_limits/__init__.py                                           # NEW (empty marker)
  - spike/source_limits/README.md                                             # NEW (how to run + interpret)
  - spike/source_limits/_common.py                                            # NEW (shared timing/aggregation utils)
  - spike/source_limits/awc_concurrent.py                                     # NEW (AWC live METAR concurrent spike)
  - spike/source_limits/ghcnh_concurrent.py                                   # NEW (GHCNh static-PSV concurrent spike)
  - spike/source_limits/iem_shared_ip_spike.py                                # NEW (CRITICAL: validates Pitfall 5 IEM-ASOS+IEM-CLI shared-IP assumption)
  - .planning/research/SOURCE-LIMITS.md                                       # NEW (spike output document)
must_haves:
  truths:
    - "`.planning/research/SOURCE-LIMITS.md` exists with one section per source: AWC, GHCNh, IEM (split: ASOS and CLI sub-sections + a 'Shared-IP test' sub-section)."
    - "For each source, SOURCE-LIMITS.md documents: max concurrent connections tested {1, 2, 4, 8, 16}, p50/p95/p99 response time per N, 429 count per N, 5xx count per N, mean response body size in bytes, response body size for the empirically-largest window the API permits (1-yr / 5-yr / 168-hr per source quirk)."
    - "SOURCE-LIMITS.md explicitly states whether IEM `asos.py` and `cli.py` share a per-IP throttle budget (Pitfall 5 / Assumption A3): empirically verified by firing 2 concurrent threads — one against asos.py, one against cli.py — and observing whether 503 rate rises vs single-source baseline."
    - "SOURCE-LIMITS.md recommends one of three IEM-sharing strategies for Plan 03 PERF-04 design: Option A (per-IEM threading.Lock), Option B (max_workers=3 with serialized IEM ASOS+CLI), or Option C (no-op — empirical evidence shows 2 concurrent IEM threads tolerate the 1 req/sec/IP throttle). The recommendation is grounded in actual 503-count data, not a guess."
    - "`spike/source_limits/awc_concurrent.py` accepts an N argument (concurrent thread count) and emits a markdown row to stdout pasteable into SOURCE-LIMITS.md."
    - "Spike scripts use ONLY existing tradewinds httpx + concurrent.futures patterns — no new top-level deps."
    - "Spike scripts are NOT under `tests/` (per CONTEXT.md locked decision — they are planning/research artifacts, not test code; not subject to `@pytest.mark.live`)."
    - "The shared `_common.py` utility provides one place to compute p50/p95/p99 from a list of response-time samples and one place to count HTTP status code distribution — DRY for the three spike scripts."
    - "spike/source_limits/README.md documents exact invocation per script (`uv run python spike/source_limits/awc_concurrent.py --n 4 --repeats 5`) AND that the run is by-definition live (no recorded fixtures; the spike characterizes real endpoint behavior)."
  artifacts:
    - path: spike/source_limits/_common.py
      provides: "Timing + percentile + status-code-distribution helpers shared by the 3 spike scripts"
      contains: "def percentile"
      min_lines: 60
    - path: spike/source_limits/awc_concurrent.py
      provides: "Fires N concurrent AWC METAR GETs across distinct stations; reports p50/p95/p99 + status distribution + body size"
      contains: "def run_spike"
      min_lines: 80
    - path: spike/source_limits/ghcnh_concurrent.py
      provides: "Fires N concurrent GHCNh PSV-archive GETs across distinct station-years; reports same metrics"
      contains: "def run_spike"
      min_lines: 80
    - path: spike/source_limits/iem_shared_ip_spike.py
      provides: "Pitfall 5 / Assumption A3 verification: fires 2 concurrent IEM threads (one ASOS, one CLI) each at 1 req/sec; counts 503s vs single-source baseline"
      contains: "def measure_shared_ip"
      min_lines: 80
    - path: .planning/research/SOURCE-LIMITS.md
      provides: "Spike output: per-source max concurrent, response sizes, recommended PERF-04 IEM-sharing strategy"
      contains: "## IEM shared-IP test"
      min_lines: 100
    - path: spike/source_limits/README.md
      provides: "How to run each spike + how to interpret SOURCE-LIMITS.md + when to re-run"
      min_lines: 40
  key_links:
    - from: spike/source_limits/iem_shared_ip_spike.py
      to: .planning/research/SOURCE-LIMITS.md (## IEM shared-IP test section)
      via: "stdout markdown table pasted into SOURCE-LIMITS.md; the test result decides Plan 03 PERF-04 IEM-sharing strategy (A/B/C)"
      pattern: "503 count"
    - from: .planning/research/SOURCE-LIMITS.md
      to: PLAN-03-cross-source-parallelism.md (Task 3.1 read_first)
      via: "Plan 03 read_first explicitly cites SOURCE-LIMITS.md; the IEM-sharing-strategy recommendation is INPUT to Plan 03's `research.py` design"
    - from: spike/source_limits/*.py
      to: tradewinds._internal._http (post-PERF-03)
      via: "Spike scripts import the same `download_with_retry` + `HTTP_TIMEOUT` constants Plan 01 ships, so the spike measurements characterize the SAME timeout behavior that production code will have"
      pattern: "from tradewinds._internal._http import"
---

<objective>
Empirically characterize concurrent-request behavior of the three sources tradewinds will fan out in PERF-04 (AWC, GHCNh, IEM × {ASOS, CLI}). No published rate limits exist for AWC or NCEI GHCNh, and IEM published a 1-sec per-IP throttle as of 2026-04-21 — the spike is the only path to evidence-based PERF-04 design.

**The four questions this spike answers:**

1. **AWC concurrent tolerance** — does AWC's `/api/data/` endpoint tolerate 4 concurrent GET requests across distinct stations? At 8? At 16? What's the 429-rate inflection point?
2. **GHCNh concurrent tolerance** — same question for the GHCNh static-PSV CDN-distributed archive endpoint. (Static-PSV suggests high tolerance, but empirical verification is cheap.)
3. **CRITICAL — IEM shared-IP throttle behavior (Pitfall 5 / Assumption A3)** — does the 1-sec per-IP throttle at `mesonet.agron.iastate.edu` apply to ASOS + CLI as a SHARED budget (so two concurrent 1-req/sec threads = 2 req/sec → 503s) or do ASOS and CLI have separate per-endpoint budgets? PERF-04's `max_workers=4` design assumes the answer dictates Plan 03's IEM-sharing strategy.
4. **Response-body-size measurements** — for each source, what's the byte-size of the largest API-permitted single request (1-year IEM ASOS, 1-year GHCNh PSV, 7-day AWC live, 1-year IEM CLI)? Feeds into Plan 01's `HTTP_TIMEOUT=60s` validation.

**The spike produces THREE artifacts:**

1. `.planning/research/SOURCE-LIMITS.md` — the canonical output document, structured so PERF-04 planners (Plan 03) cite specific tables.
2. `spike/source_limits/*.py` — three executable scripts, version-controlled, re-runnable in v0.2 with one command per source.
3. `spike/source_limits/README.md` — operator's manual.

**Why this plan runs BEFORE Plan 03 (PERF-04):** Per RESEARCH.md and CONTEXT.md "IEM rate-limit risk added 2026-05-22", three Plan 03 design choices depend on the spike output: (A) per-IEM lock in `research.py`, (B) `max_workers=3` with serialized IEM ASOS+CLI, or (C) no-op (4-way fan-out as currently sketched). The choice is empirical, not a guess.

**Why this plan runs in PARALLEL with Plan 01 (PERF-01/02/03):** The plans modify zero overlapping files. Plan 01 modifies `_fetchers/iem_asos.py` + `_internal/_http.py`; Plan 02 modifies `spike/source_limits/` + `.planning/research/`. CONTEXT.md notes Plan 02 "could run in parallel with Plan 1 but recommend serial for review-panel attention efficiency" — the recommendation is soft; here we treat them as parallel sub-branches off `merged-vision` in the same wave to compress wall-clock time, with the 3-reviewer panel running on each sub-branch independently.

**Out of scope:** Adaptive rate-limiting code (v0.2). Cross-station parallelism (v0.2). Polymarket / Kalshi (markets package). The spike is DESCRIPTIVE (what happens at N=8?), not PRESCRIPTIVE (build a retry strategy).
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md
@.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md
@./CLAUDE.md
</execution_context>

<phase_summary>

**Goal:** Run a one-shot empirical spike for AWC, GHCNh, and IEM (the critical shared-IP question) and document everything PERF-04 needs to know in `.planning/research/SOURCE-LIMITS.md`.

**Branch:** `phase-1-5/wave-1/source-limits-spike` off `merged-vision`. Independent of Plan 01's branch — zero file overlap.

**Atomic commit boundaries:**
- Task 2.1 (spike infra) → 1 commit
- Task 2.2 (AWC + GHCNh spikes) → 1 commit
- Task 2.3 (IEM shared-IP spike — the critical one for PERF-04) → 1 commit
- Task 2.4 (run spikes live + author SOURCE-LIMITS.md) → 1 commit

**Spike duration (CONTEXT.md / RESEARCH.md): ~50 minutes total wall time** (mostly idle on politeness pauses). The Claude execution of authoring + reviewing the SOURCE-LIMITS.md output is ~1-2h after the scripts finish.

**Live API constraint:** The spike scripts hit real public APIs. Per CLAUDE.md, `@pytest.mark.live` excludes from CI; spike scripts are NOT pytest tests at all (they are stand-alone CLI scripts under `spike/`). No CI mocking — but the user inspects the SOURCE-LIMITS.md output before merge.

**3-reviewer panel applies even though no production code changes:** SOURCE-LIMITS.md contains the recommendation that becomes Plan 03's design input — getting the empirical interpretation wrong (e.g. recommending Option C when the data says Option A) is a CRITICAL Plan 03 bug seeded here. Codex `high` + python-architect (interpretation sanity) + security (HTTPS endpoints; no secrets; but: the spike fires N=16 concurrent against public endpoints — confirm this doesn't violate any endpoint's published ToS).

</phase_summary>

<tasks>

<task type="auto">
  <name>Task 2.1: Scaffold `spike/source_limits/` with shared `_common.py` utilities</name>
  <files>spike/source_limits/__init__.py, spike/source_limits/_common.py, spike/source_limits/README.md</files>
  <implements>PERF-05 scaffolding — DRY infra for the 3 spike scripts</implements>
  <read_first>
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md (Specifics section — spike scope; locked decisions — "Rate-limit spike documentation lives in `.planning/research/`")
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 509-543 — rate-limit characterization methodology; line 528-532 — metrics worth capturing per N)
    - packages/core/src/tradewinds/_internal/_http.py (current state — after Plan 01 merges, HTTP_TIMEOUT will be 60s; spike scripts must accommodate either value at run time)
    - packages/weather/src/tradewinds/weather/_fetchers/awc.py (read to see the AWC URL pattern + the politeness pause)
    - packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py (read to see the GHCNh URL pattern)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py (read to see the IEM asos.py URL + 1-sec politeness — IEM_POLITE_DELAY)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_cli.py (read to see the IEM cli.py URL + same politeness)
    - CLAUDE.md (TDD mandatory — spike scripts are utility code; they are NOT covered by 80% coverage rule because they are NOT in `tradewinds.*` namespace, but the `_common.py` utility math (percentile, status-code-count) IS testable and SHOULD have a tiny pytest module)
  </read_first>
  <action>
    Step 1 — Create `spike/source_limits/__init__.py` (empty marker file).

    Step 2 — Create `spike/source_limits/_common.py` with these utilities (designed for cut-and-paste into all 3 spike scripts):

    ```python
    """Shared timing + status-code + body-size helpers for source_limits spikes.

    Not a test module. Not under tradewinds.* namespace. Runs as stand-alone CLI.
    """
    from __future__ import annotations

    import time
    import statistics
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from dataclasses import dataclass, field
    from typing import Callable


    @dataclass
    class RequestResult:
        url: str
        status_code: int
        elapsed_s: float
        body_size_bytes: int
        error: str | None = None


    @dataclass
    class SpikeResult:
        n: int
        repeats: int
        per_request: list[RequestResult] = field(default_factory=list)

        @property
        def status_distribution(self) -> dict[int, int]:
            return dict(Counter(r.status_code for r in self.per_request if r.error is None))

        @property
        def error_count(self) -> int:
            return sum(1 for r in self.per_request if r.error is not None)

        @property
        def elapsed_p50(self) -> float:
            elapsed = [r.elapsed_s for r in self.per_request if r.error is None]
            return statistics.median(elapsed) if elapsed else float("nan")

        @property
        def elapsed_p95(self) -> float:
            return percentile([r.elapsed_s for r in self.per_request if r.error is None], 95)

        @property
        def elapsed_p99(self) -> float:
            return percentile([r.elapsed_s for r in self.per_request if r.error is None], 99)

        @property
        def mean_body_size(self) -> float:
            sizes = [r.body_size_bytes for r in self.per_request if r.error is None]
            return statistics.mean(sizes) if sizes else float("nan")

        @property
        def max_body_size(self) -> int:
            sizes = [r.body_size_bytes for r in self.per_request if r.error is None]
            return max(sizes) if sizes else 0


    def percentile(values: list[float], p: int) -> float:
        if not values:
            return float("nan")
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * (p / 100)
        f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
        return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


    def fan_out(
        urls: list[str],
        max_workers: int,
        fetch: Callable[[str], RequestResult],
    ) -> list[RequestResult]:
        """Run `fetch(url)` for each URL with ThreadPoolExecutor(max_workers)."""
        results: list[RequestResult] = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(fetch, u): u for u in urls}
            for f in as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as exc:  # noqa: BLE001
                    results.append(RequestResult(url=futures[f], status_code=0, elapsed_s=0.0, body_size_bytes=0, error=str(exc)))
        return results


    def render_markdown_row(label: str, result: SpikeResult) -> str:
        """One markdown table row pasteable into SOURCE-LIMITS.md."""
        return (
            f"| {label} | {result.n} | {result.elapsed_p50:.2f} | {result.elapsed_p95:.2f} "
            f"| {result.elapsed_p99:.2f} | {result.status_distribution} "
            f"| {result.mean_body_size:.0f} | {result.max_body_size} | {result.error_count} |"
        )
    ```

    Step 3 — Add a tiny pytest in `spike/source_limits/test_common.py` (yes, inside `spike/`, NOT inside `tests/`; this is a self-contained utility test for the math):
    ```python
    from spike.source_limits._common import percentile

    def test_percentile_p50_is_median():
        assert percentile([1, 2, 3, 4, 5], 50) == 3.0

    def test_percentile_p99_takes_top_value():
        assert percentile([1.0] * 99 + [100.0], 99) > 50.0  # heavy upper tail

    def test_percentile_empty_returns_nan():
        import math
        assert math.isnan(percentile([], 95))
    ```

    Run `uv run pytest spike/source_limits/test_common.py -x -v` — MUST pass.

    Step 4 — Author `spike/source_limits/README.md`:
    ```markdown
    # spike/source_limits

    One-shot empirical characterization of AWC, GHCNh, IEM concurrent-request behavior.
    Output: `.planning/research/SOURCE-LIMITS.md`.

    ## Why these are spikes, not tests

    These scripts hit real public APIs and intentionally fire N=16 concurrent requests.
    Tradewinds policy (CLAUDE.md): tests under `tests/` use recorded fixtures via
    pytest-recording; live tests are tagged `@pytest.mark.live` and run pre-publish.
    These scripts are neither — they characterize endpoint behavior empirically and
    persist their output as a planning artifact. They are kept in version control so
    re-validation in v0.2 is one command.

    ## How to run

    ```bash
    # Total wall time ~50 min across all three; mostly idle on politeness pauses.
    uv run python spike/source_limits/awc_concurrent.py --n-levels 1,2,4,8,16 --repeats 5
    uv run python spike/source_limits/ghcnh_concurrent.py --n-levels 1,2,4,8,16 --repeats 5
    uv run python spike/source_limits/iem_shared_ip_spike.py --repeats 10
    ```

    Each script prints a markdown table to stdout that you paste into the
    corresponding section of `.planning/research/SOURCE-LIMITS.md`.

    ## When to re-run

    - v0.2 milestone — confirm rate limits haven't tightened since spring 2026.
    - After any IEM/AWC/NCEI published policy change.
    - When PERF-04 wall-time regresses unexpectedly in CI.
    ```

    Step 5 — Commit: `feat(phase-1-5): scaffold spike/source_limits with shared timing utilities (PERF-05)`.
  </action>
  <verify>
    <automated>uv run pytest spike/source_limits/test_common.py -x -v && uv run ruff check spike/source_limits/</automated>
  </verify>
  <acceptance_criteria>
    - `test -d spike/source_limits/` returns 0
    - `test -f spike/source_limits/__init__.py` returns 0
    - `test -f spike/source_limits/_common.py` returns 0
    - `test -f spike/source_limits/README.md` returns 0
    - `grep -c "def percentile" spike/source_limits/_common.py` returns 1
    - `grep -c "class SpikeResult" spike/source_limits/_common.py` returns 1
    - `grep -c "def fan_out" spike/source_limits/_common.py` returns 1
    - `grep -c "def render_markdown_row" spike/source_limits/_common.py` returns 1
    - `uv run pytest spike/source_limits/test_common.py -x -v` exits 0 with 3 passed
    - `uv run ruff check spike/source_limits/` returns 0 errors
    - `grep "## How to run" spike/source_limits/README.md` returns non-empty
  </acceptance_criteria>
  <done>
    `spike/source_limits/` package exists with `_common.py`, README, and tested percentile/fan-out/render utilities. Ready for spike scripts to import.
  </done>
</task>

<task type="auto">
  <name>Task 2.2: Author AWC + GHCNh concurrent-spike scripts</name>
  <files>spike/source_limits/awc_concurrent.py, spike/source_limits/ghcnh_concurrent.py</files>
  <implements>PERF-05 — AWC + GHCNh concurrent tolerance characterization</implements>
  <read_first>
    - spike/source_limits/_common.py (from Task 2.1 — the utilities you'll import)
    - packages/weather/src/tradewinds/weather/_fetchers/awc.py (the exact URL pattern + politeness pause used in production; the spike should use the SAME URL pattern to characterize realistic behavior)
    - packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py (same — exact GHCNh URL pattern)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 517-543 — spike methodology recommendation; lines 528-543 — response-size methodology per source; AWC live: 7-day max; GHCNh: one PSV per station-year)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md (Specifics — exact filename targets for spike scripts)
  </read_first>
  <action>
    Step 1 — Author `spike/source_limits/awc_concurrent.py`. Skeleton:

    ```python
    """AWC concurrent-request spike.

    Fires N concurrent GET to the AWC METAR endpoint for distinct stations.
    Measures p50/p95/p99 + status-code distribution + body size.

    Output: markdown table to stdout, paste into SOURCE-LIMITS.md § AWC.

    Run: uv run python spike/source_limits/awc_concurrent.py --n-levels 1,2,4,8,16 --repeats 5
    """
    from __future__ import annotations

    import argparse
    import time
    import httpx
    from spike.source_limits._common import (
        RequestResult, SpikeResult, fan_out, render_markdown_row,
    )

    # Same URL pattern as packages/weather/src/tradewinds/weather/_fetchers/awc.py
    AWC_METAR_URL = "https://aviationweather.gov/api/data/metar?ids={station}&format=json&hours=168"

    # 20 distinct stations — large enough for N=16 without repeats
    SPIKE_STATIONS = [
        "KNYC", "KLAX", "KMIA", "KMDW", "KORD", "KATL", "KDEN", "KBOS",
        "KSFO", "KSEA", "KAUS", "KIAD", "KDFW", "KPHX", "KMCO", "KMSP",
        "KCLE", "KDTW", "KLAS", "KPDX",
    ]


    def fetch_one(url: str) -> RequestResult:
        t0 = time.monotonic()
        try:
            r = httpx.get(url, timeout=60.0)  # match Plan 01 HTTP_TIMEOUT
            elapsed = time.monotonic() - t0
            return RequestResult(
                url=url,
                status_code=r.status_code,
                elapsed_s=elapsed,
                body_size_bytes=len(r.content),
            )
        except Exception as exc:  # noqa: BLE001
            return RequestResult(
                url=url,
                status_code=0,
                elapsed_s=time.monotonic() - t0,
                body_size_bytes=0,
                error=str(exc),
            )


    def run_spike(n: int, repeats: int) -> SpikeResult:
        result = SpikeResult(n=n, repeats=repeats)
        for _ in range(repeats):
            urls = [AWC_METAR_URL.format(station=s) for s in SPIKE_STATIONS[:n]]
            batch = fan_out(urls, max_workers=n, fetch=fetch_one)
            result.per_request.extend(batch)
        return result


    def main() -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--n-levels", default="1,2,4,8,16", help="comma-separated N values")
        parser.add_argument("--repeats", type=int, default=5)
        args = parser.parse_args()

        print("## AWC METAR live endpoint (`/api/data/metar`)")
        print()
        print("| N (concurrent) | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | error_count |")
        print("|---|---|---|---|---|---|---|---|")
        for n in [int(x) for x in args.n_levels.split(",")]:
            r = run_spike(n, args.repeats)
            print(render_markdown_row(f"N={n}", r))
            print(f"  (debug: {r.repeats} repeats × {n} = {r.repeats * n} requests; error_count={r.error_count})", flush=True)


    if __name__ == "__main__":
        main()
    ```

    Step 2 — Author `spike/source_limits/ghcnh_concurrent.py`. Mirror structure to AWC but:
    - URL pattern: `https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/{year}/psv/GHCNh_{station_full}_{year}.psv` (verify exact pattern by reading the production fetcher).
    - Station-year tuples: combine 4-5 distinct stations × 4-5 distinct years to get 16 distinct URLs without duplication. Use `SPIKE_STATIONS[:5]` × `range(2020, 2025)` = 25 distinct URLs (enough for N=16).
    - Note in docstring: GHCNh static-PSV is CDN-distributed; expect very high tolerance.

    Step 3 — Test BOTH scripts compile and accept `--help`:
    ```bash
    uv run python spike/source_limits/awc_concurrent.py --help
    uv run python spike/source_limits/ghcnh_concurrent.py --help
    ```
    Both must exit 0.

    Step 4 — Run a 1-shot smoke check with `--n-levels 1 --repeats 1` for both to verify they're live-runnable (this fires 1 real request to each endpoint — minimal load). Capture stdout but DO NOT commit those numbers — Task 2.4 runs the full spike. If either script errors at this minimal smoke load, fix before commit.

    Step 5 — `uv run ruff check --fix .` + `uv run ruff format .`. Commit: `feat(phase-1-5): spike scripts for AWC + GHCNh concurrent characterization (PERF-05)`.
  </action>
  <verify>
    <automated>uv run python spike/source_limits/awc_concurrent.py --help && uv run python spike/source_limits/ghcnh_concurrent.py --help && uv run ruff check spike/source_limits/</automated>
  </verify>
  <acceptance_criteria>
    - `test -f spike/source_limits/awc_concurrent.py` returns 0
    - `test -f spike/source_limits/ghcnh_concurrent.py` returns 0
    - `grep -c "def run_spike" spike/source_limits/awc_concurrent.py` returns 1
    - `grep -c "def run_spike" spike/source_limits/ghcnh_concurrent.py` returns 1
    - `grep "aviationweather.gov" spike/source_limits/awc_concurrent.py` returns non-empty
    - `grep "ncei.noaa.gov" spike/source_limits/ghcnh_concurrent.py` returns non-empty
    - `grep "timeout=60.0" spike/source_limits/awc_concurrent.py` returns non-empty (matches Plan 01 HTTP_TIMEOUT)
    - `uv run python spike/source_limits/awc_concurrent.py --help` exits 0
    - `uv run python spike/source_limits/ghcnh_concurrent.py --help` exits 0
    - `uv run ruff check spike/source_limits/` returns 0 errors
    - 1-request smoke for both endpoints succeeds (status 200) when run manually with `--n-levels 1 --repeats 1`
  </acceptance_criteria>
  <done>
    Two CLI-runnable spike scripts that emit pasteable markdown tables. Ready for Task 2.4 to run them under full N-sweep.
  </done>
</task>

<task type="auto">
  <name>Task 2.3: Author IEM shared-IP spike — the critical Pitfall 5 / Assumption A3 verifier</name>
  <files>spike/source_limits/iem_shared_ip_spike.py</files>
  <implements>PERF-05 — IEM `asos.py` vs `cli.py` shared-IP throttle verification (CRITICAL input to Plan 03)</implements>
  <read_first>
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 319-335 — Pitfall 5 with full mitigation options A/B/C; lines 612-616 — Assumption A3 explicit)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/CONTEXT.md ("IEM rate-limit risk added 2026-05-22" — three mitigation paths documented)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py (production IEM ASOS URL pattern + IEM_POLITE_DELAY = 1.0)
    - packages/weather/src/tradewinds/weather/_fetchers/iem_cli.py (production IEM CLI URL pattern + politeness pause)
    - spike/source_limits/_common.py (helpers to reuse)
  </read_first>
  <action>
    Step 1 — Author `spike/source_limits/iem_shared_ip_spike.py`. The structure:

    ```python
    """IEM shared-IP throttle spike — the Pitfall 5 / Assumption A3 verifier.

    Hypothesis: IEM 1-sec per-IP throttle (2026-04-21) at mesonet.agron.iastate.edu
    applies to BOTH asos.py and cli.py as a SHARED budget. If true, then a PERF-04
    design that fires concurrent IEM-ASOS + IEM-CLI threads (each sleeping 1s
    between requests) emits 2 req/sec to the same IP and triggers 503s.

    This spike tests the hypothesis directly:
      - Baseline: 1 IEM-ASOS thread, 10 requests, 1 sec/req. Count 503s.
      - Treatment: 1 IEM-ASOS + 1 IEM-CLI thread CONCURRENT, each 10 requests, each
        1 sec/req. Count 503s in each thread.

    If treatment 503 rate >> baseline 503 rate → SHARED-IP confirmed.
    If treatment 503 rate ≈ baseline → separate per-endpoint budgets.

    Output: markdown table + EXPLICIT recommendation for Plan 03 PERF-04 design.

    Run: uv run python spike/source_limits/iem_shared_ip_spike.py --repeats 10
    """
    from __future__ import annotations

    import argparse
    import threading
    import time
    import httpx
    from spike.source_limits._common import RequestResult, SpikeResult, render_markdown_row

    IEM_POLITE_DELAY = 1.0  # mirror production constant

    # Distinct stations for each thread to avoid station-cache collisions
    ASOS_STATIONS = ["KNYC", "KLAX", "KMIA", "KMDW", "KORD", "KATL", "KDEN", "KBOS", "KSFO", "KSEA"]
    CLI_STATIONS = ["KAUS", "KIAD", "KDFW", "KPHX", "KMCO", "KMSP", "KCLE", "KDTW", "KLAS", "KPDX"]

    # Same URL patterns as production fetchers; year=2024 for a stable historical window
    ASOS_URL = (
        "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
        "?station={station}&data=all&year1=2024&month1=1&day1=1"
        "&year2=2024&month2=1&day2=2&tz=Etc/UTC&format=onlycomma"
    )
    CLI_URL = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=CLI{station}"  # adjust per actual production pattern


    def serial_thread(urls: list[str], delay: float) -> SpikeResult:
        result = SpikeResult(n=1, repeats=len(urls))
        for url in urls:
            t0 = time.monotonic()
            try:
                r = httpx.get(url, timeout=60.0)
                result.per_request.append(RequestResult(
                    url=url, status_code=r.status_code,
                    elapsed_s=time.monotonic() - t0,
                    body_size_bytes=len(r.content),
                ))
            except Exception as exc:  # noqa: BLE001
                result.per_request.append(RequestResult(
                    url=url, status_code=0, elapsed_s=time.monotonic() - t0,
                    body_size_bytes=0, error=str(exc),
                ))
            time.sleep(delay)
        return result


    def measure_shared_ip(repeats: int) -> tuple[SpikeResult, SpikeResult, SpikeResult]:
        """Returns (baseline_asos, treatment_asos, treatment_cli)."""
        urls_asos_baseline = [ASOS_URL.format(station=s) for s in ASOS_STATIONS[:repeats]]
        baseline = serial_thread(urls_asos_baseline, IEM_POLITE_DELAY)

        # Treatment: two threads concurrent
        urls_asos = [ASOS_URL.format(station=s) for s in ASOS_STATIONS[:repeats]]
        urls_cli = [CLI_URL.format(station=s) for s in CLI_STATIONS[:repeats]]

        treatment_asos = SpikeResult(n=2, repeats=repeats)
        treatment_cli = SpikeResult(n=2, repeats=repeats)

        def run_asos():
            r = serial_thread(urls_asos, IEM_POLITE_DELAY)
            treatment_asos.per_request.extend(r.per_request)

        def run_cli():
            r = serial_thread(urls_cli, IEM_POLITE_DELAY)
            treatment_cli.per_request.extend(r.per_request)

        t1 = threading.Thread(target=run_asos)
        t2 = threading.Thread(target=run_cli)
        t1.start(); t2.start()
        t1.join(); t2.join()

        return baseline, treatment_asos, treatment_cli


    def recommend_option(baseline: SpikeResult, treatment_asos: SpikeResult, treatment_cli: SpikeResult) -> str:
        baseline_503 = baseline.status_distribution.get(503, 0)
        treatment_503 = treatment_asos.status_distribution.get(503, 0) + treatment_cli.status_distribution.get(503, 0)

        if treatment_503 > 2 * max(baseline_503, 1):
            return (
                "**Option A (RECOMMENDED — SHARED IP confirmed):** Use `threading.Lock()` "
                "shared between IEM-ASOS and IEM-CLI workers in `research.py`. Acquire the lock "
                "around `download_with_retry` calls in IEM fetchers only. Treatment 503 rate "
                f"({treatment_503}) significantly exceeded baseline ({baseline_503})."
            )
        elif treatment_503 <= baseline_503:
            return (
                "**Option C (RECOMMENDED — separate per-endpoint budgets):** No additional "
                "synchronization needed. Treatment 503 rate "
                f"({treatment_503}) ≈ baseline ({baseline_503}). The IEM `asos.py` and `cli.py` "
                "endpoints appear to have separate throttle budgets; PERF-04's 4-way fan-out "
                "is safe as-sketched."
            )
        else:
            return (
                f"**Option B (RECOMMENDED — partial-share suspected):** Treatment 503 rate "
                f"({treatment_503}) is elevated over baseline ({baseline_503}) but not 2×+. "
                "Use `max_workers=3` with serialized IEM ASOS+CLI in a single 'iem' worker "
                "function. Loses some parallelism but is structurally safe and avoids the "
                "lock-contention complexity of Option A."
            )


    def main() -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--repeats", type=int, default=10, help="Requests per thread")
        args = parser.parse_args()

        print("## IEM shared-IP throttle test (Pitfall 5 / Assumption A3)")
        print()
        print(f"Methodology: baseline = 1 serial ASOS thread, {args.repeats} requests, 1 sec/req.")
        print(f"Treatment = 1 ASOS + 1 CLI thread concurrent, each {args.repeats} requests, each 1 sec/req.")
        print()
        baseline, treatment_asos, treatment_cli = measure_shared_ip(args.repeats)

        print("| Variant | requests | p50_s | p95_s | status_dist | error_count |")
        print("|---|---|---|---|---|---|")
        print(render_markdown_row("baseline (1 ASOS)", baseline))
        print(render_markdown_row("treatment (ASOS, concurrent w/ CLI)", treatment_asos))
        print(render_markdown_row("treatment (CLI, concurrent w/ ASOS)", treatment_cli))
        print()
        print("### Recommendation for Plan 03 PERF-04 design:")
        print()
        print(recommend_option(baseline, treatment_asos, treatment_cli))


    if __name__ == "__main__":
        main()
    ```

    Step 2 — Verify the IEM CLI URL pattern matches production (`packages/weather/src/tradewinds/weather/_fetchers/iem_cli.py`). If the production pattern differs (likely uses a JSON or different endpoint), update the spike's `CLI_URL` accordingly. The spike's goal is to hit `mesonet.agron.iastate.edu` (the throttled host), not to use any particular product endpoint shape.

    Step 3 — Compile-check + ruff:
    ```bash
    uv run python spike/source_limits/iem_shared_ip_spike.py --help
    uv run ruff check spike/source_limits/iem_shared_ip_spike.py
    ```
    Both must exit 0.

    Step 4 — Run a 1-shot smoke with `--repeats 2` to verify both threads complete and produce a recommendation (this fires 2 + 2 + 2 = 6 real requests). Verify the recommendation logic doesn't crash on near-zero data.

    Step 5 — Commit: `feat(phase-1-5): IEM shared-IP throttle spike — verifies Pitfall 5 (PERF-05)`.
  </action>
  <verify>
    <automated>uv run python spike/source_limits/iem_shared_ip_spike.py --help && uv run ruff check spike/source_limits/iem_shared_ip_spike.py</automated>
  </verify>
  <acceptance_criteria>
    - `test -f spike/source_limits/iem_shared_ip_spike.py` returns 0
    - `grep -c "def measure_shared_ip" spike/source_limits/iem_shared_ip_spike.py` returns 1
    - `grep -c "def recommend_option" spike/source_limits/iem_shared_ip_spike.py` returns 1
    - `grep -c "Option A" spike/source_limits/iem_shared_ip_spike.py` returns ≥1
    - `grep -c "Option B" spike/source_limits/iem_shared_ip_spike.py` returns ≥1
    - `grep -c "Option C" spike/source_limits/iem_shared_ip_spike.py` returns ≥1
    - `grep "mesonet.agron.iastate.edu" spike/source_limits/iem_shared_ip_spike.py` returns ≥2 hits (ASOS_URL + CLI_URL both target it)
    - `grep "IEM_POLITE_DELAY" spike/source_limits/iem_shared_ip_spike.py` returns non-empty (uses production constant)
    - `uv run python spike/source_limits/iem_shared_ip_spike.py --help` exits 0
    - `uv run ruff check spike/source_limits/iem_shared_ip_spike.py` returns 0 errors
    - 2-repeat smoke run completes (exits 0) and prints all 4 markdown rows (header + baseline + treatment-ASOS + treatment-CLI) plus a recommendation paragraph
  </acceptance_criteria>
  <done>
    `iem_shared_ip_spike.py` exists with the baseline-vs-treatment design. Recommendation logic deterministically picks Option A/B/C from 503-rate evidence. Ready for Task 2.4 to run full spike.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2.4: Run all three spikes live + author `.planning/research/SOURCE-LIMITS.md`</name>
  <files>.planning/research/SOURCE-LIMITS.md</files>
  <implements>PERF-05 — the deliverable: documented empirical limits + Plan 03 input</implements>
  <read_first>
    - spike/source_limits/awc_concurrent.py (Task 2.2)
    - spike/source_limits/ghcnh_concurrent.py (Task 2.2)
    - spike/source_limits/iem_shared_ip_spike.py (Task 2.3)
    - .planning/phase-01-5-fetcher-optimization-cross-source-parallelism/RESEARCH.md (lines 509-543 — methodology)
    - .planning/research/ (verify dir exists; create if missing)
  </read_first>
  <what-built>
    Tasks 2.1-2.3 are done: spike scripts compile, smoke-runs pass, recommendation logic is implemented. Now execute the full spike against live APIs and write up `.planning/research/SOURCE-LIMITS.md` so Plan 03 has its input.
  </what-built>
  <how-to-verify>
    **Step A — Run the three spikes live (sequentially; total ~50 min wall time):**

    ```bash
    # AWC: N ∈ {1,2,4,8,16} × 5 repeats × ~3s per request (politeness) ≈ 15 min
    uv run python spike/source_limits/awc_concurrent.py --n-levels 1,2,4,8,16 --repeats 5 | tee /tmp/awc_spike.md

    # GHCNh: same N grid; PSV files are static so should be faster ≈ 10 min
    uv run python spike/source_limits/ghcnh_concurrent.py --n-levels 1,2,4,8,16 --repeats 5 | tee /tmp/ghcnh_spike.md

    # IEM shared-IP: 10 repeats × 1s/req × 2 phases ≈ 25 min
    uv run python spike/source_limits/iem_shared_ip_spike.py --repeats 10 | tee /tmp/iem_spike.md
    ```

    **Step B — Author `.planning/research/SOURCE-LIMITS.md`:**

    Structure (Claude assembles from the three `/tmp/*.md` captured outputs):

    ```markdown
    # SOURCE-LIMITS.md

    **Spike date:** 2026-05-22 (Phase 1.5 PERF-05)
    **Re-run command:** see `spike/source_limits/README.md`
    **Valid until:** v0.2 milestone OR any IEM/AWC/NCEI published policy change

    ## Summary

    [2-3 sentences: e.g. "AWC tolerates up to N=8 concurrent without 429s. GHCNh static-PSV
    tolerates N=16 freely (CDN-distributed). IEM `asos.py` and `cli.py` SHARE / DO NOT SHARE
    per-IP throttle budgets (1 sec/req at 2 concurrent threads produces 0 / X 503s)."]

    ## AWC METAR live endpoint

    | N (concurrent) | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | error_count |
    |---|---|---|---|---|---|---|---|
    [paste from /tmp/awc_spike.md]

    **Largest single-request body:** ~[size] bytes (168-hour AWC live window for a single station).

    **Recommended max concurrent for tradewinds:** N=4 (PERF-04 baseline).

    ## GHCNh static PSV archive

    | N (concurrent) | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | error_count |
    |---|---|---|---|---|---|---|---|
    [paste from /tmp/ghcnh_spike.md]

    **Largest single-request body:** ~[size] bytes for a single station-year PSV (5-year sample
    = 5 separate requests; 5-year-aggregate size = 5 × per-year size).

    **Recommended max concurrent for tradewinds:** N=4 (no evidence of upper limit).

    ## IEM shared-IP test (Pitfall 5 / Assumption A3)

    [paste from /tmp/iem_spike.md — includes baseline + treatment + recommendation]

    ### Recommendation for Plan 03 PERF-04 design

    [Verbatim from spike output — Option A or B or C with rationale grounded in 503-count data]

    ## Response-size measurements

    | Source | Window | Mean size | Max size | Notes |
    |---|---|---|---|---|
    | AWC live | 168 hr | [from spike] | [from spike] | 168-hr is API max |
    | GHCNh | 1 station-year | [from spike] | [from spike] | 5-year = 5 separate requests |
    | IEM ASOS | 1 year | [from spike] | [from spike] | 1-year is PERF-01 chunk size |
    | IEM CLI | 1 station-year | [from spike] | [from spike] | API granularity |

    ## Inputs to other plans

    - **Plan 03 PERF-04:** IEM-sharing strategy = [Option A | B | C] per the IEM shared-IP test above
    - **Plan 01 PERF-03:** HTTP_TIMEOUT=60s is adequate; max observed p99 response time across all sources is [X] s
    - **v0.2 retry strategy planner:** Adaptive rate limiting is deferred; this spike establishes the v0.1 empirical baseline
    ```

    **Step C — Verify the document is grounded in real numbers:**

    ```bash
    # Sanity: SOURCE-LIMITS.md must contain at least one of each spike's output table
    grep -c "## AWC METAR" .planning/research/SOURCE-LIMITS.md  # 1
    grep -c "## GHCNh" .planning/research/SOURCE-LIMITS.md      # 1
    grep -c "## IEM shared-IP" .planning/research/SOURCE-LIMITS.md  # 1
    grep -cE "Option [ABC]" .planning/research/SOURCE-LIMITS.md  # ≥1 (the recommendation)
    ```

    All must be ≥1.

    **Step D — Confirm to user:**

    Report SHA-256 of the captured spike outputs + the chosen Option (A/B/C) + headline numbers (e.g. "AWC N=16 produced 0 429s and max body 12 KB; GHCNh N=16 produced 0 errors; IEM treatment produced 5 503s vs baseline 0 → Option A recommended").

    User reads SOURCE-LIMITS.md, confirms the recommendation matches the data, types `approved` to commit + merge.

    **Step E — Commit:**

    ```bash
    git add .planning/research/SOURCE-LIMITS.md
    git commit -m "docs(phase-1-5): SOURCE-LIMITS.md from PERF-05 spike — recommend Option [X] for PERF-04"
    ```
  </how-to-verify>
  <resume-signal>
    Type `approved` after reviewing SOURCE-LIMITS.md to confirm the Option A/B/C recommendation matches the data; this triggers commit + 3-reviewer panel + merge to `merged-vision`. Type `rerun` if the spike output looks anomalous (e.g. transient endpoint downtime) — Task 2.4 re-runs the spike with the same scripts.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| spike scripts → AWC / GHCNh / IEM public endpoints | Outbound HTTPS; spike fires up to N=16 concurrent requests for ~50 min total. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-1.5-06 | Denial of Service (to remote) | spike scripts firing N=16 against public endpoints | mitigate | The spike is one-shot and totals ~50 min wall time. Per-request politeness is preserved (IEM 1 sec/req inside threads; AWC + GHCNh have no published rate-limit so no enforced delay, but N≤16 across 20 distinct stations is well below typical scraper traffic). AWC + GHCNh + IEM all serve millions of requests/day per their public dashboards; tradewinds' spike adds at most ~500 requests cumulative. Document spike re-run cadence in README as "v0.2 milestone or post-policy-change" so this stays one-shot, not recurring. |
| T-1.5-07 | Information Disclosure | spike output stored in `.planning/` | accept | Spike output is response-size + timing measurements + status codes. No PII, no secrets, no auth tokens. The endpoints are public-by-design. Accept. |
| T-1.5-08 | Tampering | SOURCE-LIMITS.md becomes Plan 03 design input | mitigate | A wrong recommendation (e.g. claiming Option C when data says Option A) seeds a CRITICAL bug into Plan 03 (PERF-04 fires concurrent IEM threads that hit 503s in production). Mitigation: (a) the spike's `recommend_option` function picks deterministically from 503-rate data (no Claude-narrative override allowed in the SOURCE-LIMITS.md "Recommendation" section); (b) the 3-reviewer panel includes python-architect with explicit prompt to sanity-check the recommendation against the raw 503-count data. |
</threat_model>

<verification>
| Check | Command | Expected |
|-------|---------|----------|
| `_common.py` percentile + helpers unit test | `uv run pytest spike/source_limits/test_common.py -x -v` | 3 passed |
| Spike scripts compile + help | `uv run python spike/source_limits/awc_concurrent.py --help && uv run python spike/source_limits/ghcnh_concurrent.py --help && uv run python spike/source_limits/iem_shared_ip_spike.py --help` | exit 0 |
| SOURCE-LIMITS.md exists | `test -f .planning/research/SOURCE-LIMITS.md` | exit 0 |
| SOURCE-LIMITS.md structure | `grep -c "## AWC METAR\|## GHCNh\|## IEM shared-IP" .planning/research/SOURCE-LIMITS.md` | ≥3 |
| SOURCE-LIMITS.md has Option recommendation | `grep -cE "Option [ABC]" .planning/research/SOURCE-LIMITS.md` | ≥1 |
| Ruff + format | `uv run ruff check spike/source_limits/ && uv run ruff format --check spike/source_limits/` | 0 errors |
</verification>

<success_criteria>
- [ ] `spike/source_limits/` package exists with `_common.py`, README, 3 spike scripts, and `test_common.py`
- [ ] All three spike scripts accept `--help` and pass `uv run python <script> --help`
- [ ] `_common.py`'s `percentile` is correct (median = p50, empty list returns NaN) and verified by `test_common.py`
- [ ] `iem_shared_ip_spike.py` deterministically picks Option A/B/C from 503-count data; logic is testable by injecting a `recommend_option(baseline, treatment_asos, treatment_cli)` call with synthetic SpikeResult data
- [ ] All three spike scripts ran live and produced markdown output
- [ ] `.planning/research/SOURCE-LIMITS.md` exists with sections for AWC, GHCNh, IEM shared-IP test, response-size measurements, and "Inputs to other plans"
- [ ] SOURCE-LIMITS.md states the chosen IEM-sharing Option (A/B/C) for Plan 03, with the recommendation grounded in the 503-count data printed in the spike output
- [ ] Pre-commit hooks green: `uv run pre-commit run --all-files` exits 0 (no `--no-verify`)
- [ ] Branch `phase-1-5/wave-1/source-limits-spike` is ready for 3-reviewer panel
</success_criteria>

<output>
After completion, create `.planning/phase-01-5-fetcher-optimization-cross-source-parallelism/01-5-02-SUMMARY.md` documenting:

- Spike run date + total wall time
- Headline numbers per source (AWC max-N-no-429, GHCNh max-N-no-error, IEM treatment 503 count vs baseline)
- Chosen Option (A/B/C) for Plan 03 IEM-sharing strategy + 1-paragraph rationale grounded in the data
- Path to SOURCE-LIMITS.md
- Any endpoint downtime / anomaly during the spike (re-run if needed)
- Time spent (Claude execution + live spike wall time + human review of SOURCE-LIMITS.md)
- Downstream signal for Plan 03: SOURCE-LIMITS.md is the input; the IEM-sharing-Option section is its task-1 read_first
</output>
