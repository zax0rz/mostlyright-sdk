// TS-W4 Plan 02 Task 1 — lag transform.
//
// Pure row→row port of Python `tradewinds.transforms.lag` (packages/core/src/
// tradewinds/transforms.py:43-45). TS does NOT have pandas Series; we operate
// on a `ReadonlyArray<Row>` and add a derived column `{col}_lag_{n}` to each
// output row. Source rows are NOT mutated.
//
// Numeric coercion is STRICT: only `typeof v === 'number' && Number.isFinite(v)`
// passes through. Strings like `'3.5'` are NOT auto-parsed — upstream parsers
// (the AWC / IEM / CLI adapters) are responsible for coercion before any
// transform runs. This avoids silent type confusion in the data layer.

/**
 * Shift a column by `n` rows.
 *
 * Mirrors Python `pd.Series.shift(periods=n)` semantics: at output index `i`,
 * the derived column carries `rows[i-n][col]` if available, else `null`.
 *
 * @param rows  input rows (NOT mutated; pure function)
 * @param col   column name to lag
 * @param n     positive integer; rows at index `< n` get `null` in the derived column
 * @returns     new array of rows, each carrying `{col}_lag_{n}` derived column
 * @throws RangeError if `n < 1` or `!Number.isInteger(n)`
 */
export function lag<Row extends Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  col: string,
  n = 1,
): ReadonlyArray<Row & Record<string, number | null>> {
  if (!Number.isInteger(n) || n < 1) {
    throw new RangeError(`lag: n must be a positive integer; got ${n}`);
  }
  const key = `${col}_lag_${n}`;
  const out: Array<Row & Record<string, number | null>> = [];
  for (let i = 0; i < rows.length; i++) {
    let v: number | null = null;
    if (i >= n) {
      const src = rows[i - n]?.[col];
      if (typeof src === "number" && Number.isFinite(src)) {
        v = src;
      }
    }
    out.push({ ...(rows[i] as Row), [key]: v } as Row & Record<string, number | null>);
  }
  return out;
}
