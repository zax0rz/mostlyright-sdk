# Pitfalls Research

**Domain:** Local-first Python SDK for prediction-market weather contracts (Kalshi NHIGH/NLOW, NWS/IEM/AWC/GHCNh data sources, temporal-safety + source-identity invariants)
**Researched:** 2026-05-21
**Confidence:** HIGH for Kalshi settlement specifics + parquet/pyarrow gotchas; MEDIUM for IEM/AWC operational delays and rate limits; LOW for v0.2-era MCP test flakiness (limited public discussion). Verified via Kalshi help docs, IEM docs, NWS instruction 10-1003 references, multiple GitHub issues for pyarrow/pandas, and astral-sh/uv issue tracker.

**Reading guide:** Each pitfall is tagged with **Severity** and **Phase**. Parity-breaking pitfalls (PB) get top priority because the Day 3 hard gate fails for any of them. Silent-data-corruption (SDC) pitfalls are dangerous because they pass tests locally but corrupt live trades. Annoying-but-survivable (ABS) pitfalls are documented to prevent escalation.

---

## Critical Pitfalls

### Pitfall 1: Kalshi settlement-station ID guessed wrong (KNYC, not KLGA/KJFK; KMDW, not KORD)

**Severity:** PARITY-BREAKING + SILENT-DATA-CORRUPTION (entire historical settlement table wrong)
**Phase:** Phase B — CATALOG-05 (Kalshi contract specs)

**What goes wrong:**
A reasonable developer maps "NYC" → `KLGA` or `KJFK` (the canonical aviation METAR stations everyone knows) and "Chicago" → `KORD` (the major hub). Both are wrong for Kalshi settlement. NYC contracts settle on **KNYC (Central Park)**. Chicago contracts settle on **KMDW (Midway)**, NOT O'Hare. The CLI product for `CLINYC` is issued by NWS OKX (Upton, NY) using Central Park, not LGA. Same family of mismatch for other cities (DCA vs IAD vs BWI for DC; KBOS for Boston; KDEN for Denver; KAUS for Austin).

**Why it happens:**
- The most-trafficked station is not the settlement station.
- IEM/AWC return data for ALL three NYC airports; nothing in the response says "this is the settlement station."
- Kalshi's public help page says "NWS Daily Climate Report" but doesn't tabulate station IDs in one place; you have to inspect each city's market page or contract PDF.
- Aviation training data (METAR for ATC) overweights LGA/JFK/ORD relative to the climate stations.

**How to avoid:**
- Hard-code the Kalshi → NWS-station mapping table in `tradewinds.markets.catalog.kalshi_nhigh` and `kalshi_nlow` as a constant `KALSHI_SETTLEMENT_STATIONS`. Treat it as load-bearing (same status as `policies_climate.py`).
- Pin the table with citations to the per-market Kalshi page URL in a comment next to each row.
- Contract test: for every supported contract ticker, assert the resolved settlement station is in the known-good list (KNYC, KMDW, KMIA, KAUS, KLAX, KDEN, KBOS, ...) and never KLGA/KJFK/KORD.
- Property test: `research(contract="KXHIGHNY", ...)` must use a `settlement_source` whose station resolves to `KNYC`, never `KLGA`.

**Warning signs:**
- Settlement parity off by 1-3°F on humid summer days (LGA is windy/warmer than Central Park).
- Backtest PnL diverges from on-chain settlement history.
- Snowfall contracts settle at wildly different values than ASOS hourly highs at the "wrong" station.

**Phase to address:** Phase B (CATALOG-05), with a contract test in Phase B Day 11.

---

### Pitfall 2: Float32 ↔ Float64 silent precision loss through parquet cache roundtrip

**Severity:** PARITY-BREAKING (byte-equivalent test fails)
**Phase:** Phase A (parity lift) + CACHE-01

**What goes wrong:**
The v0.14.1 monorepo emits temperature values as `float64`. The cache writes them to parquet. The next call reads them back. If `pyarrow` (version-dependent) silently casts through `float32` during a partition merge or `coerce_timestamps=` path, or if a pandas dtype falls into the `pyarrow`-backed dtype path (`dtype_backend="pyarrow"`), values like `74.1` come back as `74.099998474121094`. Mode 1 byte-equivalence fails on Day 3 even though the data is "right."

**Why it happens:**
- `pd.read_parquet` does NOT preserve dtype-backend choice from write time unless metadata says so.
- pyarrow 13.0.0 silently changed `datetime64[ns]` → `datetime64[us]` on read (Arrow issue 38171). Same family of silent cast exists for floats when version mismatches.
- Some monorepo paths may have used `pyarrow.compute.cast(...)` for memory reasons; lifting verbatim into a fresh pyproject with looser pin can shift it.

**How to avoid:**
- Pin `pyarrow` and `pandas` to the EXACT versions used in `monorepo-v0.14.1/pyproject.toml`. Do not let `uv add` resolve. (Already in TODOS.md — promote to a Day 1 gate.)
- In `cache.py`, set `pyarrow.parquet.write_table(..., version="2.6", use_compliant_nested_type=True, coerce_timestamps="us")` explicitly. Never rely on defaults.
- After every cache write, do a read-back-and-compare check on the first 10 rows in `pytest.mark.live` smoke tests.
- Parity fixtures stored as parquet on disk; compare via `df.equals(other)` AND `np.allclose(df.values, other.values, rtol=0, atol=0)` — `equals` returns True for NaN-equal-NaN but False for any precision drift; `allclose(rtol=0, atol=0)` is exact-equal for floats.

**Warning signs:**
- `test_parity.py` fails with diff of `0.000000000001`.
- A pristine fixture passes today, fails after `uv lock --upgrade`.
- `df.dtypes` shows `float64[pyarrow]` instead of plain `float64`.

**Phase to address:** Phase A Day 1 (pinning) + Phase A Day 3 (parity gate is the trip wire).

---

### Pitfall 3: Timezone-aware vs timezone-naive timestamps coerced through parquet

**Severity:** PARITY-BREAKING + SILENT-DATA-CORRUPTION (DST off-by-one across the boundary)
**Phase:** Phase A + Phase B (CORE-01 `TimePoint`)

**What goes wrong:**
Parquet stores timestamps as int64 with a unit (ns/us/ms) and an OPTIONAL timezone tag stored in the Arrow schema (NOT the parquet schema). pyarrow reads naive timestamps and **silently interprets them as UTC** when converting back to pandas. The CLI product timestamp ("649 PM PDT TUE MAY 19 2026") is parsed to a localized datetime in LST/LDT, written to cache as `datetime64[ns, US/Eastern]`, and read back as `datetime64[ns]` (naive UTC). The next merge against IEM observations (also "naive UTC" but actually LST) shifts every observation by 4-5 hours, off-by-one-day for late-evening highs.

**Why it happens:**
- pandas-to-arrow metadata preserves the timezone IF the Arrow schema metadata block was written. But cross-engine reads (e.g., fastparquet writing, pyarrow reading) drop it.
- Apache Arrow issue 37355: `pyarrow.parquet.read_table` with filters was broken for timezone-aware timestamps since 13.0.0.
- `coerce_timestamps="us"` is required for some downstream tools, and the coerce path is one of the silent-tz-loss code paths.
- Kalshi NHIGH/NLOW settlement uses LST (Local Standard Time — not LDT), and the CLI product's "valid until 23:59 LST" rule is the only correct interpretation. Naive UTC interpretation breaks every day-boundary case.

**How to avoid:**
- Define a single canonical timestamp representation in `tradewinds.core.temporal.TimePoint`: always store as UTC tz-aware (`Timestamp("...", tz="UTC")`).
- Convert at I/O boundaries: parse local-time CLI products to UTC immediately; convert back to LST only at display time.
- In `cache.py`, when writing parquet: pass an explicit `pyarrow.schema` with `timestamp("us", tz="UTC")` for every timestamp column. When reading: assert the schema's timestamp columns have `tz` set and equal `"UTC"`.
- Property test (Hypothesis) for `TimePoint`: draw datetimes in `[2015-01-01, 2026-12-31]` UTC, roundtrip through parquet, assert exact equality at us precision.
- Property test for DST boundary: explicitly draw datetimes in `[2024-03-09 06:00 UTC, 2024-03-10 12:00 UTC]` (DST spring forward) and `[2024-11-02 04:00 UTC, 2024-11-03 12:00 UTC]` (fall back). These ranges should be constrained explicitly rather than via shrinking, because Hypothesis is known to be inefficient at shrinking timezone-aware datetime pathologies (see Hypothesis issues 2273, 2662).

**Warning signs:**
- `df["event_time"].dt.tz` returns `None` after cache read.
- Daily highs appear in the wrong row date (e.g., the 5pm high gets bucketed to the next day).
- Parity test diff shows the same temperature value but `event_time` 5 hours off.

**Phase to address:** Phase B Day 5 (`TimePoint` + `KnowledgeView`) with property tests immediately.

---

### Pitfall 4: pandas categorical dtype lost on parquet roundtrip (station IDs, source IDs)

**Severity:** PARITY-BREAKING (dtype mismatch fails `df.equals`)
**Phase:** Phase A (CACHE-01) + Phase B (CORE-05 format serializers)

**What goes wrong:**
`station_id`, `source`, `report_type` are natural categoricals. v0.14.1 may or may not have used `pd.Categorical` for these — but if either side does and the other doesn't, parity fails. Worse: pyarrow engine reading a parquet file written with pyarrow engine **silently** converts string categoricals back to `object` dtype unless `read_dictionary=[...]` is passed explicitly. (Pandas issue 26616, dask issue 9966.) fastparquet engine preserves categoricals; pyarrow doesn't. Mixing fastparquet write and pyarrow read produces `object` dtype on the read side.

**Why it happens:**
- Default pandas-to-arrow conversion stores the categorical metadata, but the default arrow-to-pandas conversion ignores it unless told.
- Numeric categoricals (e.g., `report_type_priority`) are read back as int64 directly (not as category).

**How to avoid:**
- Phase A: explicitly inspect monorepo-v0.14.1's `client.pairs()` output dtypes via `dtypes.to_dict()` and pin them in `tests/fixtures/parity/expected_dtypes.json`. Parity test asserts dtypes match exactly.
- In `cache.py`, when reading: pass `read_dictionary=["station_id", "source", "report_type"]` to `pyarrow.parquet.read_table()`.
- Decide upfront whether the canonical research output uses `pd.Categorical` for these columns or plain string. Document in `schema.observation.v1`. Validate with Validator.
- Roundtrip test for each format: `df` → parquet → read → assert `df.equals(read_back)` AND `assert df.dtypes.equals(read_back.dtypes)`.

**Warning signs:**
- Parity test fails with "dtype mismatch: category != object".
- `df.memory_usage(deep=True)` doubles after a cache read.

**Phase to address:** Phase A Day 1 (capture v0.14.1 dtypes); Phase A Day 3 (parity gate); Phase B Day 8 (format serializer roundtrip tests).

---

### Pitfall 5: CLI product timestamp parsing — late-night issuance straddling DST

**Severity:** SILENT-DATA-CORRUPTION (settlement day attributed to wrong calendar date)
**Phase:** Phase B — CATALOG-03 (`cli` adapter, `_parse_product_timestamp` already in `_vendor`)

**What goes wrong:**
CLI products are issued between 12:30 AM and 5:00 AM local time the next morning. The product header carries UTC ("KOKX 200647" = 06:47 UTC on the 20th) AND a local time in the body ("147 AM EDT TUE MAY 20 2026"). The product **summarizes the calendar day that just ended in LST** — but on the spring-forward DST night, the prior day was 23 hours, and on the fall-back DST night, the prior day was 25 hours. Worse: the product is issued in LDT (the new daylight time, e.g., EDT) but the CLI rules state "23:59 LST" — so on the spring-forward Sunday morning, the summary is for the 23-hour day in LST. Naive parsing of "147 AM EDT" → "prior calendar day = 2026-05-19 LST" can be off if the parser uses `dateutil` with `tzname` matching against an EDT abbreviation while the body says EST.

**Why it happens:**
- The CLI text product mixes timezones in different segments (header is UTC, body is "PDT" or "PST" depending on whether it's summer or winter — but the data is always in LST).
- `dateutil.tz.tzlocal()` is not a stable parser for these strings; it picks whatever the host is set to.
- On a late-night issuance crossing midnight UTC (e.g., 23:47 EST on Dec 31 = 04:47 UTC Jan 1), the date in the UTC header is one day ahead of the date in the local body — and the data is for the day BEFORE the local-body date.

**How to avoid:**
- Lift `_parse_product_timestamp` from `monorepo-v0.14.1/_climate.py` verbatim — do not "improve" it. It was hardened against these cases.
- Contract test: feed a known DST-spring-forward CLI product (e.g., 2024-03-10) and a known DST-fall-back CLI product (2024-11-03) as fixtures; assert the parsed `summary_date` is the LST calendar day that just ended.
- Late-night fixture: feed a CLI product issued at 11:47 PM PST on Dec 31 (06:47 UTC Jan 1) and assert `summary_date == 2024-12-31`, not `2025-01-01`.
- Validator check: `summary_date` must be ≤ `issued_at_local_date` and ≥ `issued_at_local_date - 2 days` (allowing up to 48h late). Anything outside that flags as suspicious.

**Warning signs:**
- A handful of settlements off-by-one-day on March or November weekends.
- Mismatch between `cli_high_f` and ASOS hourly max in obs table for the supposedly same day.

**Phase to address:** Phase B Day 7 (`cli` adapter wrap), with parity fixtures including DST boundary cases.

---

### Pitfall 6: NWS substitutes data from "nearby representative" station when primary is missing — silent

**Severity:** SILENT-DATA-CORRUPTION (settlement at city A actually reflects city B's data, no flag in row)
**Phase:** Phase B — CATALOG-03 (`cli` adapter) + CORE-02 (Validator)

**What goes wrong:**
Per NWS Instruction 10-1003 / weather.gov/im/datamis.htm: when the ASOS sensor at the settlement station fails or returns missing for a temperature element, the WFO is instructed to "use the calendar day values from the closest, meteorologically representative location." For NYC: if KNYC (Central Park) is down, the OKX office may substitute from NYC's other ASOS or even from a cooperative observer. The CLI product is supposed to mark these as "Estimated" — but the marking is in free text, not in a structured field. Your parser sees a normal `Maximum: 74` row and writes it to cache. Three months later you train a model, and 12 of those days are not actually KNYC observations.

**Why it happens:**
- The "Estimated" tag is in the CLI product's REMARKS section or as a parenthetical, not in the column data.
- Different WFOs format the disclaimer differently — there's no fixed grammar.
- The substitution is operationally invisible to downstream API consumers (NOWData shows the value as-is).

**How to avoid:**
- `_climate.py` parser MUST extract REMARKS lines verbatim into a `cli_remarks` field on the settlement row.
- Validator check on `schema.settlement.cli.v1`: if `cli_remarks` contains any of `(?i)(estimated|substituted|nearby|representative|backup|cooperative)` → set a `cli_data_quality` flag column to "ESTIMATED" and quarantine into a separate code path that the Validator surfaces to the caller.
- Schema must include `cli_data_quality` enum: `{"OFFICIAL", "ESTIMATED", "PRELIMINARY", "UNKNOWN"}`. Default OFFICIAL; downgrade based on REMARKS.
- Audit script in Phase B Day 11 contract test: parse 3 years of CLI for KNYC + KMDW + KMIA; report % of days flagged ESTIMATED. Should be small (≤1%) — if higher, the parser regex needs work.

**Warning signs:**
- Training set has 0% estimated flag rate → parser is silently consuming substituted data.
- Backtest does well on a small holdout but fails live; on inspection, the failing days had unusual remarks.
- Live API observed values diverge wildly from CLI value for the same date.

**Phase to address:** Phase B Day 7 (`cli` adapter) — schema includes the `cli_data_quality` field. Phase B Day 11 (contract test) validates the audit.

---

### Pitfall 7: AWC API breaking change September 2025 — `/cgi-bin/` paths gone

**Severity:** PARITY-BREAKING (live tests fail; lifted code may have stale URLs)
**Phase:** Phase A — `_vendor/_awc.py` lifted from v0.14.1 (which may have stale URLs)

**What goes wrong:**
`monorepo-v0.14.1` was published before Sep 2025. Its `_awc.py` may still hit `aviationweather.gov/cgi-bin/data/metar.php?ids=KSFO` style endpoints. Those returned 404 starting Sep 2025. The new URL is `/api/data/metar?ids=KSFO`. The response JSON schema also changed: some parameters were renamed, some fields are now nested differently. Lifted code that worked in v0.14.1's snapshot fixtures will fail on first live call.

**Why it happens:**
- The migration was announced but `cgi-bin` paths were maintained briefly in compat mode; they're now removed.
- Recorded fixtures in `monorepo-v0.14.1/tests/` pass because they replay the old responses — that's exactly what the lift preserves.
- Live tests would catch this, but CI excludes `@pytest.mark.live`.

**How to avoid:**
- Day 1 manual smoke: `curl -s "https://aviationweather.gov/api/data/metar?ids=KORD&format=json" | jq .` to validate the new endpoint shape.
- If `_vendor/_awc.py` has any `cgi-bin` literal: update the URL but NOTHING else. Mark it with a `# LIFT-FIX: AWC 2025-09 migration` comment so we know what diverged from the verbatim lift.
- Recorded-fixture refresh: re-record the AWC fixtures against the new endpoint as part of Phase A Day 2.
- Catalog adapter `awc.py` declares `_API_BASE = "https://aviationweather.gov/api/data"` as a module constant; never inline-construct URLs.
- Live smoke test in `@pytest.mark.live` block that calls the real endpoint on every release tag.

**Warning signs:**
- `httpx.HTTPStatusError: 404` on first live call.
- Recorded fixture parity passes but live mode fails.
- AWC JSON has keys you don't recognize (new schema fields like `metar_id`, `prior`).

**Phase to address:** Phase A Day 2 (refresh AWC fixtures). Phase B Day 6 (live smoke on `awc` adapter).

---

### Pitfall 8: IEM `M` missing-data convention is three-way ambiguous

**Severity:** SILENT-DATA-CORRUPTION (a "0" can be missing, a quality-rejected value, or a sensor zero)
**Phase:** Phase B — CATALOG-01 (`iem` adapter)

**What goes wrong:**
IEM ASOS data marks missing as the literal string `M`. Per IEM docs: `M` could be (1) genuinely never reported, (2) reported but rejected by QC, or (3) set to missing post-hoc. The METAR format doesn't distinguish. If `_iem.py` does `df.replace("M", np.nan)` and then `df["temp_f"].fillna(0)` anywhere downstream, you have silent zeros that look like cold-snap data. If the parser does `int(value)` on `M` it raises — but if it does `pd.to_numeric(value, errors="coerce")` it silently produces NaN.

**Why it happens:**
- The "M" value is documented as "missing" but the ambiguity is buried in the dataset doc page.
- Some columns in IEM responses (e.g., precipitation when no rain) return `0` not `M` — and a sensor stuck-at-zero produces the same `0`.
- Numeric parsers in pandas coerce string `M` to NaN by default; the data quality flag is lost.

**How to avoid:**
- In `_vendor/_iem.py`, when reading the response, preserve a separate `_missing_columns: list[str]` field per row that lists which columns were `M` in the raw response.
- Never convert `M` → 0. Convert to `pd.NA` (NOT `np.nan` — `pd.NA` survives nullable dtype roundtrips per pandas integer_na docs).
- Schema for `schema.observation.v1` requires `temp_f`, `dewpt_f`, etc. to be nullable float dtype (`Float64`, not `float64`) so `pd.NA` doesn't get coerced to NaN on parquet write.
- Validator rejects rows where `temp_f == 0.0` and `_raw_metar` doesn't actually contain a "00/00" or "M00" pattern — these are sensor failures masquerading as data.
- Property test: feed `M` and `0` synthetic rows; assert they're distinguishable through the full pipeline.

**Warning signs:**
- Histogram of temperatures has a suspicious spike at exactly `0.0`.
- Model trained on this data predicts "32°F" too often (a sentinel value for one of the precipitation-coded-as-zero patterns).
- `df["temp_f"].isna().sum()` shows 0 for a station that's supposed to have outages.

**Phase to address:** Phase B Day 6 (`iem` adapter wrap); Validator (CORE-02) check on Day 6.

---

### Pitfall 9: IEM MOS forecast deprecation in favor of NBM — model behavior drift

**Severity:** ANNOYING-BUT-SURVIVABLE in v0.1, but model-degrading for the user
**Phase:** Phase B — CATALOG-01 (IEM forecast leg)

**What goes wrong:**
NBM v5.0 went live 2026-05-05 (NOAA/MDL Service Change Notice 26-24). MOS is being kept alive for legacy consumers, but the forecast skill of the operational track moved to NBM. If `tradewinds` exposes only `iem.archive`/`iem.live` MOS, the user is training on a slowly-deprecating product. Worse: the IEM MOS archive may stop updating at some future date with little public warning; recorded fixtures keep tests green while the live source goes stale.

**Why it happens:**
- NOAA's deprecation cadence is slow but real. MOS has been "scheduled for sunset" for years.
- The transition to NBM is partial — GFS-MOS is still produced, but NAM-MOS may have already stopped or be next.
- IEM's MOS archive is a community service; if NOAA pulls upstream, IEM may not be able to backfill.

**How to avoid:**
- v0.1 ships IEM MOS as-is for parity (the user explicitly listed it in scope).
- In `catalog/iem.py`, add a `__deprecation_notice__` constant exposed at import: `"NWS MOS will be sunset in favor of NBM; tradewinds v0.2 will add iem.nbm source."`
- Schema includes a `forecast_model` enum: `{"GFS_MOS", "NAM_MOS", "LAV", "MET", "NBM"}` so callers can filter.
- Live smoke test: weekly cron pulls fresh IEM MOS for 3 stations and asserts non-empty. First empty-response triggers an issue.
- Plan v0.2 work to add NBM via the BIG-NBM endpoint or NOAA's blend.mdl.nws.noaa.gov text products.

**Warning signs:**
- IEM MOS endpoint returns 404 for a model that was working last week.
- Forecast skill degrades on dates ≥ 2026-05-05 vs. earlier dates (NBM v5.0 cutover).
- IEM forum posts about "MOS being phased out."

**Phase to address:** Phase B Day 6 (`iem` adapter with deprecation notice); Phase C (v0.2) for NBM addition.

---

### Pitfall 10: uv workspace does not pin inter-package version constraints in built wheels

**Severity:** PARITY-BREAKING for end-users (`pip install tradewinds==0.1.0` may resolve `tradewinds-weather==0.2.0`)
**Phase:** Phase B Day 13 — CI/CD + PKG-01

**What goes wrong:**
When you publish `tradewinds==0.1.0` and `tradewinds-weather==0.1.0` to PyPI from a uv workspace, the built wheel for `tradewinds` declares `Requires-Dist: tradewinds-weather` — with NO version constraint, because uv currently generates loose constraints from workspace path sources. (astral-sh/uv issue 9811, open as of 2026-05.) Six months later, when `tradewinds-weather==0.2.0` is published with a breaking change, anyone doing `pip install tradewinds==0.1.0` gets `tradewinds-weather==0.2.0` and the install is broken. Quickstart fails for the fresh installer test — but only AFTER v0.2 ships, so you don't catch it before announce.

**Why it happens:**
- `tool.uv.sources` directs uv-internal resolution to the workspace path, but doesn't translate to a version constraint in the published wheel's METADATA.
- uv issue 9811 is labeled "needs-design"; no automatic solution yet.
- Poetry's monorepo plugin did this; uv hasn't matched that capability.

**How to avoid:**
- Manual pin: every workspace member's `pyproject.toml` must declare inter-package deps with explicit version ranges:
  ```toml
  [project]
  dependencies = ["tradewinds-weather>=0.1.0,<0.2"]
  ```
  In addition to `[tool.uv.sources] tradewinds-weather = { workspace = true }`.
- Pre-publish check: `uv build --no-sources --package tradewinds` then inspect the wheel's `METADATA` file. Grep for `Requires-Dist: tradewinds-weather`. If no version constraint follows, fail the build.
- CI publish step: build all three packages, then a separate test step does `pip install dist/tradewinds-0.1.0-*.whl` into a fresh venv (no `--find-links`) and asserts import works.
- Publish order: weather + markets first (no inter-deps), then core (which depends on them). Or wait for `uv` to fix 9811.

**Warning signs:**
- `pip show tradewinds` shows `Requires: tradewinds-weather` with no version.
- A fresh `pip install tradewinds==0.1.0` 3 months from now installs a tradewinds-weather that breaks.
- QUICKSTART-01 timed install works today, fails next time someone tries.

**Phase to address:** Phase B Day 13 (CI/CD); manual pin in Phase B Day 9 when pyproject.toml's are first written.

---

### Pitfall 11: Hypothesis property tests on temporal invariants shrink slowly to long timestamp ranges

**Severity:** ANNOYING-BUT-SURVIVABLE (tests pass but are slow + may time out in CI)
**Phase:** Phase B — CORE-01 property tests for `TimePoint`, `KnowledgeView`, `LeakageDetector`

**What goes wrong:**
The intuition is to draw datetimes from `[1970-01-01, 2100-01-01]` for full generality. Hypothesis's datetime strategy is documented as having shrinking pathologies (issues 2273, 2662): timezone-aware datetimes shrink very slowly because the fold/DST logic is sensitive to timezone choice. A property test that finds a failure in 2087 takes 30+ minutes to shrink to the minimal counterexample. CI times out, the test is marked flaky, and someone disables it with `@pytest.mark.skip("flaky")`.

**Why it happens:**
- Hypothesis treats datetime ordering for shrinking as "tricky" per upstream docs.
- Imaginary datetimes (DST-skipped hours) are drawn by default; allow_imaginary=False adds an internal error path on some Hypothesis versions (issue 2662).
- `tzinfo` shrinking is "almost arbitrary" per Hypothesis source — there's no nice well-order on tz objects.

**How to avoid:**
- Constrain Hypothesis `datetimes()` strategy to a tight range relevant to prediction markets: `min_value=datetime(2018, 1, 1)` (oldest data anyone cares about), `max_value=datetime(2027, 12, 31)` (a year past current planning).
- Use `timezones=just(timezone.utc)` in `KnowledgeView` tests — `TimePoint` is canonically UTC, so generating arbitrary tzinfo is irrelevant for the invariant we're testing.
- For DST-sensitive tests (CLI parsing), use explicit fixtures (not Hypothesis): `@pytest.mark.parametrize("ts", DST_BOUNDARY_DATES)`.
- Set `@settings(deadline=2000, max_examples=200)` on every property test. CI failures with `deadline_exceeded` indicate a real perf regression, not flake.
- `pass_imaginary=False` only on the most recent Hypothesis version (≥6.99); test with the pinned version first.

**Warning signs:**
- A property test takes >60s to shrink.
- CI logs show `Falsifying example` with a datetime in 2099 — that's the shrinker stuck at a weird boundary.
- Different runs produce different "minimal" counterexamples (true shrinking instability).

**Phase to address:** Phase B Day 5 (when property tests first land).

---

### Pitfall 12: Recorded fixtures rot silently — they pass forever while live behavior diverges

**Severity:** SILENT-DATA-CORRUPTION (parity test passes against stale truth)
**Phase:** Phase A (fixture capture) + continuous

**What goes wrong:**
Phase A Day 0.5 captures 5 parity fixtures from `mostlyright==0.14.1` against live AWC/IEM/CLI responses on that day. The fixtures are committed. Three months later, the AWC schema changes (Pitfall 7), IEM `M` handling changes, or NBM cuts in. Recorded fixtures replay the old HTTP responses; tests pass green. But running `research()` live now diverges from `mostlyright==0.14.1` running live, because both diverged from the captured snapshot.

**Why it happens:**
- The fixtures replay the OLD response, not what the live API returns today.
- The parity test isn't asserting "tradewinds matches mostlyright==0.14.1 today" — it's asserting "tradewinds matches what mostlyright==0.14.1 produced on Day 0.5."
- No drift detection runs.

**How to avoid:**
- Two-tier fixture set:
  1. **Frozen parity fixtures** (`tests/fixtures/parity/`) — never re-recorded; the hard gate.
  2. **Drift detection fixtures** (`tests/fixtures/drift/`) — re-recorded weekly via a `pytest.mark.live` job; compared against the same 5 station/date pairs.
- Weekly cron in GitHub Actions: pull fresh AWC/IEM/CLI for the canonical 5 stations × 2 days; diff against last week's drift fixture; alert on any diff.
- Don't fix the failing drift alert by updating the fixture — investigate first. Drift is a signal.
- Document the rotation policy in `tests/README.md`: "Parity fixtures are append-only; drift fixtures are replaced weekly."

**Warning signs:**
- `git log tests/fixtures/parity/` shows no changes in 6 months but production trades disagree with `research()`.
- A user reports "today's high doesn't match what tradewinds returned."

**Phase to address:** Phase A Day 0.5 (initial capture); Phase B Day 13 (weekly drift cron in CI/CD).

---

### Pitfall 13: `mostly-light/strategies/kxhigh` uses `therminal-py` calls beyond the 5 named call sites

**Severity:** PARITY-BREAKING for the migration gate (ROADMAP.md Day 11)
**Phase:** Phase B Day 11 — MIGRATION-01

**What goes wrong:**
PROJECT.md says "5 call sites" from the kxhigh strategy. But Python imports are notoriously transitive: `therminal-py.client.pairs()` may internally call `therminal-py.utils.now_lst()` or `therminal-py.cache.get()` that the strategy never calls directly but relies on as a side effect. The 5 surface-level call sites pass migration; the implicit dependency on `therminal-py`'s clock skew handling silently produces different numbers. `kxhigh` backtest scores look identical → live PnL differs.

**Why it happens:**
- "Migrate 5 call sites" is a checklist item; the implicit dependencies are not.
- `therminal-py` may patch global state (warnings filters, `pandas.set_option`, env vars) that the strategy doesn't notice.
- Side-effect contracts (file paths, env var reads, package-level imports running code) are not in the 5 named calls.

**How to avoid:**
- Phase B Day 9 (before Day 11): audit `mostly-light` for every `import therminal` or `from therminal import` line. Grep for the strategy package recursively, not just the 5 named files.
- Audit for env-var reads in `therminal_py.__init__.py` or any module loaded at import.
- The MIGRATION-01 test is NOT just "the 5 call sites return the same values." It's: "run the full `kxhigh` strategy end-to-end in dry-run mode against tradewinds, compare output trades/positions to therminal-py baseline, byte-equivalent."
- Use `pip show therminal-py` for the version pin and import the same submodules in `tradewinds` to verify exports match.

**Warning signs:**
- All 5 call sites return identical values, but the `kxhigh` strategy's signal vector diverges in middle iterations.
- Replacing `therminal-py` with `tradewinds` shows a warning that wasn't there before (e.g., `FutureWarning` from pandas that therminal-py was filtering).
- Trade history diverges only on dates where the cache was stale (suggesting cache-key drift).

**Phase to address:** Phase B Day 9 audit; Day 11 full-strategy dry-run, not surface-level test.

---

### Pitfall 14: `filelock` on shared/networked filesystems (Dropbox, iCloud Drive, NFS) is unreliable

**Severity:** SILENT-DATA-CORRUPTION (cache race writes corrupt parquet)
**Phase:** Phase B — CACHE-01

**What goes wrong:**
PROJECT.md cache path: `$HOME/.tradewinds/cache/`. If a user's `$HOME` is on iCloud Drive (default for many macOS users), Dropbox sync folder, or NFS mount, `flock()` semantics break: different kernels do different random things for fcntl over NFS; iCloud Drive doesn't expose meaningful flock at all; multiple processes can "hold" the lock simultaneously. Two notebook kernels write to the same parquet partition → corrupted file → next read throws `pyarrow.lib.ArrowInvalid` or worse, silently truncated data.

**Why it happens:**
- macOS quietly relocates `~/Documents` to iCloud Drive on many configurations.
- The `py-filelock` package documents this: "use `SoftFileLock` on network filesystems, not the default kernel-enforced lock."
- The default `FileLock` falls back to ineffective behavior without raising on shared filesystems — the developer has no indication anything is wrong.

**How to avoid:**
- On import of `tradewinds.weather.cache`, resolve `$HOME/.tradewinds/` and check via `os.statvfs` (Linux) or `psutil` (macOS) whether it's on a local FS.
- If not local: warn loudly + redirect to a tmpdir or `~/Library/Application Support/tradewinds/cache/` on macOS (a non-synced location).
- Document the cache location override env var: `TRADEWINDS_CACHE_DIR`.
- Use `filelock.SoftFileLock` (mtime-based heartbeat) instead of `filelock.FileLock` when the cache dir resolves to a path containing `iCloud`, `Dropbox`, or matches `/mnt/`, `/nfs/`, `/Volumes/`.
- Atomic write pattern: `cache.py` writes to `{path}.tmp.{pid}.{epoch}` then `os.rename()` (atomic on POSIX, atomic on macOS HFS+/APFS for same-filesystem renames).
- Pre-commit hook test that mocks `Path.home()` to a tmpdir and runs concurrent writes via `ProcessPoolExecutor`.

**Warning signs:**
- Users on macOS report `pyarrow.lib.ArrowInvalid: Could not open Parquet input source: Invalid: Parquet magic bytes not found`.
- Cache files show truncated content (`du -h` shows partial size).
- Two processes claim to hold the lock simultaneously (`filelock` returns immediately for both).

**Phase to address:** Phase B Day 10 (cache updates).

---

### Pitfall 15: `pd.NA` vs `np.nan` vs `None` in nullable columns — silent dtype coercion

**Severity:** PARITY-BREAKING (parquet roundtrip + Validator both affected)
**Phase:** Phase A (parity output) + Phase B Day 5 (Schema, Validator)

**What goes wrong:**
v0.14.1's `client.pairs()` may return columns with `np.nan` for missing values. Phase B's CORE-02 Validator with `schema.observation.v1` might prefer `pd.NA` (the modern pandas missing indicator). Mixing the two in a single dataframe column coerces the column dtype to `object` — losing the numeric semantic. `df.equals(other)` returns False because `np.nan == np.nan` is False but `pd.NA == pd.NA` is `pd.NA` (not True). Parity test diff is mysterious.

**Why it happens:**
- pandas docs explicitly call out this trap (working_with_missing_data page): "mixing None, np.nan, and values in the same column can coerce to object."
- `Float64` (capital F, nullable) holds `pd.NA`. `float64` (lowercase, numpy-backed) holds `np.nan`. Both look identical in printed output.
- `pd.read_parquet` may default to one or the other depending on `dtype_backend` arg.

**How to avoid:**
- Decide one canonical missing-value representation per column type and pin in `schema.observation.v1`:
  - Numeric: `Float64` dtype with `pd.NA` for missing.
  - String: `string[pyarrow]` dtype with `pd.NA` for missing.
- For Mode 1 (v0.14.1 parity): inspect what `mostlyright==0.14.1` actually emits. If it's `float64`+`np.nan`, parity mode emits that; Mode 2 uses the canonical Float64+pd.NA.
- Validator function `_check_no_mixed_nulls(df)` walks each column, asserts only one of `{np.nan, pd.NA, None}` appears, and the column dtype is consistent.
- Roundtrip test: parquet write a dataframe with `Float64`+`pd.NA`, read back, assert dtype unchanged AND `df.isna().sum()` equal both ways.
- DO NOT use `df.fillna(value=0)` anywhere in the merge/output path; explicit null preservation is required.

**Warning signs:**
- `df.dtypes` shows mixed `float64` and `Float64`.
- `df.equals(other)` returns False but every value looks the same.
- `df.isna().sum()` differs from `(df == np.nan).sum()`.

**Phase to address:** Phase A Day 1 (capture Mode 1 representation); Phase B Day 5 (canonical for Mode 2).

---

### Pitfall 16: Kalshi settlement edge — preliminary higher than final, market determination delayed

**Severity:** SILENT-DATA-CORRUPTION (training labels are PRELIMINARY values but live trades settle on FINAL)
**Phase:** Phase B — CATALOG-03 (`cli`) + Validator + Markets contract spec

**What goes wrong:**
Kalshi help docs explicitly note: "Market determination may be delayed in the rare instances of (a) high temperature not consistent with 6-hr or 24-hr highs reported by METAR or (b) the final NWS Climate Report high temperature value is lower than a previous preliminary report." That means: most days settle on the prelim. A few days settle on the final, which can be LOWER than prelim. If `tradewinds`'s `research()` returns the latest CLI value (prelim → final, final wins because of `(-report_type_priority, source_received_at, ingestion_id)`), the historical training labels are correct. But there's a window — between prelim issuance and final issuance — where a researcher running `research()` would get prelim values and a live trade settles on the final. If `retrieved_at` was during that window, the label is the prelim; if your model uses that label, it's mismatched against what would have settled.

**Why it happens:**
- Prelim is published in the late-evening CLI (~3-5pm local).
- Final is published the next morning's CLI (~12:30am-5am local).
- A user running `research(to_date=today)` at 9pm local has prelims for today and finals for yesterday — but the prelim → final delta is silent.

**How to avoid:**
- `schema.settlement.cli.v1` MUST include `cli_data_quality` field (already required by Pitfall 6).
- `research()` Mode 2 includes a `settlement_finality` column: `"FINAL"`, `"PRELIMINARY"`, `"DELAYED"`.
- For dates within 48 hours of `retrieved_at`, mark settlement as `PRELIMINARY` regardless of CLI's stated report_type.
- Validator emits a warning (not error) when `to_date >= today - 1` for any settlement-using query. Tell the user: "Settlement for {date} is preliminary; will be revised."
- Mode 1 (v0.14.1 parity) preserves whatever `mostlyright==0.14.1` did. Mode 2 makes the issue explicit.
- For the `KalshiContractSpec` resolution: include `is_preliminary` boolean in returned rows.

**Warning signs:**
- Backtest computes `expected_pnl` higher than realized PnL by a small but consistent margin.
- Loss days disproportionately fall on dates where the user queried within 24h of the contract expiration.
- The model "learns" a feature that's actually the prelim-vs-final delta.

**Phase to address:** Phase B Day 7 (`cli` adapter) + Day 9 (Kalshi spec, including finality fields).

---

### Pitfall 17: Schema evolution on parquet append — adding a column to an existing cache partition

**Severity:** ANNOYING-BUT-SURVIVABLE (writes fail; recovery requires cache clear)
**Phase:** Phase B Day 10 — CACHE-01 updates, retrieved_at addition

**What goes wrong:**
v0.1.0-alpha1 (Day 4) ships cache with columns `[event_time, station, temp_f, ...]`. Day 10 adds `retrieved_at` to cache rows for the 30-day volatile window. Existing cache parquet files don't have the column. When `cache.append(new_rows)` writes the new schema into an existing partition, pyarrow raises `ArrowInvalid: Schemas don't match` (issue 37898). Users who installed alpha1 and cached data then upgraded to v0.1.0 see all cache calls fail until they manually `rm -rf ~/.tradewinds/cache/`.

**Why it happens:**
- Parquet schema evolution is limited: column additions usually work for reads (the missing column reads as null), but writes require schema-compatible files.
- `pyarrow.dataset.write_dataset(..., existing_data_behavior="overwrite_or_ignore")` has options, but the default behavior depends on writer version.
- `unify_schema()` doesn't work for some evolutions (issue 37898).

**How to avoid:**
- Cache layout includes a schema version in the path: `~/.tradewinds/cache/v1/observations/...`. Bumping the schema increments to `v2/`.
- On startup, `cache.py` checks `~/.tradewinds/cache/v1/SCHEMA_VERSION` file; if it doesn't match the package's expected version, log a warning and migrate (or just ignore the old version).
- New columns added as part of schema bumps are nullable; reads of older cache files that don't have the column return `pd.NA` for that column.
- Document in README: cache is per-version; upgrading clears old cache automatically.

**Warning signs:**
- v0.1.0-alpha1 → v0.1.0 upgrade breaks every test until cache is wiped.
- `pyarrow.lib.ArrowInvalid: Schemas don't match`.
- Cache files exist but `cache.read(...)` returns empty.

**Phase to address:** Phase B Day 10 (when `retrieved_at` is added to cache).

---

### Pitfall 18: 30-day volatile window detection — how do you actually know an archive observation was amended?

**Severity:** SILENT-DATA-CORRUPTION (cache returns stale value; live source has updated)
**Phase:** Phase B Day 10 — CACHE-01 (30-day exclusion)

**What goes wrong:**
ROADMAP says: "Archive data within the last 30 days stays direct-from-source." This implies a 30-day window where IEM/AWC archives can still receive amendments. But what's the *evidence* that an amendment happened? IEM doesn't expose an "amended_at" field per row. The archive endpoint just returns the current value; the original value is never preserved unless you stored it. If `tradewinds` caches an observation at Day 0, the volatile window check at Day 28 should detect that an amendment occurred between Day 0 and now — but the only way to detect that is to RE-FETCH the same observation, which defeats the cache.

**Why it happens:**
- IEM ASOS data: "the archive provides the as-is collection of historical observations." No revision tracking is exposed.
- NCEI metadata may have `data_provider_quality_flag` per record, but that's the QC flag, not amendment history.
- The "30-day window" rule is operational, not technical: it's a heuristic that within 30 days, the archive may still change.

**How to avoid:**
- The 30-day rule is enforced by CACHE BYPASS: any query whose `to_date >= today - 30` skips the cache and goes direct to source, every time. That's the rule, not "detect amendments."
- Cache rows have `retrieved_at` recorded; consumers can check `retrieved_at > to_date + 30 days` for the "fully settled" guarantee.
- For historical queries (`to_date < today - 30`), cache is authoritative — UNLESS the user explicitly passes `fresh=True` (note: this contradicts ROADMAP "No user-visible `fresh=` kwarg"; resolve by either allowing it as an env var override `TRADEWINDS_BYPASS_CACHE=1` for ops investigations, or documenting the trade-off).
- Drift detection (Pitfall 12): the weekly cron compares fresh fetches at Day 31 against the cache; any diff signals an undetected amendment. Logs the finding; doesn't auto-correct (the operator triages).

**Warning signs:**
- A historical research query 2 years later returns slightly different values than the same query a year ago.
- The drift detection cron at Day 31 finds amendments not reflected in cache.
- Users report "the May 2023 high was 73, but tradewinds says 72."

**Phase to address:** Phase B Day 10 (cache 30-day exclusion); ongoing for drift detection.

---

### Pitfall 19: GHCNh station ID drift — same station, different identifier over time

**Severity:** SILENT-DATA-CORRUPTION (historical query splices two stations as if one)
**Phase:** Phase B — CATALOG-04 (`ghcnh` adapter)

**What goes wrong:**
GHCNh tries to use the same GHCN identifier for stations common to GHCNd and GHCNh — but only "in general." Stations can have multiple IDs over their lifetime (legacy COOP ID, WBAN, ICAO, GHCN ID). The HOMR database tracks these — but a naive `ghcnh` adapter that maps "give me KORD historical hourly" to a single GHCN ID misses that the underlying physical station's ID changed in 1998 or 2010 (renumberings happen). Result: a 30-year query is actually two stations concatenated.

**Why it happens:**
- Station network mergers, instrument relocations within an airport, and digitization of older paper records all cause identifier changes.
- GHCNh integrates 100+ data sources; the harmonization is best-effort.
- The "same GHCN identifier" claim is "in general" — the exceptions are not surfaced.

**How to avoid:**
- For each Kalshi-supported station, hard-code a `station_id_history: list[tuple[id, valid_from, valid_to]]` mapping in `kalshi_settlement_stations.py`.
- The `ghcnh` adapter queries by `(id, time_range)` and looks up the correct ID for the queried period.
- Validator check: when joining observations across time, assert the station's `metadata_hash` is consistent. If GHCNh returns rows with inconsistent station metadata (lat/lon shift), flag and quarantine.
- For v0.1: limit `ghcnh` adapter to Kalshi settlement stations only (KNYC, KMDW, etc.); they're more likely to have stable IDs over the prediction-market era (post-2015).

**Warning signs:**
- A long historical query shows a discontinuity in the time series.
- `df.groupby("station").lat.nunique()` returns >1 for what should be one station.
- Temperature distribution shifts at a specific date for no meteorological reason.

**Phase to address:** Phase B Day 8 (`ghcnh` adapter).

---

### Pitfall 20: First-fetch concurrent users on the same partition — filelock serialization causes timeout cascades

**Severity:** ANNOYING-BUT-SURVIVABLE (slow not wrong)
**Phase:** Phase B Day 10 (cache) — already in TODOS.md (documentation)

**What goes wrong:**
TODOS.md mentions this is by-design. Adding the operational edge: when filelock is held by process A for a 5-minute first-fetch of a 5-year range, process B's `filelock.acquire()` blocks. If process B has its own timeout (httpx default is 5s; user-set 30s on the SDK), it can timeout WHILE WAITING ON THE LOCK, not on the network. The error returned is confusing: "Connection timeout" when the connection wasn't even attempted.

**Why it happens:**
- `filelock.acquire(timeout=None)` blocks forever; `filelock.acquire(timeout=N)` raises Timeout — but N often defaults to "until timeout".
- The httpx client timeout is separate from the cache lock timeout.

**How to avoid:**
- `cache.acquire_lock(station, month)` has its own explicit timeout (e.g., 10 minutes) DISTINCT from the httpx timeout.
- Raise a distinct exception `CacheLockTimeout` (subclass of `TradewindsError`) when the lock can't be acquired, with a useful message: "Another process is fetching {station}/{month}; this can take up to N minutes on first fetch. Re-run after that completes."
- Document in the existing TODOS.md item.

**Warning signs:**
- Users report `httpx.ConnectTimeout` errors that don't correlate with network conditions.
- A batch script with 4 processes hangs forever on the same station.

**Phase to address:** Phase B Day 10.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Lift `_vendor/_*.py` verbatim without re-testing | Day 1-4 speed; parity preservation | Stale URLs (Pitfall 7), stale `M`-handling (Pitfall 8), no doc-string updates | ALWAYS for parity; mark with `LIFT-FROZEN` decorator and never edit without a fixture re-record |
| `df.fillna(0)` to "clean up" missing data | Removes downstream NaN warnings | Silent data corruption (Pitfall 8, 15); zeros indistinguishable from sensor failures | NEVER. Always preserve nulls explicitly |
| `dtype_backend="pyarrow"` for pandas | Faster operations on string columns | Mixed `Float64`/`float64` in same pipeline (Pitfall 15); parity diffs | Only if every column in every output path is pyarrow-backed; pick one and pin |
| Re-record drift fixtures when they fail | Tests stay green | Silent erosion of parity guarantee (Pitfall 12) | NEVER without investigation; drift signal must trigger code change, not fixture update |
| Skip property tests with `@pytest.mark.skip("slow")` | CI passes | Temporal invariants regress (Pitfall 11) | Only with `@pytest.mark.slow` AND a nightly job that runs the slow tier |
| Use `--no-verify` to skip pre-commit hooks | Quick fix shipping | Quality bar erodes over commits | NEVER per CLAUDE.md |
| Cache `cli.archive` data with `retrieved_at` = NOW always | Simple write logic | Within-30-days cache rows look "settled" when they're not (Pitfall 18) | Never; `retrieved_at` is the fetch time, not the cache-write time |
| Map "NYC" → KLGA because "everyone knows LGA" | Easy to remember | All training labels wrong vs. settlement (Pitfall 1) | NEVER |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| IEM ASOS METAR archive | Treating `M` as 0 or NaN without preserving the missing-flag | Preserve raw string; convert to `pd.NA` in nullable float column; never `fillna(0)` |
| AWC METAR JSON | Using v0.14.1 monorepo's `/cgi-bin/` URLs that 404 since Sep 2025 | Update URLs to `/api/data/` only; mark with `LIFT-FIX` comment; refresh fixtures |
| NWS CLI text product | Parsing the body's local time string and ignoring DST/LST distinction | Use UTC from product header; only fall back to body local time with explicit tz mapping |
| NWS CLI product | Treating prelim and final as interchangeable | Track `report_type_priority` per row; expose `is_preliminary` to caller; surface delay window |
| GHCN-hourly | Querying by GHCN ID for a 30-year span without checking ID history | Use `(station_alias, valid_from, valid_to)` mapping per Kalshi station |
| Kalshi NHIGH/NLOW settlement | Mapping NYC→KLGA, Chicago→KORD because they're "the" airports | Hard-code KNYC (Central Park) and KMDW; never derive from aviation METAR popularity |
| pyarrow parquet write | Using defaults (no `version=`, no explicit timestamp unit) | Always set `version="2.6"`, explicit timestamp unit, explicit tz, explicit `coerce_timestamps` |
| pyarrow parquet read | Reading category columns without `read_dictionary=[...]` | Pass `read_dictionary=["station_id", "source", "report_type"]` |
| filelock on `$HOME` | Assuming `$HOME` is always local FS (macOS Documents folder is iCloud) | Detect cloud-sync folders; use `SoftFileLock` for non-local; allow `TRADEWINDS_CACHE_DIR` override |
| Hypothesis datetimes | `datetimes()` with `min_value=datetime.min` shrinking pathology | Constrain to `[2018-01-01, 2027-12-31]`; pin `timezones=just(UTC)` for KnowledgeView tests |
| uv workspace publish | Releasing without explicit version pins on inter-package deps | Manual `dependencies = ["tradewinds-weather>=0.1.0,<0.2"]` in each pyproject; verify METADATA before publish |
| Recorded fixtures | Treating fixtures as "the truth" forever after capture | Two-tier: frozen parity fixtures (immutable) + weekly drift fixtures (rotated with investigation) |
| therminal-py migration | Counting only the 5 named call sites without auditing transitive imports | `grep -r "import therminal\|from therminal"` across the strategy package; verify side-effect parity |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Cold-cache first fetch sequentially across 5+ years × 4 stations | Multi-hour `research()` calls; user thinks it's broken | Document in README (TODOS); chunk by month and parallelize across stations with backoff; surface progress | First non-trivial use; ~5 minutes per station-year typical |
| `pyarrow.parquet.read_table` for a partitioned dataset without column pruning | OOM on large date ranges | `read_table(..., columns=[...])`; always project the needed columns | When dataset grows beyond ~1GB in cache (~10 station-years) |
| Hypothesis property tests with `max_examples=1000` and slow datetime shrinking | CI times out (Pitfall 11) | `max_examples=100-200`; `deadline=2000`; tight datetime ranges | Phase B Day 12 coverage push |
| IEM "live" endpoint hit on every cache read for in-window dates | Rate-limited by IEM; banned IP | Honor the documented 18-36 hour delay; only re-fetch archive after that window | Heavy backtest user fetching 1000s of stations |
| Storing every row's `_raw_metar` string in cache parquet | 5-10x cache size; slow reads | Store only when explicitly requested via `include_raw=True`; default is parsed-only | First cache exceeds 10GB |
| Filelock-serialized concurrent writers on same partition | `httpx.ConnectTimeout` (actually lock timeout, Pitfall 20) | Distinct `CacheLockTimeout` exception; clear error message; document | When users run notebook + scheduled job concurrently |
| Re-validating every row in Validator for huge dataframes | 30-second validation pass on a 1M-row research call | Sample validation (random 10K rows); full validation only on `--strict` | Above 100K rows |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing API tokens in test fixtures | Public PyPI package leaks keys | None of the v0.1 sources require auth tokens (AWC, IEM, NWS CLI, GHCNh are public). Verify on every PR that no `Authorization:` header was added |
| Caching with overly-permissive umask (777) | Other users on shared system read cache | `cache.py` creates with `0o700` (user read/write/execute only) explicitly |
| Replaying user-provided station IDs into URL paths without validation | URL injection; IEM rejects but logs may include garbage | Validate station ID against ICAO regex `^K[A-Z0-9]{3}$` (CONUS) or known whitelist before forming URL |
| Logging full HTTP request bodies including future Kalshi API tokens (v0.2+) | Token leak in user logs | `_internal/http.py` redacts `Authorization` and `X-API-Key` headers before logging; test for this in a unit test |
| Trusting CLI product text without bounds check on parsed temperatures | A malformed CLI returning "9999" silently enters training data | `_bounds.py` (already lifted from v0.14.1) enforces -100 ≤ temp_f ≤ 150; Validator rejects out-of-bounds |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent fallback from `iem.live` to `awc.live` on transient failure | User trained on AWC, infers on IEM (source drift) — exactly the bug the project exists to prevent | NEVER fall back across source IDs without raising `SourceMismatchError`. Retry within the same source ID with backoff; if all retries fail, raise. (Mode 2 enforces this; Mode 1 keeps v0.14.1 fallback for parity but warns.) |
| `research()` returns silently empty DataFrame when no data is available | User thinks query succeeded with no results; actually a config error | Return empty but emit `warnings.warn("No data found for {station}/{date_range}; check station ID")`; consider raising `SourceUnavailableError` for empty live calls |
| Cache hit returns "fresh" data because in-process cache wasn't invalidated after the 30-day-volatile threshold passed | User runs a query on Day 0 (cached), Day 31 (should re-fetch), gets stale value | `cache.py` checks file mtime against `to_date + 30 days` rule on every read; doesn't trust in-process state alone |
| First-fetch slowness with no progress indication | User Ctrl-C's thinking it's hung (Pitfall 20 + TODOS performance note) | Print one-line progress per station-year: `"Fetching KNYC 2020 [1/30]..."`; document in README |
| `research()` raises a generic `Exception` instead of `TradewindsError` subclass | User can't catch the right exception programmatically | Every code path raises a `TradewindsError` subclass per CORE-04; no bare `Exception` or `ValueError` |
| Deprecation warning on Mode 1 fires on every call | Notebook output noise; users disable warnings entirely | Fire only ONCE per session (use `warnings.warn(..., stacklevel=2)` with a module-level `_warned = False` flag) |
| Settlement values returned as floats; user expects `Decimal` for currency-like precision | Float arithmetic errors in PnL calculation | Document that values are physical temperature (not currency); they're floats. If users want exactness, they round explicitly |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Parity test green:** Verify the 5 fixtures are diverse — not all the same station, not all the same date range. Include at least one DST-boundary date and one date with `M` missing data in observations.
- [ ] **Cache writes work:** Verify behavior on a path containing `iCloud`, `Dropbox`, or `/Volumes/` — not just on the developer's home laptop (Pitfall 14).
- [ ] **Property tests pass:** Verify `max_examples >= 100` per test (not the default 10 from older Hypothesis); verify `deadline` is set explicitly; verify datetime ranges are constrained (Pitfall 11).
- [ ] **Validator rejects mixed nulls:** Verify a synthetic df with both `np.nan` and `pd.NA` in the same column triggers `SchemaValidationError` (Pitfall 15).
- [ ] **Kalshi contract spec correct:** Verify `KalshiContractSpec("KXHIGHNY").settlement_station == "KNYC"`, not "KLGA" (Pitfall 1). Same for KMDW/KMIA/etc.
- [ ] **CLI parser handles DST:** Verify fixtures for 2024-03-10 (spring forward) and 2024-11-03 (fall back) parse to the correct LST summary_date (Pitfall 5).
- [ ] **AWC URLs updated:** Verify no `/cgi-bin/` in lifted `_awc.py`; live smoke test passes against `/api/data/metar` (Pitfall 7).
- [ ] **Missing-data flag preserved:** Verify a row from IEM with `M` for temperature is `pd.NA` in `Float64` column AND the original `M` is recorded in `_missing_columns` or `_raw_metar` (Pitfall 8).
- [ ] **CLI product remarks parsed:** Verify a CLI product with REMARKS containing "estimated" sets `cli_data_quality = "ESTIMATED"` (Pitfall 6).
- [ ] **Preliminary/final tracked:** Verify `research(to_date=today)` rows have `settlement_finality = "PRELIMINARY"`, while `to_date=today-7` has `"FINAL"` (Pitfall 16).
- [ ] **uv workspace pubpins:** Verify the built wheel's METADATA file has explicit `Requires-Dist: tradewinds-weather>=0.1.0,<0.2`, not bare `Requires-Dist: tradewinds-weather` (Pitfall 10).
- [ ] **Float precision exact:** Verify `np.allclose(df1.values, df2.values, rtol=0, atol=0)` passes (not just `df1.equals(df2)`) for parity fixtures (Pitfall 2).
- [ ] **Timezone preserved:** Verify `df["event_time"].dt.tz == ZoneInfo("UTC")` after cache roundtrip (Pitfall 3).
- [ ] **Categorical preserved:** Verify `df["station_id"].dtype == "category"` (or whichever is canonical) after cache roundtrip (Pitfall 4).
- [ ] **Drift detection runs:** Verify a weekly cron is set up in `.github/workflows/`; verify the test would actually flag a fixture-vs-live mismatch (Pitfall 12).
- [ ] **therminal-py migration audited:** Verify the `kxhigh` strategy has NO `import therminal_py.*` left; verify the full dry-run matches baseline, not just the 5 named call sites (Pitfall 13).
- [ ] **Source fallback raises:** Verify a forced AWC failure raises `SourceUnavailableError`, does NOT silently fall back to IEM (Mode 2; Pitfall in UX table).
- [ ] **Schema migration safe:** Verify upgrading from v0.1.0-alpha1 to v0.1.0 with existing cache produces a clear warning, not a crash (Pitfall 17).

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Parity test fails due to float precision (Pitfall 2) | LOW (1-2 hours) | Inspect dtype divergence; pin pyarrow/pandas; set `version="2.6"` on writer; refresh fixtures from clean source |
| Kalshi station mapping wrong (Pitfall 1) | MEDIUM (1 day + retraining) | Patch `KALSHI_SETTLEMENT_STATIONS` constant; users must rerun research; trained models must be re-evaluated against the corrected labels |
| AWC URL stale (Pitfall 7) | LOW (2 hours) | Update `_API_BASE` in `awc.py`; refresh recorded fixtures; bump patch version |
| CLI DST parsing wrong (Pitfall 5) | MEDIUM (1 day + audit historical) | Patch `_parse_product_timestamp`; refetch all historical CLI for affected dates; users notified to invalidate cache for affected dates |
| Mixed null types in column (Pitfall 15) | LOW (few hours) | Validator catches at runtime; fix the producer to use `pd.NA` consistently; never fix by altering the validator |
| Cache lock corruption on iCloud (Pitfall 14) | MEDIUM (clear cache + redirect path) | User clears `~/.tradewinds/cache/`; sets `TRADEWINDS_CACHE_DIR=$HOME/Library/Application Support/tradewinds/cache` |
| uv workspace inter-pkg version drift (Pitfall 10) | HIGH (PyPI yank + re-release) | Yank affected version; update pyproject pins; re-release; notify users via CHANGELOG to upgrade all three packages together |
| Estimated CLI data silently consumed (Pitfall 6) | MEDIUM (Validator update + re-audit) | Patch CLI parser regex; backfill `cli_data_quality` on cached rows; users rerun training |
| Fixture rot detected via drift (Pitfall 12) | LOW-MEDIUM (depends on source) | Triage the diff (real change vs. transient noise); update code (NOT the parity fixture); update drift fixture; communicate in release notes |
| Migration test fails on full dry-run despite 5 calls passing (Pitfall 13) | HIGH (potentially blocks v0.1 release) | Audit transitive deps; identify the side-effect parity gap; either implement the side effect in tradewinds or change kxhigh to not depend on it |
| GHCNh station ID drift detected (Pitfall 19) | MEDIUM (per-station fix) | Add affected station to `station_id_history` table; refetch affected periods; mark old cache rows invalid |
| Schema evolution breaks alpha1→0.1.0 (Pitfall 17) | LOW (users clear cache) | Document cache wipe in CHANGELOG; auto-migrate by deleting old `v1/` cache dir on startup with a warning |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| # | Pitfall | Prevention Phase | Verification |
|---|---------|------------------|--------------|
| 1 | Kalshi station ID guessed wrong | Phase B Day 9 (CATALOG-05) | Phase B Day 11 contract test asserts KXHIGHNY → KNYC, KXHIGHCHI → KMDW |
| 2 | Float32/64 precision through parquet | Phase A Day 1 (pinning) + Day 3 (parity) | `np.allclose(rtol=0, atol=0)` on parity fixtures |
| 3 | Timezone-aware/naive parquet coercion | Phase B Day 5 (CORE-01 TimePoint) | Property test for DST boundaries; assert `event_time.dt.tz == UTC` after roundtrip |
| 4 | Categorical dtype lost on parquet roundtrip | Phase A Day 1 (capture dtypes) + Day 3 (parity) | `df.dtypes.equals(expected_dtypes)` in parity test |
| 5 | CLI DST late-night issuance parsing | Phase B Day 7 (CATALOG-03 cli) | Fixtures for 2024-03-10, 2024-11-03, 2024-12-31 23:47 EST |
| 6 | NWS substitutes data from nearby station silently | Phase B Day 7 + Day 11 (Validator) | `cli_data_quality` enum populated; audit script reports >0% estimated flag rate |
| 7 | AWC API breaking change Sep 2025 | Phase A Day 2 (refresh fixtures) | Live smoke test on `/api/data/metar` endpoint |
| 8 | IEM `M` missing convention ambiguous | Phase B Day 6 (CATALOG-01 iem) | Property test feeds `M`, `0`, valid value; assert distinguishable downstream |
| 9 | IEM MOS deprecation in favor of NBM | Phase B Day 6 + planned Phase C | `__deprecation_notice__` constant; v0.2 issue tracks NBM addition |
| 10 | uv workspace inter-package version pinning | Phase B Day 9 (pyproject writes) + Day 13 (CI publish) | Pre-publish check inspects wheel METADATA for explicit version bounds |
| 11 | Hypothesis temporal shrinking pathology | Phase B Day 5 (property tests land) | All property tests have `max_examples=200`, `deadline=2000`, constrained datetime ranges |
| 12 | Recorded fixtures rot silently | Phase A Day 0.5 (capture) + Phase B Day 13 (drift cron) | Weekly cron runs; alerts on any diff |
| 13 | therminal-py implicit dependencies beyond 5 call sites | Phase B Day 9 (audit) + Day 11 (full dry-run) | Migration test runs full kxhigh strategy E2E, byte-equiv to baseline |
| 14 | filelock unreliable on iCloud/NFS | Phase B Day 10 (cache updates) | Detect cloud-sync; redirect or use SoftFileLock; test with mocked path |
| 15 | `pd.NA`/`np.nan`/`None` mixing in columns | Phase A Day 1 (capture Mode 1) + Phase B Day 5 (canonical Mode 2) | Validator `_check_no_mixed_nulls`; roundtrip test |
| 16 | Kalshi preliminary vs final settlement | Phase B Day 7 (cli adapter) + Day 9 (Kalshi spec) | `settlement_finality` field populated; query within 24h flags PRELIMINARY |
| 17 | Parquet schema evolution on append | Phase B Day 10 (retrieved_at addition) | Versioned cache path; auto-migrate older versions; CHANGELOG note |
| 18 | 30-day amendment detection | Phase B Day 10 (CACHE-01 30-day exclusion) | Cache bypass for `to_date >= today-30`; drift cron audits historical |
| 19 | GHCNh station ID drift over decades | Phase B Day 8 (CATALOG-04 ghcnh) | `station_id_history` table; metadata-hash check |
| 20 | filelock + httpx timeout cascade | Phase B Day 10 | Distinct `CacheLockTimeout`; clear error message; document |

---

## Sources

### Primary (HIGH confidence — official docs / authoritative)

- [Weather Markets | Kalshi Help Center](https://help.kalshi.com/markets/popular-markets/weather-markets) — Source-of-record for "NWS Daily Climate Report" as the only settlement source; explicitly notes the prelim/final delay condition
- [Kalshi NHIGH contract terms PDF](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/NHIGH.pdf) — Binary content, requires page-fetch
- [Kalshi NOWDATASNOW contract terms](https://kalshi-public-docs.s3.amazonaws.com/contract_terms/NOWDATASNOW.pdf)
- [KalshiEX LLC CFTC filing Feb 2026](https://www.cftc.gov/sites/default/files/filings/orgrules/26/02/rules02042638732.pdf)
- [NWS Missing Climate Data Estimation Procedures](https://www.nws.noaa.gov/im/datamis.htm) — Substitution from nearby station policy; HTTP 403 on direct fetch but referenced by multiple secondary
- [NWS Time Zone reference](https://www.weather.gov/tg/time) — UTC vs LST for meteorological reports
- [NWS National Weather Service Instruction 10-1003](https://www.weather.gov/media/directives/010_pdfs_archived/pd01010003c.pdf) — CLI product timing and content
- [NOAA Service Change Notice 26-24 NBM V5.0](https://www.weather.gov/media/notification/pdf_2026/scn26-24NBM_V5.0.pdf) — NBM v5.0 cutover 2026-05-05
- [IEM Datasets: metar](https://mesonet.agron.iastate.edu/info/datasets/metar.html) — IEM ingestion and processing
- [IEM Note about ASOS Precipitation Data](https://mesonet.agron.iastate.edu/ASOS/precipnote.phtml) — Data quality caveats
- [AWC Data API documentation](https://aviationweather.gov/data/api/) — Sep 2025 schema migration; `/cgi-bin/` deprecation
- [AWC Change Log](https://aviationweather.gov/help/changelog/) — API redevelopment history
- [GHCN-Hourly documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf)
- [GHCNh dataset metadata](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC01688)
- [NCEI Climate Data Online](https://www.ncei.noaa.gov/cdo-web/) — Underlying daily CLI data
- [astral-sh/uv issue 9811 — workspace member version pinning](https://github.com/astral-sh/uv/issues/9811) — Open issue; uv doesn't pin inter-package deps
- [pyarrow.parquet.write_table reference](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html) — `version`, `coerce_timestamps`, `allow_truncated_timestamps` params
- [pyarrow Parquet documentation](https://arrow.apache.org/docs/python/parquet.html) — Schema metadata behavior
- [pandas nullable integer data type](https://pandas.pydata.org/pandas-docs/stable/user_guide/integer_na.html) — `pd.NA` semantics
- [pandas Working with missing data](https://pandas.pydata.org/docs/user_guide/missing_data.html) — Mixed null type coercion warning
- [Hypothesis datetime strategies source](https://hypothesis.readthedocs.io/en/latest/_modules/hypothesis/strategies/_internal/datetime.html)
- [py-filelock documentation](https://py-filelock.readthedocs.io/en/latest/) — SoftFileLock for network filesystems

### Secondary (MEDIUM confidence — verified GitHub issues / community discussion)

- [Apache Arrow issue 37355 — read_table with filters broken for tz-aware timestamps since 13.0.0](https://github.com/apache/arrow/issues/37355)
- [Apache Arrow issue 38171 — pyarrow 13.0.0 silently converted datetime64[ns] to [us] on read](https://github.com/apache/arrow/issues/38171)
- [Apache Arrow issue 37898 — unify_schema fails during schema evolution](https://github.com/apache/arrow/issues/37898)
- [pandas issue 26616 — categorical doesn't survive parquet roundtrip](https://github.com/pandas-dev/pandas/issues/26616)
- [pandas issue 60491 — parquet roundtrip fails with numerical categorical dtype](https://github.com/pandas-dev/pandas/issues/60491)
- [Hypothesis issue 2273 — folds and imaginary datetimes shrinking](https://github.com/HypothesisWorks/hypothesis/issues/2273)
- [Hypothesis issue 2662 — allow_imaginary=False internal error](https://github.com/HypothesisWorks/hypothesis/issues/2662)
- [tox-dev/tox issue 1115 — filelock with NFS fails](https://github.com/tox-dev/tox/issues/1115)
- [weather-gov/api discussion 751 — observations delayed 1+ hours](https://github.com/weather-gov/api/discussions/751) — Confirms 8-30 min publication delay for METAR
- [apenwarr / chris.improbable.org — Everything you never wanted to know about file locking](https://apenwarr.ca/log/20101213) — flock over NFS, macOS SMB
- [Lychee weather markets analysis](https://lycheedata.com/guides/kalshi-weather-prediction-markets-analysis) — Kalshi station-by-station mapping (Chicago = Midway, NYC = Central Park)
- [bettingonweather.com weather betting guide](https://www.bettingonweather.com/pages/temperature.php)

### Tertiary (LOW confidence — context only, not load-bearing)

- [Aviation Routine Weather Report (METAR) overview](https://meteocentre.com/doc/metar.html)
- [MCP Cheat Sheet 2026](https://www.webfuse.com/mcp-cheat-sheet) — General MCP context, not load-bearing for v0.1
- [Building MCP servers in Python primer 2026](https://dev.to/tufailkhan457/building-mcp-servers-in-python-a-production-primer-for-2026-4kh2)

---

*Pitfalls research for: tradewinds — local-first prediction-market weather contract SDK*
*Researched: 2026-05-21*
*Note: This research deliberately does NOT re-warn about temporal leakage or source drift — those are the project's foundational WHY, encoded in CORE-01/02 and `policies_climate.py`. The 20 pitfalls here are the second-order subtleties that bite once the foundations are in place.*
