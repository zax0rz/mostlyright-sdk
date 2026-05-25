# Live streaming — `mostlyright.live.stream()` / `live.latest()`

`mostlyright.live` is the **ticker** surface. Use it when you want a live
feed of fresh METARs from a single weather source — for dashboards, alerting,
or any program that polls and reacts in real time. It is intentionally
different from `mostlyright.research()`, which is the **database** surface.

Both Python and TypeScript SDKs ship the same two surfaces with mirrored
APIs.

## 1. Overview — `live.stream()` vs `research()`

| | `research()` | `live.stream()` / `live.latest()` |
|---|---|---|
| Role | DATABASE (training pairs, settlement) | TICKER (real-time monitoring) |
| Sources | AWC + IEM + GHCNh + CLI (fused) | ONE of `awc` \| `iem` |
| Cache writes | Yes (parquet, year-aligned) | No |
| QC | Yes (Phase 3.4) | No |
| Loop semantics | None — point-in-time | Async generator |
| Use case | Backtest, train a model, settle a contract | Watch live conditions, page on threshold, build a dashboard |

If you reach for `live.stream()`, you almost certainly do NOT want
multi-source fusion: a single feed lets you reason about the latency
of "what AWC said at 12:01" without IEM's ~10-min delay smearing the
picture. If you need fused data, use `research()` instead.

## 2. API — `live.stream()`

```python
# Python
import asyncio
import mostlyright

async def main() -> None:
    async for row in mostlyright.live.stream("KNYC"):
        print(row["observed_at"], row["temp_f"])

asyncio.run(main())
```

```ts
// TypeScript
import { stream } from "@mostlyright/weather";

for await (const row of stream("KNYC")) {
  console.log(row.observed_at, row.temp_f);
}
```

**Signature:**

- Python: `mostlyright.live.stream(station, *, source=None, poll_seconds=None) -> AsyncIterator[dict]`
- TS: `stream(station: string, opts?: { source?, pollSeconds?, signal? }): AsyncGenerator<LiveObservation>`

**Per-row contract:**

- Same shape as the canonical `Observation` schema (`station_code`,
  `observed_at` ISO-8601 UTC, `observation_type` METAR/SPECI, plus weather
  fields).
- `source` is the live identity tag: `"awc.live"` or `"iem.live"`.
- Duplicate emission is suppressed: the generator yields a row only when
  its `observed_at` differs from the previously-yielded one. AWC and IEM
  both serve "the latest METAR" repeatedly between observation cycles —
  deduping by `observed_at` collapses that noise.

## 3. API — `live.latest()`

```python
# Python — one shot
row = await mostlyright.live.latest("KNYC")
print(row["temp_f"])
```

```ts
// TypeScript — one shot
const row = await latest("KNYC");
console.log(row.temp_f);
```

**Signature:**

- Python: `mostlyright.live.latest(station, *, source=None) -> dict`
- TS: `latest(station: string, opts?: { source? }): Promise<LiveObservation>`

`latest()` shares the per-tick fetch path with `stream()` but returns
exactly once. Use it from cron-style schedulers, or when you want a
single fresh observation without managing an async generator's lifecycle.

Unlike `stream()`, `latest()` raises `NoLiveDataError` when the upstream
returned no observations (empty list, network failure, etc.). The error's
`to_dict()` (Python) / `toDict()` (TS) payload includes the resolved
`station` and the `source` identity tag so caller logs can branch.

## 4. Sources

| Source | Default? | Endpoint | Typical latency | Use when |
|---|---|---|---|---|
| `"awc"` | yes | `aviationweather.gov/api/data/metar` | <1 minute | Default — lowest latency for live METARs |
| `"iem"` | no | `mesonet.agron.iastate.edu/cgi-bin/request/asos.py` | ~5–10 minutes | AWC is down, or you want a cross-check against an independent provider |

Each row carries its source identity on the `source` field:

- AWC rows: `source == "awc.live"`
- IEM rows: `source == "iem.live"`

The `.live` suffix distinguishes these from the archive-channel tags
(`"awc"` / `"iem"`) emitted by `research()` and the historical fetchers.
If a downstream consumer cares about the channel, branching on
`row["source"].endswith(".live")` is the documented public contract.

## 5. Polite floors

`mostlyright.live` will not let you poll an upstream API faster than its
polite floor:

| Source | Floor (seconds) |
|---|---|
| `awc` | 30 |
| `iem` | 60 |

Calls to `stream(..., poll_seconds=10)` for an AWC stream raise
`ValueError("poll_seconds=10 below polite floor 30s for source='awc'")`
**before the first poll** — fail fast. Omitting `poll_seconds=` uses
the floor.

The floor exists for two reasons:

1. **Politeness.** Both endpoints are public goods. AWC has no documented
   rate limit; IEM is a university server with explicit ask for headroom
   above 1 req/s.
2. **Useful signal.** METARs are issued at roughly hourly cadence
   (SPECI specials are intra-hour). Polling faster than ~30s does not
   surface new data on most stations — it just costs bandwidth.

## 6. Async patterns

### Python

```python
# Standard `async for` consume
async for row in mostlyright.live.stream("KNYC"):
    process(row)

# Break out cleanly — the polite-floor sleep is `asyncio.sleep`, which
# propagates `CancelledError`, so `break` exits without zombie tasks.
async for row in mostlyright.live.stream("KNYC"):
    process(row)
    if row["temp_f"] > 95:
        break

# Run multiple stations in parallel — one task per station, polite
# floors apply per-task (NOT pooled).
async def watch(station: str) -> None:
    async for row in mostlyright.live.stream(station):
        process(station, row)

await asyncio.gather(watch("KNYC"), watch("KLAX"), watch("KORD"))
```

### TypeScript

```ts
// Standard `for await` consume
for await (const row of stream("KNYC")) {
  process(row);
}

// Abort via an external `AbortSignal` — interrupts the polite-floor
// sleep promptly without waiting out the cadence.
const controller = new AbortController();
setTimeout(() => controller.abort(), 60_000); // stop after a minute

for await (const row of stream("KNYC", { signal: controller.signal })) {
  process(row);
}

// Multi-station fan-out
await Promise.all(
  ["KNYC", "KLAX", "KORD"].map(async (station) => {
    for await (const row of stream(station)) {
      process(station, row);
    }
  }),
);
```

## 7. FAQ

**Q. Can I write live rows to the parquet cache?**
No. `live.stream()` never writes to disk. If you want a durable
back-of-tape, call `research()` separately — that's its job.

**Q. Can I fuse AWC and IEM?**
Not in this surface — it's intentionally single-source. Use `research()`
for fused output. If you really want both channels live, run two
`stream()` tasks in parallel (`asyncio.gather` in Python,
`Promise.all` in TS) and join them yourself.

**Q. What if my `poll_seconds` is below the polite floor?**
`ValueError` is raised **before the first poll** with the floor and source
named in the message. Streaming fails fast — there's no first-tick edge
case to debug.

**Q. What if the upstream is down for a tick?**
`stream()` swallows the per-tick error and waits for the next polite-floor
cycle. Logs are emitted via the SDK logger but the generator keeps running.
If you want a hard failure on empty/error responses, use `latest()`
(it raises `NoLiveDataError`).

**Q. Can a row's `observed_at` arrive out of order?**
In practice no — METAR `observed_at` is monotonic per station. The
dedup invariant compares by string equality (`current != last_observed_at`),
so even if the upstream re-serves an OLDER METAR for some reason, that
row would still be emitted on the first occurrence (since it differs from
the previously-yielded one). The first-occurrence semantics match
`research()`'s strict-priority merge.

**Q. How do I tag rows for downstream join with `research()`?**
The `source` field is the channel-aware key: `"awc.live"` rows from
`live.stream()` will never collide with `"awc"` archive rows from
`research()`. If you join, do it on `(station_code, observed_at)` and
keep `source` for provenance.

## Usage patterns

### Continuous monitoring

```python
import asyncio
import mostlyright

async def alert_when_hot(station: str, threshold_f: float) -> None:
    async for row in mostlyright.live.stream(station):
        if row["temp_f"] and row["temp_f"] >= threshold_f:
            await page(f"{station} hit {row['temp_f']}F at {row['observed_at']}")

asyncio.run(alert_when_hot("KNYC", 95.0))
```

### Single-shot poll (cron-style)

```python
# Run from cron every 5 minutes, get one fresh row per invocation.
import asyncio
import mostlyright

async def main() -> None:
    try:
        row = await mostlyright.live.latest("KNYC")
        write_row_to_db(row)
    except mostlyright.live.NoLiveDataError as e:
        log.warning("no live data: %s", e.to_dict())

asyncio.run(main())
```

### Multi-station fan-out

```ts
// Watch every Kalshi NHIGH-NY ICAO in parallel — one stream per station.
import { stream } from "@mostlyright/weather";

const stations = ["KNYC", "KLGA", "KJFK", "KEWR"];

await Promise.all(
  stations.map(async (station) => {
    for await (const row of stream(station, { source: "awc" })) {
      console.log(station, row.observed_at, row.temp_f);
    }
  }),
);
```
