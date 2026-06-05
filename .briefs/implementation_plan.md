# Implementation Plan: NWP Fields & Cloud Cover (Issue #63)

Fix the latent GFS precipitation duplicate-record crash and implement three new weather forecast columns (`cloud_cover_pct`, `visibility_m`, and `cloud_ceiling_m`) for HRRR and GFS models.

## Proposed Changes

### Core component (schema)

#### [MODIFY] [forecast_nwp.py](file:///Users/zach/.openclaw/workspace-chad/mostlyright-sdk/packages/core/src/mostlyright/core/schemas/forecast_nwp.py)
- Add columns:
  - `cloud_cover_pct` (float64, %, nullable)
  - `visibility_m` (float64, meters, nullable)
  - `cloud_ceiling_m` (float64, meters, nullable)

### Weather component (fetchers & models)

#### [MODIFY] [forecast_nwp.py](file:///Users/zach/.openclaw/workspace-chad/mostlyright-sdk/packages/weather/src/mostlyright/weather/forecast_nwp.py)
- Implement `_pick_record(group)` helper to filter duplicate records (prioritizing instantaneous over window-aggregated and breaking ties by `record_no`).
- Update `_extract_records` to call `_pick_record` and log a warning instead of raising `GribIntegrityError` when `len(group) > 1`.
- Add short-name lookups directly to `_GRIB_VAR_TO_CFGRIB_NAME`:
  - `("TCDC", "entire atmosphere"): "tcc"`
  - `("VIS", "surface"): "vis"`
  - `("HGT", "cloud ceiling"): "gh"`
- Register new columns in `nullable_numeric_cols` and `_empty_dataframe`.

#### [MODIFY] [gfs.py](file:///Users/zach/.openclaw/workspace-chad/mostlyright-sdk/packages/weather/src/mostlyright/weather/_fetchers/_nwp_grids/gfs.py)
- Add to `VARIABLE_MAP`:
  - `"cloud_cover_pct": ("TCDC", "entire atmosphere")`
  - `"visibility_m": ("VIS", "surface")`
  - `"cloud_ceiling_m": ("HGT", "cloud ceiling")`

#### [MODIFY] [hrrr.py](file:///Users/zach/.openclaw/workspace-chad/mostlyright-sdk/packages/weather/src/mostlyright/weather/_fetchers/_nwp_grids/hrrr.py)
- Add to `VARIABLE_MAP`:
  - `"cloud_cover_pct": ("TCDC", "entire atmosphere")`
  - `"visibility_m": ("VIS", "surface")`
  - `"cloud_ceiling_m": ("HGT", "cloud ceiling")`

#### [MODIFY] [rules_nwp.py](file:///Users/zach/.openclaw/workspace-chad/mostlyright-sdk/packages/weather/src/mostlyright/weather/qc/rules_nwp.py)
- Add QC rules to `RULES_NWP_NCEP`:
  - `cloud_cover_pct` $\in [0, 100]$
  - `visibility_m` $\ge 0$
  - `cloud_ceiling_m` $\ge 0$

### Test component

#### [MODIFY] [test_forecast_nwp.py](file:///Users/zach/.openclaw/workspace-chad/mostlyright-sdk/packages/weather/tests/test_forecast_nwp.py)
- Add `TestDisambiguationHeuristics` to test `_pick_record` logic with synthetic indices.
- Add GFS live smoke test to ensure no crashes.
- Add test coverage for new fields.

## Verification Plan

### Automated Tests
- `uv run pytest -m "not live" -q`
- `uv run pytest -k "test_forecast_nwp_live" -q` (smoke live check for HRRR + GFS)
- `uv run ruff check --fix . && uv run ruff format .`

### Manual Verification
- Verify generated schemas JSON files under `schemas/json/`.
