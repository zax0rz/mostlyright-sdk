# Changelog

All notable changes to `mostlyright`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] — 2026-05-27 — Phase 21: TypeScript SDK Parity Completion

Closes the 11 audit-identified deltas between the Python and TypeScript SDKs from the 2026-05-27 cross-SDK audit. The TS SDK is now surface-equivalent to Python across `research()` kwargs, the typed-exception hierarchy, the cache versioning invariant, the `obs()` ingest-planner port, the `dailyExtremes()` wrapper, the markets trades shape, the `forecastNwp()` stub messaging, the codegen description propagation, the `preprocessing` namespace, and the `climateGaps()` structured error.

### Added
- **`DataAvailabilityError` typed exception in BOTH SDKs** (closes [Issue #26](https://github.com/mostlyrightmd/mostlyright-sdk/issues/26)). Shared 6-value reason enum (`model_unavailable | out_of_window | cache_miss | source_404 | source_5xx | rate_limited`) lets consumers branch on `e.reason` instead of string-matching the error message. Subclasses `TradewindsError` — existing `except TradewindsError` handlers continue to work. Three Python and four TS raise sites migrated; `SourceUnavailableError` remains in place for back-compat at other call sites.
- **`research()` composable kwargs surface — both SDKs** (TSPARITY-01). The TS `research()` accepts the same 9 kwargs as Python: `include_forecast`, `forecast_model`, `forecast_models`, `qc`, `tz_override`, `sources`, `source`, `backend`, `return_type`. Per D-03, `backend="polars"` raises `DataAvailabilityError(reason="model_unavailable")` in TS (no Polars in browser/Node); `return_type="wrapper"` is accepted as no-op. Both SDKs now reject mutually-exclusive misuse (`sources`+`source`, `forecast_model`+`forecast_models`, forecast model without `include_forecast=True`) as `TypeError` before any network fetch. The TS validator treats `null` and `undefined` uniformly as absent so JSON `None ↔ null ↔ undefined` round-trip matches Python `is not None` semantics.
- **TS `obs(station, from, to, opts?)`** (TSPARITY-04) — port of Python `tw.weather.obs()` Phase 7 ingest-planner. Strategy dispatch: `auto` (window-size heuristic), `exact_window` (date-bounded fetch — small calls pull small payloads), `warm_cache` (year-padded fetch for overlapping callers), `hosted` (raises `DataAvailabilityError`). `source="ghcnh"` raises `DataAvailabilityError` (TS GHCNh fetcher port deferred) rather than silently returning `[]`.
- **TS `dailyExtremes(station, from, to, opts?)`** (TSPARITY-05) — fetch+rollup wrapper matching Python `mostlyright.international.daily_extremes()`. Day-bucketing uses the station's IANA local tz from the STATIONS registry; pre-rollup fetch widens by ±1 UTC day so tz-edge observations are captured; post-rollup output clipped to caller's `[fromDate, toDate]` by station-local date. US ASOS stations get integer-°F precision (Phase 18 invariant); other stations get 0.1-precision values.
- **TS `versionedCacheStore` adapter** (TSPARITY-03) — wraps any `CacheStore` so reads with mismatched/missing `_cache_schema_version` return `null` (cache miss → re-fetch). Matches Python's Phase 18 18-08 parquet kv_metadata version stamp (`"v2-phase18-integer-f"`). Wired into BOTH `defaultCacheStore()` entries (Node + browser). Pre-bump cached values silently re-fetch on next call.
- **TS `mostlyright.preprocessing` namespace** (TSPARITY-10) — lowercase namespace alias matching Python's `mostlyright.preprocessing`. The PascalCase `Preprocessing` alias is deprecated but kept for back-compat; removal target v2.
- **TS validator schema descriptions via codegen** (TSPARITY-08) — `ColumnSpec.notes` → JSON Schema `description` → TS interface TSDoc `/** ... */` comments. Behavior was already shipped via `json-schema-to-typescript`; Phase 21 added a regression test (with `ts.transpileModule()` parse check) to guard against future codegen-pipeline regressions.
- **TS parity gate scaffold** (TSPARITY-02) — `packages-ts/meta/tests/parity/README.md` documents the 5-fixture row-equivalence assertion shape. Operator-triggered msw recording capture is the remaining gate-activation step.
- **Markets trades shape parity tests** (TSPARITY-06) — three potential divergences from the 21-06 plan locked in via `packages-ts/markets/tests/parity/trades-shape.parity.test.ts`: Kalshi candle bucket label, Polymarket pagination default, and equal-timestamp trade-ID tiebreaker (assertion: both SDKs preserve HTTP order — no in-SDK sort).
- **TS `forecastNwp()` improved stub messaging** (TSPARITY-07) — raises `DataAvailabilityError(reason="model_unavailable")` with a hint pointing operators at `iemMosForecasts()` workaround for stations with MOS coverage. New banner in `docs/forecasts.md`.
- **TS `climateGaps()` structured error** (TSPARITY-11) — raises `ClimateGapsNotImplementedError` (subclass of `DataAvailabilityError`) with a hint explaining the server-only architectural constraint. New `docs/climate-gaps.md` page.

### Changed
- **`research()` validation now fires BEFORE backend dispatch + network fetch** on both SDKs. A typo in kwargs no longer hits live APIs / mutates the cache before raising.
- **`SourceUnavailableError` migration sites** — three Python raise sites moved to `DataAvailabilityError(reason="model_unavailable")`: `obs(strategy="hosted")` (was `NotImplementedError`), `catalog.get_adapter(unknown)` (was `SourceUnavailableError`), `forecasts.forecast_nwp()` ImportError fallback (was `SourceUnavailableError`).
- **`obs(strategy="exact_window")` now issues a date-bounded IEM request** instead of pulling whole calendar years. A 1-day call pulls ~1 day of bytes (matching Python's Phase 7 ingest-planner semantics).
- **README + package metadata:** SEO copy sweep across top-level README, every per-package README, every `pyproject.toml`/`package.json` `description`, and (newly) `keywords` arrays on the npm packages. **Repositions the SDK as a universal public-data interface** — weather + prediction-markets are today's adapters; SEC filings, Federal Reserve series, court filings, FDA approvals, and equities structured data are named in the roadmap.
- **README package tables:** added `equities`, `courts`, and `fda` to the planned-adapters list on both the Python and TypeScript sides so the roadmap is legible at a glance.
- **GitHub repo:** description repositioned as a public-data SDK with weather + prediction-markets as launch adapters and a named adapter roadmap (EDGAR, FRED, court filings, FDA, equities). Discovery topics expanded to include `public-data`, `financial-data`, `sec-edgar`, and `fred`.

### Fixed
- **TS cache returned raw concrete store** — `defaultCacheStore()` in both Node (`default.ts`) and browser (`index.browser.ts`) entries now wraps the inner store in `versionedCacheStore(CACHE_SCHEMA_VERSION)` so pre-Phase-18 ASOS `0.06°F`-precision cache rows silently miss instead of being served stale. Iter-1/iter-2 review fix.
- **TS `dailyExtremes()` tz-edge silent row loss** — pre-fix the filter compared UTC date prefix against station-local date strings asymmetrically, dropping local-day observations that fell on adjacent UTC days. Iter-2 fix widens pre-rollup UTC fetch by ±1 day; clip post-rollup by station-local `localDate` matching Python parity.
- **TS `obs(source="ghcnh"|"cli")` silent empty rows** — pre-fix the type allowed those values but `fetchByStrategy` had no branch, so the call silently returned `[]`. Iter-1 fix: `"cli"` removed (not a valid Python source filter); `"ghcnh"` raises `DataAvailabilityError` upfront.
- **README:** switch PyPI download badges from Pepy/Shields to Badgen with PyPIStats detail links because Pepy has not indexed the `mostlyrightmd*` projects and Shields can surface upstream rate limits for fresh packages.

## [1.1.3] — 2026-05-27

Metadata-only republish. No runtime API or source-code behavior changes.

### Changed
- **PyPI + npm:** republish the already-merged registry metadata so latest package artifacts include website, docs, repository, issue-tracker, and changelog links.
- **PyPI + npm:** keep the broadened core descriptions that position the SDK as prediction-market research over public data, not only weather research.

## [1.1.2] — 2026-05-27

Patch release. Closes plan 18-09 (parity fixture re-capture), plan 18-11c Task 2 (TS parity fixture re-export), and refreshes registry-visible metadata. Runtime SDK APIs and source behavior are unchanged.

### Changed
- **README:** add PyPI/npm monthly download badges, keep the public-data positioning beyond weather-only, and surface package-level download badges for stable Python and TypeScript packages.
- **PyPI metadata:** add Homepage, Documentation, Repository, Issues, and Changelog URLs to all three Python distributions; broaden the core `mostlyrightmd` package description beyond weather-only.
- **npm metadata:** add homepage, repository, and issue-tracker fields to all four published TypeScript packages; broaden the `@mostlyrightmd/core` description beyond weather-only.
- **Docs:** refresh the Sphinx landing description to position the SDK as public-data prediction-market research, not only weather settlement research.

(The v1.1.1 number was burned by a concurrent registry-metadata refresh published from a separate branch. This v1.1.2 release ships the parity work originally targeted for v1.1.1.)

### Notes
- **Parity fixture re-capture (plan 18-09):** All 5 cases re-captured against post-Phase-18 `research()` via live network. Outcome: all 5 parquet bytes IDENTICAL to the pre-Phase-18 v0.14.1 baseline. The chosen cases (Jan 2025 → Nov 2025) fall outside AWC's 168h archive window, so they source from IEM/GHCNh — whose `temp_f` paths Phase 18 does NOT change. Future parity cases that exercise the AWC live window WILL surface the integer-°F shift; this release confirms the existing 5 cases remain valid baselines.
- **TS parity fixture re-export (plan 18-11c Task 2):** Re-ran `tests/fixtures/parity/export_for_ts.py` against the new parquets; produced byte-identical TS JSONs since the source parquets didn't shift.
- **Only artifact change:** `tests/fixtures/parity/expected_dtypes.json` column ordering — schema-ordered now (`date, station, cli_*, obs_*, fcst_*, market_close_utc`) instead of alphabetical. Test reads as dict — equality assertion preserved.
- **Parity HARD GATE remains GREEN.** `uv run pytest tests/test_parity.py -m live -v` → 5 PASSED in ~58s.
- **No behavior change.** Drop-in patch for any 1.1.0 caller.

### Audit trail
- See `.planning/phases/18-precision-fix-asos-integer-fahrenheit/18-09-PARITY-DELTA.md` for per-case shasums + why-no-shift explanation.

## [1.1.0] — 2026-05-27

Phase 18 release. Recovers native integer-°F precision for U.S. ASOS stations and fixes the `temp_f` false-precision bug surfaced in issue [#16](https://github.com/mostlyrightmd/mostlyright-sdk/issues/16). ASOS sensors observe in integer °F; the Tgroup in METAR remarks (`T########`) is a downstream encoding of the whole-°F internal value, not an independent precision tier. Pre-Phase-18 code back-converted Tgroup tenths-°C → °F via `celsius_to_fahrenheit()`, producing artifacts like `80.06°F` where the native reading was `80°F`. After this release, `temp_f` is integer-valued for ASOS rows recovered from Tgroup; non-Tgroup (international) stations keep the legacy float path.

### Added
- **PyPI + npm:** shared `parse_tgroup` / `parseTgroup` helper at `_internal/tgroup.py` / `_internal/tgroup.ts` — single source of truth for ASOS Tgroup parsing across AWC + IEM parsers.
- **PyPI + npm:** AWC integer-°F recovery — when raw METAR contains a Tgroup, `temp_f` / `dewpoint_f` are emitted as the recovered integer °F (e.g. `T02670122` → `temp_f=80.0`, NOT `80.06`).
- **PyPI + npm:** IEM Tgroup override of `temp_c` / `dewpoint_c` — when raw METAR contains a Tgroup, override the back-derived tenths with the source-truth Tgroup tenths. Critical: `temp_f` stays as `raw_tmpf` (NOT derived from `temp_c`); the two fields are different coded views of the same integer-°F sensor reading.
- **PyPI:** parquet observation cache embeds `_cache_schema_version = "v2-phase18-integer-f"` in file metadata + auto-invalidate on read mismatch. Existing pre-Phase-18 user caches silently re-fetch on next call. (`packages/weather/src/mostlyright/weather/cache.py`)
- **PyPI:** new property test (hypothesis) covering every integer °F in [-50, 140] round-trip through Tgroup tenths-°C; new 12-station AWC↔IEM cross-source consistency test.
- **PyPI:** new live anti-regression test at `packages/weather/tests/live/test_12_station_asos_integer_f.py` covering KLGA / KJFK / KEWR / KBOS / KORD / KDFW / KLAX / KMIA / KDEN / KSEA / KATL / KPHX (gated behind `-m live`; run pre-publish).
- **npm:** 5 new TypeScript test files (25 new tests + 12 skipped live) covering the same invariants as the Python suite — Tgroup helper unit tests, AWC integer-°F recovery, IEM Tgroup-override + consistency, exhaustive 191-value round-trip, 12-station live anti-regression.
- **npm:** `internationalDailyExtremes` Phase 18 lattice-rationale comment documenting how callers should pick `precision=1` for US-ASOS-lattice data vs `precision=0` for international.

### Changed
- **PyPI:** schema description language updated in `observation.json` / `daily_extreme.json` / `synoptic_extremes.json` — "0.1°C precision for US stations" was overstated; the tenths-°C is a Tgroup-encoded display precision, not independent source resolution.
- **PyPI:** `_ghcnh.py` carries a Phase 18 boundary-marker comment above the `celsius_to_fahrenheit(temp_c)` path documenting the deferral pending NCEI native-units documentation.
- **PyPI:** `mostlyright.international.daily_extremes` precision-rationale comment documents how US-ASOS-lattice inputs interact with the `precision = 1 if is_us else 0` branch.
- **PyPI:** `test_international.py` synthetic non-lattice temperatures replaced with realistic integer-°F-lattice values (`[10.0, 11.1, 12.2, 9.4]` from `[50, 52, 54, 49]°F`); a separate dedicated HALF_UP-mechanics test preserves the rounding-semantics coverage.
- **Docs:** `docs/live-streaming.md` alert example casts `temp_f` via `int()` (Python) / `Math.round()` (TS) so the rendered example never surfaces back-conversion artifacts. New "Note on `temp_f` precision (Phase 18)" section.

### Notes
- **Parity fixtures NOT re-captured** in this release. Plan 18-09 requires live network calls + operator-approval checkpoint and is deferred. The `tests/test_parity.py` HARD GATE still compares against the pre-Phase-18 baseline; users who rely on byte-equivalent parity vs `mostlyright==0.14.1` should pin to 1.0.x until 18-09 ships.
- **TS cache schema-version field** deferred. The TS cache is a generic key/value abstraction (Memory/Fs/IndexedDB) used for many caller value shapes; adding a version field across all `CacheEntry` consumers requires a separate refactor. TS callers that hit a pre-Phase-18 IndexedDB / FsStore cache may see stale `tempF=80.06` values until they invalidate manually.
- **Existing user Python caches auto-invalidate** on next `research()` call via the new `_cache_schema_version` mechanism — one round of slow first-read, no manual user action required.

### Review
- Two-iteration two-reviewer panel per `REVIEW-DISCIPLINE.md`. Iter-1: Python Architect PASS; codex `high` + TS Architect REVISE (both independently surfaced the same CRITICAL — IEM Tgroup-override missing the tmpf-validity gate from Python `_iem.py:184-188`). Iter-2: all three PASS after the gate was restored and 3 regression tests added.

## [1.0.1] — 2026-05-27

Hotfix release. Every live IEM MOS forecast fetch (NBE / GFS / LAV / MET / ECM) via either SDK has been broken end-to-end since the fetcher shipped — the IEM `/api/1/mos.json` endpoint validates the `model` query param against an uppercase-only regex and rejects lowercase values with HTTP 422. Both Python and TypeScript SDKs sent lowercase. This release fixes both sides in lockstep.

### Fixed
- **PyPI:** `mostlyright.weather._fetchers._iem_mos.fetch_iem_mos` now sends the `model` query param uppercased (e.g. `"NBE"`, not `"nbe"`) to match IEM's regex `^(AVN|GFS|ETA|NAM|NBS|NBE|ECM|LAV|MEX)$`. Closes [#17](https://github.com/mostlyrightmd/mostlyright-sdk/issues/17).
- **npm:** `@mostlyrightmd/weather` `iemMosForecasts(...)` applies the same uppercase fix to the TS fetcher. Same root cause; same one-character fix on both sides.

### Notes
- No API changes. `pip install mostlyrightmd==1.0.1` and `npm install @mostlyrightmd/weather@1.0.1` are drop-in patches for any caller already on 1.0.0.
- The regression was invisible to the unit suites because both used opaque HTTP mocks (`MagicMock` / `vi.fn`) that never inspected the actual query string. The new regression tests use `httpx.MockTransport` (Python) and a recording `fetchFn` (TS) to assert against the wire-level URL.

## [1.0.0] — 2026-05-26

First stable release. Promotes the 0.1.x line to SemVer-stable: the public API is committed to backward compatibility within the 1.x major.

### Added
- Code of conduct (Contributor Covenant 2.1) and SECURITY.md disclosure policy
- Status badges in the root README (PyPI version, npm version, license, docs)

### Changed
- Root README rewritten as user-facing copy. Positions the SDK as the public-data SDK for quants and AI agents, with weather + prediction-markets data shipping today and SEC filings (EDGAR) + Federal Reserve economic data (FRED) on the roadmap.
- Cross-package pin bound from `>=0.1.0,<0.2` to `>=1.0.0,<2.0` on all 3 PyPI distros. Lockstep contract is now anchored to the 1.x major line.
- No source-code or API changes vs. 0.1.4. `pip install mostlyrightmd==1.0.0` and `pip install mostlyrightmd==0.1.4` produce identical runtime behavior.

## [0.1.4] — 2026-05-26

Coordinated release on PyPI + npm: refreshes registry-visible copy and graduates the TypeScript SDK from `0.1.0-rc.*` to its `0.1.0` final.

### Changed
- **PyPI:** `mostlyrightmd`, `mostlyrightmd-weather`, `mostlyrightmd-markets` bumped `0.1.3 → 0.1.4`. No source-code or API changes. Per-package descriptions and READMEs cleaned for public consumption.
- **npm:** `@mostlyrightmd/core`, `@mostlyrightmd/weather`, `@mostlyrightmd/markets`, and the unscoped `mostlyright` meta-package shipped `0.1.0` (first non-rc release). All four moved from the `@next` dist-tag to `latest`.
- CHANGELOG header corrected.

## [0.1.0] — [0.1.3] — 2026-05-26

Initial production releases on PyPI. Versions `0.1.0` through `0.1.3` shipped on the same day during a staggered first-publish sequence: each release iterated on trusted-publisher registration for one PyPI package at a time, with the prior versions re-publishing alongside.

### Live on PyPI after [0.1.3]
- `mostlyrightmd` — versions `[0.1.0, 0.1.1, 0.1.2, 0.1.3]`
- `mostlyrightmd-weather` — versions `[0.1.2, 0.1.3]` (versions 0.1.0 and 0.1.1 were not published due to a publisher-registration typo at the time; the gap is intentional and harmless because the package-extra resolves transitively to the newest available version)
- `mostlyrightmd-markets` — version `[0.1.3]` (first available version on PyPI; the 0.1.0–0.1.2 gap mirrors the weather story above)

### Added
- `mostlyright.research(station, from_date, to_date)` — the canonical observation × climate join, byte-equivalent to `mostlyright==0.14.1`'s `client.pairs()` on the captured parity fixtures
- `mostlyright.weather` — direct fetchers for AWC, IEM ASOS, IEM CLI, GHCNh, NWS CLI
- `mostlyright.markets.catalog.kalshi_nhigh` / `kalshi_nlow` — Kalshi NHIGH/NLOW contract resolvers
- `mostlyright.markets.polymarket` — Polymarket discovery + settlement helpers
- `mostlyright.core` — schemas, validators, temporal-safety primitives (`KnowledgeView`, `LeakageDetector`), source-identity invariants (`SourceMismatchError`)
- Local parquet cache at `~/.mostlyright/cache/` (Python) — deterministic, file-locked, year-aligned
- Three-package PyPI layout: `mostlyrightmd` (core) + `mostlyrightmd-weather` + `mostlyrightmd-markets`

### Renamed (from earlier scaffold)
- PyPI distribution names migrated from `mostlyright*` to `mostlyrightmd*`. The Python import path remains `import mostlyright`. The PyPI install name move avoids version-shadowing the legacy `mostlyright==0.14.1` package.
- npm scope migrated from `@mostlyright/*` to `@mostlyrightmd/*`. The unscoped `mostlyright` meta-package is unchanged.
- Cache directory renamed from `~/.tradewinds/cache/` to `~/.mostlyright/cache/`. Environment variable renamed from `TRADEWINDS_CACHE_DIR` to `MOSTLYRIGHT_CACHE_DIR`. Back-compat shim accepts both names during the 0.1.x line; the legacy name will be removed at v0.3.

## [0.0.1] — Initial scaffold

Workspace + three-package layout. SDK foundations ported from the predecessor codebase (`tradewinds*`).
