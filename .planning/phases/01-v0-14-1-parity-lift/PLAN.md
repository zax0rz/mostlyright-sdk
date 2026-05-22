---
phase: 01-v0-14-1-parity-lift
type: execute
mode: gap-closure
duration: Days 1-4 (4 working days — Wave 1-2 Day 1-2, Wave 3 Day 3 HARD GATE, Wave 4 Day 4 publish)
waves: 4
depends_on: []        # First phase; foundations already done on merged-vision
branch_strategy: per-wave; sub-branch per parallel task off `merged-vision`; Codex review per sub-branch before merge to wave branch; wave branch merges back to `merged-vision` at end of wave
requirements:
  - PARITY-01
  - PARITY-02
  - PARITY-03
  - CORE-06
  - CATALOG-06
  - PKG-02
  - PKG-04
  - PKG-05
  - PKG-06
  - CACHE-01
  - CACHE-07
autonomous: false      # Wave 4 includes founder-only PyPI publish (requires UV_PUBLISH_TOKEN)
files_modified:
  # Wave 1
  - packages/weather/src/tradewinds/weather/cache.py                           # NEW (cache layer)
  - packages/weather/tests/test_cache.py                                       # NEW
  - packages/core/src/tradewinds/_internal/merge/__init__.py                   # NEW (merge re-exports)
  - packages/core/src/tradewinds/_internal/merge/observations.py               # NEW (port _dedup_rows)
  - packages/core/src/tradewinds/_internal/merge/climate.py                    # NEW (port _dedup_climate_rows)
  - packages/core/src/tradewinds/_internal/merge/_schemas.py                   # NEW (OBSERVATION_SCHEMA, CLIMATE_SCHEMA lift)
  - packages/core/tests/_internal/merge/test_observations.py                   # NEW (lift v0.14.1 tests)
  - packages/core/tests/_internal/merge/test_climate.py                        # NEW
  - packages/core/tests/_internal/merge/test_awc_gap_filled_by_iem.py          # NEW (synthetic case-5 reference)
  - packages/core/src/tradewinds/snapshot.py                                   # NEW (lift verbatim)
  - packages/core/src/tradewinds/_internal/_stations.py                        # NEW (lift verbatim)
  - packages/core/tests/test_snapshot.py                                       # NEW (lift)
  - packages/core/tests/_internal/test_stations.py                             # NEW (lift)
  # Wave 2
  - packages/core/src/tradewinds/_internal/_pairs.py                           # NEW (lift build_pairs + pairs_to_dataframe verbatim)
  - packages/core/src/tradewinds/research.py                                   # NEW (orchestrator)
  - packages/core/src/tradewinds/__init__.py                                   # MODIFY (re-export research)
  - packages/core/tests/test_research.py                                       # NEW (respx-mocked unit smoke vs case-1 fixture)
  - packages/core/tests/_internal/test_pairs.py                                # NEW (lift v0.14.1 pairs.py tests)
  # Wave 3
  - tests/test_parity.py                                                       # NEW (5-fixture parametrized parity test)
  - tests/fixtures/parity/expected_dtypes.json                                 # NEW (PARITY-03 ground truth)
  # Wave 4
  - packages/core/pyproject.toml                                               # version bump + pandas/pyarrow tightening
  - packages/weather/pyproject.toml                                            # version bump + pandas/pyarrow tightening
  - packages/markets/pyproject.toml                                            # (no version bump — stays 0.0.1)
  - packages/core/src/tradewinds/_internal/__init__.py                         # MODIFY (lift-inventory docstring)
  - packages/weather/src/tradewinds/weather/__init__.py                        # MODIFY (lift-inventory docstring)
  - tests/test_packaging.py                                                    # NEW (PKG-02/05/06 metadata checks)
  - tests/test_wheel_layout.py                                                 # NEW (PKG-04 namespace-collision check)
  - README.md                                                                  # MODIFY (workspace quickstart)
  - uv.lock                                                                    # MODIFY (after pin tightening)
must_haves:
  truths:
    - "tradewinds.research('KNYC', '2025-01-06', '2025-01-12') returns a pandas DataFrame with the same 19 columns, dtypes, and row values as case_1_KNYC_2025-01-06_2025-01-12.parquet (PARITY-01, case 1)."
    - "All 5 parametrized parity cases (KNYC, KMDW, KLAX, KMIA, KMSY) pass `assert_frame_equal(actual, expected, check_dtype=True, check_exact=True)` after _canon() sort — the Day 3 HARD GATE."
    - "tradewinds.research dtypes match tests/fixtures/parity/expected_dtypes.json byte-for-byte (PARITY-03)."
    - "merge_observations dedupe respects AWC > IEM > GHCNh priority on `(station_code, observed_at, observation_type)` keys (CORE-06 / merge)."
    - "merge_climate dedupe respects strict-`>` report_type_priority on `(station_code, observation_date)` keys with first-seen wins on ties (CORE-06 / merge)."
    - "Synthetic AWC-gap-IEM-fills test exercises the case-5 policy: when AWC rows are missing for some hours, IEM rows fill them with no overwrites at shared timestamps."
    - "Local parquet cache writes to $HOME/.tradewinds/cache/v1/observations/{STATION}/{YYYY}/{MM}.parquet with `pyarrow` version='2.6', coerce_timestamps='us' (CACHE-01, CACHE-07)."
    - "TRADEWINDS_CACHE_DIR env var overrides the cache root (CACHE-01)."
    - "Cache write skips the station's current-LST month (no parquet emitted, no exception)."
    - "Cache read/write are filelock-guarded against concurrent writers (2-process test: only one wins, file is not truncated)."
    - "research() composes cache → fetcher → parser → merge → cache-write → dataframe-build with NO hosted-API call (replaces the v0.14.1 client.pairs() HTTP path with a local pipeline)."
    - "_internal/__init__.py and weather/__init__.py docstrings record the lift inventory: monorepo-v0.14.1 source path + git SHA + lift date + modifications for each lifted module (CATALOG-06)."
    - "`uv build --all-packages` produces three wheels: tradewinds-0.1.0a1, tradewinds_weather-0.1.0a1, tradewinds_markets-0.0.1 (PKG-04)."
    - "Only tradewinds-0.1.0a1*.whl contains `tradewinds/__init__.py`; tradewinds_weather and tradewinds_markets wheels carry NO top-level `tradewinds/__init__.py` (PKG-02 — PEP 420 namespace)."
    - "packages/core/pyproject.toml and packages/weather/pyproject.toml pin `pandas>=2.2,<3.0` (PKG-05) and `pyarrow>=17.0,<24.0` (PKG-06)."
    - "Post-publish smoke (founder action): in a clean venv, `pip install 'tradewinds[parquet]==0.1.0a1' 'tradewinds-weather[parquet]==0.1.0a1'` followed by `python -c 'import tradewinds as tw; tw.research(\"KNYC\", \"2025-04-01\", \"2025-04-07\")'` returns a DataFrame."
  artifacts:
    - path: packages/weather/src/tradewinds/weather/cache.py
      provides: "read_cache, write_cache, cache_path; LST-current-month-skip; FileLock-guarded; pyarrow version=2.6 + coerce_timestamps=us"
      min_lines: 80
    - path: packages/core/src/tradewinds/_internal/merge/observations.py
      provides: "merge_observations(rows) + SOURCE_PRIORITY = {awc: 3, iem: 2, ghcnh: 1}"
      contains: "def merge_observations"
      min_lines: 40
    - path: packages/core/src/tradewinds/_internal/merge/climate.py
      provides: "merge_climate(rows) + REPORT_TYPE_PRIORITY (strict-gt, first-seen on ties)"
      contains: "def merge_climate"
      min_lines: 40
    - path: packages/core/src/tradewinds/_internal/merge/_schemas.py
      provides: "OBSERVATION_SCHEMA + CLIMATE_SCHEMA (pyarrow schemas lifted from v0.14.1 ingest/storage/parquet.py)"
    - path: packages/core/src/tradewinds/snapshot.py
      provides: "_lst_offset, _station_code_normalized, settlement_window_utc, settlement_date_for (lifted verbatim)"
    - path: packages/core/src/tradewinds/_internal/_stations.py
      provides: "20-station IATA + LST-offset table (lifted verbatim)"
    - path: packages/core/src/tradewinds/_internal/_pairs.py
      provides: "build_pairs, build_pairs_row, date_range, pairs_to_dataframe, _obs_aggregates, market_close_utc (lifted verbatim from pairs.py)"
      min_lines: 350
    - path: packages/core/src/tradewinds/research.py
      provides: "research(station, from_date, to_date, *, include_forecast=False, forecast_model=None, as_dataframe=True, tz_override=None) -> pd.DataFrame | list[dict]"
      contains: "def research"
      min_lines: 80
    - path: tests/test_parity.py
      provides: "test_parity_case[1..5] — the Day 3 HARD GATE"
      contains: "assert_frame_equal"
    - path: tests/fixtures/parity/expected_dtypes.json
      provides: "Ground-truth dtypes for the 5 parity fixtures (PARITY-03)"
    - path: tests/test_packaging.py
      provides: "test_pandas_upper_bound, test_pyarrow_upper_bound (PKG-05, PKG-06)"
    - path: tests/test_wheel_layout.py
      provides: "test_no_init_collision (PKG-02 / PKG-04)"
  key_links:
    - from: tradewinds.research
      to: tradewinds.weather.cache.read_cache + tradewinds.weather._fetchers.iem_asos.download_iem_asos + tradewinds._internal.merge.merge_observations + tradewinds._internal._pairs.build_pairs
      via: "cache-first orchestration: month-loop → cache hit returns dicts; cache miss → fetch+parse+merge → write_cache → return"
    - from: tradewinds._internal.merge.merge_observations
      to: SOURCE_PRIORITY dict
      via: "dedup key (station_code, observed_at, observation_type); highest priority wins"
    - from: tradewinds.weather.cache.write_cache
      to: filelock.FileLock + pyarrow.parquet.write_table(version='2.6', coerce_timestamps='us')
      via: "atomic write: tmp file → FileLock → rename"
    - from: tests/test_parity.py::test_parity_case
      to: tradewinds.research + tests/fixtures/parity/case_*.parquet
      via: "pd.read_parquet(fixture) vs tradewinds.research(...); _canon() sort; assert_frame_equal(check_dtype=True, check_exact=True)"
    - from: packages/core/src/tradewinds/__init__.py
      to: tradewinds.research.research
      via: "`from tradewinds.research import research` re-export (top-level tw.research(...) is the public surface)"
---

<objective>
Close the 5 remaining gaps on `merged-vision` to ship the Day 3 HARD GATE (5-fixture byte-equivalent parity vs `mostlyright==0.14.1`) and the Day 4 alpha PyPI publish (`tradewinds==0.1.0a1` + `tradewinds-weather==0.1.0a1`).

**Foundations already shipped on `merged-vision` (DO NOT replan, DO NOT touch):** workspace bootstrap (3-package uv workspace), `_internal/` shared utils (`_http`, `_convert`, `_bounds`, `_capabilities`, `exceptions`, `versioning`, `models/`, 17 JSON specs), 4 weather parsers (`_awc`, `_iem`, `_climate`, `_ghcnh` with W3A Codex fixes applied), 4 HTTP fetchers (`_fetchers/awc.py`, `iem_asos.py`, `iem_cli.py`, `ghcnh.py`), 5 parity fixtures captured + committed, the `_v02/` reference (266 tests, Phase 2 territory).

**Five gaps to close** (each maps to a wave below; mapping documented in must_haves and the per-task `<implements>` tags):

1. Cache layer — `packages/weather/.../cache.py` (CACHE-01, CACHE-07)
2. Merge policies — observation + climate dedup ports + `_internal/merge/_schemas.py` lift (CORE-06 / merge half)
3. `research.py` orchestration — replaces v0.14.1 hosted-API call with local pipeline (PARITY-01 load-bearing)
4. Parity test harness + `expected_dtypes.json` + bug-fix loop until 5/5 green (PARITY-01, PARITY-02, PARITY-03)
5. Pre-publish hygiene + founder-action prep (CATALOG-06, PKG-02, PKG-04, PKG-05, PKG-06)

**Critical correction from research (Open Q1 & Q2 RESOLVED):** v0.14.1 has NO `ingest/merge/policies.py`, NO `policies_climate.py`, NO `_cache.py`. The merge logic lives in `monorepo-v0.14.1/ingest/storage/parquet.py` (`_SOURCE_PRIORITY` line 47-48, `_dedup_rows` line 246-261, `_dedup_climate_rows` line 477-494). The cache layer is built fresh from scratch (no v0.14.1 reference). `research.py` REPLACES the hosted-API call inside `monorepo-v0.14.1/src/mostlyright/client.py::MostlyRightClient.pairs()` (lines 527-748) with a local fetcher→parser→merge→cache pipeline; the pure-shaping half (`pairs.py::build_pairs`, `build_pairs_row`, `pairs_to_dataframe`) is lifted verbatim.

**Output of this phase:** `tradewinds.research(...)` returns a DataFrame byte-equivalent to `mostlyright==0.14.1`'s `client.pairs(...)` across 5 fixtures; `uv build --all-packages` produces three wheels with no PEP 420 collision; founder publishes alpha1 wheels to PyPI.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/phase-01-v0-14-1-parity-lift/RESEARCH.md
@roadmap/sprint0.md
@tests/fixtures/parity/README.md
</execution_context>

<phase_summary>

**Goal:** Close the 5 gaps to ship the Day 3 HARD GATE and Day 4 alpha PyPI publish.

**Four-wave structure:**

| Wave | Day | Sub-branches (parallel) | Output | Codex priority |
|------|-----|------------------------|--------|----------------|
| 1 | Day 1 | 4 parallel sub-branches off `merged-vision` | cache layer + observation merge + climate merge + snapshot/_stations lift | HIGH on merge sub-branches; MEDIUM on cache; LOW on snapshot lift |
| 2 | Day 2 | 1 sub-branch (depends on Wave 1 merged) | `_internal/_pairs.py` + `research.py` orchestrator | HIGH (parity-critical orchestration) |
| 3 | Day 3 | 1 sub-branch — HARD GATE | parity test + `expected_dtypes.json` + bug-fix iterations | MEDIUM (test code) but iterating against real fixtures |
| 4 | Day 4 | 1 sub-branch (Claude) + founder action | pre-publish hygiene + founder publish | LOW (docs + pyproject) |

**Branch model:**
- Each wave gets a `phase-1/wave-{N}-{slug}` integration branch off `merged-vision`.
- Each Wave 1 sub-task gets its own branch off the wave branch (e.g. `phase-1/wave-1-cache`, `phase-1/wave-1-merge-obs`, `phase-1/wave-1-merge-climate`, `phase-1/wave-1-snapshot-lift`).
- Codex review per sub-branch BEFORE merge to wave branch. Wave branch merges to `merged-vision` at end of wave.
- Wave 3 expects 1-3 bug-fix iterations on the wave-3 branch before all 5 fixtures go green.

**Atomic commit boundaries:**
- One commit per sub-branch end-state (no WIP commits to wave branches; sub-branches squash-merge).
- Wave 1 produces 4 commits on `merged-vision`. Wave 2 produces 1. Wave 3 produces 1 + N bug-fix commits. Wave 4 produces 1 Claude commit + 1 founder publish (no source change).

**Cross-cutting risks (RESEARCH.md §Risk Register):**
- **R1 (HIGH):** Local merge produces row-level diffs vs hosted-API fixtures. Mitigation: lift v0.14.1's `test_parquet.py` cases verbatim in Wave 1; pair-debug with Codex in Wave 3.
- **R2 (MEDIUM):** Float averaging produces 1-ULP diff in `obs_mean_f`/`obs_mean_dewpoint_f` due to non-associative IEEE add. Mitigation: pre-sort observations by `observed_at` before averaging (already the v0.14.1 behavior — preserved in `_pairs.py` lift); fallback ladder for `check_exact` documented in Wave 3.
- **R3 (LOW):** "NYC" vs "KNYC" station-code mismatch. Mitigation: `_station_code_normalized` strips leading "K"; tested in Wave 1 snapshot-lift sub-branch.
- **R5 (MEDIUM):** AWC last-168h limitation means historical fixtures (cases 2-5) never exercise AWC merge priority. Mitigation: synthetic AWC-gap-IEM-fills test in Wave 1 (lifted from `monorepo-v0.14.1/tests/test_merge_scheduler.py::TestMergeCycle::test_awc_gap_filled_by_iem` lines 296-336).

**Open Q3 (assert_frame_equal kwargs) — recommendation:** start with `check_dtype=True, check_exact=True, check_like=False` (strict, column-order-preserving). Fallback ladder if Wave 3 sees float diffs:
1. `check_exact=False, rtol=0, atol=0` (still strict — only allows true equality after typecast)
2. `check_exact=False, rtol=0, atol=1e-12` (1-ULP-ish tolerance for `obs_mean_f` only)
3. `check_exact=False, rtol=0, atol=1e-9` (last-resort; documents the float-averaging non-associativity)
Document the chosen rung in Wave 3's bug-fix commit message and in `tests/test_parity.py`'s docstring.

</phase_summary>

<wave id="1" name="Parallel leaf modules (cache + merges + snapshot lift)" day="Day 1" parallel="true">

**Goal:** Land 4 independent leaf modules in parallel sub-branches off `merged-vision`. Each is a Wave 2 prerequisite. None of these touch the same files.

**Branches:**
- `phase-1/wave-1` (integration branch off `merged-vision`)
- `phase-1/wave-1-cache` (sub-branch off `phase-1/wave-1`)
- `phase-1/wave-1-merge-obs` (sub-branch off `phase-1/wave-1`)
- `phase-1/wave-1-merge-climate` (sub-branch off `phase-1/wave-1`)
- `phase-1/wave-1-snapshot-lift` (sub-branch off `phase-1/wave-1`)

**Merge order into wave-1 branch:** snapshot-lift → merge-obs + merge-climate (parallel) → cache (depends on `_stations.py` from snapshot-lift for `_lst_offset`). Cache must merge LAST inside Wave 1.

**Wave 1 exit gate:** `uv run pytest -m "not live" -q` green; `phase-1/wave-1` merges to `merged-vision`.

<task id="1.1" type="auto" tdd="true" branch="phase-1/wave-1-snapshot-lift">
  <name>Task 1.1: Lift snapshot.py + _stations.py from v0.14.1</name>
  <implements>Prerequisite for Wave 1 cache (LST-month-skip via `_lst_offset`) and Wave 2 research.py (`settlement_date_for`, `_station_code_normalized`). No direct requirement; enables PARITY-01.</implements>
  <files>
    packages/core/src/tradewinds/snapshot.py (NEW — lift verbatim)
    packages/core/src/tradewinds/_internal/_stations.py (NEW — lift verbatim)
    packages/core/tests/test_snapshot.py (NEW — lift v0.14.1 tests, rename imports)
    packages/core/tests/_internal/test_stations.py (NEW — lift)
  </files>
  <behavior>
    - `_lst_offset("KNYC")` returns `timedelta(hours=-5)` (EST, no DST in LST)
    - `_lst_offset("KLAX")` returns `timedelta(hours=-8)` (PST)
    - `_station_code_normalized("KNYC")` returns `"NYC"` (strips leading K)
    - `_station_code_normalized("NYC")` returns `"NYC"` (idempotent)
    - `settlement_window_utc(date(2025, 1, 6), "KNYC")` returns the UTC start/end of the NYC LST settlement day (24-hour window starting at 05:00Z for KNYC)
    - `settlement_date_for(datetime(2025, 1, 6, 23, 30, tzinfo=UTC), "KNYC")` returns `"2025-01-06"` (in LST, 23:30Z = 18:30 EST = same day)
    - `settlement_date_for(datetime(2025, 1, 7, 4, 30, tzinfo=UTC), "KNYC")` returns `"2025-01-06"` (in LST, 04:30Z = 23:30 EST prior day = same settlement day)
    - West-coast edge: `settlement_date_for(datetime(2025, 3, 9, 12, 0, tzinfo=UTC), "KLAX")` should NOT shift across DST boundary — LST stays PST (no DST in LST).
  </behavior>
  <action>
    1. **Source:** `monorepo-v0.14.1/src/mostlyright/snapshot.py` (468 lines) — lift VERBATIM into `packages/core/src/tradewinds/snapshot.py`.
       Adjust imports only: `from mostlyright._stations` → `from tradewinds._internal._stations`. No logic changes.
    2. **Source:** `monorepo-v0.14.1/src/mostlyright/_stations.py` — lift VERBATIM into `packages/core/src/tradewinds/_internal/_stations.py`.
       Adjust imports only. The IATA + LST-offset table for the 20 whitelist stations must transfer unchanged.
    3. **Tests:** lift relevant tests from `monorepo-v0.14.1/tests/` (search for `test_snapshot*`, `test_stations*`, `test_settlement*` — lift all that exercise `_lst_offset`, `_station_code_normalized`, `settlement_window_utc`, `settlement_date_for`). Rename imports `mostlyright.*` → `tradewinds.*`. Expected: ~80-150 LOC of tests, all green.
    4. Add lift-provenance comment at top of each lifted file:
       ```python
       # Lifted from monorepo-v0.14.1/src/mostlyright/snapshot.py
       # Source SHA: <run `git -C ../monorepo-v0.14.1 rev-parse HEAD` and paste>
       # Lift date: 2026-05-21
       # Modifications: import-rename mostlyright._stations -> tradewinds._internal._stations
       ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/test_snapshot.py packages/core/tests/_internal/test_stations.py -x -v</automated>
    Manual: `python -c "from tradewinds.snapshot import settlement_date_for; from datetime import datetime, timezone; print(settlement_date_for(datetime(2025,1,7,4,30,tzinfo=timezone.utc), 'KNYC'))"` → prints `2025-01-06`.
  </verify>
  <done>
    All lifted tests green (≥1 test per public function: `_lst_offset`, `_station_code_normalized`, `settlement_window_utc`, `settlement_date_for`). Lift-provenance comment present in both files. Sub-branch ready for Codex LOW-priority review (verbatim lift; reviewer confirms imports renamed correctly, no logic drift).
  </done>
</task>

<task id="1.2" type="auto" tdd="true" branch="phase-1/wave-1-merge-obs">
  <name>Task 1.2: Port observation merge policy from v0.14.1</name>
  <implements>CORE-06 (merge half); R1 mitigation; case-5 KMSY synthetic test.</implements>
  <files>
    packages/core/src/tradewinds/_internal/merge/__init__.py (NEW — re-exports)
    packages/core/src/tradewinds/_internal/merge/observations.py (NEW — port _dedup_rows)
    packages/core/src/tradewinds/_internal/merge/_schemas.py (NEW — lift OBSERVATION_SCHEMA from v0.14.1)
    packages/core/tests/_internal/merge/test_observations.py (NEW — lift verbatim test cases from monorepo-v0.14.1/tests/test_parquet.py)
    packages/core/tests/_internal/merge/test_awc_gap_filled_by_iem.py (NEW — lift case-5 reference test)
  </files>
  <behavior>
    - `SOURCE_PRIORITY` is `{"awc": 3, "iem": 2, "ghcnh": 1}` (verbatim from v0.14.1 line 47-48).
    - `merge_observations(rows)` dedupes by key `(station_code, observed_at, observation_type)`, keeps the row with highest `SOURCE_PRIORITY.get(row['source'], 0)`.
    - On tie (same source-priority), first-seen wins (insertion-order stable).
    - Unknown source string ("madis", "unknown") → priority 0; loses to any known source.
    - Empty input returns empty list.
    - Synthetic case: 24 AWC METAR rows for KMSY 2024-09-11 with hours [0..11, 18..23] (gap 12-17) PLUS 24 IEM rows for hours [0..23] → merged result has 24 rows, hours 0-11 + 18-23 are AWC, hours 12-17 are IEM (`test_awc_gap_filled_by_iem`).
  </behavior>
  <action>
    1. **Source:** `monorepo-v0.14.1/ingest/storage/parquet.py` lines 47-48 (`_SOURCE_PRIORITY`) and lines 246-261 (`_dedup_rows`). Port into `_internal/merge/observations.py`:
       ```python
       # Lifted from monorepo-v0.14.1/ingest/storage/parquet.py:47-48, 246-261
       # Source SHA: <fill>
       # Lift date: 2026-05-21
       # Modifications: renamed _dedup_rows -> merge_observations; renamed _SOURCE_PRIORITY -> SOURCE_PRIORITY (public).
       SOURCE_PRIORITY: dict[str, int] = {"awc": 3, "iem": 2, "ghcnh": 1}

       def merge_observations(rows: list[dict]) -> list[dict]:
           """Dedupe observations by (station_code, observed_at, observation_type).
           Keeps highest-priority source for each key. Stable on ties."""
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
    2. **Source:** `monorepo-v0.14.1/ingest/storage/parquet.py` lines 51-103 (`OBSERVATION_SCHEMA`). Lift VERBATIM into `_internal/merge/_schemas.py`. This pyarrow schema is what Wave 1.4 (cache) will use for `pq.write_table(table, schema=OBSERVATION_SCHEMA, ...)`.
    3. **Re-exports:** `_internal/merge/__init__.py`:
       ```python
       from tradewinds._internal.merge.observations import merge_observations, SOURCE_PRIORITY
       from tradewinds._internal.merge.climate import merge_climate, REPORT_TYPE_PRIORITY  # populated by Task 1.3
       __all__ = ["merge_observations", "merge_climate", "SOURCE_PRIORITY", "REPORT_TYPE_PRIORITY"]
       ```
    4. **Tests — lift verbatim:** find every test in `monorepo-v0.14.1/tests/test_parquet.py` that exercises `_dedup_rows` (likely 4-6 cases). Lift, rename `from mostlyright_ingest.storage.parquet import _dedup_rows` → `from tradewinds._internal.merge.observations import merge_observations`. Rename function calls. All must pass.
    5. **Synthetic test:** lift `monorepo-v0.14.1/tests/test_merge_scheduler.py::TestMergeCycle::test_awc_gap_filled_by_iem` (lines 296-336). This is the case-5 reference. Strip the scheduler wrapper; reduce to a pure call: build synthetic AWC + IEM rows (24 hours each, AWC missing hours 12-17), call `merge_observations(awc_rows + iem_rows)`, assert exactly 24 rows in output, assert hours [12,13,14,15,16,17] have `source == "iem"`, all others `source == "awc"`.
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/_internal/merge/test_observations.py packages/core/tests/_internal/merge/test_awc_gap_filled_by_iem.py -x -v</automated>
  </verify>
  <done>
    All lifted v0.14.1 cases pass byte-identically. Synthetic AWC-gap-IEM-fills test passes. Lift-provenance comment present. `SOURCE_PRIORITY` dict matches v0.14.1 line 47-48 exactly. Codex HIGH-priority review approved (parity-critical: any drift in this dedup logic = parity gate fail).
  </done>
</task>

<task id="1.3" type="auto" tdd="true" branch="phase-1/wave-1-merge-climate">
  <name>Task 1.3: Port climate merge policy from v0.14.1</name>
  <implements>CORE-06 (merge half); supports PARITY-01.</implements>
  <files>
    packages/core/src/tradewinds/_internal/merge/climate.py (NEW — port _dedup_climate_rows)
    packages/core/src/tradewinds/_internal/merge/_schemas.py (APPEND CLIMATE_SCHEMA — note: Task 1.2 created this file; Task 1.3 appends. Coordinate via merge order — Task 1.2 merges first into wave-1 branch.)
    packages/core/tests/_internal/merge/test_climate.py (NEW)
  </files>
  <behavior>
    - `REPORT_TYPE_PRIORITY` is `{"final": 3, "correction": 2, "preliminary": 1}` (or whatever v0.14.1 line ~477 specifies — confirm from source).
    - `merge_climate(rows)` dedupes by key `(station_code, observation_date)`, keeps row where `REPORT_TYPE_PRIORITY[row['report_type']]` is **strictly greater** than the existing.
    - Tie behavior: first-seen wins (NOT replaced). I.e. two "final" rows for same key → first one kept.
    - Strict-`>` (NOT `>=`) is the key difference vs observations merge: same-priority does NOT overwrite.
    - Empty input returns empty list.
    - Unknown `report_type` → priority 0; cannot overwrite known.
  </behavior>
  <action>
    1. **Source:** `monorepo-v0.14.1/ingest/storage/parquet.py` lines 477-494 (`_dedup_climate_rows`). Read it carefully — verify the strict-`>` comparison vs strict-`>=`. Document the exact priority mapping from the source. Port into `_internal/merge/climate.py` with the same provenance header pattern as Task 1.2:
       ```python
       # Lifted from monorepo-v0.14.1/ingest/storage/parquet.py:477-494
       # Source SHA: <fill>
       # Lift date: 2026-05-21
       # Modifications: renamed _dedup_climate_rows -> merge_climate
       REPORT_TYPE_PRIORITY: dict[str, int] = {<as-confirmed-from-source>}

       def merge_climate(rows: list[dict]) -> list[dict]:
           """Dedupe climate observations by (station_code, observation_date).
           Strict-greater-than on REPORT_TYPE_PRIORITY; first-seen wins on ties."""
           best: dict[tuple[str, str], dict] = {}
           for row in rows:
               key = (row["station_code"], row["observation_date"])
               priority = REPORT_TYPE_PRIORITY.get(row.get("report_type", ""), 0)
               if key not in best:
                   best[key] = row
               else:
                   existing_priority = REPORT_TYPE_PRIORITY.get(best[key].get("report_type", ""), 0)
                   if priority > existing_priority:   # STRICT >  (not >=)
                       best[key] = row
           return list(best.values())
       ```
    2. **Append `CLIMATE_SCHEMA` to `_internal/merge/_schemas.py`** (file created by Task 1.2). Lift verbatim from v0.14.1 `parquet.py` (same file as OBSERVATION_SCHEMA; CLIMATE_SCHEMA is also defined there).
    3. **Tests:** lift every test in `monorepo-v0.14.1/tests/test_parquet.py` that exercises `_dedup_climate_rows`. Add an explicit "two-final-rows-first-wins" test case (the strict-`>` tie behavior is easy to break in re-implementation).
    4. Coordinate with Task 1.2 on merge order: Task 1.2 must land in `phase-1/wave-1` branch BEFORE Task 1.3 (Task 1.3 appends to `_schemas.py` and to `__init__.py` re-exports). Communicate via PR sequencing.
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/_internal/merge/test_climate.py -x -v</automated>
  </verify>
  <done>
    All lifted v0.14.1 climate-dedup tests pass. Two-final-rows-first-wins test passes (proves strict-`>`). Lift-provenance comment present. `REPORT_TYPE_PRIORITY` mapping matches v0.14.1 source exactly. Codex HIGH-priority review approved.
  </done>
</task>

<task id="1.4" type="auto" tdd="true" branch="phase-1/wave-1-cache">
  <name>Task 1.4: Build local parquet cache layer (NEW — no v0.14.1 reference)</name>
  <implements>CACHE-01, CACHE-07.</implements>
  <depends_on>Task 1.1 (needs `_lst_offset` from `_stations.py`) and Task 1.2 (needs `OBSERVATION_SCHEMA` from `_schemas.py`). MUST merge LAST in Wave 1.</depends_on>
  <files>
    packages/weather/src/tradewinds/weather/cache.py (NEW, ~120 LOC)
    packages/weather/tests/test_cache.py (NEW, ~150 LOC)
  </files>
  <behavior>
    - `cache_path("KNYC", 2025, 1)` returns `Path("~/.tradewinds/cache/v1/observations/KNYC/2025/01.parquet")` (expanded).
    - `TRADEWINDS_CACHE_DIR=/tmp/foo` env var redirects to `/tmp/foo/v1/observations/KNYC/2025/01.parquet`.
    - `read_cache("KNYC", 2025, 1)` returns `list[dict]` if cache file exists AND (year, month) is NOT current-LST-month for KNYC; else returns `None`.
    - `write_cache("KNYC", 2025, 1, rows)` writes parquet with `version="2.6"`, `coerce_timestamps="us"`. NO write if (year, month) is current-LST-month.
    - Atomic write: write to `.tmp` file inside FileLock, then `os.rename(tmp, dest)`.
    - Concurrent test: two `multiprocessing.Process` workers writing same path. Only one succeeds; file is not truncated; final read yields the contents of one or the other (no partial bytes).
    - Climate cache lives at `~/.tradewinds/cache/v1/climate/{STATION}/{YYYY}.parquet` (annual granularity — matches IEM CLI fetch shape). Public surface: `read_climate_cache(station, year)`, `write_climate_cache(station, year, rows)`. Same FileLock + pyarrow options + LST-current-year-skip.
  </behavior>
  <action>
    1. **Public surface (from RESEARCH.md §Gap-1):**
       ```python
       # packages/weather/src/tradewinds/weather/cache.py
       import os
       from datetime import datetime, timezone
       from pathlib import Path
       import pyarrow as pa
       import pyarrow.parquet as pq
       from filelock import FileLock
       from tradewinds._internal._stations import _lst_offset
       from tradewinds._internal.merge._schemas import OBSERVATION_SCHEMA, CLIMATE_SCHEMA

       CACHE_VERSION = "v1"
       DEFAULT_ROOT = Path.home() / ".tradewinds" / "cache"

       def _cache_root() -> Path:
           return Path(os.environ.get("TRADEWINDS_CACHE_DIR", DEFAULT_ROOT))

       def cache_path(station: str, year: int, month: int) -> Path: ...
       def climate_cache_path(station: str, year: int) -> Path: ...
       def _is_current_lst_month(station: str, year: int, month: int) -> bool: ...
       def _is_current_lst_year(station: str, year: int) -> bool: ...
       def read_cache(station: str, year: int, month: int) -> list[dict] | None: ...
       def write_cache(station: str, year: int, month: int, rows: list[dict]) -> None: ...
       def read_climate_cache(station: str, year: int) -> list[dict] | None: ...
       def write_climate_cache(station: str, year: int, rows: list[dict]) -> None: ...
       ```
    2. **Atomic write template** (used by both write paths):
       ```python
       def _atomic_write(path: Path, rows: list[dict], schema: pa.Schema) -> None:
           path.parent.mkdir(parents=True, exist_ok=True)
           tmp = path.with_suffix(".tmp")
           with FileLock(str(path) + ".lock", timeout=30):
               table = pa.Table.from_pylist(rows, schema=schema)
               pq.write_table(table, tmp, version="2.6", coerce_timestamps="us")
               tmp.rename(path)
       ```
    3. **LST-current-month-skip:** `_lst_offset(station)` returns a `timedelta`; compute `now_lst = datetime.now(timezone.utc) + offset`; compare `(now_lst.year, now_lst.month)` to `(year, month)`. Same pattern for `_is_current_lst_year`.
    4. **Tests** (covers CACHE-01 + CACHE-07):
       - `test_path_layout`: `cache_path("KNYC", 2025, 1).parts[-4:] == ("v1", "observations", "KNYC", "01.parquet" wait no — last 4 parts)`. Adjust assertion to check the right tail.
       - `test_env_var_override`: set `TRADEWINDS_CACHE_DIR=/tmp/tw-test`, assert `cache_path` returns under `/tmp/tw-test/v1/...`.
       - `test_roundtrip_preserves_dtypes`: write a 3-row list[dict] matching OBSERVATION_SCHEMA dtypes; read back; assert exact equality.
       - `test_current_month_skip_write`: monkeypatch `datetime.now` (or use `freezegun`) so `now_lst` is in (2025, 6) for KNYC; call `write_cache("KNYC", 2025, 6, rows)`; assert no parquet emitted at the expected path.
       - `test_current_month_skip_read`: same date freeze; pre-write a parquet to the expected path; call `read_cache("KNYC", 2025, 6)`; assert returns `None`.
       - `test_parquet_options`: write a small cache; use `pq.read_metadata(path)` to assert the parquet version starts with "2.6" and timestamp columns coerced to `us`.
       - `test_concurrent_writers`: spawn 2 `multiprocessing.Process` workers each calling `write_cache("KMSY", 2024, 9, rows_a)` and `write_cache("KMSY", 2024, 9, rows_b)`. Wait. Read result. Assert read succeeds (no corruption); content is either rows_a or rows_b (not partial).
       - `test_climate_cache_roundtrip`: same as observation roundtrip but for `write_climate_cache`/`read_climate_cache`.
    5. **DO NOT** import `tradewinds.weather._iem` or any parser — cache must be parser-agnostic (it operates on already-parsed `list[dict]`). This decouples cache from any single fetcher's failure mode.
  </action>
  <verify>
    <automated>uv run pytest packages/weather/tests/test_cache.py -x -v</automated>
    Manual: `TRADEWINDS_CACHE_DIR=/tmp/tw-smoke python -c "from tradewinds.weather.cache import cache_path; print(cache_path('KNYC', 2025, 1))"` prints `/tmp/tw-smoke/v1/observations/KNYC/2025/01.parquet`.
  </verify>
  <done>
    All 8 tests pass. Concurrent-writer test runs in <5s. `pq.read_metadata` shows version="2.6" + `us` timestamp coercion. Codex MEDIUM-priority review approved (cache correctness matters for parity if Wave 3 hits race conditions; lower than merge priority because cache itself doesn't affect byte-equivalence — it just speeds up re-runs).
  </done>
</task>

</wave>

<wave id="2" name="research.py orchestration" day="Day 2" parallel="false">

**Goal:** Land the orchestrator that composes Wave 1 outputs into `research(station, from_date, to_date) -> pd.DataFrame`. This is the load-bearing PARITY-01 task. Codex HIGH-priority review required.

**Branch:** `phase-1/wave-2-research` off `merged-vision` (with Wave 1 already merged in).

**Wave 2 exit gate:** `tradewinds.research("KNYC", "2025-01-06", "2025-01-12")` returns a DataFrame with the same 19 columns as the case-1 parity fixture. Full parity assertion is Wave 3 — Wave 2 only proves the pipeline runs end-to-end against a respx-mocked HTTP layer. Wave 2 merges to `merged-vision` after Codex approval.

<task id="2.1" type="auto" tdd="true" branch="phase-1/wave-2-research" codex_priority="HIGH">
  <name>Task 2.1: Lift pairs.py + write research.py orchestrator</name>
  <implements>PARITY-01 (load-bearing); CATALOG-06 (lift inventory partially — provenance comments).</implements>
  <files>
    packages/core/src/tradewinds/_internal/_pairs.py (NEW — lift pairs.py VERBATIM, ~447 LOC)
    packages/core/src/tradewinds/research.py (NEW — orchestrator, ~120 LOC)
    packages/core/src/tradewinds/__init__.py (MODIFY — add `from tradewinds.research import research`)
    packages/core/tests/_internal/test_pairs.py (NEW — lift v0.14.1 pairs tests)
    packages/core/tests/test_research.py (NEW — respx-mocked unit smoke against case-1 fixture columns)
  </files>
  <behavior>
    - `research("KNYC", "2025-01-06", "2025-01-12")` returns a `pd.DataFrame` with:
      - 7 rows (one per settlement day in the inclusive range)
      - 19 columns: `date` (index → reset_index makes it a column), `station` (object — "NYC" not "KNYC", per `_station_code_normalized`), `cli_high_f`, `cli_low_f`, `cli_data_quality`, `cli_report_type` (object), `market_close_utc` (object), `obs_high_f`, `obs_low_f`, `obs_mean_f`, `obs_mean_dewpoint_f`, `obs_max_wind_kt`, `obs_max_gust_kt`, `obs_total_precip_in`, `obs_count`, `fcst_high_f`, `fcst_low_f`, `fcst_mean_f`, `fcst_source`, `fcst_retrieved_at` (last 6 all object/None since `include_forecast=False`).
      - dtypes match `tests/fixtures/parity/case_1_KNYC_2025-01-06_2025-01-12.parquet` (case-1 verified during research: int64 for `cli_high_f`/`cli_low_f`/`obs_max_wind_kt`/`obs_max_gust_kt`/`obs_count`; float64 for `obs_high_f`/`obs_low_f`/`obs_mean_f`/`obs_mean_dewpoint_f`/`obs_total_precip_in`; object for `station`/`cli_report_type`/`market_close_utc`/`fcst_*`).
    - `include_forecast=False` (default): `fcst_*` columns emitted as None/object (matches fixtures).
    - `as_dataframe=False`: returns `list[dict]` instead of DataFrame.
    - For each month in the request range: try cache; on miss, fetch from IEM ASOS (always), AWC (only if requested month is within last ~168h — else skip), GHCNh (always for historical), parse, merge via `merge_observations`, write cache, return.
    - For climate: annual cache; fetch from IEM CLI; parse; merge via `merge_climate`; write cache; return.
    - Groups observations by `settlement_date_for(observed_at, station)` — NOT by `observed_at[:10]`. This is the Pitfall-1 fix.
  </behavior>
  <action>
    1. **Lift `_pairs.py` VERBATIM** from `monorepo-v0.14.1/src/mostlyright/pairs.py` (447 lines). Adjust imports only:
       - `from mostlyright.snapshot` → `from tradewinds.snapshot`
       - `from mostlyright._stations` → `from tradewinds._internal._stations`
       - `from mostlyright._convert` → `from tradewinds._internal._convert`
       - `from mostlyright._types` → `from tradewinds._internal.models` (verify shape; may need item-by-item)
       - DO NOT lift `pairs_to_toon` if it imports `mostlyright._toon` (defer to Phase 2). If `pairs.py::pairs_to_dataframe` uses any TOON code, **excise the TOON import + function**; keep only `build_pairs`, `build_pairs_row`, `date_range`, `pairs_to_dataframe`, `_obs_aggregates`, `market_close_utc`.
       - Per RESEARCH.md Open Q7: drop `format="toon"` support from `research()` for Phase 1 (TOON serialization deferred to Phase 2 CORE-05). `research()` only emits DataFrame or list[dict].
    2. **Write `research.py`** (skeleton from RESEARCH.md §Gap-3 code example):
       ```python
       # packages/core/src/tradewinds/research.py
       # NEW orchestrator. Replaces v0.14.1 client.pairs() hosted-API call with local pipeline.

       from __future__ import annotations
       from datetime import date as _date, timedelta as _td
       from typing import Any
       import pandas as pd
       from tradewinds._internal.merge import merge_observations, merge_climate
       from tradewinds.snapshot import settlement_date_for, _station_code_normalized
       from tradewinds._internal._pairs import build_pairs, date_range, pairs_to_dataframe

       def research(
           station: str,
           from_date: str,
           to_date: str,
           *,
           include_forecast: bool = False,
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
    3. **Implement `_fetch_observations_range(code, from_date, extended_to)`** as a private helper inside `research.py`:
       - Compute month-list spanning `[from_date, extended_to]` inclusively.
       - For each `(year, month)`:
         - `cached = read_cache(code, year, month)`; if hit, extend `result` and continue.
         - Else: build a per-source fetch plan based on age:
           - IEM ASOS: always fetch (call `tradewinds.weather._fetchers.iem_asos.download_iem_asos(code, year, month)`, parse via `tradewinds.weather._iem.parse_iem_file`).
           - AWC: only if the month is within the last ~168h (7 days). Otherwise skip — AWC's `/api/data/metar?hours=168` won't return historical (per `spike/SPIKE_REPORT.md`).
           - GHCNh: always fetch for historical (call `tradewinds.weather._fetchers.ghcnh.download_ghcnh(code, year)`, parse via `_ghcnh.py`). NOTE: GHCNh is annual; cache key per `(code, year)`. Cross-month dedup happens in `merge_observations`.
         - Merge via `merge_observations(iem_rows + awc_rows + ghcnh_rows)`.
         - **Pre-sort by `observed_at`** before returning (R2 mitigation — non-associative IEEE add).
         - `write_cache(code, year, month, merged_rows)` (skips current-LST-month automatically).
         - Extend `result`.
       - Return `result`.
    4. **Implement `_fetch_climate_range(code, from_date, to_date)`** symmetrically:
       - Iterate years in range inclusively.
       - `read_climate_cache(code, year)` → on miss, `tradewinds.weather._fetchers.iem_cli.download_iem_cli(code, year)`, parse via `weather._climate.parse_cli_file`, `merge_climate(rows)`, `write_climate_cache(code, year, rows)`, return.
    5. **Re-export from `packages/core/src/tradewinds/__init__.py`:**
       ```python
       from tradewinds.research import research
       __all__ = [..., "research"]
       ```
       The user-facing surface is `tradewinds.research(...)`.
    6. **Tests (`test_research.py`)** — respx-mocked HTTP, no network:
       - Capture the case-1 KNYC HTTP responses once into `tests/fixtures/respx/case_1_KNYC/*.json` (IEM ASOS month CSVs + IEM CLI year JSON; AWC excluded because case-1 is Jan 2025 = historical, AWC skipped).
       - Use `respx.mock` to serve those captures.
       - Assert `tradewinds.research("KNYC", "2025-01-06", "2025-01-12")` returns:
         - DataFrame with 7 rows.
         - Column set exactly matches case-1 fixture columns (do NOT yet assert values — that's Wave 3).
         - dtypes match case-1 fixture dtypes (this is the Wave 2 dtype-only smoke; full value parity is Wave 3).
       - Smoke assertions on a single row's `obs_count` > 0, `cli_high_f` is non-None.
    7. **Lift pairs-specific tests** from `monorepo-v0.14.1/tests/` (test_pairs*, test_build_pairs*). Strip any tests that hit the hosted API; keep only pure-function tests on `build_pairs`, `build_pairs_row`, `pairs_to_dataframe`, `_obs_aggregates`, `market_close_utc`, `date_range`. Rename imports `from mostlyright.pairs` → `from tradewinds._internal._pairs`. All green.
    8. Lift-provenance header on `_pairs.py`:
       ```python
       # Lifted from monorepo-v0.14.1/src/mostlyright/pairs.py (447 LOC, full file minus TOON imports)
       # Source SHA: <fill>
       # Lift date: 2026-05-21
       # Modifications:
       #   - import-renames: mostlyright.* -> tradewinds.*
       #   - removed pairs_to_toon function and `from mostlyright._toon import ...` (TOON deferred to Phase 2)
       ```
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/_internal/test_pairs.py packages/core/tests/test_research.py -x -v</automated>
    Manual: `python -c "import tradewinds as tw; df = tw.research('KNYC', '2025-01-06', '2025-01-12'); print(df.shape); print(df.dtypes); print(df.head())"` (requires network — IEM ASOS + IEM CLI) returns 7 rows, columns match fixture.
  </verify>
  <done>
    All lifted pairs tests green. `test_research.py` respx smoke green. `tradewinds.research(...)` callable from top-level (`tw.research(...)`). Lift-provenance headers present on `_pairs.py`. Codex HIGH-priority review approved (parity-critical orchestration; reviewer specifically checks: (a) settlement_date_for grouping not date-string slicing, (b) pre-sort by observed_at before merge, (c) merge_observations called on combined rows, (d) write_cache skips current-LST-month implicitly, (e) build_pairs called with forecasts_by_date=None for Phase 1, (f) station code normalized via `_station_code_normalized`).
  </done>
</task>

</wave>

<wave id="3" name="Parity test harness + bug-fix loop" day="Day 3 HARD GATE" parallel="false">

**Goal:** Write the 5-fixture parity test, run it, iterate until all 5 cases pass. **This IS the Day 3 HARD GATE. Sprint 0 ships only if green.** Expect 1-3 bug-fix iterations on fixture-level diffs.

**Branch:** `phase-1/wave-3-parity` off `merged-vision` (with Wave 2 merged in).

**Wave 3 exit gate:** `uv run pytest tests/test_parity.py -x` green on all 5 parametrized cases. Wave 3 merges to `merged-vision`.

<task id="3.1" type="auto" tdd="true" branch="phase-1/wave-3-parity" codex_priority="MEDIUM">
  <name>Task 3.1: Write parity test harness + capture expected_dtypes.json</name>
  <implements>PARITY-01, PARITY-02, PARITY-03.</implements>
  <files>
    tests/test_parity.py (NEW, ~80 LOC)
    tests/fixtures/parity/expected_dtypes.json (NEW — captured from the 5 .parquet fixtures)
    scripts/capture_expected_dtypes.py (NEW, ~30 LOC — one-shot dtype-dump script)
  </files>
  <behavior>
    - `pytest tests/test_parity.py -x` runs 5 parametrized cases (KNYC, KMDW, KLAX, KMIA, KMSY) — all 5 must pass.
    - For each case: `actual = tradewinds.research(station, frm, to)`; `expected = pd.read_parquet(FIXTURES / f"case_{n}_{station}_{frm}_{to}.parquet")`; `_canon` sort; `assert_frame_equal(actual_canon, expected_canon, check_dtype=True, check_exact=True)`.
    - `expected_dtypes.json` contains a map `{case_n: {column: dtype_str}}` for all 5 cases; loaded once at test-collection time; one assertion per case verifies `actual.dtypes.to_dict()` matches.
  </behavior>
  <action>
    1. **Capture `expected_dtypes.json`** via `scripts/capture_expected_dtypes.py`:
       ```python
       import json
       from pathlib import Path
       import pandas as pd

       CASES = [
           (1, "KNYC", "2025-01-06", "2025-01-12"),
           (2, "KMDW", "2025-04-01", "2025-04-30"),
           (3, "KLAX", "2025-03-01", "2025-03-31"),
           (4, "KMIA", "2024-12-01", "2025-11-30"),
           (5, "KMSY", "2024-09-08", "2024-09-22"),
       ]
       FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures" / "parity"
       out: dict = {}
       for n, station, frm, to in CASES:
           df = pd.read_parquet(FIXTURES / f"case_{n}_{station}_{frm}_{to}.parquet")
           df = df.reset_index() if df.index.name else df
           out[f"case_{n}"] = {col: str(dtype) for col, dtype in df.dtypes.items()}
       (FIXTURES / "expected_dtypes.json").write_text(json.dumps(out, indent=2, sort_keys=True))
       ```
       Run once: `python scripts/capture_expected_dtypes.py`. Commit the JSON.
    2. **Write `tests/test_parity.py`:**
       ```python
       """Day 3 HARD GATE — 5-fixture byte-equivalent parity vs mostlyright==0.14.1.

       Tolerance ladder (RESEARCH.md Open Q3):
         - Rung 1 (current): check_dtype=True, check_exact=True
         - Rung 2: check_exact=False, rtol=0, atol=0
         - Rung 3: check_exact=False, rtol=0, atol=1e-12
         - Rung 4: check_exact=False, rtol=0, atol=1e-9  (last resort)
       Document chosen rung in commit message if relaxing below rung 1.
       """
       import json
       from pathlib import Path
       import pandas as pd
       import pytest
       from pandas.testing import assert_frame_equal
       import tradewinds

       FIXTURES = Path(__file__).parent / "fixtures" / "parity"
       EXPECTED_DTYPES = json.loads((FIXTURES / "expected_dtypes.json").read_text())

       CASES = [
           (1, "KNYC", "2025-01-06", "2025-01-12"),
           (2, "KMDW", "2025-04-01", "2025-04-30"),
           (3, "KLAX", "2025-03-01", "2025-03-31"),
           (4, "KMIA", "2024-12-01", "2025-11-30"),
           (5, "KMSY", "2024-09-08", "2024-09-22"),
       ]

       def _canon(df: pd.DataFrame) -> pd.DataFrame:
           out = df.reset_index() if df.index.name else df.reset_index(drop=True)
           if "index" in out.columns and "date" in out.columns:
               out = out.drop(columns=["index"])
           return out.sort_values(["date", "station"]).reset_index(drop=True)

       @pytest.mark.parametrize("n,station,frm,to", CASES)
       def test_parity_case(n, station, frm, to):
           expected = pd.read_parquet(FIXTURES / f"case_{n}_{station}_{frm}_{to}.parquet")
           actual = tradewinds.research(station, frm, to)
           actual_c, expected_c = _canon(actual), _canon(expected)
           # PARITY-03: dtype ground truth
           assert {c: str(d) for c, d in actual_c.dtypes.items()} == EXPECTED_DTYPES[f"case_{n}"], (
               f"dtype mismatch case {n}\nactual: {dict(actual_c.dtypes)}\nexpected: {EXPECTED_DTYPES[f'case_{n}']}"
           )
           # PARITY-02: value + dtype equivalence
           assert_frame_equal(actual_c, expected_c, check_dtype=True, check_exact=True)

       def test_dtypes_match_ground_truth():
           """PARITY-03: expected_dtypes.json is the ground-truth dtype contract."""
           for n, station, frm, to in CASES:
               df = pd.read_parquet(FIXTURES / f"case_{n}_{station}_{frm}_{to}.parquet")
               df = df.reset_index() if df.index.name else df
               actual = {c: str(d) for c, d in df.dtypes.items()}
               assert actual == EXPECTED_DTYPES[f"case_{n}"]
       ```
    3. **Run the test. Expect failure(s).** This is the iteration loop. Likely failure modes and fixes (from RESEARCH.md risk register):
       - **Failure mode A (most likely):** `obs_count` differs by ~30% on busy stations. Cause: SPECI excluded from iem_asos fetch (Pitfall 3). Fix: verify `_fetchers/iem_asos.py` emits both METAR (`obs_type=3`) and SPECI (`obs_type=4`) rows; if not, patch the fetcher's monthly_chunks loop.
       - **Failure mode B:** `obs_high_f` / `obs_low_f` differ on KLAX (case 3) for the DST-boundary date 2025-03-09. Cause: settlement-date grouping wrong (Pitfall 1). Verify `research.py` groups via `settlement_date_for(observed_at, station)`, NOT `observed_at[:10]`.
       - **Failure mode C:** `obs_mean_f` differs by 1-ULP in some row. Cause: float averaging order (R2). Verify pre-sort by `observed_at` before passing to `build_pairs`. If still failing, relax to rung 2 (`atol=0`) — same numeric values, looser float comparator.
       - **Failure mode D:** `station` column is "KNYC" not "NYC". Cause: missed `_station_code_normalized` (R3). Fix in research.py.
       - **Failure mode E:** `fcst_*` columns dtype drift — emitted as float64 NaN instead of object None. Cause: `build_pairs` called with `forecasts_by_date={}` instead of `forecasts_by_date=None` (R4). Fix: pass `None`.
       - **Failure mode F:** `cli_report_type` mismatch on case 4 (full-year Miami, year boundary). Cause: climate annual cache key off-by-one. Verify `_fetch_climate_range` iterates years inclusively.
       - **Failure mode G:** Case 5 KMSY misses rows. Cause: AWC fetcher silently failed (last-168h limitation) and merge logic mishandled empty-AWC. Verify `merge_observations` accepts `[] + iem_rows` and returns `iem_rows` unchanged.
    4. **Each fix = atomic commit** on `phase-1/wave-3-parity`. Commit message format:
       ```
       fix(phase-1): case {n} {station} — {root cause} ({pitfall ref})

       - {what was broken}
       - {how fixed}
       - Tolerance rung: 1 (check_exact=True)
       ```
    5. **If float diff persists after all root-cause fixes:** relax to rung 2 (`check_exact=False, rtol=0, atol=0`). If that still fails, escalate to rung 3 (`atol=1e-12`). Document the rung in the test docstring AND in the wave-3 merge commit message. Rung 4 (`atol=1e-9`) requires explicit human review — flag to founder before relaxing.
    6. **Sanity check:** after all 5 cases green, run the entire `pytest -m "not live" -q` suite from repo root. No regressions in Wave 1 or Wave 2 tests.
  </action>
  <verify>
    <automated>uv run pytest tests/test_parity.py -x -v</automated>
    Full smoke: `uv run pytest -m "not live" -q` (whole suite, expect ≥700 tests still green plus new ones from Wave 1-3).
  </verify>
  <done>
    All 5 `test_parity_case[n-station-frm-to]` pass. `test_dtypes_match_ground_truth` passes. `expected_dtypes.json` committed. Full test suite green. Tolerance rung documented (default rung 1; if relaxed, note the rung + reason in the wave-3 merge commit body). Codex MEDIUM-priority review approved (test code itself; the source fixes that landed during the bug-fix loop already had HIGH-priority review from their respective wave-1/wave-2 sub-branches — Codex reviews the cumulative diff against `merged-vision`).
  </done>
</task>

</wave>

<wave id="4" name="Pre-publish hygiene + founder action prep" day="Day 4" parallel="false">

**Goal:** Tighten pyproject.toml pins, write lift-inventory docstrings, produce three wheels, document the exact `uv publish` commands for the founder. The PyPI publish itself is FOUNDER ACTION (requires `UV_PUBLISH_TOKEN`).

**Branch:** `phase-1/wave-4-prepublish` off `merged-vision` (with Wave 3 HARD GATE passed and merged).

**Wave 4 exit gate:** `uv build --all-packages` produces three valid wheels; founder approves; founder publishes; post-publish smoke test green in clean venv.

<task id="4.1" type="auto" branch="phase-1/wave-4-prepublish" codex_priority="LOW">
  <name>Task 4.1: Tighten dep pins + version bumps + lift-inventory docstrings + packaging tests</name>
  <implements>CATALOG-06, PKG-02, PKG-04, PKG-05, PKG-06.</implements>
  <files>
    packages/core/pyproject.toml (MODIFY — version + pandas + pyarrow pins)
    packages/weather/pyproject.toml (MODIFY — version + pandas + pyarrow pins)
    packages/markets/pyproject.toml (MODIFY — no version bump; verify metadata only)
    packages/core/src/tradewinds/_internal/__init__.py (MODIFY — lift inventory docstring)
    packages/weather/src/tradewinds/weather/__init__.py (MODIFY — lift inventory docstring)
    tests/test_packaging.py (NEW, ~40 LOC — assert pin bounds)
    tests/test_wheel_layout.py (NEW, ~50 LOC — assert PEP 420 namespace integrity)
    README.md (MODIFY — workspace-level quickstart added)
    uv.lock (MODIFY — regenerated after pin tightening)
  </files>
  <behavior>
    - `packages/core/pyproject.toml` `[project]` section: `version = "0.1.0a1"`; `dependencies` includes `pandas>=2.2,<3.0` and `pyarrow>=17.0,<24.0`.
    - `packages/weather/pyproject.toml` `[project]` section: `version = "0.1.0a1"`; same `pandas` and `pyarrow` pins.
    - `packages/markets/pyproject.toml` stays at `version = "0.0.1"` (no impl; namespace reservation only).
    - `uv build --all-packages` produces three wheels in `dist/`: `tradewinds-0.1.0a1-py3-none-any.whl`, `tradewinds_weather-0.1.0a1-py3-none-any.whl`, `tradewinds_markets-0.0.1-py3-none-any.whl`.
    - `unzip -l dist/tradewinds-0.1.0a1-*.whl | grep '__init__.py'` shows `tradewinds/__init__.py`.
    - `unzip -l dist/tradewinds_weather-0.1.0a1-*.whl | grep '__init__.py'` does NOT show a top-level `tradewinds/__init__.py` (only `tradewinds/weather/__init__.py` and deeper). Same for `tradewinds_markets`.
    - `_internal/__init__.py` docstring documents lift inventory: snapshot.py, _stations.py, _pairs.py, merge/observations.py, merge/climate.py, merge/_schemas.py with source path + git SHA + lift date + modifications per module.
    - `weather/__init__.py` docstring documents lift inventory for the 4 parsers (already lifted on `merged-vision` — Wave 4 just adds the provenance block).
  </behavior>
  <action>
    1. **Version bumps:**
       - `packages/core/pyproject.toml`: change `version = "0.0.1"` → `version = "0.1.0a1"`.
       - `packages/weather/pyproject.toml`: same.
       - `packages/markets/pyproject.toml`: leave at `0.0.1` (or `0.1.0a1` if already at a placeholder above 0.0.1 — verify on `merged-vision` head; stay consistent).
    2. **Pin tightening (PKG-05, PKG-06):**
       - In BOTH `packages/core/pyproject.toml` and `packages/weather/pyproject.toml`, find `dependencies = [...]` and update:
         - `"pandas>=2.2"` → `"pandas>=2.2,<3.0"` (PKG-05; pandas 3.0 breaking changes deferred per RESEARCH.md A1).
         - `"pyarrow>=17.0"` → `"pyarrow>=17.0,<24.0"` (PKG-06; matches v0.14.1 floor; soft upper avoids future surprise per RESEARCH.md §Gap-5).
    3. **Cross-package version pin (PKG-03 placeholder — formal CI check is Phase 4):**
       - `packages/weather/pyproject.toml`: ensure dependencies includes `"tradewinds>=0.1.0a1,<0.2"`. Update if missing.
    4. **PEP 420 verification (PKG-02):**
       - Confirm `packages/weather/src/tradewinds/` has NO `__init__.py` at that level.
       - Confirm `packages/markets/src/tradewinds/` has NO `__init__.py` at that level.
       - Only `packages/core/src/tradewinds/__init__.py` exists.
       - If any extras have crept in during foundations work, delete them.
    5. **Lift inventory docstrings (CATALOG-06):**
       - `packages/core/src/tradewinds/_internal/__init__.py`: add a multi-line module docstring at the top:
         ```python
         """tradewinds._internal — shared utilities lifted from monorepo-v0.14.1.

         Lift inventory (provenance for parity-critical code):

         | Module                          | Source path                                          | Source SHA | Lift date  | Modifications |
         |---------------------------------|------------------------------------------------------|------------|------------|---------------|
         | _http.py                        | monorepo-v0.14.1/src/mostlyright/_http.py            | <SHA>      | <date>     | namespace rename |
         | _convert.py                     | monorepo-v0.14.1/src/mostlyright/_convert.py         | <SHA>      | <date>     | namespace rename |
         | _bounds.py                      | monorepo-v0.14.1/src/mostlyright/_bounds.py          | <SHA>      | <date>     | namespace rename |
         | _capabilities.py                | monorepo-v0.14.1/src/mostlyright/_capabilities.py    | <SHA>      | <date>     | namespace rename |
         | exceptions.py                   | monorepo-v0.14.1/src/mostlyright/exceptions.py       | <SHA>      | <date>     | namespace rename |
         | versioning.py                   | monorepo-v0.14.1/src/mostlyright/versioning.py       | <SHA>      | <date>     | namespace rename |
         | models/                         | monorepo-v0.14.1/src/mostlyright/models/             | <SHA>      | <date>     | namespace rename |
         | specs/*.json                    | monorepo-v0.14.1/src/mostlyright/specs/              | <SHA>      | <date>     | none (data-only) |
         | _stations.py                    | monorepo-v0.14.1/src/mostlyright/_stations.py        | <SHA>      | <Wave 1>   | namespace rename |
         | _pairs.py                       | monorepo-v0.14.1/src/mostlyright/pairs.py            | <SHA>      | <Wave 2>   | namespace rename + TOON excised |
         | merge/observations.py           | monorepo-v0.14.1/ingest/storage/parquet.py:47,246-261 | <SHA>     | <Wave 1>   | rename _dedup_rows -> merge_observations |
         | merge/climate.py                | monorepo-v0.14.1/ingest/storage/parquet.py:477-494   | <SHA>      | <Wave 1>   | rename _dedup_climate_rows -> merge_climate |
         | merge/_schemas.py               | monorepo-v0.14.1/ingest/storage/parquet.py:51-103    | <SHA>      | <Wave 1>   | none |
         """
         ```
       - Run `git -C ../monorepo-v0.14.1 rev-parse HEAD` once; paste the SHA into every `<SHA>` slot. Use `2026-05-21` (or the actual Wave date) for each `<date>`.
       - `packages/weather/src/tradewinds/weather/__init__.py`: same docstring pattern for `_awc.py`, `_iem.py`, `_climate.py`, `_ghcnh.py`, `_bounds.py`, `_fetchers/awc.py`, `_fetchers/iem_asos.py`, `_fetchers/iem_cli.py`, `_fetchers/ghcnh.py`, `cache.py`. The 4 fetchers are NEW (not lifted); mark "NEW (Sprint 0 Day 1-2)" in the Modifications column. `cache.py` is NEW (Wave 1); same.
    6. **Packaging tests:**
       - `tests/test_packaging.py`:
         ```python
         import tomllib
         from pathlib import Path

         ROOT = Path(__file__).parents[1]

         def _pyproject(pkg: str) -> dict:
             return tomllib.loads((ROOT / "packages" / pkg / "pyproject.toml").read_text())

         def test_pandas_upper_bound():
             for pkg in ("core", "weather"):
                 deps = _pyproject(pkg)["project"]["dependencies"]
                 assert any("pandas>=2.2,<3.0" in d for d in deps), f"{pkg} missing pandas upper bound"

         def test_pyarrow_upper_bound():
             for pkg in ("core", "weather"):
                 deps = _pyproject(pkg)["project"]["dependencies"]
                 assert any("pyarrow>=17.0,<24.0" in d for d in deps), f"{pkg} missing pyarrow upper bound"

         def test_core_version_is_alpha1():
             assert _pyproject("core")["project"]["version"] == "0.1.0a1"

         def test_weather_version_is_alpha1():
             assert _pyproject("weather")["project"]["version"] == "0.1.0a1"
         ```
       - `tests/test_wheel_layout.py`:
         ```python
         """PKG-02 + PKG-04: PEP 420 namespace integrity after build."""
         import subprocess
         import zipfile
         from pathlib import Path

         ROOT = Path(__file__).parents[1]
         DIST = ROOT / "dist"

         def _build_wheels():
             # Clean and build
             for wheel in DIST.glob("*.whl") if DIST.exists() else []:
                 wheel.unlink()
             subprocess.run(["uv", "build", "--all-packages"], cwd=ROOT, check=True)

         def test_three_wheels_produced():
             _build_wheels()
             wheels = list(DIST.glob("*.whl"))
             assert len(wheels) == 3, f"expected 3 wheels, got {[w.name for w in wheels]}"

         def test_no_init_collision():
             _build_wheels()
             core_wheel = next(DIST.glob("tradewinds-0.1.0a1-*.whl"))
             weather_wheel = next(DIST.glob("tradewinds_weather-0.1.0a1-*.whl"))
             markets_wheel = next(DIST.glob("tradewinds_markets-*.whl"))

             def _has_top_init(wheel: Path) -> bool:
                 with zipfile.ZipFile(wheel) as z:
                     return "tradewinds/__init__.py" in z.namelist()

             assert _has_top_init(core_wheel), "core wheel must ship tradewinds/__init__.py"
             assert not _has_top_init(weather_wheel), "weather wheel must NOT ship tradewinds/__init__.py (PEP 420)"
             assert not _has_top_init(markets_wheel), "markets wheel must NOT ship tradewinds/__init__.py (PEP 420)"
         ```
    7. **README quickstart update:** add at the top of repo-root `README.md`:
       ```markdown
       ## Quickstart (alpha1)

       ```bash
       pip install "tradewinds[parquet]==0.1.0a1" "tradewinds-weather[parquet]==0.1.0a1"
       python -c "import tradewinds as tw; print(tw.research('KNYC', '2025-01-06', '2025-01-12').head())"
       ```

       That's it. `research(station, from_date, to_date)` returns a pandas DataFrame; local parquet cache lives at `$HOME/.tradewinds/cache/` (override with `TRADEWINDS_CACHE_DIR`); no API keys; no hosted backend.
       ```
       Keep the rest of README.md unchanged.
    8. **Regenerate lockfile:** `uv sync` to update `uv.lock` with the tightened pins. Commit the lockfile change.
  </action>
  <verify>
    <automated>uv run pytest tests/test_packaging.py tests/test_wheel_layout.py -x -v</automated>
    Manual: `uv build --all-packages && ls dist/ | sort` shows the three wheels (core 0.1.0a1, weather 0.1.0a1, markets 0.0.1) + their sdists.
    Manual: `unzip -l dist/tradewinds_weather-0.1.0a1-*.whl | grep '__init__'` should show ONLY `tradewinds/weather/__init__.py` and deeper, NEVER `tradewinds/__init__.py` at the top level.
  </verify>
  <done>
    `test_packaging.py` (4 tests) all green. `test_wheel_layout.py` (2 tests) all green. Three wheels in `dist/`. Lift-inventory docstrings present in both `_internal/__init__.py` and `weather/__init__.py` with real SHAs. README quickstart present. `uv.lock` regenerated. Codex LOW-priority review approved (docs + config; no source-code parity risk).
  </done>
</task>

<task id="4.2" type="checkpoint:human-action" gate="blocking" branch="phase-1/wave-4-prepublish">
  <name>Task 4.2: FOUNDER ACTION — Publish alpha wheels to PyPI</name>
  <implements>PKG-04 publish half.</implements>
  <what-built>
    Three wheels in `dist/` (validated by Task 4.1):
    - `tradewinds-0.1.0a1-py3-none-any.whl` + sdist
    - `tradewinds_weather-0.1.0a1-py3-none-any.whl` + sdist
    - `tradewinds_markets-0.0.1-py3-none-any.whl` + sdist
    Lift-inventory docstrings, pin tightening, packaging tests all green on `phase-1/wave-4-prepublish`.
  </what-built>
  <why-human>
    PyPI publish requires `UV_PUBLISH_TOKEN` (account-scoped API token tied to operator vuhcze@gmail.com). Claude cannot autonomously authenticate to PyPI. The token must not be committed to the repo or passed through Claude's context — founder runs the publish commands directly in their shell.
  </why-human>
  <founder-instructions>
    **Pre-flight checks (founder runs):**
    ```bash
    cd /Users/helloiamvu/Documents/GitHub/tradewinds
    git checkout phase-1/wave-4-prepublish
    uv build --all-packages
    ls dist/ | sort
    # Expect: tradewinds-0.1.0a1.tar.gz, tradewinds-0.1.0a1-py3-none-any.whl,
    #         tradewinds_weather-0.1.0a1.tar.gz, tradewinds_weather-0.1.0a1-py3-none-any.whl,
    #         tradewinds_markets-0.0.1.tar.gz, tradewinds_markets-0.0.1-py3-none-any.whl
    ```

    **Optional TestPyPI dry-run** (RECOMMENDED — burns version `0.1.0a1.dev1`, NOT the real `0.1.0a1`; see RESEARCH.md Pitfall 4):
    ```bash
    # Bump to .dev1 just for TestPyPI
    # Edit packages/core/pyproject.toml: version = "0.1.0a1.dev1"
    # Edit packages/weather/pyproject.toml: version = "0.1.0a1.dev1"
    uv build --all-packages
    UV_PUBLISH_TOKEN=$TESTPYPI_TOKEN uv publish --publish-url https://test.pypi.org/legacy/ \
      dist/tradewinds-0.1.0a1.dev1*.whl dist/tradewinds-0.1.0a1.dev1*.tar.gz \
      dist/tradewinds_weather-0.1.0a1.dev1*
    # Then revert to 0.1.0a1 and rebuild for real PyPI.
    git checkout -- packages/core/pyproject.toml packages/weather/pyproject.toml
    uv build --all-packages
    ```

    **Real PyPI publish:**
    ```bash
    UV_PUBLISH_TOKEN=$PYPI_TOKEN uv publish \
      dist/tradewinds-0.1.0a1*.whl dist/tradewinds-0.1.0a1*.tar.gz
    UV_PUBLISH_TOKEN=$PYPI_TOKEN uv publish \
      dist/tradewinds_weather-0.1.0a1*.whl dist/tradewinds_weather-0.1.0a1*.tar.gz
    # Only publish markets if 0.0.1 isn't already on PyPI:
    UV_PUBLISH_TOKEN=$PYPI_TOKEN uv publish \
      dist/tradewinds_markets-0.0.1*.whl dist/tradewinds_markets-0.0.1*.tar.gz
    ```

    **Post-publish smoke (founder runs in a clean venv):**
    ```bash
    python3 -m venv /tmp/tw-postpublish-venv
    source /tmp/tw-postpublish-venv/bin/activate
    pip install "tradewinds[parquet]==0.1.0a1" "tradewinds-weather[parquet]==0.1.0a1"
    python -c "
    import tradewinds as tw
    df = tw.research('KNYC', '2025-04-01', '2025-04-07')
    print(df.shape)
    print(df.columns.tolist())
    assert df.shape[0] == 7, f'expected 7 rows, got {df.shape[0]}'
    print('Post-publish smoke: PASS')
    "
    deactivate
    rm -rf /tmp/tw-postpublish-venv
    ```
  </founder-instructions>
  <resume-signal>
    Founder responds either:
    - "PUBLISHED — smoke green; here are the PyPI URLs: https://pypi.org/project/tradewinds/0.1.0a1/ and https://pypi.org/project/tradewinds-weather/0.1.0a1/"
    - "FAILED at {step} with {error}; need fix"
    On PUBLISHED: Claude merges `phase-1/wave-4-prepublish` to `merged-vision`, tags `v0.1.0a1` on the merge commit, and closes Phase 1.
    On FAILED: Claude opens a fix-up sub-branch off `phase-1/wave-4-prepublish` and addresses the specific failure (most likely: METADATA `Requires-Dist` missing inter-package pin, OR pyarrow ABI mismatch on the build host).
  </resume-signal>
  <verify>
    Manual (founder): post-publish `pip install` + smoke yields a DataFrame with 7 rows.
    Automated (Claude after PUBLISHED signal): `git tag v0.1.0a1 <merge-commit-sha> && git push origin v0.1.0a1`.
  </verify>
  <done>
    Both `tradewinds==0.1.0a1` and `tradewinds-weather==0.1.0a1` resolvable from PyPI (`pip index versions tradewinds` shows `0.1.0a1`). Post-publish smoke green in a clean venv. `v0.1.0a1` git tag pushed to origin. `phase-1/wave-4-prepublish` merged to `merged-vision`. Phase 1 closed.
  </done>
</task>

</wave>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `research()` → IEM ASOS / IEM CLI / GHCNh / AWC HTTP endpoints | Untrusted CSV/JSON payloads from public APIs cross into the parser layer. |
| `read_cache()` → on-disk parquet | Local parquet files could be corrupted by partial writes (crash mid-`write_cache`) or tampered with by an attacker with disk access. |
| Founder shell → `uv publish` | Publish secret (`UV_PUBLISH_TOKEN`) crosses from founder's env to PyPI. Token must not leak into Claude's context, repo, or logs. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Tampering | `read_cache()` reading partially-written parquet | mitigate | Atomic write via `.tmp` + `os.rename` inside `FileLock`. `pq.read_table()` raises `pyarrow.lib.ArrowInvalid` on corrupted bytes — surface to caller, do not silently return None. |
| T-01-02 | Denial-of-service | `_fetchers/*.py` against rate-limited public APIs | accept | All four endpoints are no-auth public. `_internal/_http.py` already has retry + backoff (CORE-06 lifted). Worst case: a single `research()` call sleeps + retries; not a system risk. |
| T-01-03 | Information Disclosure | Lift-inventory docstring exposing `monorepo-v0.14.1` git SHA | accept | SHA is from a private worktree but the lifted code itself is MIT-licensed (same as tradewinds). SHA disclosure is provenance, not a secret. |
| T-01-04 | Tampering | Concurrent `write_cache` workers corrupting same parquet | mitigate | `FileLock(timeout=30)` blocks the second writer until the first completes. Test in Task 1.4 spawns 2 multiprocessing workers and verifies no truncation. |
| T-01-05 | Elevation of Privilege | `TRADEWINDS_CACHE_DIR` set to a path the user can't write | accept | `Path.mkdir(parents=True, exist_ok=True)` raises `PermissionError`; surface to user. Not a privilege-elevation vector. |
| T-01-06 | Tampering | Parser receives malformed IEM/AWC payload | mitigate | All 4 parsers are lifted from v0.14.1 with W3A Codex hardening already applied (per RESEARCH.md "What's DONE"). Validation already in place via `jsonschema` in `_internal/specs/`. |
| T-01-07 | Spoofing | `UV_PUBLISH_TOKEN` leak via Claude context | mitigate | Task 4.2 instructions explicitly direct founder to run `uv publish` outside Claude's session. Token never enters Claude's input. |
| T-01-08 | Repudiation | Wrong source SHA in lift-inventory docstring | mitigate | Task 4.1 specifies running `git -C ../monorepo-v0.14.1 rev-parse HEAD` once and pasting the exact SHA. Codex LOW-priority review verifies SHA is non-placeholder. |
| T-01-09 | Tampering | `merge_observations` row-order dependence (R2) | mitigate | Pre-sort by `observed_at` in `_fetch_observations_range` before passing to `merge_observations` (which is stable-on-tie). Documented in Task 2.1 action step 3. |
| T-01-10 | Information Disclosure | `expected_dtypes.json` capture script reads fixtures | accept | Fixtures are committed to the repo; dumping their dtypes to JSON is a copy operation, no disclosure beyond what's already in git. |

</threat_model>

<verification>

## Per-Wave Verification

| Wave | Command | Expected |
|------|---------|----------|
| Wave 1 (after all sub-branches merged to `phase-1/wave-1`) | `uv run pytest -m "not live" -q` | All previous tests still green + new: ~80 LOC of snapshot tests, ~120 LOC of merge tests (4-6 obs cases + 1 synthetic + 4-6 climate cases), ~150 LOC of cache tests (8 tests). |
| Wave 2 (after `phase-1/wave-2-research` merged) | `uv run pytest -m "not live" -q` + manual `python -c "import tradewinds as tw; df = tw.research('KNYC', '2025-01-06', '2025-01-12'); print(df.shape, df.columns.tolist())"` | Returns DataFrame `(7, 19)` with expected columns. Cache files materialize at `$HOME/.tradewinds/cache/v1/observations/NYC/2025/01.parquet`. |
| Wave 3 (HARD GATE) | `uv run pytest tests/test_parity.py -x -v` | 5/5 parametrized cases pass + `test_dtypes_match_ground_truth` passes. |
| Wave 4 (Claude side) | `uv run pytest tests/test_packaging.py tests/test_wheel_layout.py -x` + `uv build --all-packages` | 6 tests green; 3 wheels in `dist/`. |
| Wave 4 (founder side, post-publish) | `pip install "tradewinds[parquet]==0.1.0a1" "tradewinds-weather[parquet]==0.1.0a1"` in clean venv → `tw.research('KNYC', '2025-04-01', '2025-04-07')` | Returns 7-row DataFrame. |

## Phase Exit Gate (must be true to close Phase 1)

- [ ] All 5 parity fixtures pass `assert_frame_equal(actual_canon, expected_canon, check_dtype=True, check_exact=True)` (HARD GATE).
- [ ] `tradewinds==0.1.0a1` and `tradewinds-weather==0.1.0a1` resolvable from PyPI.
- [ ] Post-publish smoke green in clean venv.
- [ ] `v0.1.0a1` git tag pushed.
- [ ] `merged-vision` contains Wave 1-4 merge commits in order.
- [ ] All 11 phase requirements (PARITY-01..03, CORE-06, CATALOG-06, PKG-02, PKG-04, PKG-05, PKG-06, CACHE-01, CACHE-07) have a green test backing them.

</verification>

<success_criteria>

Phase 1 is complete when:

1. **HARD GATE PASSED:** `pytest tests/test_parity.py -x` green on all 5 parametrized cases (PARITY-01, PARITY-02). The chosen `check_exact` tolerance rung documented in commit history.
2. **Ground-truth dtypes committed:** `tests/fixtures/parity/expected_dtypes.json` present; `test_dtypes_match_ground_truth` green (PARITY-03).
3. **Wheels published:** `pip install "tradewinds[parquet]==0.1.0a1" "tradewinds-weather[parquet]==0.1.0a1"` works from a fresh venv; `tradewinds_markets==0.0.1` namespace-reserved (PKG-04).
4. **No PEP 420 collision:** `tests/test_wheel_layout.py::test_no_init_collision` green (PKG-02).
5. **Pin tightening landed:** `tests/test_packaging.py::test_pandas_upper_bound` + `test_pyarrow_upper_bound` green (PKG-05, PKG-06).
6. **Lift inventory documented:** `_internal/__init__.py` and `weather/__init__.py` docstrings contain provenance table with real `monorepo-v0.14.1` git SHA (CATALOG-06).
7. **Cache layer working:** `tests/test_cache.py` 8/8 green; concurrent-writer test passes (CACHE-01, CACHE-07).
8. **Merge policies verified:** observation + climate dedup tests all green, including synthetic AWC-gap-IEM-fills case (CORE-06).
9. **HTTP layer audited:** existing `_internal/_http.py` (already lifted) reviewed; retry/timeout/User-Agent confirmed present (CORE-06).
10. **No regressions:** full `pytest -m "not live" -q` green across all packages (~700+ existing tests + new Wave 1-4 tests).

</success_criteria>

<output>

After Phase 1 completes:

1. Create `.planning/phase-01-v0-14-1-parity-lift/SUMMARY.md` capturing:
   - Tolerance rung chosen (rung 1, 2, 3, or 4) + reason if relaxed below rung 1.
   - Per-fixture row counts (KNYC=7, KMDW=30, KLAX=31, KMIA=365, KMSY=15) confirmed.
   - Number of bug-fix iterations in Wave 3 (and what they fixed — feeds Phase 2's understanding of merge edge cases).
   - PyPI URLs for the published alpha1 wheels.
   - Outstanding risks deferred to Phase 2 (e.g., if rung 2+ relaxation was needed, document the float-averaging order assumption for Phase 2's revisit).

2. Update `.planning/ROADMAP.md` Phase 1 entry: change `[ ]` to `[x]`; update plans count to `1/1 plans`; mark status `Complete`.

3. Update `.planning/STATE.md`:
   - Bump `Phase: 1 of 4` → `Phase: 2 of 4 (Core Primitives + Catalog Adapters)`.
   - `Status: Phase 1 complete; alpha1 wheels published; ready for Phase 2 plan` (Phase 2 PLAN.md already exists per repo state).
   - Add to Decisions: tolerance rung chosen.

</output>
