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

  it("ships v0.1.0 schemas pre-registered (codex iter-1 P2 regression)", () => {
    // Fresh import must already know the canonical schemas; callers must
    // NOT need to call `registerSchema` before `describe(...)` works.
    for (const id of [
      "schema.observation.v1",
      "schema.forecast.iem_mos.v1",
      "schema.settlement.cli.v1",
      "schema.observation_ledger.v1",
      "schema.observation_qc.v1",
    ]) {
      const out = describeSchema(id);
      expect(out).toContain(`Schema: ${id}`);
      expect(out).toContain("Columns:");
    }
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

describe("climateGaps() — Phase 21 21-11 messaging", () => {
  it("throws ClimateGapsNotImplementedError (back-compat alias still works)", () => {
    expect(() => climateGaps("KNYC", "2025-01-01", "2025-01-31")).toThrow(
      ClimateGapsNotImplementedError,
    );
  });

  it("also catchable as DataAvailabilityError (new typed exception)", async () => {
    // Import lazily to keep the describe-test contract surface tight.
    const { DataAvailabilityError } = await import("../../src/exceptions/index.js");
    try {
      climateGaps("KNYC", "2025-01-01", "2025-01-31");
      throw new Error("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(DataAvailabilityError);
      const err = e as InstanceType<typeof DataAvailabilityError>;
      expect(err.reason).toBe("model_unavailable");
      expect(err.source).toBe("climate-cache-browser");
    }
  });

  it("error hint explains the 10+ MB / server-only architecture", () => {
    try {
      climateGaps("KNYC", "2025-01-01", "2025-01-31");
    } catch (e) {
      const err = e as ClimateGapsNotImplementedError;
      expect(err.hint).toMatch(/10\+ MB|server-only/);
    }
  });

  it("error hint points users at the Python SDK as the v1.x workaround", () => {
    try {
      climateGaps("KNYC", "2025-01-01", "2025-01-31");
    } catch (e) {
      const err = e as ClimateGapsNotImplementedError;
      expect(err.hint).toMatch(/Python SDK|mostlyright\.discover\.climate_gaps/);
    }
  });

  it("error hint links to docs/climate-gaps URL", () => {
    try {
      climateGaps("KNYC", "2025-01-01", "2025-01-31");
    } catch (e) {
      const err = e as ClimateGapsNotImplementedError;
      expect(err.hint).toMatch(/climate-gaps/);
    }
  });
});
