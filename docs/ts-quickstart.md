# TypeScript SDK quickstart (`@tradewinds/*`)

The TS SDK mirrors the Python public surface and ships four npm packages:

| npm | Path | Use case |
|---|---|---|
| [`@tradewinds/core`](../packages-ts/core/) | core types, schemas, temporal/QC primitives, formats | every consumer |
| [`@tradewinds/weather`](../packages-ts/weather/) | AWC/IEM/GHCNh/CLI fetchers + parsers | observations + climate |
| [`@tradewinds/markets`](../packages-ts/markets/) | Kalshi NHIGH/NLOW + Polymarket discover/settle | settlement logic |
| [`tradewinds`](../packages-ts/meta/) | meta convenience re-export | full-SDK import |

Five-minute path: **Node** + **browser** below. The browser path is for service workers / content scripts in extensions or web apps; the Node path is for scripts, backtests, Workers, and Bun/Deno.

## Node (and Bun / Deno) — Mode 1 parity

```bash
npm install @tradewinds/core @tradewinds/weather @tradewinds/markets
# OR
npm install tradewinds   # meta convenience: re-exports the three scoped packages
```

```ts
import { research } from "tradewinds";

const rows = await research("KNYC", "2025-01-06", "2025-01-12");
console.log(rows[0]);
// {
//   date: "2025-01-06",
//   station: "NYC",
//   cli_high_f: 38, cli_low_f: 25,
//   obs_high_f: 37, obs_low_f: 23,
//   obs_high_at: "2025-01-06T17:51:00Z",
//   obs_low_at: "2025-01-06T06:51:00Z",
//   ...
// }
```

`research(station, fromDate, toDate)` returns the same 20-column shape Python emits — byte-equivalent on the 5 canonical parity fixtures.

## Cache

The TS SDK caches AWC observations + IEM CLI + IEM ASOS + GHCNh under `$HOME/.tradewinds/cache-ts/` (Node), browser IndexedDB at `tradewinds-cache-v1` (browser), or in-memory (Workers / no-storage runtimes). Auto-detection picks the right store for the runtime; override via the `cache` option on `research()` if needed.

```ts
import { defaultCacheStore, MemoryStore } from "@tradewinds/core/internal/cache";

const cache = new MemoryStore(); // ephemeral; useful for tests
await research("KNYC", "2025-01-06", "2025-01-12", { cache });
```

## Polymarket discover + settle

Polymarket lives at the [`@tradewinds/markets/polymarket`](../packages-ts/markets/src/polymarket/) subpath — server-side only (CORS-blocked from browsers per [`.planning/research/TS-CORS-MATRIX.md`](../.planning/research/TS-CORS-MATRIX.md)).

```ts
import { polymarketDiscover, polymarketSettle } from "@tradewinds/markets/polymarket";

// Discover active weather events.
const events = await polymarketDiscover();
console.log(`${events.length} events; ${events.filter(e => e.icao).length} resolvable`);

// Settle a known event. Caller supplies the observation loader (typically a
// cache reader) — the engine pulls daily extremes from internationalDailyExtremes.
const result = await polymarketSettle({
  event: events[0]!,
  loader: async ({ icao, fromDate, toDate }) => {
    // Return observation rows for the station between fromDate and toDate.
    return [];
  },
});
console.log(result);
// {
//   eventId: "...",
//   settlementDate: "2026-05-23",
//   icao: "EGLL",
//   measure: "high",
//   resolvedValue: 30,           // native unit (C for international, F for US)
//   resolvedValueC: 30,
//   resolvedValueF: 86,
//   unit: "celsius",
//   resolutionSourceType: "noaa_wrh",
//   dataQualityAlert: null,
// }
```

Security defenses: UUID-ish event-id regex, 16 KB description cap, netloc allowlist (`wunderground.com`, `weather.gov`). All enforced before any HTTP fetch.

## Kalshi resolver helper

```ts
import { kalshiSettlementFor } from "@tradewinds/markets";

const r = kalshiSettlementFor("KHIGHNYC", "2025-01-06");
// { settlementSource: "cli.archive", settlementStation: "KNYC",
//   cityTicker: "NYC", contractDate: "2025-01-06" }
```

## Discovery surface

```ts
import {
  availability,
  internationalDailyExtremes,
  buildSnapshot,
  dataVersionForResearch,
  describe,
  featureCatalog,
} from "@tradewinds/core/discovery";
import { MemoryStore } from "@tradewinds/core/internal/cache";

const cache = new MemoryStore();
const a = await availability("KNYC", cache);
console.log(a);
// { station: "NYC", monthsCached: 0, firstMonth: null, ... }

console.log(describe("schema.observation.v1"));
console.log(featureCatalog());
// ["calendarFeatures", "clipOutliers", "diff", "diff2", "heatIndex", ...]
```

## Browser quickstart

See [`docs/browser-integration.md`](./browser-integration.md) for service-worker / content-script integration and the [in-repo Chrome extension example](../packages-ts/examples/chrome-extension-mvp/).

## What's NOT shipped in v0.1.0

Mirrors Python v0.1.0 deferrals:

- Polymarket order book / fills (Sprint 0.5+).
- UMA oracle on-chain validation.
- Taipei / HK-low markets (raise `DeferredMarketError`; CWA/HKO clients are v0.2).
- Live HRRR/GFS/NBM forecast fetch (Python ships the dispatch seam; live wiring is v0.2).
- Climate-gap scanning (`climateGaps` throws `ClimateGapsNotImplementedError`; v0.2).

## API stability

- `@tradewinds/core`: public functions stable at v0.1.0; new exports MUST land at SUBPATH entries to preserve the 25 KB main-bundle gate (see [`packages-ts/core/src/index.ts`](../packages-ts/core/src/index.ts) header).
- Schema generated types (`@tradewinds/core/src/schemas/generated/*`) are codegen output; do NOT hand-edit.
- Result shapes (`ResearchRow`, `DailyExtreme`, `PolymarketSettlementResult`) follow [`PYTHON-SURFACE-INVENTORY.md`](../.planning/research/PYTHON-SURFACE-INVENTORY.md). Drift triggers a parity ticket per [`CROSS-SDK-SYNC.md`](../.planning/CROSS-SDK-SYNC.md).
