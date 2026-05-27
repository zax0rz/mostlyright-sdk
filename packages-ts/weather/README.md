# @mostlyrightmd/weather

Weather data fetchers and parsers for the [mostlyright](https://github.com/mostlyrightmd/mostlyright-sdk) TypeScript SDK — live METAR (AWC), ASOS archive (IEM), IEM CLI, historical observations (GHCNh), NWS climate text products (CLI), plus the local-first cache layer — for quants, ML training pipelines, and weather-bot agents. Direct public-API access; no hosted backend, no API key. Mirrors the Python `mostlyrightmd-weather` distribution. Declares `@mostlyrightmd/core` as a peer dependency.

## Install

```bash
pnpm add @mostlyrightmd/weather @mostlyrightmd/core
```

## Docs

See <https://mostlyright.md/docs/sdk/quickstart-typescript/> for a 60-second quickstart, or the full API reference at <https://mostlyright.md/docs/sdk/>.

## What's NOT in the TypeScript SDK (yet)

- **`forecastNwp()` is a typed stub in v1.x.** Gridded NWP forecasts
  (HRRR, GFS, NBM, …) require GRIB2 decode, which depends on native
  libraries (eccodes / cfgrib) that don't run in browser or Node.js
  without an impractical WASM bundle. The function signature is stable —
  you can write code today that keeps working when v2.0+ lands the
  execution body. Calls throw `NwpNotAvailableError` (subclass of
  `DataAvailabilityError`).
- **`climateGaps()` is a typed stub in v1.x.** Climate cache is
  server-only (GHCNh CSVs are 10+ MB per station-year).

**For gridded NWP today, use the Python SDK** — `mostlyrightmd-weather`
ships 11 NCEP-family models (HRRR, GFS, NBM, RAP, RRFS, …) end-to-end.
See [docs/nwp-forecasts.md](https://github.com/mostlyrightmd/mostlyright-sdk/blob/main/docs/nwp-forecasts.md)
for the architectural rationale, workaround paths, and v2.0+ roadmap.

For the 7 major US stations with IEM MOS coverage (KNYC, KLAX, KORD,
KMIA, KDEN, KSEA, KATL), `iemMosForecasts()` ships today as the
recommended TS-side workaround.
