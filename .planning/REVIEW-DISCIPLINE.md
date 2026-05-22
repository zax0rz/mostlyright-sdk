# Review Discipline (tradewinds)

Every code change goes through this routine before merging to `merged-vision`. Lean version of [mostlyright/playbook/review-discipline.md](https://github.com/Tarabcak/tradewinds/blob/_archive/review-inspiration); two reviewers instead of four, loop instead of single-shot, severity gate tight enough to keep signal high.

## The two-reviewer loop

For every branch (sub-branches inside a wave, integration branches between waves, etc.) — before `git merge` to `merged-vision`:

1. **Dispatch both reviewers in parallel** against the branch diff vs `merged-vision`:
   - **Codex** — independent cross-model adversarial review. `codex review --base merged-vision -c 'model_reasoning_effort="high"'`. **`high` is the only tier used** — no `medium` / `low` passes for any branch type (parity-critical, trivial, hotfix, follow-up — all run `high`). The savings from a lower tier don't justify the loss of depth in catching design/sequencing/architecture bugs.
   - **Python Architect** — Claude general-purpose agent with the "Senior Python Architect" persona. Brutal about correctness, idioms, test fidelity, blast radius. **Not** style nits.
2. **Collect findings.** Severity gate (only the top two block):
   - **CRITICAL** — bug, security hole, silent data corruption, broken invariant, parity-critical regression
   - **HIGH** — meaningful design issue OR test that won't catch what it claims (tautological assertion, wrong fixture data, leaked state)
   - ~MEDIUM / LOW~ — noted in commit message if relevant; do NOT block on these
3. **If any CRITICAL or HIGH:** fix on the branch (not on `merged-vision`), then **re-dispatch both reviewers**. Loop.
4. **Stop conditions:** both reviewers return clean (no CRITICAL/HIGH), OR iteration count reaches 3. Hitting 3 iterations is a smell — escalate to user before pushing further.
5. **Merge** with `git merge --no-ff` once clean. Commit message references the reviewers and final iteration count.

## When to skip the loop

- Trivial commits: typo fixes in prose, version bumps without API change, README/CONTRIBUTING wording polish, GIF/screenshot swaps.
- The skip is documented in the commit message: `[review-skip: trivial]`.
- **Never skip — even if the change "looks like docs"** — when the diff includes:
  - Anything under `_internal/merge/`, `_internal/_pairs.py`, `_vendor/` (lifted parsers), `research.py`, `tradewinds.weather.cache`, schema files (`_internal/merge/_schemas.py`, `_internal/specs/*.json`), exception payloads, parity-fixture files.
  - **Any planning artifact under `.planning/` whose diff contains code, schema fragments, priority constants, fixture rows, or success-criterion threshold numbers.** A wrong literal in `PLAN.md` (e.g., `awc:3` → `awc:2` in a SOURCE_PRIORITY table, or a typo in an OBSERVATION_SCHEMA field type) propagates straight into Wave-N implementation. PLAN.md prose changes (rewording, reordering paragraphs) ARE skip-eligible; code-like fragments are NOT.
  - Anything touching `pyproject.toml` dependency floors (`tradewinds-weather` ↔ `pyarrow`, `pandas` upper bound, etc.) or pre-commit/pre-push hook config.

## Severity examples (calibration)

- Wrong return type on a public API → CRITICAL
- Test asserts subset that's trivially true (passes even if invariant disappears) → HIGH
- `tmp.rename(dest)` fails on Windows when dest exists → HIGH (real cross-platform bug)
- A docstring typo → skip
- Could use a comprehension instead of a loop → skip
- `dict` ordering vs `OrderedDict` performance preference → skip

## Reviewer prompt rules

- Tell the reviewer the severity gate explicitly ("only CRITICAL or HIGH").
- Tell them what NOT to report ("skip MEDIUM/LOW", "no nits", "no style").
- Give them the diff + the source of truth (canonical schema, design doc section, PLAN.md task spec).
- Ask for PASS or REVISE verdict, not free-form prose.

## Lineage

- Inspired by `mostlyright/playbook/review-discipline.md` (398 lines, four reviewers + Compatibility Contract + Blast Radius sections + planned CI enforcement). Adopted: the two-reviewer parallel dispatch idea, severity-gate-at-top-two principle, "loop until clean" framing. Dropped: security-reviewer and architect as separate roles (architect persona merged into python-architect for v0.1.0; security review only when touching auth / secrets / payload validation), Compatibility Contract section (Phase 1 has the parity gate built in; v0.2+ adds it back if/when contracts diverge), CI workflow enforcement (post-Phase-4 polish).
- v0.1.0 is the lean version. v0.2 likely adds security-reviewer + architect as separate roles once the surface grows.
