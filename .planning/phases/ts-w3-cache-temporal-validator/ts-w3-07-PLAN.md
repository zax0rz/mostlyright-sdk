---
phase: ts-w3-cache-temporal-validator
plan: 07
type: execute
wave: 7
depends_on: []
files_modified:
  - packages-ts/core/src/formats/json.ts
  - packages-ts/core/src/formats/csv.ts
  - packages-ts/core/src/formats/toon.ts
  - packages-ts/core/src/formats/index.ts
  - packages-ts/core/src/index.ts
  - packages-ts/core/package.json
  - packages-ts/core/tests/formats/json.test.ts
  - packages-ts/core/tests/formats/csv.test.ts
  - packages-ts/core/tests/formats/toon.test.ts
  - packages-ts/core/tests/formats/roundtrip.test.ts
autonomous: true
requirements:
  - TS-FORMAT-01
must_haves:
  truths:
    - "jsonDumps(rows) emits records-form for non-empty; {columns, data} envelope for empty (matches Python)"
    - "jsonLoads(data) accepts both records-form and envelope-form"
    - "csvDumps(rows) emits header row + value rows, no index column (matches Python pandas index=False)"
    - "csvLoads(data) parses header + rows back into Array&lt;Record&gt;"
    - "toonDumps(rows) emits TOON v3.0 tabular block 'rows[N]{col1,col2}:' format (matches Python encode_tabular output byte-for-byte on shared 3-row fixture)"
    - "toonLoads(data) parses the TOON tabular block back into Array&lt;Record&gt;"
    - "All three pairs roundtrip non-empty AND empty cases"
    - "Parquet + DataFrame serializers are explicitly NOT in v0.1.0 (no stub files; documented in module README)"
  artifacts:
    - path: packages-ts/core/src/formats/json.ts
      provides: "jsonDumps + jsonLoads"
    - path: packages-ts/core/src/formats/csv.ts
      provides: "csvDumps + csvLoads"
    - path: packages-ts/core/src/formats/toon.ts
      provides: "toonDumps + toonLoads"
    - path: packages-ts/core/src/formats/index.ts
      provides: "Barrel exports all 6 functions"
  key_links:
    - from: packages-ts/core/src/index.ts
      to: packages-ts/core/src/formats/index.ts
      via: "export * from './formats/index.js'"
      pattern: "from.*formats"
---

<objective>
Port the three serializer pairs from Python at `@tradewinds/core/formats`:

| Function | Python source | TS contract |
|---|---|---|
| `jsonDumps` / `jsonLoads` | `packages/core/src/tradewinds/core/formats/json.py` | Records form for non-empty rows; `{columns, data}` envelope for empty |
| `csvDumps` / `csvLoads` | `packages/core/src/tradewinds/core/formats/csv.py` | Header + rows, no index column |
| `toonDumps` / `toonLoads` | `packages/core/src/tradewinds/core/formats/toon.py` + `_toon.py` (encoder) + `_toon_list_codec.py` | TOON v3.0 tabular block — byte-equivalent to Python `encode_tabular` |

**Out of scope (per TS-FORMAT-01):**
- `parquet` — deferred to v0.2 via `parquet-wasm` (no stub file).
- `dataframe` — TS has no DataFrames (no stub file).

Both omissions are documented in the formats module README so consumers know why they're absent.

Independent of all other plans (no cache, no temporal, no validator deps) — can run in any wave.
</objective>

<context_files>
- `.planning/REQUIREMENTS.md` TS-FORMAT-01 (canonical text: 3 pairs; JSON empty-frame envelope shape)
- `packages/core/src/tradewinds/core/formats/json.py` (Python source — 77 lines; empty-frame envelope is the load-bearing case)
- `packages/core/src/tradewinds/core/formats/csv.py` (Python source — 51 lines; pandas index=False, default dtype inference)
- `packages/core/src/tradewinds/core/formats/toon.py` (Python source — 416 lines; the DataFrame coercion layer)
- `packages/core/src/tradewinds/core/formats/_toon.py` (Python source — 343 lines; the actual TOON encoder)
- `packages/core/src/tradewinds/core/formats/_toon_list_codec.py` (Python source — 269 lines; list cell encoding)
- `packages-ts/core/src/snapshot.ts` (TS-W1 — style guide)
- `packages-ts/core/package.json` (add `./formats` subpath export)
- TS-SDK-DESIGN.md §8 line 437 ("json: port; csv: port; toon: port; dataframe: skip (no DataFrame); parquet: defer (v0.2)")
- `@tradewinds/codegen` does NOT generate TOON code — port the encoder/decoder by hand from Python
</context_files>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: jsonDumps + jsonLoads</name>
  <files>packages-ts/core/src/formats/json.ts, packages-ts/core/tests/formats/json.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/core/formats/json.py` (full file — 77 lines)
  </read_first>
  <behavior>
    - `jsonDumps(rows: ReadonlyArray&lt;Record&lt;string, unknown&gt;&gt;): string`
      - Non-empty: emits records form via `JSON.stringify(rows)` — `[{"col1":v,"col2":v2},...]`.
      - Empty: emits envelope `{"columns": ["col1","col2"], "data": []}`.
      - **The columns for empty case must be derivable.** Python infers from `df.columns`; TS arrays have no inherent column list. The signature accepts `jsonDumps(rows, columns?)` where `columns` is required ONLY if `rows.length === 0` (otherwise inferred from `Object.keys(rows[0])`). Throw `RangeError("jsonDumps: columns required when rows is empty")` if missing.
      - Timestamps as ISO strings (rows already store ISO strings per the TS conversion rule in TS-SDK-DESIGN.md §6.1).
    - `jsonLoads(data: string): { rows: Array&lt;Record&lt;string, unknown&gt;&gt;; columns: string[] }`
      - Records form (starts with `[`): parses to rows; columns derived from first row's keys (or empty if no rows).
      - Envelope form (starts with `{`): parses `{ columns, data }`; rows is `data`.
      - Returns BOTH rows AND columns so the caller can preserve column order on empty cases (matches Python's "envelope survives empty roundtrip" guarantee).
  </behavior>
  <action>
    Implement `packages-ts/core/src/formats/json.ts`:
    ```typescript
    /** Serialize rows to JSON. Empty rows emit the {columns, data} envelope so column names survive roundtrip. */
    export function jsonDumps(
      rows: ReadonlyArray&lt;Record&lt;string, unknown&gt;&gt;,
      columns?: ReadonlyArray&lt;string&gt;,
    ): string {
      if (rows.length === 0) {
        if (!columns) {
          throw new RangeError("jsonDumps: columns parameter is required when rows is empty (envelope form preserves column order)");
        }
        return JSON.stringify({ columns: [...columns], data: [] });
      }
      return JSON.stringify(rows);
    }

    /** Parse JSON to rows + columns. Accepts both records form and {columns, data} envelope. */
    export function jsonLoads(data: string): { rows: Array&lt;Record&lt;string, unknown&gt;&gt;; columns: string[] } {
      const trimmed = data.trimStart();
      if (trimmed.startsWith("{")) {
        const parsed = JSON.parse(data) as { columns?: unknown; data?: unknown };
        if (Array.isArray(parsed.columns) && Array.isArray(parsed.data)) {
          const columns = parsed.columns.map(String);
          const rows = (parsed.data as Array&lt;Record&lt;string, unknown&gt;&gt;) ?? [];
          return { rows, columns };
        }
        throw new RangeError(`jsonLoads: envelope form must have {columns: string[], data: object[]}; got ${data.slice(0, 80)}`);
      }
      const rows = JSON.parse(data) as Array&lt;Record&lt;string, unknown&gt;&gt;;
      if (!Array.isArray(rows)) throw new RangeError(`jsonLoads: expected array or envelope; got ${typeof rows}`);
      const columns = rows.length &gt; 0 ? Object.keys(rows[0] as Record&lt;string, unknown&gt;) : [];
      return { rows, columns };
    }
    ```

    Write `tests/formats/json.test.ts`:
    - Roundtrip 3-row: dumps → loads → same rows.
    - Empty + columns: `jsonDumps([], ["a","b","c"])` → `'{"columns":["a","b","c"],"data":[]}'`; `jsonLoads(that)` → `{ rows: [], columns: ["a","b","c"] }`.
    - Empty without columns: `jsonDumps([])` → RangeError.
    - Envelope without `data` field: `jsonLoads('{"columns":["a"]}')` → RangeError.
    - Records form with timestamps: rows containing `{event_time: "2025-01-01T12:00:00Z"}` roundtrip as exact strings.
    - Null values preserved (null is JSON-safe).
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- formats/json` ≥ 8 cases all green.
    - `grep -n "envelope\\|columns.*data" packages-ts/core/src/formats/json.ts` confirms envelope handling.
    - `grep -n "jsonDumps\\|jsonLoads" packages-ts/core/src/formats/json.ts` confirms exports.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: csvDumps + csvLoads</name>
  <files>packages-ts/core/src/formats/csv.ts, packages-ts/core/tests/formats/csv.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/core/formats/csv.py` (full file — 51 lines)
    - TS-SDK-DESIGN.md line 543 ("CSV parsing uses a hand-rolled minimal parser, not `papaparse` (if size-limit demands).")
  </read_first>
  <behavior>
    - `csvDumps(rows): string` — emits header (column names from `Object.keys(rows[0])`) + value rows. No index column.
    - `csvLoads(data): { rows, columns }` — parses header + rows. Hand-rolled minimal parser to avoid the `papaparse` bundle hit (TS-SDK-DESIGN explicit guidance).
    - Quote-escaping: RFC 4180 — double-quote any cell containing `,`, `"`, `\n`, or `\r`; escape internal `"` as `""`.
    - Null/undefined cells → empty string (matches Python's pandas behavior).
    - For empty rows: emits an empty string (matches `pd.DataFrame({}).to_csv(index=False)` which emits `""`).
  </behavior>
  <action>
    Implement `packages-ts/core/src/formats/csv.ts`. Implementation outline:
    ```typescript
    function quoteCell(v: unknown): string {
      if (v == null) return "";
      const s = String(v);
      if (/[,"\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
      return s;
    }

    export function csvDumps(rows: ReadonlyArray&lt;Record&lt;string, unknown&gt;&gt;): string {
      if (rows.length === 0) return "";
      const columns = Object.keys(rows[0] as Record&lt;string, unknown&gt;);
      const header = columns.join(",");
      const dataLines = rows.map((r) =&gt; columns.map((c) =&gt; quoteCell((r as Record&lt;string, unknown&gt;)[c])).join(","));
      return [header, ...dataLines].join("\n") + "\n";
    }

    /** Minimal RFC-4180 CSV parser — hand-rolled to avoid papaparse bundle hit. */
    function parseCsvLine(line: string): string[] {
      const out: string[] = [];
      let i = 0;
      const n = line.length;
      while (i &lt;= n) {
        if (i &lt; n && line[i] === '"') {
          let v = "";
          i++;
          while (i &lt; n) {
            if (line[i] === '"') {
              if (line[i + 1] === '"') { v += '"'; i += 2; continue; }
              i++; break;
            }
            v += line[i]; i++;
          }
          out.push(v);
        } else {
          let v = "";
          while (i &lt; n && line[i] !== ",") { v += line[i]; i++; }
          out.push(v);
        }
        if (i &gt;= n) break;
        if (line[i] === ",") { i++; continue; }
      }
      return out;
    }

    export function csvLoads(data: string): { rows: Array&lt;Record&lt;string, string&gt;&gt;; columns: string[] } {
      const trimmed = data.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\n$/, "");
      if (trimmed.length === 0) return { rows: [], columns: [] };
      const lines = trimmed.split("\n");
      const columns = parseCsvLine(lines[0] ?? "");
      const rows = lines.slice(1).map((line) =&gt; {
        const cells = parseCsvLine(line);
        const r: Record&lt;string, string&gt; = {};
        for (let i = 0; i &lt; columns.length; i++) r[columns[i] as string] = cells[i] ?? "";
        return r;
      });
      return { rows, columns };
    }
    ```
    Note: For full RFC 4180 multiline-quoted-cells support, the parser needs to handle newlines INSIDE quoted cells. For v0.1.0 simplicity (and to match the TS-SDK-DESIGN guidance against papaparse), document the limitation: "csvLoads does not handle newlines embedded inside quoted cells. Use jsonDumps/jsonLoads or toonDumps/toonLoads for free-form text columns."

    Write `tests/formats/csv.test.ts`:
    - Roundtrip 3-row simple.
    - Roundtrip with commas in cells (quoting + unquoting).
    - Roundtrip with quotes in cells (double-quote escape).
    - Null/undefined → empty string.
    - Empty rows → empty string.
    - Header-only parse: `csvLoads("a,b,c\n")` → `{ rows: [], columns: ["a","b","c"] }`.
    - Document gap: embedded-newline test that demonstrates the v0.1 limitation (skipped with reason).
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- formats/csv` ≥ 7 cases all green.
    - `grep -n "csvDumps\\|csvLoads" packages-ts/core/src/formats/csv.ts` confirms exports.
    - `grep -n "papaparse" packages-ts/core/package.json` returns nothing (no papaparse dep added).
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: toonDumps + toonLoads + roundtrip suite + subpath export</name>
  <files>packages-ts/core/src/formats/toon.ts, packages-ts/core/src/formats/index.ts, packages-ts/core/src/index.ts, packages-ts/core/package.json, packages-ts/core/tests/formats/toon.test.ts, packages-ts/core/tests/formats/roundtrip.test.ts</files>
  <read_first>
    - `packages/core/src/tradewinds/core/formats/_toon.py` (Python source — `encode_tabular` is the load-bearing function; lines 1-343)
    - `packages/core/src/tradewinds/core/formats/toon.py` (Python wrapper — coercion + the loads parser)
    - TS-SDK-DESIGN.md §6 mentions of TOON
  </read_first>
  <behavior>
    - TOON v3.0 tabular block format (from Python `encode_tabular`):
      ```
      rows[N]{col1,col2,col3}:
        v1a,v2a,v3a
        v1b,v2b,v3b
      ```
      Where `N` is row count, `{...}` is column list, each subsequent line is one row's values.
    - `toonDumps(rows): string` — produces the above block. Columns from `Object.keys(rows[0])` (or empty for `[]`: emits `rows[0]{}:` with no data lines).
    - `toonLoads(data): { rows, columns }` — parses the block back. Validates the header line matches the expected shape.
    - Value coercion mirrors Python:
      - Strings: quoted with `"..."` if they contain `,`, `"`, or whitespace; otherwise bare.
      - Numbers: emitted as `String(value)`. `null` and `undefined` → bare empty string.
      - Booleans: `true` / `false`.
      - Objects/arrays: stringified via `JSON.stringify` with sorted keys (deterministic — matches Python's `_format_key` + `json.dumps(value, sort_keys=True)`).
    - 3-row fixture for byte-equivalence with Python: capture a Python `encode_tabular` output for a known 3-row dict-list, commit as `tests/formats/fixtures/toon-byte-equiv.txt`, and assert `toonDumps(rows) === fixtureContent`.
    - Roundtrip property test (fast-check): for `arbRows`, `toonLoads(toonDumps(rows)).rows` deep-equals `rows` (after string coercion).
  </behavior>
  <action>
    1. Implement `packages-ts/core/src/formats/toon.ts`. The encoder needs ~80-120 lines; the decoder needs ~50-80 lines. Reference Python `_toon.py` `encode_tabular` for the canonical algorithm:
       - Quoting: if value matches `/[,"\\s]/`, wrap in `"..."` and escape internal `"` as `\\"`.
       - Header line: `rows[${rows.length}]{${columns.join(",")}}:`.
       - Data lines: two-space indent, comma-separated quoted/bare cells.
       - Decoder: parse the header regex `/^rows\[(\d+)\]\{(.*)\}:$/`, then read N data lines, then parse each as a quoted-CSV-like line (same parser as csv.ts can be reused or inlined).

    2. Capture a 3-row byte-equivalence fixture from Python:
       ```bash
       uv run python -c "from tradewinds.core.formats._toon import encode_tabular; import json; rows = [{'a':1,'b':'two,three','c':None},{'a':4,'b':'five','c':True},{'a':6,'b':'','c':False}]; print(encode_tabular(rows))" &gt; packages-ts/core/tests/formats/fixtures/toon-byte-equiv.txt
       ```
       Commit the fixture. The TS test reads it and asserts byte-equality:
       ```typescript
       const fixture = readFileSync("./tests/formats/fixtures/toon-byte-equiv.txt", "utf8");
       expect(toonDumps(rows)).toBe(fixture);
       ```
       NOTE: if `encode_tabular` import path differs in current Python (it's a private function — the public wrapper is `toon.dumps`), use the public wrapper and adjust to a DataFrame:
       ```bash
       uv run python -c "import pandas as pd; from tradewinds.core.formats.toon import dumps; df = pd.DataFrame([{'a':1,'b':'two,three','c':None},...]); print(dumps(df))" ...
       ```

    3. Create `packages-ts/core/src/formats/index.ts` barrel:
       ```typescript
       export { jsonDumps, jsonLoads } from "./json.js";
       export { csvDumps, csvLoads } from "./csv.js";
       export { toonDumps, toonLoads } from "./toon.js";
       ```

    4. Update `packages-ts/core/package.json` to add subpath export:
       ```json
       "./formats": {
         "types": "./dist/formats/index.d.ts",
         "import": "./dist/formats/index.mjs",
         "require": "./dist/formats/index.cjs"
       }
       ```
       Add `src/formats/index.ts` to tsup entries.

    5. Re-export from `packages-ts/core/src/index.ts`:
       ```typescript
       export * from "./formats/index.js";
       ```

    6. Write `tests/formats/toon.test.ts`:
       - Byte-equivalence with Python fixture (Task 3 capture).
       - Roundtrip 3-row simple.
       - Empty rows: `toonDumps([])` produces `"rows[0]{}:\n"` (or whatever shape matches Python); roundtrip returns `[]`.
       - Special chars: comma-in-cell, quote-in-cell, whitespace-in-cell.
       - Null cells → empty bare cell.
       - Boolean cells.

    7. Write `tests/formats/roundtrip.test.ts` (covers all 3 formats with fast-check):
       ```typescript
       import fc from "fast-check";
       import { jsonDumps, jsonLoads, csvDumps, csvLoads, toonDumps, toonLoads } from "../../src/formats/index.js";

       describe("roundtrip property: dump → load preserves rows for all 3 formats", () =&gt; {
         const arbRow = fc.record({
           id: fc.integer({ min: -1000, max: 1000 }),
           name: fc.string({ minLength: 0, maxLength: 30 }).filter((s) =&gt; !s.includes("\n")),
           value: fc.option(fc.float({ noNaN: true, noDefaultInfinity: true })),
         });

         it("JSON roundtrip", () =&gt; {
           fc.assert(fc.property(fc.array(arbRow, { minLength: 1, maxLength: 20 }), (rows) =&gt; {
             const dumped = jsonDumps(rows);
             const { rows: loaded } = jsonLoads(dumped);
             return JSON.stringify(loaded) === JSON.stringify(rows);
           }), { numRuns: 100 });
         });

         it("CSV roundtrip (with string coercion)", () =&gt; {
           // CSV loses dtypes — load returns Record&lt;string, string&gt;; assert per-column.
           // ...
         });

         it("TOON roundtrip", () =&gt; {
           fc.assert(fc.property(fc.array(arbRow, { minLength: 0, maxLength: 20 }), (rows) =&gt; {
             const dumped = toonDumps(rows);
             const { rows: loaded } = toonLoads(dumped);
             // TOON loses null vs empty-string distinction depending on encoding; assert column-by-column.
             // ...
           }), { numRuns: 100 });
         });
       });
       ```
  </action>
  <acceptance_criteria>
    - `pnpm --filter @tradewinds/core test -- formats` runs json + csv + toon + roundtrip suites; all green.
    - `packages-ts/core/tests/formats/fixtures/toon-byte-equiv.txt` exists and is non-empty.
    - `toonDumps(fixtureRows) === readFileSync(fixturePath, "utf8")` byte-equality asserted.
    - `grep -n '"./formats"' packages-ts/core/package.json` confirms subpath export.
    - `pnpm --filter @tradewinds/core run build` emits `dist/formats/{json,csv,toon,index}.{mjs,cjs,d.ts}`.
    - From a sibling package: `import { jsonDumps, csvLoads, toonDumps } from "@tradewinds/core/formats"` resolves AND from root: `import { jsonDumps } from "@tradewinds/core"` resolves.
    - `grep -n "parquet\\|dataframe" packages-ts/core/src/formats/index.ts` returns nothing (no stubs).
    - Bundle-size check: `@tradewinds/core` total ≤ 25 KB. If formats push it over, flag follow-up: split TOON into a separate subpath that consumers opt into.
  </acceptance_criteria>
</task>

</tasks>

<verification>
1. `pnpm --filter @tradewinds/core test -- formats` runs all 4 test files (json, csv, toon, roundtrip); all green.
2. `pnpm --filter @tradewinds/core run typecheck` clean.
3. `pnpm --filter @tradewinds/core run build` emits `dist/formats/{json,csv,toon,index}.{mjs,cjs,d.ts}`.
4. `pnpm -r run typecheck` clean — sibling packages can import `@tradewinds/core/formats`.
5. TOON byte-equivalence: `toonDumps(referenceRows) === fixtureFileContent`.
6. Bundle-size: `pnpm --filter @tradewinds/core run size-limit` (if configured) — core stays ≤ 25 KB.
</verification>

<success_criteria>
- TS-FORMAT-01 fully met — 6 functions ship (`jsonDumps/Loads`, `csvDumps/Loads`, `toonDumps/Loads`).
- Empty-frame JSON envelope shape matches Python byte-for-byte.
- TOON encoder byte-equivalent to Python on a shared 3-row fixture.
- CSV parser is hand-rolled (no `papaparse` dep).
- Parquet + DataFrame omissions are explicit (no stub files; documented in module).
- Both subpath (`@tradewinds/core/formats`) AND root (`@tradewinds/core`) imports work.
</success_criteria>

<review_discipline>
TypeScript-only changes under `packages-ts/core/**`. Per `.planning/REVIEW-DISCIPLINE.md`:

- **Reviewers**: codex `high` + **TypeScript Architect** (parallel).
- **Severity gate**: CRITICAL or HIGH only.
- **Loop**: fix on branch, re-dispatch, cap at 3.
- **Rubric calibration**:
  - CRITICAL if TOON encoder output drifts from Python `encode_tabular` byte-for-byte on the shared fixture (silent cross-language drift — every Python TOON consumer would mis-parse TS-produced TOON).
  - CRITICAL if `jsonDumps([])` returns `"[]"` instead of the `{columns, data}` envelope (loses column names on empty cases — Python downstream readers would break).
  - HIGH if `csvDumps` includes an index column (TS-SDK-DESIGN parity gap; Python uses `index=False`).
  - HIGH if `papaparse` or another CSV library is pulled in (TS-SDK-DESIGN explicitly says hand-rolled).
  - HIGH if parquet or dataframe stub files ship (creates phantom surface; documented as out of scope).
  - HIGH if `toonLoads` doesn't validate the header regex and silently returns junk for malformed input.
</review_discipline>
