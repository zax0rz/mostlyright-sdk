import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  ClimateGapsNotImplementedError,
  UnknownSchemaError,
  climateGaps,
  describe as describeSchema,
  featureCatalog,
  registerSchema,
} from "../../src/discovery/describe.js";

describe("describe()", () => {
  // Each test registers its own schemas so the registry state is predictable.
  // The registry is module-level; we don't expose a clear() so we accept that
  // a registered schema from one test will be visible to later ones, and use
  // unique ids to keep tests independent.

  it("returns a multi-line description for a registered schema", () => {
    registerSchema({
      id: "test.describe.basic",
      title: "Test schema",
      columnCount: 2,
      columns: [
        { name: "a", description: "first col", nullable: false },
        { name: "b", description: "second col", nullable: true },
      ],
    });
    const out = describeSchema("test.describe.basic");
    expect(out).toContain("Schema: test.describe.basic");
    expect(out).toContain("Title: Test schema");
    expect(out).toContain("Columns: 2");
    expect(out).toContain("- a — first col");
    expect(out).toContain("- b? — second col");
  });

  it("throws UnknownSchemaError for unregistered ids", () => {
    expect(() => describeSchema("nonexistent.schema.v1")).toThrow(UnknownSchemaError);
  });

  it("omits the dash when a column has no description", () => {
    registerSchema({
      id: "test.describe.no-desc",
      title: "T",
      columnCount: 1,
      columns: [{ name: "x", description: "", nullable: false }],
    });
    const out = describeSchema("test.describe.no-desc");
    expect(out).toContain("- x");
    expect(out).not.toContain("- x —");
  });
});

describe("featureCatalog()", () => {
  it("returns a stable-sorted list of transform names", () => {
    const c = featureCatalog();
    expect(c).toEqual([
      "calendarFeatures",
      "clipOutliers",
      "diff",
      "diff2",
      "heatIndex",
      "lag",
      "rolling",
      "spread",
      "windChill",
    ]);
  });

  it("returns a frozen array", () => {
    expect(Object.isFrozen(featureCatalog())).toBe(true);
  });
});

describe("climateGaps()", () => {
  it("throws ClimateGapsNotImplementedError with the expected message", () => {
    expect(() => climateGaps("KNYC", "2025-01-01", "2025-01-31")).toThrow(
      ClimateGapsNotImplementedError,
    );
    try {
      climateGaps("KNYC", "2025-01-01", "2025-01-31");
    } catch (e) {
      expect((e as Error).message).toContain("Python-only");
    }
  });
});
