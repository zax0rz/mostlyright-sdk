---
phase: 11
plan: 01
wave: 1
depends_on: [10]
files_modified:
  # Python
  - packages/core/src/tradewinds/live/__init__.py
  - packages/core/src/tradewinds/live/_stream.py
  - packages/core/src/tradewinds/live/_latest.py
  - packages/core/src/tradewinds/live/_sources.py
  - packages/core/src/tradewinds/core/exceptions.py
  - packages/core/src/tradewinds/__init__.py
  - packages/core/tests/test_live_stream.py
  - packages/core/tests/test_live_latest.py
  # TS
  - packages-ts/weather/src/live/index.ts
  - packages-ts/weather/src/live/stream.ts
  - packages-ts/weather/src/live/latest.ts
  - packages-ts/weather/src/live/sources.ts
  - packages-ts/weather/src/index.ts
  - packages-ts/core/src/exceptions/index.ts
  - packages-ts/meta/src/index.ts
  - packages-ts/weather/tests/live/stream.test.ts
  - packages-ts/weather/tests/live/latest.test.ts
  # Docs
  - docs/live-streaming.md
requirements: [LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, LIVE-06, LIVE-07, LIVE-08, LIVE-09]
autonomous: true
review_panel:
  - codex high
  - python-architect
  - typescript-architect
must_haves:
  truths:
    - live.stream() is an async generator that yields one observation row per polled tick
    - source="awc" (default) and source="iem" both supported; mutually exclusive
    - per-source polite floors enforced (AWC=30s, IEM=60s) — caller cannot poll faster
    - latest() returns ONE observation row (same fetch path as stream(); no loop)
    - both surfaces are SINGLE-SOURCE — no fusion, no cache writes, no QC
    - rows emitted carry per-source `source` identity tag (`awc.live` / `iem.live`)
    - dedup by observed_at — successive ticks for the same observation do NOT re-yield
    - cancellation via `async for` break / iterator.aclose() is clean (no zombie httpx tasks)
    - empty-response ticks do not abort the stream — backoff to next polite-floor cycle
    - TS surface mirrors Python via AsyncIterable + identical option shape
  artifacts:
    - packages/core/src/tradewinds/live/__init__.py (new module)
    - packages/core/src/tradewinds/live/_stream.py (new — async generator)
    - packages/core/src/tradewinds/live/_latest.py (new — one-shot)
    - packages/core/src/tradewinds/live/_sources.py (new — source registry + floors)
    - packages/core/src/tradewinds/core/exceptions.py (LiveStreamError, NoLiveDataError added)
    - packages/core/tests/test_live_stream.py (new — 14 tests)
    - packages/core/tests/test_live_latest.py (new — 8 tests)
    - packages-ts/weather/src/live/{index,stream,latest,sources}.ts (new)
    - packages-ts/weather/tests/live/{stream,latest}.test.ts (new — 22 tests)
    - docs/live-streaming.md (new — 7 sections + 3 patterns)
  key_links:
    - .planning/ROADMAP.md#phase-11
    - .planning/REVIEW-DISCIPLINE.md
    - packages/weather/src/tradewinds/weather/_fetchers/awc.py
    - packages/weather/src/tradewinds/weather/_awc.py (awc_to_observation parser)
    - packages-ts/weather/src/_fetchers/awc.ts
    - packages-ts/weather/src/_parsers/awc.ts
---

# Phase 11: Live Streaming Iterator

## TS Parity

Phase 11 is **dual-SDK** (paired Python + TS in same merge per CROSS-SDK-SYNC.md §2). The streaming/latest surfaces ship for both SDKs in the same PR.

| Python | TS counterpart |
|---|---|
| `tradewinds.live.stream(station, *, source="awc", poll_seconds=None)` async generator | `import { stream } from "@tradewinds/weather/live"` AsyncIterable |
| `tradewinds.live.latest(station, *, source="awc")` one-shot async | `import { latest } from "@tradewinds/weather/live"` Promise |
| `LiveStreamError(TradewindsError)` | `LiveStreamError extends TradewindsError` |
| `NoLiveDataError(LiveStreamError)` | `NoLiveDataError extends LiveStreamError` |
| Polite floors: `AWC=30s`, `IEM=60s` enforced in `_sources.py` | Same constants in `sources.ts` |

**No TS-only constraints triggered.** Streaming is pure logic over the existing AWC/IEM fetchers (already CORS-documented per TS-CORS-MATRIX.md). Bundle delta ≤2KB (one new file per package surface).

## Objective

Add a tradewinds **ticker** surface — `live.stream()` continuously polls a single source and yields fresh observations, `latest()` returns one. This is intentionally **different from `research()`**:

| Surface | Role | Sources | Cache | QC | Loop |
|---|---|---|---|---|---|
| `research()` | DATABASE (training pairs, settlement) | AWC + IEM + GHCNh + CLI (fused) | Yes (parquet) | Yes (Phase 3.4) | No — point-in-time |
| `live.stream()` | TICKER (real-time monitoring) | ONE of AWC \| IEM | No | No | Yes — async generator |
| `live.latest()` | TICKER one-shot | ONE of AWC \| IEM | No | No | No |

`research()` stays unchanged — Phase 11 is purely additive.

## Tasks

### Wave 1 (Plan 11-01) — Scaffolding

<read_first>
- packages/weather/src/tradewinds/weather/_fetchers/awc.py (fetch_awc_metars)
- packages/weather/src/tradewinds/weather/_awc.py (awc_to_observation)
- packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py (download_iem_asos)
- packages/core/src/tradewinds/core/exceptions.py (TradewindsError + subclass pattern)
- packages-ts/weather/src/_fetchers/awc.ts + _parsers/awc.ts (TS analogues)
- packages-ts/core/src/exceptions/index.ts (TradewindsError TS hierarchy)
</read_first>

<action>
**Python (`packages/core/src/tradewinds/live/`):**
- `__init__.py` re-exports `stream`, `latest`, `LiveStreamError`, `NoLiveDataError`, `SUPPORTED_SOURCES`.
- `_sources.py` defines `POLITE_FLOORS_S = {"awc": 30.0, "iem": 60.0}` + `SUPPORTED_SOURCES = ("awc", "iem")` + `validate_source(s: str) -> str` (normalizes case, raises ValueError on unknown).
- `_stream.py` defines `async def stream(station: str, *, source: str = "awc", poll_seconds: float | None = None) -> AsyncIterator[dict]`. Body delegates to `_latest.py` for the per-tick fetch + dedup by `observed_at`.
- `_latest.py` defines `async def latest(station: str, *, source: str = "awc") -> dict`. Uses `asyncio.to_thread()` around the existing sync `fetch_awc_metars` / `download_iem_asos` calls. Returns the most-recent observation row (parsed via `awc_to_observation` / IEM parser). Raises `NoLiveDataError` if fetcher returns empty.

**Exceptions (`packages/core/src/tradewinds/core/exceptions.py`):**
- `class LiveStreamError(TradewindsError)` — `default_error_code = "LIVE_STREAM_ERROR"`.
- `class NoLiveDataError(LiveStreamError)` — `default_error_code = "NO_LIVE_DATA"`. Carries `station: str` + `source: str` attributes; surfaced in `_payload()`.

**Public surface (`packages/core/src/tradewinds/__init__.py`):**
- Add `from tradewinds import live` re-export so callers do `tradewinds.live.stream(...)`.

**TS (`packages-ts/weather/src/live/`):**
- `index.ts` re-exports.
- `sources.ts` mirrors Python: `POLITE_FLOORS_S = { awc: 30, iem: 60 } as const` + `SUPPORTED_SOURCES = ["awc", "iem"] as const` + `validateSource(s: string): "awc" | "iem"`.
- `stream.ts`: `export async function* stream(station: string, opts?: { source?: "awc" | "iem"; pollSeconds?: number }): AsyncGenerator<Observation>`.
- `latest.ts`: `export async function latest(station: string, opts?: { source?: "awc" | "iem" }): Promise<Observation>`.

**TS exceptions (`packages-ts/core/src/exceptions/index.ts`):**
- `class LiveStreamError extends TradewindsError` with `error_code = "LIVE_STREAM_ERROR"`.
- `class NoLiveDataError extends LiveStreamError` with `error_code = "NO_LIVE_DATA"`, station/source on payload.

**TS meta (`packages-ts/meta/src/index.ts`):**
- Re-export `stream`, `latest`, `LiveStreamError`, `NoLiveDataError`.

**TS weather index (`packages-ts/weather/src/index.ts`):**
- Re-export the `live/*` surface so `import { stream } from "@tradewinds/weather"` works (in addition to the subpath import).
</action>

<acceptance_criteria>
- `from tradewinds.live import stream, latest, LiveStreamError, NoLiveDataError` works.
- `import { stream, latest } from "@tradewinds/weather/live"` and `from "@tradewinds/weather"` and `from "tradewinds"` all work.
- `validate_source("AWC")` returns `"awc"` (case-insensitive normalize).
- `validate_source("nws")` raises `ValueError`.
- `NoLiveDataError("no data", station="KNYC", source="awc.live").to_dict()` includes both `station` + `source` in payload.
- `POLITE_FLOORS_S["awc"] == 30.0` and `POLITE_FLOORS_S["iem"] == 60.0`.
</acceptance_criteria>

### Wave 2 (Plan 11-02) — Python TDD (22 tests)

<read_first>
- packages/weather/tests/test_fetcher_awc.py (existing AWC test patterns)
- packages/core/tests/conftest.py (httpx mock pattern)
- packages/core/src/tradewinds/_internal/_http.py (retry semantics)
</read_first>

<action>
Build `_stream.py` + `_latest.py` to make these tests pass. Mock `fetch_awc_metars` and `download_iem_asos` with monkeypatch — DO NOT hit the network. Use `pytest.mark.asyncio` for stream tests.

**`packages/core/tests/test_live_latest.py` (8 tests):**
1. `test_latest_awc_returns_observation_row` — mocked fetcher returns one METAR; `latest("KNYC")` returns row with `source == "awc.live"` and required keys.
2. `test_latest_awc_default_source` — no `source=` kwarg → defaults to AWC.
3. `test_latest_iem_source_selectable` — `source="iem"` invokes IEM fetcher path, not AWC.
4. `test_latest_unknown_source_raises` — `source="ghcnh"` raises `ValueError`.
5. `test_latest_empty_response_raises_no_live_data` — mocked fetcher returns `[]` → `NoLiveDataError`.
6. `test_latest_no_live_data_error_carries_station_and_source` — `NoLiveDataError.to_dict()` includes both.
7. `test_latest_returns_most_recent_when_multiple` — fetcher returns 3 METARs; latest() picks largest `obsTime`.
8. `test_latest_strips_unparseable_metars` — fetcher returns 2 METARs, one with bad icaoId; latest() picks the valid one.

**`packages/core/tests/test_live_stream.py` (14 tests):**
1. `test_stream_yields_observations` — mocked fetcher returns metars; `async for row in stream("KNYC")` yields rows.
2. `test_stream_default_source_awc` — `source=` omitted → AWC fetcher invoked.
3. `test_stream_iem_source` — `source="iem"` invokes IEM fetcher.
4. `test_stream_dedup_by_observed_at` — same observation served twice in a row → only first yielded.
5. `test_stream_yields_new_observation_when_obs_time_advances` — second poll returns NEWER `obsTime` → second row yielded.
6. `test_stream_unknown_source_raises` — `source="bogus"` raises `ValueError` before first poll.
7. `test_stream_polite_floor_awc_30s_default` — no `poll_seconds=` → uses 30s for AWC.
8. `test_stream_polite_floor_iem_60s_default` — no `poll_seconds=`, `source="iem"` → uses 60s.
9. `test_stream_raises_below_polite_floor` — `poll_seconds=10` with `source="awc"` raises `ValueError` (below 30s floor).
10. `test_stream_accepts_above_polite_floor` — `poll_seconds=120` with `source="awc"` works.
11. `test_stream_empty_tick_does_not_abort` — first poll returns `[]`, second returns one METAR → stream yields exactly one row (no exception in between).
12. `test_stream_cancellation_via_break` — `async for` + `break` cleanly exits (sleep task cancelled, no warnings).
13. `test_stream_source_tag_on_row_awc` — row's `source` field is `"awc.live"`.
14. `test_stream_source_tag_on_row_iem` — row's `source` field is `"iem.live"`.

**Polite-floor sleep should be patchable** — use `asyncio.sleep` so tests can monkeypatch it to a no-op for fast runs.
</action>

<acceptance_criteria>
- All 22 Python tests pass (`uv run pytest packages/core/tests/test_live_stream.py packages/core/tests/test_live_latest.py -v`).
- Stream tests use `pytest.mark.asyncio` and complete in <1s wall time (sleep monkeypatched).
- No new live network tests (no `@pytest.mark.live` added).
- `uv run pytest -m "not live" -q` total count rises by 22.
</acceptance_criteria>

### Wave 2 (Plan 11-03) — TS TDD (22 tests)

<read_first>
- packages-ts/weather/tests/awc.test.ts (existing AWC test patterns + msw recordings)
- packages-ts/weather/vitest.config.ts
- packages-ts/core/src/exceptions/index.ts (toDict pattern)
</read_first>

<action>
Mirror the 22 Python tests in TS. Use vitest's `vi.useFakeTimers()` for the polite-floor sleep, mock fetch via `vi.spyOn(globalThis, "fetch")` with canned responses. Tests live at `packages-ts/weather/tests/live/{stream,latest}.test.ts`.

The 22 test names are the camelCase analogues of the Python ones (e.g. `testStreamPoliteFloorAwc30sDefault` etc.).
</action>

<acceptance_criteria>
- All 22 TS tests pass (`pnpm --filter @tradewinds/weather test`).
- Tests use `vi.useFakeTimers()` for poll-loop sleeps; complete in <1s wall time.
- No new live network tests.
- TS test count rises by 22.
</acceptance_criteria>

### Wave 3 (Plan 11-04) — Docs + review + merge

<read_first>
- docs/ (existing docs structure)
- README.md (existing quickstart)
</read_first>

<action>
Write `docs/live-streaming.md` with 7 sections:
1. **Overview** — when to use `live.stream()` vs `research()`. Clearly state the ticker-vs-database split.
2. **API: `live.stream()`** — Python signature, TS signature, return shape (one row per yield), per-row schema.
3. **API: `live.latest()`** — same.
4. **Sources** — AWC (default, fastest) vs IEM (~10min delay, alternative for AWC outages). Source identity tag (`awc.live` / `iem.live`).
5. **Polite floors** — 30s AWC, 60s IEM, with rationale (don't hammer public APIs).
6. **Async patterns** — Python `async for` + `break`, TS `for await` + `AbortController`.
7. **FAQ** — "Can I write to parquet from stream?" (no, use research() with cache=True), "Can I fuse AWC+IEM?" (no, this is single-source on purpose), "What if my poll is below the floor?" (raises ValueError at startup).

+3 usage patterns at the bottom:
- **Continuous monitoring** — `async for row in tradewinds.live.stream("KNYC"): print(row["temp_f"])`
- **Single-shot poll** — `row = await tradewinds.live.latest("KNYC")` in a cron job
- **Multi-station fan-out** — `asyncio.gather(stream("KNYC"), stream("KLAX"))` — one task per station, polite floors apply per-task.

**Review:** run codex + python-architect + typescript-architect in parallel against the branch diff vs main. Cap at 5 iterations. Loop until all PASS or 5 iter hit (then escalate).

**STATE.md:** update `last_activity` + add Phase 11 closeout block (mirror Phase 10's closeout structure).

**Merge:** if Phase 12 (rename) lands first, rebase. Use `git merge --no-ff phase-11/live-streaming-iterator` from main.
</action>

<acceptance_criteria>
- `docs/live-streaming.md` exists with all 7 sections + 3 patterns.
- All Python (~1971 + 22) and TS (~1323 + 22) tests pass.
- Codex + Python Architect + TypeScript Architect all return PASS (or 5-iter cap reached + escalation noted).
- `.planning/STATE.md` updated.
- Branch merged to main with `--no-ff`.
</acceptance_criteria>
