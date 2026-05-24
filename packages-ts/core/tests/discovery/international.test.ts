import { describe, expect, it } from "vitest";

import {
  type InternationalRow,
  internationalDailyExtremes,
} from "../../src/discovery/international.js";

function row(observedAt: string, tempC: number | null, source = "iem"): InternationalRow {
  return { observed_at: observedAt, temp_c: tempC, source };
}

function dense(
  localDateUtcMidnight: string,
  tempCs: number[],
  tz: string,
  hourSpacing = 1,
): InternationalRow[] {
  // Spread `tempCs.length` observations across the requested local day.
  // We anchor the first row at `localDateUtcMidnight` (which the caller
  // chose to land in the desired tz day) and increment by `hourSpacing`
  // UTC hours so all rows stay inside the same local day.
  const start = new Date(localDateUtcMidnight).getTime();
  const out: InternationalRow[] = [];
  for (let i = 0; i < tempCs.length; i += 1) {
    const t = new Date(start + i * hourSpacing * 3600 * 1000).toISOString();
    out.push(row(t, tempCs[i] ?? null));
  }
  return out;
}

describe("internationalDailyExtremes — basic semantics", () => {
  it("returns an empty array when no rows are passed", () => {
    expect(internationalDailyExtremes([], { stationTz: "America/New_York" })).toEqual([]);
  });

  it("requires a non-empty stationTz", () => {
    expect(() => internationalDailyExtremes([], { stationTz: "" })).toThrow(RangeError);
    expect(() => internationalDailyExtremes([], { stationTz: "Not/A/Zone" })).toThrow(RangeError);
  });

  it("nulls tmin/tmax/tmean when n_obs is below the threshold", () => {
    const rows = [row("2025-01-01T05:00:00Z", 5), row("2025-01-01T15:00:00Z", 10)];
    const out = internationalDailyExtremes(rows, { stationTz: "UTC" });
    expect(out).toHaveLength(1);
    expect(out[0]?.localDate).toBe("2025-01-01");
    expect(out[0]?.nObs).toBe(2);
    expect(out[0]?.tempMinC).toBeNull();
    expect(out[0]?.tempMaxC).toBeNull();
    expect(out[0]?.tempMeanC).toBeNull();
    expect(out[0]?.sourceTmin).toBeNull();
    expect(out[0]?.sourceTmax).toBeNull();
  });

  it("populates tmin/tmax/tmean once n_obs meets the threshold", () => {
    const rows = dense(
      "2025-01-01T00:00:00Z",
      [
        // 12 observations, 1-hour apart, all on 2025-01-01 UTC.
        -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
      ],
      "UTC",
    );
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", precision: 0 });
    expect(out).toHaveLength(1);
    expect(out[0]?.tempMinC).toBe(-2);
    expect(out[0]?.tempMaxC).toBe(9);
    // Mean is 3.5 → HALF_UP at 0 places rounds to 4.
    expect(out[0]?.tempMeanC).toBe(4);
  });

  it("rounds HALF_UP at precision=0 (whole-°C international convention)", () => {
    const rows = dense(
      "2025-01-01T00:00:00Z",
      [
        // 12 obs averaging 0.5 → rounds to 1 under HALF_UP, not 0 under banker's rounding.
        0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1,
      ],
      "UTC",
    );
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", precision: 0 });
    expect(out[0]?.tempMeanC).toBe(1);
  });

  it("rounds to tenths at precision=1 for US-style stations", () => {
    const rows = dense(
      "2025-01-01T00:00:00Z",
      [
        // Mean 0.05 → rounds to 0.1 under HALF_UP at 1 place.
        0, 0, 0, 0, 0, 0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
      ],
      "UTC",
    );
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", precision: 1 });
    expect(out[0]?.tempMeanC).toBe(0.1);
  });

  it("computes °F counterparts from rounded °C", () => {
    const rows = dense("2025-01-01T00:00:00Z", new Array(12).fill(0), "UTC");
    const out = internationalDailyExtremes(rows, { stationTz: "UTC" });
    expect(out[0]?.tempMinC).toBe(0);
    expect(out[0]?.tempMinF).toBe(32);
    expect(out[0]?.tempMaxF).toBe(32);
  });

  it("sums precip_mm_1h across rows of the same local day", () => {
    const rows: InternationalRow[] = [
      { observed_at: "2025-01-01T03:00:00Z", temp_c: 5, precip_mm_1h: 1.2 },
      { observed_at: "2025-01-01T09:00:00Z", temp_c: 6, precip_mm_1h: 0.8 },
      { observed_at: "2025-01-01T15:00:00Z", temp_c: 7, precip_mm_1h: 2.0 },
    ];
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", minObs: 1 });
    expect(out[0]?.precipMm).toBe(4);
  });

  it("preserves source identity on tmin and tmax", () => {
    const rows: InternationalRow[] = [];
    for (let h = 0; h < 11; h += 1) {
      rows.push({
        observed_at: `2025-01-01T${String(h).padStart(2, "0")}:00:00Z`,
        temp_c: 0,
        source: "ghcnh",
      });
    }
    rows.push({ observed_at: "2025-01-01T12:00:00Z", temp_c: -10, source: "iem" });
    rows.push({ observed_at: "2025-01-01T13:00:00Z", temp_c: 20, source: "awc" });
    const out = internationalDailyExtremes(rows, { stationTz: "UTC" });
    expect(out[0]?.sourceTmin).toBe("iem");
    expect(out[0]?.sourceTmax).toBe("awc");
  });

  it("drops rows without a parseable observed_at", () => {
    const rows: InternationalRow[] = [
      { observed_at: "not-a-timestamp", temp_c: 5 },
      { observed_at: null, temp_c: 5 },
      { temp_c: 5 },
      { observed_at: "", temp_c: 5 },
    ];
    const out = internationalDailyExtremes(rows, { stationTz: "UTC" });
    expect(out).toEqual([]);
  });

  it("ignores non-finite temp_c values", () => {
    const rows: InternationalRow[] = [
      { observed_at: "2025-01-01T00:00:00Z", temp_c: Number.NaN },
      { observed_at: "2025-01-01T01:00:00Z", temp_c: Number.POSITIVE_INFINITY },
      { observed_at: "2025-01-01T02:00:00Z", temp_c: 5 },
    ];
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", minObs: 1 });
    expect(out[0]?.nObs).toBe(1);
    expect(out[0]?.tempMinC).toBe(5);
  });

  it("does not crash when minObs=0 and a day has no finite temps (codex iter-4 P2)", () => {
    // Day-bucket has a parseable timestamp but no usable temperature. With
    // minObs=0 the prior code-path entered the extremes branch with nObs=0
    // and dereferenced an empty temps[] → TypeError. Should now emit a
    // null-temps row instead.
    const rows: InternationalRow[] = [
      { observed_at: "2025-01-01T00:00:00Z", temp_c: null },
      { observed_at: "2025-01-01T01:00:00Z", temp_c: Number.NaN },
    ];
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", minObs: 0 });
    expect(out).toHaveLength(1);
    expect(out[0]?.nObs).toBe(0);
    expect(out[0]?.tempMinC).toBeNull();
    expect(out[0]?.tempMaxC).toBeNull();
    expect(out[0]?.tempMeanC).toBeNull();
  });
});

describe("internationalDailyExtremes — UTC-wrap edge cases", () => {
  it("RJTT (UTC+9): late-night UTC observations belong to the next local day", () => {
    // 2025-01-31 16:00 UTC = 2025-02-01 01:00 JST. Should bucket as 2025-02-01.
    const rows: InternationalRow[] = [
      { observed_at: "2025-01-31T16:00:00Z", temp_c: 0, source: "ghcnh" },
      { observed_at: "2025-01-31T20:00:00Z", temp_c: 1, source: "ghcnh" },
      { observed_at: "2025-02-01T00:00:00Z", temp_c: 2, source: "ghcnh" },
    ];
    const out = internationalDailyExtremes(rows, { stationTz: "Asia/Tokyo", minObs: 1 });
    const dates = out.map((r) => r.localDate);
    expect(dates).toContain("2025-02-01");
    // The 2025-01-31T16Z observation should NOT be in 2025-01-31 local.
    const jan31 = out.find((r) => r.localDate === "2025-01-31");
    expect(jan31?.nObs ?? 0).toBeLessThan(2);
  });

  it("SAEZ (UTC-3): early-morning UTC observations belong to the previous local day", () => {
    // 2025-01-01 02:00 UTC = 2024-12-31 23:00 ART. Should bucket as 2024-12-31.
    const rows: InternationalRow[] = [
      { observed_at: "2025-01-01T02:00:00Z", temp_c: 25 },
      { observed_at: "2025-01-01T05:00:00Z", temp_c: 22 },
    ];
    const out = internationalDailyExtremes(rows, {
      stationTz: "America/Argentina/Buenos_Aires",
      minObs: 1,
    });
    const dates = new Set(out.map((r) => r.localDate));
    expect(dates.has("2024-12-31")).toBe(true);
    expect(dates.has("2025-01-01")).toBe(true);
  });

  it("NZWN (UTC+12/+13 DST): handles DST transition without losing rows", () => {
    // NZDT is UTC+13 in late March / early April. Picking observations
    // straddling the day boundary; the result should always have valid local
    // dates from the formatter (no NaN), regardless of where DST falls.
    const rows: InternationalRow[] = [
      { observed_at: "2025-04-05T11:00:00Z", temp_c: 15 },
      { observed_at: "2025-04-05T13:00:00Z", temp_c: 14 },
      { observed_at: "2025-04-05T15:00:00Z", temp_c: 13 },
    ];
    const out = internationalDailyExtremes(rows, {
      stationTz: "Pacific/Auckland",
      minObs: 1,
    });
    expect(out.length).toBeGreaterThan(0);
    for (const r of out) {
      expect(r.localDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });

  it("UTC station produces the same boundary as the UTC clock", () => {
    const rows: InternationalRow[] = [
      { observed_at: "2025-01-01T23:59:59Z", temp_c: 1 },
      { observed_at: "2025-01-02T00:00:00Z", temp_c: 2 },
    ];
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", minObs: 1 });
    const dates = out.map((r) => r.localDate);
    expect(dates).toEqual(["2025-01-01", "2025-01-02"]);
  });
});

describe("internationalDailyExtremes — output shape", () => {
  it("freezes each result row", () => {
    const rows = dense("2025-01-01T00:00:00Z", [0, 1, 2], "UTC");
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", minObs: 1 });
    expect(Object.isFrozen(out[0])).toBe(true);
  });

  it("emits rows in ascending localDate order", () => {
    const rows: InternationalRow[] = [
      { observed_at: "2025-01-03T00:00:00Z", temp_c: 0 },
      { observed_at: "2025-01-01T00:00:00Z", temp_c: 0 },
      { observed_at: "2025-01-02T00:00:00Z", temp_c: 0 },
    ];
    const out = internationalDailyExtremes(rows, { stationTz: "UTC", minObs: 1 });
    const dates = out.map((r) => r.localDate);
    expect(dates).toEqual(["2025-01-01", "2025-01-02", "2025-01-03"]);
  });
});
