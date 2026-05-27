// Phase 18 PREC-05: 12-station live anti-regression test for ASOS Tgroup
// integer-°F lattice (TS parity port of Python plan 18-07).
//
// Pulls fresh METARs via AWC for the 12 canonical U.S. ASOS stations and
// asserts every Tgroup-derived temp_c round-trips from an integer °F.
// Catches any regression where the parser drifts off the integer-°F lattice
// — the empirical invariant for U.S. ASOS observation Tgroups (Phase 18
// CONTEXT.md).
//
// Gated behind `RUN_LIVE_TESTS=1` env var so default `pnpm test` skips it.
// Run manually before each publish::
//
//   RUN_LIVE_TESTS=1 pnpm --filter @mostlyrightmd/weather test -- live/12-station-asos-integer-f

import { describe, expect, it } from "vitest";

import { fetchAwcMetars } from "../../src/_fetchers/awc.js";
import { parseTgroup } from "../../src/_internal/tgroup.js";

const STATIONS = [
  "KLGA",
  "KJFK",
  "KEWR",
  "KBOS",
  "KORD",
  "KDFW",
  "KLAX",
  "KMIA",
  "KDEN",
  "KSEA",
  "KATL",
  "KPHX",
] as const;

const RUN_LIVE = process.env.RUN_LIVE_TESTS === "1";

describe.skipIf(!RUN_LIVE)("12-station live anti-regression — Phase 18 PREC-05", () => {
  // Pre-compute the integer-°F lattice: every integer F in [-50, 140]
  // mapped back to its Tgroup tenths-°C representation. Any observed
  // tenth-°C not in this set signals parser drift.
  const lattice = new Set<number>();
  for (let f = -50; f <= 140; f += 1) {
    lattice.add(Math.round((((f - 32) * 5) / 9) * 10) / 10);
  }

  it.each(STATIONS)(
    "%s: every Tgroup tenth-°C from last 168h lies on the integer-°F lattice",
    async (station) => {
      const metars = await fetchAwcMetars([station], { hours: 168 });
      const observed: number[] = [];
      for (const m of metars) {
        const [tc, td] = parseTgroup(m.rawOb ?? "");
        if (tc !== null) observed.push(tc);
        if (td !== null) observed.push(td);
      }
      const mismatches = observed.filter((c) => !lattice.has(c));
      expect(
        mismatches.length,
        `${station}: ${mismatches.length} Tgroup values off integer-°F lattice: ${JSON.stringify(
          [...new Set(mismatches)].slice(0, 10),
        )}`,
      ).toBe(0);
      expect(
        observed.length,
        `${station}: no Tgroup readings in last 168h (test data sparse?)`,
      ).toBeGreaterThan(0);
    },
    30_000, // 30s per-station timeout for the network call
  );
});
