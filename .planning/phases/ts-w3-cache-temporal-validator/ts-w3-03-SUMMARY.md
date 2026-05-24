---
phase: ts-w3-cache-temporal-validator
plan: 03
subsystem: internal/cache
tags: [skip-rules, cache-keys, lst-offset, ts-new-divergence, fixture]
status: complete
commits:
  - 80ce29f feat(ts-w3/03): cache-skip rules + key generators + 5-case fixture
test_delta: +24 (16 skip-rules + 8 keys)
---

# TS-W3 Plan 03: Skip Rules + Key Generators Summary

Pure predicates + key strings for the cache layer.

## What shipped
- `skip-rules.ts`:
  - `shouldSkipCacheForCurrentLstMonth(station, year, month, now?)`
  - `shouldSkipCacheForCurrentLstYear(station, year, now?)`
  - `isLiveSource(source)` — byte-equivalent to Python `_is_live_source`
  - **TS-NEW** `isWithinVolatileWindow(eventDate, archiveAsOf, days=30)`
    — TS-CACHE-02 requirement not present in Python (back-port tracked
    as CROSS-SDK-SYNC parity ticket; documented in the module header).
- `keys.ts`:
  - `cacheKeyForObservations("KNYC", 2025, 1)` →
    `"tradewinds:v1:observations:KNYC:2025:01"` (zero-padded month).
  - `cacheKeyForClimate("KNYC", 2025)` →
    `"tradewinds:v1:climate:KNYC:2025"`.
  - Both validate year ∈ [1900, 2100] + month ∈ [1, 12] (RangeError).
- `tests/internal/cache/fixtures/skip-rules-behavior.json` — 5 canonical
  cases (KNYC current month, last month, .live source, volatile-window,
  RJTT UTC+9 year-wrap).

## Key decisions
- **`now: Date` test seam** on every predicate. Production callers pass
  `new Date()` once (plan 06); tests pass fixed instants.
- **RJTT chosen for case 5** because it's in the codegen station
  registry with `tz: "Asia/Tokyo"` — confirmed via grep.
- **TS-NEW divergence documented in-source** (TS-W0 iter-1 lesson:
  silent cross-SDK drift triggers HIGH severity).

## Test delta
Core: 314 → 338 (+24).
