import { describe, expect, it } from "vitest";

import {
  PayloadTooLargeError,
  PolymarketEventError,
  PolymarketSettlementError,
  TooEarlyToSettleError,
} from "../../src/polymarket/index.js";

describe("Polymarket error classes", () => {
  it("expose the standard TradewindsError surface (name, message, toDict)", () => {
    const err = new PolymarketEventError("bad event");
    expect(err.name).toBe("PolymarketEventError");
    expect(err.message).toBe("bad event");
    const d = err.toDict();
    expect(d.message).toBe("bad event");
  });

  it("PayloadTooLargeError stays a separate class (sibling of PolymarketEventError)", () => {
    const err = new PayloadTooLargeError("over 16KB");
    expect(err.name).toBe("PayloadTooLargeError");
    expect(err).not.toBeInstanceOf(PolymarketEventError);
  });

  it("PolymarketSettlementError carries the documented error code", () => {
    expect(PolymarketSettlementError.defaultErrorCode).toBe("POLYMARKET_SETTLEMENT_FAILED");
  });

  it("TooEarlyToSettleError exposes waitHours + resolutionSourceType on the instance", () => {
    const err = new TooEarlyToSettleError("retry later", {
      waitHours: 3.5,
      resolutionSourceType: "wunderground",
    });
    expect(err.waitHours).toBe(3.5);
    expect(err.resolutionSourceType).toBe("wunderground");
  });

  it("TooEarlyToSettleError.toDict includes wait_hours + resolution_source_type (codex iter-1 P2)", () => {
    const err = new TooEarlyToSettleError("retry later", {
      waitHours: 3.5,
      resolutionSourceType: "wunderground",
    });
    const d = err.toDict();
    expect(d.wait_hours).toBe(3.5);
    expect(d.resolution_source_type).toBe("wunderground");
  });
});
