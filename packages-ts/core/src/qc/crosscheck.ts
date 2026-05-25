// TS-W4 Plan 06 — crosscheckIemGhcnh: disagreement detection between IEM +
// GHCNh temperature readings. Mirrors Python
// `mostlyright.qc.crosscheck_iem_ghcnh` at
// `packages/core/src/mostlyright/qc.py:191-228`.
//
// Inner-joins by composite key `(station, eventTime)`. For matched pairs
// where both temp_c values are finite numbers and the absolute delta
// exceeds `opts.tolC` (default 2.0 °C), emits a disagreement row.
//
// Threshold is STRICT `>` (NOT `>=`) per Python qc.py:228 —
// `merged.loc[merged["delta_c"] > tol_c]`. A delta exactly equal to the
// tolerance produces NO disagreement.
//
// Parity-Ticket: Python returns snake_case keys
// (event_time, temp_c_iem, temp_c_ghcnh, delta_c); TS returns camelCase
// (eventTime, tempCIem, tempCGhcnh, deltaC) to match the TS-idiom used
// elsewhere in the codebase (see `obsQcStatus` from Wave 5). Wire-format
// conversion to snake_case happens at the JSON serializer boundary
// (TS-W3 Plan 07 `jsonDumps`).
//
// Lives at the `@mostlyright/core/qc` subpath (NOT root barrel) to keep
// the main `@mostlyright/core` bundle under its 25 KB size-limit gate.

/** Options for {@link crosscheckIemGhcnh}. */
export interface CrosscheckOptions {
  /**
   * Maximum acceptable absolute delta in °C between paired IEM/GHCNh
   * `temp_c` values. Defaults to `2.0` °C (matches Python
   * `crosscheck_iem_ghcnh(tol_c=2.0)`). A delta strictly greater than
   * `tolC` produces a disagreement row; equality does NOT.
   */
  tolC?: number;
}

/**
 * Disagreement row emitted by {@link crosscheckIemGhcnh}. Keys are
 * camelCase per the TS-idiom Parity-Ticket; Python's snake_case
 * equivalents are `event_time`, `temp_c_iem`, `temp_c_ghcnh`, `delta_c`.
 */
export interface CrosscheckDisagreement {
  readonly station: string;
  readonly eventTime: string;
  readonly tempCIem: number;
  readonly tempCGhcnh: number;
  readonly deltaC: number;
}

/**
 * Minimal row shape consumed by {@link crosscheckIemGhcnh}. Rows MUST
 * carry `station: string`, `eventTime: string`, and `temp_c: number |
 * null` (or `undefined`/non-finite, which are skipped). Additional keys
 * are allowed and ignored.
 */
interface CrosscheckRowIn {
  station?: unknown;
  eventTime?: unknown;
  temp_c?: unknown;
}

/**
 * Cross-check IEM and GHCNh temperatures; return rows where the two
 * sources disagree above `opts.tolC` (default 2.0 °C).
 *
 * Algorithm:
 * 1. If `iemRows.length === 0 || ghcnhRows.length === 0` → return `[]`
 *    (matches Python qc.py:212-215).
 * 2. Validate `station` + `eventTime` present (string) on every input
 *    row; throw `Error` on first violation (parity with Python
 *    `ValueError` at qc.py:217-220).
 * 3. Build `iemMap: Map<string, IemRow>` keyed by
 *    `${row.station}|${row.eventTime}`. On duplicate keys, LAST iem row
 *    wins — deterministic but a documented deviation from Python's
 *    `pd.merge` (which would cartesian-product duplicates).
 * 4. For each GHCNh row, look up the matching IEM row by composite key.
 *    If missing → skip. If either `temp_c` is null / non-finite →
 *    skip.
 * 5. If `Math.abs(iem.temp_c - ghcnh.temp_c) > tolC` → emit a
 *    disagreement row. STRICT `>` (NOT `>=`).
 *
 * Output array order matches the iteration order of `ghcnhRows`
 * (deterministic, independent of `iemRows` order).
 *
 * Pure: input arrays are NOT mutated.
 *
 * @param iemRows  IEM observation rows.
 * @param ghcnhRows  GHCNh observation rows.
 * @param opts  Tolerance options. `tolC` default = 2.0.
 * @throws Error if any iem or ghcnh row is missing `station` or
 *   `eventTime` (or they are not strings).
 */
export function crosscheckIemGhcnh(
  iemRows: ReadonlyArray<CrosscheckRowIn>,
  ghcnhRows: ReadonlyArray<CrosscheckRowIn>,
  opts: CrosscheckOptions = {},
): ReadonlyArray<CrosscheckDisagreement> {
  const tolC = opts.tolC ?? 2.0;

  if (iemRows.length === 0 || ghcnhRows.length === 0) return [];

  // Validate column presence upfront (parity with Python ValueError).
  for (const r of iemRows) {
    if (typeof r?.station !== "string" || typeof r?.eventTime !== "string") {
      throw new Error(
        "crosscheckIemGhcnh: iem rows must carry 'station' (string) and 'eventTime' (string) keys",
      );
    }
  }
  for (const r of ghcnhRows) {
    if (typeof r?.station !== "string" || typeof r?.eventTime !== "string") {
      throw new Error(
        "crosscheckIemGhcnh: ghcnh rows must carry 'station' (string) and 'eventTime' (string) keys",
      );
    }
  }

  // Build iem lookup map. Last-wins on duplicate (station, eventTime).
  const iemMap = new Map<string, CrosscheckRowIn>();
  for (const r of iemRows) {
    const key = `${r.station as string}|${r.eventTime as string}`;
    iemMap.set(key, r);
  }

  const out: CrosscheckDisagreement[] = [];
  for (const g of ghcnhRows) {
    const key = `${g.station as string}|${g.eventTime as string}`;
    const i = iemMap.get(key);
    if (i === undefined) continue;
    const iT = typeof i.temp_c === "number" && Number.isFinite(i.temp_c) ? i.temp_c : null;
    const gT = typeof g.temp_c === "number" && Number.isFinite(g.temp_c) ? g.temp_c : null;
    if (iT === null || gT === null) continue;
    const delta = Math.abs(iT - gT);
    if (delta > tolC) {
      out.push({
        station: g.station as string,
        eventTime: g.eventTime as string,
        tempCIem: iT,
        tempCGhcnh: gT,
        deltaC: delta,
      });
    }
  }
  return out;
}
