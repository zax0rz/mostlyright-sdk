# Climate Gaps (TypeScript lane — v1.x deferral)

`climateGaps()` in `@mostlyrightmd/core/discovery` is **not implemented** in
v1.x of the TypeScript SDK. Calling it raises
`DataAvailabilityError(reason="model_unavailable")` (Phase 21 21-09) with a
structured hint pointing here.

This is a deliberate v1.x deferral driven by hard infrastructure constraints,
not a missing feature. The Python SDK ships the full surface against its
local parquet cache.

## What `climateGaps()` does (Python SDK)

Returns the list of date ranges where GHCNh climate data is missing for a
station's window. Useful for backtest setup: identify where the climate
signal is sparse, decide whether to interpolate, drop, or fail-loudly.

```python
from mostlyright.discover import climate_gaps

gaps = climate_gaps("KNYC", "2020-01-01", "2025-01-01")
# [{"start": "2020-03-14", "end": "2020-04-01"}, ...]
```

## Why not in TypeScript v1.x

Three architectural constraints make the browser/Node path impractical for
v1.x — all three would need to change before a parity port becomes feasible:

1. **GHCNh CSVs are 10+ MB per station-year.** A 5-year backfill is 50+ MB
   per station; multi-station portfolio queries hit hundreds of MB. The
   payload is too big to ship over a bare browser fetch on every call.

2. **Browser fetch doesn't slice.** GHCNh's CSV endpoint has no HTTP `Range`
   support; the whole file pulls per call. Mobile and low-bandwidth users
   exit the SDK as bad-citizen behavior. Server-side ingest could pre-slice,
   but that means we'd be running a hosted service — which is explicitly
   out of scope for the local-first SDK in v1.x.

3. **Cache layer doesn't scale.** IndexedDB has per-origin storage quotas
   (typically ≤2 GB before browser eviction); the working set for a quant
   backtest commonly exceeds that. The Node FS cache works for bandwidth
   savings but doesn't solve the per-call download problem the first time
   a station-year is touched.

The right design is a **hosted climate-gap-precompute API** that serves
small JSON responses keyed by `(station, window)` — this ships post-v1.x
as part of the broader hosted-cache initiative. Until then,
`climateGaps()` raises with a typed exception so consumers can branch on
`reason === "model_unavailable"` instead of string-matching the message.

## Workaround for v1.x

**Use the Python SDK.** It ships the full surface against the local parquet
cache:

```python
from mostlyright.discover import climate_gaps
gaps = climate_gaps("KNYC", "2020-01-01", "2025-01-01")
```

The cross-language gap is documented and intentional. For production TS
code that needs this surface, bridging via subprocess shell-out or a small
internal Python microservice is appropriate.

## Catching the error

The function raises `ClimateGapsNotImplementedError` (a subclass of
`DataAvailabilityError`). Catch either:

```typescript
import {
  climateGaps,
  ClimateGapsNotImplementedError,
} from "@mostlyrightmd/core/discovery";
import { DataAvailabilityError } from "@mostlyrightmd/core";

try {
  climateGaps("KNYC", "2020-01-01", "2025-01-01");
} catch (e) {
  if (e instanceof DataAvailabilityError && e.reason === "model_unavailable") {
    // Fall back to the Python SDK or skip the climate-gap step.
    console.warn("[climateGaps] not available in TS v1.x:", e.hint);
  }
}
```

New code should prefer catching `DataAvailabilityError` and dispatching on
`reason` — that pattern survives the eventual TS-side implementation
without code changes.

## Tracking

- **[Phase 21 D-08](../.planning/phases/21-typescript-sdk-parity-completion/21-CONTEXT.md)** —
  this deferral, locked decision in the Phase 21 planning round.
- Hosted climate-gap-precompute API design + scoping ships post-v1.x.

---

*See also: [forecasts.md](./forecasts.md#typescript-lane) for the parallel
deferral on `forecastNwp()`.*
