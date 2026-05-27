# mostlyright

**The public-data SDK for quants, ML pipelines, and AI agents.**

`mostlyright` is the convenience meta-package for the TypeScript SDK. A single `import { research } from "mostlyright"` re-exports the surfaces of `@mostlyrightmd/core`, `@mostlyrightmd/weather`, and `@mostlyrightmd/markets` — weather data (METAR, ASOS, GHCNh, NWS CLI), prediction-market settlements (Kalshi NHIGH/NLOW, Polymarket), and the core `research()` join. Direct calls to public APIs. No hosted backend, no API key.

Weather data + prediction-markets data are live today. SEC filings (EDGAR) and Federal Reserve economic data (FRED) are next.

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
