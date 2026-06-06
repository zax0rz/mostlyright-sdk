# `_pairs.py` source column incorrectly set for Open-Meteo rows

## How Discovered
Found by Gemini 2.5 Pro during adversarial review of PR #65 (Open-Meteo rate limiting). The review scope was cache wiring + throttling, but the reviewer traced the data flow downstream and identified a pre-existing bug in the pairs join.

## Problem

In `packages/core/src/mostlyright/_internal/_pairs.py`, `build_pairs_row()` separates IEM MOS and Open-Meteo forecast records using the **presence of `issued_at`**:

```python
iem_records = [r for r in forecasts if r.get("issued_at")]
om_records = [r for r in forecasts if not r.get("issued_at")]
```

This split is incorrect. **Phase 20 Open-Meteo Previous Runs records carry a derived `issued_at`** (cycle math: `valid_at - publish_lag`, floored to model cycle hours). Open-Meteo records with `issued_at` set get classified as IEM records.

### Impact

When both sources are requested (`forecast_source=["iem_mos", "open_meteo"]`):

1. Open-Meteo records are mixed into the IEM MOS pool
2. Run selection may pick an Open-Meteo cycle as the "best" IEM run
3. IEM-specific aggregation processes Open-Meteo rows (different column names)
4. **Data corruption:** incorrect temperature/precipitation values in output pairs

Bug is masked when only `forecast_source="open_meteo"` is used (all records end up in `iem_records` but `_select_best_run` still picks the only available run).

## Proposed Fix

Replace the `issued_at` presence check with explicit source field inspection:

```python
iem_records = [
    r for r in forecasts
    if not r.get("source", "").startswith("open_meteo")
]
om_records = [
    r for r in forecasts
    if r.get("source", "").startswith("open_meteo")
]
```

Every record carries a `source` field (`"iem_mos"` for IEM, `"open_meteo.previous_runs"` / etc. for Open-Meteo) — unambiguous.

## Secondary Issue

The fallback block uses IEM column names. OM records from `_fetch_open_meteo_range` carry `temperature_f` / `pop_6hr_pct` / `qpf_6hr_in` (converted from Celsius), but the fallback looks for `precipitation_probability_pct`. Needs column name compatibility handling.

## Test Cases Needed

1. **Mixed source classification** — both IEM MOS and OM records; verify OM records (with `issued_at`) are NOT placed in `iem_records`
2. **Column name compatibility** — OM records from research path produce correct `fcst_high`/`fcst_low`/`fcst_pop`/`fcst_qpf`
3. **Single source regression** — `iem_mos` only and `open_meteo` only still correct
