import { describe, expect, it } from "vitest";

import {
  type PairsClimateLike,
  type PairsObservationLike,
  _obsAggregates,
  buildPairs,
  buildPairsRow,
  pairsToRows,
} from "../../src/internal/pairs.js";

// ---------------------------------------------------------------------------
// _obsAggregates
// ---------------------------------------------------------------------------

describe("_obsAggregates — empty + boundary cases", () => {
  it("empty input → all-null aggregates + obs_count 0", () => {
    expect(_obsAggregates([])).toEqual({
      obs_high_f: null,
      obs_low_f: null,
      obs_mean_f: null,
      obs_mean_dewpoint_f: null,
      obs_max_wind_kt: null,
      obs_max_gust_kt: null,
      obs_total_precip_in: null,
      obs_count: 0,
    });
  });

  it("output is frozen", () => {
    const r = _obsAggregates([]);
    expect(Object.isFrozen(r)).toBe(true);
  });

  it("output key order matches Python field order", () => {
    expect(Object.keys(_obsAggregates([]))).toEqual([
      "obs_high_f",
      "obs_low_f",
      "obs_mean_f",
      "obs_mean_dewpoint_f",
      "obs_max_wind_kt",
      "obs_max_gust_kt",
      "obs_total_precip_in",
      "obs_count",
    ]);
  });
});

describe("_obsAggregates — single row", () => {
  it("single non-null temp_f row → high=low=mean=value, count=1", () => {
    const r = _obsAggregates([{ temp_f: 32 }]);
    expect(r.obs_high_f).toBe(32);
    expect(r.obs_low_f).toBe(32);
    expect(r.obs_mean_f).toBe(32);
    expect(r.obs_count).toBe(1);
  });
});

describe("_obsAggregates — multi-row aggregation", () => {
  it("max/min/mean over temp_f", () => {
    const rows: PairsObservationLike[] = [{ temp_f: 32 }, { temp_f: 50 }, { temp_f: 41 }];
    const r = _obsAggregates(rows);
    expect(r.obs_high_f).toBe(50);
    expect(r.obs_low_f).toBe(32);
    expect(r.obs_mean_f).toBeCloseTo(41, 10);
  });

  it("mean of [null, 30, 40] excludes the null → 35", () => {
    const rows: PairsObservationLike[] = [{ temp_f: null }, { temp_f: 30 }, { temp_f: 40 }];
    expect(_obsAggregates(rows).obs_mean_f).toBeCloseTo(35, 10);
  });

  it("obs_count includes ALL rows (even all-null ones)", () => {
    const rows: PairsObservationLike[] = [
      { temp_f: null, wind_speed_kt: null },
      { temp_f: 32 },
      { wind_speed_kt: 10 },
    ];
    expect(_obsAggregates(rows).obs_count).toBe(3);
  });
});

describe("_obsAggregates — wind + dewpoint + precip + snow", () => {
  it("obs_max_wind_kt + obs_max_gust_kt", () => {
    const rows: PairsObservationLike[] = [
      { wind_speed_kt: 10, wind_gust_kt: 18 },
      { wind_speed_kt: 12, wind_gust_kt: 25 },
      { wind_speed_kt: null, wind_gust_kt: 22 },
    ];
    const r = _obsAggregates(rows);
    expect(r.obs_max_wind_kt).toBe(12);
    expect(r.obs_max_gust_kt).toBe(25);
  });

  it("obs_mean_dewpoint_f is arithmetic mean over non-null dewpoint_f", () => {
    const rows: PairsObservationLike[] = [
      { dewpoint_f: 20 },
      { dewpoint_f: 30 },
      { dewpoint_f: 40 },
    ];
    expect(_obsAggregates(rows).obs_mean_dewpoint_f).toBeCloseTo(30, 10);
  });

  it("obs_total_precip_in = sum of non-null precip", () => {
    const rows: PairsObservationLike[] = [
      { precip_1hr_inches: 0.1 },
      { precip_1hr_inches: 0.0 },
      { precip_1hr_inches: 0.25 },
    ];
    expect(_obsAggregates(rows).obs_total_precip_in).toBeCloseTo(0.35, 10);
  });

  it("obs_total_precip_in = null when NO non-null precip rows (Python parity)", () => {
    const rows: PairsObservationLike[] = [{ precip_1hr_inches: null }, { temp_f: 32 }];
    expect(_obsAggregates(rows).obs_total_precip_in).toBeNull();
  });

  it("obs_total_precip_in = 0.5 when one non-null = 0.5", () => {
    expect(_obsAggregates([{ precip_1hr_inches: 0.5 }]).obs_total_precip_in).toBe(0.5);
  });
});

describe("_obsAggregates — all-null measures but populated count", () => {
  it("rows present but every measure null → all max/min/mean/sum null, count > 0", () => {
    const rows: PairsObservationLike[] = [
      {
        temp_f: null,
        dewpoint_f: null,
        wind_speed_kt: null,
        wind_gust_kt: null,
        precip_1hr_inches: null,
      },
      {
        temp_f: null,
        dewpoint_f: null,
        wind_speed_kt: null,
        wind_gust_kt: null,
        precip_1hr_inches: null,
      },
    ];
    const r = _obsAggregates(rows);
    expect(r.obs_high_f).toBeNull();
    expect(r.obs_low_f).toBeNull();
    expect(r.obs_mean_f).toBeNull();
    expect(r.obs_mean_dewpoint_f).toBeNull();
    expect(r.obs_max_wind_kt).toBeNull();
    expect(r.obs_max_gust_kt).toBeNull();
    expect(r.obs_total_precip_in).toBeNull();
    expect(r.obs_count).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// buildPairsRow + buildPairs + pairsToRows
// ---------------------------------------------------------------------------

const NYC_CLIMATE: PairsClimateLike = {
  high_temp_f: 45,
  low_temp_f: 30,
  report_type: "final",
};

describe("buildPairsRow", () => {
  it("returns 20 fields in exact Python order", () => {
    const row = buildPairsRow("2025-01-08", "NYC", [{ temp_f: 35 }], NYC_CLIMATE);
    expect(Object.keys(row)).toEqual([
      "date",
      "station",
      "cli_high_f",
      "cli_low_f",
      "cli_report_type",
      "obs_high_f",
      "obs_low_f",
      "obs_mean_f",
      "obs_mean_dewpoint_f",
      "obs_max_wind_kt",
      "obs_max_gust_kt",
      "obs_total_precip_in",
      "obs_count",
      "fcst_high_f",
      "fcst_low_f",
      "fcst_model",
      "fcst_issued_at",
      "fcst_pop_6hr_pct",
      "fcst_qpf_6hr_in",
      "market_close_utc",
    ]);
  });

  it("PairsRow is frozen", () => {
    const row = buildPairsRow("2025-01-08", "NYC", [], null);
    expect(Object.isFrozen(row)).toBe(true);
  });

  it("climate present → cli_high_f/cli_low_f/cli_report_type populated", () => {
    const row = buildPairsRow("2025-01-08", "NYC", [], NYC_CLIMATE);
    expect(row.cli_high_f).toBe(45);
    expect(row.cli_low_f).toBe(30);
    expect(row.cli_report_type).toBe("final");
  });

  it("climate null → cli_* all null", () => {
    const row = buildPairsRow("2025-01-08", "NYC", [], null);
    expect(row.cli_high_f).toBeNull();
    expect(row.cli_low_f).toBeNull();
    expect(row.cli_report_type).toBeNull();
  });

  it("all fcst_* are unconditionally null (TS-W2 Mode 1)", () => {
    const row = buildPairsRow("2025-01-08", "NYC", [{ temp_f: 35 }], NYC_CLIMATE);
    expect(row.fcst_high_f).toBeNull();
    expect(row.fcst_low_f).toBeNull();
    expect(row.fcst_model).toBeNull();
    expect(row.fcst_issued_at).toBeNull();
    expect(row.fcst_pop_6hr_pct).toBeNull();
    expect(row.fcst_qpf_6hr_in).toBeNull();
  });

  it("market_close_utc is YYYY-MM-DDTHH:MM:SSZ (no milliseconds)", () => {
    const row = buildPairsRow("2025-01-08", "NYC", [], null);
    expect(row.market_close_utc).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
  });

  it("date + station passthrough to row", () => {
    const row = buildPairsRow("2025-04-15", "LAX", [], null);
    expect(row.date).toBe("2025-04-15");
    expect(row.station).toBe("LAX");
  });

  it("obs aggregates correctly inlined", () => {
    const row = buildPairsRow("2025-01-08", "NYC", [{ temp_f: 30 }, { temp_f: 40 }], null);
    expect(row.obs_high_f).toBe(40);
    expect(row.obs_low_f).toBe(30);
    expect(row.obs_mean_f).toBe(35);
    expect(row.obs_count).toBe(2);
  });
});

describe("buildPairs", () => {
  it("2-date input → 2 rows; missing-date entries get [] obs + null climate", () => {
    const rows = buildPairs(
      "NYC",
      ["2025-01-08", "2025-01-09"],
      { "2025-01-08": [{ temp_f: 35 }] },
      { "2025-01-08": NYC_CLIMATE },
    );
    expect(rows).toHaveLength(2);
    expect(rows[0]?.obs_count).toBe(1);
    expect(rows[0]?.cli_high_f).toBe(45);
    expect(rows[1]?.obs_count).toBe(0);
    expect(rows[1]?.cli_high_f).toBeNull();
  });

  it("empty dates array → empty frozen result", () => {
    const rows = buildPairs("NYC", [], {}, {});
    expect(rows).toEqual([]);
    expect(Object.isFrozen(rows)).toBe(true);
  });

  it("returned array is frozen", () => {
    const rows = buildPairs("NYC", ["2025-01-08"], {}, {});
    expect(Object.isFrozen(rows)).toBe(true);
  });

  it("preserves input date order", () => {
    const rows = buildPairs("NYC", ["2025-01-10", "2025-01-08", "2025-01-09"], {}, {});
    expect(rows.map((r) => r.date)).toEqual(["2025-01-10", "2025-01-08", "2025-01-09"]);
  });
});

describe("pairsToRows", () => {
  it("returns the array unchanged (identity)", () => {
    const rows = buildPairs("NYC", ["2025-01-08"], {}, {});
    expect(pairsToRows(rows)).toBe(rows);
  });
});
