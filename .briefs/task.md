# Task: NWP Fields & Cloud Cover (Issue #63)

- [x] Phase 1: Fix GFS Precipitation Bug (Crash Prevention)
  - [x] Write unit tests for `_pick_record` heuristic and synthetic GFS duplicate `.idx` check in `test_forecast_nwp.py` (RED)
  - [x] Implement `_pick_record` helper and update `_extract_records` in `forecast_nwp.py` (GREEN)
  - [x] Run formatter, ruff check, and verify fast test suite (REFACTOR)
  - [x] Submit Phase 1 for user approval

- [x] Phase 2: Implement Cloud Cover, Visibility, & Ceiling Columns
  - [x] Add columns to `NwpForecastSchema`
  - [x] Export schema JSON using `export_schemas.py`
  - [x] Add VARIABLE_MAP entries for HRRR and GFS
  - [x] Register new short-names in `_GRIB_VAR_TO_CFGRIB_NAME`
  - [x] Setup `_empty_dataframe` and `nullable_numeric_cols`
  - [x] Add QC rules to `rules_nwp.py`
  - [x] Add unit tests and live smoke tests for new columns
  - [x] Verify test suite, format code, and push branch `fix/63-nwp-cloud-cover-precip`
