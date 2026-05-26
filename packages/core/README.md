# mostlyrightmd

Local-first Python SDK for quants researching prediction-market weather settlements.

Calls AWC, IEM, GHCNh, and NWS CLI directly; no hosted backend, no API key. Exposes `mostlyright.research(station, from_date, to_date)` — the observation × climate join that returns one row per settlement date.

## Install

```bash
pip install mostlyrightmd                # core only (helpers + snapshot primitives)
pip install 'mostlyrightmd[research]'    # core + weather; enables research()
pip install mostlyrightmd-weather        # weather data sources only (brings core transitively)
```

`mostlyrightmd` and `mostlyrightmd-weather` share the `mostlyright.*` Python namespace but ship as separate PyPI distributions, so users who only need the helpers can skip the heavier weather deps. `research()` lazy-imports `mostlyright.weather` and raises a clear error if the weather package is not installed.

## Docs

Quickstart, concepts, and the full API reference live at <https://mostlyright.md/docs/sdk/>.
