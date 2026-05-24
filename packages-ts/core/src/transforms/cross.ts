// TS-W4 Plan 04 Task 1 — spread (pairwise cross-feature).
//
// Pure row→row port of Python `tradewinds.transforms.spread` (packages/core/
// src/tradewinds/transforms.py:103-105). TS does NOT have pandas Series; we
// operate on a `ReadonlyArray<Row>` and add a derived column
// `{colA}_minus_{colB}` to each output row. Source rows are NOT mutated.
//
// Numeric coercion is STRICT: only `typeof v === 'number' && Number.isFinite(v)`
// passes through. Strings like `'10'` are NOT auto-parsed — upstream parsers
// are responsible for coercion before any transform runs. Matches Wave 2/3
// strictness (lag/diff/rolling/calendar).

/**
 * Pairwise difference between two numeric columns.
 *
 * Mirrors Python `transforms.spread(df, col_a, col_b)`. Derived column name
 * is exactly `{colA}_minus_{colB}`. Value at index i is `rows[i][colA] -
 * rows[i][colB]` when both are finite numbers; otherwise `null`.
 *
 * @param rows  input rows (NOT mutated; pure function)
 * @param colA  minuend column
 * @param colB  subtrahend column
 * @returns     new array of rows, each carrying `{colA}_minus_{colB}` column
 */
export function spread<Row extends Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  colA: string,
  colB: string,
): ReadonlyArray<Row & Record<string, number | null>> {
  const key = `${colA}_minus_${colB}`;
  const out: Array<Row & Record<string, number | null>> = [];
  for (const r of rows) {
    const a = r?.[colA];
    const b = r?.[colB];
    const v =
      typeof a === "number" && Number.isFinite(a) && typeof b === "number" && Number.isFinite(b)
        ? a - b
        : null;
    out.push({ ...(r as Row), [key]: v } as Row & Record<string, number | null>);
  }
  return out;
}
