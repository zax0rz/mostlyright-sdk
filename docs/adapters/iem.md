# IEM (Iowa Environmental Mesonet)

## Overview

- **Source IDs:** `iem.archive`, `iem.live`
- **Provider:** Iowa State University — Iowa Environmental Mesonet (ASOS archive + CLI JSON mirror)
- **License:** Public-domain weather data (NWS originator; IEM hosts and reformats)
- **Endpoints:**
  - ASOS observations: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`
  - CLI JSON mirror: `https://mesonet.agron.iastate.edu/json/cli.py?station={icao}&year={year}`
- **Catalog module:** `tradewinds.weather.catalog.iem.IEMAdapter`
- **Fetcher modules:** `tradewinds.weather._fetchers.iem_asos`, `tradewinds.weather._fetchers.iem_cli`
- **Parser module:** `tradewinds.weather._iem` (METAR/SPECI rows → canonical observation rows)

IEM is the historical-depth backbone of the v0.1.0 observation merge. Where AWC
gives us the freshest live METAR (US-only, ≤7 days deep) and GHCNh gives us
international + multi-decade coverage, IEM provides the archive that holds
v0.14.1 parity together — `iem.archive` is the dominant source on the 5 frozen
parity fixtures.

IEM also hosts a JSON mirror of NWS CLI text products at `cli.py`. The DATA in
those rows is the NWS Climate product (settlement source for Kalshi NHIGH/NLOW);
the TRANSPORT is IEM. See [`cli.md`](cli.md) for the settlement product itself.

## Canonical Schema

Output conforms to `schema.observation.v1` with the catalog overlay columns.
The projection from raw IEM parser rows applies the shared SI-unit transform
(`_obs_projection.PROJECTION_SPEC`):

| Canonical column         | Source field (raw METAR / IEM)     | Notes                                                   |
| ------------------------ | ---------------------------------- | ------------------------------------------------------- |
| `temp_C`                 | `tmpf` (°F → °C)                   | `M` sentinel maps to `None` before projection           |
| `dewpoint_C`             | `dwpf` (°F → °C)                   |                                                         |
| `wind_speed_mps`         | `sknt` (knots → m/s)               |                                                         |
| `wind_gust_mps`          | `gust` (knots → m/s)               | `None` when no gust group in METAR                      |
| `wind_direction_deg`     | `drct`                             | Integer degrees from true north                         |
| `visibility_m`           | `vsby` (statute miles → metres)    |                                                         |
| `precipitation_mm`       | `p01i` (inches → mm)               | 1-hour precipitation                                    |
| `pressure_hpa`           | `mslp` or `alti` (inHg → hPa)      |                                                         |
| `relative_humidity_pct`  | `relh`                             |                                                         |
| `cloud_ceiling_m`        | derived from cloud groups (ft → m) |                                                         |
| `raw_metar`              | `metar`                            | Preserved verbatim per CLAUDE.md (MetPy re-parse seam)  |
| `event_time`             | `valid` (parsed to UTC datetime64) | Observation valid time                                  |
| `knowledge_time`         | `event_time + 15 min`              | METAR/SPECI broadcast lag (`IEM_METAR_LAG`)             |
| `source`                 | `"iem.archive"` or `"iem.live"`    | Set by `IEMAdapter.from_rows`                           |
| `retrieved_at`           | wall-clock UTC of the fetch        | Tz-aware datetime64                                     |

The `_v02` / Phase 2 `core.formats.dataframe` serializer roundtrips these rows
losslessly through parquet, JSON, and TOON.

## Gotchas

- **`M` sentinel.** IEM's textual ASOS endpoint emits `M` for missing values.
  The parser converts `M` to `None` (not `0`, not `np.nan`). The projection
  preserves `None` through unit conversion — downstream callers see `pd.NA` /
  `None` in the canonical DataFrame, never a silent zero. (CLAUDE.md Pitfall 8.)
- **Year-spanning queries.** The ASOS endpoint streams CSV row-by-row; very
  long ranges have rare row drops on server-side timeouts. The Phase 1.5 PERF-04
  fix in `_fetchers/iem_asos.py` chunks any request whose span > 365 days into
  per-year sub-requests via `_iem_chunks.py`. Callers above the fetcher (e.g.
  `research()` callers requesting decade-long ranges) never see partial rows.
- **Rate limit / etiquette.** IEM publishes no formal rate limit but the
  community convention is ≤1 req/sec from a single IP. Concurrent fetches in
  `research()`'s Phase 1.5 PERF-04 fan-out are bounded by the four-source
  parallelism (one IEM ASOS request + one IEM CLI request at most simultaneously);
  no further throttling needed for v0.1.
- **Two source IDs, same parser.** `iem.archive` and `iem.live` use the same
  `iem_to_observation` parser. The split exists for Validator dispatch and
  cache-residency policy — `*.live` is the current-month staging cache window
  (skipped from `parquet.gz` cache), `*.archive` is the closed-month frozen
  cache. There is no parser-level difference in v0.1.
- **MOS forecast leg deferred.** `IEMAdapter.fetch_forecasts()` raises
  `NotImplementedError` in v0.1. IEM does serve MOS at
  `mesonet.agron.iastate.edu/json/mos.py`, but the forecast leg lands in
  Phase 3.2 (multi-forecast HRRR + GFS + NBM via NOAA BDP).

## Timezone Handling

- IEM ASOS returns the `valid` column in **UTC** as an ISO string. The parser
  parses to a tz-aware `datetime64[ns, UTC]` immediately at the boundary.
- The CLI JSON mirror returns local-date strings for `observation_date` — those
  do NOT carry tz info. Settlement-window math is delegated to
  `tradewinds.snapshot.settlement_date_for(observed_at, station_code,
  tz_override=...)`, which uses the per-station IANA zone (`_STATION_TZ` for
  the 20 Kalshi-traded stations).
- DST boundaries: ASOS valid times never shift (UTC is monotonic). Settlement
  dates DO shift on DST days — handled at the settlement-window join in
  `_pairs.py`, not in the adapter.

## Source-Pairing Rules

- **Observation merge priority** (`_internal/merge/observations.py:SOURCE_PRIORITY`):
  - `awc=3 > iem=2 > ghcnh=1`
  - IEM wins over GHCNh whenever both have a row for the same `(station,
    observation_date)` key; AWC wins over IEM on the same key.
  - Tie-break is strict-`>` first-row-seen (lifted byte-for-byte from
    `monorepo-v0.14.1/pairs.py`).
- **Live priority** (CLAUDE.md "LIVE_V1 observations"): AWC > IEM > GHCNh.
  IEM is the live fallback when AWC has a gap (e.g. station temporarily
  out-of-feed). NCEI is excluded from live priority due to latency.
- **CLI cross-reference.** IEM hosts the CLI JSON mirror but the CLI DATA is
  the NWS Climate product. Read [`cli.md`](cli.md) for the settlement-source
  semantics; IEM is just the transport.

## Cache Layout

- On-disk path: `$HOME/.tradewinds/cache/v1/observations/{station}/{year}/{month}.parquet`
- `filelock`-guarded per-file (cross-process safe). Phase 1.5 PERF-04 added an
  iCloud/Dropbox auto-detect — cloud-sync filesystems fall back to `SoftFileLock`.
- Cache-skip rules:
  - Current LST month for that station is never written (still volatile —
    final report types may arrive in correction passes).
  - `*.live` source IDs are never cached.
  - Closed months are immutable — re-fetches read from parquet without
    touching the network.

## See Also

- [`awc.md`](awc.md) — live-priority observation source (US-only, ≤7d)
- [`cli.md`](cli.md) — settlement source (NWS CLI via IEM JSON mirror)
- [`ghcnh.md`](ghcnh.md) — international + multi-decade fallback
- Source-of-truth code: `packages/weather/src/tradewinds/weather/catalog/iem.py`
- Merge logic: `packages/core/src/tradewinds/_internal/merge/observations.py`
- Phase 1.5 PERF-04 chunker: `packages/weather/src/tradewinds/weather/_fetchers/_iem_chunks.py`
