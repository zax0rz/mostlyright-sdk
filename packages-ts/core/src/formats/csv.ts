// CSV format — pandas-style serialization without an index column.
//
// Mirrors `packages/core/src/tradewinds/core/formats/csv.py`:
//   - dumps emits header row + value rows, no index column
//   - loads parses header + rows back into Array<Record<string,string>>
//   - all values stringify to "" if null/undefined (matches pandas NaN
//     emit behavior + the load-side empty-cell → empty-string convention)
//
// Hand-rolled minimal RFC-4180 parser to avoid the `papaparse` bundle hit
// (TS-SDK-DESIGN §5.4 explicit guidance). Limitation: does NOT handle
// newlines embedded inside quoted cells. Callers with free-form text
// should prefer jsonDumps/jsonLoads or toonDumps/toonLoads.

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
 */
export function csvDumps(rows: ReadonlyArray<Record<string, unknown>>): string {
  if (rows.length === 0) return "";
  const columns = Object.keys(rows[0] as Record<string, unknown>);
  const header = columns.join(",");
  const dataLines = rows.map((r) =>
    columns.map((c) => quoteCell((r as Record<string, unknown>)[c])).join(","),
  );
  return `${[header, ...dataLines].join("\n")}\n`;
}

/**
 * Minimal RFC-4180 single-line tokenizer — splits one row into cells.
 * Quoted cells unwrap doubled internal quotes. Does NOT handle embedded
 * newlines (the caller pre-splits on `\n`).
 */
function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  const n = line.length;
  let i = 0;
  while (i <= n) {
    if (i < n && line[i] === '"') {
      // Quoted cell — scan to matching close quote, unwrapping `""` → `"`.
      let v = "";
      i++;
      while (i < n) {
        if (line[i] === '"') {
          if (line[i + 1] === '"') {
            v += '"';
            i += 2;
            continue;
          }
          i++;
          break;
        }
        v += line[i];
        i++;
      }
      out.push(v);
    } else {
      // Bare cell — read until next comma or EOL.
      let v = "";
      while (i < n && line[i] !== ",") {
        v += line[i];
        i++;
      }
      out.push(v);
    }
    if (i >= n) break;
    if (line[i] === ",") {
      i++;
    }
  }
  return out;
}

/**
 * Parse a CSV string into rows + columns.
 *
 * Returns string-valued cells; CSV is dtype-lossy (pandas
 * read_csv would re-infer dtypes — we leave that to the caller).
 *
 * Empty input → `{ rows: [], columns: [] }`. Header-only input →
 * `{ rows: [], columns: [...] }`.
 */
export function csvLoads(data: string): {
  rows: Array<Record<string, string>>;
  columns: string[];
} {
  // Normalize line endings + strip exactly one trailing newline.
  const normalized = data.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\n$/, "");
  if (normalized.length === 0) return { rows: [], columns: [] };
  const lines = normalized.split("\n");
  const columns = parseCsvLine(lines[0] ?? "");
  const rows = lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    const r: Record<string, string> = {};
    for (let i = 0; i < columns.length; i++) {
      r[columns[i] as string] = cells[i] ?? "";
    }
    return r;
  });
  return { rows, columns };
}
