# NWS CLI (Climate Product — settlement source)

## Overview

- **Source IDs:** `cli.archive`, `cli.live`
- **Provider:** NOAA / National Weather Service (CLI = "Climatological Report")
- **License:** Public-domain (US federal government work)
- **Endpoint (via IEM mirror):** `https://mesonet.agron.iastate.edu/json/cli.py?station={icao}&year={year}`
- **Catalog module:** `mostlyright.weather.catalog.cli.CLIAdapter`
- **Fetcher module:** `mostlyright.weather._fetchers.iem_cli`
- **Parser module:** `mostlyright.weather._climate` (`parse_cli_record`, `parse_cli_response`)

CLI is **the** settlement source for Kalshi NHIGH/NLOW. Every byte-equivalent
parity fixture in `tests/fixtures/parity/` joins observation rows against the
CLI daily-extremes ledger; any drift in CLI dedup logic immediately invalidates
the gate. Treat the dedup as load-bearing (CLAUDE.md "Data + parity rules").

The DATA in CLI rows is the NWS Climate text product. The TRANSPORT in v0.1 is
IEM's JSON mirror at `json/cli.py` — see [`iem.md`](iem.md) for the IEM
hosting side. The two `cli.*` source IDs differ from the two `iem.*` source IDs
deliberately: Validator dispatch on `schema.settlement.cli.v1` looks for
`cli.archive` / `cli.live`, not the IEM transport IDs.

## Canonical Schema

Output conforms to `schema.settlement.cli.v1`. The projection from raw CLI
parser records:

| Canonical column         | Source field (CLI JSON / parser)    | Notes                                                  |
| ------------------------ | ----------------------------------- | ------------------------------------------------------ |
| `station`                | `station_code`                      | 4-letter ICAO                                          |
| `observation_date`       | `observation_date`                  | Local date (station_tz), Python `date` object          |
| `report_type`            | `preliminary` / `final` / `correction` | Drives the dedup priority                              |
| `temp_max_F`             | `high_temp_f`                       | Float64 (parser emits int; adapter coerces)            |
| `temp_min_F`             | `low_temp_f`                        |                                                        |
| `precipitation_in`       | `precipitation_in`                  |                                                        |
| `snowfall_in`            | `snowfall_in`                       |                                                        |
| `product_release_time`   | `issued_at` (ISO → datetime64 UTC)  | Per `docs/design.md` §BB.3                             |
| `station_tz`             | per-station IANA name               | Required for `event_time`; `"UTC"` sentinel fails loud |
| `event_time`             | 00:00 station-local → UTC           | Derived in `_event_time_from_date`                     |
| `cli_data_quality`       | `"clean"` (v0.1 default)            | QC engine release populates richer values              |
| `settlement_finality`    | `provisional` / `final`             | Mapped from `report_type` (final/correction → final)   |
| `source`                 | `"cli.archive"` or `"cli.live"`     | Set by `CLIAdapter.from_records`                       |
| `retrieved_at`           | wall-clock UTC of fetch             |                                                        |
| `knowledge_time`         | = `product_release_time`            | Canonical CLI semantics                                |

## Gotchas

- **`(station, observation_date)` dedup is parity-load-bearing.** The CLI
  product issues in three forms: `preliminary` (early next morning), `final`
  (later same day after QC), and `correction` (occasional, days later). The
  v0.14.1 lift in `_climate.py:REPORT_TYPE_PRIORITY` keeps the **strictly
  higher** priority per `(station, observation_date)`, with first-row-seen
  wins at equal priority. `REPORT_TYPE_PRIORITY = {"final": 3.0,
  "ncei_final": 2.5, "correction": 2.0, "preliminary": 1.0, "estimated": 0.0}`.
  **Strict `>` is critical** — `>=` would let a later `final` row replace an
  equal-priority earlier one and drift the parity fixtures. (CLAUDE.md
  "Climate LIVE_V1" section.)
- **`cli_data_quality` enum.** The QC engine release populates this with
  richer values (`clean`, `quarantine`, `corrected`, …). v0.1 hard-codes
  `"clean"`. Downstream callers must treat unknown enum values as a soft
  signal, not a hard failure, until the QC engine lands.
- **`settlement_finality` enum.** Maps from `report_type`:
  `preliminary → provisional`, `final → final`, `correction → final`. Any
  unmapped `report_type` falls through to `provisional` (defensive default).
- **REMARKS regex.** CLI text records carry a REMARKS section that can flag
  estimated data or corrections. The current parser does basic regex
  extraction; the QC engine release's richer parse goes into `cli_data_quality`.
- **Per-station IANA tz mapping.** The US stations carry a
  hard-coded `station_tz` lookup in
  `packages/weather/src/mostlyright/weather/catalog/_cli_station_tz.py`. Stations
  outside the registry default to the `"UTC"` sentinel, which is intentionally
  wrong — the Validator's `event_time` check fires and the caller learns
  immediately. Production code MUST pass the real zone.
- **`retrieved_at` must be tz-aware.** `CLIAdapter.from_records` rejects naive
  `retrieved_at` with a clear `ValueError` (defensive: pandas's tz-coerce of a
  naive datetime emits a cryptic error otherwise).
- **Empty-pull path.** When zero records survive
  dedup, the adapter still constructs a properly-typed empty DataFrame
  (`observation_date: object`, `product_release_time: datetime64[ns, UTC]`).
  Validator accepts the empty frame without a dtype mismatch.

## Timezone Handling

- `observation_date` is **station-local**. The IEM mirror serves it as a
  date-only ISO string (`"2025-01-06"`) with no tz info.
- `product_release_time` is **UTC**. The parser parses to tz-aware
  `datetime64[ns, UTC]` at the boundary.
- `event_time` is **UTC midnight of the local date**, derived in
  `_event_time_from_date(date_series, station_tz)`. DST boundaries:
  - On a spring-forward day, local midnight maps to the standard-offset UTC
    (no skipped hour at 00:00 local).
  - On a fall-back day, local midnight maps to the standard-offset UTC
    (no duplicate hour at 00:00 local).
  - For stations that observe DST, the UTC midnight shifts by 1 hour
    across the DST transition — this is the correct semantic for settlement
    windows that are defined in local calendar dates.

## Source-Pairing Rules

- **Settlement is single-source.** CLI is the only settlement source in v0.1.
  Observations (AWC / IEM / GHCNh) are merged for the observation leg of the
  `research()` join; the settlement leg is CLI-exclusive.
- **`cli.archive` vs `cli.live`.** Same parser, different cache-residency
  policy. The current LST month for the station is `cli.live` (volatile —
  `preliminary` reports may be revised to `final`/`correction` within days).
  Closed months are `cli.archive`. The Validator dispatch ensures train/infer
  source-identity matching across the boundary.
- **IEM transport ≠ CLI source.** A row whose `source = "cli.archive"` was
  fetched via `mesonet.agron.iastate.edu/json/cli.py` — the IEM JSON mirror.
  The IEM hosting is invisible at the Validator level; what matters is the
  NWS CLI product semantics.

## Cache Layout

- On-disk path: `$HOME/.mostlyright/cache/v1/climate/{station}/{year}.parquet`
- Per-year cache, NOT per-month (CLI is a daily product; year-grain matches
  the IEM `json/cli.py` query parameter).
- `filelock`-guarded; same SoftFileLock fallback as observation cache.
- Current LST year for the station is volatile (preliminary → final / correction
  passes happen within days); closed years are immutable.

## See Also

- [`iem.md`](iem.md) — the IEM JSON transport for CLI products
- [`awc.md`](awc.md) — observation source (separate from settlement)
- [`ghcnh.md`](ghcnh.md) — observation source (separate from settlement)
- Source-of-truth code: `packages/weather/src/mostlyright/weather/catalog/cli.py`
- Parser: `packages/weather/src/mostlyright/weather/_climate.py`
- Fetcher: `packages/weather/src/mostlyright/weather/_fetchers/iem_cli.py`
- Merge logic (CLI dedup): `packages/core/src/mostlyright/_internal/merge/climate.py`
- Per-station tz: `packages/weather/src/mostlyright/weather/catalog/_cli_station_tz.py`
- v0.14.1 lift source: `monorepo-v0.14.1/ingest/storage/parquet.py:477-494`
  (`_dedup_climate_rows`) — byte-faithful port; any drift invalidates parity
