// TS-W4 Plan 02 Task 2 — rolling reduction transform.
//
// Pure row→row port of Python `tradewinds.transforms.rolling`
// (packages/core/src/tradewinds/transforms.py:58-68) which uses
// `df[col].rolling(window=window, min_periods=1)` and `getattr(rolling, fn)()`.
//
// Key semantics (load-bearing for Wave 5 QCEngine and Python parity):
//   - min_periods=1: every row gets a value as long as the window contains
//     at least one non-null finite number. No leading nulls from "warmup"
//     — pandas defaults to `min_periods=window` for `.rolling(window)`
//     but `transforms.py` explicitly overrides to 1.
//   - std uses Bessel's correction (denominator n-1) — matches pandas
//     default `.std(ddof=1)`. Needs ≥ 2 non-null values; else null.
//   - Derived column name: `{col}_rolling_{window}_{fn}` — exact format.
//   - `fn` is a const-union (NOT enum) so the type narrows in callers.

/** The set of reducer names accepted by `rolling`. Ordering is API surface. */
export const ROLLING_FNS = ["mean", "median", "min", "max", "std", "count"] as const;

/** Union of the six reducer-name string literals. */
export type RollingFn = (typeof ROLLING_FNS)[number];

function isRollingFn(v: unknown): v is RollingFn {
  return typeof v === "string" && (ROLLING_FNS as readonly string[]).includes(v);
}

/** Aggregate a numeric window. Empty window → null (or 0 for `count`). */
function aggregate(vals: ReadonlyArray<number>, fn: RollingFn): number | null {
  if (vals.length === 0) {
    return fn === "count" ? 0 : null;
  }
  if (fn === "count") {
    return vals.length;
  }
  if (fn === "mean") {
    let sum = 0;
    for (const v of vals) sum += v;
    return sum / vals.length;
  }
  if (fn === "min") {
    let m = vals[0] as number;
    for (let i = 1; i < vals.length; i++) {
      const x = vals[i] as number;
      if (x < m) m = x;
    }
    return m;
  }
  if (fn === "max") {
    let m = vals[0] as number;
    for (let i = 1; i < vals.length; i++) {
      const x = vals[i] as number;
      if (x > m) m = x;
    }
    return m;
  }
  if (fn === "median") {
    const sorted = [...vals].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    if (sorted.length % 2 === 0) {
      const lo = sorted[mid - 1];
      const hi = sorted[mid];
      // mid >= 1 here because length is even ≥ 2; both defined.
      if (lo === undefined || hi === undefined) return null;
      return (lo + hi) / 2;
    }
    return sorted[mid] ?? null;
  }
  // std — sample stdev with Bessel's correction (n-1 denominator).
  if (vals.length < 2) return null;
  let sum = 0;
  for (const v of vals) sum += v;
  const mean = sum / vals.length;
  let sumSq = 0;
  for (const v of vals) sumSq += (v - mean) ** 2;
  return Math.sqrt(sumSq / (vals.length - 1));
}

/**
 * Windowed reduction over a numeric column.
 *
 * At each output row `i`, the window covers
 * `rows[max(0, i-window+1) .. i]` (inclusive both ends), so the first
 * `window-1` rows compute against a partial (still-filling) window —
 * `min_periods=1` semantics from Python.
 *
 * @param rows    input rows (NOT mutated; pure function)
 * @param col     column name to reduce over
 * @param window  positive integer window size (≥ 1)
 * @param fn      one of `'mean' | 'median' | 'min' | 'max' | 'std' | 'count'`
 * @returns       new array of rows, each carrying `{col}_rolling_{window}_{fn}`
 * @throws RangeError if `window < 1`, non-integer, or `fn` is not a `RollingFn`
 */
export function rolling<Row extends Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  col: string,
  window: number,
  fn: RollingFn = "mean",
): ReadonlyArray<Row & Record<string, number | null>> {
  if (!Number.isInteger(window) || window < 1) {
    throw new RangeError(`rolling: window must be a positive integer; got ${window}`);
  }
  if (!isRollingFn(fn)) {
    throw new RangeError(
      `rolling: fn must be one of ${JSON.stringify(ROLLING_FNS)}; got '${String(fn)}'`,
    );
  }
  const key = `${col}_rolling_${window}_${fn}`;
  const out: Array<Row & Record<string, number | null>> = [];
  for (let i = 0; i < rows.length; i++) {
    const start = Math.max(0, i - window + 1);
    const slice: number[] = [];
    for (let j = start; j <= i; j++) {
      const v = rows[j]?.[col];
      if (typeof v === "number" && Number.isFinite(v)) {
        slice.push(v);
      }
    }
    const agg = aggregate(slice, fn);
    out.push({ ...(rows[i] as Row), [key]: agg } as Row & Record<string, number | null>);
  }
  return out;
}
