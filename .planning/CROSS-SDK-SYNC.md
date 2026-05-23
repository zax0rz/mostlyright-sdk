# Cross-SDK Sync Process

**Status:** Canonical (binding for all PRs that change `packages/`, `packages-ts/`, `schemas/`, `scripts/export_schemas.py`, or `packages/mcp/` once it exists)
**Drafted:** 2026-05-23
**Owners:** Vu (Python lane), Rob (TypeScript lane)
**Lives at:** `.planning/CROSS-SDK-SYNC.md`

## 0. TL;DR

tradewinds ships from **one repo, two SDKs (Python + TypeScript), one shared schema corpus**. Python is canonical for schemas, station registry, Kalshi map, source priorities, and merge logic. TypeScript consumes those via build-time codegen. The MCP server (Python Phase 5, v0.2+) wraps the Python SDK and inherits its types.

Three sync surfaces, each with its own enforcement mechanism:

| Surface | Source of truth | Propagation | Enforcement |
|---|---|---|---|
| **Schemas + station/Kalshi data** | Python (`tradewinds.core.schemas`, `_internal._stations`, `markets.catalog.kalshi_stations`) | `scripts/export_schemas.py` → `schemas/json/*.json` + `schemas/*.json` → `@tradewinds/codegen` reads + emits TS types | `schema-drift.yml` CI workflow runs exporter + `git diff --exit-code schemas/ packages-ts/*/src/**/generated/`; fails build on drift |
| **Behavioral parity** (function signature changes, new transforms, parser fixes, settlement-math edits) | Whichever lane lands first — usually Python, occasionally TS | Parity ticket filed by the author of the canonical change before the canonical PR merges (see §3) | Parity-ticket label gate on PR; release-readiness check counts unresolved parity tickets per milestone |
| **MCP surface** (Phase 5+) | Python SDK as canonical implementation | `packages/mcp/` wraps SDK; `mcp-sdk-sync.yml` CI parses MCP tool registrations + asserts every tool matches an SDK function signature | `mcp-sdk-sync.yml` fails build on drift; MCP tool schema = SDK function signature via shared TypedDict / dataclass |

**The hard rule going forward:** every PR that changes Python SDK public surface MUST do exactly one of:
1. Land a paired TS change in the same PR (preferred when small).
2. File a `parity-ts` ticket using the template in §3 BEFORE the Python PR merges.
3. Apply the `python_only` label with a reason in the PR description (rare — only for things like Vu's `mostly-light` migration shim).

Same rule applies in reverse for the rare TS-first change.

---

## 1. Schema Sync

### 1.1 Pipeline

```
                                                                          ┌─────────────────┐
packages/core/src/tradewinds/core/schemas/*.py   ─┐                       │   committed     │
packages/core/src/tradewinds/_internal/          │                       │   schemas/      │
  ├── _stations.py                                │                       │  (gitignored?   │
  ├── merge/observations.py                       │                       │   NO — always   │
  └── merge/climate.py                            │   scripts/             │   committed)    │
packages/markets/src/tradewinds/markets/         ├── export_schemas.py ─► ├── json/*.json  │
  catalog/kalshi_stations.py                      │  (deterministic;      │  stations.json  │
packages/core/src/tradewinds/core/merge.py       │   sorted keys; fixed  │  kalshi-...json │
packages/core/src/tradewinds/international.py    ┘   indent; no time)    │  source-...json │
                                                                          └────────┬────────┘
                                                                                   │
                                                                                   ▼
                                                                       ┌────────────────────────┐
                                                                       │  @tradewinds/codegen   │
                                                                       │  (build-time)          │
                                                                       │                        │
                                                                       │  reads schemas/ →      │
                                                                       │  emits:                │
                                                                       │  - .d.ts types         │
                                                                       │  - ajv standalone      │
                                                                       │    validators          │
                                                                       │  - typed stations.ts   │
                                                                       │  - typed kalshi.ts     │
                                                                       │  - typed priority.ts   │
                                                                       └──────────┬─────────────┘
                                                                                  │
                                                                                  ▼
                                                                  packages-ts/*/src/**/generated/*
                                                                  (committed; ts-only tests run
                                                                   against these; no network)
```

### 1.2 The exporter (`scripts/export_schemas.py`)

**Determinism is load-bearing.** Two consecutive runs MUST produce byte-identical output, or `schema-drift.yml` flags false positives and reviewers learn to ignore it (NEVER let drift cron become noise).

Requirements:

1. **Sorted keys** in all JSON outputs (`json.dump(..., sort_keys=True)`).
2. **Fixed indent** (`indent=2`).
3. **No wall-clock fields.** Never emit a `generated_at` or `exported_at` timestamp.
4. **No machine-specific paths.** Use repo-relative paths only; never absolute.
5. **Pinned schema version per file.** Each JSON Schema carries `version` derived from the Python `Schema.schema_id` (e.g. `schema.observation.v1`); the file is replaced wholesale when the version bumps.
6. **Idempotent on enums.** Enum values sorted lexicographically; preserve Python tuple order via `Schema.COLUMNS` only where ordering is semantically meaningful (column order in the source-of-truth schema).
7. **Self-test.** Exporter runs in CI with `--check` flag that asserts second-run output matches first-run output exactly.

Outputs (all under `schemas/` at repo root, all committed to git):

- `schemas/json/schema.observation.v1.json`
- `schemas/json/schema.forecast.iem_mos.v1.json`
- `schemas/json/schema.settlement.cli.v1.json`
- `schemas/json/schema.observation_ledger.v1.json`
- `schemas/json/schema.observation_qc.v1.json`
- `schemas/stations.json` — array of all stations (US + intl) with `{code, icao, ghcnh_id, name, tz, latitude, longitude}` where available
- `schemas/kalshi-settlement-stations.json` — `{ stations: { NYC: {station, citation}, ... }, known_wrong: ["KLGA", ...] }`
- `schemas/source-priority.json` — `{ observation: {...}, climate: {...}, live_v1: {...} }`
- `schemas/polymarket-city-stations.json` — Phase 3.1 catalog (39 cities → 40 ICAOs)
- `schemas/qc-alpha-rules.json` — Phase 3.4 rule IDs + bit positions (so TS QC bit-positions can't drift)
- `schemas/EXPORT_MANIFEST.json` — list of every file the exporter writes + their SHA-256 (used by the drift gate as a checksum manifest)

### 1.3 The codegen consumer (`@tradewinds/codegen`)

Reads `schemas/` and writes to `packages-ts/*/src/**/generated/`. Triggers:

- `pnpm codegen` (manual, idempotent).
- Pre-build step in every `tsup` config: `"prebuild": "pnpm --filter @tradewinds/codegen run codegen"`.
- CI step: `pnpm codegen && git diff --exit-code packages-ts/*/src/**/generated/`.

Generated files are **committed** so:
- Consumers reading source aren't surprised by missing files.
- Reviewers see actual generated diff in PRs (not just "codegen will emit X").
- TS-only builds don't require a Python environment.

Generated headers carry `// AUTO-GENERATED by @tradewinds/codegen from schemas/json/<file>.json. DO NOT EDIT.` — edits are reverted by next codegen run.

### 1.4 Schema version policy

- **Additive change** (adding nullable column, adding enum value, widening type): keep same `vN`, regenerate, bump TS/Python patch.
- **Breaking change** (removing column, narrowing type, removing enum value, renaming): create `schema.<name>.v(N+1)`. Both `vN` and `v(N+1)` coexist for one minor release; consumers migrate; `vN` removed in the minor after that. Document in CHANGELOG.

### 1.5 What is NOT schema-synced

Things explicitly out of the Python→TS codegen pipeline (deliberately re-implemented per language):

- Parsers (AWC, IEM, GHCNh, CLI). Parity-tested instead of codegen-shared because byte-level CSV/JSON/PSV decoding has language idioms.
- Fetchers / HTTP layer. Different HTTP stacks (`httpx` vs `fetch`); behavior tested by parity gate.
- Cache backend. Filesystem-parquet (Python) vs IndexedDB/FS-JSON (TS); behavior tested by per-language cache-skip fixtures.
- Format serializers (json/csv/toon). Output BYTE format is part of the parity gate; implementation is per-language.

---

## 2. Behavioral Parity (the "Parity Ticket" Workflow)

### 2.1 When a parity ticket is required

Any PR touching Python that changes any of the following:

- Public function signature in any of: `tradewinds.research`, `tradewinds.snapshot.*`, `tradewinds.mode2.*`, `tradewinds.transforms.*`, `tradewinds.qc.*`, `tradewinds.discovery.*`, `tradewinds.international.*`, `tradewinds.forecasts.*`, `tradewinds.markets.*`, `tradewinds.core.*`.
- New public function added to any of the above.
- Behavior of merge policy, source priority, settlement math (LST offset, `market_close_utc`, `cli_available_at`), QC rule firing, transform formula.
- New canonical schema, new station, new Kalshi-mapped city, new source ID.
- New exception class.
- New endpoint added to any fetcher (URL change, query-param change, response-shape change).

PRs touching **only** internal helpers (`_internal/_*` names) without public-surface impact do NOT require a parity ticket.

### 2.2 The parity ticket template

File location: GitHub issue OR `.planning/parity-tickets/PT-NNNN-<slug>.md`. Either is acceptable; issue is preferred for visibility. PR body must contain `Parity-Ticket: #NNNN` line if not landing the TS change in the same PR.

```markdown
# Parity Ticket PT-NNNN — <short title>

**Type:** [SCHEMA | FUNCTION | BEHAVIOR | EXCEPTION | ENDPOINT | DATA]
**Direction:** [PYTHON_TO_TS | TS_TO_PYTHON]
**Canonical PR:** #<number> (the PR landing the change in the source language)
**Target SDK:** [tradewinds-ts | tradewinds]
**Filed by:** @<author of canonical PR>
**Assigned to:** @<author of parity PR — defaults to canonical PR author unless explicitly handed off>
**Filed:** YYYY-MM-DD
**Milestone:** [TS v0.1.0 | TS v0.1.x | Python v0.2 | ...]
**Priority:** [P0 (release-blocker) | P1 (next-release) | P2 (eventual)]

## What changed in the canonical SDK

<1-3 sentences. Link to the canonical PR.>

## Exact surface delta

```diff
- old signature / old behavior
+ new signature / new behavior
```

## Why it must port

<Trust gate. e.g.: "TS users hitting the same API would get inconsistent rows
without this fix" or "schema column added is consumed by the Chrome extension
overlay">.

## Port scope

- [ ] Function signature port
- [ ] Test parity (recorded fixture against canonical output)
- [ ] Documentation update
- [ ] Bundle-size verification (if TS) / METADATA verification (if Python)
- [ ] Drift fixture rotation (if behavioral change affects parity gate)

## Verification checklist

- [ ] Generated codegen output unchanged OR regenerated + reviewed
- [ ] Behavior tested against shared fixture under `tests/fixtures/parity/` or `tests/fixtures/parity-ts/`
- [ ] CHANGELOG / `.changeset/*.md` entry in target language
- [ ] Cross-link added to canonical PR body once parity PR opens

## Release-readiness gate

This parity ticket is one of the things that blocks the next minor release of
the target SDK. Counted by `scripts/parity_status.py` (lists open parity
tickets per milestone) in the release checklist.
```

### 2.3 Parity-ticket states

| State | Meaning |
|---|---|
| `filed` | Ticket created; parity PR not yet open |
| `in_progress` | Parity PR open; review underway |
| `resolved` | Parity PR merged; codegen up to date; tests green |
| `accepted_drift` | Explicit decision to leave the languages out of sync; requires a Key-Decision entry in PROJECT.md citing reason (rare; expected ≤ 2-3 times per minor) |
| `cancelled` | Canonical PR reverted; parity ticket no longer needed |

### 2.4 Ownership rule (the "you broke it, you fix it" default)

**Author of the canonical change files the parity ticket and is the default assignee.** If the canonical-PR author can't port (e.g., Vu landing Python work but TS is Rob's specialty), they file the ticket and ping the other lane's lead in the ticket description; the assignment hand-off is explicit (`Assigned to: @rob`).

**Code review enforces this.** The canonical PR reviewer (codex + python-architect for Python; codex + ts-architect — see §6.4 for ts review-panel decision — for TS) checks for:
- Is this a parity-ticket-required change per §2.1? → If yes, look for `Parity-Ticket:` line in PR body OR a paired-language diff in the same PR.
- Is the parity ticket actually filed (not just promised)? → Click the link.
- Does the parity ticket name an assignee? → If not, request changes.

### 2.5 Milestones can't ship with open P0 parity tickets

Release-readiness checklist (already exists for Python v0.1.0; adopt for TS v0.1.0 and all future minors):

- [ ] No open P0 parity tickets against this milestone
- [ ] All P1 parity tickets either resolved or explicitly deferred to next milestone with comment

`scripts/parity_status.py --milestone <name>` lists open tickets; CI release workflow refuses to publish on non-empty P0 list.

---

## 3. MCP Sync (Python Phase 5, v0.2+)

### 3.1 What MCP sync means

The MCP server at `packages/mcp/` (lands in Python Phase 5) exposes tradewinds capabilities as MCP tools to AI agents. Every MCP tool wraps an SDK function. Drift between the MCP tool signature and the SDK function it wraps = silent agent failures.

Three sync invariants:

1. **Tool schema ≡ SDK function signature.** Every MCP tool's input schema is derived from the wrapped SDK function's Python type hints (via a `typing.get_type_hints()` + `inspect.signature()` reflector); the output schema is derived from the function's return annotation. No hand-written tool schemas.
2. **Tool surface ≡ public SDK surface.** Every public SDK function listed in §2.1's parity-ticket trigger list has either a corresponding MCP tool OR an explicit `mcp_tool_excluded: true` annotation in the function's docstring with a reason.
3. **Tool behavior ≡ SDK behavior.** MCP tool tests are recorded-fixture tests that call the tool via JSON-RPC subprocess and compare result against direct SDK call. Any divergence is a sync bug.

### 3.2 The MCP-sync CI workflow (`mcp-sdk-sync.yml`)

Runs on every push that touches `packages/core/`, `packages/weather/`, `packages/markets/`, or `packages/mcp/`. Performs:

1. **Tool-registration reflection.** Walks `packages/mcp/src/tradewinds/mcp/tools/*.py`; for each `@mcp.tool` decorated function, asserts the wrapped SDK function exists and the signatures match (parameters, types, return).
2. **Coverage assertion.** Walks the public surface manifest at `schemas/public-surface.json` (a NEW codegen output — see §3.3) and confirms each entry has either a tool or an `mcp_tool_excluded` marker.
3. **Behavioral parity.** Runs `tests/mcp/test_tool_sdk_parity.py` which spawns the MCP server subprocess and asserts every tool's JSON-RPC response matches the direct SDK call output for a small set of fixed inputs.

Failure modes:

- `New SDK function added without corresponding MCP tool` → Fail. Author either adds the tool or sets `mcp_tool_excluded`.
- `MCP tool signature drift` → Fail. Author updates the tool to match SDK.
- `Behavioral divergence` → Fail. Almost certainly an MCP-side serialization bug.

### 3.3 The public-surface manifest

`scripts/export_schemas.py` is extended (Phase 5 work, NOT v0.1.0 work) to emit `schemas/public-surface.json`:

```json
{
  "functions": [
    {
      "id": "tradewinds.research",
      "module": "tradewinds.research",
      "name": "research",
      "signature": "research(station: str, from_date: str, to_date: str, ...) -> pd.DataFrame",
      "parameters": [...],
      "returns": {"type": "pd.DataFrame", "schema": "schema.research_pairs.v1"},
      "mcp_tool": "research",
      "mcp_tool_excluded_reason": null,
      "added_in": "0.1.0",
      "deprecated_in": null
    },
    ...
  ],
  "classes": [...],
  "schemas": [...]
}
```

This file is the single inventory consumed by:
- `mcp-sdk-sync.yml` for coverage assertion.
- `@tradewinds/codegen` for "do all Python public functions have a TS analog?" cross-language coverage report.
- Documentation builders.

### 3.4 TS↔MCP relationship

TS does NOT consume MCP. TS calls the same HTTP endpoints directly (per `TS-SDK-DESIGN.md`). MCP server is a Python-side wrapper for AI agents and is NOT a sync target for TS.

However: TS may eventually grow an MCP **client** so a TS-based agent can drive a tradewinds MCP server. That's a v0.3+ stretch and is OUT of this document's scope. If it lands, that client treats MCP tools as a remote API and only needs the codegen-shared schemas.

### 3.5 MCP sync activation timeline

- **Now (TS v0.1.0 planning + Python v0.1.0rc1 ready)**: MCP sync rules above are documented but NOT enforced — no MCP code exists yet. Section §3 is a forward-looking contract.
- **Python Phase 5 PLAN-01 lands**: `mcp-sdk-sync.yml` workflow ships. From that point, every MCP-touching PR runs the gate.
- **Python Phase 5 final**: Coverage assertion mandatory at minor-release gate; `mcp_tool_excluded` is the only escape hatch with mandatory reason.

---

## 4. CI Enforcement Matrix

| Workflow | Trigger | What it gates | Where it lives |
|---|---|---|---|
| `schema-drift.yml` | Push/PR touching `packages/core/src/tradewinds/core/schemas/`, `_internal/_stations.py`, `_internal/merge/*.py`, `markets/catalog/kalshi_stations.py`, `international.py`, `scripts/export_schemas.py`, `schemas/`, or `packages-ts/*/src/**/generated/` | Runs `scripts/export_schemas.py` + `pnpm codegen` + `git diff --exit-code` for `schemas/` and `packages-ts/*/src/**/generated/`. Fails on drift. | `.github/workflows/schema-drift.yml` (ships in TS-W0) |
| `test-ts.yml` | Push/PR touching `packages-ts/` or `schemas/` | pnpm install → codegen → biome → tsc → vitest → size-limit. | `.github/workflows/test-ts.yml` (ships in TS-W0) |
| `test.yml` | Push/PR | Existing Python CI (3.11/3.12/3.13 matrix, ruff, mypy, pytest, coverage). | `.github/workflows/test.yml` (already shipped Python Phase 4) |
| `parity-ticket-check.yml` | PR open / synchronize | Inspects PR diff; if it touches §2.1's surface list and PR body lacks `Parity-Ticket:` line AND PR doesn't include a paired-language diff AND PR lacks `python_only`/`typescript_only` label → fail with explanatory comment. | `.github/workflows/parity-ticket-check.yml` (ships in TS-W0) |
| `mcp-sdk-sync.yml` | Push/PR touching `packages/core/`, `packages/weather/`, `packages/markets/`, or `packages/mcp/` | Reflection + coverage + behavioral-parity check per §3.2. | `.github/workflows/mcp-sdk-sync.yml` (ships in Python Phase 5 PLAN-01) |
| `drift-rotate.yml` (Python) | Weekly Mon 07:00 UTC | Live `research()` for 5 parity cases; soft-fail watchdog. | Already shipped Python Phase 4 |
| `drift-rotate-ts.yml` | Weekly Mon 07:30 UTC | TS equivalent — live `research()` for 5 parity cases; soft-fail watchdog; compares against the SAME `tests/fixtures/parity/` expected output. | `.github/workflows/drift-rotate-ts.yml` (ships in TS-W2) |
| `release.yml` (Python) | Tag `v*` (excl. rc) | PyPI trusted publish. | Already shipped Python Phase 4 |
| `release-testpypi.yml` (Python) | Tag `v*rc*` | TestPyPI trusted publish. | Already shipped Python Phase 4 |
| `release-ts.yml` | Tag `vts-*` | npm OIDC trusted publish (4 packages). | `.github/workflows/release-ts.yml` (ships in TS-W7) |
| `wheel-metadata-check.yml` | Push/PR touching `pyproject.toml` | Existing METADATA inspection. | Already shipped Python Phase 4 |

### 4.1 Soft-fail vs hard-fail discipline

- **Hard-fail** (blocks merge): `schema-drift.yml`, `test-ts.yml`, `test.yml`, `parity-ticket-check.yml`, `mcp-sdk-sync.yml`, `wheel-metadata-check.yml`, `release-*.yml`.
- **Soft-fail** (writes report, opens issue, NEVER blocks): `drift-rotate.yml`, `drift-rotate-ts.yml`.

Reason: drift cron watches the OUTSIDE WORLD (upstream APIs may legitimately change shape). Drift signals investigation, not auto-revert. Everything else watches our own outputs and is binary-correct.

---

## 5. Ownership Model

### 5.1 Lane ownership

| Surface | Primary owner | Reviewer | Backup |
|---|---|---|---|
| Python `packages/core/` | Vu | Rob + codex `high` + python-architect | — |
| Python `packages/weather/` | Vu | Rob + codex + python-architect | — |
| Python `packages/markets/` | Rob (founder) | Vu + codex + python-architect | — |
| Python `packages/mcp/` (Phase 5+) | Vu (with founder input on tool selection) | Rob + codex + python-architect + (security for tools touching untrusted input) | — |
| TS `packages-ts/core/` | Rob | Vu + codex + ts-architect (TBD) | — |
| TS `packages-ts/weather/` | Rob | Vu + codex + ts-architect | — |
| TS `packages-ts/markets/` | Rob | Vu + codex + ts-architect | — |
| TS `packages-ts/codegen/` | Rob | Vu (because output feeds back into Python-canonical schemas) | — |
| `scripts/export_schemas.py` | Vu | Rob | — |
| `schemas/` (committed outputs) | Auto-generated; no human owner; reviewed for unexpected churn at PR time | — | — |
| `.planning/CROSS-SDK-SYNC.md` | Vu + Rob jointly | Whoever isn't the author | — |

### 5.2 Hand-off etiquette

When a parity ticket needs cross-lane work:

1. Canonical-PR author opens parity ticket with `Assigned to: <self>`.
2. If self can't port, edits ticket: `Assigned to: <other lane lead>`, posts a comment pinging them and summarizing the surface delta + acceptance criteria.
3. Other lane lead acknowledges within 2 business days.
4. If not acknowledged: escalate via DM; if still no response, post a ROADMAP-level concern in STATE.md.

### 5.3 Decision rights

| Decision | Decided by |
|---|---|
| New Python canonical schema | Python lane owner (Vu) + cross-lane sanity check from Rob |
| New TS-only feature (no Python paired) | Rob, with `typescript_only: true` justification |
| `accepted_drift` on a parity ticket | Both lane leads must agree; logged as Key Decision in PROJECT.md |
| `schema-drift.yml` failure override | Never. Fix the drift. (Hard rule, no exceptions.) |
| Releasing with open P0 parity tickets | Never. Resolve, accept_drift, or defer milestone. |
| MCP-tool exclusion (`mcp_tool_excluded`) | Vu (MCP lane owner once Phase 5 active) with reason in docstring |
| Bumping schema `vN` → `v(N+1)` (breaking) | Both lane leads + cross-language migration plan in PR description |

---

## 6. Change Process — Step-by-Step Recipes

### 6.1 Recipe A: New Python public function (the common case)

**Example:** Vu adds `tradewinds.transforms.bessel_filter(rows, col, order=4)` for a quant who asked.

1. Branch off `main` → `feat/python-bessel-filter`.
2. Implement + tests + docstring in Python.
3. Open Python PR. Body includes:
   ```
   Adds `tradewinds.transforms.bessel_filter`. Closes #N.

   Parity-Ticket: #M (TS port)
   ```
4. File parity ticket `PT-NNNN` with template from §2.2, `Assigned to: @rob`.
5. Python PR runs codex + python-architect + `parity-ticket-check.yml` (which sees the `Parity-Ticket:` line and passes).
6. Python PR merges to `main`.
7. Rob picks up `PT-NNNN`, opens TS PR `feat/ts-bessel-filter`. Body includes:
   ```
   Resolves Parity-Ticket #M. Mirrors `tradewinds.transforms.bessel_filter` from #<canonical-PR>.
   ```
8. TS PR runs codex + ts-architect + `schema-drift.yml` (no schema change, passes trivially) + `test-ts.yml`.
9. TS PR merges; parity ticket updates to `resolved`.
10. Next minor release of both SDKs ships the feature in lockstep.

### 6.2 Recipe B: Schema column added (additive)

**Example:** Add nullable `apparent_temp_c` column to `schema.observation.v1`.

1. Vu edits `packages/core/src/tradewinds/core/schemas/observation.py` to add the ColumnSpec.
2. Vu runs `python scripts/export_schemas.py` locally; observes diff in `schemas/json/schema.observation.v1.json`.
3. Vu runs `pnpm codegen` locally; observes diff in `packages-ts/core/src/schemas/generated/observation.v1.d.ts`.
4. Vu commits Python source + regenerated `schemas/` + regenerated TS `generated/` together.
5. PR includes: parser updates (Python AWC/IEM/GHCNh/CLI parsers populate the new column where derivable) + parity-ticket `PT-NNNN` for TS parser equivalence.
6. `schema-drift.yml` passes (regenerated artifacts committed).
7. After Python PR merge, Rob ports the TS parser change to populate the same column from the same upstream fields. TS parity test asserts new column populated in shared fixture.

### 6.3 Recipe C: Bug fix that changes numeric output

**Example:** Vu finds an off-by-one in `_pairs.market_close_utc()` that affects 0.3% of rows.

1. Vu fixes Python; updates Python tests; updates the 5 parity fixtures with the corrected values; documents the change in the PR.
2. PR body: `Parity-Ticket: #M (TS port — MUST land before next TS release)`.
3. TS parity gate currently passes against OLD fixtures. After Python PR merge, the 5 fixture files have new bytes; TS parity test now FAILS against TS code until ported.
4. Rob's port PR fixes the analogous TS code + reruns parity → green.
5. Both SDKs release patch versions in lockstep with CHANGELOG entry citing the corrected behavior.

### 6.4 Recipe D: TS-only feature (rare)

**Example:** Add a TS helper `formatPairForKalshiOverlay(row)` used only by Rob's Chrome extension.

1. Rob's PR has body line: `typescript_only: true — UI-layer helper specific to browser overlay; no Python equivalent needed.`
2. `parity-ticket-check.yml` sees the label/flag and passes without requiring a parity ticket.
3. PR reviewed normally; merges.
4. No Python work item filed.

### 6.5 Recipe E: Schema breaking change (rare)

**Example:** `schema.observation.v1` needs to become `schema.observation.v2` because `temp_c` semantics change (different reference height).

1. New schema `packages/core/src/tradewinds/core/schemas/observation.py` adds `ObservationV2Schema` (does NOT delete V1).
2. Exporter emits both `schemas/json/schema.observation.v1.json` AND `schemas/json/schema.observation.v2.json`.
3. Codegen emits both `.d.ts` types.
4. Python `research()` defaults to `v1` for one minor; deprecation warning when v2 isn't explicit.
5. Parity-ticket `PT-NNNN` ports v2 to TS.
6. Next minor: TS adds v2 alongside; Chrome extension overlay can opt in via `{schemaVersion: 'v2'}`.
7. Minor after that: `v1` removal in both SDKs (CHANGELOG-cited).
8. Migration logged as Key Decision in PROJECT.md.

---

## 7. Anti-Patterns (DO NOT)

- **Don't hand-edit `schemas/` files.** They're regenerated; your edits are lost on next exporter run.
- **Don't hand-edit `packages-ts/*/src/**/generated/`** for the same reason.
- **Don't suppress drift-gate failures.** If `schema-drift.yml` fails, the answer is always "regenerate + commit," never "skip the check." There is no legitimate case where Python schemas should drift from `schemas/` outputs.
- **Don't merge a Python PR that warrants a parity ticket without one.** Code review enforces this; `parity-ticket-check.yml` enforces this. If both fail to catch it, the next release-readiness gate will.
- **Don't loosen the TS parity gate tolerance** to make a TS-side bug pass. JS Number IS float64; if the bytes don't match, there is either a Python bug (re-fix in both) or a TS bug (fix TS).
- **Don't ship MCP tools that wrap private (`_internal/`) functions.** MCP tools wrap public surface only. If you need a primitive that's private, promote it to public surface first (parity ticket + codegen update).
- **Don't add a new endpoint to a fetcher in one SDK without filing the parity ticket.** Endpoint drift between Python and TS means users with `Mode 2` source-explicit dispatch get different data depending on which SDK they used.
- **Don't accept_drift without logging it in PROJECT.md.** Otherwise drift accumulates silently and becomes the new normal.

---

## 8. Open Questions (resolve before TS-W0 ships)

1. **Should `schemas/` live at repo root or under `.planning/schemas/`?** Default: repo root. Reason: it's a build artifact consumed by codegen, not a planning artifact. (Decision deferred to TS-W0 Wave 2.)
2. **Parity ticket location: GitHub issues vs `.planning/parity-tickets/*.md`?** Default: GitHub issues for visibility; the `.planning/parity-tickets/` path is a fallback for offline / git-only review flows. (Decision deferred; both can coexist.)
3. **`ts-architect` reviewer role.** Python has `python-architect` per REVIEW-DISCIPLINE.md. TS needs an equivalent — likely a `ts-architect` Claude-Code agent or similar second-pair reviewer. (Decision deferred to TS-W0; REVIEW-DISCIPLINE.md updated then.)
4. **`scripts/parity_status.py` implementation.** Lists open parity tickets per milestone for the release-readiness gate. Reads from GitHub via `gh` CLI OR from `.planning/parity-tickets/*.md` front-matter. (Decision deferred to TS-W7.)

---

## 9. Document Lifecycle

This document evolves at the following events:

- **TS-W0 ships**: §8 questions resolved; §4 workflows updated to "shipped".
- **Each new Python public-surface item**: §6 may grow new recipes; §3 manifest updates.
- **Python Phase 5 (MCP) starts**: §3 moves from "forward-looking" to "active"; `mcp-sdk-sync.yml` ships.
- **Per minor release** of either SDK: §5.1 reviewed for ownership drift; release-readiness gate checks §4 workflows still green.

Last-updated marker at bottom of file; bumped by author on each material edit.

---

*Drafted 2026-05-23. Vu + Rob to approve before TS-W0 begins. Once approved, this document is binding across all future PRs.*
