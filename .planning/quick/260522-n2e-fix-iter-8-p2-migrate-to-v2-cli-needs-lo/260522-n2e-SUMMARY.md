---
task_id: 260522-n2e
title: Fix Codex iter-8 P2 — migrate_to_v2() CLI needs lock around _legacy_v014_to_v021_migration
date: 2026-05-22
branch: planning/v01-intl-nwp-polymarket
type: quick-fix
severity: HIGH (P2)
finding_source: Codex review iteration 8
phase: 02.1
plan: 03
status: complete
---

# 260522-n2e — Fix Codex iter-8 P2: migrate_to_v2() CLI needs lock around lock-free migration helper

## Problem

Codex iteration-8 P2 finding (HIGH): after iteration-7 P1 refactored `_legacy_v014_to_v021_migration` to be **lock-free** (assuming the caller holds the per-file lock — the "single-locking-layer invariant"), the Task 3 CLI helper `migrate_to_v2()` in `02.1-PLAN-03-cache-layer-refactor.md` still called the migration helper **directly with no lock**.

This re-opened the exact race the iter-7 P1 fix was meant to close:

- Two `migrate_to_v2()` processes (or one CLI + one concurrent `write_cache`/`read_cache` auto-upgrade) could enter the migration code path concurrently for the same `(station, year, month)` ledger.
- With the helper lock-free and the CLI unlocked, `_atomic_write` torn-write / duplicate-ingestion-id / `.legacy` rename loss become possible.
- Lock coverage existed for only two of the three call sites (`write_cache` and `read_cache` auto-upgrade), violating the single-locking-layer invariant the iter-7 P1 mitigation depended on.

## Fix

Four edits to `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md`:

### Edit A — `migrate_to_v2()` body (Task 3 Python code block, lines ~356-376)

Wrap the `_legacy_v014_to_v021_migration` call in `FileLock(str(ledger_path) + ".lock")` with re-check inside lock:

```python
ledger_path = cache._ledger_path(cache_root, station, year, month)
if ledger_path.exists():
    _LOG.info("Skip (ledger exists): %s", legacy_path)
    continue
# Acquire the per-file lock BEFORE calling the lock-free migration helper
# (codex iter-8 P2 mitigation; same lock pattern used by write_cache step 3a
# and read_cache auto-upgrade step 4e — single-locking-layer invariant).
from filelock import FileLock
lock_path = str(ledger_path) + ".lock"
with FileLock(lock_path, timeout=cache.LOCK_TIMEOUT_SECONDS):
    # Re-check inside lock: another process may have completed migration while we waited.
    if ledger_path.exists():
        _LOG.info("Skip (ledger now exists, raced): %s", legacy_path)
        continue
    if dry_run:
        _LOG.info("[DRY RUN] Would migrate %s -> %s", legacy_path, ledger_path)
        continue
    rows = cache._legacy_v014_to_v021_migration(legacy_path, ledger_path, station, year, month)
    total_rows += rows
    _LOG.info("Migrated %d rows: %s -> %s", rows, legacy_path, ledger_path)
```

Notes on design choices:
- **Per-file lock, NOT directory lock** — matches the exact lock pattern used by `write_cache` step 3a and `read_cache` auto-upgrade step 4e. A directory lock would over-serialize unrelated months.
- **Re-check inside the lock** — another process (CLI or `write_cache` / `read_cache` auto-upgrade) may have completed migration while we waited on the lock; second-arriver becomes a clean no-op rather than wasting work or risking inconsistency.
- **`dry_run` runs INSIDE the lock** — captures any concurrent migration that completes between the outer `ledger_path.exists()` check and our actual decision, making "would migrate" output correct on shared cache roots. Lock acquisition is cheap; correctness wins.
- **`cache.LOCK_TIMEOUT_SECONDS`** — reuses the existing constant used by `write_cache` / `read_cache` for a single source of truth on timeout behavior.
- The outer `for legacy_path in sorted(...)` loop, the `try/except` path parsing, and the `ledger_path = cache._ledger_path(...)` resolution all stay **outside** the lock — the lock scope is intentionally minimal (only the migration write itself).

### Edit B — Acceptance criteria (Task 3 `<acceptance_criteria>`, lines ~406-407)

Added two grep-checkable invariants right after the `climate` grep check:

- `grep -c "FileLock\|with FileLock" packages/weather/src/tradewinds/weather/cache_migration.py` returns ≥ 1 (CLI acquires the per-file lock before calling lock-free migration helper — codex iter-8 P2 mitigation)
- `grep -cE "ledger_path.with_suffix\(.\.lock.\)|str\(ledger_path\) \+ .\.lock." packages/weather/src/tradewinds/weather/cache_migration.py` returns ≥ 1 (per-file lock pattern, NOT directory lock)

The second grep is specifically authored to **fail loudly if someone "fixes" the race by adding a directory lock** instead of the per-file lock pattern.

### Edit C — Threat T-02.1.3-02 mitigation (lines ~431)

Extended the existing `T-02.1.3-02` mitigation paragraph (`Auto-upgrade race scenarios`) with an additional clause explicitly covering the CLI:

> ...; the CLI `migrate_to_v2()` (Task 3) ALSO acquires the per-file lock with a re-check inside the locked section before calling the lock-free migration helper — codex iter-8 P2 mitigation completes the lock coverage across ALL THREE call sites (write_cache, read_cache auto-upgrade, and migrate_to_v2 CLI).

The threat register now documents lock coverage as universal across all three call sites, restoring the single-locking-layer invariant the iter-7 P1 mitigation depended on.

### Edit D — Done line (Task 3 `<done>`, line ~412)

Appended "CLI lock-pattern unified with write_cache and read_cache auto-upgrade":

> `migrate_to_v2() CLI exists, idempotent, deterministic ingestion_id, dry-run mode, climate skipped, subprocess invokable; CLI lock-pattern unified with write_cache and read_cache auto-upgrade. 8 tests pass.`

This makes the lock-pattern unification a first-class success criterion for the task, not just a buried threat-model detail.

## Why this matters

The iteration-7 P1 fix's value depended on the invariant: **every call into the lock-free helper must be lock-guarded by the caller**. The iter-8 P2 finding identified that one of the three callers (the CLI) didn't honor that invariant. Without this fix:

- Running `python -m tradewinds.weather.cache_migration` on a cache root that's simultaneously serving a live `research()` session would race on every `(station, year, month)` with extant legacy data.
- The race window is the entire migration helper duration (read → transform → atomic write → rename), which can be seconds for multi-MB parquets — easily long enough to lose to OS scheduling.
- Outcomes range from torn parquets (caught by `_atomic_write`'s tmp+replace, but the migrated rows are silently dropped) to duplicate `ingestion_id` rows (cross-machine determinism guarantees break in T-02.1.3-05).

By unifying lock coverage across all three call sites, the threat model's "Auto-upgrade race scenarios" mitigation is now structurally complete — the CLI is no longer a backdoor around the locking layer.

## Files changed

- `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` (4 edits in Task 3)

## Acceptance verification (grep-checkable post-fix)

Once Task 3 ships `cache_migration.py`, the new grep invariants in Edit B will gate the fix:

- `FileLock` import + usage present in the CLI module → fails build if removed.
- Per-file lock-path pattern (`str(ledger_path) + ".lock"` OR `ledger_path.with_suffix(".lock")`) present → fails build if someone substitutes a directory lock.

## Out of scope / explicitly not changed

- `_legacy_v014_to_v021_migration` itself stays lock-free (iter-7 P1 invariant preserved).
- `write_cache` and `read_cache` auto-upgrade paths already lock correctly (Task 1 step 3a + Task 2 step 4e) — untouched.
- Test 8 (subprocess) doesn't need an explicit "concurrent migrate_to_v2 lock test" because the lock invariant is enforced structurally via the grep gate; adding such a test is a Wave 3 implementation concern, not a plan-spec concern.

## Commit

Single atomic commit on `planning/v01-intl-nwp-polymarket`:

> `docs(02.1-plan-03): lock migrate_to_v2 around lock-free migration helper (iter-8 P2)`

## Self-check

- [x] Edit A — `migrate_to_v2()` body now acquires `FileLock(str(ledger_path) + ".lock", timeout=cache.LOCK_TIMEOUT_SECONDS)` with re-check inside lock (verified lines 360-375 of plan).
- [x] Edit B — Two new grep-checkable acceptance criteria added (verified lines 406-407 of plan).
- [x] Edit C — T-02.1.3-02 mitigation extended to explicitly cover `migrate_to_v2()` CLI as the third call site (verified line 431 of plan).
- [x] Edit D — Done line includes "CLI lock-pattern unified with write_cache and read_cache auto-upgrade" (verified line 412 of plan).
- [x] No other files modified — single-file edit confirmed via `git status --short`.
