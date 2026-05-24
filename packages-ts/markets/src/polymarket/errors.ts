// TS-W5 — Polymarket-specific errors. All subclass TradewindsError so they
// gain toDict() and the standard request-id/error-code payload shape.

import { TradewindsError } from "@tradewinds/core";

/** Event payload is malformed (bad event id, oversized description, bad URL). */
export class PolymarketEventError extends TradewindsError {
  constructor(message: string) {
    super(message);
    this.name = "PolymarketEventError";
  }
  static readonly defaultErrorCode = "POLYMARKET_EVENT_INVALID";
}

/** Settlement engine couldn't resolve an event to a value. */
export class PolymarketSettlementError extends TradewindsError {
  constructor(message: string) {
    super(message);
    this.name = "PolymarketSettlementError";
  }
  static readonly defaultErrorCode = "POLYMARKET_SETTLEMENT_FAILED";
}

/**
 * Settlement attempted before the resolution source's publication delay
 * has elapsed. Carries `waitHours` so the caller can schedule a retry.
 *
 * Codex iter-1 P2: overrides `payload()` so `toDict()` (and any MCP
 * serializer downstream) includes the structured retry metadata. The
 * fields are otherwise only readable via the live JS error object.
 */
export class TooEarlyToSettleError extends TradewindsError {
  readonly waitHours: number;
  readonly resolutionSourceType: string;
  constructor(message: string, opts: { waitHours: number; resolutionSourceType: string }) {
    super(message);
    this.name = "TooEarlyToSettleError";
    this.waitHours = opts.waitHours;
    this.resolutionSourceType = opts.resolutionSourceType;
  }
  static readonly defaultErrorCode = "POLYMARKET_TOO_EARLY";

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      wait_hours: this.waitHours,
      resolution_source_type: this.resolutionSourceType,
    };
  }
}

/**
 * Description exceeded the 16 KB cap. Direct subclass of TradewindsError
 * (rather than PolymarketEventError) because TS prevents narrowing a
 * `static readonly` literal type in a subclass.
 */
export class PayloadTooLargeError extends TradewindsError {
  constructor(message: string) {
    super(message);
    this.name = "PayloadTooLargeError";
  }
  static readonly defaultErrorCode = "POLYMARKET_PAYLOAD_TOO_LARGE";
}
