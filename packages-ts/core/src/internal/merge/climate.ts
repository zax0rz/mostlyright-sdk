// Climate-row dedup — keep highest `report_type_priority` per (station, date).
//
// Migrated from `packages-ts/weather/src/_parsers/cli.ts::mergeClimate`
// (TS-W1 Wave 4) to its canonical home under @mostlyright/core/internal/merge
// in TS-W2 Plan 04. Behavior is unchanged — only the module location moves.
//
// Byte-faithful TS port of `mostlyright._internal.merge.climate.merge_climate`
// (Python), itself a lift of `_dedup_climate_rows` from
// `monorepo-v0.14.1/ingest/storage/parquet.py:477-494`.
//
// Type strategy: structural `ClimateKey` interface (3 fields) so this
// module does not pull `ClimateObservation` from @mostlyright/weather into
// @mostlyright/core. Callers pass the full row type and the generic
// preserves it.

/**
 * Subset of `ClimateObservation` that `mergeClimate` needs.
 * The first two fields form the dedup key; `report_type_priority` is the
 * tiebreak field (codegen-sourced from `REPORT_TYPE_PRIORITY`).
 */
export interface ClimateKey {
  readonly station_code: string;
  readonly observation_date: string;
  readonly report_type_priority: number;
}

/**
 * Deduplicate climate rows by `(station_code, observation_date)`.
 *
 * Keeps the row with the highest `report_type_priority` using **STRICT `>`**
 * (not `>=`). First-seen wins at equal priority — this preserves the
 * overnight `final` (which IS the Kalshi settlement value) when a
 * `preliminary` arrives first in input order.
 *
 * Generic over `T extends ClimateKey` so consumers can pass the full
 * `ClimateObservation` shape without losing fields.
 *
 * Empty input returns an empty array.
 */
export function mergeClimate<T extends ClimateKey>(rows: ReadonlyArray<T>): ReadonlyArray<T> {
  const best = new Map<string, T>();
  for (const row of rows) {
    // Null-byte separator — station_code is `[A-Z]{3,4}`, observation_date
    // is `YYYY-MM-DD`; neither can carry a literal `\x00`.
    const key = `${row.station_code}\x00${row.observation_date}`;
    const existing = best.get(key);
    if (existing === undefined) {
      best.set(key, row);
      continue;
    }
    // Strict `>`; first-seen wins on equal priority.
    if (row.report_type_priority > existing.report_type_priority) {
      best.set(key, row);
    }
  }
  return Array.from(best.values());
}
