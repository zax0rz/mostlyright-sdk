import { describe, expect, it } from "vitest";

import { helloCodegen, runCodegen, version } from "../src/index.js";

describe("@mostlyrightmd/codegen hello-world scaffold", () => {
  it("exports the placeholder version string", () => {
    expect(version).toBe("0.0.0");
  });

  it("returns the expected hello string", () => {
    expect(helloCodegen()).toBe("hello @mostlyrightmd/codegen");
  });

  it("exposes runCodegen as an async function (real impl shipped in TS-W0 Wave 3)", () => {
    expect(typeof runCodegen).toBe("function");
  });
});
