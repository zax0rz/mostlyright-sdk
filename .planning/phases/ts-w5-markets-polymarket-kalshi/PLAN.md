# Phase TS-W5 — Markets (Polymarket Live + Kalshi Wiring)

**Status:** Stub (run `/gsd-plan-phase ts-w5`).
**Milestone:** TypeScript v0.1.0
**Lane:** Rob
**Depends on:** Phase TS-W4 (transforms surface + Mode 2 dispatch) AND Phase TS-W6 (`internationalDailyExtremes` from TS-INTL-01 is consumed by `polymarketSettle`) AND Python Phase 3.1 INTL-02 (the Group B gated codegen output `schemas/polymarket-city-stations.json` must be populated for Wave 2's Tier 3 catalog resolver). **Strictly serial after TS-W6 — NOT parallel.** Earlier "Parallel with TS-W6" claim was wrong: TS-POLY-03 reads `internationalDailyExtremes()` (TS-INTL-01 / TS-W6) as the resolution source, so TS-W5 Wave 4 cannot compile against W6 deliverables that haven't shipped.

## Goal

Activate Polymarket discover/settle in TS (Python v0.1.0 ships only boundary stubs with `NotImplementedError`; the substantive engine lives in TS, not Python). Maintain Python's security defenses verbatim — UUID4 regex, 16 KB description cap, netloc allowlist. Wire Kalshi resolver into a higher-level helper for the Chrome extension's overlay use case.

## Requirements

- TS-MARKETS-01 already shipped in TS-W1; this phase adds:
- TS-MARKETS-02 (`kalshiSettlementFor` higher-level helper)
- TS-POLY-01 (Polymarket Gamma client)
- TS-POLY-02 (discover + Tier 0/1/2/3 resolver)
- TS-POLY-03 (settle engine + security defenses)

## Success Criteria

1. `PolymarketClient` over `https://gamma-api.polymarket.com`: User-Agent header required (Cloudfront 403s on blank UA), 0.2s rate limit, 429+5xx retries, pagination by `offset += 100` up to 10000 events, dedup by slug. Ports Python Sprint 2t s1+s4 client.
2. `polymarketDiscover()` against live Gamma API returns ≥ 50 active weather events end-to-end. Tier 0 deferred-station check raises `DeferredMarketError` for Taipei/HK-lowest. Tier 1 `resolutionSource` URL match on Wunderground/NOAA WRH. Tier 2 description URL match. Tier 3 catalog fallback via `resolveStationForEvent` using codegen `schemas/polymarket-city-stations.json`. Drops 11 US slugs already covered by US station registry.
3. `polymarketSettle(eventId, opts?)` enforces UUID4 regex on `eventId` (rejects non-UUID), 16 KB description cap (`PayloadTooLargeError`), netloc allowlist (`wunderground.com`, `weather.gov` + `www.` variants).
4. Settlement engine reads `internationalDailyExtremes()` (TS-INTL-01 / TS-W6) for the resolution source, applies half-up rounding to whole-degree-native. Verified against a **fixture set of ≥5 historically-resolved Polymarket weather events** with `{eventId, expectedBucket, expectedValue, polymarketPublishedValue}` — NOT against Python `polymarket_settle` (which is `NotImplementedError` in v0.1.0). ±1°F / 0.6°C diff vs `polymarketPublishedValue` emits `dataQualityAlert` (does NOT throw). `TooEarlyToSettleError` raised when source-specific finalization delay hasn't elapsed (Wunderground 6h, NOAA WRH 4h, default 24h).
5. `kalshiSettlementFor(contractId, date)` (TS-MARKETS-02) higher-level helper returns `{settlementSource, settlementStation, cityTicker, contractDate}` — dispatch by prefix (`KHIGH*` → NHIGH resolver, `KLOW*` → NLOW resolver). Used by Chrome extension overlay.

## Waves

- **Wave 1**: `PolymarketClient` (rate limit, retry, paginator).
- **Wave 2**: Tier 0/1/2/3 resolver chain + city catalog (`polymarket_city_stations.json` from codegen).
- **Wave 3**: `polymarketDiscover()` end-to-end live test against Gamma API.
- **Wave 4**: `polymarketSettle()` engine — UUID4/16KB/netloc allowlist defenses (negative tests), half-up rounding, finalization-delay logic.
- **Wave 5**: `kalshiSettlementFor` higher-level helper + Chrome extension integration example.

## Security review

URL-parsing logic is security-adjacent — resolution-source URLs come from untrusted Polymarket event descriptions. Codex pass must verify strict netloc allowlist + 16 KB cap + UUID4 regex are all enforced, with negative tests.

## Out of Scope

- Polymarket order book / fills / paid market data (stays deferred — Sprint 0.5+ in Python; same posture in TS).
- UMA Oracle on-chain validation (Polymarket's own settlement mechanism).
- Taipei + HK-lowest markets (require CWA + HKO clients; deferred).
- Persistent settlement-record JSON (settlements compute on-demand; no `settlements_ledger/` table).
