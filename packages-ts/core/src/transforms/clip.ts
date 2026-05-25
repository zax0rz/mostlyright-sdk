// TS-W4 Plan 04 Task 2 — clipOutliers (winsorize) + PHYSICS_BOUNDS.
//
// Pure row→row port of Python `mostlyright.preprocessing.clip_outliers` at
// packages/core/src/mostlyright/preprocessing.py:49-91. The v0.1.0 canonical
// surface (supersedes the older `transforms.clip_outliers`).
//
// Decision tree (mirrors Python preprocessing.py:75-91):
//   1. opts.bounds set            → clip to explicit [lo, hi]
//   2. PHYSICS_BOUNDS.has(col)    → clip to physics defaults
//   3. else                       → sigma fallback (mu ± std*sigma)
//
// Phase 3.5 review-iter HIGH fixes (preserved here):
//   - Architect iter-1 HIGH: std<=0 in the sigma branch silently collapses
//     every row to the mean. Python raises ValueError; we throw RangeError.
//   - Sigma=0 pass-through: when all values are identical, sample sigma is
//     zero and the clamp [mu, mu] would collapse the column. Pass values
//     through unchanged instead (a TS-side improvement on top of Python).
//
// Numeric coercion is STRICT: only `typeof v === 'number' && Number.isFinite(v)`
// passes through. Strings like '5' do NOT auto-parse. Matches Wave 2/3/04-task1.

/**
 * Physics-based clipping defaults for canonical observation columns.
 *
 * Mirrors Python `mostlyright.preprocessing.PHYSICS_BOUNDS` (preprocessing.py:34-46).
 * Values are `[min, max]` tuples in canonical units (°C for temp, m/s and kt
 * for wind, hPa for pressure, percent for humidity, mm for precip).
 *
 * Both `dew_point_c`/`dewpoint_c` and `wind_dir_deg`/`wind_dir_degrees` are
 * aliased to support legacy + canonical column names.
 */
export const PHYSICS_BOUNDS: ReadonlyMap<string, readonly [number, number]> = new Map([
  ["temp_c", [-89.0, 57.0] as const],
  ["dew_point_c", [-89.0, 35.0] as const],
  ["dewpoint_c", [-89.0, 35.0] as const],
  ["wind_speed_ms", [0.0, 100.0] as const],
  ["wind_speed_kt", [0.0, 200.0] as const],
  ["wind_dir_deg", [0.0, 360.0] as const],
  ["wind_dir_degrees", [0.0, 360.0] as const],
  ["slp_hpa", [870.0, 1085.0] as const],
  ["sea_level_pressure_mb", [870.0, 1085.0] as const],
  ["relative_humidity_pct_2m", [0.0, 100.0] as const],
  ["precip_mm_1h", [0.0, 305.0] as const],
]);

export interface ClipOutliersOptions {
  /** Explicit `[lo, hi]` range. Overrides PHYSICS_BOUNDS and sigma fallback. */
  bounds?: readonly [number, number];
  /** Sigma multiplier for the fallback branch. Default 3.0. Must be > 0. */
  std?: number;
}

/**
 * Winsorize a numeric column.
 *
 * Mirrors Python `mostlyright.preprocessing.clip_outliers`. Returns rows with
 * a derived `{col}_clipped` column; the source `col` is preserved unchanged.
 *
 * Decision tree:
 *  - `opts.bounds` set            → clip to explicit `[lo, hi]`
 *  - `PHYSICS_BOUNDS.has(col)`    → clip to physics defaults
 *  - else                         → sigma fallback (`mu ± std*sigma`)
 *
 * **Phase 3.5 review-iter fixes:**
 *  - Throws `RangeError` if `std ≤ 0` in the sigma fallback (matches Python
 *    `ValueError` at preprocessing.py:84-88; silent dataset corruption
 *    otherwise).
 *  - Sigma=0 pass-through: when all values are identical, sample sigma is
 *    zero and the clamp `[mu, mu]` would collapse the column. Pass values
 *    through unchanged instead.
 *
 * @param rows  input rows (NOT mutated; pure function)
 * @param col   column to clip
 * @param opts  optional bounds / std overrides; defaults: PHYSICS_BOUNDS or sigma=3
 * @returns     new array of rows, each carrying `{col}_clipped`
 * @throws RangeError  if sigma fallback would use `std <= 0` or non-finite std
 */
export function clipOutliers<Row extends Record<string, unknown>>(
  rows: ReadonlyArray<Row>,
  col: string,
  opts: ClipOutliersOptions = {},
): ReadonlyArray<Row & Record<string, number | null>> {
  const std = opts.std ?? 3.0;
  const key = `${col}_clipped`;

  // Determine clip range. `passThrough` short-circuits to "copy value unchanged"
  // for the sigma=0 / n<2 edge cases (Phase 3.5 review-iter HIGH fix).
  let lo: number;
  let hi: number;
  let passThrough = false;

  if (opts.bounds !== undefined) {
    [lo, hi] = opts.bounds;
  } else if (PHYSICS_BOUNDS.has(col)) {
    const b = PHYSICS_BOUNDS.get(col);
    if (b === undefined) {
      // Unreachable (we just checked has()), but the narrowing requires it.
      throw new Error(`PHYSICS_BOUNDS.get(${col}) unexpectedly undefined`);
    }
    [lo, hi] = b;
  } else {
    // Sigma fallback. Architect iter-1 HIGH: std<=0 collapses to mu.
    if (!Number.isFinite(std) || std <= 0) {
      throw new RangeError(
        `clipOutliers: std must be > 0 for the sigma fallback (got ${std}); pass bounds=[lo, hi] or use a physics-default column`,
      );
    }
    // Compute mu + sigma over non-null finite values.
    const vals: number[] = [];
    for (const r of rows) {
      const v = r?.[col];
      if (typeof v === "number" && Number.isFinite(v)) vals.push(v);
    }
    if (vals.length < 2) {
      // Not enough values to compute sample sigma → pass-through.
      passThrough = true;
      lo = Number.NEGATIVE_INFINITY;
      hi = Number.POSITIVE_INFINITY;
    } else {
      const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
      const sumSq = vals.reduce((a, b) => a + (b - mu) ** 2, 0);
      const sigma = Math.sqrt(sumSq / (vals.length - 1)); // sample stdev (Bessel n-1)
      if (sigma === 0 || !Number.isFinite(sigma)) {
        // Phase 3.5 review-iter HIGH: pass values through unchanged
        // instead of collapsing to [mu, mu] (NOT NaN, NOT mu).
        passThrough = true;
        lo = Number.NEGATIVE_INFINITY;
        hi = Number.POSITIVE_INFINITY;
      } else {
        lo = mu - std * sigma;
        hi = mu + std * sigma;
      }
    }
  }

  const out: Array<Row & Record<string, number | null>> = [];
  for (const r of rows) {
    const v = r?.[col];
    let clipped: number | null;
    if (typeof v === "number" && Number.isFinite(v)) {
      clipped = passThrough ? v : Math.min(Math.max(v, lo), hi);
    } else {
      clipped = null;
    }
    out.push({ ...(r as Row), [key]: clipped } as Row & Record<string, number | null>);
  }
  return out;
}
