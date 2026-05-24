import { describe, expect, it } from "vitest";

import {
  dataVersionForResearch,
  dataVersionFromComponents,
} from "../../src/discovery/data-version.js";

describe("dataVersionFromComponents", () => {
  it("produces a frozen DataVersion with a 64-hex token", async () => {
    const v = await dataVersionFromComponents({
      sdkVersion: "0.1.0",
      schemaIds: ["schema.observation.v1"],
      sources: ["awc.live"],
      codeSha: "abcdef",
      dataSha: "deadbeef",
    });
    expect(Object.isFrozen(v)).toBe(true);
    expect(v.token).toMatch(/^[0-9a-f]{64}$/);
  });

  it("matches the Python from_components canonical concatenation", async () => {
    // Reference: Python computes
    //   sha256(b"0.1.0|schema.observation.v1|awc.live|code|data").hexdigest()
    // which equals the constant below. The TS implementation must produce
    // the same hex for the same inputs (sorted by Python contract).
    const v = await dataVersionFromComponents({
      sdkVersion: "0.1.0",
      schemaIds: ["schema.observation.v1"],
      sources: ["awc.live"],
      codeSha: "code",
      dataSha: "data",
    });
    // Compute the reference here so the test is self-contained — same
    // canonical form, same algorithm, same encoding.
    const reference = await sha256Hex("0.1.0|schema.observation.v1|awc.live|code|data");
    expect(v.token).toBe(reference);
  });

  it("sorts schemaIds and sources before hashing (order-independent)", async () => {
    const a = await dataVersionFromComponents({
      sdkVersion: "0.1.0",
      schemaIds: ["schema.b", "schema.a"],
      sources: ["src.z", "src.a"],
      codeSha: "c",
      dataSha: "d",
    });
    const b = await dataVersionFromComponents({
      sdkVersion: "0.1.0",
      schemaIds: ["schema.a", "schema.b"],
      sources: ["src.a", "src.z"],
      codeSha: "c",
      dataSha: "d",
    });
    expect(a.token).toBe(b.token);
    expect(a.schemaIds).toEqual(["schema.a", "schema.b"]);
    expect(a.sources).toEqual(["src.a", "src.z"]);
  });

  it("round-trips: same inputs → same token", async () => {
    const args = {
      sdkVersion: "0.1.0",
      schemaIds: ["x"],
      sources: ["y"],
      codeSha: "z",
      dataSha: "w",
    };
    const t1 = (await dataVersionFromComponents(args)).token;
    const t2 = (await dataVersionFromComponents(args)).token;
    expect(t1).toBe(t2);
  });

  it("changes the token when any component changes", async () => {
    const base = {
      sdkVersion: "0.1.0",
      schemaIds: ["x"],
      sources: ["y"],
      codeSha: "z",
      dataSha: "w",
    };
    const t0 = (await dataVersionFromComponents(base)).token;
    const t1 = (await dataVersionFromComponents({ ...base, sdkVersion: "0.1.1" })).token;
    const t2 = (await dataVersionFromComponents({ ...base, codeSha: "Z" })).token;
    const t3 = (await dataVersionFromComponents({ ...base, dataSha: "W" })).token;
    expect(new Set([t0, t1, t2, t3]).size).toBe(4);
  });
});

describe("dataVersionForResearch", () => {
  it("encodes the call signature in codeSha", async () => {
    const v = await dataVersionForResearch({
      sdkVersion: "0.1.0",
      station: "KNYC",
      fromDate: "2025-01-01",
      toDate: "2025-01-07",
      dataSha: "abc",
    });
    expect(v.codeSha).toBe("research:KNYC:2025-01-01:2025-01-07");
    expect(v.sources).toContain("awc.live");
    expect(v.sources).toContain("iem.archive");
    expect(v.schemaIds).toContain("schema.observation.v1");
  });

  it("two calls with the same args produce the same token", async () => {
    const args = {
      sdkVersion: "0.1.0",
      station: "KNYC",
      fromDate: "2025-01-01",
      toDate: "2025-01-07",
      dataSha: "abc",
    } as const;
    const t1 = (await dataVersionForResearch(args)).token;
    const t2 = (await dataVersionForResearch(args)).token;
    expect(t1).toBe(t2);
  });
});

// Local SHA-256 helper using Web Crypto — same primitive the implementation
// uses, just so the test isn't a tautology against the implementation's
// internal hex encoder. Hand-rolled hex here, structurally distinct path.
async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const arr = Array.from(new Uint8Array(digest));
  return arr.map((b) => b.toString(16).padStart(2, "0")).join("");
}
