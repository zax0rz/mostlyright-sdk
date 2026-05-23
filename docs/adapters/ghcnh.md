# GHCNh (Global Historical Climatology Network — hourly)

## Overview

- **Source ID:** `ghcnh.archive`
- **Provider:** NOAA / NCEI (National Centers for Environmental Information)
- **License:** Public-domain (US federal government work)
- **Endpoint:** NCEI GHCNh PSV (pipe-separated) files
- **Catalog module:** `tradewinds.weather.catalog.ghcnh.GHCNhAdapter`
- **Fetcher module:** `tradewinds.weather._fetchers.ghcnh`
- **Parser module:** `tradewinds.weather._ghcnh` (`parse_ghcnh_row`)

GHCNh is the international + multi-decade observation backbone. Where AWC
gives ≤7 days of fresh US-only METARs and IEM gives full-depth US ASOS, GHCNh
gives global QC-accepted hourly records. It is the **lowest-priority** source
in the v0.14.1 merge (`awc=3 > iem=2 > ghcnh=1`) — used as fallback when
neither AWC nor IEM has a row for the requested `(station, observation_date)`
key. NCEI is **excluded from live priority** per CLAUDE.md ("NCEI excluded
from live due to latency").

There is no `ghcnh.live` in v0.1.0 — the only source ID is `ghcnh.archive`.
Live observation needs are served by AWC and IEM exclusively.

## Canonical Schema

Output conforms to `schema.observation.v1` with the catalog overlay columns.
The projection from raw GHCNh parser rows applies the shared SI-unit transform
(`_obs_projection.PROJECTION_SPEC`):

| Canonical column         | Source field (GHCNh PSV)             | Notes                                                  |
| ------------------------ | ------------------------------------ | ------------------------------------------------------ |
| `temp_C`                 | `Temperature` (°F → °C in parser)    | QC-accepted values only (see Gotchas)                  |
| `dewpoint_C`             | `Dew_Point_Temperature`              |                                                        |
| `wind_speed_mps`         | `Wind_Speed` (knots → m/s)           |                                                        |
| `wind_gust_mps`          | `Wind_Gust`                          | Often missing in older records (pre-2000)              |
| `wind_direction_deg`     | `Wind_Direction`                     |                                                        |
| `visibility_m`           | `Visibility` (statute miles → m)     |                                                        |
| `precipitation_mm`       | `Precipitation` (inches → mm)        | Hourly accumulation                                    |
| `pressure_hpa`           | `Sea_Level_Pressure`                 |                                                        |
| `relative_humidity_pct`  | `Relative_Humidity`                  |                                                        |
| `raw_metar`              | `remarks` / raw row                  | GHCNh isn't pure METAR — store full row text           |
| `event_time`             | parsed from `DATE` + `HOUR` (→ UTC)  | Observation valid time                                 |
| `knowledge_time`         | `event_time + 6 hours`               | `GHCNH_LAG` — archive lag, not live                    |
| `source`                 | `"ghcnh.archive"`                    | Set by `GHCNhAdapter.from_rows`                        |
| `retrieved_at`           | wall-clock UTC of fetch              | Tz-aware datetime64                                    |

## Gotchas

- **Pipe-separated, NOT tab-separated.** GHCNh files use `|` as the column
  delimiter (PSV format), despite NCEI sometimes calling them "CSV". Naive
  `pd.read_csv(... sep=",")` returns garbage. The parser uses `sep="|"`
  explicitly. Any lift / re-implementation MUST preserve this.
- **QC flag filtering.** GHCNh tags every measurement with a quality-control
  flag. The parser's `_is_qc_accepted` helper filters out non-accepted rows
  before projection — downstream callers never see QC-rejected values. This
  is the loud-by-default approach: bad data is dropped before it enters the
  merge, not silently labeled.
- **Older-record gaps.** Wind gusts, dewpoint, and visibility are often null
  in pre-2000 GHCNh records. `None` propagates through the projection — the
  Validator accepts `pd.NA` in nullable columns.
- **No live feed.** NCEI publishes GHCNh on a multi-week to multi-month
  cadence. There is no streaming or hourly-rolling GHCNh feed. Any caller
  needing live data must route through AWC or IEM.
- **6-hour archive lag.** `GHCNH_LAG = timedelta(hours=6)` is the
  `knowledge_time - event_time` overlay. This is the FLOOR — in practice
  NCEI lag is much longer (days to weeks). The 6-hour floor exists so that
  the temporal-safety primitives (`KnowledgeView`, `LeakageDetector`) treat
  the row as "not yet knowable" for at least one merge boundary cycle.
- **International coverage post-Phase 3.1.** GHCNh is the primary archive
  source for non-US Kalshi stations. The Phase 3.1 international station
  expansion routes non-CONUS stations through GHCNh (with IEM as a secondary
  for stations that happen to be in IEM's ASOS catalog).

## Timezone Handling

- GHCNh `DATE` + `HOUR` columns encode **UTC** observation times. The parser
  parses to tz-aware `datetime64[ns, UTC]` at the boundary.
- The 20 Kalshi-traded stations carry per-station IANA zones via
  `tradewinds.snapshot._STATION_TZ`. International stations added in Phase
  3.1 carry their own IANA mappings.
- DST handling: same as IEM. UTC observation times are monotonic; LST
  settlement-window math happens at the `_pairs.py` layer, not in the adapter.

## Source-Pairing Rules

- **Observation merge priority** (`_internal/merge/observations.py:SOURCE_PRIORITY`):
  - `awc=3 > iem=2 > ghcnh=1`. GHCNh contributes a row only when neither AWC
    nor IEM has one for the same `(station, observation_date)` key.
  - Tie-break is strict-`>` first-row-seen.
- **Live priority** (CLAUDE.md "LIVE_V1 observations"): GHCNh is **excluded**
  from the live merge (latency too high). AWC > IEM > GHCNh applies only to
  the historical/archive path.
- **International fallback.** For non-US stations where AWC has no coverage
  and IEM has gaps, GHCNh is often the only archive option. Source-priority
  numbers don't change, but in practice GHCNh contributes the majority of
  rows for international stations.
- **CLI cross-reference.** GHCNh does NOT serve settlement data. CLI is the
  only settlement source ([`cli.md`](cli.md)).

## Cache Layout

- On-disk path: `$HOME/.tradewinds/cache/v1/observations/{station}/{year}/{month}.parquet`
- Same path layout as AWC and IEM — observation rows from all three sources
  share the parquet file, distinguished by the `source` overlay column.
- `filelock`-guarded; SoftFileLock fallback on cloud-sync filesystems.
- Because GHCNh has no live feed, every month is treated as cacheable
  (no current-month skip rule applies — the data is already days/weeks old
  by the time it's published).

## See Also

- [`iem.md`](iem.md) — primary US archive + live fallback
- [`awc.md`](awc.md) — live observation source (US-only, ≤7d)
- [`cli.md`](cli.md) — settlement source (CLI; separate from observation merge)
- Source-of-truth code: `packages/weather/src/tradewinds/weather/catalog/ghcnh.py`
- Parser: `packages/weather/src/tradewinds/weather/_ghcnh.py`
- Fetcher: `packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py`
- Merge logic: `packages/core/src/tradewinds/_internal/merge/observations.py`
