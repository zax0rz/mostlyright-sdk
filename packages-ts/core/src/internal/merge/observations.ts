// Observation source-priority dedup — AWC > IEM > GHCNh with strict-> + first-seen tiebreak.
//
// Byte-faithful TS port of
// `packages/core/src/tradewinds/_internal/merge/observations.py::merge_observations`.
//
// Why this lives in @tradewinds/core (not @tradewinds/weather): the merge
// policy is a tradewinds-wide invariant — every settlement-grade path that
// joins multi-source observations depends on it. Putting it in core keeps
// the dep direction clean (weather + meta → core), avoids a circular
// import between weather/parsers and the orchestrator, and matches the
// Python layout (`_internal/merge/`).
//
// Type strategy: a STRUCTURAL `ObservationKey` interface (4 fields) avoids
// pulling the full `Observation` shape from @tradewinds/weather into core.
// The function is generic over `T extends ObservationKey` so callers can
// pass the full row type without losing fields.

/**
 * Source priority — strictly greater means "wins on tiebreak".
 * Verbatim from Python `SOURCE_PRIORITY` at
 * `packages/core/src/tradewinds/_internal/merge/observations.py:18`.
 *
 * Frozen so consumers cannot mutate the policy at runtime.
 */
export const SOURCE_PRIORITY: Readonly<Record<string, number>> = Object.freeze({
  awc: 3,
  iem: 2,
  ghcnh: 1,
});

/**
 * Subset of `Observation` that `mergeObservations` needs to dedup +
 * priority-rank. The four fields below form the dedup key (first three)
 * plus the source string that the priority map keys on. Unknown sources
 * resolve to priority 0 (lose to any known source).
 */
export interface ObservationKey {
  readonly station_code: string;
  readonly observed_at: string;
  readonly observation_type: string;
  readonly source: string;
}

/**
 * Deduplicate observation rows by `(station_code, observed_at,
 * observation_type)`, keeping the row whose source has the highest
 * {@link SOURCE_PRIORITY}.
 *
 * Tiebreak: **STRICT `>`** — on equal priority the FIRST row seen wins.
 * This is the byte-faithful semantics of Python v0.14.1, which preserved
 * input order through `dict.values()`. TS uses `Map.values()` with the
 * same insertion-order guarantee.
 *
 * The order-dependent tiebreak is intentional: callers can rely on a
 * canonical fetch order (AWC live → IEM yearly chunk → GHCNh yearly
 * chunk) to deterministically pick the AWC row over IEM/GHCNh on tied
 * priority (which only happens for unknown sources in practice).
 *
 * Unknown source strings resolve to priority 0 (lose to any of awc/iem/
 * ghcnh). Empty input returns an empty array.
 *
 * Output order is `Map.values()` insertion order — first row per key
 * wins both priority AND output position when no later row outranks it.
 *
 * Generic over `T extends ObservationKey` so the consumer (e.g. the
 * `research()` orchestrator in TS-W2 Plan 06) can pass the full
 * `Observation` row type without losing fields. The returned array is
 * a freshly-allocated `T[]`, not the input array.
 */
export function mergeObservations<T extends ObservationKey>(
  rows: ReadonlyArray<T>,
): ReadonlyArray<T> {
  const best = new Map<string, T>();
  for (const row of rows) {
    // Null-byte separator: station_code is `[A-Z]{3,4}`, observed_at is
    // `\d{4}-...Z`, observation_type is `METAR|SPECI` — none can carry a
    // literal `\x00`. Defense-in-depth against upstream parser bugs that
    // might leak weird characters.
    const key = `${row.station_code}\x00${row.observed_at}\x00${row.observation_type}`;
    const existing = best.get(key);
    if (existing === undefined) {
      best.set(key, row);
      continue;
    }
    const priority = SOURCE_PRIORITY[row.source] ?? 0;
    const existingPriority = SOURCE_PRIORITY[existing.source] ?? 0;
    if (priority > existingPriority) {
      // STRICT `>`: on equal priority the first-seen row stays.
      best.set(key, row);
    }
  }
  return Array.from(best.values());
}
