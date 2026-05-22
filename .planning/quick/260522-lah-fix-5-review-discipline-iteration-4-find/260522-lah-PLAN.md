---
phase: quick
plan: 260522-lah
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md
  - .planning/STATE.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "REQUIREMENTS.md no longer simultaneously activates and defers POLY-01 (stale Sprint-0.5+ entry removed)"
    - "ROADMAP.md Phase 2.1 summary bullet column name matches Success Criteria (`source_received_at`, not `observation_received_at`)"
    - "PLAN-04 class (c) test assertion reflects actual merge behavior (`r.get('source_received_at') or ''` → null wins, not baseline)"
    - "ROADMAP.md Phase 3.4 QC engine description writes the bitmask into `obs_qc_status` (not the `observation_quality` enum)"
    - "STATE.md frontmatter `total_phases` reflects current 12-phase count and `total_plans` reflects existing planned plans"
    - "All five doc edits land on planning/v01-intl-nwp-polymarket, then merge --no-ff into merged-vision and push to origin"
  artifacts:
    - path: ".planning/REQUIREMENTS.md"
      provides: "POLY-01 single-status (activated, not deferred)"
    - path: ".planning/ROADMAP.md"
      provides: "Phase 2.1 line ~19 + Phase 3.4 line ~179 corrections"
    - path: ".planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md"
      provides: "Class (c) assertion + comments flipped to match merge implementation"
    - path: ".planning/STATE.md"
      provides: "Accurate progress counts"
  key_links:
    - from: "planning/v01-intl-nwp-polymarket"
      to: "merged-vision"
      via: "git merge --no-ff"
      pattern: "merge commit landing all five doc fixes on merged-vision and pushed to origin"
---

<objective>
Fix 5 surgical findings from REVIEW-DISCIPLINE iteration 4 (4 HIGH + 1 LOW). All edits are planning-doc text changes — no source code, no new features, no schema changes. After commit, merge the planning branch into `merged-vision` (no-ff) and push to origin.

Purpose: Close the iteration-4 findings before the Phase 2.1 plans go into execution, so the planning docs are internally consistent (POLY-01 status, column names, test assertions, progress counts).

Output:
- Surgical edits to 4 planning files
- One commit on `planning/v01-intl-nwp-polymarket` containing all 5 fixes
- Merge commit on `merged-vision` (no-ff) + push to origin
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/ROADMAP.md
@.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md

Branch context: `git branch --show-current` is `planning/v01-intl-nwp-polymarket` (verified at plan-write time). All commits should happen on this branch before the final task switches to `merged-vision` for the merge.

Finding-source: the iteration-4 review report identified these 5 issues. Each fix is a literal text replacement specified by the user — DO NOT reinterpret scope. The exact text to change is given in each task's `<action>`.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove stale POLY-01 from Sprint-0.5+ deferral section in REQUIREMENTS.md (Finding 1, HIGH)</name>
  <files>.planning/REQUIREMENTS.md</files>
  <action>
The bug: POLY-01 appears in BOTH the v2-deferred section ("Markets API Client (Sprint 0.5+)") AND the active Phase 3.3 stubs section. The Phase 3.3 stubs start at POLY-02 because POLY-01 was "repurposed" to Phase 3.3 on 2026-05-22 — but the stale deferral entry was never deleted, leaving POLY-01 simultaneously activated AND deferred.

The fix: delete the stale deferral entry. The Phase 3.3 stubs section already correctly notes the repurposing (line 99: "Activates `POLY-01` (formerly Sprint 0.5+ deferral; now Phase 3.3 v0.1.0 scope)." and line 106: "(Note: `POLY-01` repurposed from `Sprint 0.5+` to Phase 3.3 v0.1.0 scope as of 2026-05-22 expansion. Its earlier "v0.x+ as demand emerges" entry in "Markets API Client (Sprint 0.5+)" below is superseded; see Phase 3.3 in ROADMAP.)").

Step 1 — Use the `Read` tool to read `.planning/REQUIREMENTS.md` lines 181-195 to confirm the exact text of the stale entry. You should see (around line 184):
```
### Markets API Client (Sprint 0.5+)

- **KALSHI-01**: Kalshi API client (orderbook, fills, settlement queries)
- **POLY-01**: Polymarket adapter (out of v0.1 scope; v0.x+ as demand emerges)
```

Step 2 — Use the `Edit` tool to delete ONLY the POLY-01 bullet line. The `### Markets API Client (Sprint 0.5+)` heading and the `KALSHI-01` bullet MUST remain (KALSHI-01 is genuinely Sprint-0.5+).

Use this exact `old_string` (with surrounding context to make it unique):
```
- **KALSHI-01**: Kalshi API client (orderbook, fills, settlement queries)
- **POLY-01**: Polymarket adapter (out of v0.1 scope; v0.x+ as demand emerges)
```

And this exact `new_string`:
```
- **KALSHI-01**: Kalshi API client (orderbook, fills, settlement queries)
```

(Net effect: removes the POLY-01 line; preserves the heading + KALSHI-01.)

Step 3 — Also update the explanatory note on line 106. The current text refers to "Its earlier 'v0.x+ as demand emerges' entry in 'Markets API Client (Sprint 0.5+)' below is superseded; see Phase 3.3 in ROADMAP." This note is now slightly stale (the entry no longer exists below). Update it to past-tense to make the doc self-consistent.

Use Read to confirm the current text of line 106 (it's the closing `(Note: ...)` parenthetical inside the Phase 3.3 stubs section). Then Edit:

old_string (must match exactly — use Read first to confirm):
```
(Note: `POLY-01` repurposed from `Sprint 0.5+` to Phase 3.3 v0.1.0 scope as of 2026-05-22 expansion. Its earlier "v0.x+ as demand emerges" entry in "Markets API Client (Sprint 0.5+)" below is superseded; see Phase 3.3 in ROADMAP.)
```

new_string:
```
(Note: `POLY-01` repurposed from `Sprint 0.5+` to Phase 3.3 v0.1.0 scope as of 2026-05-22 expansion. The earlier "v0.x+ as demand emerges" entry under "Markets API Client (Sprint 0.5+)" was removed 2026-05-22 as part of this fix; see Phase 3.3 in ROADMAP.)
```
  </action>
  <verify>
    <automated>grep -n "POLY-01" .planning/REQUIREMENTS.md | grep -v "POLY-02\|POLY-01..\|repurposed" || echo "OK: no stale POLY-01 deferral entries remain"</automated>
    Also: `grep -c "POLY-01: Polymarket adapter" .planning/REQUIREMENTS.md` should return 0 (the stale bullet is gone). `grep -c "KALSHI-01" .planning/REQUIREMENTS.md` should return 1 (KALSHI-01 retained).
  </verify>
  <done>
- The `- **POLY-01**: Polymarket adapter (out of v0.1 scope; v0.x+ as demand emerges)` line is deleted from the Sprint-0.5+ section.
- The `### Markets API Client (Sprint 0.5+)` heading + KALSHI-01 bullet remain.
- The explanatory note on line ~106 reads "was removed 2026-05-22 as part of this fix" (past tense), no longer claiming the entry exists "below".
- POLY-01 now appears in REQUIREMENTS.md only as part of the Phase 3.3 traceability + the explanatory note.
  </done>
</task>

<task type="auto">
  <name>Task 2: Fix Phase 2.1 column-name mismatch in ROADMAP.md line ~19 (Finding 2, HIGH)</name>
  <files>.planning/ROADMAP.md</files>
  <action>
The bug: ROADMAP line 19 (Phase 2.1 summary bullet) says lineage columns include `observation_received_at`, but the canonical Success Criterion #1 (lines 83-87) was previously fixed to `source_received_at`. The summary bullet was missed during that fix.

Step 1 — Use the `Read` tool to read `.planning/ROADMAP.md` line 19. The current text reads:
```
- [ ] **Phase 2.1: Sprint 2o Lineage Refactor (Per-Source Provenance)** [INSERTED 2026-05-22] - Lift mostlyright Sprint 2o (PR #101): silver-tier observation ledger in **rows-per-source long format** (multiple rows per (station, observed_at), one per contributing source) + read-time `ObservationMergePolicy.apply()` materializes single-row-per-key gold for Mode 1 parity callers. Lineage columns: `source`, `parser_name`, `parser_version`, `as_of_time`, `ingestion_id`, `observation_quality` enum, `observation_received_at`. Enables Phase 3.1 international + 3.3 Polymarket to record per-source identity. Parity-fixture pre-flight gate mandatory (Days 9.5-15.5)
```

Step 2 — Use the `Edit` tool to replace `observation_received_at` with `source_received_at` in that bullet only. Use this exact `old_string`:
```
Lineage columns: `source`, `parser_name`, `parser_version`, `as_of_time`, `ingestion_id`, `observation_quality` enum, `observation_received_at`. Enables Phase 3.1 international
```

And this exact `new_string`:
```
Lineage columns: `source`, `parser_name`, `parser_version`, `as_of_time`, `ingestion_id`, `observation_quality` enum, `source_received_at`. Enables Phase 3.1 international
```

(The surrounding-context unique anchor ensures we change ONLY line 19, not any other reference to either column name.)
  </action>
  <verify>
    <automated>grep -n "observation_received_at" .planning/ROADMAP.md || echo "OK: no observation_received_at references remain"</automated>
    Then: `grep -n "source_received_at" .planning/ROADMAP.md` should now show at least 2 occurrences (the summary bullet on line ~19 plus the Success Criteria block around lines 83-87).
  </verify>
  <done>
- `.planning/ROADMAP.md` no longer contains the string `observation_received_at` anywhere.
- The Phase 2.1 summary bullet on line 19 lists `source_received_at` as the lineage column (matching Success Criterion #1 on line 83).
  </done>
</task>

<task type="auto">
  <name>Task 3: Flip backwards null-source assertion in Phase 2.1 PLAN-04 lines 261-267 + 239-240 + 299 (Finding 3, HIGH)</name>
  <files>.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md</files>
  <action>
The bug: PLAN-04's pre-flight test class (c) describes a NULL `source_received_at` sibling and asserts the baseline (with timestamp) wins. But the actual merge implementation uses `r.get("source_received_at") or ""` which means a `None` value gets coerced to `""` — an EMPTY STRING — which is the lexicographically smallest possible value. So in the secondary tiebreak (which sorts by `source_received_at` ascending, then earliest wins), the null-coerced-to-`""` row sorts FIRST and WINS — not loses. The class (c) commentary + the +300 marker logic + the line-299 comment are all backwards.

The fix has three sub-edits in the same file:

Sub-edit A — Lines 239-240 (comment in `_hardcoded_silver_with_duplicates` docstring listing class (c)):

old_string:
```
        #   (c) same-priority + NULL source_received_at: iem sibling, no timestamp — baseline wins
        #       (this verifies null source_received_at loses vs present timestamp via lex order)
```

new_string:
```
        #   (c) same-priority + NULL source_received_at: iem sibling, no timestamp — null-source sibling wins
        #       (merge coerces None → "" via `r.get("source_received_at") or ""`, which lex-sorts
        #       BEFORE any RFC3339 timestamp → null-source row wins the secondary tiebreak)
```

Sub-edit B — Lines 261-267 (the class (c) synthetic row construction comment + temp marker):

old_string:
```
            # (c) iem(2) sibling with NULL source_received_at — baseline (has ts) should win
            synthetic.append({
                **b,
                "source": "iem",
                "ingestion_id": f"legacy:null:{station}:{i:08d}",
                "source_received_at": None,
                "temp_c": b["temp_c"] + 300.0,  # if this wins, null lost tiebreak incorrectly
            })
```

new_string:
```
            # (c) iem(2) sibling with NULL source_received_at — null-source row should win
            #     (None → "" via merge's `or ""` coercion → lex-MIN → null wins secondary tiebreak)
            synthetic.append({
                **b,
                "source": "iem",
                "ingestion_id": f"legacy:null:{station}:{i:08d}",
                "source_received_at": None,
                "temp_c": b["temp_c"] + 300.0,  # if baseline wins, null-coercion-to-"" tiebreak is broken
            })
```

Sub-edit C — Line 299 (comment in `test_pre_flight_strict_priority_with_synthetic_duplicates`):

old_string:
```
        # Same-priority + later/null source_received_at classes (b)+(c): baseline wins via tiebreak.
```

new_string:
```
        # Same-priority + later source_received_at class (b): baseline wins via tiebreak (earliest ts).
        # Same-priority + NULL source_received_at class (c): null-source sibling wins via tiebreak
        #   (None → "" via merge's `or ""` coercion → lex-MIN). Class (c) intentionally exercises
        #   the legacy-row case where source_received_at is unknown — those rows preempt timestamped
        #   siblings because we treat "no timestamp" as "arrived first" (legacy v0.14.1 semantics).
```

Note: this finding documents the EXPECTED behavior of the merge implementation. We are not changing the implementation — we are flipping the test's assertion intent so it matches what the merge actually does (and what it SHOULD do per the legacy-row design rationale). The Wave 2 merge engine plan + tests already implement `or ""` semantics deliberately to handle pre-2.1 cache rows that have no `source_received_at`. The PLAN-04 pre-flight test was the only place this got described backwards.

After all three sub-edits, the new test assertion semantics are: for class (c), the +300 marker SHOULD win (because the null-source row sorts first by lex coercion). Both `_legacy_dedup_rows()` and `query_time_merge()` must agree — both must pick the null-source sibling. If either picks baseline, that's the regression the test now correctly catches.
  </action>
  <verify>
    <automated>grep -n "baseline (has ts) should win" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md || echo "OK: backwards class (c) comment removed"</automated>
    Plus: `grep -n "null-source sibling wins" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` should return ≥1 hit (sub-edit A landed). And `grep -n "or \"\"" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md` should return ≥1 hit (the coercion rationale is now in the test comment).
  </verify>
  <done>
- Sub-edit A landed: the `_hardcoded_silver_with_duplicates` docstring for class (c) reads "null-source sibling wins" (not "baseline wins").
- Sub-edit B landed: the class (c) synthetic-row construction comment reads "null-source row should win" and the `temp_c` marker comment is flipped to "if baseline wins, null-coercion-to-`""` tiebreak is broken".
- Sub-edit C landed: line ~299 comment splits class (b) (baseline wins) from class (c) (null-source wins) and explains the `or ""` lex-MIN semantics.
- No remaining references to "baseline (has ts) should win" or to class (c) baseline-victory framing.
  </done>
</task>

<task type="auto">
  <name>Task 4: Fix QC bitmask column name in ROADMAP.md line ~179 (Finding 4, HIGH)</name>
  <files>.planning/ROADMAP.md</files>
  <action>
The bug: ROADMAP Phase 3.4 Success Criterion #1 says the QC engine writes the bitmask into the column `observation_quality`. But `observation_quality` is the lineage enum `{clean, flagged, suspect}` (Phase 2.1 LINEAGE-01). The bitmask belongs in `obs_qc_status` (per REQUIREMENTS.md QC-05 and per Phase 3.4 Success Criterion #5 on line 183 which already says `obs_qc_status`).

Step 1 — Use the `Read` tool to confirm the exact text of line 179. It reads (approximately):
```
  1. **QC engine + bitfield rule registry**: `tradewinds.weather.qc.engine.QCEngine` ports `mostlyright/src/mostlyright/qc/engine.py` verbatim. `QCFlag` registry assigns each rule a power-of-2 bitfield ID; a row's `observation_quality` bitmask records every rule it tripped (allows "flagged AND suspect" composition). `QCEngine.run(rows) → list[QCEntry]` returns one sidecar entry per rule firing per row.
```

Step 2 — Use the `Edit` tool to replace the column name. Use this exact `old_string`:
```
`QCFlag` registry assigns each rule a power-of-2 bitfield ID; a row's `observation_quality` bitmask records every rule it tripped
```

And this exact `new_string`:
```
`QCFlag` registry assigns each rule a power-of-2 bitfield ID; a row's `obs_qc_status` bitmask records every rule it tripped
```

(Surrounding context anchors this to line 179 only — we are NOT touching `observation_quality` references elsewhere in ROADMAP that correctly describe the lineage enum. Specifically, line 19 / line 83 mentioning `observation_quality` enum `{clean, flagged, suspect}` MUST remain untouched.)
  </action>
  <verify>
    <automated>grep -n "observation_quality.*bitmask" .planning/ROADMAP.md || echo "OK: no more bitmask-into-observation_quality references"</automated>
    Then: `grep -n "obs_qc_status.*bitmask" .planning/ROADMAP.md` should return ≥1 hit (line ~179). And `grep -n "observation_quality.*enum" .planning/ROADMAP.md` should still return at least 2 hits (the legitimate enum references on Phase 2.1 lines).
  </verify>
  <done>
- ROADMAP line 179 says `obs_qc_status` bitmask (not `observation_quality` bitmask).
- ROADMAP still describes `observation_quality` as the enum `{clean, flagged, suspect}` elsewhere (Phase 2.1 references untouched).
- Phase 3.4 Success Criterion #1 (QC engine writes bitmask) now uses the same column name as Success Criterion #5 (Mode 2 surfaces `obs_qc_status`) — internally consistent.
  </done>
</task>

<task type="auto">
  <name>Task 5: Update STATE.md frontmatter counts (Finding 5, LOW)</name>
  <files>.planning/STATE.md</files>
  <action>
The bug: STATE.md YAML frontmatter says `total_phases: 10` but the project is now 12 phases (per the Current Position section line 28: "Phase: 1.5 of 12"). And `total_plans: 0` is stale — at minimum Phase 2.1 has 4 plans, Phase 1.5 has 3 plans, and Phase 5 has 6 plans (per ROADMAP).

Step 1 — Use the `Read` tool to read `.planning/STATE.md` lines 1-15 to confirm current frontmatter values.

Step 2 — Count plans by scanning ROADMAP.md `**Plans:**` blocks. From ROADMAP (verified at plan-write time):
- Phase 1.5 — 3 plans (PLAN-01/02/03)
- Phase 2.1 — 4 plans (PLAN-01/02/03/04, per directory listing — the directory `02.1-sprint-2o-lineage-refactor-per-source-provenance/` contains `02.1-PLAN-01-schema-and-validator.md`, `02.1-PLAN-02-merge-policy-port.md`, `02.1-PLAN-03-cache-layer-refactor.md`, `02.1-PLAN-04-integration-parity-gate.md`)
- Phase 5 — 6 plans (PLAN-00 through PLAN-05)
- All other phases — TBD (0 plans)

Total planned plans = 3 + 4 + 6 = 13.

Step 3 — Use the `Edit` tool to update the frontmatter. Use this exact `old_string`:
```
progress:
  total_phases: 10
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 8
```

And this exact `new_string`:
```
progress:
  total_phases: 12
  completed_phases: 0
  total_plans: 13
  completed_plans: 0
  percent: 6
```

(Rationale: `total_phases: 12` matches "Phase: 1.5 of 12" on line 28. `total_plans: 13` is the sum of planned plans across Phase 1.5, 2.1, and 5. `percent: 6` matches the existing prose on line 33: "~6%" — keeps the two values in sync. `completed_plans: 0` is unchanged because Phase 1 Wave 1 was merged but no PLAN.md was ever written for it.)
  </action>
  <verify>
    <automated>grep -A 5 "^progress:" .planning/STATE.md | head -7</automated>
    Expected output should show `total_phases: 12`, `completed_phases: 0`, `total_plans: 13`, `completed_plans: 0`, `percent: 6`.
  </verify>
  <done>
- STATE.md frontmatter `total_phases` is 12 (matches "Phase: 1.5 of 12" body text).
- STATE.md frontmatter `total_plans` is 13 (3 from Phase 1.5 + 4 from Phase 2.1 + 6 from Phase 5).
- STATE.md frontmatter `percent` is 6 (matches the prose "~6%").
  </done>
</task>

<task type="auto">
  <name>Task 6: Commit all 5 fixes, merge to merged-vision, push to origin</name>
  <files>(no file edits — git operations only)</files>
  <action>
This task runs only after Tasks 1-5 have all landed and verified. The branch is `planning/v01-intl-nwp-polymarket` (confirmed at plan-write time via `git branch --show-current`).

Step 1 — Verify clean working state on the current branch:
```bash
git branch --show-current  # expect: planning/v01-intl-nwp-polymarket
git status -s              # expect: only the 4 modified files (REQUIREMENTS, ROADMAP, PLAN-04, STATE)
                           # plus possibly the new quick-plan dir under .planning/quick/260522-lah-*/
git diff --stat            # confirm the changed line counts look surgical (small diffs)
```

If the working state has unexpected files, STOP and surface them. Do NOT proceed to commit until the working state shows only the expected files.

Step 2 — Stage the 4 edited files plus the quick-plan PLAN.md (so the plan itself is preserved alongside its execution):
```bash
git add .planning/REQUIREMENTS.md \
        .planning/ROADMAP.md \
        .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md \
        .planning/STATE.md \
        .planning/quick/260522-lah-fix-5-review-discipline-iteration-4-find/260522-lah-PLAN.md
```

(Do NOT use `git add -A` or `git add .` — only the explicit files above.)

Step 3 — Commit with a clear conventional-commits message via HEREDOC:
```bash
git commit -m "$(cat <<'EOF'
docs(planning): close 5 REVIEW-DISCIPLINE iteration-4 findings

- REQUIREMENTS.md: remove stale POLY-01 deferral entry (POLY-01 is now
  activated under Phase 3.3, was simultaneously deferred under Sprint-0.5+)
- ROADMAP.md line ~19: fix Phase 2.1 summary bullet column name
  `observation_received_at` -> `source_received_at` (matches Success
  Criterion #1)
- Phase 2.1 PLAN-04: flip class (c) null-source assertion + comments to
  reflect merge implementation (`r.get("source_received_at") or ""`
  coerces None -> "" -> lex-MIN -> null-source row wins, not baseline)
- ROADMAP.md line ~179: fix Phase 3.4 QC engine column name
  `observation_quality` (the lineage enum) -> `obs_qc_status` (the
  bitmask column from QC-05)
- STATE.md frontmatter: total_phases 10 -> 12; total_plans 0 -> 13;
  percent 8 -> 6 (consistent with body text "Phase: 1.5 of 12" and "~6%")

All edits are surgical doc text changes — no source code, no schema
changes, no new features. Closes iteration-4 review findings before
Phase 2.1 plans go into execution.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If the commit fails due to pre-commit hooks, fix the underlying issue and create a NEW commit (do NOT use `--amend`, do NOT use `--no-verify`). Per CLAUDE.md the pre-commit hooks here are ruff + format + whitespace + YAML/TOML; markdown files should pass cleanly. If they don't, read the hook output, fix the doc, re-stage, re-commit.

Step 4 — Verify the commit landed:
```bash
git log -1 --oneline
git log -1 --stat | head -20  # confirm 5 files in the commit
```

Step 5 — Switch to `merged-vision`, fast-fail if it doesn't exist or has uncommitted changes:
```bash
git checkout merged-vision
git status  # expect: clean working tree
git pull --ff-only origin merged-vision  # sync with remote before merging
```

If the pull fails or the branch is not clean, STOP and surface the issue. Do NOT force-push or reset.

Step 6 — Merge `planning/v01-intl-nwp-polymarket` into `merged-vision` with `--no-ff` (preserves the planning-branch commit boundary as a merge commit):
```bash
git merge --no-ff planning/v01-intl-nwp-polymarket -m "$(cat <<'EOF'
Merge branch 'planning/v01-intl-nwp-polymarket' into merged-vision

Brings in iteration-4 REVIEW-DISCIPLINE doc fixes:
- POLY-01 deferral cleanup in REQUIREMENTS.md
- Phase 2.1 column name fix in ROADMAP.md
- Phase 2.1 PLAN-04 null-source test assertion flip
- Phase 3.4 QC bitmask column name fix
- STATE.md frontmatter count corrections (10->12 phases, 0->13 plans)

All edits are planning-doc only. Phase 2.1 PLAN-01..04 ready for
execution after this merge.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Step 7 — Verify the merge commit:
```bash
git log -2 --oneline           # expect: merge commit + the docs commit
git log -1 --stat | head -25   # confirm the merge brought in the expected files
```

Step 8 — Push `merged-vision` to origin:
```bash
git push origin merged-vision
```

If the push is rejected (non-fast-forward), STOP and surface the issue — do NOT force-push to merged-vision. Per CLAUDE.md project rules, never use destructive git operations without explicit user instruction.

Step 9 — Switch BACK to `planning/v01-intl-nwp-polymarket` so the working state at end-of-task matches the start-of-task:
```bash
git checkout planning/v01-intl-nwp-polymarket
git branch --show-current  # expect: planning/v01-intl-nwp-polymarket
```

(This restores the development branch as the current branch so subsequent work continues there.)
  </action>
  <verify>
    <automated>git log -1 --format="%H %s" merged-vision | grep -E "Merge branch 'planning/v01-intl-nwp-polymarket'" && git branch --show-current | grep -q "planning/v01-intl-nwp-polymarket" && echo "OK: merge landed on merged-vision and we're back on planning branch"</automated>
    Plus manually: `git log origin/merged-vision -1 --oneline` should show the new merge commit (confirms push succeeded).
  </verify>
  <done>
- Single commit on `planning/v01-intl-nwp-polymarket` containing all 5 doc fixes (4 edited files + the quick-plan PLAN.md preserved).
- Merge commit on `merged-vision` (no-ff, preserves the docs-commit boundary) brought in via `git merge --no-ff planning/v01-intl-nwp-polymarket`.
- `merged-vision` pushed to `origin/merged-vision`.
- Current branch restored to `planning/v01-intl-nwp-polymarket` so subsequent work continues there.
  </done>
</task>

</tasks>

<verification>
After all 6 tasks complete, run these to confirm the entire fix landed cleanly:

```bash
# Finding 1: POLY-01 deferral entry gone
grep -c "POLY-01: Polymarket adapter" .planning/REQUIREMENTS.md  # expect: 0
grep -c "KALSHI-01" .planning/REQUIREMENTS.md                    # expect: 1

# Finding 2: column name fixed in ROADMAP
grep -c "observation_received_at" .planning/ROADMAP.md           # expect: 0
grep -c "source_received_at" .planning/ROADMAP.md                # expect: ≥2

# Finding 3: PLAN-04 class (c) assertion flipped
grep -c "baseline (has ts) should win" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md  # expect: 0
grep -c "null-source sibling wins\|null-source row should win" .planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-04-integration-parity-gate.md  # expect: ≥2

# Finding 4: bitmask column name fixed
grep -c "observation_quality. bitmask" .planning/ROADMAP.md      # expect: 0
grep -c "obs_qc_status. bitmask" .planning/ROADMAP.md            # expect: ≥1

# Finding 5: STATE.md counts updated
grep "total_phases:" .planning/STATE.md                          # expect: total_phases: 12
grep "total_plans:" .planning/STATE.md                           # expect: total_plans: 13
grep "  percent:" .planning/STATE.md                             # expect: percent: 6

# Git state
git log --oneline merged-vision -2                               # expect: merge commit + docs commit
git branch --show-current                                        # expect: planning/v01-intl-nwp-polymarket
```
</verification>

<success_criteria>
- All 5 iteration-4 findings closed via surgical text edits to 4 planning files.
- One commit on `planning/v01-intl-nwp-polymarket` (this branch) bundling all 5 fixes + the quick-plan itself.
- One merge commit on `merged-vision` (--no-ff, preserves docs-commit boundary).
- `merged-vision` pushed to `origin/merged-vision`.
- Working branch restored to `planning/v01-intl-nwp-polymarket`.
- No source code changes, no schema changes, no new features.
- Pre-commit hooks pass without `--no-verify`.
</success_criteria>

<output>
After completion, append a one-line entry to STATE.md's "Quick Tasks Completed" table with the commit SHA + this directory path. (This is a follow-up bookkeeping step, NOT part of this plan's main 6 tasks — the executor can handle it manually after Task 6 verifies.)
</output>
