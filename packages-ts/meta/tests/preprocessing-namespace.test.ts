// Phase 21 21-10 — verify the `preprocessing` (lowercase) namespace
// matches Python `mostlyright.preprocessing` and the `Preprocessing`
// (PascalCase) deprecated alias points at the same module.

import { describe, expect, it } from "vitest";

import { Preprocessing, preprocessing } from "../src/index.js";

describe("preprocessing namespace (Phase 21 21-10)", () => {
  it("exports the lowercase `preprocessing` namespace from the meta barrel", () => {
    expect(preprocessing).toBeDefined();
    expect(typeof preprocessing).toBe("object");
  });

  it("surfaces clipOutliers via the lowercase namespace", () => {
    expect(typeof preprocessing.clipOutliers).toBe("function");
  });

  it("surfaces PHYSICS_BOUNDS via the lowercase namespace", () => {
    expect(preprocessing.PHYSICS_BOUNDS).toBeDefined();
    expect(typeof preprocessing.PHYSICS_BOUNDS).toBe("object");
  });

  it("surfaces iemCrosscheck via the lowercase namespace (Python parity)", () => {
    expect(typeof preprocessing.iemCrosscheck).toBe("function");
  });

  it("PascalCase Preprocessing alias points at the same module object", () => {
    expect(Preprocessing).toBe(preprocessing);
  });

  it("Preprocessing.clipOutliers === preprocessing.clipOutliers (same fn)", () => {
    expect(Preprocessing.clipOutliers).toBe(preprocessing.clipOutliers);
  });

  it("clipOutliers runs end-to-end via the namespace", () => {
    const rows = [
      { temp_c: 10, station: "X" },
      { temp_c: 20, station: "X" },
      { temp_c: 30, station: "X" },
    ];
    // Explicit-bounds branch — original col preserved; `{col}_clipped` added.
    const out = preprocessing.clipOutliers(rows, "temp_c", { bounds: [15, 25] });
    expect(out.map((r) => r.temp_c)).toEqual([10, 20, 30]);
    expect(out.map((r) => r.temp_c_clipped)).toEqual([15, 20, 25]);
  });
});
