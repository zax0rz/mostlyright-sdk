import { describe, expect, it, vi } from "vitest";

import { helloCodegen, runCodegen, version } from "../src/index.js";

describe("@tradewinds/codegen hello-world scaffold", () => {
  it("exports the placeholder version string", () => {
    expect(version).toBe("0.0.0");
  });

  it("returns the expected hello string", () => {
    expect(helloCodegen()).toBe("hello @tradewinds/codegen");
  });

  it("runCodegen logs the placeholder notice (real impl lands in Wave 3)", () => {
    const spy = vi.spyOn(console, "log").mockImplementation(() => undefined);
    runCodegen();
    expect(spy).toHaveBeenCalledWith(
      "@tradewinds/codegen - implementation lands in Wave 3",
    );
    spy.mockRestore();
  });
});
