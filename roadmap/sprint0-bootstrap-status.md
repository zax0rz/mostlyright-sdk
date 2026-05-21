# Sprint 0 — Day 1 Morning Bootstrap Status

**Branch:** `sprint0/wave1-bootstrap` (off `merged-vision`)
**Owner:** Lane F (Founder) — agent run, founder action pending
**Date:** 2026-05-21

## Verified

- **Dep floors match v0.14.1** across `packages/{core,weather,markets}/pyproject.toml`.
  Cross-referenced `~/Documents/GitHub/monorepo-v0.14.1/pyproject.toml`:
  - `httpx>=0.27` ✓
  - `jsonschema>=4.21` ✓
  - `pyarrow>=17.0` ✓ (under `[parquet]` extra, mirroring v0.14.1)
  - `pandas>=2.2` ✓ (under `[parquet]` extra)
  - `filelock>=3.12` ✓ (weather only — used for parquet cache; not in v0.14.1, new for tradewinds)
  - `tzdata; sys_platform == 'win32'` ✓ (core, weather; not needed in markets which has no ZoneInfo import)
  No tightenings needed — current pins are exact match to v0.14.1 floors.

- **`uv sync` clean** from worktree root. Installs 41 packages including all three
  workspace members in editable mode. `tradewinds-workspace` root deps (added in
  `7309e7a`) pull workspace members so plain `uv sync` (no `--all-packages` flag)
  installs everything.

- **`uv run python -c "import tradewinds"`** succeeds. Reports `version = 0.0.1`.

## Pending Founder Action

PyPI placeholder reservation for the three package names is **not** done here
(founder owns the PYPI_TOKEN). This must happen before public announcement so
the namespace is locked.

### Copy-paste commands

```bash
cd /Users/helloiamvu/Documents/GitHub/tradewinds  # or wherever the merged branch lands
uv build  # produces dist/tradewinds-0.0.1*, dist/tradewinds_weather-0.0.1*, dist/tradewinds_markets-0.0.1*

# Set token once per shell (or use uv publish --token <token>)
export UV_PUBLISH_TOKEN=<your-pypi-token>

uv publish dist/tradewinds-0.0.1*.whl dist/tradewinds-0.0.1*.tar.gz
uv publish dist/tradewinds_weather-0.0.1*.whl dist/tradewinds_weather-0.0.1*.tar.gz
uv publish dist/tradewinds_markets-0.0.1*.whl dist/tradewinds_markets-0.0.1*.tar.gz
```

After publish, verify on https://pypi.org/project/tradewinds/, /tradewinds-weather/,
/tradewinds-markets/. Day 4 will bump core+weather to `0.1.0` and republish; markets
stays at `0.0.1` placeholder through Sprint 0.

## Out of scope this commit

- PyPI publish (founder action above)
- Lifting `_internal/` code (other Wave 1 agents)
- Touching `packages/core/src/tradewinds/_v02/` (already merged in `merged-vision`)
