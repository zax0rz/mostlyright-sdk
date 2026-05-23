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

describe("tradewinds (meta) hello-world scaffold", () => {
  it("exports the placeholder version string", () => {
    expect(version).toBe("0.0.0");
  });

  it("re-exports helloCore from @tradewinds/core", () => {
    expect(helloCore()).toBe("hello @tradewinds/core");
  });

  it("re-exports helloWeather from @tradewinds/weather", () => {
    expect(helloWeather()).toBe("hello @tradewinds/weather");
  });

  it("re-exports helloMarkets from @tradewinds/markets", () => {
    expect(helloMarkets()).toBe("hello @tradewinds/markets");
  });

  it("namespaces each underlying package's version constant", () => {
    expect(core.version).toBe("0.0.0");
    expect(weather.version).toBe("0.0.0");
    expect(markets.version).toBe("0.0.0");
  });
});
