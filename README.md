# mostlyright

**The public-data SDK for quants, ML pipelines, and AI agents.**

[![PyPI version](https://img.shields.io/pypi/v/mostlyrightmd.svg)](https://pypi.org/project/mostlyrightmd/)
[![PyPI downloads](https://badgen.net/pypi/dm/mostlyrightmd?label=PyPI%20downloads)](https://pypistats.org/packages/mostlyrightmd)
[![npm version](https://img.shields.io/npm/v/mostlyright.svg)](https://www.npmjs.com/package/mostlyright)
[![npm downloads](https://img.shields.io/npm/dm/mostlyright?label=npm%20downloads)](https://www.npmjs.com/package/mostlyright)
[![Python versions](https://img.shields.io/pypi/pyversions/mostlyrightmd.svg)](https://pypi.org/project/mostlyrightmd/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mostlyright.md-blue.svg)](https://mostlyright.md/docs/sdk/)

`mostlyright` is a Python + TypeScript SDK for quants, ML engineers, and AI agents — direct, schema-versioned access to **weather data** (live METAR/ASOS, forecasts, GHCNh climate history, NWS CLI text products) and **prediction-market settlements** (Kalshi NHIGH/NLOW, Polymarket discovery + settlement, Kalshi + Polymarket trades). SEC filings (EDGAR) and Federal Reserve series (FRED) land next. Local-first: no hosted backend, no API key for the public-data layer, byte-equivalent reproducibility from research to backtest, and leakage-free training pairs for ML pipelines.

---

## Install

```bash
# Python
pip install 'mostlyrightmd[research]'

# TypeScript / Node
pnpm add mostlyright
```

Python 3.11+. Node 18+. No API key required for any package below.

## Quickstart

```python
# Python
import mostlyright

df = mostlyright.research("KNYC", "2025-01-06", "2025-01-12")
print(df.head())
# pandas DataFrame: one row per LST settlement date
# Columns: date, station, cli_high_f, cli_low_f, obs_high_f, obs_low_f,
#          obs_mean_f, obs_count, fcst_*, market_close_utc
```

```ts
// TypeScript
import { research } from "mostlyright";

const rows = await research("KNYC", "2025-01-06", "2025-01-12");
console.log(rows[0]);
// ReadonlyArray<PairsRow>: same schema as Python, JSON-serializable
```

First call writes a parquet (Python) or JSON-envelope (Node) cache to `~/.mostlyright/cache/`. Subsequent calls in the same window are local-only — no network.

Full quickstart with concepts at <https://mostlyright.md/docs/sdk/>.

## Packages

### Python (PyPI)

| Package | Description | Downloads | Status |
|---|---|---|---|
| [`mostlyrightmd`](https://pypi.org/project/mostlyrightmd/) | Core types, schemas, validators, the `research()` join, and snapshot primitives. Imports as `mostlyright`. | [![monthly downloads](https://badgen.net/pypi/dm/mostlyrightmd?label=monthly)](https://pypistats.org/packages/mostlyrightmd) | stable |
| [`mostlyrightmd-weather`](https://pypi.org/project/mostlyrightmd-weather/) | Weather data fetchers — live METAR (AWC), ASOS archive (IEM), historical observations (GHCNh), and NWS climate text products (CLI). Direct public-API access. | [![monthly downloads](https://badgen.net/pypi/dm/mostlyrightmd-weather?label=monthly)](https://pypistats.org/packages/mostlyrightmd-weather) | stable |
| [`mostlyrightmd-markets`](https://pypi.org/project/mostlyrightmd-markets/) | Prediction-market data — Kalshi NHIGH/NLOW weather-contract resolvers, Polymarket discovery + settlement, and Kalshi + Polymarket trade history. | [![monthly downloads](https://badgen.net/pypi/dm/mostlyrightmd-markets?label=monthly)](https://pypistats.org/packages/mostlyrightmd-markets) | stable |
| `mostlyrightmd-edgar` | SEC filings (10-K, 10-Q, 8-K) — direct EDGAR full-text + facts access. | n/a | planned |
| `mostlyrightmd-fred` | Federal Reserve economic data (FRED series, observations, releases). | n/a | planned |

### TypeScript (npm)

| Package | Description | Downloads | Status |
|---|---|---|---|
| [`mostlyright`](https://www.npmjs.com/package/mostlyright) | Meta package — one `import { research } from "mostlyright"` for weather data + prediction-market settlements + the core join. | [![monthly downloads](https://img.shields.io/npm/dm/mostlyright?label=monthly)](https://www.npmjs.com/package/mostlyright) | stable |
| [`@mostlyrightmd/core`](https://www.npmjs.com/package/@mostlyrightmd/core) | Core types, schemas, validators, temporal-safety primitives, and the `research()` join. | [![monthly downloads](https://img.shields.io/npm/dm/%40mostlyrightmd%2Fcore?label=monthly)](https://www.npmjs.com/package/@mostlyrightmd/core) | stable |
| [`@mostlyrightmd/weather`](https://www.npmjs.com/package/@mostlyrightmd/weather) | Weather data fetchers — live METAR (AWC), ASOS archive (IEM), historical observations (GHCNh), and NWS climate text products (CLI). | [![monthly downloads](https://img.shields.io/npm/dm/%40mostlyrightmd%2Fweather?label=monthly)](https://www.npmjs.com/package/@mostlyrightmd/weather) | stable |
| [`@mostlyrightmd/markets`](https://www.npmjs.com/package/@mostlyrightmd/markets) | Prediction-market data — Kalshi NHIGH/NLOW weather-contract resolvers, Polymarket discovery + settlement, and Kalshi + Polymarket trade history. | [![monthly downloads](https://img.shields.io/npm/dm/%40mostlyrightmd%2Fmarkets?label=monthly)](https://www.npmjs.com/package/@mostlyrightmd/markets) | stable |
| `@mostlyrightmd/edgar` | SEC filings (10-K, 10-Q, 8-K). | n/a | planned |
| `@mostlyrightmd/fred` | Federal Reserve economic data. | n/a | planned |

## What you can build

### Backtest prediction-market settlements

Pull joined climate + observation rows for a settlement window, compare against contract spec, and produce a deterministic settlement decision.

```python
import mostlyright
from mostlyright.markets.catalog import kalshi_nhigh

# 1. What does the contract settle on?
contract = kalshi_nhigh.resolve("KHIGHNYC", date(2025, 1, 15))
# 2. Pull the data that decides it.
df = mostlyright.research(contract.settlement_station, "2025-01-15", "2025-01-15")
# 3. Apply the threshold and decide.
```

### Train models with train/infer source parity

`research()` stamps a source identity on every row. The validator catches train/infer mismatches at load time, instead of silently corrupting predictions in production.

```python
from mostlyright.mode2 import research_by_source
from mostlyright.core import validate_dataframe

train = research_by_source("KNYC", "iem.archive", "2024-01-01", "2024-12-31")
# Validator pins the schema's expected source. SourceMismatchError fires if
# you accidentally route a Mode 1 (fused AWC+IEM+GHCNh) DataFrame through a
# Mode 2 (iem.archive only) schema.
validate_dataframe(train, schema_id="schema.observation.v1")
```

### Feed AI agents structured public data

Every response carries a stable `schema.*.v1` URI and serializes to JSON-Schema-validated shapes. Drop responses into MCP tool outputs or OpenAI/Anthropic function-call returns without re-shaping.

```ts
import { research } from "mostlyright";
import { validateRows } from "@mostlyrightmd/core/validator";

const rows = await research("KNYC", "2025-01-06", "2025-01-12");
const result = validateRows(rows, "schema.observation.v1");
// result.audit_log carries the schema URI + source identity + row count
// — ready to pass through to an agent's tool-call response.
```

## Why mostlyright

- **No hosted backend.** Direct calls to public APIs (NOAA, NWS, IEM, Kalshi, Polymarket). No proxy. No vendor account. No rate-limited tier.
- **Local-first cache.** Parquet (Python) or JSON envelope (Node) at `~/.mostlyright/cache/`. Byte-stable across runs — deterministic backtests.
- **Schema-versioned outputs.** Every response carries a stable `schema.*.v1` URI. Train/infer source mismatches fail loudly instead of silently corrupting models.
- **Python + TypeScript peers.** Same `research()` shape, byte-equivalent on the parity fixtures. Use whichever runtime your stack prefers.
- **MIT licensed.** Use it commercially. Fork it. Ship it.

## Documentation

- **Quickstart + concepts:** <https://mostlyright.md/docs/sdk/>
- **API reference:** <https://mostlyright.md/docs/sdk/> (Python + TypeScript reference auto-generated per release)
- **Migration from the legacy hosted-API client:** <https://mostlyright.md/docs/sdk/migration/legacy/>

## Contributing

Bug reports, feature requests, and pull requests are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development workflow (fork → branch → PR) and the test gate. See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community guidelines.

For security issues, see [`SECURITY.md`](SECURITY.md) — do not file public issues for vulnerabilities; email <vu@mostlyright.md> instead.

## License

MIT. See [`LICENSE`](LICENSE).

## Acknowledgements

`mostlyright` calls the following public APIs directly. We are grateful for the work that makes weather and market data accessible at the public-API layer:

- **NOAA Aviation Weather Center** (AWC) — live METAR feeds
- **Iowa State University Iowa Environmental Mesonet** (IEM) — ASOS archive + CLI text products
- **NOAA National Centers for Environmental Information** (NCEI) — GHCNh historical observations
- **National Weather Service** (NWS) — climate data products (CLI) and forecast model outputs
- **Kalshi** + **Polymarket** — public prediction-market metadata + settlement feeds
