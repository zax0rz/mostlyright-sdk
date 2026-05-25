// TS-W4 Plan 02 Task 1 — diff + diff2 transforms.
//
// Pure row→row ports of Python `mostlyright.transforms.diff` and `diff2`
// (packages/core/src/mostlyright/transforms.py:48-55). The TS port operates
// on `ReadonlyArray<Row>` and adds a single derived column per call:
//   - diff  → `{col}_diff_{n}`
//   - diff2 → `{col}_diff2`    (NOT `{col}_diff_1` + `{col}_diff2`)
//
// Numeric coercion is STRICT: only finite numbers pass through; strings,
// null, undefined, NaN, and ±Infinity all produce `null` in the derived
// column (matches Python `pd.NA`/`None` behavior on serialization).

/**
 * First (or nth-order) discrete difference of a column.
 *
 * At output index `i`, the derived column carries
 * `rows[i][col] - rows[i-n][col]` if both are finite numbers, else `null`.
 *
 * @param rows  input rows (NOT mutated; pure function)
 * @param col   column name to difference
 * @param n     positive integer step (default 1)
 * @returns     new array of rows, each carrying `{col}_diff_{n}` derived column
 * @throws RangeError if `n < 1` or `!Number.isInteger(n)`
 */
export function diff<Row extends Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  col: string,
  n = 1,
): ReadonlyArray<Row & Record<string, number | null>> {
  if (!Number.isInteger(n) || n < 1) {
    throw new RangeError(`diff: n must be a positive integer; got ${n}`);
  }
  const key = `${col}_diff_${n}`;
  const out: Array<Row & Record<string, number | null>> = [];
  for (let i = 0; i < rows.length; i++) {
    let v: number | null = null;
    if (i >= n) {
      const a = rows[i]?.[col];
      const b = rows[i - n]?.[col];
      if (
        typeof a === "number" &&
        Number.isFinite(a) &&
        typeof b === "number" &&
        Number.isFinite(b)
      ) {
        v = a - b;
      }
    }
    out.push({ ...(rows[i] as Row), [key]: v } as Row & Record<string, number | null>);
  }
  return out;
}

/**
 * Second discrete difference of a column.
 *
 * Equivalent to `diff(diff(col))`. The first two output rows carry `null`
 * (no prior diff available). Mirrors Python `df[column].diff().diff()` which
 * returns a single Series — so the TS output carries ONLY `{col}_diff2`,
 * NOT the intermediate `{col}_diff_1` from the first pass.
 *
 * @param rows  input rows (NOT mutated; pure function)
 * @param col   column name to second-difference
 * @returns     new array of rows, each carrying `{col}_diff2` derived column
 */
export function diff2<Row extends Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  col: string,
): ReadonlyArray<Row & Record<string, number | null>> {
  // Pass 1: compute first-differences into a parallel numeric array.
  // Doing it this way (rather than chaining `diff(diff(...))`) lets us
  // drop the intermediate `{col}_diff_1` column cleanly — the output
  // carries only `{col}_diff2`, matching Python's single-Series return.
  const first: Array<number | null> = new Array(rows.length).fill(null);
  for (let i = 1; i < rows.length; i++) {
    const a = rows[i]?.[col];
    const b = rows[i - 1]?.[col];
    if (
      typeof a === "number" &&
      Number.isFinite(a) &&
      typeof b === "number" &&
      Number.isFinite(b)
    ) {
      first[i] = a - b;
    }
  }
  // Pass 2: second-differences from `first`.
  const key = `${col}_diff2`;
  const out: Array<Row & Record<string, number | null>> = [];
  for (let i = 0; i < rows.length; i++) {
    let v: number | null = null;
    if (i >= 2) {
      const a = first[i];
      const b = first[i - 1];
      if (a != null && b != null) {
        v = a - b;
      }
    }
    out.push({ ...(rows[i] as Row), [key]: v } as Row & Record<string, number | null>);
  }
  return out;
}
