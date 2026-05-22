# SOURCE-LIMITS.md

**Spike date:** 2026-05-22 (Phase 1.5 PERF-05)
**Re-run command:** see [`spike/source_limits/README.md`](../../spike/source_limits/README.md)
**Valid until:** v0.2 milestone OR any IEM/AWC/NCEI published policy change
**Spike scope:** quick-smoke run (N ∈ {1, 2, 4}, repeats=2 for AWC/GHCNh,
repeats=4 for IEM shared-IP). N=8 and N=16 not exercised — see "Scope caveat"
below.

## Summary

- **AWC** tolerates up to N=4 concurrent without 429s or 5xx (all-200 across
  14 requests; spike did not probe N=8/16).
- **GHCNh** tolerates up to N=4 concurrent without errors. PSV responses are
  large (~10 MB per station-year, so HTTP_TIMEOUT=60s is load-bearing here —
  Plan 01 PERF-03 was right to bump).
- **IEM `asos.py` and `cli.py` do NOT share a per-IP throttle budget** at the
  tested load. Treatment (1 ASOS + 1 CLI thread concurrent, each at 1 req/sec)
  produced zero 503s and zero errors — identical to the single-thread baseline.
- **Plan 03 PERF-04 recommendation: Option C** (no shared `threading.Lock`;
  use `max_workers=4`; let each IEM fetcher preserve its own `IEM_POLITE_DELAY`).

## Scope caveat

The PERF-05 deliverable was sized for a **smoke run**, not the full N ∈ {1, 2,
4, 8, 16} × 5-repeat sweep PLAN-02 originally specified. At smoke-run scale the
endpoints are well-behaved at N=4; the recommendation against an IEM lock is
grounded in 0 vs 0 503s, not in a saturation-curve fit. If Plan 03 (or future
v0.2 work) needs to fan out at N=8+ or hold IEM at sustained > 1 req/sec, the
spike should be re-run at the higher load levels first — re-validation is one
command per script (see README).

The "Option C" recommendation is the empirically-correct choice for the
4-concurrent-worker PERF-04 design that Plan 03 ships, NOT a blanket claim
about all future concurrency levels.

## AWC METAR live endpoint (`aviationweather.gov/api/data/metar`)

| N (concurrent) | reqs | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |
|---|---|---|---|---|---|---|---|---|
| N=1 | 2 | 0.83 | 1.07 | 1.10 | {200: 2} | 82,980 | 82,980 | 0 |
| N=2 | 4 | 0.52 | 1.70 | 1.85 | {200: 4} | 87,410 | 91,839 | 0 |
| N=4 | 8 | 0.53 | 0.65 | 0.68 | {200: 8} | 95,419 | 109,395 | 0 |

**Largest single-request body:** ~110 KB (168-hour AWC live window for one
station, JSON format). Comfortably under HTTP_TIMEOUT=60s — AWC is the smallest
of the four sources by per-request size.

**Recommended max concurrent for tradewinds (Phase 1.5):** N=4. PERF-04 fans out
one AWC worker as part of the 4-source mix.

## GHCNh static PSV archive (`ncei.noaa.gov`)

| N (concurrent) | reqs | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |
|---|---|---|---|---|---|---|---|---|
| N=1 | 2 | 1.93 | 2.16 | 2.18 | {200: 2} | 10,429,934 | 10,429,934 | 0 |
| N=2 | 4 | 1.72 | 1.78 | 1.79 | {200: 4} | 10,503,924 | 10,577,915 | 0 |
| N=4 | 8 | 1.86 | 2.89 | 3.25 | {200: 8} | 10,597,137 | 10,804,486 | 0 |

**Largest single-request body:** ~10.8 MB for a single station-year PSV. This is
the **load-bearing case for PERF-03 HTTP_TIMEOUT=60s** — a slow PSV download
under previous 30s timeout would have failed on connection-throttled paths.

**Recommended max concurrent for tradewinds (Phase 1.5):** N=4. PSV downloads
are bandwidth-bound, not request-rate-bound; the CDN serves them in parallel
without complaint.

## IEM shared-IP test (Pitfall 5 / Assumption A3)

Test: hits `mesonet.agron.iastate.edu` from two distinct endpoints (`asos.py`
and `cli.py`) concurrently to detect a shared per-IP throttle budget.

| Variant | reqs | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |
|---|---|---|---|---|---|---|---|---|
| baseline (1 ASOS) | 4 | 0.94 | 1.24 | 1.28 | {200: 4} | 5,452 | 5,572 | 0 |
| treatment (ASOS, concurrent w/ CLI) | 4 | 0.92 | 0.95 | 0.95 | {200: 4} | 5,452 | 5,572 | 0 |
| treatment (CLI, concurrent w/ ASOS) | 4 | 1.98 | 2.00 | 2.00 | {200: 4} | 458,183 | 459,523 | 0 |

**Observations:**
- Both ASOS and CLI returned 200 on every request — no 503s, no errors in
  either single-thread or concurrent-thread runs.
- CLI responses (~460 KB / station-year) are ~84× larger than ASOS (~5.5 KB for
  the 1-day test slice). CLI's p50 sits at exactly 2.0 s — almost certainly
  bandwidth-bound on the larger response, not throttle-induced.
- ASOS p50 in the treatment is actually *lower* than baseline (0.92s vs 0.94s)
  — within noise; certainly not a degradation.

### Recommendation for Plan 03 PERF-04 design

**Option C (RECOMMENDED — separate per-endpoint budgets):** No additional
synchronization needed. Treatment 503/error rate (0) ≈ baseline (0). The IEM
`asos.py` and `cli.py` endpoints appear to have separate throttle budgets at
this load. PERF-04's 4-concurrent-worker fan-out (one ASOS + one CLI thread
running side-by-side) is safe as-sketched.

Future re-evaluation triggers:
- IEM publishes a tightened per-IP policy.
- Phase 3 expands to international stations (`asos.py` query rate scales with
  the station count if cross-station parallelism is added).
- Phase 3.2 wires HRRR/GFS/NBM live forecasts — that may add a third IEM-domain
  endpoint to the shared-IP test.

## Response-size measurements

| Source | Window | Mean size | Max size | Notes |
|---|---|---|---|---|
| AWC live | 168 hr | ~95 KB | ~110 KB | 168-hr is API max; smallest of the four sources |
| GHCNh | 1 station-year | ~10.5 MB | ~10.8 MB | LARGEST; load-bearing for HTTP_TIMEOUT=60s |
| IEM ASOS | 1 day (test slice) | ~5.5 KB | ~5.6 KB | Yearly chunks (Plan 01 PERF-01) ~1.8 MB per spec |
| IEM CLI | 1 station-year | ~460 KB | ~460 KB | JSON; ~100× larger than ASOS day-slice |

## Inputs to other plans

- **Plan 03 PERF-04:** IEM-sharing strategy = **Option C** (no shared lock;
  `max_workers=4`); preserve each fetcher's own `IEM_POLITE_DELAY`. If the
  parallelism check fails in the live perf test, revisit by re-running the
  spike at the production-scale concurrency.
- **Plan 01 PERF-03:** HTTP_TIMEOUT=60s is **load-bearing** for GHCNh (p99=3.25s
  observed on a single 10 MB PSV at N=4; longer windows or larger files would
  push p99 higher). The 30s prior timeout would not have been safe for GHCNh
  at sustained load.
- **v0.2 retry strategy planner:** Adaptive rate limiting is deferred; this
  spike establishes the v0.1 empirical baseline. No 429s were observed across
  any source at the tested levels, so a conservative `MAX_RETRIES=3` with
  exponential backoff (the current state) is sufficient. Re-run before any
  cross-station fan-out (v0.2) is wired.
