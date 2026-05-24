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

## Language routing

The two-reviewer loop above is universal. The IDENTITY of the second reviewer (codex `high` is always the first) is selected by the PR's language footprint:

| PR diff touches | Reviewer pair |
|---|---|
| **Python only** — `packages/core/`, `packages/weather/`, `packages/markets/`, `tests/`, `scripts/*.py`, `.github/workflows/*python*`, or Python-only docs (`docs/**.md` referencing Python APIs) | codex `high` + **Python Architect** |
| **TypeScript only** — `packages-ts/**`, `.github/workflows/*ts*` (e.g. `test-ts.yml`, `release-ts.yml`, `drift-rotate-ts.yml`), or TS-only docs (anything under `packages-ts/examples/**`, which counts as language-neutral docs) | codex `high` + **TypeScript Architect** |
| **Mixed** — Python source AND TS source in the same PR (e.g. a Python lift paired with its TS port per CROSS-SDK-SYNC.md §6.1 Recipe A) | codex `high` + **Python Architect** + **TypeScript Architect** running in parallel; loop continues until ALL THREE return clean (no CRITICAL/HIGH) |

**Language-neutral diffs** (root `README.md`, `LICENSE`, `.gitignore`, top-level `.planning/` docs that don't include code/schema fragments, `pyproject.toml`/`package.json` workspace-root metadata without dependency floor changes) follow the trivial-skip rules below regardless of which architect would otherwise route. The never-skip path list still applies — a `pyproject.toml` dependency floor change or a `.planning/CROSS-SDK-SYNC.md` edit containing code-like fragments triggers the loop irrespective of language footprint.

**Schemas + codegen edge case.** A PR that touches `scripts/export_schemas.py` + `schemas/` + `packages-ts/*/src/**/generated/` (the canonical Python→TS codegen flow per CROSS-SDK-SYNC.md §1) routes as **mixed** — the Python Architect reviews the exporter changes and the TypeScript Architect reviews the consumed shape (generated `.d.ts`, runtime validators, typed station/Kalshi imports).

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

## TypeScript Architect rubric

The TypeScript Architect is a Claude general-purpose agent with the "Senior TypeScript Architect" persona — brutal about correctness, idioms, type safety, and bundle/browser-runtime constraints. Same severity-gate discipline as the Python Architect (CRITICAL or HIGH only; no MEDIUM/LOW; no style nits). The reviewer is told to read the diff against the rubric below and emit a PASS or REVISE verdict.

Focus areas (each finding cites the bucket it falls into):

**1. Type safety.**
- `strict: true` plus the four mandated `tsconfig` flags from TS-SDK-DESIGN §3.1 (`strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`) hold — no per-file or per-line opt-outs.
- No unjustified `any` / `unknown` casts. `as X` casts have a comment explaining why the type system can't prove it. Type-guards (`function isX(v: unknown): v is X`) preferred over assertions when the predicate is non-trivial.
- Discriminated unions preferred over runtime tag-checking with `if ('foo' in obj)`. Exhaustive `switch` on discriminants via `const _exhaustive: never = x;` (or equivalent `assertNever` helper).
- Narrowing is explicit at API boundaries (don't smuggle wider types through).

**2. Bundle size impact.**
- Per-package `size-limit` gates from **TS-BUNDLE-01** hold: `@tradewinds/core` ≤ 25 KB, `@tradewinds/weather` ≤ 35 KB, `@tradewinds/markets` ≤ 10 KB, `tradewinds` meta ≤ 70 KB (all min+gzip). PRs that materially grow a bundle MUST show the size-limit report in the PR description; HIGH if a gate is breached without justification.
- No accidental tree-shake breakers: top-level side effects in package source (run-on-import code, top-level `await`, mutating module-scope state), dynamic-key `require` / dynamic `import(name)` where `name` isn't statically analyzable, broad re-export barrels that pull in heavy modules unconditionally.
- No `import *` from heavy deps (e.g. `import * as arrow from 'apache-arrow'` instead of named imports). Optional adapters (Arrow, parquet-wasm) MUST stay behind `peerDependenciesMeta: { optional: true }` and a runtime feature-detect, never a top-level import.

**3. Browser / MV3 compatibility.**
- MV3 service-worker constraints: no `eval`, no `new Function(...)`, no remote code loading; CSP-safe in `script-src 'self'`. `ajv` runtime validators MUST be the `ajv-standalone` precompiled form (per TS-SDK-DESIGN §4.3) — never runtime `ajv` in shipped bundles.
- No Node-only APIs (`node:fs`, `node:path`, `node:crypto.randomBytes`, `node:os`, `node:net`, `process.cwd()`) in the `@tradewinds/core` or `@tradewinds/weather` shared surface. Node-only code (e.g. `FsStore`) lives behind a runtime feature-detect (`typeof process !== 'undefined' && process.versions?.node`) per TS-SDK-DESIGN §5.4, never a top-level import.
- CORS posture preserved per `.planning/research/TS-CORS-MATRIX.md` (per **TS-CORS-01**). If a fetcher is changed to call a new upstream endpoint or change a request shape, CORS posture is re-verified empirically and the matrix updated in the same PR (or a parity ticket filed). HIGH if a new fetch is added with no matrix entry.

**4. API surface parity with Python SDK.**
- Function signatures, return shapes, error types, and casing rules match `.planning/research/PYTHON-SURFACE-INVENTORY.md` for any surface item the TS port covers. Deviations (additive widening, parameter rename, return-shape change, exception class swap) require a CROSS-SDK-SYNC parity ticket per `.planning/CROSS-SDK-SYNC.md` §2.1 — HIGH if the PR introduces drift without a `Parity-Ticket:` line in the PR body or a paired Python diff in the same PR.
- Codegen-shared types (`schemas/json/*.json` → `packages-ts/*/src/**/generated/*.d.ts`) are NOT hand-edited; the rubric calls HIGH on any direct edit to `generated/` (per CROSS-SDK-SYNC.md §7 anti-patterns).
- Per-row source identity / source-mismatch semantics (Python `SourceMismatchError`) are preserved in the TS exception class hierarchy. Public exception classes carry a `toDict()` method analogue (`{ name, message, ...payload }`) for future MCP-client serialization per TS-SDK-DESIGN §1 non-goals (MCP client deferred; serialization shape stays compatible).

**5. TypeScript idioms.**
- Prefer `readonly` / `Readonly<T>` / `ReadonlyArray<T>` on public contracts (rows, options, returned envelopes). Mutating shared rows post-return is a HIGH.
- Named function exports over default exports across all package source (default exports break IDE rename, hide barrels' re-exports, and complicate tree-shaking).
- ESM-first: no CJS-only patterns (`module.exports`, `require()`) in package source. The dual ESM/CJS dist is produced by `tsup`; source stays ESM.
- Avoid `enum` in favor of `const` unions (`as const` arrays + `typeof X[number]` derived unions) — enums emit runtime code that defeats tree-shaking and don't survive `verbatimModuleSyntax`.
- Errors thrown across the API surface are subclasses of the relevant `TradewindsError` analogue, never bare `Error` or `string`.

**Calibration examples.** Same severity gate as Python Architect: CRITICAL = silent data corruption / broken invariant / parity-critical regression; HIGH = meaningful design issue OR test that won't catch what it claims. Examples specific to TS:

- TS adapter emits `source: "awc.live"` while Python emits `"awc"` (or vice-versa), without a parity ticket → CRITICAL (silent per-row source-identity drift; the iter-1 finding from TS-W1 review).
- Top-level `await fetch(...)` added to `@tradewinds/core/src/index.ts` → CRITICAL (breaks MV3 service-worker import + balloons bundle).
- `as any` cast on a row at the public boundary of `research()` → HIGH (smuggles untyped data through a typed contract).
- `import * as luxon from 'luxon'` in `@tradewinds/core` when only `DateTime.fromISO` is needed → HIGH (bundle-size impact; named import required).
- `enum Source { AWC = 'awc', IEM = 'iem' }` added to a generated types file → HIGH (defeats tree-shaking; use `const` union).
- `// @ts-expect-error` with no comment → HIGH (untracked type debt).
- Prettier-ish formatting nit (`,` vs `;` at end of interface line) → skip.
- "Could rename `fetchObs` to `fetchObservations` for clarity" → skip (style nit unless it conflicts with PYTHON-SURFACE-INVENTORY name).

## Lineage

- Inspired by `mostlyright/playbook/review-discipline.md` (398 lines, four reviewers + Compatibility Contract + Blast Radius sections + planned CI enforcement). Adopted: the two-reviewer parallel dispatch idea, severity-gate-at-top-two principle, "loop until clean" framing. Dropped: security-reviewer and architect as separate roles (architect persona merged into python-architect for v0.1.0; security review only when touching auth / secrets / payload validation), Compatibility Contract section (Phase 1 has the parity gate built in; v0.2+ adds it back if/when contracts diverge), CI workflow enforcement (post-Phase-4 polish).
- v0.1.0 is the lean version. v0.2 likely adds security-reviewer + architect as separate roles once the surface grows.
- 2026-05-24: TypeScript Architect reviewer added alongside Python Architect via the language-routing matrix above. Resolves [`CROSS-SDK-SYNC.md` §8 open question #3](./CROSS-SDK-SYNC.md#8-open-questions-resolve-before-ts-w0-ships) ("ts-architect reviewer role — likely a `ts-architect` Claude-Code agent or similar second-pair reviewer; decision deferred to TS-W0; REVIEW-DISCIPLINE.md updated then"). The TS Architect rubric mirrors the Python Architect's severity-gate discipline (CRITICAL/HIGH only; no nits) and is calibrated against TS-SDK-DESIGN §1 (goals/non-goals), §3.1 (mandated tsconfig flags), §4.3 (codegen + ajv-standalone), §5 (browser/CORS), and `.planning/research/PYTHON-SURFACE-INVENTORY.md` (API parity).
