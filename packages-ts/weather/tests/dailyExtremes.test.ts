// Phase 21 21-05 — dailyExtremes(station, from, to, opts?) tests.
//
// Smoke-tests for:
//  - station registry lookup (unknown station rejection)
//  - merge-mode dispatch (TypeError on unknown mode)
//  - projection from internationalDailyExtremes shape into the Python-
//    mirroring DailyExtremeRow shape (date/tmin_f/tmax_f/tmean_f/.../n_obs)
//  - low_coverage gate (n_obs < 12 → null tmin/tmax/tmean)
//
// HTTP-backed end-to-end tests live in `tests/dailyExtremes.live.test.ts`
// (gated by @live; not run in CI). The unit tests below mock the network
// layer to assert the wrapper's shape-projection + dispatch behavior.

import { describe, expect, it, vi } from "vitest";

import * as awcFetcher from "../src/_fetchers/awc.js";
import * as iemFetcher from "../src/_fetchers/iem-asos.js";
import { dailyExtremes } from "../src/dailyExtremes.js";

describe("dailyExtremes — station registry lookup", () => {
  it("throws when station is not in the STATIONS registry", async () => {
    await expect(dailyExtremes("XXXX", "2025-01-06", "2025-01-12")).rejects.toThrow(
      /not in registry/,
    );
  });
});

describe("dailyExtremes — merge mode dispatch", () => {
  it("rejects unknown merge mode at runtime", async () => {
    // EGLL is in the international STATIONS registry.
    await expect(
      dailyExtremes("EGLL", "2025-01-06", "2025-01-12", {
        merge: "bogus" as never,
      }),
    ).rejects.toThrow(TypeError);
  });
});

describe("dailyExtremes — shape projection (iem_only, empty fetch)", () => {
  it("returns an empty array when the fetcher returns no rows", async () => {
    vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([]);
    const out = await dailyExtremes("EGLL", "2025-01-06", "2025-01-06", {
      merge: "iem_only",
    });
    expect(out).toEqual([]);
  });
});

describe("dailyExtremes — full-day shape projection (US ASOS, integer-°F)", () => {
  it("projects DailyExtreme → DailyExtremeRow with concrete date/station/n_obs", async () => {
    // 12 synthetic readings across 2025-01-08 UTC at KNYC. KNYC is in
    // America/New_York (UTC-5 standard) so half of the hourly readings
    // bucket into 2025-01-07 local and half into 2025-01-08 local — the
    // caller asks for [2025-01-08, 2025-01-08] (station-local) so only
    // the 2025-01-08 bucket is returned (post-rollup clip to the
    // station-local window matches Python `daily_extremes()` semantics
    // at international.py:319 — drop rows where `local_d < from_date or
    // local_d > to_date`).
    //
    // Phase 21 21-05 fix-iter-2 (codex CRITICAL): pre-fix the wrapper
    // returned BOTH local days because the pre-rollup filter was UTC
    // date-prefix vs station-local date-prefix (asymmetric). The fix
    // widens pre-rollup by ±1 UTC day THEN clips post-rollup by
    // station-local `localDate` — symmetric with Python.
    const csv = buildSyntheticIemCsv("KNYC", "2025-01-08", 12, 0);
    vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([
      { chunkStart: "2025-01-01", chunkEnd: "2025-12-31", csv },
    ]);
    const out = await dailyExtremes("KNYC", "2025-01-08", "2025-01-08", {
      merge: "iem_only",
    });
    // Exactly 1 station-local day — the one the caller asked for. The
    // tz-shifted UTC neighbor 2025-01-07 bucket is dropped by the
    // post-rollup clip (Python parity).
    expect(out).toHaveLength(1);
    const row = out[0];
    if (row === undefined) throw new Error("expected exactly one row");
    expect(row.station).toBe("KNYC");
    expect(row.date).toBe("2025-01-08");
    expect(typeof row.low_coverage).toBe("boolean");
    expect(Number.isInteger(row.n_obs)).toBe(true);
    expect(row.n_obs).toBeGreaterThan(0);
  });

  it("includes tz-edge observations from the previous UTC day in the requested local day (Python parity)", async () => {
    // Request a 2-day window so the rollup can demonstrate per-bucket
    // accounting AND the widened-by-±1 fetch keeping tz-edge observations.
    // 12 UTC hours on 2025-01-08 → half into 2025-01-07 local + half into
    // 2025-01-08 local; both fall inside the [2025-01-07, 2025-01-08]
    // request and must be returned.
    const csv = buildSyntheticIemCsv("KNYC", "2025-01-08", 12, 0);
    vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([
      { chunkStart: "2025-01-01", chunkEnd: "2025-12-31", csv },
    ]);
    const out = await dailyExtremes("KNYC", "2025-01-07", "2025-01-08", {
      merge: "iem_only",
    });
    expect(out).toHaveLength(2);
    for (const row of out) {
      expect(row.station).toBe("KNYC");
      expect(row.date).toMatch(/^2025-01-0[78]$/);
    }
    const totalNObs = out.reduce((s, r) => s + r.n_obs, 0);
    expect(totalNObs).toBe(12);
  });
});

describe("dailyExtremes — low_coverage gate fires below 12 obs", () => {
  it("sparse day (4 obs) → low_coverage=true with null tmin/tmax/tmean", async () => {
    // Only 4 readings — under the n_obs<12 threshold.
    const csv = buildSyntheticIemCsv("EGLL", "2025-01-08", 4, 0);
    vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([
      { chunkStart: "2025-01-01", chunkEnd: "2025-12-31", csv },
    ]);
    const out = await dailyExtremes("EGLL", "2025-01-08", "2025-01-08", {
      merge: "iem_only",
    });
    // Strict — exactly one row expected; no `if (out.length > 0)` escape
    // hatch (a regression returning [] would silently pass the test).
    expect(out).toHaveLength(1);
    const row = out[0];
    if (row === undefined) throw new Error("expected exactly one row");
    expect(row.low_coverage).toBe(true);
    expect(row.tmin_f).toBeNull();
    expect(row.tmax_f).toBeNull();
    expect(row.tmean_f).toBeNull();
    expect(row.n_obs).toBe(4);
  });
});

describe("dailyExtremes — merge='live_v1' tolerates AWC fetch failure", () => {
  it("falls back to IEM-only when AWC throws", async () => {
    vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([]);
    vi.spyOn(awcFetcher, "fetchAwcMetars").mockRejectedValueOnce(new Error("network down"));
    // Default merge is live_v1 — must not propagate the AWC error.
    const out = await dailyExtremes("EGLL", "2025-01-06", "2025-01-06");
    expect(out).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Helpers — synthetic IEM CSV fixture.
// ---------------------------------------------------------------------------

function buildSyntheticIemCsv(
  station: string,
  date: string,
  nObs: number,
  baseTempC: number,
): string {
  // Minimal IEM ASOS CSV shape the parser accepts: station,valid,tmpf,...
  // We emit METAR-typed rows at hourly intervals across the day.
  const header =
    "station,valid,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust,skyc1,skyc2,skyc3,skyc4,skyl1,skyl2,skyl3,skyl4,wxcodes,ice_accretion_1hr,ice_accretion_3hr,ice_accretion_6hr,peak_wind_gust,peak_wind_drct,peak_wind_time,feel,metar,snowdepth";
  const lines: string[] = [header];
  for (let i = 0; i < nObs; i++) {
    const hour = String(i % 24).padStart(2, "0");
    const valid = `${date} ${hour}:00`;
    const tmpf = baseTempC * (9 / 5) + 32 + i; // varied for tmin/tmax
    const metar = `${station} ${date.replace(/-/g, "")}${hour}00Z AUTO 00000KT 10SM CLR ${Math.round(tmpf).toString().padStart(2, "0")}/M00 A3000 RMK AO2`;
    lines.push(`${station},${valid},${tmpf.toFixed(2)},,,,,,,,,,,,,,,,,,,,,,,,,,${metar},`);
  }
  return `${lines.join("\n")}\n`;
}
