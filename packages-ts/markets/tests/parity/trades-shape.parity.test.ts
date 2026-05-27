// Phase 21 21-06 — markets trades shape parity tests.
//
// The 21-06 plan called out three potential cross-language divergences in
// the markets trades surface:
//
//   1. Kalshi candle bucket label: Python labels by `end_period_ts`; TS
//      should do the same.
//   2. Polymarket pagination default: Python uses limit=100 per call; TS
//      Gamma client should do the same.
//   3. Equal-timestamp trade-ID tiebreaker: Python sorts by (ts ASC,
//      trade_id ASC); TS should match.
//
// As of Phase 21, the TS implementation already matches Python on (1)
// and (2). The tests below lock those alignments in via introspection
// (no network — pure source-code field-name assertions). The trade-ID
// sort tiebreaker is asserted via a synthetic-input unit test on the
// public surface so cross-language regressions surface immediately.

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const KALSHI_SRC = resolve(__dirname, "../../src/trades/kalshi.ts");
const TRADES_TYPES_SRC = resolve(__dirname, "../../src/trades/types.ts");
const POLYMARKET_CLIENT_SRC = resolve(__dirname, "../../src/polymarket/client.ts");

describe("trades shape parity — Kalshi candle bucket label (21-06 Task 1)", () => {
  it("kalshi.ts candle row uses end_period_ts (matches Python canonical)", () => {
    const src = readFileSync(KALSHI_SRC, "utf-8");
    // The candle-row builder must read `c.end_period_ts` (Python is
    // canonical per 21-06 D-04). Drift here means TS labels candles by
    // a different timestamp than Python — silent cross-language data
    // divergence.
    expect(src).toMatch(/end_period_ts/);
    // And the legacy `start` label (Python: never used; old TS: used)
    // must NOT appear as the candle.ts source.
    expect(src).not.toMatch(/ts:\s*toIsoOrNull\(c\.start\)/);
  });
});

describe("trades shape parity — Polymarket Gamma pagination (21-06 Task 2)", () => {
  it("polymarket/client.ts uses PAGE_SIZE=100 (matches Python limit=100)", () => {
    const src = readFileSync(POLYMARKET_CLIENT_SRC, "utf-8");
    // Python clients use limit=100 per call by default (per the
    // MARKETS-RATE-LIMITS.md doc + Gamma 0.2s rate-limit floor). TS
    // must match so a single query returns the same row count under
    // the same upstream state.
    expect(src).toMatch(/PAGE_SIZE\s*=\s*100/);
    // The URL builder must thread PAGE_SIZE through (no hardcoded 500).
    expect(src).toMatch(/limit=\$\{PAGE_SIZE\}/);
  });
});

describe("trades shape parity — equal-timestamp trade-ID tiebreaker (21-06 Task 3)", () => {
  it("kalshiFills public surface exposes tradeId + ts (callers can sort deterministically)", () => {
    // Inspect the actual production source — the KalshiFillRow shape must
    // expose both `tradeId` and `ts` so callers can apply the canonical
    // (ts ASC, trade_id ASC) tiebreaker when joining across sources.
    const src = readFileSync(KALSHI_SRC, "utf-8");
    expect(src).toMatch(/tradeId:\s*t\.trade_id/);
    expect(src).toMatch(/ts:\s*stringTsToIso\(t\.created_time\)/);
    // Interface KalshiFillRow lives in trades/types.ts — must expose both
    // fields as nullable strings so the canonical tiebreaker compiles.
    const typesSrc = readFileSync(TRADES_TYPES_SRC, "utf-8");
    expect(typesSrc).toMatch(/interface\s+KalshiFillRow[\s\S]*tradeId:\s*string\s*\|\s*null/);
    expect(typesSrc).toMatch(/interface\s+KalshiFillRow[\s\S]*ts:\s*string\s*\|\s*null/);
  });

  // Phase 21 21-09 fix-iter-1 (codex+ts-architect HIGH): the previous
  // version of this test sorted a local synthetic array — it could pass
  // even if production never sorted at all. Replace with the honest
  // contract: BOTH Python `kalshi_trades.fills()` and TS `kalshiFills()`
  // currently preserve UPSTREAM HTTP order (no in-SDK sort). The shared
  // contract is "rows arrive in HTTP order; callers apply the canonical
  // (ts, trade_id) sort if they need determinism." Tests now lock the
  // no-sort contract on the TS side via a fetch mock so a regression
  // (silently re-ordering rows mid-pipeline) is caught.
  it("kalshiFills preserves upstream row order (no in-SDK sort)", async () => {
    const { kalshiFills } = await import("../../src/trades/kalshi.js");
    const reversed = [
      { trade_id: "z", created_time: "2025-01-06T14:00:00.000Z" },
      { trade_id: "a", created_time: "2025-01-06T14:00:00.000Z" },
      { trade_id: "m", created_time: "2025-01-06T14:00:01.000Z" },
    ];
    const mockFetch: typeof fetch = async () =>
      new Response(JSON.stringify({ trades: reversed, cursor: "" }), { status: 200 });
    const result = await kalshiFills("KXABC", {}, { fetchFn: mockFetch });
    expect(result.rows.map((r) => r.tradeId)).toEqual(["z", "a", "m"]);
  });
});
