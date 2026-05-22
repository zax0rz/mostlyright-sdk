# tradewinds

Local-first SDK for quants researching prediction-market weather settlements.

Meta package: exposes `tradewinds.research()` (the observation × climate join) and re-exports common utilities.

## Install

```bash
pip install tradewinds                # core only (helpers + snapshot primitives)
pip install tradewinds[research]      # core + weather, enables `tradewinds.research()`
pip install tradewinds-weather        # weather data sources (transitively brings core)
```

`tradewinds` and `tradewinds-weather` share the `tradewinds.*` namespace but ship as separate PyPI distributions so users who need only the helpers can skip the heavier weather deps. `research()` lazy-imports `tradewinds.weather` and raises a clear error if the weather package is not installed.

See the workspace [README](../../README.md) and [CLAUDE.md](../../CLAUDE.md) for project rules.
