// Strict row-equivalence assertion for TS parity gate.
//
// Per stub PLAN: "DO NOT loosen the tolerance" on float mismatches.
// Integers via ===, floats via ===, strings via ===, null via ===. If a
// future column proves IEEE-non-stable across platforms, refactor away the
// precision-loss path or document the divergence — NOT a blanket tolerance.

import type { PairsRow } from "@tradewinds/core/internal/pairs";
import { expect } from "vitest";

export function canonicalSort(rows: ReadonlyArray<PairsRow>): PairsRow[] {
  return [...rows].sort((a, b) => {
    if (a.date < b.date) return -1;
    if (a.date > b.date) return 1;
    if (a.station < b.station) return -1;
    if (a.station > b.station) return 1;
    return 0;
  });
}

function sortExpected(
  rows: ReadonlyArray<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  return [...rows].sort((a, b) => {
    const ad = String(a.date);
    const bd = String(b.date);
    if (ad < bd) return -1;
    if (ad > bd) return 1;
    const as = String(a.station);
    const bs = String(b.station);
    if (as < bs) return -1;
    if (as > bs) return 1;
    return 0;
  });
}

/**
 * Assert per-row, per-column equality between TS research() output and the
 * Python-derived JSON fixture. Failure messages include the row date so
 * debugging is fast.
 */
export function assertRowsRowEqual(
  actualRaw: ReadonlyArray<PairsRow>,
  expectedRaw: ReadonlyArray<Record<string, unknown>>,
  label: string,
): void {
  const actual = canonicalSort(actualRaw);
  const expected = sortExpected(expectedRaw);
  expect(actual.length, `${label}: row count`).toEqual(expected.length);
  for (let i = 0; i < expected.length; i++) {
    const a = actual[i] as unknown as Record<string, unknown>;
    const e = expected[i] as Record<string, unknown>;
    const expectedKeys = Object.keys(e).sort();
    for (const k of expectedKeys) {
      expect(a[k], `${label}: row ${i} col ${k} (date=${String(e.date)})`).toEqual(e[k]);
    }
  }
}
