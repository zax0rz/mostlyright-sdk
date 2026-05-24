# TS parity fixtures — JSON projection

**Source of truth:** `tests/fixtures/parity/case_*.parquet` (the canonical v0.14.1 ground truth).
**Produced by:** `tests/fixtures/parity/export_for_ts.py`.
**Consumed by:** `packages-ts/meta/tests/parity/parity.test.ts` (Plan 08 — lands in TS-W2).

## What's in this directory

| File | Purpose |
|------|---------|
| `case_N_<STATION>_<FROM>_<TO>.json` | Row-equivalent JSON projection of the matching parquet fixture |
| `manifest.json` | Per-case metadata (station, dates, row_count, sha256, dtypes) |

## DO NOT EDIT THESE FILES BY HAND

Same discipline as the parent `parity/README.md`. The JSON files are derived
artifacts from the parquet fixtures — regenerate via the exporter only.

## Regenerate

Re-run only if the parquet fixtures change (which itself only happens on a
fresh v0.14.1 re-capture — see parent README §Re-capture):

```bash
uv run python tests/fixtures/parity/export_for_ts.py
```

The determinism gate (`tests/test_parity_ts_export.py::test_export_deterministic`)
asserts two consecutive runs produce byte-identical output.

## JSON shape

Each `case_N_*.json` is an array of objects. Each object is one settlement-date
row with 20 fields (per `pairs_to_dataframe` output, Mode 1):

- `date`: ISO `YYYY-MM-DD` string
- `station`: string (3-letter NWS code)
- `cli_high_f`, `cli_low_f`: integer (or float in case 4 where NaN cells coerce the column to float64)
- `cli_report_type`: string or null
- `obs_high_f`, `obs_low_f`, `obs_mean_f`, `obs_mean_dewpoint_f`, `obs_total_precip_in`: float or null (NaN → null)
- `obs_max_wind_kt`, `obs_max_gust_kt`, `obs_count`: integer (or float if NaN-coerced)
- `fcst_high_f`, `fcst_low_f`, `fcst_model`, `fcst_issued_at`, `fcst_pop_6hr_pct`, `fcst_qpf_6hr_in`: all `null` (Mode 1: forecast disabled)
- `market_close_utc`: string `"YYYY-MM-DDTHH:MM:SSZ"` or null

## Type-fidelity rules

The exporter MUST preserve numeric type:
- int64 columns → JSON integers (no trailing `.0`)
- float64 columns → JSON floats (full IEEE precision)
- NaN / NaT cells → JSON `null`
- Date column → ISO `YYYY-MM-DD` string (parquet stores `datetime64[ns]`)

Plan 08's parity test uses `JSON.parse` + per-column numeric-equality
assertions; integer-vs-float drift is a parity break, not noise.

## Why JSON instead of replaying parquet

`parquet-wasm` is deferred to v0.2 per `TS-SDK-DESIGN.md` §1 (NON-GOALS).
JSON is the only cross-language settlement-grade format the TS SDK can
consume without a binary dep in v0.1.0.
