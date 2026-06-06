# Gemini Review Brief: Issue #64 — Open-Meteo Rate Limiting Fix

## Context

You are reviewing a code change for Issue #64 in the `mostlyright-sdk` repo. This is a public SDK for weather prediction market research. The code was written by Claude Code and has already had one adversarial review from Blenda (the infrastructure agent). We need a second independent review from a different model perspective.

**Repo:** `mostlyrightmd/mostlyright-sdk` @ `16d62de` (v1.5.2, on `main` — changes are uncommitted working tree)
**Issue:** https://github.com/mostlyrightmd/mostlyright-sdk/issues/64

## What Changed

Two source files modified, three test files created:

| File | Change |
|------|--------|
| `packages/core/src/mostlyright/research.py` | Cache wiring (Fix 1) + variable trimming (Fix 3) in `_fetch_open_meteo_range()` |
| `packages/weather/src/mostlyright/weather/_fetchers/_open_meteo.py` | Weight-aware throttle + date chunking (Fix 2) + `variables=` param + `_validate_variables()` |
| `packages/core/tests/test_open_meteo_cache_wiring.py` | Tests for cache hit/miss and variable trimming on research path |
| `packages/weather/tests/test_open_meteo_variables_param.py` | Tests for `variables=` param (trim, unknown rejection, Single Runs no suffix) |
| `packages/weather/tests/test_open_meteo_window_chunking.py` | Tests for chunking (under/over 14 days, Single Runs exempt) |

## The Diff (research.py)

```diff
--- a/packages/core/src/mostlyright/research.py
+++ b/packages/core/src/mostlyright/research.py

+_OM_RESEARCH_VARIABLES: tuple[str, ...] = (
+    "temperature_2m",
+    "precipitation",
+    "precipitation_probability",
+)
+_OM_RESEARCH_SOURCE: str = "open_meteo.previous_runs"
+
+
 def _fetch_open_meteo_range(
     info: StationInfo,
     from_date: str,
     to_date: str,
     *,
     model: str,
 ) -> dict[str, list[dict[str, Any]]]:
-    """Phase 20 OM-05 — fetch Open-Meteo forecasts grouped by settlement date.
-    Wraps ``mostlyright.weather._fetchers._open_meteo.fetch_open_meteo`` in
-    training mode (Previous Runs API) and pivots its tabular DataFrame
-    into the ``{date_iso: [forecast_row, ...]}`` shape that
-    ``build_pairs(forecasts_by_date=...)`` expects. Each row carries
-    ``model`` / ``issued_at`` / ``valid_at`` / ``temperature_f`` /
-    ``pop_6hr_pct`` / ``qpf_6hr_in`` keys for build_pairs_row compatibility.
+    """Phase 20 OM-05 — fetch Open-Meteo forecasts grouped by settlement date.
+    Reads from the Phase 20 forecast cache before hitting the network. On a
+    cache miss the fetcher writes each elapsed month's rows back so subsequent
+    calls for the same window are served from disk. Only the 3 variables
+    consumed by the pairs join are requested (Fix 3 — cuts weighted call cost).
+    Returns the ``{date_iso: [forecast_row, ...]}`` shape that
+    ``build_pairs(forecasts_by_date=...)`` expects.
     """
+    from datetime import date as _date
+    from datetime import timedelta as _timedelta
+
     import pandas as pd

     from mostlyright.weather._fetchers._open_meteo import fetch_open_meteo
+    from mostlyright.weather.cache import read_forecast_cache, write_forecast_cache
+
+    # Enumerate (year, month) partitions covered by [from_date, to_date].
+    start = _date.fromisoformat(from_date)
+    end = _date.fromisoformat(to_date)
+    months: list[tuple[int, int]] = []
+    cur = _date(start.year, start.month, 1)
+    while cur <= end:
+        months.append((cur.year, cur.month))
+        cur = _date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
+
+    # Serve cached partitions; collect months that need a network fetch.
+    all_rows: list[dict[str, Any]] = []
+    missing: list[tuple[int, int]] = []
+    for y, m in months:
+        hit = read_forecast_cache(info.icao, _OM_RESEARCH_SOURCE, model, y, m)
+        if hit is not None:
+            all_rows.extend(hit)
+        else:
+            missing.append((y, m))
+
+    # Fetch the missing span and populate the cache.
+    if missing:
+        miss_start = max(_date(missing[0][0], missing[0][1], 1), start)
+        miss_end_y, miss_end_m = missing[-1]
+        last_day = _date(miss_end_y + (miss_end_m // 12), (miss_end_m % 12) + 1, 1) - _timedelta(
+            days=1
+        )
+        miss_end = min(last_day, end)
+
+        df_fetched = fetch_open_meteo(
+            info.icao,
+            miss_start.isoformat(),
+            miss_end.isoformat(),
+            model=model,
+            mode="training",
+            variables=_OM_RESEARCH_VARIABLES,
+        )
+
+        if df_fetched is not None and not df_fetched.empty:
+            for y, m in missing:
+                mask = (df_fetched["valid_at"].dt.year == y) & (
+                    df_fetched["valid_at"].dt.month == m
+                )
+                month_rows = df_fetched[mask].to_dict("records")
+                if month_rows:
+                    write_forecast_cache(info.icao, _OM_RESEARCH_SOURCE, model, y, m, month_rows)
+            all_rows.extend(df_fetched.to_dict("records"))

-    df = fetch_open_meteo(info.icao, from_date, to_date, model=model, mode="training")
     groups: dict[str, list[dict[str, Any]]] = {}
-    if df is None or df.empty:
+    if not all_rows:
         return groups
-    for _, row in df.iterrows():
+
+    for row in all_rows:
         ftime = row.get("valid_at")
         if ftime is None or (isinstance(ftime, float) and ftime != ftime):
             continue
```

## The Diff (_open_meteo.py)

```diff
--- a/packages/weather/src/mostlyright/weather/_fetchers/_open_meteo.py
+++ b/packages/weather/src/mostlyright/weather/_fetchers/_open_meteo.py

+from datetime import UTC, date, datetime, timedelta
+from math import ceil

+#: Open-Meteo per-call weight thresholds (free tier billing model).
+_OM_MAX_DAYS_PER_CALL: int = 14
+_OM_VAR_FREE_BUDGET: int = 10

+def _chunk_date_range(
+    from_date: str,
+    to_date: str,
+    max_days: int = _OM_MAX_DAYS_PER_CALL,
+) -> list[tuple[str, str]]:
+    """Split [from_date, to_date] into ≤max_days-day chunks."""
+    start = date.fromisoformat(from_date)
+    end = date.fromisoformat(to_date)
+    chunks: list[tuple[str, str]] = []
+    cur = start
+    while cur <= end:
+        chunk_end = min(cur + timedelta(days=max_days - 1), end)
+        chunks.append((cur.isoformat(), chunk_end.isoformat()))
+        cur = chunk_end + timedelta(days=1)
+    return chunks
+
+def _weighted_call_cost(num_vars: int, num_days: int) -> float:
+    """Open-Meteo weighted call cost: ceil(vars/10) * ceil(days/14)."""
+    return float(ceil(num_vars / _OM_VAR_FREE_BUDGET) * ceil(num_days / _OM_MAX_DAYS_PER_CALL))
+
+def _validate_variables(variables: tuple[str, ...] | None) -> tuple[str, ...]:
+    """Validate caller-supplied variables; return full default set when None."""
+    if variables is None:
+        return _OM_VARIABLES_TO_FETCH
+    unknown = [v for v in variables if v not in _OM_VAR_TO_COLUMN]
+    if unknown:
+        raise ValueError(
+            f"unknown OM variable(s) — {unknown!r}; allowed: {sorted(_OM_VAR_TO_COLUMN)}"
+        )
+    return tuple(variables)

-def _build_hourly_param(endpoint: str) -> str:
+def _build_hourly_param(
+    endpoint: str,
+    variables: tuple[str, ...] = _OM_VARIABLES_TO_FETCH,
+) -> str:
     if endpoint == OPEN_METEO_PREVIOUS_RUNS_URL:
-        return ",".join(f"{v}_previous_day1" for v in _OM_VARIABLES_TO_FETCH)
+        return ",".join(f"{v}_previous_day1" for v in variables)
-    return ",".join(_OM_VARIABLES_TO_FETCH)
+    return ",".join(variables)

 # In fetch_open_meteo():
+    vars_to_fetch = _validate_variables(variables)
+
+    # Chunk date ranges >14 days for Previous Runs API (no issued_at).
+    # Single Runs uses run= and returns a full 168h horizon — no chunking.
+    if issued_at is None and endpoint == OPEN_METEO_PREVIOUS_RUNS_URL:
+        chunks = _chunk_date_range(from_date, to_date)
+    else:
+        chunks = [(from_date, to_date)]
+
+    close_client = client is None
     if client is None:
         client = httpx.Client(timeout=timeout)
-        close_client = True
-
-    retrieved_at = datetime.now(UTC)
-    payload: dict[str, Any] = {}
+    frames: list[pd.DataFrame] = []
     try:
-        for attempt in range(_MAX_RETRIES + 1):
-            # ... retry logic unchanged ...
-        time.sleep(_OM_POLITE_DELAY_S)
+        for chunk_from, chunk_to in chunks:
+            params = { ... "hourly": _build_hourly_param(endpoint, vars_to_fetch), ... }
+            # ... retry loop per chunk (same 429/404 handling) ...
+
+            # Weight-aware polite delay scales with per-call cost.
+            num_days = (date.fromisoformat(chunk_to) - date.fromisoformat(chunk_from)).days + 1
+            cost = _weighted_call_cost(len(vars_to_fetch), num_days)
+            time.sleep(_OM_POLITE_DELAY_S * ceil(cost))
+
+            if payload:
+                frames.append(_project_payload_to_dataframe(...))
     finally:
         if close_client:
             client.close()
+
+    if not frames:
+        return _empty_df()
+    if len(frames) == 1:
+        return frames[0]
+    return pd.concat(frames, ignore_index=True)
```

## The Test Files

### test_open_meteo_cache_wiring.py (155 lines)
- Mocks `fetch_open_meteo`, verifies cache file written on first call, cache hit on second call (no network), and that `variables=` kwarg passes exactly 3 variables.

### test_open_meteo_variables_param.py (152 lines)
- Uses `httpx.MockTransport` to verify: default call requests 18 vars, trimmed call requests 3, unknown variable raises ValueError before HTTP, Single Runs has no `_previous_day1` suffix.

### test_open_meteo_window_chunking.py (143 lines)
- Uses `httpx.MockTransport` to verify: 7-day window = 1 call, 30-day window = 2-3 chunks (each ≤13 days), Single Runs mode = 1 call regardless of window size.

## Project Rules (CLAUDE.md)

These MUST be followed. Flag any violations:

1. **Never commit directly to main.** Always branch + PR. Branch name: `fix/64-open-meteo-rate-limiting`.
2. **TDD mandatory.** Tests first, RED → GREEN → REFACTOR. 80% coverage minimum.
3. **Two-reviewer loop** (Codex + Python Architect) before merging to `merged-vision`.
4. **Pre-commit hooks mandatory** — `uv run ruff check --fix . && uv run ruff format .` before committing.
5. **Pre-push hooks mandatory** — `uv run pytest -m "not live"` before pushing. No `--no-verify`.
6. **Dual-SDK rule:** Any public API change must include a TS parity section.
7. **All API calls direct from SDK.** No hosted API client calls anywhere.
8. **Branch workflow:** Feature branches off `merged-vision` (but this is a fix, so off `main` is acceptable per the issue workflow).
9. **Documentation:** Update CHANGELOG.md and relevant docs.

## Previous Review Findings (Blenda)

Already identified — verify these are handled:

1. **Missing partial cache hit test** — No test covers the case where some months are cached and some are missing (e.g., month 1 hits cache, month 2 misses → fetch only month 2, concatenate).
2. **NaT timestamp round-trip** — `df.to_dict("records")` converts pandas NaT timestamps. On cache read, these come back as... what? Could break the downstream `isinstance(ftime, float) and ftime != ftime` NaN check.
3. **Branch discipline** — Changes are on `main`, need to be on a branch.
4. **`_parse_om_row` with subset variables** — When only 3 variables are requested, `_parse_om_row` still iterates over all 18 `_OM_VAR_TO_COLUMN` entries. The unrequested variables will have `None` values from `series[idx]` falling through to the `else` branch when the key doesn't exist in `hourly_payload`. Verify this doesn't cause index errors on the `idx >= len(series)` check when `series` is None.

## What to Review

Please provide:

1. **Correctness:** Any logic bugs, edge cases, race conditions?
2. **API design:** Does `variables=` param fit the SDK's conventions? Is `_validate_variables` in the right place?
3. **Cache design:** Is caching at the `_fetch_open_meteo_range` level correct, or should it be lower (in `fetch_open_meteo` itself)? What about cache invalidation?
4. **Weight calculation:** Does `ceil(vars/10) * ceil(days/14)` match Open-Meteo's actual billing? Check against https://open-meteo.com/en/pricing.
5. **Chunking logic:** Any off-by-one errors in `_chunk_date_range`? What about a 1-day window or same-day from/to?
6. **Test coverage:** What's missing beyond the partial cache hit test?
7. **Performance:** The cache writes `to_dict("records")` which materializes all rows. For a 1-year window with hourly data, that's ~8,760 dicts per station. Is Parquet round-trip actually faster than the HTTP call for small windows?
8. **CLAUDE.md violations:** Any rules broken?
9. **TS parity:** Does this change need a TS parity note?
10. **Anything else** that a second pair of eyes catches?
