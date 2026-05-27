# mostlyrightmd

**The public-data SDK for quants, ML pipelines, and AI agents.**

`mostlyrightmd` is the Python entry point: core types, schemas, validators, temporal-safety primitives, and the `research()` join that ties weather observations × climate into one row per settlement date — ready for prediction-market backtests (Kalshi NHIGH/NLOW, Polymarket), ML training pipelines, and AI-agent tool calls. Direct calls to public APIs (NOAA, NWS, IEM, GHCNh, Kalshi, Polymarket). No hosted backend, no API key.

Weather data + prediction-markets data are live today. SEC filings (EDGAR) and Federal Reserve economic data (FRED) are next.

## Install

```bash
pip install mostlyrightmd                # core only (helpers + snapshot primitives)
pip install 'mostlyrightmd[research]'    # core + weather; enables research()
pip install mostlyrightmd-weather        # weather data sources only (brings core transitively)
```

`mostlyrightmd` and `mostlyrightmd-weather` share the `mostlyright.*` Python namespace but ship as separate PyPI distributions, so users who only need the helpers can skip the heavier weather deps. `research()` lazy-imports `mostlyright.weather` and raises a clear error if the weather package is not installed.

## Quickstart

```python
import mostlyright

df = mostlyright.research("KNYC", "2025-01-06", "2025-01-12")
print(df.head())
```

## Documentation

Quickstart, concepts, and the full API reference live at <https://mostlyright.md/docs/sdk/>.
