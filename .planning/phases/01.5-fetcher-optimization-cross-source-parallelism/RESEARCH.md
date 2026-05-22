# Phase 1.5: Fetcher Optimization + Cross-Source Parallelism — Research

**Researched:** 2026-05-22
**Domain:** HTTP fetcher chunking + cross-source thread-pool orchestration + rate-limit characterization
**Confidence:** HIGH on PR #85 content (full diff retrieved via `gh api`), HIGH on httpx/threading semantics (Python stdlib docs + httpx maintainer guidance), MEDIUM on AWC/GHCNh empirical limits (no published numbers — spike will produce them).

## Summary

PR #85 (commit `cf9eb85`, merged 2026-05-12 to `Tarabcak/mostlyright`) is a self-contained patch with verbatim-liftable content for PERF-01/02/03. The full diff is accessible via `gh api repos/Tarabcak/mostlyright/contents/...?ref=cf9eb85` and was retrieved during this research. The new `_iem_chunks.py` module is 96 lines, exports two helpers (`yearly_chunks_inclusive` for IEM MOS, `yearly_chunks_exclusive_end` for IEM ASOS), and uses `date(year+1, 1, 1)` not `timedelta(days=365)` — the canonical leap-year-safe pattern. `HTTP_TIMEOUT` simply bumps `30.0` → `60.0` in `_http.py`; no other change to that file. The cache-filename change in `iem_gap_fill.py` is the most subtle of the three: it adds a `_partial` infix and uses `datetime.now(timezone.utc).date()` (not `date.today()`) for the cutoff — locking that detail is a CRITICAL parity-and-correctness requirement.

ThreadPoolExecutor + httpx for 4-way I/O fan-out is a solved, low-risk pattern: `httpx.Client` is documented thread-safe; futures propagate exceptions through `.result()`. The PERF-04 wiring lives in a NEW `research.py` file (the file doesn't exist yet — see Wave-0 note below). Per-source `time.sleep` politeness already lives inside each fetcher, so cross-source parallelism does NOT need a global rate limiter — each source thread paces itself.

The biggest non-obvious finding: **as of 2026-04-21 IEM published a formal 1 second per-IP throttle** (see `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help=`). The existing `IEM_POLITE_DELAY = 1.0` is already correctly aligned with this, but it means cross-source parallelism CANNOT include two IEM workers without colliding with their own throttle — and the 4-way fan-out (AWC + IEM-ASOS + GHCNh + CLI) already has the right shape because IEM-ASOS and IEM-CLI are separate threads each paced at 1 req/sec, against a 1 req/sec **per-IP** budget shared by both. This is a real risk that needs to be addressed in PERF-04 planning. See **Pitfall 5** below.

**Primary recommendation:** lift PR #85 byte-faithfully (`_iem_chunks.py` as `packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py`, mirror the `_partial` cache filename in `iem_asos.py`, bump `HTTP_TIMEOUT` in `_internal/_http.py`). For PERF-04, share one `httpx.Client` across threads inside each fetcher (already the pattern), do NOT share clients across fetchers, and submit ONE future per source to `ThreadPoolExecutor(max_workers=4)`. Spike `iem.archive` (ASOS) + `iem.archive` (CLI) parallelism explicitly in PERF-05 — they share an IP throttle.

## Project Constraints (from CLAUDE.md)

These constraints are non-negotiable for Phase 1.5 planning. Treat with the same authority as locked decisions.

| Constraint | Source | Phase 1.5 implication |
|------------|--------|------------------------|
| `httpx>=0.28,<1.0`, sync only in v0.1 | CLAUDE.md tech stack | No `httpx.AsyncClient`, no `async def`, no `aiohttp`. Threads only. |
| Lift source pinned to v0.14.1 tag | CLAUDE.md data + parity rules | PR #85 patches lift onto v0.14.1, NOT monorepo HEAD (HEAD has Open-Meteo removal + settlement_v1 intake + other diverged changes). |
| `pandas>=2.2,<3.0` | CLAUDE.md tech stack | Phase 1.5 should not introduce a pandas dependency it doesn't already have. Cache-poison fix + chunker = pure stdlib + httpx — no pandas needed in the fetcher path. |
| TDD mandatory (RED → GREEN → REFACTOR), 80% coverage | CLAUDE.md collab rules | Every lifted helper gets a test that fails before the implementation, including `_iem_chunks` reversed-range, leap-year, and `_partial` filename branches. |
| Pre-commit + pre-push hooks; no `--no-verify` | CLAUDE.md | All plan tasks must pass `uv run pre-commit run --all-files` + `uv run pytest -m "not live" -q` before commit. |
| Direct API calls only — no `api.mostlyright.md` | CLAUDE.md | Fetchers stay direct-to-source. PERF-04 orchestration sits in `research.py` (local code), not behind any hosted layer. |
| `@pytest.mark.live` for tests that hit real public APIs (excluded from CI) | CLAUDE.md testing | The PERF-05 spike scripts are NOT under `tests/` (per CONTEXT). They live in `spike/source_limits/` as one-shot manual scripts. The PERF-04 parallelism assertion goes against recorded fixtures (pytest-recording) so it can run in CI, not live. |
| Never commit directly to main; PR + review loop | CLAUDE.md | Three-reviewer panel (codex high + python-architect + security) confirmed in CONTEXT. |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Concurrency primitive:** `concurrent.futures.ThreadPoolExecutor` with `max_workers=4` (one per source). Forbid `asyncio`, `httpx.AsyncClient`, `async def`.
- **Sequencing:** strictly serial after Phase 1, strictly before Phase 2. No co-execution with Phase 2 Wave 1 — both phases touch `_internal/_http.py`.
- **Lift fidelity:** PERF-01/02/03 lift from `mostlyright` PR #85 (commit `cf9eb85`, 2026-05-12). Diff must be reviewable against that exact commit. Do NOT lift from monorepo HEAD.
- **Parallelism check threshold:** `wall_time ≤ max(per_source_t_i) * 1.2`. Rejected: earlier `≤45% of sum` (mathematically invalid when sources are uneven).
- **Empirical performance gate:** KNYC 5-year ASOS backfill ≤ 12 min wall time at 1 req/sec. Other-station regression: pick one of {KMDW, KLAX, KMIA} and confirm against per-station baseline from the spike — no fixed cross-station threshold.
- **Cache scope:** PERF-02 applies ONLY to `_fetchers/iem_asos.py`'s raw-CSV staging cache. The user-facing parquet cache (`tradewinds.weather.cache`) is UNTOUCHED.
- **Parity gate handling:** re-run all 5 parity fixtures BEFORE merge to `merged-vision`. If drift, decide post-spike between (a) revert chunk change, or (b) change merge `>` → `>=` with deterministic secondary key (`source` then `chunk_start`). Decision deferred to empirical outcome.
- **Rate-limit spike artifacts:** `.planning/research/SOURCE-LIMITS.md` (output) + `spike/source_limits/` (scripts). Spike scripts NOT under `tests/`.
- **Review panel:** 3 reviewers for Phase 1.5 (codex `high` + python-architect + security). Reverts to standard 2-reviewer after Phase 1.5 ships.

### Claude's Discretion

- Exact name/location of the `_iem_chunks` helper module (recommendation below: `packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` — sibling to `iem_asos.py`).
- Plan granularity: 1 plan vs N plans (recommendation: 3 plans — see plan-shape note below).
- Whether PERF-05 spike runs before or after PERF-04 within the phase (recommendation: spike FIRST — PERF-04 needs the empirical max-concurrency numbers).
- Exact assertion form for `wall_time ≤ max(per_source_t_i) * 1.2` (recommendation: pytest fixture + `time.monotonic()` against recorded-fixture HTTP — see "Test strategy for PERF-04" below).

### Deferred Ideas (OUT OF SCOPE)

- v0.2+ async refactor of catalog adapters
- Cross-station parallelism (KNYC + KMDW + KLAX simultaneously) — Phase 1.5 parallelizes only across SOURCES for a single station
- Adaptive rate limiting based on response headers — v0.2
- The parity-gate fallback choice (revert vs merge change) — deferred to empirical outcome

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| PERF-01 | IEM ASOS + MOS chunk size 365 calendar-aligned days; shared `_iem_chunks()` leap-year safe; KNYC 5-yr backfill ≤ 12 min | Full `_iem_chunks.py` source retrieved from PR #85 below; leap-year algorithm verified (`date(year+1, 1, 1)`); PR #85 measured 10 min for KNYC, allowing 20% headroom |
| PERF-02 | IEM CSV staging cache filename encodes full chunk window; `_partial` namespace for skip-cache OR `chunk_end > today_utc` | Full `_iem_cache_filename` + `download_iem` loop retrieved below; `today_utc = datetime.now(timezone.utc).date()` (UTC, NOT local!) is critical and was a HIGH-severity round-2 finding in PR #85 |
| PERF-03 | `HTTP_TIMEOUT` 30s → 60s in `_internal._http` | Full `_http.py` diff retrieved: one-line change `HTTP_TIMEOUT = 60.0` + new docstring explaining 12x payload-per-request rationale |
| PERF-04 | `research.py` orchestrator fires AWC + IEM + GHCNh + NWS CLI concurrently via `ThreadPoolExecutor(max_workers=4)`; parallelism check `wall_time ≤ max(per_source_t_i) * 1.2` | Pattern verified in stdlib docs; `httpx.Client` thread-safety verified; **Wave-0 gap: `research.py` does not exist yet** — Phase 1.5 must create it (or stub if Phase 2 wants ownership) |
| PERF-05 | AWC + GHCNh rate-limit headroom; SOURCE-LIMITS.md + `spike/source_limits/` scripts | No published rate limits for AWC; NCEI GHCNh has no public published rate-limit doc; **empirical spike is the only path**. Spike methodology in §"Rate-limit characterization" below |

## Standard Stack

### Core (already pinned in CLAUDE.md — no new deps)

| Library | Version (pinned) | Phase 1.5 use |
|---------|------------------|----------------|
| `httpx` | `>=0.28,<1.0` | Sync HTTP client. Already used by every fetcher. |
| `concurrent.futures` | stdlib | `ThreadPoolExecutor` for PERF-04. Python 3.11+ stdlib. |
| `datetime` | stdlib | Calendar arithmetic for `_iem_chunks` — MUST use `date(year+1, 1, 1)`, NOT `timedelta(days=365)`. |
| `filelock` | `>=3.20,<4` | Already used by the parquet cache (untouched). NOT needed for the CSV staging cache. |
| `pytest-recording` (vcrpy) | `>=0.13.4` | Recorded-fixture tests for PERF-04 parallelism check. Already mentioned in CLAUDE.md as the canonical VCR-style choice. |

**No new dependencies required for Phase 1.5.** Verify before adding any.

### Verification

```bash
# Version sanity check inside the project venv
uv run python -c "import httpx, sys; print('httpx', httpx.__version__, 'py', sys.version_info)"
# Expected: httpx 0.28.1+, Python 3.11+
```
[VERIFIED: project worktree, 2026-05-22 — `httpx 0.28.1`]

## Architecture Patterns

### Pattern 1: Shared chunker module — single source of truth

**What:** One `_iem_chunks.py` module with two helpers — `yearly_chunks_inclusive` (for any future MOS work) and `yearly_chunks_exclusive_end` (for `iem_asos.py` which sends IEM's exclusive-end `day2`). Both helpers leap-year safe via `date(year+1, 1, 1)`, both guard against reversed ranges (`if start > end: return []`).

**When to use:** Any IEM fetcher that does range-chunking. In v0.1.0 only `iem_asos.py` consumes it; v0.2 MOS work would consume it without re-deriving the algorithm.

**Source (from PR #85 commit `cf9eb85`, file `ingest/sources/_iem_chunks.py`):**

```python
# [VERIFIED: gh api repos/Tarabcak/mostlyright/contents/ingest/sources/_iem_chunks.py?ref=cf9eb85]
from __future__ import annotations
from datetime import date

__all__ = ["yearly_chunks_inclusive", "yearly_chunks_exclusive_end"]


def yearly_chunks_inclusive(start: date, end: date) -> list[tuple[date, date]]:
    """[start, end] split into per-calendar-year inclusive-end chunks."""
    if start > end:
        return []
    chunks: list[tuple[date, date]] = []
    current = start
    while current <= end:
        year_end = date(current.year, 12, 31)
        chunk_end = min(year_end, end)
        chunks.append((current, chunk_end))
        current = date(current.year + 1, 1, 1)  # leap-year safe
    return chunks


def yearly_chunks_exclusive_end(start: date, end: date) -> list[tuple[date, date]]:
    """Range split into per-calendar-year EXCLUSIVE-end chunks (Jan 1 of next year)."""
    if start > end:
        return []
    chunks: list[tuple[date, date]] = []
    current = date(start.year, 1, 1)
    while current <= end:
        chunk_start = max(current, start)
        next_year_1st = date(current.year + 1, 1, 1)
        chunks.append((chunk_start, next_year_1st))
        current = next_year_1st
    return chunks
```

**Recommended location in tradewinds:** `packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py` (sibling of `iem_asos.py`). The leading underscore signals "internal helper, not part of the SDK public surface."

### Pattern 2: Cache-filename encodes chunk window + `_partial` namespace

**What:** Replace the `iem_<YYYYMM>_<suffix>.csv` filename with `iem_{start_iso}_{end_iso}{_partial?}_{suffix}.csv`. A chunk is "partial" when `skip_cache=True` OR `chunk_end > today_utc`. Partial chunks go to `_partial`-named files; backfill paths never read partial files; cache-hit logic ONLY matches canonical filenames.

**Why:** PR #85 documented this as a CRITICAL silent-data-loss fix. Before the change, a live-sweep `skip_cache=True` request wrote `iem_2026_metar.csv` containing only Jan 1..May 11 data, and the next backfill call cache-hit on that filename as if it were a complete-year file. No error, no warning, settlement-grade silent data corruption.

**The UTC subtlety (HIGH-severity PR #85 round-2 finding):** Use `datetime.now(timezone.utc).date()`, NOT `date.today()`. IEM ASOS endpoint takes `tz=Etc/UTC`, so chunk completeness must be evaluated in UTC. On a non-UTC host (the upstream maintainer is in Europe/Prague) `date.today()` returns local-today, which is AHEAD of UTC for ~half the day — a chunk_end == local-today gets treated as canonical while UTC has NOT yet reached that exclusive end, writing a "canonical" file that's missing the UTC tail of data.

**Source (filename helper from PR #85):**

```python
# [VERIFIED: gh api repos/Tarabcak/mostlyright/contents/ingest/sources/iem_gap_fill.py?ref=cf9eb85]
def _iem_cache_filename(
    chunk_start: date,
    chunk_end: date,
    suffix: str,
    *,
    partial: bool,
) -> str:
    partial_infix = "_partial" if partial else ""
    return (
        f"iem_{chunk_start.isoformat()}_{chunk_end.isoformat()}"
        f"{partial_infix}_{suffix}.csv"
    )
```

**Source (download loop chunk-is-partial decision):**

```python
# [VERIFIED: gh api repos/Tarabcak/mostlyright/contents/ingest/sources/iem_gap_fill.py?ref=cf9eb85]
today_utc = datetime.now(timezone.utc).date()  # UTC, NOT date.today()
for chunk_start, chunk_end in chunks:
    chunk_is_partial = skip_cache or chunk_end > today_utc
    for report_type, suffix, _ in _IEM_REPORT_TYPES:
        filename = _iem_cache_filename(
            chunk_start, chunk_end, suffix, partial=chunk_is_partial
        )
        dest = dest_dir / station.code / filename
        if dest.exists() and not chunk_is_partial:
            paths.append(dest)
            continue
        url = _build_iem_url(station, chunk_start, chunk_end, report_type)
        download_with_retry(url, dest)
        time.sleep(IEM_POLITE_DELAY)
        paths.append(dest)
```

**Subtle correctness point:** `chunk_end == today_utc` is NOT partial (because IEM `day2` is exclusive — the chunk's last covered day is `today_utc - 1`, which is fully populated in UTC). Only `chunk_end > today_utc` is partial. The CONTEXT-mentioned condition "skip_cache=True AND chunk_end > today_utc routes to `_partial`" is slightly wrong as written — the actual condition is **OR**, not **AND**: `chunk_is_partial = skip_cache or chunk_end > today_utc`. **Planner must catch this** — the OR-vs-AND distinction is the difference between "skip_cache live-sweep gets safely partitioned" and "skip_cache live-sweep poisons cache".

### Pattern 3: HTTP timeout matches payload size

**What:** Bump `HTTP_TIMEOUT` from 30s to 60s in `packages/core/src/tradewinds/_internal/_http.py`. One-line change with a docstring explaining the 12x payload increase per chunk.

**Source (verbatim from PR #85):**

```python
# [VERIFIED: gh api repos/Tarabcak/mostlyright/contents/ingest/sources/_http.py?ref=cf9eb85]
MAX_RETRIES = 3
BASE_DELAY = 1.0
# Round-2 review (PR #85) HIGH-2: 12x larger payload-per-request after the
# IEM chunk bump (90d→year). Pre-bump ASOS was ~150 KB/month (30s plenty);
# post-bump it's ~1.8 MB/year on the empirical KNYC sample with potentially
# larger payloads for high-traffic stations.
HTTP_TIMEOUT = 60.0
TRANSIENT_CODES = frozenset({500, 502, 503, 504})
```

### Pattern 4: ThreadPoolExecutor for I/O-bound HTTP fan-out

**What:** `concurrent.futures.ThreadPoolExecutor(max_workers=4)` with one task per source. `httpx.Client` is documented thread-safe; the per-fetcher pattern in tradewinds (each fetcher creates its own `httpx.Client` inside a context manager — see `_internal/_http.py:download_with_retry` and `_fetchers/awc.py`) is already correct for the four-thread model.

**Reference idiom (from CONTEXT.md — verified against `concurrent.futures` docs):**

```python
# [VERIFIED: docs.python.org/3/library/concurrent.futures.html]
import concurrent.futures
import time

def research(station, start, end):
    t_start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(_fetch_iem_asos, station, start, end): "iem.archive",
            ex.submit(_fetch_awc, station, start, end): "awc.live",
            ex.submit(_fetch_ghcnh, station, start, end): "ghcnh.archive",
            ex.submit(_fetch_cli, station, start, end): "cli.archive",
        }
        results = {}
        per_source_times = {}
        for f, name in futures.items():
            t0 = time.monotonic()
            results[name] = f.result()  # raises on per-source exception
            per_source_times[name] = time.monotonic() - t0  # NB: see Pitfall 6
    wall_time = time.monotonic() - t_start
    return results, wall_time, per_source_times
```

**Critical idiom points:**
1. **Use `.result()` to propagate exceptions.** A future's `.result()` raises whatever exception the worker raised. Without calling `.result()`, an exception is silently dropped — a known Python pitfall. ([Python docs § Future.result](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.result))
2. **Do NOT pass `timeout=` to `.result()` for the per-source layer** — `HTTP_TIMEOUT=60s` in httpx is the per-REQUEST timeout, and each fetcher does many requests (e.g. 5 years × 1 yearly chunk × 2 report types = 10 IEM requests). The total fetcher wall time can exceed any small future timeout. Let httpx handle timeouts at the request level.
3. **Per-source timing measurement has a subtle bug.** The `t0 = time.monotonic()` BEFORE `f.result()` does NOT capture when the worker started — it captures when the iteration reached the future. If futures complete out of submission order, the first `result()` call blocks for the slowest source and `per_source_times` for it gets inflated. See Pitfall 6.

### Pattern 5: `httpx.Client` thread-safety

**What:** `httpx.Client` is thread-safe; a single client instance shared across threads benefits from connection pooling. However, each tradewinds fetcher already creates its own `httpx.Client` inside a `with` context — that pattern is fine because each thread has its own client, and connection pooling at the thread level still works.

**Recommendation:** do NOT introduce a module-level shared `httpx.Client` in Phase 1.5. Keep the existing per-fetcher-context pattern. Reason: scope discipline. The CONTEXT scope is "add parallelism", not "refactor fetcher HTTP discipline".

**Verified statements:**
- "HTTPX is intended to be thread-safe, and a single client-instance across all threads will do better in terms of connection pooling than using an instance-per-thread." [CITED: github.com/encode/httpx/discussions/1633]
- "Closing the client in one thread and making requests in another would probably break the client state." [CITED: same]
- HTTP/2 + ThreadPoolExecutor has known issues (httpx#3002). We use HTTP/1.1 (httpx default — no `http2=True` anywhere in tradewinds). [VERIFIED: `grep -rn http2 packages/` returns no hits]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Calendar-year chunking | Custom `for year in range(...)` | Lift `_iem_chunks.yearly_chunks_exclusive_end` from PR #85 verbatim | Already empirically validated; handles reversed-range and leap-year edge cases |
| Leap-year arithmetic | `start + timedelta(days=365)` | `date(year+1, 1, 1)` (the PR #85 pattern) | `timedelta(days=365)` drifts by one day every leap year — produces wrong chunks for 2024, 2028, etc. |
| "Is this chunk partial?" decision | Reimplement | Lift verbatim: `chunk_is_partial = skip_cache or chunk_end > today_utc` (UTC, not local) | Subtle correctness point — the OR (not AND) AND the UTC-not-local both matter |
| Cross-thread exception swallowing | Try/except per worker | Let `.result()` raise; catch only at the orchestrator level | `concurrent.futures` propagates exceptions through `.result()` cleanly; bare workers that swallow exceptions hide regressions |
| HTTP retry/backoff | New code | Existing `download_with_retry` in `_internal/_http.py` | Already battle-tested; PERF-03 only bumps the timeout constant, doesn't touch retry logic |
| Rate limiting in `research.py` | A global Lock or Semaphore | Per-fetcher `time.sleep(POLITE_DELAY)` is already correct | Each source has its own throttle budget; cross-source workers naturally interleave |
| `httpx.AsyncClient` | "Async is faster" | Sync threads — CLAUDE.md locks sync in v0.1 | Already locked; threads are sufficient for 4-way fan-out |

**Key insight:** PR #85 is a well-reviewed, empirically validated patch. The single highest-leverage Phase 1.5 action is **lift it byte-faithfully** — don't reinvent any of the three changes. Add the new code (ThreadPoolExecutor in `research.py`, spike scripts) as the only "net new" work; everything else is a translation exercise.

## Runtime State Inventory

Not applicable. Phase 1.5 is code-only: changes to fetcher chunk size, cache filename pattern (inside `_fetchers/iem_asos.py` — fetcher-internal staging only), HTTP timeout constant, and a new `research.py`. No data migration, no running services, no OS-registered state, no secrets, no build artifacts to invalidate.

**Cache concern (documented for planner):** existing `iem_<YYYYMM>_<suffix>.csv` files on disk under `$HOME/.tradewinds/cache/iem_staging/<station>/` (if any developers ran observation fetches before Phase 1.5 lands) will be orphaned by the new `iem_{start_iso}_{end_iso}_*.csv` naming. Per PR #85 CHANGELOG: "Old monthly cache files are harmless (will not be read by the yearly chunker); next backfill regenerates yearly files." Document this in tradewinds CHANGELOG.md the same way; no migration required.

## Common Pitfalls

### Pitfall 1: `timedelta(days=365)` for year chunking

**What goes wrong:** Drift of one day every leap year. A 5-year chunk starting `2023-01-01` ends `2027-12-31` arithmetically, but with `timedelta(days=365)` you get `2027-12-30` — off by one day, silent data loss at the chunk boundary.

**Why it happens:** Naïve year arithmetic. 365 days != 1 calendar year in 2024, 2028.

**How to avoid:** Use the PR #85 pattern `current = date(current.year + 1, 1, 1)`. Test the leap-year boundary explicitly: a chunk crossing 2024-02-29 must include that date.

**Warning signs:** A test that runs `_iem_chunks(date(2023,1,1), date(2025,1,1))` and asserts the second chunk's exclusive end is `date(2025, 1, 1)`. If your implementation returns `date(2024, 12, 31)` (off by 1) the leap year bit you.

### Pitfall 2: Local time instead of UTC for chunk-completeness cutoff

**What goes wrong:** On a non-UTC host (Europe/Prague is UTC+1 standard / UTC+2 DST), `date.today()` returns local-today, which is AHEAD of UTC by 1–2 hours. A chunk with `chunk_end == local-today` gets classified as canonical (because `chunk_end > date.today()` is `False`), but UTC has not yet reached that day's start — the response covers data up to "yesterday in UTC", and the missing UTC tail gets baked into a canonical file. Next backfill cache-hits the partial file silently.

**Why it happens:** Defaulting to `date.today()` feels natural; the IEM endpoint's `tz=Etc/UTC` semantic is invisible in the Python code.

**How to avoid:** ALWAYS use `datetime.now(timezone.utc).date()` for the cutoff. Verbatim from PR #85. Test this with `freezegun` or `unittest.mock.patch` of both `datetime.now` AND `date.today` — if your test stubs only one, the bug can hide.

### Pitfall 3: OR vs AND in "is this partial"

**What goes wrong:** The CONTEXT.md description "`skip_cache=True` AND `chunk_end > today_utc` routes to `_partial`" reads as conjunction. The actual PR #85 code is disjunction: `chunk_is_partial = skip_cache or chunk_end > today_utc`. If you implement AND, then a `skip_cache=True` live-sweep with `chunk_end <= today_utc` (entirely-historical sweep) is classified as canonical — and rewrites the canonical cache file with a re-fetched response. Probably idempotent in practice, but it defeats the `_partial` namespace's safety purpose.

**Why it happens:** Misreading the spec.

**How to avoid:** Test both paths explicitly. Two tests: `test_skip_cache_alone_writes_to_partial` (skip_cache=True, all chunks historical → must hit `_partial`) and `test_future_chunk_end_alone_writes_to_partial` (skip_cache=False, but some chunk in-progress → must hit `_partial`). Both must pass; both fail-then-pass under RED-GREEN.

### Pitfall 4: Chunk-iteration order affects merge tie-break

**What goes wrong:** `_internal/merge/observations.py` uses strict `>` on `SOURCE_PRIORITY` — first-row-seen wins on same-priority ties. Same-priority ties happen on:
- AWC + IEM same-station-same-timestamp (both priority `awc:3`, `iem:2` — different priority, no tie)
- IEM METAR vs IEM SPECI at same `(station, observed_at, observation_type)` (same source, same priority — first row seen wins)
- Two GHCNh rows at the same timestamp (unlikely; PSV is single-file-per-year)

The **real** tie risk is METAR vs SPECI within a single IEM chunk where the row order changes as a function of chunk size — a 12-month chunk emits rows in a different sequence than 12 monthly chunks combined.

**Why it happens:** Chunk size affects request pattern → CSV emit order → list-iteration order → merge tie outcome.

**How to avoid:**
- Cheap pre-check (recommended BEFORE running all 5 parity fixtures): re-run a single parity fixture under both `_monthly_chunks` (old) and `yearly_chunks_exclusive_end` (new). If the single fixture is byte-equal, the chunker change is observation-merge-safe and you can proceed to the full 5-fixture run with confidence. If it drifts, you've spent ~30 seconds detecting it instead of the full fixture-suite runtime.
- If drift: per CONTEXT, decide between (a) revert chunk size, or (b) change merge `>` to `>=` with deterministic secondary key (`source` then `chunk_start`). Both are acceptable; choose based on empirical magnitude.

**Warning signs:** A parity fixture's diff is in `(observation_type, retrieved_at)` columns only — that strongly suggests a tie-break flip, not a real data-loss bug.

### Pitfall 5: IEM 1-second per-IP throttle and PERF-04's two IEM workers

**What goes wrong:** As of 2026-04-21, IEM publishes a formal 1 second per-IP throttle (any source under `mesonet.agron.iastate.edu`). PERF-04 fires 4 sources concurrently: AWC, IEM-ASOS, GHCNh, IEM-CLI. The IEM-ASOS and IEM-CLI workers share the per-IP IEM budget. Each fetcher already sleeps `time.sleep(1.0)` per request — but they sleep INDEPENDENTLY in separate threads, so two IEM threads can each fire 1 request/sec, totalling 2 req/sec at IEM. IEM responds with HTTP 503 on overload.

**Why it happens:** Per-fetcher politeness in a serial world == per-IP politeness. In a parallel world == per-source-thread politeness. The two are not equal when multiple threads share an IP budget.

**How to avoid (planner must address):**
- **Option A (recommended):** keep ThreadPoolExecutor at `max_workers=4` but document that IEM-ASOS and IEM-CLI **must serialize** via a module-level `threading.Lock` or `threading.Semaphore(1)`. The lock is acquired around the `download_with_retry` call inside IEM fetchers only, not around AWC/GHCNh.
- **Option B:** use `max_workers=3` — combine IEM-ASOS and IEM-CLI into one serial "IEM" worker that runs both consecutively. Loses some parallelism but is structurally safer.
- **Option C (defer to PERF-05 spike):** the spike characterizes the actual concurrent IEM behavior. If empirical results show 2 concurrent IEM threads at 1 req/sec each does NOT trigger 503s, the threshold is higher than 1 req/sec per IP and Option A's lock is unnecessary.

**Recommendation:** spike FIRST (PERF-05), then choose Option A/B/C based on empirical evidence. The 4-way parallelism claim in CONTEXT.md is not yet falsified, but it's not yet verified either.

**Warning signs:** PERF-04 test produces 503s under recorded-fixture replay when IEM-ASOS and IEM-CLI are both in-flight. Or live smoke test fails with `httpx.HTTPStatusError` for 503 from `mesonet.agron.iastate.edu` after PERF-04 wiring.

[VERIFIED: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help=` — "1 second per-IP throttle is now in place" (2026-04-21)]

### Pitfall 6: Per-source timing measurement is wrong as written

**What goes wrong:** The CONTEXT-sketch code measures per-source time as:
```python
for f, name in futures.items():
    t0 = time.monotonic()
    results[name] = f.result()
    per_source_times[name] = time.monotonic() - t0
```
But `f.result()` blocks until that specific future completes. If the dict iteration starts with `iem.archive` and the IEM future is slowest, the first `.result()` call blocks for the entire wall time of IEM. When iteration reaches `awc.live`, the future is already done (AWC is fast) and `t0 = time.monotonic()` measures zero — so AWC's measured time is ~0 and IEM's measured time is wall_time. Both are wrong.

**Why it happens:** `t0` must be captured BEFORE `submit()`, not before `result()`.

**How to avoid:** capture submit-time and completion-time, both monotonic:
```python
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    submitted_at = {}
    futures = {}
    for name, fetcher_args in [...]:
        f = ex.submit(*fetcher_args)
        submitted_at[name] = time.monotonic()
        futures[f] = name
    per_source_times = {}
    for f in concurrent.futures.as_completed(futures):
        name = futures[f]
        per_source_times[name] = time.monotonic() - submitted_at[name]
        # consume result to surface exceptions
        results = f.result()  # ...
```
Using `as_completed` ensures per-source times measure actual work, not iteration order.

### Pitfall 7: `httpx.Client` lifecycle across threads

**What goes wrong:** Sharing a single `httpx.Client` across threads is documented thread-safe FOR REQUESTS, but closing the client from one thread while another is mid-request will raise. The existing per-fetcher pattern (`with httpx.Client(...) as client:`) doesn't have this problem because each thread has its own client lifecycle.

**How to avoid:** Keep the per-fetcher `with httpx.Client(...)` pattern. Do NOT factor a single module-level Client out as a "performance win". The win is small; the risk is real. (Out of scope for Phase 1.5 anyway — scope is parallelism, not refactor.)

## Code Examples

### IEM ASOS fetcher diff shape (lift target — apply to `iem_asos.py`)

The current `_fetchers/iem_asos.py` uses `_monthly_chunks` (lines 52–99) and an `iem_<YYYYMM>_<suffix>.csv` filename (line 182). The lift replaces both:

```python
# [CITED: PR #85 ingest/sources/iem_gap_fill.py]
from datetime import date, datetime, timezone
from tradewinds.weather._fetchers._iem_chunks import yearly_chunks_exclusive_end

def _yearly_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Thin wrapper around the shared exclusive-end chunker."""
    return yearly_chunks_exclusive_end(start, end)


def _iem_cache_filename(
    chunk_start: date,
    chunk_end: date,
    suffix: str,
    *,
    partial: bool,
) -> str:
    partial_infix = "_partial" if partial else ""
    return (
        f"iem_{chunk_start.isoformat()}_{chunk_end.isoformat()}"
        f"{partial_infix}_{suffix}.csv"
    )


def download_iem_asos(
    station: StationInfo,
    start: date,
    end: date,
    dest_dir: Path,
    *,
    skip_cache: bool = False,
    report_type: int = 3,
) -> list[Path]:
    if report_type not in _REPORT_TYPE_SUFFIX:
        raise ValueError(...)
    suffix = _REPORT_TYPE_SUFFIX[report_type]
    chunks = _yearly_chunks(start, end)
    today_utc = datetime.now(timezone.utc).date()  # UTC NOT local
    paths: list[Path] = []
    for chunk_start, chunk_end in chunks:
        chunk_is_partial = skip_cache or chunk_end > today_utc  # OR not AND
        filename = _iem_cache_filename(
            chunk_start, chunk_end, suffix, partial=chunk_is_partial
        )
        dest = dest_dir / station.code / filename
        if dest.exists() and not chunk_is_partial:
            log.info("IEM ASOS cache hit: %s", dest)
            paths.append(dest)
            continue
        url = _build_iem_url(station, chunk_start, chunk_end, report_type)
        download_with_retry(url, dest)
        time.sleep(IEM_POLITE_DELAY)
        paths.append(dest)
    return paths
```

**Diff caveats from current tradewinds vs PR #85 monorepo path:**
1. Current tradewinds has ONE report-type per call (`report_type` is a keyword arg, default `3` = METAR). PR #85's `download_iem` loops over `_IEM_REPORT_TYPES` and does both METAR + SPECI in one call. **Keep the current tradewinds signature** (one report type per call) — this is a v0.14.1 lift contract decision, not in PERF-01 scope.
2. Tradewinds' helper is in `_fetchers/iem_asos.py`, not `ingest/sources/iem_gap_fill.py` — paths differ but the diff content is unchanged.

### HTTP timeout (`_internal/_http.py`) diff shape

**Current line 18:**
```python
HTTP_TIMEOUT = 30.0
```

**After lift:**
```python
# Round-2 review (PR #85) HIGH-2: 12x larger payload-per-request after the
# IEM chunk bump (90d→year). Pre-bump ASOS was ~150 KB/month (30s plenty);
# post-bump it's ~1.8 MB/year on the empirical KNYC sample. Tradewinds note:
# AWC + GHCNh + CLI did not change payload size — the bump is conservative
# overhead for those endpoints, not load-bearing.
HTTP_TIMEOUT = 60.0
```

### `research.py` orchestrator (NEW file)

`research.py` does not exist yet in tradewinds; ROADMAP shows `RESEARCH-01..05` in Phase 3. The CONTEXT decides Phase 1.5 places the orchestrator now. Recommendation: **stub `research.py` minimally in Phase 1.5** — define the ThreadPoolExecutor fan-out wrapping the existing fetcher functions; defer the full `pairs()`-equivalent join semantics to Phase 3.

The minimal Phase-1.5 `research.py` is purely a fan-out + join scaffold:

```python
# packages/core/src/tradewinds/research.py — NEW (Phase 1.5 stub)
from __future__ import annotations

import concurrent.futures
import time
from datetime import date
from typing import Any

# Lazy imports avoid the cross-package circular dependency (RESEARCH-05).
def research(station: str, from_date: date, to_date: date) -> dict[str, Any]:
    """Fan-out + join for cross-source observation fetch.

    Phase 1.5 scope: ThreadPoolExecutor parallelism only. The DataFrame
    return-shape contract (PARITY-01) is delivered by Phase 2 wiring.
    """
    from tradewinds.weather._fetchers.iem_asos import download_iem_asos
    from tradewinds.weather._fetchers.awc import fetch_awc_metars
    from tradewinds.weather._fetchers.ghcnh import download_ghcnh_range
    from tradewinds.weather._fetchers.iem_cli import download_cli_range
    # ... StationInfo resolution + dest_dir resolution (omitted)

    submitted_at: dict[str, float] = {}
    futures: dict[concurrent.futures.Future, str] = {}
    t_start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for name, callable_args in [
            ("iem.archive", (download_iem_asos, station_info, from_date, to_date, dest_dir)),
            ("awc.live", (fetch_awc_metars, [station_icao], 168)),
            ("ghcnh.archive", (download_ghcnh_range, station_id, from_date.year, to_date.year, dest_dir)),
            ("cli.archive", (download_cli_range, station_icao, from_date.year, to_date.year, dest_dir)),
        ]:
            f = ex.submit(*callable_args)
            submitted_at[name] = time.monotonic()
            futures[f] = name
        results: dict[str, Any] = {}
        per_source_times: dict[str, float] = {}
        for f in concurrent.futures.as_completed(futures):
            name = futures[f]
            per_source_times[name] = time.monotonic() - submitted_at[name]
            results[name] = f.result()  # propagates exceptions
    wall_time = time.monotonic() - t_start
    return {"results": results, "wall_time": wall_time, "per_source_times": per_source_times}
```

**Open question for planner:** does Phase 1.5 own creating `research.py`, or does it create a `_orchestration.py` helper that Phase 3 wires into `research.py` later? Both are workable. Recommendation: ship a minimal `research.py` in Phase 1.5 (per CONTEXT) and accept Phase 3 will replace its return shape. The empty pre-Phase-3 `research.py` won't conflict with the planned RESEARCH-01..05 work because those features compose on top of (don't replace) the fan-out.

## Rate-limit characterization methodology (PERF-05 spike)

**No published rate limits are available for AWC or NCEI GHCNh.** AWC documentation: silent. NCEI GHCNh documentation (`ghcnh_DOCUMENTATION.pdf`): no rate-limit section. The spike is the only path.

**IEM is the exception:** as of 2026-04-21, IEM publishes a 1-second per-IP throttle and a 1000-station-year request size limit ([VERIFIED: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help=`]). Tradewinds' `IEM_POLITE_DELAY = 1.0` already complies. The spike does NOT need to characterize IEM concurrent limits beyond confirming that the 1 req/sec throttle is enforced at IP level, not URL-path level (CRITICAL for PERF-04 multi-IEM-thread design — see Pitfall 5).

**Spike design recommendation:**

```bash
# spike/source_limits/awc_concurrent.py — recommended structure
# 1. Take an N ∈ {1, 2, 4, 8, 16} arg.
# 2. For each N, fire N concurrent GET to the AWC METAR endpoint for
#    distinct stations (KNYC, KLAX, KMIA, KMDW, ...) via ThreadPoolExecutor.
# 3. Measure: p50/p95/p99 response time, count of 429s, count of 5xx, mean
#    response body size, network-error count.
# 4. Repeat each N 5 times to get spread.
# 5. Print a markdown table to stdout that pastes into SOURCE-LIMITS.md.
```

**Metrics worth capturing (per N):**
- Wall time of the entire batch
- Per-request: p50, p95, p99 response time
- HTTP status code distribution (200 / 429 / 5xx counts)
- Mean + max response body size (1-year, 5-year requested where API permits)
- Error counts (TimeoutException, RequestError)

**Methodology for response-size measurement (1-yr / 5-yr):**
- AWC live: 7-day max — the "5-year" sample is moot. Document the 168-hour max in SOURCE-LIMITS.md and skip the size-by-window axis.
- GHCNh: one PSV per station-year. "5-year" = 5 separate requests. Measure per-PSV size separately; document.
- IEM ASOS: 1 yearly chunk for 1-year sample. 5-year = 5 separate chunked requests. Document per-chunk size.
- IEM CLI: 1 request per station-year (API granularity). Same as GHCNh.

**Spike duration:** 4 sources × 5 levels of N × 5 repeats × ~30 seconds/batch ≈ 50 minutes wall time, mostly idle (politeness pauses). Run end-to-end in one session; commit results immediately.

**Out of scope for the spike:** Polymarket, Kalshi (markets package, not weather), or any rate-limiting beyond observed-behavior characterization. The spike is descriptive, not prescriptive — it does not propose retry strategies; that's v0.2's adaptive-rate-limiting work.

## Test strategy for PERF-04 parallelism check

**Recommended boundary:**

| Test type | Tool | Purpose | Lives where |
|-----------|------|---------|-------------|
| Unit: chunker correctness | pytest only | `_iem_chunks` edge cases (leap year, reversed range, single chunk, boundary on Jan 1) | `packages/weather/tests/_fetchers/test_iem_chunks.py` |
| Unit: filename helper | pytest only | `_iem_cache_filename` with `partial=True` / `partial=False` | `packages/weather/tests/_fetchers/test_iem_asos.py` (existing file) |
| Unit: UTC-vs-local cutoff | pytest + `freezegun` or `mock.patch('datetime.datetime')` | Both `datetime.now(timezone.utc).date()` AND `date.today()` independently mocked to confirm UTC branch fires | `packages/weather/tests/_fetchers/test_iem_asos.py` |
| Unit: HTTP timeout constant | pytest | `assert HTTP_TIMEOUT == 60.0` | `packages/core/tests/_internal/test_http.py` (may need creation) |
| Integration: parallelism assertion | pytest-recording (vcrpy) | Record 4 source responses once; replay shows parallelism. Assert `wall_time ≤ max(per_source_t_i) * 1.2`. | `packages/core/tests/test_research_parallelism.py` (new) |
| Integration: parity gate (pre-merge) | pytest against captured `mostlyright==0.14.1` outputs | All 5 parity fixtures still byte-equal after chunker change | `tests/fixtures/parity/` (existing) |
| Live: KNYC 5-year backfill timing | `@pytest.mark.live` | Confirms ≤12 min wall time at 1 req/sec politeness. Run manually pre-merge, not in CI | `tests/test_live_perf.py` (new) |

**Parallelism assertion design (`wall_time ≤ max(per_source_t_i) * 1.2`):**

Naïve `time.monotonic()` measurement against recorded fixtures has a flakiness risk because cassette replay is FAST (no real network) and the wall-time bound becomes `0.01ms * 1.2 = 0.012ms` — well within scheduling noise. Two options:

- **Option A:** instrument the test fetchers to call `time.sleep(X)` deterministically inside the recorded path so cassette replay has a known per-source duration. Assert against a synthetic baseline.
- **Option B (recommended):** measure the assertion against the LIVE test (`@pytest.mark.live`) only. The CI recorded-fixture test simply asserts "no source's future raised; all four ran; results dict has 4 keys". The wall-time bound runs against live data manually pre-merge.

Option B is simpler and matches how rate-limit assertions actually work in practice (real network is the only environment that exercises real concurrency).

**Pre-flight cheap parity check (before running all 5 fixtures):**

```bash
# Run ONE fixture against monthly-chunker output and yearly-chunker output;
# byte-compare the DataFrame. If equal, the chunker change is merge-safe.
uv run pytest tests/test_parity.py::test_chunker_change_does_not_drift -x
```

Saves ~30 minutes if the chunker did change tie-break order — you find out before running the full 5-fixture sweep.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | All test/dev | ✓ | 0.11.3 (2026-04-01) | — |
| Python 3.11+ | All code | ✓ (3.11+ required per CLAUDE.md) | system-installed | — |
| `httpx` | Fetchers, parallelism | ✓ | 0.28.1 | — |
| `concurrent.futures` | PERF-04 | ✓ (stdlib) | Python 3.11+ | — |
| `pytest` | All tests | ✓ (project dev dep) | per `uv.lock` | — |
| `pytest-recording` | PERF-04 integration test | ✓ (project dev dep, per CLAUDE.md research) | per `uv.lock` | — |
| `freezegun` | Pitfall-2 UTC-vs-local test (optional) | UNKNOWN | — | `unittest.mock.patch` of `datetime.datetime` |
| Internet access for live spike | PERF-05 spike | required | — | — (spike is by-definition live) |
| AWC, IEM, GHCNh, NWS CLI endpoint reachability | PERF-05 spike + live perf test | required at spike-run-time | — | If down, spike result documents "endpoint X unreachable on YYYY-MM-DD" |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:** `freezegun` — if not installed, use stdlib `unittest.mock.patch('tradewinds.weather._fetchers.iem_asos.datetime')`.

## State of the Art

| Old approach (pre-PR-85) | Current approach (PR #85) | When changed | Impact |
|--------------------------|----------------------------|--------------|--------|
| IEM ASOS monthly chunks (`iem_<YYYYMM>_*.csv`) | IEM ASOS yearly chunks (`iem_{start_iso}_{end_iso}_*.csv` + `_partial` namespace) | 2026-05-12 (PR #85 merged) | 4–12x backfill speedup; CRITICAL silent-data-loss fix on cache poisoning |
| IEM MOS `CHUNK_DAYS=365` (timedelta arithmetic) | IEM MOS via shared `_iem_chunks` (calendar-aligned) | 2026-05-12 | Leap-year correctness |
| `HTTP_TIMEOUT = 30.0` | `HTTP_TIMEOUT = 60.0` | 2026-05-12 | Matches 12x payload increase |
| `date.today()` for chunk cutoff | `datetime.now(timezone.utc).date()` | 2026-05-12 round-2 | Non-UTC-host correctness (Europe/Prague bug) |
| `>` strict priority comparison (first-row-seen wins) | (unchanged — parity-critical) | — | Risk source for chunk-size parity drift |

**Deprecated/outdated within mostlyright:** the entire `_monthly_chunks` pattern. Tradewinds currently has it (PR-pre-85 lift from v0.14.1) and replaces it in Phase 1.5.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|----------------|
| A1 | AWC endpoint has no published concurrent-connection limit and tolerates ≥4 concurrent requests for distinct stations | Rate-limit methodology | If AWC has a stricter undocumented limit, PERF-04's 4-way fan-out gets 429s. Spike (PERF-05) tests this empirically. |
| A2 | NCEI GHCNh public archive (a CDN-fronted static-file path) has no rate limit relevant at 4-thread fan-out | Rate-limit methodology | Same as A1. GHCNh is static-PSV-per-station-year so likely fine; spike confirms. |
| A3 | IEM 1-second per-IP throttle applies across BOTH `asos.py` and `cli.py` endpoints (i.e. they share the same IP budget) | Pitfall 5 | If they have separate budgets, two IEM threads at 1 req/sec each are safe. Spike confirms; planner must read the spike output before finalizing PERF-04 wiring. |
| A4 | Phase 1.5's `research.py` is a NEW file (does not yet exist) and Phase 1.5 owns its creation as a stub | Code examples: research.py | If Phase 3 expects to author `research.py` from scratch, the Phase 1.5 stub creates a merge conflict. Confirm with the planner — recommend Phase 1.5 stubs the file with a clear "Phase 3 will extend" docstring. |
| A5 | The current tradewinds `_fetchers/iem_asos.py` is the only place to apply PERF-01/02 (no MOS fetcher yet exists in tradewinds) | Standard stack | If a MOS fetcher exists in tradewinds (or lands during Phase 1.5), it also needs the chunker change. **Verified by file inventory:** only `awc.py`, `ghcnh.py`, `iem_asos.py`, `iem_cli.py` in `_fetchers/`. No MOS fetcher in v0.1 scope. |
| A6 | The cache-filename change does not require migrating existing dev-cached files | Runtime State Inventory | If a developer has months of locally cached `iem_<YYYYMM>_*.csv` data they care about, they lose cache hits on next backfill and must re-fetch. PR #85 documented this as "harmless; next backfill regenerates"; tradewinds should adopt the same CHANGELOG note. |

## Open Questions

1. **PERF-04 IEM-IP-sharing strategy: Option A (lock), B (3-worker merge), or C (no-op pending spike)?**
   - What we know: IEM published a 1 sec/IP throttle in Apr 2026; tradewinds has two IEM threads (ASOS + CLI) in the proposed PERF-04 design.
   - What's unclear: does empirical IEM tolerate 2 concurrent 1-req/sec workers without 503s?
   - Recommendation: run PERF-05 spike FIRST, decide PERF-04 based on its output. Sequencing per CONTEXT is planner's discretion — recommend spike-first.

2. **Phase 1.5 `research.py` ownership boundary with Phase 3.**
   - What we know: ROADMAP places RESEARCH-01..05 in Phase 3.
   - What's unclear: is the Phase 1.5 `research.py` a stub, a working orchestrator (without Mode 1/Mode 2 dispatch), or a `_orchestration.py` helper that Phase 3 wires in?
   - Recommendation: Phase 1.5 creates `research.py` with the ThreadPoolExecutor fan-out as the only public surface. Phase 3 extends it with Mode 1/Mode 2 dispatch + DataFrame return shape. Documented as "Phase 3 will replace the return type" in the stub's docstring.

3. **Pre-merge parity sequencing.**
   - What we know: CONTEXT requires all 5 fixtures re-run pre-merge. Either (a) revert chunker, or (b) merge `>` → `>=` with deterministic secondary key.
   - What's unclear: which secondary key matters more — `source` or `chunk_start`?
   - Recommendation: if option (b) is taken, secondary key is `(source, chunk_start)` lexicographic. This is a hypothesis; actual empirical drift may suggest a different key. Decision deferred to post-spike per CONTEXT.

4. **Does `cli_<year>.json` cache need the same `_partial` treatment as `iem_<YYYY>_*.csv`?**
   - What we know: `iem_cli.py` already uses `cli_<year>.json` filenames (single year, atomic). The cache-poisoning vector in PR #85 was multi-month-chunks-collapsing-to-yearly-filename; that vector does not exist for CLI (already single-year, never partial-window-of-year because IEM CLI's API is whole-year only).
   - What's unclear: does an in-progress year (mid-2026 fetch of cli_2026.json) suffer the same partial-data hazard?
   - Recommendation: scope-discipline — Phase 1.5 lift is verbatim from PR #85 which changed only ASOS, not CLI. Leave `cli_<year>.json` unchanged. Document the analogous hazard for CLI in CHANGELOG and defer to v0.2 if needed. (PR #85 itself did not touch CLI.)

## Plan-shape recommendation

Given CONTEXT's discretion on plan granularity, recommend **3 plans**:

1. **Plan 1: Lift PR #85 (PERF-01 + PERF-02 + PERF-03)** — single coherent lift, all three changes review together because they're a single PR upstream. Includes the `_iem_chunks.py` new module, `iem_asos.py` chunker + cache-filename change, and `_http.py` timeout bump. Parity fixture pre-flight (single-fixture check) is part of this plan's exit criteria.
2. **Plan 2: PERF-05 rate-limit spike** — runs BEFORE PERF-04. Produces `SOURCE-LIMITS.md` + `spike/source_limits/*.py`. Output of this plan informs PERF-04 design (Option A/B/C from Pitfall 5).
3. **Plan 3: PERF-04 cross-source parallelism** — uses spike output to choose IEM-sharing strategy. Creates `research.py` stub with `ThreadPoolExecutor(max_workers=4)` fan-out. Recorded-fixture integration test for parallelism check. Live KNYC 5-year backfill timing test. Full 5-fixture parity re-run as exit gate.

Dependencies: Plan 1 has no upstream deps (Phase 1 done). Plan 2 has no code deps; could run in parallel with Plan 1 but recommend serial for review-panel attention efficiency. Plan 3 depends on Plan 1 (uses chunker) AND Plan 2 (uses rate-limit numbers).

## Sources

### Primary (HIGH confidence)

- **PR #85 full diff via `gh api`** (commit `cf9eb85`, 2026-05-12):
  - `https://api.github.com/repos/Tarabcak/mostlyright/contents/ingest/sources/_iem_chunks.py?ref=cf9eb85`
  - `https://api.github.com/repos/Tarabcak/mostlyright/contents/ingest/sources/_http.py?ref=cf9eb85`
  - `https://api.github.com/repos/Tarabcak/mostlyright/contents/ingest/sources/iem_gap_fill.py?ref=cf9eb85`
  - `https://github.com/Tarabcak/mostlyright/pull/85` (PR summary, file list, validation results)
- **IEM ASOS endpoint documentation:** `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help=` — 1-second per-IP throttle (2026-04-21), 1000 station-year limit (2026-01-23), 422 on overlimit, 503 on heavy load
- **Python concurrent.futures docs:** `https://docs.python.org/3/library/concurrent.futures.html` — `Future.result()` exception semantics, `as_completed`, `ThreadPoolExecutor`
- **Project source code (worktree-local):** `packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py`, `packages/core/src/tradewinds/_internal/_http.py`, `packages/core/src/tradewinds/_internal/merge/observations.py` — current state to be modified
- **CONTEXT.md** (this phase) — locked decisions verbatim
- **ROADMAP.md** lines 17, 37–53 — Phase 1.5 section + parity-gate handling
- **REQUIREMENTS.md** PERF-01..05

### Secondary (MEDIUM confidence)

- **httpx thread-safety (encode/httpx#1633):** "HTTPX is intended to be thread-safe" — maintainer statement, verified via web search; not directly fetched (404 on individual discussion fetch)
- **PR #85 reviewer-context inline comments (round-2 HIGH findings on UTC-vs-local and reversed-range guards)** — extracted from the file-level docstrings retrieved via `gh api`; classed as MEDIUM because they're the upstream maintainer's narrative, not independently verified against the actual production incident logs

### Tertiary (LOW confidence — flagged for spike validation)

- **AWC concurrent-connection tolerance:** no published numbers. Spike (PERF-05) will produce empirical data.
- **NCEI GHCNh rate limits:** no published numbers; static-file CDN distribution suggests no hard limit but unconfirmed. Spike (PERF-05).
- **Whether IEM `asos.py` and `cli.py` share per-IP throttle budgets:** assumed yes (single domain → single IP → single budget) but not proven. Spike confirms.

## Metadata

**Confidence breakdown:**

- **Standard Stack:** HIGH — all libraries pinned in CLAUDE.md, no new deps proposed
- **Architecture patterns:** HIGH for PR #85 lift (verbatim diff retrieved); HIGH for ThreadPoolExecutor (stdlib pattern, decades-stable)
- **Cache-poison fix subtleties:** HIGH — UTC-not-local and OR-not-AND both verified against PR #85 source code
- **IEM rate limits:** HIGH — endpoint documentation directly states 1-sec per-IP throttle
- **AWC/GHCNh rate limits:** LOW — no published numbers; spike-empirical only
- **Parity drift risk from chunker change:** MEDIUM — mechanism is understood (strict `>` ties depend on row order); magnitude is unmeasured

**Research date:** 2026-05-22
**Valid until:** 2026-06-22 for PR #85 content (immutable git history); 2026-06-05 for IEM rate-limit numbers (recent policy changes possible); spike output (PERF-05) replaces all rate-limit-related claims when committed
