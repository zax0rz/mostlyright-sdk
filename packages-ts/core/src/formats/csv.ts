// CSV format — pandas-style serialization without an index column.
//
// Mirrors `packages/core/src/tradewinds/core/formats/csv.py`:
//   - dumps emits header row + value rows, no index column
//   - loads parses header + rows back into Array<Record<string,string>>
//   - all values stringify to "" if null/undefined (matches pandas NaN
//     emit behavior + the load-side empty-cell → empty-string convention)
//
// Hand-rolled RFC-4180 parser to avoid the `papaparse` bundle hit
// (TS-SDK-DESIGN §5.4 explicit guidance). Iter-1 C4: the parser is now
// stateful (character-level state machine) so it correctly preserves
// newlines inside quoted cells — which `csvDumps` itself emits when a
// cell contains `\n`. Previously `csvLoads` line-split first, breaking
// every multi-line quoted cell into spurious extra rows.

const QUOTE_NEEDED = /[,"\n\r]/;

function quoteCell(value: unknown): string {
  if (value == null) return "";
  const s = String(value);
  if (QUOTE_NEEDED.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/**
 * Serialize rows to a CSV string. Column names come from
 * `Object.keys(rows[0])`. Empty rows emits an empty string (matches
 * `pd.DataFrame({}).to_csv(index=False)`).
 *
 * Iter-2 C7: header cells are quoted the same way as data cells.
 * Python's `DataFrame.to_csv` quotes header strings on the same
 * triggers as values; without this guard a column name like `"a,b"`
 * would dump as two headers and roundtrip into the wrong schema.
 */
export function csvDumps(rows: ReadonlyArray<Record<string, unknown>>): string {
  if (rows.length === 0) return "";
  const columns = Object.keys(rows[0] as Record<string, unknown>);
  const header = columns.map(quoteCell).join(",");
  const dataLines = rows.map((r) =>
    columns.map((c) => quoteCell((r as Record<string, unknown>)[c])).join(","),
  );
  return `${[header, ...dataLines].join("\n")}\n`;
}

/**
 * Stateful RFC-4180 parser. Reads the whole `data` buffer character by
 * character, tracking whether the cursor is inside a quoted cell. Inside
 * a quoted cell every byte except `""` (escaped quote → literal `"`) and
 * the closing `"` is preserved verbatim — including newlines and commas,
 * which is the whole point of the quoting.
 *
 * Returns the parsed rows as `string[][]` (the header is row 0). Empty
 * `data` returns `[]`. A trailing newline is treated as a row terminator
 * (no spurious empty row), matching `pd.read_csv` and `csvDumps`'s emit.
 *
 * CR / CRLF normalization: standalone `\r` or `\r\n` outside a quoted
 * cell collapse to `\n`. INSIDE a quoted cell every newline byte is
 * preserved as-is to keep the roundtrip lossless.
 */
function parseCsvBuffer(data: string): string[][] {
  const rows: string[][] = [];
  let cur: string[] = [];
  let cell = "";
  let inQuotes = false;
  let i = 0;
  const n = data.length;

  while (i < n) {
    const ch = data[i];

    if (inQuotes) {
      if (ch === '"') {
        // Lookahead: doubled quote inside a quoted cell → literal `"`.
        if (data[i + 1] === '"') {
          cell += '"';
          i += 2;
          continue;
        }
        // Otherwise this closes the quoted cell.
        inQuotes = false;
        i++;
        continue;
      }
      // Any other char (including raw `\n`/`\r`/`,`) is part of the cell.
      cell += ch;
      i++;
      continue;
    }

    // OUTSIDE a quoted cell:
    if (ch === '"') {
      // Opening quote. Per RFC 4180, a quoted cell starts at the
      // beginning of a field — but we accept a stray `"` mid-field
      // gracefully (matching `csv.reader` permissive mode): treat it as
      // entering quoted mode. The next `"` (unless doubled) ends it.
      inQuotes = true;
      i++;
      continue;
    }
    if (ch === ",") {
      cur.push(cell);
      cell = "";
      i++;
      continue;
    }
    if (ch === "\r") {
      // CR or CRLF outside quotes → row terminator. Consume optional LF.
      cur.push(cell);
      rows.push(cur);
      cur = [];
      cell = "";
      i++;
      if (i < n && data[i] === "\n") i++;
      continue;
    }
    if (ch === "\n") {
      cur.push(cell);
      rows.push(cur);
      cur = [];
      cell = "";
      i++;
      continue;
    }
    cell += ch;
    i++;
  }

  // Flush the trailing record. Match csvDumps which always emits a final
  // `\n`: if the buffer ends on a newline we already pushed the final
  // row and `cur`/`cell` are both empty — skip in that case.
  if (cell.length > 0 || cur.length > 0) {
    cur.push(cell);
    rows.push(cur);
  }
  return rows;
}

/**
 * Parse a CSV string into rows + columns.
 *
 * Returns string-valued cells; CSV is dtype-lossy (pandas
 * read_csv would re-infer dtypes — we leave that to the caller).
 *
 * Empty input → `{ rows: [], columns: [] }`. Header-only input →
 * `{ rows: [], columns: [...] }`.
 *
 * Iter-1 C4: stateful parser preserves newlines inside quoted cells, so
 * `csvLoads(csvDumps(rows))` is now a faithful roundtrip even when cells
 * contain `\n` — previously the line-splitter exploded such cells into
 * extra rows.
 */
export function csvLoads(data: string): {
  rows: Array<Record<string, string>>;
  columns: string[];
} {
  if (data.length === 0) return { rows: [], columns: [] };
  const parsed = parseCsvBuffer(data);
  if (parsed.length === 0) return { rows: [], columns: [] };
  const columns = parsed[0] ?? [];
  const dataRows = parsed.slice(1);
  const rows = dataRows.map((cells) => {
    const r: Record<string, string> = {};
    for (let i = 0; i < columns.length; i++) {
      r[columns[i] as string] = cells[i] ?? "";
    }
    return r;
  });
  return { rows, columns };
}
