---
phase: ts-w3-cache-temporal-validator
plan: 05
subsystem: validator + codegen
tags: [ajv-standalone, validateRows, python-vocabulary, mv3-csp-safe]
status: complete
commits:
  - aa9aa92 feat(ts-w3/05): ajv-standalone codegen + validateRows public API
test_delta: +19 (3 codegen + 16 validator)
---

# TS-W3 Plan 05: Validator + ajv-standalone Summary

Replaces the TS-W0 placeholder with real ajv-standalone codegen + a
Python-vocabulary `validateRows` public API.

## What shipped

### Codegen (`packages-ts/codegen/src/codegen.ts`)
- ESM ajv-standalone validators per schema id (named export under safe
  identifier — `schema_observation_v1`).
- **No `require("ajv-formats/...")` runtime reference** — `addFormats`
  intentionally NOT called; format keywords (date-time) are silently
  ignored. Format-style validation lives at the wrapper layer where
  callers need it (TimePoint already enforces tz-aware ISO at parse
  time).
- Sorted barrel ensures determinism; `codegen --check` byte-equal
  across two runs.
- `ajv@^8.17.1` added as devDependency (build-time only; NOT in
  `@tradewinds/core` runtime deps — MV3-CSP-safe).

### Validator (`packages-ts/core/src/validator.ts`)
- `validateRows<Row>(rows, schemaId, opts?)` public API.
- Check order matches Python `validator.py`:
  1. Schema lookup → unknown_schema_id
  2. allowSourceDrift type guard (TypeError / RangeError)
  3. Source-attr resolution → source_attr_required
  4. Per-row source-column → source_column_required + SourceMismatchError
  5. retrievedAt resolution → retrieved_at_required
  6. Per-row ajv validation + mixed_null_sentinels scan
- All 9 vocabulary strings verbatim per TS-VALIDATOR-01.
- Sample-cap = 10 on thrown SchemaValidationError.

## Key decisions
- **Drop ajv-formats from codegen output.** The plan called for ajv-
  standalone (no runtime ajv). ajv-formats COMPILES into the standalone
  output as a `require("ajv-formats/dist/formats")` reference — defeats
  the guarantee. Drop addFormats; TimePoint handles date-time elsewhere.
- **ESM with safe identifier export name.** ajv's standalone codegen in
  ESM mode rejects dotted schema ids as export names. Use `safe`
  (e.g. `schema_observation_v1`) and let the barrel map back to the
  canonical id.
- **mixed_null_sentinels = `null` + `undefined` in same column.** Native
  JS analog of Python's `np.nan` + `pd.NA` mix.

## Test delta
Core: 338 → 354 (+16). Codegen: 3 → 6 (+3).
