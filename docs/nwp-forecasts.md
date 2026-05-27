# NWP Forecasts in the TypeScript SDK

> **Status: deferred in v1.x.** `forecastNwp()` in `@mostlyrightmd/weather`
> exists as a typed stub so callers can write code against the stable
> signature today, but every call throws `NwpNotAvailableError`. **For
> gridded NWP today, use the Python SDK** (`mostlyrightmd>=1.0`), which
> wires the NCEP family end-to-end.

This page documents what's deferred, why, and what to do instead.

## TL;DR — Decision Matrix

| Need | Path |
|---|---|
| Gridded NWP (HRRR, GFS, NBM, …) **right now** | ✅ Python SDK |
| MOS forecasts for one of 7 major US stations (KNYC, KLAX, KORD, KMIA, KDEN, KSEA, KATL) | ✅ `iemMosForecasts()` in TS |
| MOS forecasts for any station that has IEM MOS coverage | ✅ `iemMosForecasts()` in TS |
| Gridded NWP in the browser / Node.js | ⏳ TS support tracked for v2.0+ |
| The type signature so you can write forward-compatible code | ✅ `forecastNwp()` (TS) — call it, catch `NwpNotAvailableError` |

## Why the TS lane is deferred

GRIB2 is the binary format the world's NWP centers (NOAA, ECMWF, MSC, …) use
to publish gridded forecasts. Decoding GRIB2 requires one of:

- **eccodes** — the C library used by everyone, including ECMWF itself.
  No browser port; native-only.
- **cfgrib** — Python wrapper around eccodes. Native-only.
- **A WASM port of eccodes** — exists as a research project, but the
  compile-time cost and bundle size (>5 MB even with aggressive
  tree-shaking) are impractical for a v1.x SDK.

The Python SDK depends on `cfgrib` + `xarray` and decodes GRIB2 server-side
or on the user's laptop where native binaries are available. The TS SDK
runs in browsers and Node.js where eccodes-class native bindings are not
available out-of-the-box, and a WASM-shipped decoder would inflate the
SDK's bundle by 50× for a feature most browser callers never use.

We're tracking the WASM-GRIB2 ecosystem and will land the execution body
in **v2.0+** once a viable decoder ships. The function signature is stable
today — your code keeps working when the runtime upgrades.

## How to catch the deferred call

`forecastNwp()` throws `NwpNotAvailableError`, which is a subclass of
`DataAvailabilityError` (so existing catch-all handlers continue to work):

```ts
import { forecastNwp } from "@mostlyrightmd/weather";
import { NwpNotAvailableError } from "@mostlyrightmd/core";

try {
  const grid = await forecastNwp("KNYC", "gfs");
} catch (e) {
  if (e instanceof NwpNotAvailableError) {
    console.warn(`[NWP deferred] station=${e.station} model=${e.model}`);
    console.warn(e.hint); // operator-actionable workaround pointer
    // Fall through to iemMosForecasts() if your station has MOS coverage.
  } else {
    throw e;
  }
}
```

The thrown instance carries typed `.station` and `.model` properties for
log/error attribution — no message parsing required.

### Back-compat catch via DataAvailabilityError

Pre-existing code that catches `DataAvailabilityError` still works:

```ts
import { DataAvailabilityError } from "@mostlyrightmd/core";

try {
  await forecastNwp("KNYC", "gfs");
} catch (e) {
  if (e instanceof DataAvailabilityError && e.reason === "model_unavailable") {
    // Same path; .station / .model not surfaced through this catch.
  }
}
```

## Workaround: IEM MOS for 7 major US stations

If your station is one of `KNYC`, `KLAX`, `KORD`, `KMIA`, `KDEN`, `KSEA`,
`KATL` (or any station IEM MOS covers), `iemMosForecasts()` gives you
MOS-based forecasts that solve most use cases:

```ts
import { iemMosForecasts } from "@mostlyrightmd/weather";

const rows = await iemMosForecasts("KNYC", "2026-05-01", "2026-05-07", {
  model: "nbe",
});
console.log(rows[0].tempC, rows[0].source); // 20.0, "iem.archive"
```

MOS isn't gridded — it's per-station point forecasts derived from the
underlying NWP run — but for settlement / station-level prediction-market
work it's typically the right granularity anyway.

## Workaround: Python SDK

For everything else, the Python SDK wires the NCEP family end-to-end:

```bash
pip install mostlyrightmd-weather
```

```python
from mostlyright.weather import forecast_nwp

df = forecast_nwp("KNYC", "gfs", cycle="2026-05-27T12:00:00Z", fxx=24)
print(df[["station", "valid_time", "temp_c"]])
```

See [forecasts.md](./forecasts.md) for the full Python-side documentation
including wiring-status tables and rate-limit guidance.

## Supported models (signature-only in TS today)

The `NwpModel` TypeScript type accepts all 24 models from
`schema.forecast_nwp.v1` so your code is forward-compatible:

### NCEP family (11 — all wired in Python)

`hrrr` · `hrrrak` · `gfs` · `gefs` · `gdas` · `nbm` · `rap` · `rrfs` ·
`rtma` · `urma` · `cfs`

### ECMWF family (4 — reserved)

`ecmwf_ifs_hres` · `ecmwf_ifs_ens` · `ecmwf_aifs_single` ·
`ecmwf_aifs_ens`

### MSC Canadian family (5 — live-only)

`hrdps` · `rdps` · `gdps` · `geps` · `reps`

### NOMADS-only family (4 — reserved)

`hafs` · `nam` · `href` · `hiresw`

For up-to-date wiring status and historical-depth bounds, see
[forecasts.md](./forecasts.md#supported-nwp-models).

## Roadmap

- **v1.x (today)**: signature stable, throws `NwpNotAvailableError`. MOS
  workaround for 7 major US stations.
- **v2.0+ (planned)**: GRIB2 decode lands once the WASM-GRIB2 ecosystem
  matures (eccodes-wasm or equivalent reaches production quality and
  acceptable bundle size). Migration is a runtime upgrade — no signature
  break, no caller code changes required.
- **Anytime in between**: PRs welcome. If you have a working
  browser/Node GRIB2 decoder at a reasonable bundle size, open an issue.

## See also

- [forecasts.md](./forecasts.md) — Python-side NWP wiring and Mode 1/Mode 2
  `research(include_forecast=True)` documentation
- [climate-gaps.md](./climate-gaps.md) — parallel deferral on
  `climateGaps()`, also browser-environment limited
- `.planning/phases/17-forecast-catalog-expansion-herbie-wide-models/` —
  the planning context for the Python NWP build
- `.planning/phases/21-typescript-sdk-parity-completion/21-07-PLAN.md` —
  the original 21-07 stub-messaging plan
