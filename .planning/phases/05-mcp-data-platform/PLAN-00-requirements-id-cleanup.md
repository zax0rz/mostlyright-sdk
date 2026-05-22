---
phase: 05-mcp-data-platform
plan: 00
type: execute
wave: 0
duration: < 1 hour Claude execution; pre-Wave-1 prerequisite (CONTEXT.md locked decision)
waves: 1
depends_on: []      # Pre-Phase-5 hygiene; runs before any other Phase 5 plan
branch_strategy: single sub-branch off `main` (`phase-5/wave-0/mcp-id-cleanup`); 2-reviewer loop per REVIEW-DISCIPLINE.md; merges to `main` BEFORE Wave 1 starts
requirements: []    # Hygiene task — does not implement any MCP-XX requirement; it CLEANS UP the requirements list so MCP-01..MCP-10 are the unambiguous canonical set
autonomous: false   # Human-verify final REQUIREMENTS.md state + ROADMAP.md cross-refs before merge (the cleanup itself is automated; human confirms no requirement IDs were lost)
files_modified:
  - .planning/REQUIREMENTS.md                  # MODIFY — delete lines 101-108 OLD narrow MCP-01..06 block; delete line 236 ID-collision note; update mapping table; update footer count
  - .planning/ROADMAP.md                       # MODIFY (verify only — should already reference only MCP-01..MCP-10)
  - .planning/STATE.md                         # MODIFY — update `last_activity` and `stopped_at` to note cleanup complete
must_haves:
  truths:
    - "`.planning/REQUIREMENTS.md` lines 101-108 (the OLD '### MCP Server (v0.2 milestone)' block under '## v2 Requirements (Deferred)') are deleted — no narrow MCP-01..MCP-06 entries remain anywhere in the file."
    - "`.planning/REQUIREMENTS.md` line 236 ID-collision note is deleted (`> **ID-collision note:** ...`)."
    - "`.planning/REQUIREMENTS.md` mapping table at lines 251-262 (Phase 5 Traceability) lists each of MCP-01..MCP-10 exactly once with Phase 5 / Pending — no duplicate rows from the deleted narrow block."
    - "`grep -c 'MCP-0[1-6]' .planning/REQUIREMENTS.md` returns exactly 6 (one per ID, all in the canonical MCP-01..MCP-10 block at lines 238-247 + the traceability table)."
    - "`grep -c 'MCP-LEGACY' .planning/REQUIREMENTS.md` returns 0 (option (b) from CONTEXT.md was chosen — DELETE, not renumber)."
    - "`grep -nE 'MCP-(0[7-9]|10)' .planning/REQUIREMENTS.md` returns matches only inside the canonical MCP-01..MCP-10 block (lines 238-247) and the Phase 5 traceability table (lines 251-262)."
    - "`.planning/ROADMAP.md` Phase 5 entry continues to reference `MCP-01..MCP-10` (verified — already correct, no change needed)."
    - "`.planning/REQUIREMENTS.md` v2 Requirements footer count is updated: the deletion drops 6 narrow entries; coverage table footer at lines 220-223 stays at `54 total / 54 mapped / 0 unmapped` for v1 (the narrow MCP-01..06 lived under '## v2 Requirements (Deferred)' which has no count line — verify and document)."
    - "Phase 5 traceability table at lines 251-262 + footer at line 264 (`Phase 5 coverage: 10 requirements, all mapped`) remains unchanged or is updated to reflect the cleaner state."
    - "`.planning/STATE.md` `last_activity` and `stopped_at` fields are updated to: `2026-MM-DD -- Phase 5 ID-collision cleanup complete; MCP-01..MCP-10 is now the unambiguous canonical set; ready to start Phase 5 Wave 1`."
  artifacts:
    - path: .planning/REQUIREMENTS.md
      provides: "Canonical MCP-01..MCP-10 requirement set with no ID collision and no superseded narrow MCP-01..06 entries"
      contains: "MCP-10"
    - path: .planning/ROADMAP.md
      provides: "Verified to reference only the canonical MCP-01..MCP-10 set (no change expected; verify and re-commit if needed)"
      contains: "MCP-01..MCP-10"
    - path: .planning/STATE.md
      provides: "Updated stopped_at + last_activity reflecting cleanup completion"
      contains: "Phase 5 ID-collision cleanup complete"
  key_links:
    - from: .planning/REQUIREMENTS.md (lines 238-247)
      to: .planning/REQUIREMENTS.md (lines 251-262 — Phase 5 Traceability table)
      via: "every MCP-XX (X in 01..10) must appear in BOTH the requirements list AND the traceability table — 1:1 correspondence"
      pattern: "^- \\[ \\] \\*\\*MCP-(0[1-9]|10)\\*\\*"
    - from: .planning/ROADMAP.md (Phase 5 Requirements line)
      to: .planning/REQUIREMENTS.md (lines 238-247 — canonical MCP-01..MCP-10)
      via: "Phase 5 entry's `**Requirements**: MCP-01..MCP-10` line resolves to the canonical block"
      pattern: "Requirements\\*\\*:.*MCP-01\\.\\.MCP-10"
---

<objective>
**Pre-Phase-5 prerequisite — physically resolve the MCP-ID collision per CONTEXT.md locked decision (option (b): DELETE old narrow MCP-01..06 entries).**

REQUIREMENTS.md currently contains TWO sets of `MCP-XX` identifiers:
- **OLD (lines 101-108):** narrow `MCP-01..MCP-06` placeholders covering console script, `catalog_search`, `pull_pairs`, `validate_dataframe`, JSON-RPC tests, TOON serialization — written before the broader Phase 5 vision crystallized.
- **NEW (lines 238-247):** broad Phase 5 `MCP-01..MCP-10` — the canonical vision-aligned set.

The IDs collide. Phase 5 PLAN-01..PLAN-05 reference the NEW MCP-01..MCP-10 throughout. Leaving the OLD entries in REQUIREMENTS.md creates ambiguity: a future maintainer searching for "MCP-04" finds two definitions (old: `validate_dataframe` tool; new: server-enforced temporal safety). Per CONTEXT.md §id_collision: "delete the old narrow MCP-01..MCP-06 entries and treat Phase 5 MCP-01..MCP-10 as canonical."

This plan is a documentation-only edit. No code changes. No tests changed. Run before Wave 1 so PLAN-01..PLAN-05's `requirements:` frontmatter unambiguously resolves to the canonical set.

**Why a plan and not a `/gsd-quick`?** Two reasons:
1. The cleanup is a Phase 5 prerequisite explicitly called out in CONTEXT.md's locked decisions block — it belongs to Phase 5's planning artifact set, not a one-off chore.
2. The 2-reviewer loop per REVIEW-DISCIPLINE.md applies (REQUIREMENTS.md is a planning artifact whose diff contains requirement-ID literals — per REVIEW-DISCIPLINE.md "Never skip" list, planning artifacts with code-like fragments / threshold numbers ARE NOT skip-eligible).

**Out of scope:** Any change to ROADMAP.md Phase 5 prose (already references `MCP-01..MCP-10` correctly per a grep verification step). Any code change. Any test change.

**Output:** Cleaned REQUIREMENTS.md + verified ROADMAP.md cross-refs + updated STATE.md. After merge to `main`, PLAN-01..PLAN-05 can execute knowing each `MCP-XX` in their `requirements:` frontmatter has exactly one definition.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/05-mcp-data-platform/CONTEXT.md
@./CLAUDE.md
</execution_context>

<phase_summary>

**Goal:** Delete OLD narrow MCP-01..MCP-06 entries from REQUIREMENTS.md; verify ROADMAP.md needs no change; bump STATE.md.

**Branch:** `phase-5/wave-0/mcp-id-cleanup` off `main`.

**Atomic commit boundaries:**
- Task 0.1 (REQUIREMENTS.md cleanup + ROADMAP.md verify) → 1 commit
- Task 0.2 (STATE.md bump) → 1 commit

**2-reviewer loop per REVIEW-DISCIPLINE.md:** codex `high` + python-architect. Planning-artifact diff with requirement-ID literals is NOT skip-eligible.

**No pre-merge gates beyond the standard:** ruff (no-op — no Python edits), pre-commit hooks.

</phase_summary>

<tasks>

<task type="auto">
  <name>Task 0.1: Delete OLD narrow MCP-01..MCP-06 block + ID-collision note + verify ROADMAP.md</name>
  <files>.planning/REQUIREMENTS.md, .planning/ROADMAP.md</files>
  <implements>CONTEXT.md §id_collision locked decision — option (b) DELETE</implements>
  <read_first>
    - .planning/phases/05-mcp-data-platform/CONTEXT.md (lines 239-261 — id_collision section, locked decision text, subsumption mapping table)
    - .planning/REQUIREMENTS.md (CURRENT FILE — read fully; lines 97-108 = '## v2 Requirements (Deferred)' header + '### MCP Server (v0.2 milestone)' OLD block to delete; line 236 = ID-collision note to delete; lines 238-247 = canonical NEW MCP-01..MCP-10 block to PRESERVE; lines 251-262 = Phase 5 Traceability table to verify)
    - .planning/ROADMAP.md (lines 94-105 — Phase 5 entry; verify the `**Requirements**: MCP-01..MCP-10` line at line 97 references only the canonical range; lines 16-21 — Phases index for Phase 5)
    - .planning/REVIEW-DISCIPLINE.md (never-skip list — planning artifacts with code-like fragments / requirement IDs are NOT skip-eligible; 2-reviewer loop applies)
  </read_first>
  <action>
    Step 1 — Open `.planning/REQUIREMENTS.md` and perform three precise edits:

    **Edit 1: DELETE the OLD '### MCP Server (v0.2 milestone)' block (currently lines 101-108).**

    Current content to remove (exact text — verify line numbers haven't shifted by re-reading the file first):

    ```markdown
    ### MCP Server (v0.2 milestone)

    - **MCP-01**: `tradewinds-mcp-server` console script registers with Claude Code via `mcp` Python SDK (FastMCP pattern)
    - **MCP-02**: `catalog_search(market, contract_type) → JSON` tool — returns source matrix with validated/known-bad source-tuple combinations
    - **MCP-03**: `pull_pairs(contract, sources, from_date, to_date, format="toon") → bytes|str` tool — wraps `research()` Mode 2, registers schema server-side, returns `schema_id` for later validation
    - **MCP-04**: `validate_dataframe(data, schema_id, format, allow_source_drift=None) → JSON` tool — runs Validator, returns violations + quarantine summary + source-mismatch flags
    - **MCP-05**: JSON-RPC subprocess integration tests for all 3 tools
    - **MCP-06**: TOON serialization at MCP tool boundary (no raw `pd.DataFrame` returns)
    ```

    Delete the entire `### MCP Server (v0.2 milestone)` heading AND its 6 bullet items. Leave the surrounding sections (`### Pandas 3.0 Migration (v0.2)` immediately below, `## v2 Requirements (Deferred)` header above) intact.

    **Edit 2: DELETE the ID-collision note (currently line 236).**

    Current content to remove (exact text):

    ```markdown
    > **ID-collision note:** The earlier `## v2 Requirements (Deferred) > ### MCP Server (v0.2 milestone)` section uses the identifiers `MCP-01..MCP-06` for narrow MCP tool surface (`tradewinds-mcp-server` console script, `catalog_search`, `pull_pairs`, `validate_dataframe`, JSON-RPC tests, TOON serialization). Those entries are SUPERSEDED by the broader Phase 5 vision below — same identifiers, expanded scope. Resolve before Phase 5 PLAN.md is written: either (a) renumber the old entries (e.g. `MCP-LEGACY-01..06`), (b) delete the old entries and treat Phase 5 as canonical, or (c) renumber Phase 5 (e.g. `PLAT-01..10`). Default recommendation: option (b) — the Phase 5 vision subsumes the old narrow MCP tools list.
    ```

    Delete the entire `> **ID-collision note:** ...` blockquote line. Replace with a brief one-line marker:

    ```markdown
    > **Note:** The earlier `## v2 Requirements (Deferred) > ### MCP Server (v0.2 milestone)` section was DELETED on cleanup (option (b) per CONTEXT.md §id_collision). Phase 5 MCP-01..MCP-10 below is the canonical, unambiguous set.
    ```

    This preserves a paper trail that the cleanup happened without forcing readers to dig through git log.

    **Edit 3: VERIFY the Phase 5 Traceability table (lines 251-262).** No edit expected — but read it and confirm each MCP-01..MCP-10 row maps to Phase 5 / Pending with no duplicates. If the table is correct, leave it untouched. If there are duplicates from the deleted OLD block (there shouldn't be — the OLD block lived under v2 Requirements with no traceability rows), surface to user before continuing.

    **Edit 4: VERIFY the v1 footer count at line 220-223 is unchanged.** The deletion was in the v2 Requirements section which has no `**Coverage**` block — only the v1 block at lines 220-223 has the count. Confirm `v1 requirements: 54 total / Mapped to phases: 54 / Unmapped: 0` stays put. If somehow the deletion shifted these numbers, re-derive.

    Step 2 — Open `.planning/ROADMAP.md` and verify (NO edit expected) that:
    - Line 21 (Phase 5 entry in the Phases bullet list) references the new vision document and Phase 5 dependency on Phase 2 + 4 — no narrow MCP-XX IDs.
    - Line 97 (Phase 5 detail Requirements line: `**Requirements**: MCP-01..MCP-10 (see REQUIREMENTS.md § Phase 5: MCP Data Platform)`) references the canonical range. This is already correct per the pre-cleanup grep — confirm.
    - Lines 99-105 (Phase 5 Success Criteria) reference only behavioral descriptions, not bare MCP-XX IDs that could be ambiguous.

    If any ROADMAP.md edit is needed: surface the diff to the user before committing. Expected: none.

    Step 3 — Run the validation grep suite to prove the cleanup is complete:

    ```bash
    # No OLD narrow block remains
    grep -n "### MCP Server (v0.2 milestone)" .planning/REQUIREMENTS.md && echo "FAIL: old header still present" || echo "OK"

    # No MCP-LEGACY renumbering happened (option (b) DELETE, not (a) renumber)
    grep -c "MCP-LEGACY" .planning/REQUIREMENTS.md
    # Expected: 0

    # MCP-01..MCP-10 each appear exactly the expected number of times
    # (once in the canonical bullet list at lines 238-247 + once in the traceability table at lines 251-262 = 2 minimum;
    #  may also appear in deeper-level subsections — verify each ID's hits are all from canonical sections)
    for n in 01 02 03 04 05 06 07 08 09 10; do
      echo "MCP-$n:"
      grep -n "MCP-$n" .planning/REQUIREMENTS.md
    done

    # No `catalog_search` / `pull_pairs` / `validate_dataframe` strings remain (those were the OLD narrow tool names; new vision uses `list_sources`/`describe_source`/`query`/`get_schema`/`ingest`)
    grep -nE "catalog_search|pull_pairs|validate_dataframe" .planning/REQUIREMENTS.md && echo "FAIL: old tool names still present" || echo "OK"

    # ROADMAP.md unchanged for Phase 5 (or only the Phase 5 entry was touched)
    git diff .planning/ROADMAP.md
    ```

    Each grep must produce the expected output. If any FAIL, fix and re-run.

    Step 4 — Run `uv run pre-commit run --all-files` to catch any whitespace / YAML issues introduced by the edits. Expected: green.

    Step 5 — Commit: `docs(phase-5): delete OLD narrow MCP-01..06 block — MCP-01..MCP-10 is now canonical (CONTEXT.md §id_collision option b)`.
  </action>
  <verify>
    <automated>grep -n "### MCP Server (v0.2 milestone)" .planning/REQUIREMENTS.md; test $? -eq 1 && grep -c "MCP-LEGACY" .planning/REQUIREMENTS.md | grep -E "^0$" && grep -nE "catalog_search|pull_pairs|validate_dataframe" .planning/REQUIREMENTS.md; test $? -eq 1 && uv run pre-commit run --all-files</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "### MCP Server (v0.2 milestone)" .planning/REQUIREMENTS.md` returns exit 1 (heading is gone)
    - `grep -c "MCP-LEGACY" .planning/REQUIREMENTS.md` returns 0 (option (b) was DELETE, not renumber)
    - `grep -nE "catalog_search|pull_pairs|validate_dataframe" .planning/REQUIREMENTS.md` returns exit 1 (old tool names are gone)
    - `grep -c "\\*\\*MCP-0[1-9]\\*\\*" .planning/REQUIREMENTS.md` returns 9 (exactly one bold definition per ID, MCP-01..MCP-09)
    - `grep -c "\\*\\*MCP-10\\*\\*" .planning/REQUIREMENTS.md` returns 1 (exactly one bold definition for MCP-10)
    - `grep -c "MCP-LEGACY\\|MCP-01..MCP-06" .planning/REQUIREMENTS.md` returns 0 (collision-note language is gone)
    - `grep -nE "MCP-(0[1-9]|10)" .planning/REQUIREMENTS.md | wc -l` returns ≥ 20 (each ID appears in the canonical bullet list + the traceability table = ~2x each = 20; may be higher if footer counts cite them)
    - `git diff .planning/ROADMAP.md` returns empty or only whitespace-equivalent diff (no Phase 5 prose change expected)
    - `uv run pre-commit run --all-files` exits 0
    - One commit exists on `phase-5/wave-0/mcp-id-cleanup` with the cleanup; commit message references CONTEXT.md §id_collision and "option (b)"
    - No `--no-verify` used
  </acceptance_criteria>
  <done>
    REQUIREMENTS.md has exactly one definition for each MCP-01..MCP-10 (the canonical Phase 5 set). The OLD narrow block + its ID-collision note are deleted. ROADMAP.md is unchanged (confirmed correct). Pre-commit green.
  </done>
</task>

<task type="auto">
  <name>Task 0.2: Bump STATE.md to mark cleanup complete</name>
  <files>.planning/STATE.md</files>
  <implements>Project state hygiene — flag Phase 5 prereq done</implements>
  <read_first>
    - .planning/STATE.md (CURRENT FILE — note `stopped_at`, `last_updated`, `last_activity`, and `Session Continuity` block format)
    - .planning/phases/05-mcp-data-platform/CONTEXT.md (locked decisions — confirm the ID-collision cleanup was the prerequisite called out)
  </read_first>
  <action>
    Step 1 — Read current STATE.md frontmatter and `## Session Continuity` block. Note the existing date/time format.

    Step 2 — Update three fields in the frontmatter:
    - `stopped_at`: replace with a sentence noting Phase 5 ID-cleanup is complete and Wave 1 is ready (preserve a brief reference to the prior position).
    - `last_updated`: current ISO timestamp.
    - `last_activity`: today's date with `Phase 5 ID-collision cleanup complete; ready for Wave 1 (server skeleton + temporal middleware)`.

    Update `## Session Continuity` accordingly.

    DO NOT modify any other section of STATE.md (no progress bumps, no decision-log changes, no quick-tasks-completed table entry — this is a Phase 5 plan, not a `/gsd-quick`). Leave the existing Phase 1 progress bar untouched (`Phase 1.5 of 5` etc.).

    Step 3 — Run `uv run pre-commit run --all-files`. Expected: green.

    Step 4 — Commit: `docs(phase-5): bump STATE.md — ID-collision cleanup complete, Wave 1 ready`.
  </action>
  <verify>
    <automated>grep -c "Phase 5 ID-collision cleanup complete" .planning/STATE.md | grep -E "^[1-9]" && uv run pre-commit run --all-files</automated>
  </verify>
  <acceptance_criteria>
    - `grep "Phase 5 ID-collision cleanup complete" .planning/STATE.md` returns non-empty (the marker phrase is present in at least one field)
    - `grep "last_updated:" .planning/STATE.md` returns a line with a recent (today's) ISO timestamp
    - `grep -c "Phase 1.5" .planning/STATE.md` returns ≥ 1 (Phase 1.5 position context is preserved — STATE bump is additive, not a rewrite)
    - `uv run pre-commit run --all-files` exits 0
    - One commit exists for this task on `phase-5/wave-0/mcp-id-cleanup`
    - No `--no-verify` used
  </acceptance_criteria>
  <done>
    STATE.md flags Phase 5 ID-cleanup complete in `stopped_at` + `last_activity` + `last_updated`. Phase 1.5 position context preserved.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 0.3: Human-verify cleanup is complete + merge to main</name>
  <files>n/a (verification only)</files>
  <implements>Pre-Wave-1 hygiene gate (CONTEXT.md locked decision)</implements>
  <read_first>
    - .planning/REQUIREMENTS.md (POST-EDIT state — confirm OLD narrow block is gone, NEW canonical MCP-01..MCP-10 is intact, traceability table is consistent)
    - .planning/STATE.md (POST-EDIT state — confirm bump is sensible)
    - .planning/REVIEW-DISCIPLINE.md (2-reviewer loop reminder)
  </read_first>
  <what-built>
    Tasks 0.1 + 0.2 complete: REQUIREMENTS.md has the OLD narrow MCP-01..MCP-06 block deleted; the ID-collision note is removed (replaced with a brief paper-trail line); STATE.md is bumped. ROADMAP.md was verified unchanged.
  </what-built>
  <how-to-verify>
    **Step A — Read the diff:**

    ```bash
    git diff main..phase-5/wave-0/mcp-id-cleanup -- .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md
    ```

    Confirm:
    - REQUIREMENTS.md diff shows exactly the deletions described in Task 0.1 (OLD narrow `### MCP Server (v0.2 milestone)` block + ID-collision note) + the one-line paper-trail addition.
    - ROADMAP.md diff is empty (no change expected) OR only whitespace.
    - STATE.md diff shows only the three frontmatter field updates (`stopped_at`, `last_updated`, `last_activity`) + matching `## Session Continuity` updates.

    **Step B — Run the 2-reviewer loop per REVIEW-DISCIPLINE.md:**

    ```bash
    # Codex review (high reasoning, per REVIEW-DISCIPLINE.md — no medium/low for any branch)
    codex review --base main -c 'model_reasoning_effort="high"'

    # Python Architect review (Claude general-purpose agent, "Senior Python Architect" persona)
    # — review the diff; severity gate CRITICAL or HIGH only; PASS or REVISE verdict
    ```

    Expected: both reviewers PASS. The change is a documentation-only edit with no code or schema impact — should be low-friction. If REVISE: fix on the branch, re-dispatch both reviewers.

    **Step C — Merge to main:**

    ```bash
    git checkout main
    git merge --no-ff phase-5/wave-0/mcp-id-cleanup -m "Merge phase-5/wave-0/mcp-id-cleanup: MCP-01..MCP-10 is now canonical (2-reviewer loop: PASS x2, iteration 1)"
    ```

    **Step D — Confirm to user:**

    Report one of:

    (1) **All green:** "MCP-ID cleanup merged to `main`. REQUIREMENTS.md has only canonical MCP-01..MCP-10 (10 entries). Phase 5 Wave 1 (PLAN-01) is now unblocked. Type `approved` to continue."

    (2) **Reviewer revise:** "Codex / python-architect flagged [CRITICAL|HIGH] issue: [summary]. Fix on the branch and re-run the loop."
  </how-to-verify>
  <resume-signal>
    Type `approved` once REQUIREMENTS.md cleanup is merged to `main` (Phase 5 Wave 1 is unblocked). Type `revise` to iterate on the cleanup based on reviewer feedback.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| n/a | Documentation-only edit. No runtime trust boundaries are crossed by this plan. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-5.0-01 | Tampering | REQUIREMENTS.md cleanup accidentally drops a canonical MCP-XX entry | mitigate | Acceptance criteria require exactly 10 bold MCP-XX definitions (MCP-01..MCP-10) post-cleanup. Grep check `grep -c "\*\*MCP-0[1-9]\*\*"` returns 9 + `grep -c "\*\*MCP-10\*\*"` returns 1 = 10 total. If any ID is dropped, the count fails. 2-reviewer loop additionally catches semantic drift. |
| T-5.0-02 | Repudiation | Cleanup happens but no audit trail | mitigate | The brief "**Note:** ... DELETED on cleanup" paper-trail line in REQUIREMENTS.md preserves the rationale without forcing readers to dig through git log. Commit message references CONTEXT.md §id_collision + "option (b)". |
| T-5.0-03 | Information Disclosure / Tampering | Stale references in OTHER files (test fixtures, scripts) still cite OLD narrow MCP-04 (validate_dataframe) | mitigate | Final grep across the whole `.planning/` tree: `grep -rn "validate_dataframe\|catalog_search\|pull_pairs" .planning/` to catch any leftover citations. If found, either update or document as intentionally historical (e.g., in archived SUMMARY files). Codebase grep is a Task 0.1 verify-step extension if reviewer flags. |
| T-5.0-04 / 05 | Denial of Service / Elevation of Privilege | n/a | accept | Documentation-only edit; no privilege/availability boundaries affected. |
</threat_model>

<verification>
## Plan-Level Checks

| Check | Command | Expected |
|-------|---------|----------|
| OLD narrow MCP-01..06 block deleted | `grep -n "### MCP Server (v0.2 milestone)" .planning/REQUIREMENTS.md` | exit 1 (not found) |
| Old tool names gone | `grep -nE "catalog_search\|pull_pairs\|validate_dataframe" .planning/REQUIREMENTS.md` | exit 1 (not found) |
| Canonical MCP-01..MCP-09 each defined exactly once | `grep -c "\*\*MCP-0[1-9]\*\*" .planning/REQUIREMENTS.md` | 9 |
| Canonical MCP-10 defined exactly once | `grep -c "\*\*MCP-10\*\*" .planning/REQUIREMENTS.md` | 1 |
| No MCP-LEGACY renumbering (option (b) was DELETE) | `grep -c "MCP-LEGACY" .planning/REQUIREMENTS.md` | 0 |
| ROADMAP.md Phase 5 unchanged | `git diff main..HEAD .planning/ROADMAP.md` | empty or whitespace-only |
| STATE.md bumped | `grep "Phase 5 ID-collision cleanup complete" .planning/STATE.md` | non-empty |
| Pre-commit hooks green | `uv run pre-commit run --all-files` | exit 0 |
| 2-reviewer loop verdict | (manual — codex high + python-architect) | both PASS |

## Static Regression Guards

```bash
# Ensure NO file under .planning/phases/05-mcp-data-platform/ references the OLD narrow tool names
grep -rnE "catalog_search|pull_pairs|validate_dataframe" .planning/phases/05-mcp-data-platform/ && echo "FAIL: old tool names in Phase 5 docs" || echo "OK"

# Ensure NO Phase 5 PLAN file (created next in Wave 1) references both MCP-04 (server-enforced temporal) AND validate_dataframe in the same context — that would be a sign of muddled requirement
# This is a forward-looking check; runs as part of Wave 1's pre-commit.
```
</verification>

<success_criteria>
- [ ] OLD narrow `### MCP Server (v0.2 milestone)` block (REQUIREMENTS.md lines 101-108) is deleted.
- [ ] OLD ID-collision note (REQUIREMENTS.md line 236) is deleted; replaced with a brief one-line paper-trail marker.
- [ ] ROADMAP.md is unchanged (verified — Phase 5 entry already references only canonical MCP-01..MCP-10).
- [ ] REQUIREMENTS.md has exactly 10 bold MCP-XX definitions (MCP-01..MCP-10) post-cleanup.
- [ ] STATE.md `stopped_at` / `last_updated` / `last_activity` bumped to flag cleanup complete.
- [ ] Pre-commit hooks green (no `--no-verify`).
- [ ] 2-reviewer loop (codex `high` + python-architect) returns PASS x2 in ≤ 3 iterations.
- [ ] Branch `phase-5/wave-0/mcp-id-cleanup` merged to `main` via `git merge --no-ff`.
- [ ] Phase 5 Wave 1 (PLAN-01) is unblocked.
</success_criteria>

<output>
After completion, create `.planning/phases/05-mcp-data-platform/05-00-SUMMARY.md` documenting:

- Lines deleted from REQUIREMENTS.md (exact pre-edit line numbers)
- Verification grep results (all four checks: heading gone, old tool names gone, MCP-01..10 definition count = 10, MCP-LEGACY count = 0)
- 2-reviewer loop verdict (PASS x2 iteration N)
- Merge commit hash on `main`
- Time spent (Claude execution wall time)
- Downstream signal for Wave 1: REQUIREMENTS.md is canonical; PLAN-01 `requirements:` frontmatter MCP-01/04/06/07/08 each resolve unambiguously to the broad Phase 5 vision.
</output>
