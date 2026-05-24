---
phase: ts-w3-cache-temporal-validator
plan: 05
type: execute
wave: 5
depends_on:
  - ts-w3-04
files_modified:
  - packages-ts/codegen/src/codegen.ts
  - packages-ts/codegen/package.json
  - packages-ts/codegen/tests/validators.test.ts
  - packages-ts/core/src/schemas/validators/index.ts
  - packages-ts/core/src/validator.ts
  - packages-ts/core/src/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tests/validator.test.ts
autonomous: true
requirements:
  - TS-VALIDATOR-01
must_haves:
  truths:
    - "validateRows(rows, schemaId, opts) throws SchemaValidationError on violations"
    - "violation.rule values use Python vocabulary EXACTLY: source_attr_required, source_column_required, retrieved_at_required, required_column_missing, non_nullable_has_nulls, mixed_null_sentinels, dtype_mismatch, enum_value_violation, unknown_schema_id"
    - "validators are ajv-standalone compiled (no runtime ajv dependency in @tradewinds/core)"
    - "validateRows honors allowSourceDrift: when provided + non-empty, skips the source-identity check"
    - "validateRows checks source-identity invariant via opts.source ?? row[0].source ?? throw source_attr_required"
  artifacts:
    - path: packages-ts/codegen/src/codegen.ts
      provides: "ajv-standalone validator emission — replaces the TS-W0 placeholder"
    - path: packages-ts/core/src/schemas/validators/index.ts
      provides: "Generated barrel re-exporting compiled validators for each schema id"
    - path: packages-ts/core/src/validator.ts
      provides: "validateRows public API + SchemaValidationError integration"
  key_links:
    - from: packages-ts/core/src/validator.ts
      to: packages-ts/core/src/schemas/validators/index.ts
      via: "import { getValidator } from './schemas/validators/index.js'"
      pattern: "schemas/validators"
---

<objective>
Lift the TS-W0 ajv-standalone placeholder (TS-VALIDATOR-01 deferred marker) and ship the real `validateRows(rows, schemaId, opts?)` public API at `@tradewinds/core`. The wire-vocabulary `violations[]` shape MUST match Python `packages/core/src/tradewinds/core/validator.py` exactly — same `rule` strings, same hierarchical check order, same SAMPLE_CAP=10.

The codegen pipeline (`@tradewinds/codegen`) now emits standalone validator FUNCTIONS (one per schema id) using ajv's `standaloneCode` feature. The published `@tradewinds/core` package ships these compiled functions and does NOT depend on `ajv` at runtime — critical for MV3 service-worker CSP (no `unsafe-eval`) and for staying under the 25 KB bundle gate.

Out of scope:
- DataFrame-mode validation (TS has no DataFrames).
- `df.attrs["source"]` analog — TS uses an explicit `opts.source` parameter (callers pass the producer-stamped source; matches the "separate return object" pattern in TS-SDK-DESIGN.md §6.1).
- `df.attrs["retrieved_at"]` analog — uses `opts.retrievedAt` similarly.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-VALIDATOR-01 (canonical vocabulary list)
- `.planning/research/TS-SDK-DESIGN.md` §4.3 line 187 (ajv standalone code generation), line 543 ("Generated validators are ajv-standalone (no runtime ajv)"), line 623
- `packages/core/src/tradewinds/core/validator.py` (full file — port the check order + vocabulary exactly)
- `packages-ts/codegen/src/codegen.ts` (full file — current TS-W0 codegen; the new validator emission goes here)
- `packages-ts/core/src/schemas/validators/index.ts` (current placeholder)
- `packages-ts/core/src/schemas/generated/{observation,settlement.cli,observation_ledger,observation_qc,forecast.iem_mos}.v1.ts` (current generated interfaces — the validators target these schemas)
- `schemas/json/*.json` (canonical JSON Schemas the validators are compiled from)
- `packages-ts/core/src/exceptions/index.ts` lines 209-247 (`SchemaValidationError` constructor + payload)
- [`ajv` standalone docs](https://ajv.js.org/standalone.html) — `standaloneCode` API
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: ajv-standalone codegen emission</name>
  <files>packages-ts/codegen/src/codegen.ts, packages-ts/codegen/package.json, packages-ts/codegen/tests/validators.test.ts, packages-ts/core/src/schemas/validators/index.ts</files>
  <read_first>
    - `packages-ts/codegen/src/codegen.ts` (current — find the placeholder emission block for `validators/index.ts`)
    - `packages-ts/codegen/package.json` (add ajv + ajv-formats devDeps for the BUILD-TIME compile; do NOT add to @tradewinds/core dependencies)
    - `schemas/json/observation.v1.json` (and the other 4 JSON Schemas — what shapes are being compiled)
    - `schemas/EXPORT_MANIFEST.json` (manifest — which schemas are Group A vs Group B)
  </read_first>
  <behavior>
    - Codegen now emits ONE file per Group A schema: `packages-ts/core/src/schemas/validators/{schemaIdSafe}.ts`, each containing the ajv-standalone-compiled `validate` function.
    - Codegen emits a barrel `packages-ts/core/src/schemas/validators/index.ts` exporting `getValidator(schemaId): (data: unknown) =&gt; { valid: boolean; errors: Array&lt;...&gt; }`.
    - The compiled validator MUST be pure JS (no `require('ajv')` references) — verified by grep in tests.
    - Group B schemas (gated per CROSS-SDK-SYNC.md §1.2) compile if the source artifact exists; otherwise the barrel registers `null` for that schema id and `getValidator` throws `unknown_schema_id` on lookup. Matches the Group A/B taxonomy from TS-W0.
    - Codegen `--check` mode (deterministic-output) still passes after this change.
  </behavior>
  <action>
    1. Add devDeps to `packages-ts/codegen/package.json`:
       ```json
       "devDependencies": {
         "ajv": "^8.17.1",
         "ajv-formats": "^3.0.1"
       }
       ```
       Confirm: do NOT add `ajv` to `packages-ts/core/package.json` dependencies. The published package consumes pre-compiled code only.

    2. In `packages-ts/codegen/src/codegen.ts`, replace the placeholder `validators/index.ts` emission with real ajv-standalone compilation:
       ```typescript
       import Ajv from "ajv/dist/2020.js";
       import addFormats from "ajv-formats";
       import standaloneCode from "ajv/dist/standalone/index.js";

       function compileValidators(schemasDir: string, outDir: string): void {
         const ajv = new Ajv({ code: { source: true, esm: true }, allErrors: true, strict: false });
         addFormats(ajv);
         const schemaFiles = ["observation.v1.json", "forecast.iem_mos.v1.json", "settlement.cli.v1.json", "observation_ledger.v1.json", "observation_qc.v1.json"];
         const registered: Array&lt;{ id: string; safeName: string }&gt; = [];
         for (const f of schemaFiles) {
           const path = join(schemasDir, "json", f);
           if (!existsSync(path)) continue; // Group B may be missing
           const schema = JSON.parse(readFileSync(path, "utf8"));
           const id = schema.$id ?? f.replace(/\\.json$/, "");
           const safe = id.replace(/[^a-zA-Z0-9_]/g, "_");
           ajv.addSchema(schema, id);
           const code = standaloneCode(ajv, { [id]: id });
           writeFileSync(join(outDir, "validators", `${safe}.js`), header(`json/${f}`) + code);
           // Also emit a .d.ts shim so TS consumers get types.
           writeFileSync(join(outDir, "validators", `${safe}.d.ts`), `${header(`json/${f}`)}declare const validate: (data: unknown) =&gt; boolean & { errors?: Array&lt;{ instancePath: string; schemaPath: string; keyword: string; params: Record&lt;string, unknown&gt;; message?: string }&gt; }; export default validate;\n`);
           registered.push({ id, safeName: safe });
         }
         // Emit the barrel.
         const barrelLines = [
           header("(generated)"),
           ...registered.map((r) =&gt; `import validate_${r.safeName} from "./${r.safeName}.js";`),
           ``,
           `const VALIDATORS: Record&lt;string, (data: unknown) =&gt; boolean&gt; = {`,
           ...registered.map((r) =&gt; `  ${JSON.stringify(r.id)}: validate_${r.safeName} as (data: unknown) =&gt; boolean,`),
           `};`,
           ``,
           `export function getValidator(schemaId: string): ((data: unknown) =&gt; boolean) | null {`,
           `  return VALIDATORS[schemaId] ?? null;`,
           `}`,
           ``,
           `export function listValidators(): readonly string[] {`,
           `  return Object.freeze(Object.keys(VALIDATORS));`,
           `}`,
         ];
         writeFileSync(join(outDir, "validators", "index.ts"), barrelLines.join("\n"));
       }
       ```
       Wire the call inside the existing codegen orchestrator function.

    3. Write `packages-ts/codegen/tests/validators.test.ts`:
       - After running codegen against a fixture schemas dir, `packages-ts/core/src/schemas/validators/index.ts` exports `getValidator`.
       - `getValidator("schema.observation.v1")` returns a function (not null).
       - `getValidator("unknown.schema")` returns null.
       - The emitted `.js` files do NOT contain `require('ajv')` or `import * as ajv` (grep-assert).
       - `--check` mode (re-run codegen and `git diff --exit-code` simulation) is stable: running codegen twice produces identical bytes.

    4. Run `pnpm --filter @tradewinds/codegen run codegen` to regenerate the validators in `packages-ts/core/src/schemas/validators/`. Commit the regenerated files.
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/codegen test -- validators` ≥ 5 cases all green.
    - `pnpm --filter @tradewinds/codegen run codegen` succeeds.
    - `packages-ts/core/src/schemas/validators/index.ts` is regenerated (no longer the placeholder text); contains `export function getValidator`.
    - `grep -L "require('ajv')\\|require(\"ajv\")\\|from .ajv" packages-ts/core/src/schemas/validators/schema_observation_v1.js` returns the filename (no ajv refs in the compiled output).
    - `ls packages-ts/core/src/schemas/validators/*.js | wc -l` ≥ 3 (at least the 3 always-emitted Group A schemas materialize).
    - `grep -L "ajv" packages-ts/core/package.json` returns the filename (ajv NOT in @tradewinds/core deps).
    - `pnpm --filter @tradewinds/codegen run codegen` followed by `git diff --quiet` (deterministic output).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: validateRows public API + Python-vocabulary violations</name>
  <files>packages-ts/core/src/validator.ts, packages-ts/core/src/index.ts, packages-ts/core/package.json, packages-ts/core/tests/validator.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/core/validator.py` (full file — port check order + vocabulary EXACTLY)
    - `packages-ts/core/src/schemas/validators/index.ts` (Task 1 output — `getValidator`)
    - `packages-ts/core/src/exceptions/index.ts` lines 209-247 (SchemaValidationError constructor)
    - `packages-ts/core/src/schemas/generated/observation.v1.ts` (interface shape — informs what `rows` look like at the type level)
  </read_first>
  <behavior>
    - Signature: `validateRows&lt;Row = Record&lt;string, unknown&gt;&gt;(rows: ReadonlyArray&lt;Row&gt;, schemaId: string, opts?: ValidateOptions): ValidateResult`
    - `ValidateOptions`: `{ source?: string; retrievedAt?: string; allowSourceDrift?: string }`. Notes:
      - `source` is the producer-stamped source string. If absent, the validator falls back to reading the first row's `source` field. If still absent, throws `SchemaValidationError` with `rule: "source_attr_required"`.
      - `retrievedAt` likewise (or `retrieved_at` row field fallback). Missing → throws `rule: "retrieved_at_required"`.
      - `allowSourceDrift` is a non-empty reason string; presence skips the source-identity check (per Python `validator.py` design.md §J).
    - `ValidateResult`: `{ rowCount: number; source: string; retrievedAt: string }` (lightweight registration; full SchemaRegistration shape lifted in TS-W6 if needed).
    - Check order MATCHES PYTHON:
      1. Schema lookup — unknown id → `unknown_schema_id`.
      2. `allowSourceDrift` type guard — non-string OR empty-after-trim → throw TypeError/RangeError loudly.
      3. Source-attr presence — `opts.source ?? rows[0]?.source` — missing → `source_attr_required`.
      4. Per-row source-column check — every row must have `source` AND it must equal the validated source (no nulls). Violations → `SourceMismatchError` (already in exceptions).
      5. `retrievedAt` presence — `opts.retrievedAt ?? rows[i]?.retrieved_at`. Missing → `retrieved_at_required`.
      6. Per-row ajv validation via `getValidator(schemaId)` — collect violations. For each ajv error, map keyword → vocabulary string:
         - `required` → `required_column_missing`
         - `type` → `dtype_mismatch`
         - `enum` → `enum_value_violation`
         - `null` violations from non-nullable cols → `non_nullable_has_nulls`
         - mixed null/undefined sentinels in a single column → `mixed_null_sentinels` (TS analog of Python's `np.nan` vs `pd.NA` mix; TS check: column with both `null` and `undefined` → violation).
      - Sample cap: at most 10 violations in the thrown error's `sampleViolations`.
    - On any violation, throw `SchemaValidationError` constructed with `{ schemaId, violations, quarantineCount: rows.length, sampleViolations: violations.slice(0,10) }`.
  </behavior>
  <action>
    1. Implement `packages-ts/core/src/validator.ts`:
       ```typescript
       import { SchemaValidationError, SourceMismatchError } from "./exceptions/index.js";
       import { getValidator } from "./schemas/validators/index.js";

       const SAMPLE_CAP = 10;

       export interface ValidateOptions {
         readonly source?: string;
         readonly retrievedAt?: string;
         readonly allowSourceDrift?: string;
       }

       export interface ValidateResult {
         readonly rowCount: number;
         readonly source: string;
         readonly retrievedAt: string;
       }

       /** Schema-id → canonical source string (mirrors Python `_registered_source`). */
       const SCHEMA_REGISTERED_SOURCE: Record&lt;string, string&gt; = {
         "schema.observation.v1": "iem.archive",
         // ... others as Python registers them; copy from packages/core/src/tradewinds/core/schemas/*.py
       };

       export function validateRows&lt;Row = Record&lt;string, unknown&gt;&gt;(
         rows: ReadonlyArray&lt;Row&gt;,
         schemaId: string,
         opts: ValidateOptions = {},
       ): ValidateResult {
         const validate = getValidator(schemaId);
         if (validate == null) {
           throw new SchemaValidationError(
             `Unknown schema_id ${JSON.stringify(schemaId)}`,
             { schemaId, violations: [{ rule: "unknown_schema_id" }], quarantineCount: rows.length, sampleViolations: [] },
           );
         }
         // ... allowSourceDrift type guard ...
         // ... source-attr resolution + source_attr_required throw ...
         // ... per-row source column check + SourceMismatchError ...
         // ... retrievedAt resolution + retrieved_at_required throw ...
         // ... per-row ajv validation + violation collection ...
         // ... mixed_null_sentinels per-column scan ...
         // ... if violations.length &gt; 0: throw SchemaValidationError ...
         return { rowCount: rows.length, source: resolvedSource, retrievedAt: resolvedRetrievedAt };
       }
       ```
       Full implementation: ~150 lines. Reference Python `validator.py` for check order. Use the existing `getValidator(schemaId)` from Task 1; map ajv `keyword` to the 9 Python-vocabulary strings.

    2. Re-export from `packages-ts/core/src/index.ts`:
       ```typescript
       export { validateRows, type ValidateOptions, type ValidateResult } from "./validator.js";
       ```

    3. Confirm `package.json` exports — `@tradewinds/core` already exports `.` at the root; validator ships through that.

    4. Write `tests/validator.test.ts` covering each of the 9 vocabulary violations + the registration path:
       - Valid rows → returns `{ rowCount, source, retrievedAt }`.
       - Unknown schema id → throws SchemaValidationError with `violations[0].rule === "unknown_schema_id"`.
       - Missing `opts.source` AND missing `rows[0].source` → throws `source_attr_required`.
       - Per-row source column missing on non-empty rows → throws `source_column_required` (or SourceMismatchError, depending on whether the per-row column is missing vs mismatched; replicate Python).
       - Per-row source-column mismatch → throws SourceMismatchError (NOT SchemaValidationError — matches Python).
       - Missing `opts.retrievedAt` AND missing `rows[i].retrieved_at` → throws `retrieved_at_required`.
       - Required column missing → throws `required_column_missing`.
       - Non-nullable column has null → throws `non_nullable_has_nulls`.
       - Mixed null/undefined sentinels in one column → throws `mixed_null_sentinels`.
       - Wrong dtype (string where number required) → throws `dtype_mismatch`.
       - Enum value violation → throws `enum_value_violation`.
       - `allowSourceDrift: "reason"` → bypasses source-identity check; validation continues.
       - `allowSourceDrift: ""` → throws RangeError ("must be non-empty").
       - `allowSourceDrift: 123` (not a string) → throws TypeError.
       - `sampleViolations` capped at 10 even when 15 rows fail.
       - All thrown SchemaValidationError instances have `err.toDict()` emitting snake_case keys (`schema_id`, `violations`, `quarantine_count`, `sample_violations`).
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- validator` ≥ 15 cases all green.
    - `grep -c "source_attr_required\\|source_column_required\\|retrieved_at_required\\|required_column_missing\\|non_nullable_has_nulls\\|mixed_null_sentinels\\|dtype_mismatch\\|enum_value_violation\\|unknown_schema_id" packages-ts/core/src/validator.ts` ≥ 9 (each vocabulary string appears at least once).
    - `grep -n "export function validateRows" packages-ts/core/src/validator.ts` shows the public API.
    - `grep -L "import.*ajv\\|require.*ajv" packages-ts/core/src/validator.ts` returns the filename (no ajv import in @tradewinds/core source).
    - `pnpm --filter @tradewinds/core run typecheck` clean.
    - Bundle-size check: `@tradewinds/core` total ≤ 25 KB — the compiled ajv-standalone code lands in `dist/schemas/validators/*.js` and is tree-shaken to only the schemas the consumer uses. If at risk, flag a follow-up to switch to per-schema dynamic imports.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/codegen run codegen` regenerates `packages-ts/core/src/schemas/validators/*` deterministically.
2. `pnpm --filter @tradewinds/codegen test` all green (validators.test added).
3. `pnpm --filter @tradewinds/core test -- validator` all green.
4. `pnpm -r run typecheck` clean.
5. `pnpm -r run build` clean — `@tradewinds/core` ships `dist/validator.{mjs,cjs,d.ts}` + `dist/schemas/validators/*.js`.
6. `grep -L "ajv" packages-ts/core/package.json` confirms ajv is NOT a runtime dependency.
7. `pnpm --filter @tradewinds/core run size-limit` (if configured) — `@tradewinds/core` ≤ 25 KB (TS-BUNDLE-01). Flag if validators push it close; mitigation: per-schema dynamic import.
</verification>

<success_criteria>
- TS-VALIDATOR-01 fully met — `validateRows` ships with Python-vocabulary violations; ajv-standalone validators compiled by codegen; no runtime ajv dependency.
- Compiled validators are pure JS (no `eval`, no `require`), MV3-CSP-safe.
- Source-identity invariant honored via `opts.source` parameter + per-row source-column check, matching Python's `df.attrs["source"]` + per-row check semantics.
- All 9 vocabulary strings appear in test assertions verbatim.
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/codegen/**` + `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if `ajv` ends up in `@tradewinds/core` runtime dependencies (breaks MV3 service-worker CSP — `unsafe-eval` required for runtime ajv).
  - CRITICAL if the violation `rule` strings diverge from Python vocabulary by even one character (silent cross-language drift in MCP wire format; every Python downstream parser keys on these exact strings).
  - CRITICAL if `allowSourceDrift` accepts truthy non-string values (per Python iter-7 HIGH fix in `validator.py` line 226-238 — booleans, ints, etc. must NOT bypass the source-identity invariant).
  - HIGH if `getValidator(schemaId)` lookup hard-codes a closed schema set (Group B gated schemas would fail silently when added). Must use the registry barrel from codegen.
  - HIGH if `mixed_null_sentinels` check is missing entirely (Python `_has_mixed_null_sentinels` catches a real data-corruption class).
  - HIGH if codegen `--check` mode is not preserved (schema-drift CI fails non-deterministically).
  - HIGH if `validateRows` is async (Python is sync; signature drift breaks the ergonomic pattern; ajv-standalone is sync — there's no reason for the wrapper to be async).
</review_discipline>
