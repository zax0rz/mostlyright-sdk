# Markets Rate-Limit Politeness Floors (TRADES-08)

Per-issuer politeness sleeps documented for the trade-history surface
landed in Phase 9. These are the **conservative floors** the SDK ships;
they trade ~10× headroom for the documented rate ceiling against a
near-zero probability of 429s in burst scenarios.

| Issuer | Endpoint family | Documented limit | Polite floor | Headroom |
|---|---|---|---|---|
| Kalshi | `/trade-api/v2/series/{s}/markets/{m}/candlesticks`, `/markets/trades`, `/markets/{t}/orderbook` | 10 req/sec (public, unauthenticated) | 100 ms (10 req/sec) | matches ceiling exactly |
| Polymarket | `gamma-api.polymarket.com/prices-history`, `gamma-api.polymarket.com/events/{id}` | not documented | 200 ms (~300 req/min) | best-effort; well below where any reasonable WAF rate-limits |

## Kalshi

Kalshi's public documentation ([api.elections.kalshi.com docs](https://docs.kalshi.com/api/))
states a 10 req/sec ceiling on unauthenticated public endpoints (the
endpoints Phase 9 uses — candlesticks, trades, orderbook). The TS +
Python clients both use a 100 ms `sleepBetweenMs` / `_REQUEST_DELAY_S`
default, plus exponential backoff on 429 (1s → 2s → 4s) and the
documented 5xx codes (500/502/503/504).

The 10 req/sec ceiling applies per IP. Multi-process callers (e.g. a
multiprocessing pool of backtests on the same host) should pass an
explicit `sleep_between` / `sleepBetweenMs` higher than 100 ms to stay
collectively below the ceiling. We do NOT add a process-wide
distributed limiter — that's caller-side coordination.

## Polymarket Gamma

The Gamma API (`gamma-api.polymarket.com`) has no documented rate
limit. The pre-existing tradewinds `_polymarket_client.py` has used a
200 ms polite floor since v0.1.0 (Phase 3.3 — Polymarket discovery +
settlement) and the Gamma edge has not 429'd in our empirical
discovery runs over the v0.1.0 → v0.2 window. Phase 9's `polymarket_trades`
inherits that floor.

Polymarket's edge is fronted by Cloudfront which returns 403 on a blank
User-Agent. The clients always set `tradewinds-sdk/0.1` (Python) or
`tradewinds-ts/0.2.0` (TS).

## Empirical rate-limit spike — deferred

The original TRADES-08 requirement called for an empirical rate-limit
spike to set politeness floors. Phase 9 explicitly **defers** the
automated spike because:

1. Running an unbounded request rate against a third-party public API
   in CI is a DoS-class action — even if our load is tiny, doing it
   from CI infrastructure is the kind of thing that triggers an IP ban
   or a stern email.
2. The conservative floors (above) match Kalshi's documented ceiling
   exactly and Polymarket's observed working point. There's no
   ergonomic gain (faster backtests) to be had at higher rates without
   adding complexity (distributed limiter, exponential-backoff tuning,
   per-endpoint specialization).
3. Phase 9's primary user is a quant running backtests sequentially —
   1-10 req/sec is more than enough for any realistic single-strategy
   workflow.

If a future user reports throughput problems, the manual operator-led
spike can be run from a single dev workstation (not CI) with a 30-min
window and clear stop conditions. Update this doc with the findings.

## v0.3 considerations

- **WebSocket streaming.** Kalshi and Polymarket both offer websocket
  feeds. Migrating from polling to streaming changes the rate-limit
  story entirely (one persistent connection vs many polled requests).
  When v0.3 wires WS, this doc should grow a "Streaming" section
  documenting reconnect / heartbeat / subscribe-burst floors per source.
- **Authenticated endpoints.** If/when tradewinds adds authenticated
  Kalshi (orders, fills with full provenance), Kalshi documents a
  separate authenticated rate limit. Add a row to the table when that
  surface ships.
- **Distributed callers.** A future hosted-mode (Phase 11+?) running
  per-tenant might need a Redis-backed token-bucket limiter to enforce
  the per-issuer ceiling across processes. Out of scope for v0.2.

---

*Last updated: 2026-05-25 (Phase 9 closeout)*
