import { describe, expect, it } from "vitest";

import { helloMarkets, version } from "../src/index.js";

describe("@mostlyright/markets hello-world scaffold", () => {
  it("exports the placeholder version string", () => {
    expect(version).toBe("0.0.0");
  });

  it("returns the expected hello string", () => {
    expect(helloMarkets()).toBe("hello @mostlyright/markets");
  });
});
