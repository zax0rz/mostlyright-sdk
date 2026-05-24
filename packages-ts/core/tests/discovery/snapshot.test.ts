import { describe, expect, it } from "vitest";

import { dataVersionFromComponents } from "../../src/discovery/data-version.js";
import { buildSnapshot } from "../../src/discovery/snapshot.js";

describe("buildSnapshot", () => {
  it("creates a frozen snapshot with rows preserved", () => {
    const rows = [
      { date: "2025-01-01", cli_high_f: 40 },
      { date: "2025-01-02", cli_high_f: 38 },
    ];
    const s = buildSnapshot({
      schemaId: "schema.settlement.cli.v1",
      source: "nws.cli",
      rows,
      knowledgeTime: new Date("2025-01-03T00:00:00Z"),
    });
    expect(Object.isFrozen(s)).toBe(true);
    expect(s.rows).toHaveLength(2);
    expect(Object.isFrozen(s.rows[0])).toBe(true);
    expect(s.knowledgeTime).toBe("2025-01-03T00:00:00.000Z");
    expect(s.schemaId).toBe("schema.settlement.cli.v1");
    expect(s.source).toBe("nws.cli");
  });

  it("rejects empty schemaId or source", () => {
    expect(() => buildSnapshot({ schemaId: "", source: "src", rows: [] })).toThrow(RangeError);
    expect(() => buildSnapshot({ schemaId: "id", source: "", rows: [] })).toThrow(RangeError);
  });

  it("rejects non-array rows", () => {
    expect(() =>
      // @ts-expect-error testing runtime guard
      buildSnapshot({ schemaId: "id", source: "src", rows: { foo: 1 } }),
    ).toThrow(RangeError);
  });

  it("accepts an ISO string knowledgeTime and emits canonical Z form", () => {
    const s = buildSnapshot({
      schemaId: "id",
      source: "src",
      rows: [],
      knowledgeTime: "2025-01-03T00:00:00+00:00",
    });
    expect(s.knowledgeTime).toBe("2025-01-03T00:00:00.000Z");
  });

  it("rejects unparseable knowledgeTime strings", () => {
    expect(() =>
      buildSnapshot({ schemaId: "id", source: "src", rows: [], knowledgeTime: "not-a-date" }),
    ).toThrow(RangeError);
  });

  it("defaults knowledgeTime to now() when omitted", () => {
    const before = Date.now();
    const s = buildSnapshot({ schemaId: "id", source: "src", rows: [] });
    const after = Date.now();
    const ts = Date.parse(s.knowledgeTime);
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });

  it("toDict returns a JSON-safe payload with snake_case keys", () => {
    const s = buildSnapshot({
      schemaId: "id",
      source: "src",
      rows: [{ a: 1 }],
      knowledgeTime: "2025-01-01T00:00:00Z",
      metadata: { note: "test" },
    });
    const d = s.toDict();
    expect(d.knowledge_time).toBe("2025-01-01T00:00:00.000Z");
    expect(d.schema_id).toBe("id");
    expect(d.source).toBe("src");
    expect(d.data_version).toBeNull();
    expect(d.metadata).toEqual({ note: "test" });
    expect(d.rows).toEqual([{ a: 1 }]);
  });

  it("toDict coerces non-finite numbers to null", () => {
    const s = buildSnapshot({
      schemaId: "id",
      source: "src",
      rows: [{ x: Number.NaN, y: Number.POSITIVE_INFINITY, z: 1 }],
      knowledgeTime: "2025-01-01T00:00:00Z",
    });
    const rows = (s.toDict() as { rows: Array<Record<string, unknown>> }).rows;
    expect(rows[0]?.x).toBeNull();
    expect(rows[0]?.y).toBeNull();
    expect(rows[0]?.z).toBe(1);
  });

  it("toToon returns a TOON v3 tabular block", () => {
    const s = buildSnapshot({
      schemaId: "id",
      source: "src",
      rows: [
        { a: 1, b: 2 },
        { a: 3, b: 4 },
      ],
      knowledgeTime: "2025-01-01T00:00:00Z",
    });
    const toon = s.toToon();
    expect(toon.startsWith("rows[2]{a,b}:")).toBe(true);
    expect(toon).toContain("1,2");
    expect(toon).toContain("3,4");
  });

  it("includes the DataVersion in toDict output", async () => {
    const v = await dataVersionFromComponents({
      sdkVersion: "0.1.0",
      schemaIds: ["schema.observation.v1"],
      sources: ["iem.archive"],
      codeSha: "abc",
      dataSha: "def",
    });
    const s = buildSnapshot({
      schemaId: "schema.observation.v1",
      source: "iem.archive",
      rows: [{ event_time: "2025-01-01T00:00:00Z" }],
      dataVersion: v,
    });
    const d = s.toDict() as { data_version: { token: string } };
    expect(d.data_version.token).toBe(v.token);
  });

  it("isolates internal row state from caller mutations after build", () => {
    const rows = [{ a: 1 }];
    const s = buildSnapshot({ schemaId: "id", source: "src", rows });
    // Mutating the original array should not change the snapshot.
    rows.push({ a: 2 });
    expect(s.rows).toHaveLength(1);
  });
});
