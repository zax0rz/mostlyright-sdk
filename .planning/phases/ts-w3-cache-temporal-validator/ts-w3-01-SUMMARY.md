---
phase: ts-w3-cache-temporal-validator
plan: 01
subsystem: internal/cache
tags: [cache, memorystore, fsstore, proper-lockfile, contract-suite]
status: complete
commits:
  - 643af97 feat(ts-w3/01): CacheStore + MemoryStore + FsStore + subpath export
test_delta: +36 (4 types + 15 memory + 17 fs)
---

# TS-W3 Plan 01: Cache Foundation Summary

Lands the plumbing for `@tradewinds/core/internal/cache`.

## What shipped
- `types.ts` — CacheStore interface, CacheEntry, CacheSetOptions, lockKeyFor
- `memory.ts` — MemoryStore (Map + structuredClone isolation + per-key
  promise chain + absorber tail)
- `fs.ts` — FsStore (node:fs/promises atomic write via .tmp + rename;
  proper-lockfile for cross-process + in-process FIFO chain for
  deterministic same-process ordering; `defaultFsRoot()` honors
  TRADEWINDS_CACHE_DIR or falls back to ~/.tradewinds/cache-ts)
- `index.ts` barrel + `./internal/cache` subpath in package.json + tsup
- `_contract.ts` shared CacheStore contract suite (NON-test file so
  biome's noExportsInTest doesn't fire)

## Key decisions
- **Cache root distinct from Python's:** `~/.tradewinds/cache-ts` so JSON
  envelopes here can't shadow Python parquet files (per TS-CACHE-02).
- **In-process chain on top of proper-lockfile:** proper-lockfile's retry-
  based contention resolution isn't FIFO; the chain layer guarantees
  same-process ordering matches MemoryStore semantics.
- **Absorber tail on lock chain:** prevents unhandled-rejection warnings
  when `fn()` throws and no later caller chains in.

## Test delta
Core: 259 → 295 (+36).
