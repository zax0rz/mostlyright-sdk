# Forecast Sources — IEM MOS / NWP Gridded / Open-Meteo

`mostlyright` supports three forecast data sources for
`research(include_forecast=True)`:

| Source | Models | Latency | Units | Leakage-safe? | Cache eligible? |
|---|---|---|---|---|---|
| **IEM MOS** | 5 (NBE, GFS, LAV, MET, ECM) | 1-2h post-cycle | imperial (°F, kt, %) | Yes (per-cycle `runtime`) | Yes |
| **NWP gridded** | 24 declared / 11 wired (NCEP family) | mirror-dependent | model-native (K, m/s, mm, Pa) | Yes (per-cycle `issued_at`) | Yes |
| **Open-Meteo** | 36 (multi-provider) | per-cycle, ~2-6h post-cycle | metric (°C, m/s, mm) | Yes (per-cycle endpoint + conservative lower bound) | Partial (training-mode only) |

Each row in the output `DataFrame` carries its source identity via the
`source` column, so cross-source training data never silently merges.

## Open-Meteo (Phase 20, new in v1.3.0)

Open-Meteo aggregates 36 forecast models from major providers (NCEP,
ECMWF, DWD, Météo-France, JMA, KMA, CMA, BoM, UKMO, GEM Canada, etc.)
into a unified HTTP API.

### Quickstart

#### Python

```python
import mostlyright as mr

df = mr.research(
    station="KNYC",
    from_date="2024-06-01",
    to_date="2024-06-07",
    include_forecast=True,
    forecast_source="open_meteo",
    forecast_model="gfs_global",   # one of OPEN_METEO_MODELS
)
```

For cross-source comparison:

```python
df = mr.research(
    station="KNYC",
    from_date="2024-06-01",
    to_date="2024-06-07",
    include_forecast=True,
    forecast_source=["iem_mos", "open_meteo"],  # both sources, source column discriminates
)
```

#### TypeScript

```typescript
import { openMeteoForecasts } from "@mostlyrightmd/weather";

const rows = await openMeteoForecasts("KNYC", "2024-06-01", "2024-06-07", {
  model: "gfs_global",
  mode: "training",   // Previous Runs API; leakage-safe default
});
```

### Three modes

`fetch_open_meteo(..., mode=...)` dispatches to one of three endpoints:

1. **`mode="training"` (default)** — Previous Runs API
   `https://previous-runs-api.open-meteo.com/v1/forecast`
   - Broad coverage (most models from 2024-01, GFS 2m from 2021-03-23,
     JMA from 2018)
   - `issued_at` derived via conservative lower bound:
     `floor_to_cycle(valid_at - N*24h, model_cycles)`
   - Tag: `source="open_meteo.previous_runs"`

2. **`mode="training"` with `issued_at=...`** — Single Runs API
   `https://single-runs-api.open-meteo.com/v1/forecast`
   - When the caller specifies a cycle, Single Runs API returns the
     unmodified output
   - `issued_at = run` exactly (no derivation)
   - Coverage starts later (ECMWF from 2024-03-14, most others from
     2025-09)
   - Tag: `source="open_meteo.single_run"`

3. **`mode="live"`** — Live Forecast API
   `https://api.open-meteo.com/v1/forecast`
   - Real-time forward-looking; cycle rolls forward continuously
   - `issued_at` derived via cycle-math fallback:
     `floor_to_cycle(now - publish_lag(model), cycles)`
   - Tag: `source="open_meteo.live"`
   - **NOT cacheable** (rolling cycle)

### Why the Historical Forecast (seamless) endpoint is BANNED for training

The `https://historical-forecast-api.open-meteo.com/v1/forecast` endpoint
stitches forecasts from multiple model cycles into a continuous
timeseries. The cycle that produced any given value is **unrecoverable
from the response** — no debug header, no query parameter, no response
field. This caused the legacy bug
[Tarabcak/mostlyright#70](https://github.com/Tarabcak/mostlyright/issues/70),
where a snapshot training row at h13 EDT silently used the 18Z model
run (published 4-7 hours AFTER the snapshot). Apparent +6pp lift on
the MCAGE-OM benchmark was partly attributable to this leakage.

`fetch_open_meteo(mode="seamless")` raises
`OpenMeteoSeamlessLeakageError` unless the caller passes
`allow_leakage=True`. Even then, `LeakageDetector` rejects the
resulting rows whenever `as_of` is asserted.

### Cycle-math: the conservative lower bound

For Previous Runs API: `_previous_dayN` fields are stitched streams of
model forecasts initialized at least N×24h before `valid_at`. The exact
cycle is unrecoverable. Phase 20 derives the lower bound:

```
issued_at(N) = floor_to_cycle(valid_at - N*24h, model_cycles)
```

**Worked example:** NYC 2024-06-01T23:00:00Z, `_previous_day1`, GFS
(`(0, 6, 12, 18)` UTC cycles):

```
upper_bound = 2024-06-01T23:00:00Z - 24h = 2024-05-31T23:00:00Z
floor to GFS cycles {00, 06, 12, 18}: 2024-05-31T18:00:00Z
-> issued_at = 2024-05-31T18:00:00Z
```

This is provably <= the actual cycle. May under-estimate but never
over-estimates — no leakage risk.

### Supported models (36 total)

#### NCEP (8 models)
`gfs_seamless`, `gfs_global`, `gfs_graphcast025`, `aigfs025`, `hgefs025`,
`ncep_hrrr_conus`, `ncep_nbm_conus`, `ncep_nam_conus`

#### ECMWF (3 models)
`ecmwf_ifs025`, `ecmwf_ifs_hres`, `ecmwf_aifs025_single`

#### DWD (5 models)
`dwd_icon_seamless`, `dwd_icon_global`, `dwd_icon_eu`, `dwd_icon_d2`,
`dwd_icon_d2_15min`

#### Météo-France (6 models)
`meteofrance_seamless`, `meteofrance_arpege_world025`,
`meteofrance_arpege_europe`, `meteofrance_arome_france0025`,
`meteofrance_arome_france_hd`, `meteofrance_arome_france_hd_15min`

#### Asia + Oceania (8 models)
`jma_seamless`, `jma_gsm`, `jma_msm`, `kma_seamless`, `kma_gdps`,
`kma_ldps`, `cma_grapes_global`, `bom_access_global`

#### Europe (3 models)
`ukmo_global_deterministic_10km`, `ukmo_uk_deterministic_2km`,
`metno_nordic_pp`

#### GEM Canada (3 models)
`cmc_gem_gdps`, `cmc_gem_rdps`, `cmc_gem_hrdps`

Additional Open-Meteo models (MeteoSwiss CH1/CH2, KNMI Harmonie,
DMI Harmonie, ItaliaMeteo ICON) are reserved for a v0.3+ release.

### Schema

Open-Meteo rows land in the unified `schema.forecast.station.v1` schema
(Phase 20 OM-02). `schema.forecast.iem_mos.v1` is retained as a
back-compat alias. Column set includes IEM MOS shared core
(`temp_c`, `dew_point_c`, `wind_speed_ms`, `wind_dir_deg`,
`precip_probability`, `sky_cover_pct`) plus Open-Meteo extras
(`apparent_temp_c`, `shortwave_radiation_wm2`, `cape_jkg`,
`cloud_cover_pct`, `surface_pressure_hpa`, `pressure_msl_hpa`,
`freezing_level_m`, `snow_depth_m`, `visibility_m`, `wind_gusts_ms`,
`weather_code`, `direct_radiation_wm2`, `diffuse_radiation_wm2`,
`precipitation_mm`). All extras are nullable; IEM MOS rows leave them
null.

### Cache layout

```
~/.mostlyright/cache/v1/forecasts/{source}/{model}/{station}/{YYYY}/{MM}.parquet
```

- Partition by `issued_at` cycle month (immutable once published)
- Skip writes in the current UTC month (cycles may still publish)
- `source="open_meteo.live"` is NEVER cached (rolling)
- `source="open_meteo.seamless"` is NEVER cached (banned)

### Rate limits

Open-Meteo's documented free-tier limits: 600 req/min, 5,000 req/hour,
10,000 req/day, ~300,000 req/month. `mostlyright` enforces a polite
floor of 5 req/s single-worker (tighter than the documented limit),
matching the IEM MOS polite posture. 429 responses honor `Retry-After`
(capped at 60s).

### Typed exceptions

- `IssuedAtMissingError` — raised when a row would land with
  `issued_at IS NULL`.
- `OpenMeteoSeamlessLeakageError` — raised on `mode="seamless"` without
  `allow_leakage=True`. Carries `model`, `endpoint_url`,
  `origin_issue="Tarabcak/mostlyright#70"`.

Both subclass `MostlyRightError`; payload keys are snake_case for
cross-SDK MCP parity.

## IEM MOS

See [docs/forecasts.md](forecasts.md) for the IEM MOS adapter details
(5 NWS Model Output Statistics models from
`mesonet.agron.iastate.edu`). IEM MOS is the default
`forecast_source="iem_mos"` and what `research(include_forecast=True)`
returned in Phase 17 and earlier.

## NWP gridded

See [docs/forecasts.md](forecasts.md) §NWP for the NWP gridded
adapter (Phase 17 catalog of NCEP / ECMWF / MSC / HAFS / RAP / GFS family
models, GRIB2 fetch via AWS BDP / NOMADS mirrors).
