import { describe, expect, it } from "vitest";

import {
  core,
  helloCore,
  helloMarkets,
  helloWeather,
  markets,
  version,
  weather,
} from "../src/index.js";

describe("mostlyright (meta) hello-world scaffold", () => {
  it("exports the placeholder version string", () => {
    expect(version).toBe("0.0.0");
  });

  it("re-exports helloCore from @mostlyright/core", () => {
    expect(helloCore()).toBe("hello @mostlyright/core");
  });

  it("re-exports helloWeather from @mostlyright/weather", () => {
    expect(helloWeather()).toBe("hello @mostlyright/weather");
  });

  it("re-exports helloMarkets from @mostlyright/markets", () => {
    expect(helloMarkets()).toBe("hello @mostlyright/markets");
  });

  it("namespaces each underlying package's version constant", () => {
    expect(core.version).toBe("0.0.0");
    expect(weather.version).toBe("0.0.0");
    expect(markets.version).toBe("0.0.0");
  });
});
