---
phase: ts-w3-cache-temporal-validator
plan: 07
subsystem: formats
tags: [formats, json, csv, toon, byte-equivalence, fast-check]
status: complete
completed: 2026-05-24
commits:
  - 187c219 feat(ts-w3/07): jsonDumps + jsonLoads — records form + empty-frame envelope
  - d83851f feat(ts-w3/07): csvDumps + csvLoads — RFC-4180 hand-rolled parser
  - 2bffd02 feat(ts-w3/07): toonDumps + toonLoads + roundtrip + subpath export
test_delta: +32 (8 json + 7 csv + 14 toon + 4 roundtrip; 1 csv skipped as documented gap)
---

# TS-W3 Plan 07: Format Serializers Summary

Ported three serializer pairs from Python at `@tradewinds/core/formats`.

## What shipped

- **`jsonDumps` / `jsonLoads`** (`src/formats/json.ts`)
  Non-empty rows emit records form; empty rows emit envelope
  `{columns, data}` so column names survive roundtrip. Throws RangeError
  if columns missing in empty case. `jsonLoads` accepts both forms.
- **`csvDumps` / `csvLoads`** (`src/formats/csv.ts`)
  RFC-4180 hand-rolled parser. No `papaparse` dep (per TS-SDK-DESIGN
  bundle guidance). Null/undefined → empty string. Documented gap:
  embedded newlines inside quoted cells NOT supported (one `.skip` test
  documents the gap).
- **`toonDumps` / `toonLoads`** (`src/formats/toon.ts`)
  TOON v3.0 tabular block format. **Byte-equivalent to Python
  `encode_tabular`** on the 3-row shared fixture
  (`tests/formats/fixtures/toon-byte-equiv.txt`). Encoder handles
  quoting rules for numeric-like strings, control chars, NEL, LSEP/PSEP;
  decoder validates header regex + declared count + column count.
- **Barrel** (`src/formats/index.ts`) + **subpath export**
  (`./formats` in package.json + tsup.config.ts).
- **Root re-export** from `src/index.ts`.
- **fast-check roundtrip** property tests for all 3 formats (100 runs each).

## Key decisions

- **LSEP/PSEP regex handling.** The control chars ` `/` ` MUST
  appear in `NEEDS_QUOTE_CHARS_RE` for Python parity but biome's
  `noControlCharactersInRegex` flags them. Used `// biome-ignore`
  directives + escape-sequence form (` ` not the literal byte) so
  esbuild accepts the regex literal AND biome silences for the parity
  reason. Documented why in the comment.
- **CSV no-papaparse.** Hand-rolled single-line tokenizer keeps the
  core bundle under the 25 KB gate. Embedded-newline-in-quoted-cell
  case explicitly documented as v0.1.0 gap.
- **Empty-row TOON dual form.** `toonDumps([])` → `rows[0]:`. Plus
  optional `columns` arg so `toonDumps([], ["a","b"])` → `rows[0]{a,b}:`
  for parity with Python's DataFrame-aware wrapper.
- **No parquet, no DataFrame.** Explicit TS-FORMAT-01 omissions — no
  stub files. Documented in the formats module header.

## Test count delta

Core: 227 → 259 (+32 passing, +1 skipped).

## Follow-ups

None — plan executed as written. CSV embedded-newline support is a
known limitation, not a follow-up.
