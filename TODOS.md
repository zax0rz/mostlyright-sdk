# TODOS

Captured from `/office-hours` and `/plan-eng-review` on 2026-05-21. Format follows monorepo TODOS.md convention.

## Pin dependencies to monorepo-v0.14.1's tested versions on Day 1

**What:** When writing or updating each `packages/*/pyproject.toml`, copy exact version pins from `../monorepo-v0.14.1/pyproject.toml` for httpx, jsonschema, pyarrow, pandas, filelock. Do NOT let `uv add` resolve fresh versions.

**Why:** monorepo has 800+ tests against a specific dep set. Fresh resolution inherits subtle differences (e.g., pyarrow 14.x vs 15.x parquet behavior, pandas 2.1 vs 2.2 dtype promotion). Pinning inherits the test coverage. v0.14.1 deps are: `httpx>=0.27`, `jsonschema>=4.21`, `tzdata; sys_platform == 'win32'`, optional `parquet` extra `pyarrow>=17.0, pandas>=2.2`. Initial pyproject.toml files already follow these floors; tighten if monorepo-v0.14.1's pyproject reveals tighter pins.

**Depends on:** Day 0.5 (Vu's git worktree of v0.14.1 must exist first).

**Added:** 2026-05-21 (plan-eng-review D8)

## Document first-fetch slowness in README; flag as paid-tier candidate

**What:** Add a "Performance characteristics" section to the workspace `README.md` explaining that the first call for a large date range hits public APIs sequentially (minutes to hours for 5-year ranges across multiple stations); subsequent calls hit the local parquet cache and are fast. Mention that a future paid tier will offer CDN-primed cache for instant first fetch.

**Why:** Without this note, Vojtech (or any user) may think the SDK is broken on their first long query. It's a known trade-off of the local-first model, not a bug. Also informs the monetization conversation (Premise 4 in the design doc).

**Depends on:** Day 4 (Lane F README writing).

**Added:** 2026-05-21 (plan-eng-review D7)

## Document concurrent cache-writer behavior in README

**What:** Note in `README.md` that `filelock` serializes concurrent writes to the same station/month cache file. Four processes calling `tradewinds.research(station="KNYC", ...)` at first-fetch will serialize on the lock; only one fetches AWC, the others wait. Independent stations parallelize fine.

**Why:** Surface the trade-off so it doesn't get filed as a bug later. Correct behavior, not a perf regression.

**Depends on:** Day 4 (Lane F README writing).

**Added:** 2026-05-21 (plan-eng-review perf finding)

## (Open) — Add as you go

Empty slots for future TODOs. Use the same format: What / Why / Depends on / Added.
