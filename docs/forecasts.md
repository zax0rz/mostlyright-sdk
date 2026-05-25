# Forecasts

Mostlyright supports two complementary forecast surfaces:

1. **IEM MOS** (Model Output Statistics) — text/JSON, parity-compatible,
   the default for `research(include_forecast=True)`.
2. **NWP (Numerical Weather Prediction)** — gridded GRIB2 via NOAA Big
   Data Program / ECMWF Open Data / MSC Datamart. **24 models are
   declared in `schema.forecast_nwp.v1`; 11 NCEP-family models are
   wired end-to-end in v1.0** (HRRR, HRRRAK, GFS, GEFS, GDAS, NBM, RAP,
   RRFS, RTMA, URMA, CFS). The remaining 13 ship URL patterns, QC
   rules, and idx-style dispatch but `forecast_nwp()` raises:
   - `HistoricalDepthError(archive_depth=None)` — MSC×5 (HRDPS, RDPS,
     GDPS, GEPS, REPS), whose contract is "live-only Datamart, 24h
     retention" so the right error class for callers to branch on is
     historical-depth, not not-available.
   - `NwpModelNotAvailableError` — ECMWF×4, HAFS, and legacy NAM /
     HREF / HiResW until end-to-end fetch+decode wiring lands.
   See the **Wiring status** column on each family table below.

## Quick Start

```python
from mostlyright import research

# Default: include_forecast=False (parity-compatible v0.14.1 behavior)
df = research("KNYC", "2026-05-01", "2026-05-07")

# Mode 1: IEM MOS forecasts populate fcst_* columns
df = research("KNYC", "2026-05-01", "2026-05-07", include_forecast=True)
print(df[["date", "obs_high_f", "fcst_high_f", "fcst_model"]])

# Mode 2: Additionally include NWP forecasts per model
df = research(
    "KNYC", "2026-05-01", "2026-05-07",
    include_forecast=True,
    forecast_models=["hrrr", "gfs"],
)
print(df[["date", "fcst_high_f", "fcst_high_f_nwp_hrrr", "fcst_high_f_nwp_gfs"]])
```

`research(include_forecast=True)` was previously raising
`NotImplementedError`; Phase 17 wires both Mode 1 (IEM MOS) and Mode 2
(per-NWP-model) end-to-end. Settlement-day bucketing uses station LST
via `settlement_date_for(observed_at, station)` so post-midnight tail
rows roll into the correct calendar settlement.

## Supported NWP Models

> **Wiring status legend** — `✓ wired` = fetch + decode + QC end-to-end
> in v1.0. `reserved` = schema-declared (URL patterns, QC rules, idx
> dispatch present) but `forecast_nwp()` raises today. The exact
> exception class is family-specific: MSC×5 raise
> `HistoricalDepthError(archive_depth=None)` (live-only contract,
> special-cased before the reserved-models gate); ECMWF×4 / HAFS /
> NAM / HREF / HiResW raise `NwpModelNotAvailableError`. Reserved
> models flip to wired in follow-up releases as their fetch+decode
> paths land.

### NCEP family (USA — NOAA BDP + NOMADS)

| Model | Wiring | Coverage | Cycle freq | Historical depth | Notes |
|---|---|---|---|---|---|
| `hrrr` | ✓ wired | CONUS 3km | hourly | 2014-07-30 | High-resolution rapid refresh |
| `hrrrak` | ✓ wired | Alaska 3km | 3-hourly | 2018-01-01 | HRRR for Alaska |
| `gfs` | ✓ wired | Global 0.25° | 6-hourly | 2021-01-01 | Standard global model |
| `gefs` | ✓ wired | Global 0.5° ensemble (32 members) | 6-hourly | 2017-01-01 | Default member `c00`; opt in via `member=` |
| `gdas` | ✓ wired | Global 0.25° (short-range) | 6-hourly | 2021-01-01 | GFS analysis system |
| `nbm` | ✓ wired | Regional blend | hourly | 2020-01-01 | National Blend; `fxx=0` auto-bumps to `1` |
| `rap` | ✓ wired | CONUS 13km | hourly | 2020-01-01 | Rapid refresh |
| `rrfs` | ✓ wired | CONUS 3km | hourly | 2024-01-01 | HRRR successor (pre-operational) |
| `rtma` | ✓ wired | CONUS 2.5km analysis | hourly | 2024-01-01 | Real-time mesoscale analysis (`fxx=0` only) |
| `urma` | ✓ wired | CONUS 2.5km analysis | hourly | 2024-01-01 | Un-Restricted MA (`fxx=0` only) |
| `cfs` | ✓ wired | Global 1° (4-member) | 6-hourly | 2011-01-01 | Climate Forecast System |

All 11 NCEP-family models are end-to-end wired in v1.0.

### ECMWF family (Global — Open Data, 4 cloud mirrors)

| Model | Wiring | Cycle freq | Historical depth | Notes |
|---|---|---|---|---|
| `ecmwf_ifs_hres` | reserved | 6-hourly | 2022-01-01 | Deterministic IFS HRES |
| `ecmwf_ifs_ens` | reserved | 6-hourly | 2022-01-01 | Ensemble IFS |
| `ecmwf_aifs_single` | reserved | 6-hourly | 2024-02-25 | AI single |
| `ecmwf_aifs_ens` | reserved | 6-hourly | 2024-02-25 | AI ensemble |

ECMWF uses eccodes `.index` (JSON-lines) instead of wgrib2 `.idx`.
mostlyright dispatches transparently via `IDX_STYLE_BY_MODEL`. The
dispatch + URL patterns + QC tp-meters rule ship in v1.0; end-to-end
`forecast_nwp(model="ecmwf_*")` raises `NwpModelNotAvailableError`
until the eccodes decode path is wired in a follow-up.

### MSC Canadian family (Live-only, 24h Datamart retention)

| Model | Wiring | Cycle freq | Notes |
|---|---|---|---|
| `hrdps` | reserved | 6-hourly | 2.5km continental |
| `rdps` | reserved | 6-hourly | 10km regional |
| `gdps` | reserved | 12-hourly | 15km global |
| `geps` | reserved | 12-hourly | 0.5° ensemble (aggregate or per-member) |
| `reps` | reserved | 6-hourly | 10km regional ensemble (21 members) |

URL patterns + 24h Datamart `LIVE_CYCLE_WINDOW` gating ship in v1.0;
calling `forecast_nwp(model="hrdps" | "rdps" | "gdps" | "geps" |
"reps", ...)` raises `HistoricalDepthError(archive_depth=None)` today
(special-cased in `forecast_nwp.py:518-532` BEFORE the reserved-models
gate, because the contract is "live-only Datamart, 24h retention" and
historical-depth is the right branchable error class for callers).
End-to-end MSC fetch is wired in a follow-up.

### NOMADS-only + Legacy

| Model | Wiring | Cycle freq | Status |
|---|---|---|---|
| `hafs` | reserved | 6-hourly | Hurricane analysis (storm-following; requires `storm=` param when wired) |
| `nam` | reserved | 6-hourly | LEGACY — retiring 2026-08-31; emits `DeprecatedModelWarning` |
| `href` | reserved | 6-hourly | LEGACY — retiring 2026-08-31 |
| `hiresw` | reserved | 12-hourly | LEGACY — retiring 2026-08-31 |

URL patterns + QC families (HAFS basin-position, ensemble dispersion for
HREF) ship in v1.0; `forecast_nwp()` raises `NwpModelNotAvailableError`
for HAFS / NAM / HREF / HiResW today. Legacy models additionally emit
`DeprecatedModelWarning` before the not-wired error. Use HRRR / RAP /
RRFS as replacements for retiring models.

## HAFS — Storm Resolution (reserved in v1.0)

**HAFS is schema-reserved in v1.0** — `forecast_nwp(model="hafs", ...)`
raises `NwpModelNotAvailableError`. The interface contract below
documents the shape end-to-end wiring will take in a follow-up release;
write code against the signature today and the runtime will arrive
later. The `Storms()` resolver + URL patterns + basin-position QC rule
already ship in v1.0.

The active-storm resolver already ships in v1.0 (the `Storms()` cache
+ `get_active_storms()` text-table parser):

```python
from mostlyright.weather._fetchers._hafs_storms import get_active_storms

storms = get_active_storms()
# {"09l": "laura", "10l": "marco"}
```

The `Storms()` resolver caches the active list for 1 hour. Pass
`bust_cache=True` to force re-fetch.

**v1.0 call shape (today).** `forecast_nwp` has no `storm=` parameter
yet, so the gate that fires on a HAFS call is the reserved-models gate:

```python
from mostlyright.forecasts import forecast_nwp
forecast_nwp(station="KNYC", model="hafs")  # → NwpModelNotAvailableError
```

**Future call shape (when fetch+decode lands).** The follow-up wiring
will add a `storm=` argument resolvable as either a storm id (e.g.
`"09l"`, historical) or a storm name (e.g. `"laura"`, currently
active). The signature is forward-looking pseudocode — not callable
today:

```python
# Future signature; not callable in v1.0.
df = forecast_nwp(
    station="KNYC", model="hafs", storm="laura",
    cycle=datetime(2026, 9, 1, 12, tzinfo=UTC), fxx=range(0, 25),
)
```

## Historical Backfill

```python
from datetime import UTC, datetime
from mostlyright.forecasts import forecast_nwp

# Fetch ALL HRRR cycles in May 2024
df = forecast_nwp(
    station="KNYC", model="hrrr",
    cycle_range_start=datetime(2024, 5, 1, 0, tzinfo=UTC),
    cycle_range_end=datetime(2024, 5, 31, 23, tzinfo=UTC),
    fxx=range(0, 25),
)
# ~744 HRRR cycles × 25 forecast hours each
```

`cycle=` and `cycle_range_start=` are mutually exclusive. Per-model AWS
BDP depths are documented above; older cycles raise
`HistoricalDepthError`.

### Settlement-day envelope (Mode 2)

`research(include_forecast=True, forecast_models=[...])` fetches a
36-hour NWP envelope per settlement day:

- prior-day 12Z, `fxx=0..24`
- current-day 00Z, `fxx=0..24`
- current-day 12Z, `fxx=0..24`

This guarantees coverage of overnight lows and afternoon highs in the
station's LST settlement window. Analysis-only products (RTMA, URMA)
are dispatched at `fxx=0` regardless.

## QC Rules

Each model row gets a `qc_status` enum (`clean`, `flagged`, `suspect`)
from `weather.qc.rules_nwp.QC_RULES_NWP[model]`:

- **NCEP base**: 7 physics-bounds rules (temp / dewpoint / RH / gust /
  precip / `PRES_sfc` / `MSLP`). `PRES_sfc` + `MSLP` retain the Phase 3.2
  backward-compat `<= 0 Pa → suspect` branch.
- **ECMWF**: NCEP base + tp-in-meters rule (ECMWF tp unit is meters,
  not mm).
- **GEFS / HREF / REPS**: NCEP base + ensemble-dispersion sanity
  (cross-row).
- **HAFS**: NCEP base + basin-position sanity (`storm_lat ∈ [0, 60]`).
- **MSC HRDPS**: NCEP base + regional-grid bounds
  (`grid_dist_km < 50`).

Worst-case semantics: suspect > flagged > clean per row. Filter
clean-only rows with `df[df["qc_status"] == "clean"]`.

## TypeScript Lane (v1.0)

`@mostlyright/weather` v1.0 ships IEM MOS only:

```typescript
import { iemMosForecasts } from '@mostlyright/weather/forecasts';

const rows = await iemMosForecasts('KNYC', '2026-05-01', '2026-05-07', { model: 'nbe' });
console.log(rows[0].tempC, rows[0].source);  // 20.0, "iem.archive"
```

`@mostlyright/weather/forecasts.forecastNwp()` is shipped as a v1.0
STUB:

```typescript
import { forecastNwp } from '@mostlyright/weather/forecasts';
// Throws Error('TS NWP deferred to v1.1') at runtime.
// Signature stable; runtime arrives in v1.1.
```

**Why?** No production-ready browser GRIB2 decoder exists as of May
2026 (see Phase 17 CONTEXT decision 7). v1.1 re-evaluates browser WASM
GRIB2 decoders.

For TS NWP today, use the Python SDK (`mostlyright>=v1.0`) which wires
the NCEP family end-to-end (see the Wiring-status tables above).

## Rate Limits / Concurrency

- **AWS BDP / Google Cloud / Azure**: tolerate aggressive parallelism.
  Default `httpx.Limits` per `FORECAST-LIMITS.md`.
- **NOMADS**: capped at `NOMADS_CONCURRENCY_CAP=4` per Herbie #371
  IP-ban evidence. mostlyright fails fast on 403.
- **MSC Datamart**: undocumented; mostlyright is polite (treat as
  `N≤4`).
- **ECMWF Open Data**: 500 simultaneous connections per IP (per ECMWF
  docs); mostlyright uses `N≤8`.

See `.planning/research/FORECAST-LIMITS.md` for empirical data.

## References

- `.planning/research/HERBIE-PATTERNS.md` — Herbie pattern intel
- `.planning/phases/17-forecast-catalog-expansion-herbie-wide-models/17-CONTEXT.md`
- `.planning/phases/17-forecast-catalog-expansion-herbie-wide-models/17-RESEARCH.md`
- `.planning/research/FORECAST-LIMITS.md` — empirical concurrency spike
- `.planning/research/FORECAST-CORS-MATRIX.md` — browser CORS posture
