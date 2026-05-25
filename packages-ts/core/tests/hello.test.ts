import { describe, expect, it } from "vitest";

import { helloCore, version } from "../src/index.js";

describe("@mostlyright/core hello-world scaffold", () => {
  it("exports the placeholder version string", () => {
    expect(version).toBe("0.0.0");
  });

  it("returns the expected hello string", () => {
    expect(helloCore()).toBe("hello @mostlyright/core");
  });
});
