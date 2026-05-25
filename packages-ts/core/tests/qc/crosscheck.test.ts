// TS-W4 Plan 06 Task 1 — crosscheckIemGhcnh inner-join + tolerance.
//
// Mirrors Python `mostlyright.qc.crosscheck_iem_ghcnh` at
// `packages/core/src/mostlyright/qc.py:191-228`. Strict `>` boundary
// (NOT `>=`) per qc.py:228. camelCase output keys per TS-idiom Parity-Ticket.

import { describe, expect, it } from "vitest";

import { crosscheckIemGhcnh } from "../../src/qc/crosscheck.js";

describe("crosscheckIemGhcnh — empty inputs", () => {
  it("empty iem AND empty ghcnh → []", () => {
    expect(crosscheckIemGhcnh([], [])).toEqual([]);
  });

  it("empty iem, non-empty ghcnh → []", () => {
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    expect(crosscheckIemGhcnh([], ghcnh)).toEqual([]);
  });

  it("non-empty iem, empty ghcnh → []", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    expect(crosscheckIemGhcnh(iem, [])).toEqual([]);
  });
});

describe("crosscheckIemGhcnh — inner join semantics", () => {
  it("no matching (station, eventTime) → []", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ station: "LAX", eventTime: "2024-06-01T00:00:00Z", temp_c: 30 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });

  it("matching station but different eventTime → []", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T01:00:00Z", temp_c: 30 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });
});

describe("crosscheckIemGhcnh — tolerance threshold", () => {
  it("agreement within tolerance (delta=1.5, tol=2.0) → []", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 21.5 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });

  it("disagreement above tolerance (delta=5, tol=2) → 1 row", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25.0 }];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out).toEqual([
      {
        station: "NYC",
        eventTime: "2024-06-01T00:00:00Z",
        tempCIem: 20.0,
        tempCGhcnh: 25.0,
        deltaC: 5.0,
      },
    ]);
  });

  it("strict > boundary: delta === tolC → NO disagreement (NOT >=)", () => {
    // Python qc.py:228 uses strict `>`. delta_c === tol_c → NO disagreement.
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 22.0 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });

  it("strict > boundary: delta just above tolC → 1 disagreement", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 22.001 }];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out.length).toBe(1);
    expect(out[0]?.deltaC).toBeCloseTo(2.001, 10);
  });

  it("custom tolC = 0.5: delta=0.7 → 1 disagreement", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.7 }];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 0.5 });
    expect(out.length).toBe(1);
    expect(out[0]?.deltaC).toBeCloseTo(0.7, 10);
  });
});

describe("crosscheckIemGhcnh — default tolC = 2.0", () => {
  it("no opts arg, delta=2.0 → []", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 22.0 }];
    expect(crosscheckIemGhcnh(iem, ghcnh)).toEqual([]);
  });

  it("no opts arg, delta=2.5 → 1 disagreement", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 22.5 }];
    const out = crosscheckIemGhcnh(iem, ghcnh);
    expect(out.length).toBe(1);
  });

  it("opts={} (empty), delta=2.0 → []", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 22.0 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, {})).toEqual([]);
  });
});

describe("crosscheckIemGhcnh — mixed match/no-match", () => {
  it("3 iem + 3 ghcnh; only NYC matches AND disagrees", () => {
    const iem = [
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 },
      { station: "LAX", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 },
      { station: "BOS", eventTime: "2024-06-01T00:00:00Z", temp_c: 15 },
    ];
    const ghcnh = [
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 30 }, // matches+disagrees (delta=10)
      { station: "LAX", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }, // matches+agrees (delta=0)
      { station: "CHI", eventTime: "2024-06-01T00:00:00Z", temp_c: 18 }, // no match
    ];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out.length).toBe(1);
    expect(out[0]?.station).toBe("NYC");
    expect(out[0]?.deltaC).toBe(10);
  });
});

describe("crosscheckIemGhcnh — null/non-finite temp_c handling", () => {
  it("iem temp_c=null → skipped (no comparison)", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: null }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25.0 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });

  it("ghcnh temp_c=null → skipped", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20.0 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: null }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });

  it("both null → skipped", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: null }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: null }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });

  it("iem temp_c=NaN → skipped (non-finite)", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: Number.NaN }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25.0 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });

  it("iem temp_c=Infinity → skipped (non-finite)", () => {
    const iem = [
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: Number.POSITIVE_INFINITY },
    ];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25.0 }];
    expect(crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toEqual([]);
  });
});

describe("crosscheckIemGhcnh — deltaC is absolute (positive)", () => {
  it("iem=25, ghcnh=20 → deltaC: 5 (NOT -5)", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out.length).toBe(1);
    expect(out[0]?.deltaC).toBe(5);
    expect(out[0]?.tempCIem).toBe(25);
    expect(out[0]?.tempCGhcnh).toBe(20);
  });

  it("iem=20, ghcnh=25 → deltaC: 5 (also positive)", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out.length).toBe(1);
    expect(out[0]?.deltaC).toBe(5);
    expect(out[0]?.tempCIem).toBe(20);
    expect(out[0]?.tempCGhcnh).toBe(25);
  });
});

describe("crosscheckIemGhcnh — missing required columns throws", () => {
  it("iem row missing station throws Error 'must carry'", () => {
    const iem = [{ eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }] as unknown as Array<{
      station: string;
      eventTime: string;
      temp_c: number | null;
    }>;
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    expect(() => crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toThrow(/must carry/);
  });

  it("iem row missing eventTime throws Error", () => {
    const iem = [{ station: "NYC", temp_c: 20 }] as unknown as Array<{
      station: string;
      eventTime: string;
      temp_c: number | null;
    }>;
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    expect(() => crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toThrow(/must carry/);
  });

  it("ghcnh row missing station throws Error", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }] as unknown as Array<{
      station: string;
      eventTime: string;
      temp_c: number | null;
    }>;
    expect(() => crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toThrow(/must carry/);
  });

  it("ghcnh row missing eventTime throws Error", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ station: "NYC", temp_c: 25 }] as unknown as Array<{
      station: string;
      eventTime: string;
      temp_c: number | null;
    }>;
    expect(() => crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 })).toThrow(/must carry/);
  });
});

describe("crosscheckIemGhcnh — purity / immutability", () => {
  it("does NOT mutate iem rows", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    const iemBefore = JSON.parse(JSON.stringify(iem));
    crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(iem).toEqual(iemBefore);
  });

  it("does NOT mutate ghcnh rows", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    const ghcnhBefore = JSON.parse(JSON.stringify(ghcnh));
    crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(ghcnh).toEqual(ghcnhBefore);
  });
});

describe("crosscheckIemGhcnh — output order matches ghcnh iteration order", () => {
  it("disagreements emitted in ghcnh-row order", () => {
    const iem = [
      { station: "BOS", eventTime: "2024-06-01T00:00:00Z", temp_c: 10 },
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 },
    ];
    // ghcnh order: NYC first, then BOS — output must follow this order.
    const ghcnh = [
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 30 }, // delta=10
      { station: "BOS", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }, // delta=15
    ];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out.length).toBe(2);
    expect(out[0]?.station).toBe("NYC");
    expect(out[1]?.station).toBe("BOS");
  });
});

describe("crosscheckIemGhcnh — duplicate iem keys: last-wins", () => {
  it("two iem rows same (station, eventTime); last temp_c wins", () => {
    const iem = [
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 },
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 30 }, // last-wins
    ];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out.length).toBe(1);
    expect(out[0]?.tempCIem).toBe(30); // last iem row wins
    expect(out[0]?.deltaC).toBe(5);
  });
});

describe("crosscheckIemGhcnh — composite key correctness (station + eventTime)", () => {
  it("same station, different eventTime → separate entries (not collapsed)", () => {
    const iem = [
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 },
      { station: "NYC", eventTime: "2024-06-01T01:00:00Z", temp_c: 22 },
    ];
    const ghcnh = [
      { station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 30 }, // delta=10 → fires
      { station: "NYC", eventTime: "2024-06-01T01:00:00Z", temp_c: 23 }, // delta=1 → no fire
    ];
    const out = crosscheckIemGhcnh(iem, ghcnh, { tolC: 2.0 });
    expect(out.length).toBe(1);
    expect(out[0]?.eventTime).toBe("2024-06-01T00:00:00Z");
  });
});
