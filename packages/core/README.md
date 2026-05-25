# mostlyright

Local-first SDK for quants researching prediction-market weather settlements.

Meta package: exposes `mostlyright.research()` (the observation × climate join) and re-exports common utilities.

## Install

```bash
pip install mostlyright                # core only (helpers + snapshot primitives)
pip install mostlyright[research]      # core + weather, enables `mostlyright.research()`
pip install mostlyright-weather        # weather data sources (transitively brings core)
```

`mostlyright` and `mostlyright-weather` share the `mostlyright.*` namespace but ship as separate PyPI distributions so users who need only the helpers can skip the heavier weather deps. `research()` lazy-imports `mostlyright.weather` and raises a clear error if the weather package is not installed.

See the workspace [README](../../README.md) and [CLAUDE.md](../../CLAUDE.md) for project rules.
