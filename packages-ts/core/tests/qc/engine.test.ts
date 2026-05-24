// TS-W4 Plan 05 Task 2 — QCEngine.apply emits obsQcStatus bitfield column.
//
// Tests the orchestration: rule.evaluate(rows) called once per rule (vectorized),
// per-row OR-aggregation of `1 << rule.bitPosition`, immutability invariants,
// empty-input handling, custom rule injection, and the defensive bit-31 ceiling.

import { describe, expect, it } from "vitest";

import { QCEngine } from "../../src/qc/engine.js";
import type { QCRule } from "../../src/qc/rules.js";

describe("QCEngine.apply — basic semantics", () => {
  it("empty input returns empty output (no throw)", () => {
    const engine = new QCEngine();
    expect(engine.apply([])).toEqual([]);
  });

  it("no rules fire → obsQcStatus === 0", () => {
    const engine = new QCEngine();
    const out = engine.apply([
      { temp_c: 20, dew_point_c: 15, wind_speed_ms: 5, wind_dir_deg: 90, slp_hpa: 1013 },
    ]);
    expect(out.length).toBe(1);
    expect(out[0]?.obsQcStatus).toBe(0);
  });
});

describe("QCEngine.apply — single bit set", () => {
  it("bit 0 (temp_c.out_of_range): temp_c=-100 → obsQcStatus === 1", () => {
    const engine = new QCEngine();
    // dew_point_c=-110 < temp_c=-100, so bit 1 (dewpoint exceeds) does NOT fire.
    const out = engine.apply([
      { temp_c: -100, dew_point_c: -110, wind_speed_ms: 0, wind_dir_deg: 0, slp_hpa: 1000 },
    ]);
    expect(out[0]?.obsQcStatus).toBe(0b00001);
  });

  it("bit 1 (dew_point_c.exceeds_temp): dew_point > temp → obsQcStatus === 2", () => {
    const engine = new QCEngine();
    const out = engine.apply([{ temp_c: 10, dew_point_c: 15 }]);
    expect(out[0]?.obsQcStatus).toBe(0b00010);
  });

  it("bit 2 (wind_speed_ms.negative): wind_speed_ms < 0 → obsQcStatus === 4", () => {
    const engine = new QCEngine();
    const out = engine.apply([{ wind_speed_ms: -1 }]);
    expect(out[0]?.obsQcStatus).toBe(0b00100);
  });

  it("bit 3 (wind_dir_deg.out_of_range): wind_dir_deg=400 → obsQcStatus === 8", () => {
    const engine = new QCEngine();
    const out = engine.apply([{ wind_dir_deg: 400 }]);
    expect(out[0]?.obsQcStatus).toBe(0b01000);
  });

  it("bit 4 (slp_hpa.out_of_range): slp_hpa=500 → obsQcStatus === 16", () => {
    const engine = new QCEngine();
    const out = engine.apply([{ slp_hpa: 500 }]);
    expect(out[0]?.obsQcStatus).toBe(0b10000);
  });
});

describe("QCEngine.apply — multi-bit aggregation", () => {
  it("3 bits set: temp out-of-range + dewpoint exceeds + wind speed negative → 7", () => {
    const engine = new QCEngine();
    // temp_c=-100 → bit 0; dew_point_c=5 > temp_c=-100 → bit 1; wind_speed_ms=-5 → bit 2.
    const out = engine.apply([{ temp_c: -100, dew_point_c: 5, wind_speed_ms: -5 }]);
    expect(out[0]?.obsQcStatus).toBe(0b00111);
  });

  it("all 5 bits set → obsQcStatus === 31", () => {
    const engine = new QCEngine();
    // temp_c=200 → bit 0 (out of range); dew_point_c=300 > temp_c=200 → bit 1;
    // wind_speed_ms=-1 → bit 2; wind_dir_deg=999 → bit 3; slp_hpa=2000 → bit 4.
    const out = engine.apply([
      {
        temp_c: 200,
        dew_point_c: 300,
        wind_speed_ms: -1,
        wind_dir_deg: 999,
        slp_hpa: 2000,
      },
    ]);
    expect(out[0]?.obsQcStatus).toBe(0b11111);
    expect(out[0]?.obsQcStatus).toBe(31);
  });
});

describe("QCEngine.apply — immutability + shape preservation", () => {
  it("source rows are NOT mutated", () => {
    const engine = new QCEngine();
    const input = [{ temp_c: -100 }];
    const snapshot = JSON.parse(JSON.stringify(input)) as typeof input;
    engine.apply(input);
    expect(input).toEqual(snapshot);
    const inputRow = input[0];
    expect(inputRow).toBeDefined();
    if (inputRow !== undefined) {
      expect(Object.hasOwn(inputRow, "obsQcStatus")).toBe(false);
    }
  });

  it("output rows preserve all input columns + obsQcStatus", () => {
    const engine = new QCEngine();
    const input = [
      { temp_c: 20, dew_point_c: 10, station: "KORD", event_time: "2024-01-01T00:00:00Z" },
    ];
    const out = engine.apply(input);
    expect(out[0]?.temp_c).toBe(20);
    expect(out[0]?.dew_point_c).toBe(10);
    expect(out[0]?.station).toBe("KORD");
    expect(out[0]?.event_time).toBe("2024-01-01T00:00:00Z");
    expect(out[0]?.obsQcStatus).toBe(0);
  });

  it("returns one output row per input row, in order", () => {
    const engine = new QCEngine();
    const input = [{ temp_c: 0 }, { temp_c: -100 }, { temp_c: 100 }];
    const out = engine.apply(input);
    expect(out.length).toBe(3);
    expect(out[0]?.obsQcStatus).toBe(0);
    expect(out[1]?.obsQcStatus).toBe(0b00001);
    expect(out[2]?.obsQcStatus).toBe(0b00001);
  });
});

describe("QCEngine.apply — custom rule injection", () => {
  it("new QCEngine([]) with no rules → every row gets obsQcStatus: 0", () => {
    const engine = new QCEngine([]);
    const out = engine.apply([{ temp_c: -999 }, { temp_c: 999 }]);
    expect(out[0]?.obsQcStatus).toBe(0);
    expect(out[1]?.obsQcStatus).toBe(0);
  });

  it("custom rule at bit 7 → row gets 1 << 7 === 128", () => {
    const customRule: QCRule = {
      ruleId: "custom.always_fire",
      bitPosition: 7,
      description: "test",
      field: "test",
      evaluate: (rows) => rows.map(() => true),
    };
    const engine = new QCEngine([customRule]);
    const out = engine.apply([{}]);
    expect(out[0]?.obsQcStatus).toBe(128);
  });
});

describe("QCEngine constructor — defensive bit-31 ceiling", () => {
  it("throws RangeError if a rule's bitPosition >= 32", () => {
    const badRule: QCRule = {
      ruleId: "bad.bit_32",
      bitPosition: 32,
      description: "bad",
      field: "bad",
      evaluate: () => [],
    };
    expect(() => new QCEngine([badRule])).toThrow(RangeError);
  });

  it("throws RangeError if a rule's bitPosition is negative", () => {
    const badRule: QCRule = {
      ruleId: "bad.bit_neg",
      bitPosition: -1,
      description: "bad",
      field: "bad",
      evaluate: () => [],
    };
    expect(() => new QCEngine([badRule])).toThrow(RangeError);
  });

  it("accepts bitPosition === 31 (max valid)", () => {
    const okRule: QCRule = {
      ruleId: "ok.bit_31",
      bitPosition: 31,
      description: "ok",
      field: "ok",
      evaluate: () => [],
    };
    expect(() => new QCEngine([okRule])).not.toThrow();
  });
});

describe("QCEngine — vectorized evaluation contract", () => {
  it("rule.evaluate(rows) is called ONCE per rule (not per-row)", () => {
    let callCount = 0;
    const countingRule: QCRule = {
      ruleId: "counting.always",
      bitPosition: 0,
      description: "counts how many times evaluate is called",
      field: "counting",
      evaluate: (rows) => {
        callCount++;
        return rows.map(() => false);
      },
    };
    const engine = new QCEngine([countingRule]);
    engine.apply([{ x: 1 }, { x: 2 }, { x: 3 }, { x: 4 }, { x: 5 }]);
    expect(callCount).toBe(1);
  });
});
