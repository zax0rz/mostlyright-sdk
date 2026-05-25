// TS-W4 Plan 06 Task 2 — barrel re-export of crosscheckIemGhcnh from
// @mostlyrightmd/core/qc subpath. Confirms the public surface ships
// alongside QCEngine + ALPHA_RULES (Wave 5).

import { describe, expect, it } from "vitest";

import { type CrosscheckDisagreement, crosscheckIemGhcnh } from "../../src/qc/index.js";

describe("@mostlyrightmd/core/qc — crosscheckIemGhcnh barrel re-export", () => {
  it("crosscheckIemGhcnh is exported from the barrel", () => {
    expect(typeof crosscheckIemGhcnh).toBe("function");
  });

  it("returns CrosscheckDisagreement shape with camelCase keys", () => {
    const iem = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 20 }];
    const ghcnh = [{ station: "NYC", eventTime: "2024-06-01T00:00:00Z", temp_c: 25 }];
    const out: ReadonlyArray<CrosscheckDisagreement> = crosscheckIemGhcnh(iem, ghcnh);
    expect(out.length).toBe(1);
    const row = out[0];
    if (row === undefined) throw new Error("expected one disagreement row");
    expect(row).toEqual({
      station: "NYC",
      eventTime: "2024-06-01T00:00:00Z",
      tempCIem: 20,
      tempCGhcnh: 25,
      deltaC: 5,
    });
    // Explicit key-presence assertions for the camelCase contract.
    expect(Object.hasOwn(row, "eventTime")).toBe(true);
    expect(Object.hasOwn(row, "tempCIem")).toBe(true);
    expect(Object.hasOwn(row, "tempCGhcnh")).toBe(true);
    expect(Object.hasOwn(row, "deltaC")).toBe(true);
    // Should NOT have snake_case (the Python form) — wire-format
    // conversion is the JSON serializer's job, not this function's.
    expect(Object.hasOwn(row, "event_time")).toBe(false);
    expect(Object.hasOwn(row, "temp_c_iem")).toBe(false);
    expect(Object.hasOwn(row, "temp_c_ghcnh")).toBe(false);
    expect(Object.hasOwn(row, "delta_c")).toBe(false);
  });
});
