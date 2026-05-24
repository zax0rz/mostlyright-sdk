// Property test: mergeObservations is permutation-stable on the RESTRICTED
// input class where no two rows share `(station_code, observed_at,
// observation_type, source)`.
//
// IMPORTANT — DO NOT broaden this to arbitrary-shuffle stability over
// arbitrary input. Quoting TS-W2 PLAN.md SC#4 verbatim:
//
//   "an arbitrary-shuffle stability test would FALSELY require TS to
//    diverge from Python's order-dependent same-priority-tiebreak behavior"
//
// Python's merge_observations preserves input order through dict.values()
// (Python 3.7+ insertion-ordered dicts) and uses strict-`>` priority
// comparison. On equal-priority same-key rows, the FIRST one wins —
// which means SHUFFLING the input deterministically changes which row
// survives. The TS port mirrors this exactly via Map insertion order.
//
// The restricted input class (no same-(key, source) duplicates) is the
// class where permutation IS stable because each (key, source) tuple is
// unique → the priority comparison is the ONLY tiebreak, and that is
// order-independent. Anything broader is the wrong test.

import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  type ObservationKey,
  mergeObservations,
} from "../../../src/internal/merge/observations.js";

const sourceArb = fc.constantFrom("awc", "iem", "ghcnh");
const stationArb = fc.constantFrom("NYC", "ORD", "LAX", "MIA", "MSY", "JFK", "DCA", "DEN");
const observedAtArb = fc
  .integer({ min: 1_700_000_000, max: 1_800_000_000 })
  .map((ts) => `${new Date(ts * 1000).toISOString().slice(0, 19)}Z`);
const obsTypeArb = fc.constantFrom("METAR" as const, "SPECI" as const);

function rowArb() {
  return fc.record({
    station_code: stationArb,
    observed_at: observedAtArb,
    observation_type: obsTypeArb,
    source: sourceArb,
  });
}

/** Reject rows that collide on (station, observed_at, observation_type, source). */
function uniquePerSourceArb() {
  return fc.array(rowArb(), { minLength: 0, maxLength: 50 }).map((rows) => {
    const seen = new Set<string>();
    const out: ObservationKey[] = [];
    for (const r of rows) {
      const k = `${r.station_code}|${r.observed_at}|${r.observation_type}|${r.source}`;
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(r);
    }
    return out;
  });
}

/** Deterministic xorshift-based shuffle. Pure; no observable side effects. */
function shuffleRows<T>(rows: ReadonlyArray<T>, seed: number): ReadonlyArray<T> {
  const arr = [...rows];
  let s = seed | 0;
  if (s === 0) s = 1;
  for (let i = arr.length - 1; i > 0; i--) {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    const j = Math.abs(s) % (i + 1);
    const tmp = arr[i] as T;
    arr[i] = arr[j] as T;
    arr[j] = tmp;
  }
  return arr;
}

function survivorSet(rows: ReadonlyArray<ObservationKey>): Set<string> {
  const merged = mergeObservations(rows);
  return new Set(
    merged.map((r) => `${r.station_code}|${r.observed_at}|${r.observation_type}|${r.source}`),
  );
}

describe("mergeObservations — restricted-input permutation stability (TS-W2 SC#4)", () => {
  it("survivor SET equals across permutations when no same-(key, source) duplicates exist", () => {
    fc.assert(
      fc.property(
        uniquePerSourceArb(),
        fc.integer({ min: -(2 ** 31), max: 2 ** 31 - 1 }),
        (rows, seed) => {
          const baseline = survivorSet(rows);
          const shuffled = survivorSet(shuffleRows(rows, seed));
          expect(shuffled).toEqual(baseline);
        },
      ),
      { numRuns: 200 },
    );
  });
});
