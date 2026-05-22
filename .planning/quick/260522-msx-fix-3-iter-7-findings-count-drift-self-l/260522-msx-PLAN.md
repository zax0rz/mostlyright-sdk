---
phase: quick
plan: 260522-msx
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
autonomous: true
requirements: [LINEAGE-02, LINEAGE-04]
user_setup: []

must_haves:
  truths:
    - "PLAN-03 test count claims match pytest's actual `-v` output: Task 2 acceptance reports 20 tests = 10+10 (Test 9 parametrized over read_first/write_first counted as 2 cases), phase verification reports 28 tests = 10+10+8"
    - "PLAN-03 write_cache action specifies a single-locking-layer pattern: outer FileLock acquired by write_cache; inner atomic-write helper (`_atomic_write_locked`) is lock-free; no nested same-lock acquisition that could deadlock on a non-reentrant FileLock backend"
    - "PLAN-03 Test 9 specification requires a `threading.Event` (or equivalent) barrier so the `read_first`/`write_first` parametrization is deterministic and actually exercises both lock-winners — not relying on OS scheduler order"
    - "Threat T-02.1.3-02 mitigation language explicitly names the single-locking-layer pattern + the iter-7 self-locking concern"
  artifacts:
    - path: ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md"
      provides: "Updated PLAN-03 with iter-7 HIGH-finding fixes (count drift, self-lock, race-test determinism)"
      contains: "_atomic_write_locked"
  key_links:
    - from: "PLAN-03 Task 1 step 3e (write_cache atomic write)"
      to: "PLAN-03 Task 1 helper definition (_atomic_write_locked)"
      via: "rewrite of step 3e to call _atomic_write_locked() (lock-free)"
      pattern: "_atomic_write_locked"
    - from: "PLAN-03 Task 2 Test 9 spec"
      to: "PLAN-03 Task 2 acceptance grep check"
      via: "behavior spec mandates threading.Event barrier; acceptance verifies via grep"
      pattern: "threading.Event"
    - from: "PLAN-03 Task 2 acceptance line ('all 19 tests PASSED (10 + 9)')"
      to: "PLAN-03 Task 2 acceptance line ('all 20 tests PASSED (10 + 10)')"
      via: "literal string update reflecting parametrize-counts-as-2"
      pattern: "all 20 tests PASSED"
---

<objective>
Fix 3 HIGH findings on `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` flagged in REVIEW-DISCIPLINE iteration 7 (architect HIGH-1 + codex HIGH P1 + codex HIGH P2). All three findings are localised to PLAN-03; no source code is touched.

Findings:

1. **Count drift (architect iter-7 HIGH-1):** Test 9 was parametrized over `("read_first", "write_first")` in iter-6 P1, but pytest counts each parametrize case as a separate test in `-v` output. PLAN-03 still claims Task 2 runs 9 tests (actually 10), acceptance string `"all 19 tests PASSED (10 + 9)"` won't match pytest's actual output (it'll be `20 passed`), `done` says "18 silver+gold tests pass" (actually 19), and phase verification claims "10+9+8 = 27 tests" (actually 28).

2. **Self-locking write_cache (codex iter-7 P1 HIGH):** Task 1 step 3 has `write_cache` acquire FileLock on the per-file `.lock` sibling, then INSIDE the lock call `_atomic_write()` — which itself internally acquires `FileLock(str(path) + ".lock")` on the same file. filelock>=3.x IS reentrant on the same thread, so this works on current Linux/macOS, but the plan must not rely on platform/library-version-dependent reentrancy. Introduce `_atomic_write_locked()` (lock-free inner helper) so the outer write_cache lock is the only locking layer.

3. **Race test non-determinism (codex iter-7 P2 HIGH):** Test 9 parametrizes over `("read_first", "write_first")` but `.start()` order does NOT determine lock-acquisition order — the OS scheduler does. The `write_first` case may never actually exercise the write-wins race it names. Add a `threading.Event` barrier so the test is deterministic.

Purpose: Re-tighten PLAN-03 before Wave 3 execution. All findings are blocking per REVIEW-DISCIPLINE.md (HIGH = block on merge to `merged-vision`).

Output: 1 file modified (PLAN-03). Single atomic commit per finding (3 commits total — one per task).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Reconcile Test 9 parametrize count drift (architect iter-7 HIGH-1)</name>
  <files>.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md</files>
  <action>
    Source of truth decision: KEEP the parametrize (cleanest way to exercise both lock-winner orderings, already approved in iter-6 P1). Update PLAN-03 counts to match pytest's actual `-v` output (parametrize cases counted separately).

    Edit `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` in 4 sites:

    1. **Line ~225 (Task 2 Test 9 spec, last sentence):** Currently reads:
       > "The Order A/B parametrization keeps the Task 2 test COUNT at 9 (Test 9 is one parametrized test with two cases); the acceptance line `all 19 tests PASSED (10 + 9)` is unchanged."

       Replace with:
       > "The Order A/B parametrization raises the Task 2 test COUNT from 9 to 10 (Test 9 is one parametrized test, but pytest counts each parametrize case as a separate test in `-v` output, so the 8 single-case tests + Test 9's 2 parametrize cases = 10 total). The acceptance line is updated to `all 20 tests PASSED (10 + 10)` to match pytest's actual output."

    2. **Line ~277 (Task 2 acceptance — last bullet of the bulleted list inside `<acceptance_criteria>`):** Currently reads:
       > "- `uv run pytest tests/test_cache_gold_read.py tests/test_cache_silver_write.py -v` shows all 19 tests PASSED (10 + 9), 0 FAILED"

       Replace with:
       > "- `uv run pytest tests/test_cache_gold_read.py tests/test_cache_silver_write.py -v` shows all 20 tests PASSED (10 + 10), 0 FAILED"

    3. **Line ~280 (Task 2 `<done>` line):** Currently reads:
       > "...idempotent on re-read. 18 silver+gold tests pass. No dtype drift."

       Replace with:
       > "...idempotent on re-read. 19 silver+gold tests pass (10 silver + 9 gold-spec items, with Test 9 parametrized into 2 pytest cases = 20 collected). No dtype drift."

    4. **Line ~424 (phase `<verification>` step 1):** Currently reads:
       > "1. `uv run pytest tests/test_cache_silver_write.py tests/test_cache_gold_read.py tests/test_cache_migration.py -v` — all 10 + 9 + 8 = 27 tests PASSED."

       Replace with:
       > "1. `uv run pytest tests/test_cache_silver_write.py tests/test_cache_gold_read.py tests/test_cache_migration.py -v` — all 10 + 10 + 8 = 28 tests PASSED. (Task 2's Test 9 parametrizes over `('read_first', 'write_first')`, so pytest counts it as 2 cases, bringing Task 2's `-v` count to 10.)"

    Do NOT modify any other lines. Use the `Edit` tool with exact-string matching for each of the 4 sites.

    Atomic commit message:
    ```
    docs(planning): reconcile PLAN-03 Test 9 parametrize count drift (iter-7 HIGH-1)

    Test 9 parametrizes over (read_first, write_first); pytest counts each
    parametrize case as a separate test in -v output. PLAN-03 still claimed
    9 tests for Task 2 (actually 10) — acceptance strings, done line, and
    phase verification updated to match real pytest output (20 = 10+10,
    28 = 10+10+8).

    Source: REVIEW-DISCIPLINE.md iter-7 architect HIGH-1.
    ```
  </action>
  <verify>
    <automated>grep -c "all 20 tests PASSED (10 + 10)" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md</automated>
  </verify>
  <done>
    - `grep -c "all 19 tests PASSED (10 + 9)" PLAN-03` returns 0 (old count drift gone)
    - `grep -c "all 20 tests PASSED (10 + 10)" PLAN-03` returns 1 (new count present)
    - `grep -c "10 + 9 + 8 = 27" PLAN-03` returns 0 (old phase-verify count gone)
    - `grep -c "10 + 10 + 8 = 28" PLAN-03` returns 1 (new phase-verify count present)
    - `grep -c "18 silver+gold tests pass" PLAN-03` returns 0 (old done line gone)
    - `grep -c "19 silver+gold tests pass" PLAN-03` returns 1 (new done line present)
    - `grep -c "the Task 2 test COUNT at 9" PLAN-03` returns 0 (old single-source-of-truth claim gone)
    - `grep -c "raises the Task 2 test COUNT from 9 to 10" PLAN-03` returns 1 (new claim present)
    - Atomic commit landed with subject containing "iter-7 HIGH-1"
  </done>
</task>

<task type="auto">
  <name>Task 2: Specify single-locking-layer pattern in write_cache to eliminate self-locking risk (codex iter-7 P1 HIGH)</name>
  <files>.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md</files>
  <action>
    Codex iter-7 P1 concern: write_cache acquires the per-file FileLock, then calls `_atomic_write()` which itself acquires `FileLock(str(path) + ".lock")` on the same file. filelock>=3.x IS reentrant on the same thread (counts acquisitions), so on current Linux/macOS this works — but the plan must NOT rely on platform/library-version-dependent reentrancy. Make the locking pattern explicit and single-layer.

    Edit `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md`:

    1. **Add a new helper-definition step to Task 1 action.** Insert between current step 2 and step 3 (around line ~160), a new step 2-prime:

       ```
       2-prime. **Add a new lock-free atomic-write helper** `_atomic_write_locked(path: Path, table: pa.Table) -> None`. Same tmp-file + cross-platform `os.replace` atomicity as the existing `_atomic_write()`, but it does NOT acquire a FileLock — the caller is REQUIRED to hold the per-file lock already. This eliminates the self-locking-deadlock risk on non-reentrant FileLock backends: write_cache (step 3) and `_legacy_v014_to_v021_migration` (Task 2 step 3e) BOTH already hold the outer per-file lock, and the new helper is the inner write primitive they call. The original `_atomic_write()` stays on the module for any caller that does NOT already hold a lock (e.g., one-off scripts), but the in-plan production paths (write_cache, migration, auto-upgrade-on-read) all use `_atomic_write_locked()`. **Single-locking-layer invariant: the outer per-file FileLock is the ONLY locking layer; the inner atomic-write helper is lock-free.**
       ```

    2. **Update Task 1 step 3e (write_cache append/write).** Currently reads:
       > "...concat new table via `pa.concat_tables([existing, new])`, atomic write. Otherwise (neither `ledger_p` nor `legacy_p` existed at step b) atomic write directly."

       Replace with:
       > "...concat new table via `pa.concat_tables([existing, new])`, atomic write via `_atomic_write_locked(ledger_p, table)` (lock-free; the outer FileLock from step 3a is the single locking layer per the invariant in step 2-prime). Otherwise (neither `ledger_p` nor `legacy_p` existed at step b) call `_atomic_write_locked(ledger_p, table)` directly."

    3. **Update Task 1 step 3f (preservation note).** Currently reads:
       > "f. Release the FileLock. Preserve `_atomic_write()`, `coerce_timestamps="us"`, `version="2.6"` per CACHE-07."

       Replace with:
       > "f. Release the FileLock. Preserve `_atomic_write_locked()` for callers that already hold the lock (write_cache, migration, auto-upgrade) AND preserve the original `_atomic_write()` for unlocked callers. Both helpers MUST use `coerce_timestamps=\"us\"` and `version=\"2.6\"` per CACHE-07."

    4. **Update Task 2 step 3e (migration adapter atomic write).** Currently reads:
       > "e. Atomic write to `ledger_path` via existing `_atomic_write()` (preserve CACHE-07: version=\"2.6\", coerce_timestamps=\"us\"). Use FileLock around the write per existing pattern."

       Replace with:
       > "e. Atomic write to `ledger_path` via `_atomic_write_locked(ledger_path, table)` (lock-free inner helper). The OUTER FileLock is acquired by the caller — write_cache step 3a OR read_cache auto-upgrade step 4e — so the migration adapter MUST be called from inside a held lock. Preserve CACHE-07: version=\"2.6\", coerce_timestamps=\"us\". Single-locking-layer invariant: do NOT re-acquire the lock here."

    5. **Update Task 2 step 4e (auto-upgrade-on-read lock acquisition).** Currently reads:
       > "- Acquire FileLock on the per-file `.lock` sibling at `ledger_p.with_suffix(ledger_p.suffix + \".lock\")` (the SAME lock object used by write_cache step 3 — unifying the lock pattern eliminates the write_cache-vs-migrator race documented in T-02.1.3-02)."

       Replace with:
       > "- Acquire FileLock on the per-file `.lock` sibling at `ledger_p.with_suffix(ledger_p.suffix + \".lock\")` (the SAME lock object used by write_cache step 3a — unifying the lock pattern eliminates the write_cache-vs-migrator race documented in T-02.1.3-02). The lock acquired here is the SINGLE locking layer for this code path: the inner `_legacy_v014_to_v021_migration` call invokes `_atomic_write_locked()` (lock-free) — NO nested same-lock acquisition (codex iter-7 P1 mitigation; eliminates dependence on non-reentrant FileLock backends)."

    6. **Update Task 1 acceptance criteria.** Add a new bullet to Task 1's `<acceptance_criteria>` list (the existing bulleted list ending with `uv run pytest tests/test_cache_silver_write.py -v` shows 10 tests PASSED):

       ```
       - `grep -c "_atomic_write_locked" packages/weather/src/tradewinds/weather/cache.py` returns ≥ 3 (helper definition + write_cache use + migration use)
       - `grep -c "def _atomic_write_locked" packages/weather/src/tradewinds/weather/cache.py` returns 1 (helper defined exactly once)
       ```

    7. **Extend Threat T-02.1.3-02 mitigation language.** Currently the mitigation column ends with:
       > "...RESEARCH Risk 3 mitigation extended to cover the write_cache-wins-the-race case (codex iter-6 P1 finding)."

       Append (do not replace) the following sentence to that same mitigation cell:
       > " Single-locking-layer pattern (codex iter-7 P1 mitigation): the outer per-file FileLock acquired by write_cache / read_cache-auto-upgrade / migrate_to_v2 is the ONLY locking layer; the inner `_atomic_write_locked()` helper is lock-free. Eliminates dependence on non-reentrant FileLock backends and any nested-acquisition deadlock risk."

    Use exact-string `Edit` calls for each of the 7 sites.

    Atomic commit message:
    ```
    docs(planning): specify single-locking-layer pattern in PLAN-03 write path (iter-7 P1)

    Add _atomic_write_locked() lock-free inner helper. write_cache,
    _legacy_v014_to_v021_migration, and read_cache auto-upgrade all hold
    the outer per-file FileLock and call the lock-free helper — no nested
    same-lock acquisition. Eliminates dependence on non-reentrant FileLock
    backends. Threat T-02.1.3-02 mitigation extended.

    Source: REVIEW-DISCIPLINE.md iter-7 codex P1 HIGH.
    ```
  </action>
  <verify>
    <automated>grep -c "_atomic_write_locked" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md</automated>
  </verify>
  <done>
    - `grep -c "_atomic_write_locked" PLAN-03` returns ≥ 6 (step 2-prime def + Task 1 3e + Task 1 3f + Task 2 3e + Task 2 4e narrative + Task 1 acceptance grep checks)
    - `grep -c "Single-locking-layer" PLAN-03` returns ≥ 2 (step 2-prime invariant + Threat T-02.1.3-02 mitigation)
    - `grep -c "lock-free inner helper" PLAN-03` returns ≥ 1 (Task 2 step 3e)
    - `grep -c "iter-7 P1" PLAN-03` returns ≥ 1 (T-02.1.3-02 mitigation cell)
    - `grep -c "non-reentrant FileLock backends" PLAN-03` returns ≥ 1 (T-02.1.3-02 mitigation cell)
    - Old Task 1 step 3f line `Release the FileLock. Preserve _atomic_write(),` no longer present as the verbatim original — replaced with the dual-helper preservation note
    - Atomic commit landed with subject containing "iter-7 P1"
  </done>
</task>

<task type="auto">
  <name>Task 3: Mandate threading.Event barrier in Test 9 race spec to make ordering deterministic (codex iter-7 P2 HIGH)</name>
  <files>.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md</files>
  <action>
    Codex iter-7 P2 concern: Test 9 parametrizes over `("read_first", "write_first")` but `.start()` order does NOT determine which thread acquires the lock first — the OS scheduler does. Under typical scheduling, the read thread can win the lock even when the write thread `.start()`-ed first, so the `write_first` case may pass without ever exercising the write-wins race it names. Add a `threading.Event` synchronisation barrier so each ordering is deterministic.

    Edit `.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md`:

    1. **Augment Test 9 spec (line ~222-225) with the barrier requirement.** Inside Test 9's `behavior` description, locate the sentence ending in:
       > "...The test MUST run BOTH orderings (parametrize over `(\"read_first\", \"write_first\")` or use two separate test functions sharing a helper) so the write-wins case is genuinely exercised — without explicit Order B, a regression that only breaks the write-wins ordering would slip through the test suite."

       Append the following sentence immediately after it (still inside the same Test 9 bullet, before the closing line about the count):
       > " **The test implementation MUST use a `threading.Event` (or equivalent) synchronisation barrier to make each ordering deterministic — `.start()` order does NOT determine lock-acquisition order; the OS scheduler does (codex iter-7 P2 finding).** For Order B (`write_first`): the write thread (a) acquires the per-file FileLock, (b) `.set()`s a `lock_acquired_event` AFTER acquisition succeeds, (c) holds the lock through its critical section (the migrate-if-needed-inside-lock branch plus the live-row append), (d) releases the lock. The read thread waits on `lock_acquired_event.wait(timeout=5.0)` BEFORE calling `read_cache`, guaranteeing write_cache holds the lock when read_cache attempts auto-upgrade — so the iter-6 P1 write-wins case is genuinely exercised. For Order A (`read_first`): mirror the pattern — the read thread `.set()`s the event after it has begun auto-upgrade migration (i.e., after it has acquired the lock), and the write thread waits on the event before calling write_cache. The barrier guarantees deterministic test ordering; without it, a regression that only breaks one ordering can pass intermittently and slip through CI."

    2. **Add a barrier grep-check to Task 2's `<acceptance_criteria>`.** Insert a new bullet into the existing bulleted list (after the `_V014_COLUMNS` grep bullet, around line ~273):

       ```
       - `grep -cE "threading.Event|lock_acquired_event" tests/test_cache_gold_read.py` returns ≥ 1 (Test 9 barrier implementation — codex iter-7 P2 mitigation; without the barrier, the parametrize over read_first/write_first is non-deterministic and the write-wins case may never actually be exercised)
       ```

    3. **Add the barrier invariant to Task 2's `<done>` line.** Currently (after the Task 1 count-drift fix lands it will read):
       > "...idempotent on re-read. 19 silver+gold tests pass (10 silver + 9 gold-spec items, with Test 9 parametrized into 2 pytest cases = 20 collected). No dtype drift."

       Replace with:
       > "...idempotent on re-read. 19 silver+gold tests pass (10 silver + 9 gold-spec items, with Test 9 parametrized into 2 pytest cases = 20 collected, each gated by a `threading.Event` barrier so both lock-winner orderings are deterministically exercised). No dtype drift."

    4. **Strengthen Threat T-02.1.3-02 verification reference.** The mitigation cell currently ends (after Task 2's edit) with the single-locking-layer sentence. Append a final sentence:
       > " Verified by Task 2 Test 9 parametrize-with-barrier — both `read_first` and `write_first` orderings deterministically exercised via `threading.Event` (codex iter-7 P2 mitigation; OS-scheduler-induced flakiness ruled out)."

    Use exact-string `Edit` calls for each of the 4 sites. Sequence note: Task 3 runs AFTER Tasks 1 and 2, so the Task 2 `<done>` line being edited here is the COUNT-DRIFT-FIXED version (i.e., already updated by Task 1 to say "19 silver+gold tests pass...20 collected"). If Tasks 1 and 2 are run out of order, re-read the file to find the current Task 2 `<done>` line verbatim before editing.

    Atomic commit message:
    ```
    docs(planning): mandate threading.Event barrier in PLAN-03 Test 9 race spec (iter-7 P2)

    Test 9 parametrizes over (read_first, write_first), but .start() order
    does NOT determine lock-acquisition order — the OS scheduler does.
    Add a threading.Event barrier requirement so each ordering is
    deterministically exercised. Grep-check added to Task 2 acceptance.
    Threat T-02.1.3-02 mitigation extended.

    Source: REVIEW-DISCIPLINE.md iter-7 codex P2 HIGH.
    ```
  </action>
  <verify>
    <automated>grep -c "threading.Event" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md</automated>
  </verify>
  <done>
    - `grep -c "threading.Event" PLAN-03` returns ≥ 3 (Test 9 spec body + Task 2 acceptance grep bullet + Task 2 done line)
    - `grep -c "lock_acquired_event" PLAN-03` returns ≥ 2 (Test 9 spec describes both Order A and Order B uses)
    - `grep -c "OS scheduler" PLAN-03` returns ≥ 1 (Test 9 spec body)
    - `grep -c "iter-7 P2" PLAN-03` returns ≥ 2 (Test 9 spec + acceptance bullet + T-02.1.3-02 mitigation)
    - `grep -c "deterministic" PLAN-03` returns ≥ 2 (Test 9 spec emphasises determinism)
    - Atomic commit landed with subject containing "iter-7 P2"
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| reviewer (codex / architect) → planning artifact | Iter-7 reviewers raised 3 HIGH findings on PLAN-03; these MUST be fixed before Wave 3 execution (REVIEW-DISCIPLINE.md never-skip path: `.planning/` artifacts whose diff contains code-like fragments) |
| planning artifact → Wave 3 executor (future Claude) | Wave 3 will read PLAN-03 verbatim; any unfixed HIGH finding propagates to silently-wrong implementation (e.g., write_cache deadlock, intermittently-passing race test, false-positive "all tests pass" claims when pytest reports a different count) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-msx-01 | T (Tampering) | PLAN-03 count claims diverge from pytest reality, executor may "fix" tests to match the wrong count and silently lose coverage | mitigate | Task 1 edits all 4 count sites to match pytest's actual parametrize-aware `-v` output (20 = 10+10, 28 = 10+10+8) |
| T-quick-msx-02 | T (Tampering) / D (DoS) | write_cache self-locks on a non-reentrant FileLock backend → every write deadlocks for LOCK_TIMEOUT_SECONDS, then raises; silent perf cliff on Linux/macOS via reentrant counter behaviour | mitigate | Task 2 introduces `_atomic_write_locked()` (lock-free inner helper) so the outer FileLock is the single locking layer. T-02.1.3-02 mitigation extended to call out the iter-7 P1 self-locking case explicitly. |
| T-quick-msx-03 | T (Tampering) | Test 9's `write_first` parametrize case never actually exercises write-wins (OS scheduler lets read thread win lock), regression in write_cache lock-race ordering passes CI silently | mitigate | Task 3 mandates `threading.Event` barrier in Test 9 spec; grep-check added to Task 2 acceptance so the barrier is verifiable in CI without running the test. T-02.1.3-02 mitigation extended. |
| T-quick-msx-04 | I (Information disclosure) | None — all edits are to a planning markdown file; no secrets, no PII, no untrusted input | accept | N/A |
</threat_model>

<verification>
After all 3 tasks land (3 atomic commits):

1. `grep -c "all 20 tests PASSED (10 + 10)" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns 1
2. `grep -c "10 + 10 + 8 = 28" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns 1
3. `grep -c "_atomic_write_locked" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns ≥ 6
4. `grep -c "Single-locking-layer" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns ≥ 2
5. `grep -c "threading.Event" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns ≥ 3
6. `grep -c "lock_acquired_event" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns ≥ 2
7. `grep -cE "iter-7 (P1|P2|HIGH-1)" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns ≥ 4 (Task 1 commit ref + Task 2 single-locking + Task 3 barrier + T-02.1.3-02 mitigation refs)
8. `grep -c "all 19 tests PASSED (10 + 9)" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-03-cache-layer-refactor.md` returns 0 (old count drift gone)
9. `git log --oneline -3` shows 3 distinct commits, one per task, each with the iter-7 finding reference in its subject line
10. `git status` shows working tree clean (no other accidental edits)
</verification>

<success_criteria>
- 3 HIGH findings from iter-7 fixed in PLAN-03 (count drift, self-locking, race-test determinism).
- 1 file modified: `02.1-PLAN-03-cache-layer-refactor.md`.
- 3 atomic commits, each subject naming the iter-7 finding (HIGH-1 / P1 / P2).
- Threat T-02.1.3-02 mitigation language extended in two places (single-locking-layer pattern + Test 9 barrier verification).
- All grep verification checks pass.
- No source code touched; no other planning artifacts touched.
- Ready for iter-8 reviewer re-dispatch (codex `high` + python-architect) per REVIEW-DISCIPLINE.md two-reviewer loop.
</success_criteria>

<output>
After completion, no SUMMARY.md is required for a `quick/` task. Update STATE.md `Quick Tasks Completed` table with one row (id `260522-msx`, description "Fix 3 iter-7 HIGH findings on Phase 2.1 PLAN-03 (count drift + self-lock + race-test determinism)", date 2026-05-22, commit shas of the 3 atomic commits, directory path).
</output>
