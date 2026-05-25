# AWC (Aviation Weather Center)

## Overview

- **Source ID:** `awc.live`
- **Provider:** NOAA Aviation Weather Center
- **License:** Public-domain (US federal government work)
- **Endpoint:** `https://aviationweather.gov/api/data/metar`
- **Catalog module:** `mostlyright.weather.catalog.awc.AWCAdapter`
- **Fetcher module:** `mostlyright.weather._fetchers.awc`
- **Parser module:** `mostlyright.weather._awc` (`awc_to_observation`)

AWC is the freshest observation source in the v0.1.0 catalog (~5-minute lag
versus IEM's ~15-minute METAR broadcast lag). It is the **highest-priority**
LIVE_V1 source (`awc=3 > iem=2 > ghcnh=1`) and is the default the four-source
fan-out warms before the sequential assembly in `research()`.

There is **no `awc.archive`** in v0.1.0. AWC's public endpoint exposes only a
rolling ~7-day window — historical depth is IEM's job. See the gotchas below
for the endpoint migration and the 168-hour ceiling that drive this constraint.

## Canonical Schema

Output conforms to `schema.observation.v1` with the catalog overlay columns.
The projection from raw AWC parser rows applies the shared SI-unit transform
(`_obs_projection.PROJECTION_SPEC`):

| Canonical column        | Source field (AWC JSON)            | Notes                                                  |
| ----------------------- | ---------------------------------- | ------------------------------------------------------ |
| `temp_C`                | `temp`                             | AWC returns °C natively                                |
| `dewpoint_C`            | `dewp`                             |                                                        |
| `wind_speed_mps`        | `wspd` (knots → m/s)               |                                                        |
| `wind_gust_mps`         | `wgst` (knots → m/s)               | `None` when not reported                               |
| `wind_direction_deg`    | `wdir`                             | Variable winds encoded as `"VRB"` → `None`             |
| `visibility_m`          | `visib` (statute miles → metres)   | `M1/4` prefix = "below 1/4 mile" — see Gotchas         |
| `altim_hpa`             | `altim`                            |                                                        |
| `raw_metar`             | `rawOb`                            | Preserved verbatim per CLAUDE.md (MetPy re-parse seam) |
| `event_time`            | `obsTime` (epoch seconds → UTC)    | Observation valid time, tz-aware UTC                   |
| `knowledge_time`        | `event_time + 5 min`               | `AWC_LAG` — AWC pushes to its API immediately          |
| `source`                | `"awc.live"`                       | Set by `AWCAdapter.from_rows`                          |
| `retrieved_at`          | wall-clock UTC of the fetch        | Tz-aware datetime64                                    |

## Gotchas

- **Sept 2025 endpoint migration.** AWC retired the legacy CGI endpoint
  `aviationweather.gov/cgi-bin/data/metar.php` in September 2025. The fetcher
  in `_fetchers/awc.py` uses the replacement REST endpoint
  `aviationweather.gov/api/data/metar`. Code that still references the old
  URL silently returns empty lists (no 404 — the CGI is deprovisioned). Any
  lift from older mostlyright snapshots MUST update this URL.
- **168-hour ceiling.** The `hours=` query parameter is capped at ~168 (7
  days). Values above are accepted but the endpoint silently truncates
  server-side — `AWC_MAX_HOURS = 168` documents the constraint. For history,
  use IEM (see [`iem.md`](iem.md)).
- **US-CONUS coverage only.** AWC's METAR JSON feed covers ICAO codes in the
  CONUS + Alaska + Hawaii. International stations return empty lists. The
  Phase 3.1 international station expansion routes non-US Kalshi stations
  through IEM/GHCNh exclusively.
- **`M1/4` visibility prefix.** AWC encodes "below 1/4 statute mile" as the
  string `"M1/4"`. The parser in `_awc.py` line 82 handles the `M` prefix
  before fraction parsing — without that branch, the fraction parse would
  fall through to `None` and the row would lose visibility provenance.
- **5xx retries.** The fetcher retries 5xx responses with exponential backoff
  (`BASE_DELAY → 2*BASE_DELAY → …`, `MAX_RETRIES` attempts total). 4xx is
  treated as a permanent client error (malformed station list, etc.) and
  returns an empty list immediately. Network errors and non-list JSON bodies
  also return empty lists after retries — never raise to the caller.

## Timezone Handling

- AWC returns `obsTime` as **epoch seconds** (UTC monotonic). The parser
  converts to tz-aware `datetime64[ns, UTC]` at the boundary.
- AWC's `reportTime` is also UTC but is the report-issued time, not the
  observation valid time. v0.1 uses `obsTime` exclusively for `event_time`.
- Settlement-date math: same as IEM. Settlement dates are LST per the
  Kalshi-traded station's IANA zone, derived from
  `mostlyright.snapshot.settlement_date_for(obs_time, station_code)`.
- DST boundaries do not affect UTC timestamps; the LST settlement-window
  join in `_pairs.py` is the layer that handles DST.

## Source-Pairing Rules

- **Observation merge priority** (`_internal/merge/observations.py:SOURCE_PRIORITY`):
  - `awc=3 > iem=2 > ghcnh=1`. AWC wins whenever it has a row for the same
    `(station, observation_date)` key.
  - Tie-break is strict-`>` first-row-seen.
- **Live priority** (CLAUDE.md "LIVE_V1 observations"): AWC > IEM > GHCNh.
  AWC is the default live source.
- **Geographic constraint.** AWC contributes rows only for US-CONUS / AK / HI
  Kalshi-traded stations. For international stations (Phase 3.1 expansion),
  the merge skips the AWC leg entirely — IEM and GHCNh carry the load.
- **No archive overlap with IEM.** Because there is no `awc.archive`, IEM
  alone provides observation history beyond ~7 days. The merge logic does
  NOT need a tie-break rule for AWC archive rows — they cannot exist.

## Cache Layout

- On-disk path: `$HOME/.mostlyright/cache/v1/observations/{station}/{year}/{month}.parquet`
- AWC rows are cached on the closed-month boundary alongside IEM and GHCNh
  rows (per-source dedup happens at merge time, not cache time).
- `awc.live` is never written to disk in the current LST month — current-month
  rows live only in the in-memory pre-fetch path. Closed months are immutable.
- `filelock`-guarded per parquet file. Cloud-sync filesystems use
  `SoftFileLock` fallback (Phase 1.5 PERF-04).

## See Also

- [`iem.md`](iem.md) — observation archive + live fallback when AWC has gaps
- [`cli.md`](cli.md) — settlement source (CLI is the daily extremes layer)
- [`ghcnh.md`](ghcnh.md) — international + multi-decade fallback
- Source-of-truth code: `packages/weather/src/mostlyright/weather/catalog/awc.py`
- Fetcher: `packages/weather/src/mostlyright/weather/_fetchers/awc.py`
- Merge logic: `packages/core/src/mostlyright/_internal/merge/observations.py`
