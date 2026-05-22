# Phase 1: v0.14.1 Parity Lift — Research

**Researched:** 2026-05-21
**Domain:** Local-first re-implementation of v0.14.1 `client.pairs()` against public weather APIs; byte-equivalent parity gate
**Confidence:** HIGH (codebase fully surveyed; v0.14.1 source paths verified; one structural surprise resolved — see §Critical Finding)

## Summary

Phase 1 ships byte-equivalent parity to `mostlyright==0.14.1`'s `client.pairs(station, from_date, to_date)` by lifting v0.14.1 parsers + merge logic into `tradewinds` and assembling a local pipeline (fetcher → parser → merge → cache → join) that replaces the hosted API call. Foundations (parsers, fetchers, 5 fixtures, internal utils) are DONE on `merged-vision`. Five gaps remain: (1) local parquet cache layer + filelock + LST-skip, (2) **observation merge policy** (AWC > IEM > GHCNh source-priority dedup, lifted from `ingest/storage/parquet.py::_dedup_rows`) and **climate merge policy** (report_type_priority strict-greater dedup, lifted from `_dedup_climate_rows`), (3) `research.py` orchestration that ports `client.pairs()` over local fetchers + parsers + merge + cache, (4) the parity test harness, (5) alpha1 PyPI publish (founder action).

**Primary recommendation:** Implement in this order to minimise rework — Wave 1: cache layer + merge policies (independent leaf modules) → Wave 2: research.py orchestration (consumes 1) → Wave 3: parity test + bug-fix loop until Day 3 gate green → Wave 4: founder publishes `tradewinds==0.1.0a1` + `tradewinds-weather==0.1.0a1` + `tradewinds-markets==0.0.1`.

## Critical Finding (Resolves Open Question #1 + #2)

**The Vu lift-lane doc is wrong about source paths.** `monorepo-v0.14.1/ingest/merge/policies.py` and `policies_climate.py` **do not exist**. There is no `_cache.py` in `src/mostlyright/` either. The v0.14.1 SDK is a thin HTTP client to a hosted API (`api.mostlyright.md`); all source-priority merging happens server-side. The fixtures encode the SERVER's already-merged output.

The real lift targets for merge are in **`monorepo-v0.14.1/ingest/storage/parquet.py`**:
- `_SOURCE_PRIORITY = {"awc": 3, "iem": 2, "ghcnh": 1}` (line 48)
- `_dedup_rows()` — dedupe observations by `(station_code, observed_at, observation_type)`, keep highest-priority source (line 246-261)
- `_dedup_climate_rows()` — dedupe climate by `(station_code, observation_date)`, strict-`>` on `report_type_priority`, first-seen wins on ties (line 477-494)

The fixture-captured `client.pairs()` chains: hosted `/observations` (already merged via these dedup rules) → `pairs.build_pairs()` (date grouping + aggregation). tradewinds Phase 1 must reproduce both halves locally.

## What's DONE on `merged-vision` (verified)

| Area | Path | Status |
|------|------|--------|
| Workspace bootstrap | `pyproject.toml`, uv workspace with 3 members | ✓ |
| Internal utils | `packages/core/src/tradewinds/_internal/`: `_http.py`, `_convert.py`, `_bounds.py`, `_capabilities.py`, `exceptions.py`, `versioning.py`, `models/{__init__,_base,observation,station,availability}.py`, `specs/*.json` (17 schemas) | ✓ |
| Weather parsers | `packages/weather/src/tradewinds/weather/`: `_awc.py`, `_iem.py`, `_climate.py`, `_ghcnh.py` (W3A codex fixes already applied) | ✓ |
| HTTP fetchers (NEW code) | `packages/weather/src/tradewinds/weather/_fetchers/`: `awc.py` (live last-168h only), `iem_asos.py` (month-aligned cache), `iem_cli.py` (whole-year), `ghcnh.py` (annual cache) | ✓ |
| Parity fixtures | `tests/fixtures/parity/case_{1..5}_*.parquet` (KNYC, KMDW, KLAX, KMIA, KMSY), with `README.md` + `capture_fixtures.py` | ✓ |
| Spike artifacts | `spike/research_spike.py` + `SPIKE_REPORT.md` — proves all 3 public endpoints work; **flags that AWC is last-168h-only and cannot serve historical ranges** | ✓ |
| v0.2 foundations | `packages/core/src/tradewinds/_v02/` (266 tests; OUT OF Phase 1 scope — Phase 2 will rebrand) | ✓ (do not touch) |

**Dev deps already added:** `pytest>=8.0`, `hypothesis>=6.100`, `pandas>=2.2`, `pyarrow>=17.0`, `respx>=0.23.1` (workspace `dev` group).

**AWC URL already correct** in `_fetchers/awc.py`: `https://aviationweather.gov/api/data/metar` (`/api/data/`, NOT deprecated `/cgi-bin/`). The ROADMAP §SC#4 LIFT-FIX is already applied; no further action needed for that line item.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PARITY-01 | `research(station, from_date, to_date)` byte-equivalent to v0.14.1 across 5 fixtures | Gap #3 (research.py) + Gap #4 (parity test) |
| PARITY-02 | Parity asserts dtype + value equivalence (`np.allclose(rtol=0, atol=0)`) | Gap #4 (parity test); see §Open Q3 for exact kwargs |
| PARITY-03 | `expected_dtypes.json` committed as ground truth | Already inferable from fixtures — dump dtypes from each .parquet into one JSON during parity-test wave |
| CORE-06 | HTTP layer has retry/timeout/User-Agent | `_internal/_http.py` already lifted with `download_with_retry`; audit only |
| CATALOG-06 | `_vendor/__init__.py` provenance | Phase 1 docs the lift inventory in `_internal/__init__.py` and `tradewinds/weather/__init__.py` (NOT in a `_vendor/` dir — that name is from ROADMAP §SC#5 but the actual lift went to `_internal/` and `weather/` directly). Reconcile naming in Wave 4. |
| PKG-02 | PEP 420 namespace — no double `tradewinds/__init__.py` | Already correct; verify with `uv build --all` + unzip in Wave 4 |
| PKG-04 | Wheel build verification | Wave 4 founder task |
| PKG-05 | `pandas>=2.2,<3.0` upper bound | Currently `pandas>=2.2` (no upper). Wave 4 must tighten to `pandas>=2.2,<3.0` in `packages/core/pyproject.toml` AND `packages/weather/pyproject.toml` |
| PKG-06 | pyarrow pinned to v0.14.1 lockfile version | v0.14.1 lockfile shows `pyarrow==23.0.1`; v0.14.1 pyproject says `pyarrow>=17.0`. **Open question:** pin to `>=17.0,<24.0` (floor + soft ceiling) or exact `==23.0.1`? Lift-source matches v0.14.1's floor; recommend `>=17.0,<24.0` to match v0.14.1 looseness. |
| CACHE-01 | Local parquet cache at `$HOME/.tradewinds/cache/v1/observations/{station}/{year}/{month}.parquet`, honors `TRADEWINDS_CACHE_DIR` | Gap #1 |
| CACHE-07 | Parquet write uses `version="2.6"`, `coerce_timestamps="us"`, `read_dictionary=[...]` | Gap #1 (cache write path) |

## Standard Stack (verified against codebase)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `pyarrow` | `>=17.0` (v0.14.1 lockfile: 23.0.1) | Parquet read/write for cache + fixtures + DataFrame return | Already pinned |
| `pandas` | `>=2.2,<3.0` (Phase 1 tightens upper) | DataFrame return for `research()` + parity test compares | Floor already pinned; ceiling needed |
| `filelock` | `>=3.12` | Concurrent-write protection for cache parquets | Already in `packages/weather/pyproject.toml` deps |
| `httpx` | `>=0.27` | HTTP fetch (via `_internal/_http.py`) | Already pinned |
| `jsonschema` | `>=4.21` | Observation/climate validation (transitive via parsers) | Already pinned |
| `pytest` | `>=8.0` | Test runner (parity test + smoke) | Workspace dev |

No new libraries needed. Don't hand-roll: filelock, parquet I/O, retry (use `_internal/_http.download_with_retry`).

## Gap 1: Cache Layer (CACHE-01, CACHE-07)

**v0.14.1 source:** No `_cache.py` exists in the SDK. Server-side ingest used `ingest/storage/parquet.py` (`_atomic_write_parquet`, `OBSERVATION_SCHEMA`, `CLIMATE_SCHEMA` lines 51-103, atomic write at line ~320, FileLock via `threading.Lock`). Lift the *schemas + atomic-write pattern*; build the filelock + LST-skip + path layout fresh.

**tradewinds destination:**
- `packages/weather/src/tradewinds/weather/cache.py` — public surface: `read_cache(station, year, month) -> pd.DataFrame | None`, `write_cache(station, year, month, df) -> None`, `cache_path(station, year, month) -> Path`.
- Path layout: `$HOME/.tradewinds/cache/v1/observations/{STATION}/{YYYY}/{MM}.parquet` (and `v1/climate/{STATION}/{YYYY}.parquet` for climate — annual granularity matches IEM CLI fetch).
- Honors `TRADEWINDS_CACHE_DIR` env var (override root).
- `version="2.6"`, `coerce_timestamps="us"` on every parquet write (CACHE-07).
- `filelock.FileLock(str(path) + ".lock", timeout=30)` on read AND write.
- LST current-month-skip: never read/write the parquet for the station's current LST month — that data is still settling. Use `tradewinds._internal._stations.py`-derived LST offset (`_lst_offset` will be needed — see Phase 1 dep on `snapshot.py` lift in Gap #3).

**Dependencies:** None (leaf module). Can be built in parallel with Gap #2.

**Test bar:**
- Unit: write→read roundtrip preserves dtypes (use a fixture parquet).
- Unit: current-month query returns `None` (no read), no parquet written.
- Unit: concurrent writers don't corrupt — spawn 2 processes via `multiprocessing`, both write to same path, only one wins, file is not truncated.
- Unit: `TRADEWINDS_CACHE_DIR=/tmp/foo` redirects path.

**Out of Phase 1 scope (deferred to Phase 3 per ROADMAP):** CACHE-02 cloud-sync FS detection, CACHE-03 LST-skip for *queried* month (Phase 1 only does cache-side current-month-skip), CACHE-04 30-day volatile window, CACHE-05 `.live` never cached, CACHE-06 source-identity preservation.

## Gap 2: Merge Policies (CORE-06 + supports PARITY-01)

**v0.14.1 source:** `monorepo-v0.14.1/ingest/storage/parquet.py`:
- Lines 47-48: `_SOURCE_PRIORITY = {"awc": 3, "iem": 2, "ghcnh": 1}`
- Lines 246-261: `_dedup_rows()` — observations dedupe on `(station_code, observed_at, observation_type)`, keep highest source-priority
- Lines 477-494: `_dedup_climate_rows()` — climate dedupe on `(station_code, observation_date)`, strict-`>` on `report_type_priority`, first-seen on ties (first "final" wins over later "final")

**tradewinds destination:**
- `packages/core/src/tradewinds/_internal/merge/__init__.py` — re-exports `merge_observations`, `merge_climate`, `SOURCE_PRIORITY`, `REPORT_TYPE_PRIORITY`
- `_internal/merge/observations.py` — port `_dedup_rows`; rename to `merge_observations(rows) -> rows` returning sorted list
- `_internal/merge/climate.py` — port `_dedup_climate_rows`; rename to `merge_climate(rows) -> rows`

Why `_internal/merge/` not `weather/_merge/`: both observation and climate merge live in `_internal/` because they operate on dicts emitted by parsers (which themselves live in `weather/`). Putting merge under `_internal/` matches the v0.14.1 ingest layout (storage = below sources).

**Dependencies:** None (pure functions on list[dict]). Build in parallel with Gap #1.

**Test bar:**
- Lift verbatim `monorepo-v0.14.1/tests/test_parquet.py` cases on `_dedup_rows` / `_dedup_climate_rows`. Rename imports; assert identical outputs row-by-row.
- Add the AWC-gap-IEM-fills synthetic case from `monorepo-v0.14.1/tests/test_merge_scheduler.py::TestMergeCycle::test_awc_gap_filled_by_iem` (lines 296-336) — verifies the AWC+IEM merge yields no missing hours when AWC has gaps. This is the case-5 fixture's reason for being.

## Gap 3: `research.py` orchestration (PARITY-01 — load-bearing)

**v0.14.1 source:** Two files compose `client.pairs()`:
1. `monorepo-v0.14.1/src/mostlyright/client.py::MostlyRightClient.pairs()` (lines 527-748) — orchestrates: paginated `/observations` fetch (HOSTED), groups by settlement-date via `settlement_date_for()`, fetches `/climate`, optionally fetches forecasts, calls `build_pairs()`.
2. `monorepo-v0.14.1/src/mostlyright/pairs.py` (447 lines) — pure date-aggregation: `build_pairs_row()` aggregates METARs per settlement date, joins climate, joins forecasts, emits 19-col row. **No HTTP, no merge — pure data shaping.**

Also needed:
- `monorepo-v0.14.1/src/mostlyright/snapshot.py` (468 lines) — `_lst_offset`, `_station_code_normalized`, `settlement_window_utc`, `settlement_date_for`. **Pure functions, no HTTP. Lift verbatim.**
- `monorepo-v0.14.1/src/mostlyright/_stations.py` — station → IATA + LST offset map.

**tradewinds destination:**
- `packages/core/src/tradewinds/snapshot.py` — lift verbatim, rename imports `mostlyright.*` → `tradewinds._internal.*` (or `tradewinds.*` for snapshot itself).
- `packages/core/src/tradewinds/_internal/_stations.py` — lift verbatim.
- `packages/core/src/tradewinds/research.py` — NEW orchestrator (NOT a verbatim lift of `client.py::pairs()`; that calls hosted APIs). Composes:
  ```python
  def research(station: str, from_date: str, to_date: str, *, include_forecast: bool = False, as_dataframe: bool = True, ...) -> pd.DataFrame:
      # 1. Normalize station (KNYC -> NYC)
      # 2. Compute extended_to (+1 day, for east-of-UTC stations)
      # 3. For each month in [from_date, extended_to]:
      #      raw_obs += _fetch_observations_for_month(station, year, month)  # cache-first
      # 4. raw_climate = _fetch_climate(station, from_date, to_date)  # cache-first, annual fetch
      # 5. Group obs by settlement_date_for(observed_at, station)
      # 6. Build climate_by_date dict
      # 7. rows = build_pairs(code, dates, obs_by_date, climate_by_date, ...)
      # 8. Return pairs_to_dataframe(rows) -- LIFTED verbatim from pairs.py
  ```
  - Lift `build_pairs`, `build_pairs_row`, `date_range`, `pairs_to_dataframe`, `pairs_to_toon` VERBATIM from `pairs.py` into `research.py` (or co-locate as `tradewinds._internal/_pairs.py`).
- `_fetch_observations_for_month(station, year, month)`:
  - Try cache → on miss, call `iem_asos.download_iem_asos()` (already exists), parse via `weather/_iem.py::parse_iem_file` (already exists), optionally augment with `awc.py::fetch_awc_metar` (only works for last-168h windows — see SPIKE_REPORT note), optionally augment with `ghcnh.py` (already exists) → merge via `_internal.merge.merge_observations` → write cache → return.
  - **AWC-only-for-last-168h constraint:** for any month older than ~last week, skip AWC fetcher entirely (it returns empty); rely on IEM + GHCNh. For current/recent month, fold in AWC's higher-priority rows during merge.

**Dependencies:** Gap #1 (cache) + Gap #2 (merge) + existing parsers + existing fetchers.

**Test bar:**
- Unit: parity-clean test against ONE fixture (case 1 KNYC week) — full integration smoke, no network (use respx to mock HTTP).
- Defer full 5-fixture green to Gap #4.
- Lift `monorepo-v0.14.1/tests/` whatever exercises `build_pairs`, `build_pairs_row`, `settlement_window_utc`, `settlement_date_for`, `pairs_to_dataframe` — rename imports, all green.

**Codex high-reasoning review required** (per ROADMAP §Constraints + Vu lift-lane Day 2 §D).

## Gap 4: Parity Test (PARITY-01, PARITY-02, PARITY-03)

**No v0.14.1 source** — this is net-new validation infrastructure.

**tradewinds destination:** `tests/test_parity.py` at the repo root (NOT under packages/ — workspace-level integration test).

Content (per `tests/fixtures/parity/README.md` §Day-3-parity-test-contract):
```python
import json
from pathlib import Path
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
import tradewinds

FIXTURES = Path(__file__).parent / "fixtures" / "parity"
CASES = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),   # NOT KORD (whitelist constraint)
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]

def _canon(df: pd.DataFrame) -> pd.DataFrame:
    return df.reset_index().sort_values(["date", "station"]).reset_index(drop=True)

@pytest.mark.parametrize("n,station,frm,to", CASES)
def test_parity_case(n, station, frm, to):
    expected = pd.read_parquet(FIXTURES / f"case_{n}_{station}_{frm}_{to}.parquet")
    actual = tradewinds.research(station, frm, to)
    # PARITY-02: dtype check + value check
    assert _canon(actual).dtypes.equals(_canon(expected).dtypes), (
        f"dtype mismatch case {n}\nactual: {dict(actual.dtypes)}\nexpected: {dict(expected.dtypes)}"
    )
    assert_frame_equal(_canon(actual), _canon(expected), check_dtype=True, check_exact=True)
```

**PARITY-03 ground-truth dtypes:** capture once via a fixture-prep script that runs `for case in CASES: df = pd.read_parquet(...); ground_truth[case] = df.dtypes.to_dict()`; write to `tests/fixtures/parity/expected_dtypes.json`. Commit. Already partially derivable — case 1 KNYC dtypes verified (this research): `station` is object, `cli_high_f`/`cli_low_f`/`obs_max_wind_kt`/`obs_max_gust_kt`/`obs_count` are int64, `obs_high_f/low_f/mean_f/mean_dewpoint_f/obs_total_precip_in` are float64, all `fcst_*` are object (None — since `include_forecast=False`), `cli_report_type`/`market_close_utc` are object.

**Dependencies:** Gap #3 (research.py).

**Test bar:** ALL 5 cases green. This IS the hard gate. Sprint 0 ships only if green.

**Risks during this wave:**
- v0.14.1 server emits `station` as 3-letter IATA ("NYC") not 4-letter ICAO ("KNYC"). `pairs.py::_station_code_normalized` strips leading "K". tradewinds must match this exactly.
- The fixtures used the hosted API's already-merged observations. tradewinds re-merges locally — any subtle AWC/IEM/GHCNh inclusion difference produces row-level diffs.
- `assert_frame_equal(check_exact=True)` is strict on floats. `obs_mean_f`/`obs_mean_dewpoint_f` are computed averages — pure Python `sum() / len()` should be bit-identical across v0.14.1 and tradewinds **IF** the input float64 set is identical, but ordering matters (commutative add isn't associative in IEEE 754). Pre-sort observations by `observed_at` before averaging.

## Gap 5: Alpha PyPI Publish (PKG-02, PKG-04, PKG-05, PKG-06)

**Founder action** — Claude CANNOT execute this autonomously (requires `PYPI_TOKEN`).

**Pre-publish checklist (Claude DOES these):**
- [ ] Bump `version` to `0.1.0a1` in `packages/core/pyproject.toml` and `packages/weather/pyproject.toml`. Keep `packages/markets/pyproject.toml` at `0.0.1` (no impl yet).
- [ ] Tighten `pandas>=2.2` → `pandas>=2.2,<3.0` in BOTH core + weather pyproject.toml (PKG-05).
- [ ] Tighten `pyarrow>=17.0` → `pyarrow>=17.0,<24.0` in BOTH core + weather pyproject.toml (PKG-06 — matches v0.14.1 floor; soft upper avoids future surprise).
- [ ] Confirm no `__init__.py` exists at `packages/weather/src/tradewinds/` or `packages/markets/src/tradewinds/` — only at `packages/core/src/tradewinds/__init__.py` (PKG-02).
- [ ] Run `uv build --all-packages` locally → confirm three wheels produced.
- [ ] Unzip each wheel; verify only `tradewinds-0.1.0a1-*.whl` contains `tradewinds/__init__.py` (PKG-04).

**Publish (founder ONLY):**
```bash
uv publish dist/tradewinds-0.1.0a1*.whl dist/tradewinds-0.1.0a1*.tar.gz
uv publish dist/tradewinds_weather-0.1.0a1*
uv publish dist/tradewinds_markets-0.0.1*  # if not already on PyPI
```
(Requires `UV_PUBLISH_TOKEN` env var.)

**Trusted publishing via GH Actions:** Deferred to Phase 4 per ROADMAP §Phase-4-SC#3. Phase 1 ships via `uv publish` + token only.

**Test bar:**
- Post-publish smoke: in a clean venv, `pip install "tradewinds[parquet]==0.1.0a1" "tradewinds-weather[parquet]==0.1.0a1"` → `python -c "import tradewinds as tw; tw.research('KNYC', '2025-04-01', '2025-04-07')"` returns a DataFrame.

## Suggested Implementation Order

```
Wave 1 (parallel — leaf modules):
  - Cache layer (Gap #1)
  - Merge policies (Gap #2)
  - Lift snapshot.py + _stations.py from v0.14.1 (prereq for Gap #3)

Wave 2 (sequential after Wave 1):
  - research.py orchestration (Gap #3) — REQUIRES Codex high-reasoning review

Wave 3 (sequential after Wave 2):
  - Parity test (Gap #4) — pair-debug failures with cross-lane review
  - HARD GATE: all 5 fixtures green

Wave 4 (sequential after Wave 3):
  - Pre-publish hygiene (Claude does)
  - Founder publishes alpha1 wheels (founder does)
  - Post-publish smoke test in clean venv
```

## Open Questions

1. ~~Is `_cache.py` in v0.14.1?~~ **RESOLVED:** No. v0.14.1 SDK is a hosted-API client with no local cache. Cache is server-side at the ingest layer (`ingest/storage/parquet.py`). Build fresh in tradewinds.

2. ~~Does v0.14.1 `pairs.py` call merge?~~ **RESOLVED:** No. Merge is server-side; `pairs.py` is pure aggregation over already-merged dicts. tradewinds must do BOTH locally.

3. **Exact `assert_frame_equal` kwargs for PARITY-02?** Recommend `check_dtype=True, check_exact=True, check_like=False` (preserve column order — column order is part of the contract). For floats, `check_exact=True` requires bit-identical; if AWC/IEM ordering subtly shifts a `sum() / len()`, we'll see a 1-ULP diff. **Fallback if bit-identical fails:** `check_exact=False, rtol=0, atol=1e-9`. Decide during Wave 3 based on observed diffs.

4. **`include_forecast` parity coverage?** The 5 captured fixtures all used `include_forecast=False` (every `fcst_*` col is `None`/object). Phase 1 only needs Mode 1 (no forecast). Forecast wiring is Phase 2+ — but `build_pairs()` still emits the 6 `fcst_*` columns as None. **OK to skip forecast HTTP for Phase 1**; just ensure `build_pairs()` lift preserves the null-fcst-col emission.

5. **`research()` vs `pairs()` parameter parity?** v0.14.1 `client.pairs()` accepts kwargs: `include_forecast`, `forecast_model`, `as_dataframe`, `format`, `tz_override`. tradewinds `research()` should accept the same set to be a drop-in. **Default `as_dataframe=True`** in tradewinds (v0.14.1 defaults to `False` → list[dict]; tradewinds users expect DataFrames). The parity test asserts DataFrame output regardless.

6. **CATALOG-06 vs CATALOG-01..05 — what's left for Phase 1?** CATALOG-06 = lift inventory documentation. Phase 2 builds the eager adapter registry (CATALOG-01..05). For Phase 1, write a `## Lift Inventory` block in `packages/core/src/tradewinds/_internal/__init__.py` and `packages/weather/src/tradewinds/weather/__init__.py` documenting:
   - Source file in monorepo-v0.14.1 (path + git SHA from `git -C monorepo-v0.14.1 rev-parse HEAD`)
   - Date lifted
   - Modifications (e.g., import-rename, codex W3A fixes)
   No new `_vendor/` directory — the lift went directly into `_internal/` and `weather/` already; CATALOG-06 just adds the provenance docstring.

7. **Where do `pairs_to_toon` / TOON serializer go?** v0.14.1 `pairs.py::pairs_to_toon` imports `mostlyright._toon`. `_toon` is not lifted yet in tradewinds. Phase 1: either (a) lift `_toon.py` to `_internal/_toon.py` and keep `pairs_to_toon`, or (b) drop `format="toon"` from `research()` (defer to Phase 2 `CORE-05` format serializers). Recommend (b) — Phase 1 only needs DataFrame output for the parity test; TOON is downstream of Phase 2's format-serializer task.

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| R1 | Local merge produces row-level diffs vs hosted-API fixtures (e.g., AWC included extra obs the hosted API didn't, or vice versa) | HIGH | HARD GATE FAIL | Strict TDD on merge policies + lift v0.14.1's `test_parquet.py` cases verbatim before integration. Pair-debug with Codex. |
| R2 | Float averaging produces 1-ULP diff (`obs_mean_f`, `obs_mean_dewpoint_f`) due to non-associative IEEE add | MEDIUM | HARD GATE FAIL | Pre-sort observations by `observed_at` before averaging. Match v0.14.1's `_obs_aggregates` summation order. Fallback: relax `check_exact=False` with `atol=1e-9`. |
| R3 | `station` column convention mismatch ("NYC" vs "KNYC") | LOW | HARD GATE FAIL on every fixture | `pairs.py::_station_code_normalized` strips leading "K" — port unchanged. Test on case 1. |
| R4 | `fcst_*` columns dtype drift — fixtures show object (None) but if tradewinds emits float64 NaN, parity breaks | LOW | HARD GATE FAIL | `build_pairs_row()` already emits dict-with-None when `forecasts is None` (parity-clean). Don't pass `forecasts={}`; pass `forecasts_by_date=None`. |
| R5 | AWC last-168h limitation means hist-only sources for old months — AWC > IEM > GHCNh priority never fires on older fixtures | MEDIUM | Merge logic untested in hot path | Case 5 (KMSY Hurricane Francine 2024-09) is in the past — AWC won't have it; merge will use IEM only. Phase 1 merge correctness still tested via Gap #2 unit tests + synthetic AWC-gap fixture. Cross-source merge in real `research()` will only be exercised on current-week queries (Phase 3 territory). |
| R6 | `pandas` 2.x dtype subtleties — `Int64` (nullable) vs `int64` (numpy) — fixtures captured against v0.14.1 with pandas 2.x; tradewinds default could be different | LOW-MED | HARD GATE FAIL on dtype check | Fixture inspection (this research) confirms fixtures use numpy `int64`/`float64`/`object` (no nullable types). Match in `pairs_to_dataframe()` lift. |
| R7 | `pyarrow>=17.0` allows 17 through 25+; behavioral drift between major versions | LOW | HARD GATE FAIL on parquet roundtrip | Pin upper to `<24.0` (PKG-06 interpretation); test on the lockfile-pinned 23.0.1. |
| R8 | Capture script worked once with `MOSTLYRIGHT_API_KEY` shim — if fixtures are lost or need regen, only operator vuhcze@gmail.com can re-capture | LOW | Cannot reproduce | Keep fixtures committed to repo (already done). README documents the constraint. |
| R9 | The 20-station whitelist on `api.mostlyright.md` means we can never re-capture for any non-whitelisted station — case 2 already had to swap KORD→KMDW | LOW | Scope limitation, not gate fail | Documented in README.md. tradewinds local-first SDK has no such whitelist. |
| R10 | `_internal/snapshot.py` or `_stations.py` not yet lifted — Wave 1 blocker if missed | HIGH (process) | Delays Wave 2 | Explicitly list in Wave 1 task plan (currently the `_internal/__init__.py` docstring says these are NOT listed). |

## Architecture Patterns

### Pattern 1: Cache-first orchestration
**What:** Each `_fetch_observations_for_month()` call: `try cache → on miss, fetch + parse + merge + write_cache → return df`.
**When:** Inside `research.py` for every month-station pair.
**Example:** see pseudocode in §Gap-3-research.py.

### Pattern 2: Pure-function merge
**What:** `merge_observations(rows: list[dict]) -> list[dict]` and `merge_climate(rows: list[dict]) -> list[dict]` — no I/O, no state, no `pd.DataFrame`. Operate on dicts emitted by parsers.
**When:** Always called after multi-source fetch, before cache write.
**Example:** lift verbatim from `ingest/storage/parquet.py::_dedup_rows` / `_dedup_climate_rows`.

### Pattern 3: Atomic parquet write
**What:** Write to `.tmp` next to dest, then `os.rename(tmp, dest)`. Wrapped in `FileLock(str(dest) + ".lock")`.
**When:** All cache writes.
**Source:** `monorepo-v0.14.1/ingest/storage/parquet.py::_atomic_write_parquet` (lift the function; replace threading.Lock with filelock.FileLock for cross-process safety).

### Anti-Patterns to Avoid
- **Caching `.live` endpoints:** AWC `awc.py` only serves last-168h — caching wastes disk and risks stale data. Phase 1 skips AWC caching (CACHE-05 is Phase 3, but the principle still applies).
- **Returning `pd.DataFrame` from cache layer:** keep cache I/O on `list[dict]` ⇄ parquet; DataFrame conversion only in `pairs_to_dataframe()`. Decouples cache from pandas version.
- **Re-parsing on every read:** `_iem.py` parses CSVs to dicts; cache them as parquet so subsequent reads skip re-parsing. (Current `iem_asos.py` caches the RAW CSV; we want the PARSED dicts in cache parquet.)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent file locking | `os.O_EXCL` + manual retry | `filelock.FileLock` | Cloud-sync FS, cross-process, cross-platform edge cases. v0.14.1 server used `threading.Lock` (in-process only) which is wrong for our local cache. |
| Atomic file write | `open(path, "w")` directly | Stage to `.tmp` then `os.rename(tmp, dest)` (lift `_atomic_write_parquet`) | Partial writes on crash, corrupted parquet on Ctrl-C |
| HTTP retry | manual try/except loop | `tradewinds._internal._http.download_with_retry` (already lifted) | Exponential backoff, status-code logic, atomic write all in one |
| Source-priority dedup | new logic | `merge_observations()` lifting `_dedup_rows()` | v0.14.1 has 4 tests around this exact policy; lift carries the tests |
| Settlement window math | new logic | Lift `snapshot.py::settlement_window_utc`, `settlement_date_for`, `_lst_offset` verbatim | LST not LDT, market-close hour, DST handling — already correct in v0.14.1 |

## Common Pitfalls

### Pitfall 1: Settlement date drift on west-coast stations
**What goes wrong:** KLAX settlement window extends to next-day 07:59Z (PST). If you slice by UTC date, you miss the late-evening obs.
**Why:** `settlement_date_for()` is LST-aware; UTC date slicing is not.
**How to avoid:** Use `settlement_date_for(observed_at, station)` to group, NEVER `observed_at[:10]`.
**Warning signs:** case 3 (KLAX) row count differs from fixture; `obs_high_f` differs.

### Pitfall 2: Whole-year IEM CLI fetch on multi-year ranges
**What goes wrong:** case 4 spans 2024-12 → 2025-11 (year boundary). One CLI fetch per year = 2 fetches.
**How to avoid:** `_fetch_climate(station, from_date, to_date)` iterates years inclusively; cache key is `{station}/cli_{YYYY}.json`.

### Pitfall 3: `obs_count` includes SPECI in v0.14.1
**What goes wrong:** If tradewinds merges METAR-only and skips SPECI, `obs_count` drops.
**How to avoid:** Both report types (`obs_type=3` METAR + `obs_type=4` SPECI) lifted in `iem_asos._monthly_chunks`. Verify the fetcher emits both.
**Warning signs:** `obs_count` field differs by ~30% on busy stations.

### Pitfall 4: TestPyPI ≠ PyPI version availability
**What goes wrong:** Founder publishes to TestPyPI to dry-run, then publishes same version `0.1.0a1` to real PyPI — but if TestPyPI accepted it, the artifact in TestPyPI is forever; no re-upload.
**How to avoid:** Use `0.1.0a1.dev1` etc for TestPyPI runs; reserve `0.1.0a1` for real PyPI.

## Code Examples

### Cache read with current-month-skip (Gap #1)
```python
# packages/weather/src/tradewinds/weather/cache.py
import os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from filelock import FileLock
from tradewinds._internal._stations import _lst_offset  # lifted from v0.14.1
from tradewinds._internal.merge import merge_observations  # Gap #2

CACHE_VERSION = "v1"
DEFAULT_ROOT = Path.home() / ".tradewinds" / "cache"

def _cache_root() -> Path:
    return Path(os.environ.get("TRADEWINDS_CACHE_DIR", DEFAULT_ROOT))

def cache_path(station: str, year: int, month: int) -> Path:
    return _cache_root() / CACHE_VERSION / "observations" / station / str(year) / f"{month:02d}.parquet"

def _is_current_lst_month(station: str, year: int, month: int) -> bool:
    """Returns True if (year, month) is the current month in the station's LST."""
    offset = _lst_offset(station)  # negative timedelta for stations west of UTC
    now_lst = datetime.now(timezone.utc) + offset
    return now_lst.year == year and now_lst.month == month

def read_cache(station: str, year: int, month: int) -> list[dict] | None:
    path = cache_path(station, year, month)
    if not path.exists() or _is_current_lst_month(station, year, month):
        return None
    with FileLock(str(path) + ".lock", timeout=30):
        if not path.exists():  # double-check inside lock
            return None
        table = pq.read_table(path)
        return table.to_pylist()

def write_cache(station: str, year: int, month: int, rows: list[dict]) -> None:
    if _is_current_lst_month(station, year, month):
        return
    path = cache_path(station, year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with FileLock(str(path) + ".lock", timeout=30):
        # Reuse the OBSERVATION_SCHEMA from monorepo-v0.14.1/ingest/storage/parquet.py
        from tradewinds._internal.merge.observations import OBSERVATION_SCHEMA
        table = pa.Table.from_pylist(rows, schema=OBSERVATION_SCHEMA)
        pq.write_table(
            table, tmp,
            version="2.6",
            coerce_timestamps="us",
        )
        tmp.rename(path)
```

### Merge port (Gap #2)
```python
# packages/core/src/tradewinds/_internal/merge/observations.py
# Lifted from monorepo-v0.14.1/ingest/storage/parquet.py:246-261 (git SHA: <fill>)

SOURCE_PRIORITY: dict[str, int] = {"awc": 3, "iem": 2, "ghcnh": 1}

def merge_observations(rows: list[dict]) -> list[dict]:
    """Dedupe observations by (station_code, observed_at, observation_type).
    Keeps highest-priority source for each key.
    """
    best: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["station_code"], row["observed_at"], row["observation_type"])
        priority = SOURCE_PRIORITY.get(row.get("source", ""), 0)
        if key not in best:
            best[key] = row
        else:
            existing_priority = SOURCE_PRIORITY.get(best[key].get("source", ""), 0)
            if priority > existing_priority:
                best[key] = row
    return list(best.values())
```

### research.py skeleton (Gap #3)
```python
# packages/core/src/tradewinds/research.py
# NEW orchestrator. Lifts pairs.py logic; replaces hosted-API fetch with local pipeline.

from __future__ import annotations
from datetime import date as _date, timedelta as _td
from typing import Any
import pandas as pd

from tradewinds._internal.merge import merge_observations, merge_climate
from tradewinds.snapshot import settlement_date_for, _station_code_normalized
# pairs.py functions lifted into _internal._pairs
from tradewinds._internal._pairs import build_pairs, date_range, pairs_to_dataframe

def research(
    station: str,
    from_date: str,
    to_date: str,
    *,
    include_forecast: bool = False,  # Phase 1: forecast columns emitted as None
    forecast_model: str | None = None,
    as_dataframe: bool = True,
    tz_override: str | None = None,
) -> pd.DataFrame | list[dict]:
    code = _station_code_normalized(station)
    dates = date_range(from_date, to_date)
    extended_to = (_date.fromisoformat(to_date) + _td(days=1)).isoformat()

    raw_obs = _fetch_observations_range(code, from_date, extended_to)
    raw_climate = _fetch_climate_range(code, from_date, to_date)

    obs_by_date: dict[str, list[dict]] = {d: [] for d in dates}
    for r in raw_obs:
        d = settlement_date_for(r["observed_at"], code, tz_override=tz_override)
        if d in obs_by_date:
            obs_by_date[d].append(r)

    climate_by_date: dict[str, dict | None] = {}
    for r in raw_climate:
        if r.get("observation_date"):
            climate_by_date[r["observation_date"]] = r

    rows = build_pairs(
        code, dates, obs_by_date, climate_by_date,
        forecasts_by_date=None,  # Phase 1 mode 1 only
        forecast_model=forecast_model,
        tz_override=tz_override,
    )
    return pairs_to_dataframe(rows) if as_dataframe else rows
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest>=8.0` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest -m "not live" -q` |
| Full suite command | `uv run pytest -q` (includes `live` tests) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PARITY-01 | research() byte-equivalent to v0.14.1 fixtures | integration | `pytest tests/test_parity.py -x` | ❌ Wave 3 |
| PARITY-02 | dtype + value equivalence assertion | integration | `pytest tests/test_parity.py::test_parity_case -x` | ❌ Wave 3 |
| PARITY-03 | expected_dtypes.json committed | integration (snapshot) | `pytest tests/test_parity.py::test_dtypes_match_ground_truth -x` | ❌ Wave 3 |
| CORE-06 | HTTP retry/timeout/UA in `_internal/_http` | unit | `pytest packages/core/tests/_internal/test_http.py -x` | ✅ |
| CACHE-01 | Path layout + env-var override | unit | `pytest packages/weather/tests/test_cache.py::test_path_layout -x` | ❌ Wave 1 |
| CACHE-01 | LST current-month-skip | unit | `pytest packages/weather/tests/test_cache.py::test_current_month_skip -x` | ❌ Wave 1 |
| CACHE-07 | parquet `version="2.6"` + `coerce_timestamps="us"` | unit | `pytest packages/weather/tests/test_cache.py::test_parquet_options -x` | ❌ Wave 1 |
| CORE-06 (merge) | `merge_observations` AWC>IEM>GHCNh priority | unit | `pytest packages/core/tests/_internal/merge/test_observations.py -x` | ❌ Wave 1 |
| CORE-06 (merge) | `merge_climate` strict-`>` priority + first-seen | unit | `pytest packages/core/tests/_internal/merge/test_climate.py -x` | ❌ Wave 1 |
| PKG-02 | No double `tradewinds/__init__.py` across wheels | manual + CI | `uv build --all && python tests/test_wheel_layout.py` | ❌ Wave 4 |
| PKG-04 | Wheel builds | manual | `uv build --all-packages` | manual |
| PKG-05 | `pandas<3.0` upper bound in deps | unit | `pytest tests/test_packaging.py::test_pandas_upper_bound -x` | ❌ Wave 4 |

### Sampling Rate
- **Per task commit:** `uv run pytest -m "not live" -q` (full quick suite, ~30s expected once Wave 3 lands).
- **Per wave merge:** Same + manual `uv run python -c "import tradewinds; tradewinds.research('KNYC', '2025-04-01', '2025-04-07')"` smoke.
- **Phase gate:** All 5 parity fixtures green via `pytest tests/test_parity.py -x` (HARD GATE).

### Wave 0 Gaps
- [ ] `tests/test_parity.py` — covers PARITY-01, PARITY-02, PARITY-03 (Wave 3)
- [ ] `tests/test_packaging.py` — covers PKG-02, PKG-05, PKG-06 (Wave 4)
- [ ] `tests/test_wheel_layout.py` — covers PKG-04 (Wave 4)
- [ ] `packages/weather/tests/test_cache.py` — covers CACHE-01, CACHE-07 (Wave 1)
- [ ] `packages/core/tests/_internal/merge/test_observations.py` + `test_climate.py` (Wave 1)
- [ ] `packages/core/tests/test_research.py` — integration smoke for research() (Wave 2)

## Sources

### Primary (HIGH confidence)
- `monorepo-v0.14.1/src/mostlyright/pairs.py` (447 lines) — `build_pairs`, `build_pairs_row`, `pairs_to_dataframe`, `_obs_aggregates`, `market_close_utc`
- `monorepo-v0.14.1/src/mostlyright/client.py:527-748` — `MostlyRightClient.pairs()` orchestration (HOSTED, but the date-grouping logic is the template for tradewinds research.py)
- `monorepo-v0.14.1/src/mostlyright/snapshot.py` (468 lines) — `_lst_offset`, `settlement_window_utc`, `settlement_date_for`, `_station_code_normalized`
- `monorepo-v0.14.1/ingest/storage/parquet.py:47-261, 477-494` — `_SOURCE_PRIORITY`, `_dedup_rows`, `_dedup_climate_rows`, `OBSERVATION_SCHEMA`, `CLIMATE_SCHEMA`, `_atomic_write_parquet`
- `monorepo-v0.14.1/tests/test_merge_scheduler.py:296-336` — `test_awc_gap_filled_by_iem` reference test
- `monorepo-v0.14.1/uv.lock` — pyarrow 23.0.1 (PKG-06 anchor)
- `tradewinds/tests/fixtures/parity/case_1_KNYC_2025-01-06_2025-01-12.parquet` — ground-truth dtypes (read in this research session): 19 columns, mixed int64/float64/object
- `tradewinds/tests/fixtures/parity/README.md` — capture context + API whitelist + day-3 parity-test pseudocode
- `tradewinds/spike/SPIKE_REPORT.md` — proves AWC last-168h-only; IEM ASOS + IEM CLI work for arbitrary historical ranges

### Secondary (MEDIUM confidence)
- `tradewinds/roadmap/sprint0.md` + lane checklists — original plan (some paths wrong; this research corrects them)
- `tradewinds/.planning/{ROADMAP,REQUIREMENTS,PROJECT,STATE}.md` — Phase 1 success criteria + 11 requirements

### Tertiary (LOW confidence — not needed for Phase 1)
- v0.14.1 `_toon.py` — deferred to Phase 2 CORE-05

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pyarrow>=17.0,<24.0` is safe (lockfile pin is 23.0.1; soft upper avoids future breaks) | Gap #5 PKG-06 | Wheel rebuilds break on a pyarrow 25 release; tighten to `==23.0.1` if seen |
| A2 | `assert_frame_equal(check_exact=True)` will hold for `obs_mean_f` averaging | Gap #4 + Risk R2 | Need to relax to `atol=1e-9` — graceful degradation, not a gate fail |
| A3 | `merge_climate` lift will match server-side hosted dedup exactly (since both come from the same source code) | Gap #2 | If hosted API has additional climate sources we don't know about (e.g., ACIS), fixtures may disagree — investigate during Wave 3 debug |
| A4 | AWC last-168h limitation means case-5 KMSY 2024-09 has zero AWC rows in tradewinds local fetch; fixture's AWC contribution came from hosted server's archived AWC ingest | Risk R5 | Confirmed by SPIKE_REPORT.md; mitigation = IEM-only fetch on historical months. If fixture expected AWC-specific cols, parity will fail; inspect with case-5 row inspection during Wave 3 |
| A5 | `_lst_offset` lift is sufficient — no need to also re-implement tz-override handling for KMSY (CST/CDT) since the fixture used the default | Gap #1, Gap #3 | Low — KMSY is in `_stations.py` |

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all deps already pinned + audited
- Architecture: HIGH — v0.14.1 source paths verified, gaps mapped, dependencies between gaps clear
- Pitfalls: MEDIUM-HIGH — major risks (R1, R2) flagged with mitigation; lower-severity risks (R5, R10) explicit
- Lift surface: HIGH — `pairs.py`, `snapshot.py`, `_dedup_rows`, `_dedup_climate_rows` all located + read

**Research date:** 2026-05-21
**Valid until:** 2026-06-04 (~14 days; v0.14.1 source is frozen, so the lift targets won't drift; tradewinds `merged-vision` will evolve and may absorb some gaps — re-verify the DONE list before Wave 1)
