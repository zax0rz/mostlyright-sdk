# mostlyright

**The public-data SDK for quants, ML pipelines, and AI agents.**

`mostlyright` is the convenience meta-package for the TypeScript SDK. A single `import { research } from "mostlyright"` re-exports the surfaces of `@mostlyrightmd/core`, `@mostlyrightmd/weather`, and `@mostlyrightmd/markets` — weather data (METAR, ASOS, GHCNh, NWS CLI), prediction-market settlements (Kalshi NHIGH/NLOW, Polymarket), and the core `research()` join. Direct calls to public APIs. No hosted backend, no API key.

Weather + prediction-markets adapters are live today. SEC filings (EDGAR), equities structured data, Federal Reserve series (FRED), court filings, and FDA approvals are next — and the architecture is built to ship an adapter for any public data source.

If you only need one slice of the SDK, depend on the scoped packages directly. If you want everything in one import, this is the package.

## Install

```bash
pnpm add mostlyright
# or: npm install mostlyright
```

## Quickstart

```ts
import { research } from "mostlyright";

const rows = await research("KNYC", "2025-01-06", "2025-01-12");
console.log(rows[0]);
```

## Documentation

Quickstart, concepts, and the full API reference live at <https://mostlyright.md/docs/sdk/>.

## TypeScript SDK limitations vs Python

A few surfaces ship as **typed stubs** in v1.x because their Python implementations depend on native libraries that aren't viable in browser/Node bundles today:

| TS Function | Status | Use Python? | Workaround in TS |
|---|---|---|---|
| `research()` | ✅ Wired | optional | — |
| `iemMosForecasts()` | ✅ Wired | optional | — |
| `obs()` / `dailyExtremes()` | ✅ Wired | optional | — |
| `forecastNwp()` | ⏳ v2.0+ stub | **yes** for gridded NWP | `iemMosForecasts()` for the 7 major US stations |
| `climateGaps()` | ⏳ v2.0+ stub | **yes** for climate-gap analysis | — |

Stub calls throw typed errors (`NwpNotAvailableError`, `DataAvailabilityError`) so you can `instanceof`-dispatch instead of parsing messages.

For the rationale and roadmap, see [docs/nwp-forecasts.md](https://github.com/mostlyrightmd/mostlyright-sdk/blob/main/docs/nwp-forecasts.md) and [docs/climate-gaps.md](https://github.com/mostlyrightmd/mostlyright-sdk/blob/main/docs/climate-gaps.md).
