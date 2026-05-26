# Changelog

All notable changes to `mostlyright`. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(next changes land here)

## [1.0.0] — TBD

First stable release. Promotes the 0.1.x line to SemVer-stable: the public API is committed to backward compatibility within the 1.x major.

### Added
- Code of conduct (Contributor Covenant 2.1) and SECURITY.md disclosure policy
- Status badges in the root README (PyPI version, npm version, license, docs)

### Changed
- Root README rewritten as user-facing copy. Positions the SDK as the public-data SDK for quants and AI agents, with weather + prediction-markets data shipping today and SEC filings (EDGAR) + Federal Reserve economic data (FRED) on the roadmap.
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
