# Changelog

All notable changes to `mostlyright`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(next changes land here)

## [1.1.1] — 2026-05-27

Patch release. Closes plan 18-09 (parity fixture re-capture), plan 18-11c Task 2 (TS parity fixture re-export), and refreshes registry-visible metadata. Runtime SDK APIs and source behavior are unchanged.

### Changed
- **README:** add PyPI/npm monthly download badges, keep the public-data positioning beyond weather-only, and surface package-level download badges for stable Python and TypeScript packages.
- **PyPI metadata:** add Homepage, Documentation, Repository, Issues, and Changelog URLs to all three Python distributions; broaden the core `mostlyrightmd` package description beyond weather-only.
- **npm metadata:** add homepage, repository, and issue-tracker fields to all four published TypeScript packages; broaden the `@mostlyrightmd/core` description beyond weather-only.
- **Docs:** refresh the Sphinx landing description to position the SDK as public-data prediction-market research, not only weather settlement research.

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
