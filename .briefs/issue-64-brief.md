# Brief: Fix Open-Meteo Rate Limiting (Issue #64)

**Repo:** `mostlyrightmd/mostlyright-sdk` @ `16d62de` (v1.5.2)
**Branch:** `fix/64-open-meteo-rate-limiting` (off `main`)
**Issue:** <https://github.com/mostlyrightmd/mostlyright-sdk/issues/64>
**Labels:** bug + enhancement

## Problem

Three compounding issues cause users to hit Open-Meteo free-tier rate limits during backtests:

1. **Forecast cache exists but is never called** — `read_forecast_cache` / `write_forecast_cache` in `cache.py:542-571` are only referenced in `test_cache_forecasts.py`. `_fetch_open_meteo_range()` in `research.py:1384` calls the network directly every time. A quant iterating on a model re-fetches identical historical data on every run.
2. **Politeness throttle counts requests, not weight** — `_OM_POLITE_DELAY_S = 0.2` caps at ~300 req/min nominally, but Open-Meteo bills by *weighted* call cost (`max(vars/10, 1) × max(days/14, 1) × locations`). A 1-year window with 18 variables weighs ~47 calls — exhausts the 600/min ceiling in ~13 stations.
3. **Over-fetching 18 variables on the `research()` path** — `_OM_VARIABLES_TO_FETCH` always requests 18 hourly variables, but `_fetch_open_meteo_range()` in `research.py:1384` only consumes `temp_c`, `precip_probability`, and `precipitation_mm` from the returned DataFrame. The other 15 variables are fetched, billed, and discarded.

## Scope

### Fix 1: Wire forecast cache into `_fetch_open_meteo_range` (highest impact)

**File:** `packages/core/src/mostlyright/research.py` — function `_fetch_open_meteo_range()` (line 1384)

**What to do:**
- After fetching the DataFrame from `fetch_open_meteo()`, group rows by `(station, source, model, year, month)` and write each group to the cache using `write_forecast_cache()`.
- Before the `fetch_open_meteo()` call, attempt to read cached data covering `[from_date, to_date]` using `read_forecast_cache()` for each month in the range.
- On cache hit: reconstruct the DataFrame from the cached rows (they're `list[dict]`) and skip the network call for that month range.
- On cache miss (partial or full): fetch from network for the missing portion, cache the result, and concatenate with any cached data.
- **Never cache `live` or `seamless` source rows** — `read_forecast_cache` and `write_forecast_cache` already enforce this (they return None / no-op for live/seamless sources).
- **Never cache the current UTC month** — already enforced by the cache functions.

**Cache key partitioning:** The cache is partitioned by `(station, source, model, year, month)` as Parquet files. For `_fetch_open_meteo_range`, the `source` will be `"open_meteo.previous_runs"` (since `mode="training"` is hardcoded in the caller at line 1404).

**Key consideration:** `read_forecast_cache` returns `list[dict]` — these are row dicts as stored, NOT the same format as `_parse_om_row` output. The cached rows are what `write_forecast_cache` receives, which in this case would be the row dicts from the fetched DataFrame. We need to ensure the cached format round-trips correctly through `_fetch_open_meteo_range`'s grouping logic. **Recommendation:** cache at the DataFrame level (convert to list[dict] for write, reconstruct DataFrame from list[dict] on read) rather than trying to cache the already-grouped `{date_iso: [row]}` structure.

**What NOT to change:** Do not modify `fetch_open_meteo()` itself. The cache should be applied at the `_fetch_open_meteo_range` level in `research.py`, which is the orchestration layer. This keeps the fetcher as a pure HTTP→DataFrame function (testable, composable).

### Fix 2: Throttle by weight, not request count

**File:** `packages/weather/src/mostlyright/weather/_fetchers/_open_meteo.py`

**What to do:**
- The file already has `_OM_POLITE_DELAY_S = 0.2` and the fetcher sleeps this amount after each HTTP call.
- After each successful HTTP call, calculate the weighted cost using `_weighted_call_cost(num_vars, num_days)` and scale the sleep: `time.sleep(_OM_POLITE_DELAY_S * ceil(weight))`.
- This means a 1.8-weight call sleeps 0.4s, a 3.9-weight call sleeps 0.8s, etc. — keeping the effective rate under 600/min regardless of per-call weight.
- **Also:** chunk date ranges >14 days client-side. Add `_chunk_date_range(from_date, to_date, max_days=14)` that splits into ≤14-day windows and issues separate HTTP calls per chunk, concatenating the DataFrames. This keeps per-call weight at ~1.8 (18 vars / 10 × 1) instead of ballooning. Single-Runs API is exempt (it uses `run=` and returns the full horizon).
- The chunking + weight-aware throttle together mean the existing `_OM_POLITE_DELAY_S` becomes a base rate that scales up proportionally.

**Constants to add:**
```python
_OM_MAX_DAYS_PER_CALL: int = 14    # Open-Meteo weight threshold
_OM_VAR_FREE_BUDGET: int = 10      # Open-Meteo free variable count per call
```

### Fix 3: Trim variables on the `research()` path

**File:** `packages/core/src/mostlyright/research.py` — function `_fetch_open_meteo_range()` (line 1384)

**What to do:**
- Pass `variables=("temperature_2m", "precipitation_probability", "precipitation")` to the `fetch_open_meteo()` call at line 1404 instead of letting it default to the full 18-variable set.
- This drops the per-call variable weight from 1.8 to 1.0 — cutting the weighted cost in half.
- The `fetch_open_meteo()` function already supports a `variables` parameter (added in a prior change — check `_validate_variables()` at line ~195 of `_open_meteo.py`). If not yet present, it needs to be added.
- The returned DataFrame will have all canonical columns but only 3 will be populated; the rest will be null. This is fine — `_fetch_open_meteo_range` already handles null values (lines 1431-1449).
- **Do NOT change the default behavior of `fetch_open_meteo()`** — the standalone API should still fetch all 18 variables for users who want the full DataFrame. Only trim on the `research()` orchestration path.

**IMPORTANT — verify `variables` param exists:** Check if `fetch_open_meteo()` already accepts `variables=`. Look for `_validate_variables()` and a `variables` parameter in the function signature. If it doesn't exist yet, it needs to be added to `_open_meteo.py` first (including the validation, the hourly param builder adjustment, and the row parser handling for missing columns).

## Files to Modify

| File | Change |
|------|--------|
| `packages/core/src/mostlyright/research.py` | Fix 1 (cache wiring) + Fix 3 (variable trim) in `_fetch_open_meteo_range()` |
| `packages/weather/src/mostlyright/weather/_fetchers/_open_meteo.py` | Fix 2 (weight-aware throttle + chunking) + possibly `variables` param if missing |

## Files to Create (Tests)

| File | What to test |
|------|-------------|
| `packages/core/tests/test_open_meteo_cache_wiring.py` | Cache hit/miss/partial in `_fetch_open_meteo_range` (mock HTTP, verify cache read/write) |
| `packages/weather/tests/test_open_meteo_throttle.py` | Weight-aware sleep calculation, chunking logic |
| `packages/core/tests/test_open_meteo_variables_trim.py` | `_fetch_open_meteo_range` passes trimmed variables, returned DF has only 3 non-null columns |

## Testing Approach

- **Fix 1 (cache):** Mock `fetch_open_meteo` to return a known DataFrame. First call → cache miss → network fetch → cache write. Second call → cache hit → no network call → same data. Verify with `unittest.mock.patch`.
- **Fix 2 (throttle):** Test `_chunk_date_range()` directly (pure function, no mocks needed). Test `_weighted_call_cost()` directly. Test that `fetch_open_meteo` with a long date range issues the correct number of chunked requests (mock HTTP, count calls).
- **Fix 3 (variables):** Mock `fetch_open_meteo`, verify it receives `variables=("temperature_2m", "precipitation_probability", "precipitation")` when called from `_fetch_open_meteo_range`. Verify the returned grouped dict still has `temperature_f`, `pop_6hr_pct`, `qpf_6hr_in` populated correctly.

## Constraints

- **Branch from `main`.** Do not commit directly to main.
- **TDD:** Write tests first, then implement.
- **Run `uv run ruff check --fix . && uv run ruff format .` before committing.**
- **Run `uv run pytest -m "not live" -q` to verify.**
- **Backward compatible:** `fetch_open_meteo()` standalone API must still fetch all 18 variables by default.
- **Cache format:** `list[dict]` of row dicts (Parquet-backed via `write_forecast_cache`).
- **Never cache live/seamless/current-month** — already enforced by cache functions.
- **Don't break `_fetch_open_meteo_range`'s return type:** `dict[str, list[dict[str, Any]]]` — keyed by settlement date ISO.

## Acceptance Criteria

1. `_fetch_open_meteo_range("KNYC", "2024-06-01", "2024-12-31", model="gfs_global")` caches results on first call and reads from cache on second call (no network).
2. `fetch_open_meteo("KNYC", "2024-01-01", "2024-12-31", model="gfs_global")` with a 1-year window issues ≤27 chunked requests (ceil(365/14) = 27) instead of 1 unbounded-weight call.
3. `_fetch_open_meteo_range` requests only 3 variables instead of 18.
4. Weighted sleep scales with call cost (verify with time mocking or assert sleep duration in tests).
5. All existing tests pass (`uv run pytest -m "not live" -q`).
6. New tests cover cache hit/miss, chunking, variable trimming.
