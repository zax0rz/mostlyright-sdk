import { describe, expect, it } from "vitest";

import { helloWeather, version } from "../src/index.js";

describe("@mostlyright/weather hello-world scaffold", () => {
  it("exports the placeholder version string", () => {
    expect(version).toBe("0.0.0");
  });

  it("returns the expected hello string", () => {
    expect(helloWeather()).toBe("hello @mostlyright/weather");
  });
});
