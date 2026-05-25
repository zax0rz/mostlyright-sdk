# mostlyrightmd

Local-first SDK for quants researching prediction-market weather settlements.

Meta package: exposes `mostlyright.research()` (the observation × climate join) and re-exports common utilities.

## Install

```bash
pip install mostlyrightmd                # core only (helpers + snapshot primitives)
pip install mostlyrightmd[research]      # core + weather, enables `mostlyright.research()`
pip install mostlyrightmd-weather        # weather data sources (transitively brings core)
```

`mostlyrightmd` and `mostlyrightmd-weather` share the `mostlyright.*` Python namespace but ship as separate PyPI distributions so users who need only the helpers can skip the heavier weather deps. `research()` lazy-imports `mostlyright.weather` and raises a clear error if the weather package is not installed.

See the workspace [README](../../README.md) and [CLAUDE.md](../../CLAUDE.md) for project rules.
