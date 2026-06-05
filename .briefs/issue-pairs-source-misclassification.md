# Issue Report Draft: Source Misclassification in `build_pairs_row` (`_pairs.py`)

## Title (proposed)
`bug(pairs): build_pairs_row misclassifies Open-Meteo records as IEM MOS when both sources requested — causes incorrect run selection and data corruption`

## Labels (proposed)
`bug`

## How Discovered
Found by Gemini 2.5 Pro during adversarial review of PR #64 (Open-Meteo rate limiting). The review scope was cache wiring + throttling, but the reviewer traced the data flow downstream and identified a pre-existing bug in the pairs join that becomes more impactful now that Open-Meteo data is cached and reliable.

## Problem

In `packages/core/src/mostlyright/_internal/_pairs.py`, `build_pairs_row()` separates IEM MOS and Open-Meteo forecast records using the **presence of `issued_at`**:

```python
# Current code (line ~297-298)
iem_records = [r for r in forecasts if r.get("issued_at")]
om_records = [r for r in forecasts if not r.get("issued_at")]
```

This split is incorrect. **Phase 20 Open-Meteo Previous Runs records carry a derived `issued_at`** (cycle math: `valid_at - publish_lag`, floored to model cycle hours). This means Open-Meteo records **do** have `issued_at` set, and get classified as `iem_records`.

### Impact

When `forecast_source=["iem_mos", "open_meteo"]` (or when `forecast_source=None` which defaults to `("iem_mos",)` but may include both):

1. Open-Meteo records are mixed into the IEM MOS pool.
2. Both sources' runs are grouped together under `_select_best_run(iem_records, market_close)`.
3. Run selection may pick an Open-Meteo cycle as the "best" IEM run (wrong model metadata).
4. The IEM-specific `_aggregate_fcst_temps_iem` path processes Open-Meteo rows, which carry different column names (`temp_c` vs `temperature_f`, `precip_probability` vs `precipitation_probability_pct`).
5. **Data corruption:** incorrect temperature/precipitation values in the output pairs.

When only `forecast_source="open_meteo"` is requested, the bug is masked because there are no IEM records to confuse — all records end up in `iem_records` but `_select_best_run` on a single run still works. The bug only manifests when **both sources are requested simultaneously**.

### Why It Wasn't Caught

- Open-Meteo `issued_at` was added in Phase 20 to support leakage detection.
- The existing test fixtures for `build_pairs_row` likely use records without `issued_at` (matching the old Open-Meteo seamless behavior where `issued_at` was null by design).
- The `research()` single-source path (`forecast_source="open_meteo"`) works despite the misclassification because `_select_best_run` still picks the only available run.
- CI skips `@pytest.mark.live` tests, so the mixed-source path may not be exercised in CI.

## Proposed Fix

Replace the `issued_at` presence check with an explicit source field inspection:

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

This is unambiguous — every record carries a `source` field (set by the fetchers: `"iem_mos"` for IEM, `"open_meteo.previous_runs"` / `"open_meteo.single_run"` / `"open_meteo.seamless"` / `"open_meteo.live"` for Open-Meteo).

### Secondary Issue: Open-Meteo Fallback Block Uses IEM Column Names

The current fallback block (when IEM MOS yields no data and OM records exist) calls `_aggregate_fcst_temps_openmeteo()` which expects a specific column format. If `_fetch_open_meteo_range` is the source (via #64's cache wiring), the rows carry `temperature_f`, `pop_6hr_pct`, and `qpf_6hr_in` (converted from Celsius in `_fetch_open_meteo_range` lines ~1449-1468). But the fallback block looks for `precipitation_probability_pct` — a different column name than what the research path produces.

A proposed fix would inline the aggregation and handle both column name conventions:

```python
if fcst_high is None and om_records:
    om_with_issued = [r for r in om_records if r.get("issued_at")]
    om_no_issued = [r for r in om_records if not r.get("issued_at")]

    best_om_records = []
    if om_with_issued:
        best_issued, best_om_records = _select_best_run(om_with_issued, market_close)
    else:
        best_om_records = om_no_issued

    if best_om_records:
        temps_f = []
        for r in best_om_records:
            if win_start_iso <= r.get("valid_at", "") <= win_end_iso:
                if r.get("temperature_f") is not None:
                    temps_f.append(r["temperature_f"])
                elif r.get("temperature_c") is not None:
                    temps_f.append(r["temperature_c"] * 9 / 5 + 32)
        if temps_f:
            fcst_high = max(temps_f)
            fcst_low = min(temps_f)

        # Support both pop_6hr_pct (research path) and precipitation_probability_pct (legacy)
        probs = []
        for r in window_om:
            if r.get("pop_6hr_pct") is not None:
                probs.append(r["pop_6hr_pct"])
            elif r.get("precipitation_probability_pct") is not None:
                probs.append(r["precipitation_probability_pct"])
        fcst_pop = max(probs) if probs else None
```

## Scope Decision Needed

This fix touches `build_pairs_row` — the core join function that every `research()` call passes through. Options:

1. **Bundle with this issue** — smallest PR, but mixes a #64 rate-limiting fix with a pairs-join correctness fix.
2. **Separate issue** (recommended) — `bug(pairs): Open-Meteo records misclassified as IEM in build_pairs_row`. Clean scope, independent review. Can reference #64 as the discovery context.

## Test Cases Needed

1. **Mixed source classification** — `build_pairs_row` with both IEM MOS and Open-Meteo records; verify OM records (with `issued_at`) are NOT placed in `iem_records`.
2. **Column name compatibility** — OM records from `_fetch_open_meteo_range` (carrying `temperature_f`, `pop_6hr_pct`, `qpf_6hr_in`) produce correct `fcst_high`, `fcst_low`, `fcst_pop`, `fcst_qpf` in the output.
3. **Single source regression** — `forecast_source="iem_mos"` only and `forecast_source="open_meteo"` only still produce correct results (no regression).

## TS Parity

If the TS SDK has an equivalent `build_pairs_row` or join function, the same source classification bug likely exists there. The TS parity note should reference `CROSS-SDK-SYNC.md`.

## References

- Discovered during review of: #64 (`fix(weather): wire forecast cache + weight-aware throttle + variable trim`)
- Related: Phase 20 OM-05 (`_fetch_open_meteo_range` — the function that produces the OM rows with `issued_at`)
- Related: `_aggregate_fcst_temps_openmeteo` (the existing helper that handles the fallback, may need column name update)
