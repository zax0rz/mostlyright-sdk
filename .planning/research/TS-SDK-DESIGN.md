# tradewinds-ts — Design Document

**Status:** Planning (no implementation yet)
**Drafted:** 2026-05-23
**Source of truth:** [`PYTHON-SURFACE-INVENTORY.md`](./PYTHON-SURFACE-INVENTORY.md)
**Consumer-of-record:** Rob's Chrome extension (Kalshi-page weather overlay) + future web dashboards
**Naming:** `tradewinds-ts` is the colloquial name; npm publishes under the scope `@tradewinds/*` (see §2).

---

## 0. TL;DR

`tradewinds-ts` is a TypeScript port of the `tradewinds` Python SDK. It calls the SAME public APIs (AWC, IEM ASOS, IEM CLI, GHCNh, NOAA BDP, Polymarket Gamma) from the SAME endpoints, mirrors the SAME schemas, and returns the SAME row shapes as the Python SDK — just as plain object arrays instead of pandas DataFrames. No backend, no proxy in the default path.

Primary consumer: a Chrome extension that overlays settlement-station weather on Kalshi market pages. Secondary consumers: standalone web dashboards, Node scripts, Cloudflare Workers, Bun/Deno.

The Python SDK at v0.1.0 stays canonical. Schemas, station registry, Kalshi settlement map, source priorities, and merge logic are **exported from Python via codegen** and consumed by TS at build time — there is exactly one source of truth.

Going forward, every new feature added to `tradewinds` (Python) gets a paired TS work item; ROADMAP.md tracks both lanes.

---

## 1. Goals + Non-Goals

### Goals (v0.1.0 of `@tradewinds/*` npm packages)

1. `research(station, fromDate, toDate)` returns row-equivalent output to Python `tradewinds.research()` Mode 1 — same 19 columns, same values within float-roundtrip tolerance, same merge precedence.
2. Public surface from §1.1-1.19 of PYTHON-SURFACE-INVENTORY is ported (snapshot math, mode2 dispatch, transforms, qc alpha, discovery, international stations, forecasts stub, Kalshi resolvers, Polymarket discover/settle stub, format serializers, validator, temporal primitives, exception hierarchy).
3. Runs in: Chrome extension MV3 service worker, regular browser (with CORS caveats — §5), Node ≥20, Bun, Deno, Cloudflare Workers.
4. Bundle size: `@tradewinds/core` + `@tradewinds/weather` combined ≤ 60 KB minified+gzipped (excludes optional `apache-arrow` adapter).
5. Schemas + station registry + Kalshi map come from Python via codegen — no manual duplication.
6. Parity gate: the 5 Python parity fixtures + 5 TS-port fixtures (Phase TS-W2) replay against the TS implementation and produce row-equivalent output.

### Non-Goals (v0.1.0 of `@tradewinds/*`)

- **No DataFrame.** Rows are plain objects. (Optional `toArrow()` adapter via `apache-arrow` is opt-in dependency.)
- **No parquet I/O.** Cache stores JSON. (Cross-tool parquet read with `parquet-wasm` is a v0.2 stretch.)
- **No Python-cache compatibility.** Python writes `~/.tradewinds/cache/v1/...parquet`; TS writes `~/.tradewinds/cache-ts/v1/...json`. Different roots, different formats, no migration in v0.1.
- **No NWP (HRRR/GFS/NBM).** GRIB decode in browser is a v0.2 problem; v0.1 ships the same `NotImplementedError` stub Python ships.
- **No MCP server.** That's Python Phase 5.
- **No CLI binary.** v1.1+ for both languages.

---

## 2. Repo Layout + npm Package Topology

### 2.1 Where it lives

The TS workspace lives **in the same repo** as Python:

```
tradewinds/                              # repo root
├── packages/                            # existing Python workspace (PEP 420)
│   ├── core/      → tradewinds (PyPI)
│   ├── weather/   → tradewinds-weather (PyPI)
│   └── markets/   → tradewinds-markets (PyPI)
├── packages-ts/                         # NEW — npm workspace (pnpm)
│   ├── core/      → @tradewinds/core
│   ├── weather/   → @tradewinds/weather
│   ├── markets/   → @tradewinds/markets
│   ├── meta/      → tradewinds (unscoped meta-package re-exporting all three)
│   └── codegen/   → @tradewinds/codegen (build-only; not published)
├── schemas/                             # NEW — codegen output, committed
│   ├── json/                            #   JSON Schema (draft-2020-12) per canonical schema
│   ├── stations.json                    #   US + intl station registry export
│   ├── kalshi-settlement-stations.json  #   20-city Kalshi map + KNOWN_WRONG list
│   └── source-priority.json             #   merge precedence + LIVE_V1 policy
├── scripts/                             # existing
│   └── export_schemas.py                # NEW — Python script, writes everything under schemas/
├── .planning/                           # existing GSD planning
├── pnpm-workspace.yaml                  # NEW
├── package.json                         # NEW — workspace root
└── ...
```

**Rationale for same-repo:** the user said *"the roadmap and planning must cover BOTH"*. Single repo = single PLAN.md per feature can have a Python wave and a TS wave. Schema codegen lives next to Python schemas. CI runs both lanes from one workflow file. Rob (TS lane) and Vu (Python lane) submit PRs against the same `main` with cross-language review.

### 2.2 npm packages

| Package | npm name | Mirrors Python | Purpose |
|---|---|---|---|
| `packages-ts/core` | `@tradewinds/core` | `tradewinds` | `research`, snapshot, mode2, transforms, qc, discovery, international, forecasts stub, core (temporal/validator/formats/merge/exceptions) |
| `packages-ts/weather` | `@tradewinds/weather` | `tradewinds-weather` | Fetchers (AWC, IEM ASOS, IEM CLI, GHCNh), parsers, cache, catalog adapters |
| `packages-ts/markets` | `@tradewinds/markets` | `tradewinds-markets` | Kalshi NHIGH/NLOW resolvers, Polymarket discover/settle |
| `packages-ts/meta` | `tradewinds` | — | Convenience meta — re-exports from the other three so `import { research } from 'tradewinds'` works |
| `packages-ts/codegen` | `@tradewinds/codegen` (unpublished) | — | Build-time scripts: read `schemas/json/` and emit `.d.ts` + runtime validators |

**Peer-dependency wiring:**
- `@tradewinds/weather` declares `peerDependencies: { "@tradewinds/core": "^0.1.0" }`
- `@tradewinds/markets` declares the same
- `tradewinds` meta declares both as `dependencies`

**Versioning:** TS package versions track the Python version lockstep. The first TS release will be `0.1.0` matching Python `0.1.0`. Schema files carry an explicit `schemaVersion` field; the TS validator refuses to load a schema whose version it wasn't generated against (loud failure, no silent drift).

### 2.3 Workspace tool

**pnpm**, not npm or yarn. Reasons: faster install in monorepos, content-addressable store keeps disk usage sane across 5 packages, and `pnpm -r build` is the cleanest topological-build invocation in 2026.

```yaml
# pnpm-workspace.yaml
packages:
  - 'packages-ts/*'
```

---

## 3. Build + Test Tooling

### 3.1 Build

- **Bundler:** `tsup` (esbuild-based). One config per package produces:
  - `dist/index.mjs`   — ESM (primary)
  - `dist/index.cjs`   — CJS (Node CommonJS fallback)
  - `dist/index.global.js` — IIFE for `<script>` tags / Chrome extension content scripts
  - `dist/index.d.ts`  — declarations (via `tsup --dts`)
- **Type checker:** `tsc --noEmit` separately for strict mode.
- **TS config:** `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`, `target: ES2022`, `module: NodeNext`.

### 3.2 Test

- **Runner:** `vitest` (native ESM, Jest-compatible API, Vite-powered HMR).
- **HTTP mocking:** `msw` (works in both Node and browser). Recorded fixtures via `msw`'s `recordHandlers` workflow → committed JSON fixtures.
- **Property-based:** `fast-check` (TS equivalent of Hypothesis). Used for KnowledgeView, LeakageDetector, merge policy invariants.
- **Coverage:** `@vitest/coverage-v8`. Target ≥ 90% branch on `@tradewinds/core`, ≥ 80% line on `@tradewinds/weather` and `@tradewinds/markets`.
- **Live tests:** tagged `live` via `describe.skipIf(!process.env.TRADEWINDS_LIVE)`. Excluded from CI; run manually before publish.

### 3.3 Lint + Format

- `biome` (Rust-based, replaces eslint + prettier in one tool). Fast enough for pre-commit.
- Alternative: keep `eslint` + `prettier` if biome's rule coverage doesn't match house style — decide at TS-1.

### 3.4 Pre-commit

`lefthook` (Go binary, fast, language-agnostic — already a fit if Python is also using pre-commit; lefthook coexists). Runs `biome check`, `pnpm -r typecheck`, and `pnpm -r test --run -m '!live'`.

---

## 4. Schema + Data Codegen Pipeline

### 4.1 The hard rule

**Python is the source of truth.** TS never hand-redefines a schema, a station entry, a Kalshi city, or a source priority. If the Python data shape drifts, the TS build breaks loudly.

### 4.2 The export step (Python-side)

New script `scripts/export_schemas.py` walks every registered `Schema` subclass in `tradewinds.core.schemas` and emits JSON Schema (draft-2020-12) to `schemas/json/`:

```
schemas/json/
├── schema.observation.v1.json
├── schema.forecast.iem_mos.v1.json
├── schema.settlement.cli.v1.json
├── schema.observation_ledger.v1.json
└── schema.observation_qc.v1.json
```

Each JSON Schema file carries `$id`, `$schema`, `title`, `version`, and a `properties` map with `type/format/enum/description/minimum/maximum` from `ColumnSpec`. Imperial-rename maps emit as a sibling `imperialRenames` field (non-standard but documented).

The same script also writes:
- `schemas/stations.json` — array of all 20 US + 41 international stations with `{code, icao, ghcnh_id, name, tz, latitude, longitude}`. Built from `_internal._stations.STATIONS` + `international.INTERNATIONAL_STATIONS`.
- `schemas/kalshi-settlement-stations.json` — `{ stations: {NYC: {station: 'KNYC', citation: '...'}, ...}, known_wrong: ['KLGA', ...] }`. Built from `markets.catalog.kalshi_stations`.
- `schemas/source-priority.json` — `{ observation: {awc: 3, iem: 2, ghcnh: 1, ncei: 0}, climate: {final: 3.0, ncei_final: 2.5, correction: 2.0, preliminary: 1.0, estimated: 0.0}, live_v1: {...} }`. Built from `_internal.merge.observations.SOURCE_PRIORITY` + `_internal.merge.climate.REPORT_TYPE_PRIORITY` + `core.merge.LIVE_V1`.

These files are **committed to git** (not gitignored) so the TS build doesn't require a Python environment. CI runs `export_schemas.py` and `git diff --exit-code schemas/` — drift fails the build.

### 4.3 The consume step (TS-side)

`@tradewinds/codegen` runs at the start of every build:

1. Reads `schemas/json/*.json`.
2. Emits TypeScript types via `json-schema-to-typescript`:
   ```
   packages-ts/core/src/schemas/generated/
   ├── observation.v1.d.ts          // exports type ObservationV1
   ├── forecast-iem-mos.v1.d.ts
   ├── settlement-cli.v1.d.ts
   ├── observation-ledger.v1.d.ts
   └── observation-qc.v1.d.ts
   ```
3. Emits compiled runtime validators via `ajv` standalone code generation (each validator is a self-contained function — no runtime ajv dependency in the published bundle).
4. Emits typed station + Kalshi imports:
   ```ts
   // packages-ts/core/src/data/generated/stations.ts
   export const STATIONS: ReadonlyArray<StationInfo> = [...] as const;
   export const STATION_BY_CODE: ReadonlyMap<string, StationInfo> = ...;
   ```

Generated files live under `src/.../generated/` directories, are committed (so consumers can read sources), and are regenerated on `pnpm codegen`. CI checks `git diff --exit-code packages-ts/*/src/**/generated/`.

### 4.4 What the schema bridge does NOT do

- Does NOT export Python implementation logic (parsers, fetchers, merge). Those are hand-ported per phase with the parity gate.
- Does NOT auto-sync. New schemas added to Python require explicit `scripts/export_schemas.py` run + commit + paired TS phase.

---

## 5. Browser Reality Check: CORS, Permissions, Cache

### 5.1 CORS posture per endpoint (must verify in Phase TS-W1)

| Endpoint | Likely CORS | If blocked from web app |
|---|---|---|
| `aviationweather.gov/api/data/metar` | Yes (`Access-Control-Allow-Origin: *`) | n/a |
| `mesonet.agron.iastate.edu/cgi-bin/request/asos.py` | Unknown — must test | Document; recommend CORS proxy or extension-only |
| `mesonet.agron.iastate.edu/json/cli.py` | Yes (JSON endpoint, typically `*`) | n/a |
| `www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/...` | Unknown — must test | Document; GHCNh is the most likely casualty |
| `gamma-api.polymarket.com/events` | Yes | n/a |
| NOAA BDP (HRRR/GFS/NBM) | S3-fronted, typically yes | n/a (deferred to v0.2 anyway) |

**Phase TS-W1 must do a one-shot empirical CORS test against each endpoint** and write `.planning/research/TS-CORS-MATRIX.md` documenting actual behavior + workaround per endpoint (mirrors how `SOURCE-LIMITS.md` was captured for Python Phase 1.5).

### 5.2 Chrome extension consumer

In MV3, fetch from the service worker bypasses CORS if `host_permissions` declares the domain:

```json
// In Rob's extension manifest.json
"host_permissions": [
  "https://aviationweather.gov/*",
  "https://mesonet.agron.iastate.edu/*",
  "https://www.ncei.noaa.gov/*",
  "https://gamma-api.polymarket.com/*"
]
```

Recommend Rob imports `@tradewinds/core` in the service worker (where fetch + IndexedDB + Web Locks all work). Content scripts talk to it via `chrome.runtime.sendMessage`. Don't ship the fetchers in content-script bundles — content scripts have CORS, no IndexedDB access pattern, and stricter CSP.

### 5.3 Non-extension web app

For dashboards: document the CORS matrix. If GHCNh is blocked, offer a guidance section in README: "Run a tiny Cloudflare Worker / Vercel Edge Function proxy. Here's a 20-line template."

### 5.4 Cache topology

Cache is pluggable via `CacheStore` interface:

```ts
interface CacheStore {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T, opts?: { ttlMs?: number }): Promise<void>;
  delete(key: string): Promise<void>;
  withLock<T>(key: string, fn: () => Promise<T>): Promise<T>;
}
```

Concrete implementations:
- `IndexedDBStore` — `idb` lib (Jake Archibald, ~3KB minified). Uses Web Locks API for `withLock`.
- `FsStore` — Node `node:fs/promises` + `proper-lockfile`. Root: `process.env.TRADEWINDS_CACHE_DIR ?? path.join(os.homedir(), '.tradewinds', 'cache-ts')`. Note: distinct root from Python cache (`cache-ts` vs `cache`) — no cross-language compat in v0.1.
- `MemoryStore` — Map-backed, no persistence. Default for Cloudflare Workers / ephemeral runtimes.

Auto-detection in `defaultCacheStore()`:
```ts
if (typeof indexedDB !== 'undefined') return new IndexedDBStore();
if (typeof process !== 'undefined' && process.versions?.node) return new FsStore();
return new MemoryStore();
```

Key scheme: `tradewinds:v1:observations:<STATION>:<YYYY>:<MM>` storing JSON-serialized row arrays. Cache-skip same as Python: current LST month and any `.live` source. 30-day volatile-window exclusion for archive endpoints.

---

## 6. API Shape: Pandas → Plain Objects

### 6.1 Conversion rules (apply across all surfaces)

| Python | TypeScript |
|---|---|
| `pd.DataFrame` | `ReadonlyArray<RowT>` where `RowT` is a generated interface |
| Column access `df['temp_c']` | `rows.map(r => r.tempC)` (camelCase by default) |
| `df.attrs['source']` | A separate return object: `{ rows, source, retrievedAt }` |
| `datetime.datetime` (tz-aware UTC) | `string` (ISO 8601) at the data boundary; `Date` only at user-facing helpers |
| `datetime.date` | `string` (YYYY-MM-DD) |
| `float` (NaN/inf safe) | `number \| null` — null is the canonical "missing" sentinel; NaN is forbidden in stored rows |
| `int` | `number` (no BigInt; ranges fit in Number) |
| `Enum`-valued column | TS string-literal union from JSON Schema `enum` |
| `frozenset` | `ReadonlySet<T>` |
| `dataclass(frozen=True)` | `interface` + `Object.freeze` at construction site (or `readonly` fields) |
| `pd.Categorical` | string-literal union; no separate category type |

**Casing:** snake_case in Python → camelCase in TS by default at the public boundary. Internal generated types from JSON Schema keep snake_case (the wire format). A thin adapter at the API surface converts. Opt-in `{ casing: 'snake' }` flag on `research()` for users porting Python code (returns identical key names so a diff against Python output is mechanical).

### 6.2 `research()` shape

```ts
// @tradewinds/core
export interface ResearchOptions {
  includeForecast?: boolean;   // throws NotImplementedError in v0.1, like Python
  forecastModel?: string;
  tzOverride?: string;
  casing?: 'camel' | 'snake';  // default 'camel'
  cache?: CacheStore;          // default: auto-detected
  signal?: AbortSignal;        // browser-friendly cancellation
}

export interface ResearchRow {
  date: string;                // YYYY-MM-DD
  station: string;             // 3-letter code
  cliHighF: number | null;
  cliLowF: number | null;
  cliReportType: string | null;
  obsHighF: number | null;
  obsLowF: number | null;
  obsMeanF: number | null;
  obsMeanDewpointF: number | null;
  obsMaxWindKt: number | null;
  obsMaxGustKt: number | null;
  obsTotalPrecipIn: number | null;
  obsCount: number;
  fcstHighF: number | null;
  fcstLowF: number | null;
  fcstModel: string | null;
  fcstIssuedAt: string | null; // ISO 8601 UTC
  fcstPop6hrPct: number | null;
  fcstQpf6hrIn: number | null;
  marketCloseUtc: string;      // ISO 8601 UTC
}

export async function research(
  station: string,
  fromDate: string,
  toDate: string,
  opts?: ResearchOptions
): Promise<ResearchRow[]>;
```

### 6.3 Temporal primitives

```ts
export class TimePoint {
  constructor(value: Date | string);
  static now(): TimePoint;
  toUTCDate(): Date;
  toISOString(): string;        // always ends in 'Z'
  asZone(tz: string): string;   // ISO string in given IANA tz, via Intl.DateTimeFormat
  equals(other: TimePoint): boolean;
  before(other: TimePoint): boolean;
  after(other: TimePoint): boolean;
}

export class KnowledgeView<Row extends { knowledge_time: string }> {
  constructor(rows: ReadonlyArray<Row>, asOf: TimePoint);
  rows(): ReadonlyArray<Row>;   // returns rows where knowledge_time <= asOf
  get asOf(): TimePoint;
}

export function assertNoLeakage<Row extends { knowledge_time: string }>(
  rows: ReadonlyArray<Row>,
  asOf: TimePoint
): void; // throws LeakageError
```

### 6.4 Exceptions — class hierarchy mirroring Python

```ts
export class TradewindsError extends Error {
  readonly errorCode: string;
  readonly source: string | null;
  readonly requestId: string | null;
  toDict(): Record<string, unknown>;
}
export class SourceUnavailableError extends TradewindsError { /* +http_status, +retryable, ... */ }
export class SchemaValidationError extends TradewindsError { /* +schema_id, +violations, ... */ }
export class SourceMismatchError extends TradewindsError { /* +schema_source, +data_source, +role */ }
export class LeakageError extends TradewindsError { /* +as_of, +violating_count, +sample_violations */ }
export class TemporalDriftError extends TradewindsError { /* ... */ }
export class PayloadTooLargeError extends TradewindsError { /* ... */ }
export class DeferredMarketError extends TradewindsError { /* ... */ }
export class PolymarketEventError extends TradewindsError { /* ... */ }
```

`toDict()` JSON-safe shape matches Python `to_json_safe` semantics exactly — `null` for missing, ISO strings for dates, recursive coercion, cycle detection (returns `{ _cycle: true, value: String(obj) }`). Documented in the codegen output spec.

`MostlyRightMCPError` deprecation alias is **NOT** ported — TS is a clean start, no v0-era compat shims.

---

## 7. Phase Plan for TS Milestone

Detailed below in §11 and as stubs under `.planning/phases/ts-NN-*/`. Quick summary:

- **TS-W0 (Foundations)** — repo scaffold, pnpm workspace, tsup/vitest/biome, Python schema-export script, codegen pipeline, CORS matrix.
- **TS-W1 (Chrome-extension MVP)** — exceptions, station registry, Kalshi resolvers, AWC + IEM CLI fetchers, minimal `research()` (no GHCNh, no cache, in-memory only). Unblocks Rob's overlay.
- **TS-W2 (Parity gate)** — IEM ASOS fetcher, GHCNh fetcher (with CORS workaround), full parsers + merge_observations + merge_climate ports, parity test against 5 Python fixtures.
- **TS-W3 (Cache + temporal)** — `CacheStore` interface + IndexedDB/Fs/Memory impls, KnowledgeView/TimePoint/LeakageDetector, Validator with ajv-compiled standalone validators.
- **TS-W4 (Mode 2 + transforms + QC)** — `researchBySource`, transforms (lag/diff/rolling/calendar/wind_chill/heat_index/spread), QC alpha rules, IEM/GHCNh crosscheck.
- **TS-W5 (Markets)** — Kalshi NHIGH/NLOW resolvers wired to events; Polymarket discover/settle.
- **TS-W6 (Discovery + Snapshot + DataVersion)** — availability/describe/feature_catalog, DataSnapshot equivalent, DataVersion token.
- **TS-W7 (Docs + release)** — README, typedoc, parity write-up, Chrome-extension integration smoke test, npm publish via Changesets + GitHub OIDC.

Naming: TS-W rather than TS-N to keep them visually distinct from Python phases 1-5.

---

## 8. Feature Map: Python → TS Disposition

For every public Python surface item from PYTHON-SURFACE-INVENTORY, here is the v0.1.0 TS disposition. **Port** = 1:1 functional equivalent; **Adapt** = signature changes (e.g., DataFrame→array); **Stub** = ships with NotImplementedError matching Python; **Defer** = not in TS v0.1.0; **Skip** = Python-implementation detail not surfaced.

### Core

| Python | TS | Notes |
|---|---|---|
| `research()` | Adapt | Promise-returning, plain rows |
| `research_by_source` | Adapt | Same, with role-explicit dispatch |
| `assert_source_identity` | Port | |
| `snapshot.settlement_date_for` | Port | |
| `snapshot.settlement_window_utc` | Port | |
| `snapshot.cli_available_at` | Port | |
| `snapshot.build_snapshot` | Adapt | Returns `DataSnapshot` plain object |
| `DataSnapshot` | Adapt | TS interface + `Object.freeze` |
| `transforms.lag/diff/diff2/rolling` | Port | Operate on `Array<Row>`; same column-naming convention |
| `transforms.calendar_features` | Port | Use `Intl.DateTimeFormat` for tz-aware hour/dow extraction |
| `transforms.spread/wind_chill/heat_index` | Port | NWS formulas identical |
| `transforms.clip_outliers` | Port | |
| `qc.QCEngine + ALPHA_RULES` | Port | Bitfield ints stay as `number` (32-bit safe) |
| `qc.crosscheck_iem_ghcnh` | Port | |
| `discovery.availability` | Port | Reads from CacheStore instead of fs |
| `discovery.climate_gaps` | Stub | `NotImplementedError` like Python |
| `discovery.describe` | Port | Reads JSON-Schema description fields |
| `discovery.feature_catalog` | Port | |
| `discovery.DataVersion` (v2 shape) | Port | Use Web Crypto `crypto.subtle.digest('SHA-256')` |
| `international.daily_extremes` | Port | `Intl.DateTimeFormat` for local calendar day |
| `international.INTERNATIONAL_STATIONS` | Port | From codegen output |
| `international.DeferredMarketError` | Port | |
| `forecasts.forecast_nwp` | Stub | NotImplementedError; deferred to v0.2 like Python |
| `core.TimePoint` | Port | `__slots__` → readonly fields + `Object.freeze` |
| `core.KnowledgeView` | Port | Generic over row type |
| `core.LeakageDetector` / `assert_no_leakage` | Port | |
| `core.Schema/ColumnSpec/SchemaRegistration` | Port | Lite version — ajv handles most of what Schema framework does in Python |
| `core.validate_dataframe` | Adapt → `validateRows(rows, schemaId, opts)` | |
| `core.register_schema` | Skip (codegen handles it) | |
| `core.formats.{df,parquet,json,csv,toon}_{dumps,loads}` | Mixed | json: port; csv: port; toon: port; dataframe: skip (no DataFrame); parquet: defer (v0.2) |
| `core.merge.query_time_merge` | Port | |
| `core.merge.LIVE_V1` / `ObservationMergePolicy` | Port | From codegen |
| Exception hierarchy (8 classes) | Port | See §6.4 |
| `MostlyRightMCPError` deprecation alias | Skip | |

### Weather

| Python | TS | Notes |
|---|---|---|
| `_fetchers.awc.fetch_awc_metars` | Port | `fetch()` based, retry wrapper |
| `_fetchers.iem_asos.download_iem_asos` | Port | Yearly chunks (lifted from Python Phase 1.5); CORS-flagged |
| `_fetchers.iem_cli.download_cli` | Port | |
| `_fetchers.iem_cli.download_cli_range` | Port | |
| `_fetchers.ghcnh.download_ghcnh` | Port | CORS workaround documented |
| `_fetchers._iem_chunks.yearly_chunks_*` | Port | Pure-function date math |
| `_awc.awc_to_observation` | Port | |
| `_iem.iem_to_observation` | Port | |
| `_iem.parse_iem_file` | Port | CSV parser (use `papaparse` minimal, ~10KB) |
| `_climate.parse_cli_record + parse_cli_response` | Port | |
| `_climate.infer_report_type` + `REPORT_TYPE_PRIORITY` | Port | From codegen |
| `_ghcnh.parse_ghcnh_row + parse_ghcnh_file` | Port | PSV parser |
| `_ghcnh.ghcnh_station_to_code` | Port | |
| `cache.cache_path/climate_cache_path/read_cache/write_cache/...` | Adapt | Key generator + CacheStore abstraction |
| `catalog.WeatherAdapter` Protocol | Port | TS interface |
| `catalog.IEMAdapter/AWCAdapter/GHCNhAdapter/CLIAdapter` | Port | |
| `catalog.register_adapter/get_adapter/list_sources` | Port | |
| pyarrow `OBSERVATION_SCHEMA` etc. | Skip | Replaced by JSON-Schema + ajv |

### Markets

| Python | TS | Notes |
|---|---|---|
| `KALSHI_SETTLEMENT_STATIONS` + `KNOWN_WRONG_STATIONS` | Port | From codegen |
| `kalshi_nhigh.resolve` / `kalshi_nlow.resolve` | Port | Identical contract IDs |
| `NHighResolution/NLowResolution` / `StationCitation` | Port | TS interfaces |
| `polymarket.polymarket_discover` | Port (lite stub matching Python) | Eventually wired in TS-W5 |
| `polymarket.polymarket_settle` | Port | UUID4 regex, 16KB cap, netloc allowlist all enforced |
| `RESOLUTION_SOURCE_ALLOWLIST` | Port | |

### Internal helpers

| Python | TS | Notes |
|---|---|---|
| `_internal._convert.*` (unit conversions) | Port | Pure functions; same constants |
| `_internal._bounds.*` + regex constants | Port | |
| `_internal._http.download_with_retry` | Adapt | Wrap `fetch()` with retry/backoff/timeout via `AbortController` |
| `_internal._pairs.build_pairs / pairs_to_dataframe` | Adapt | `buildPairs(...) => ResearchRow[]` |
| `_internal._pairs.market_close_utc` | Port | |
| `_internal.merge.merge_observations/merge_climate` | Port | |
| `_internal.versioning.DataVersion` (v1 shape) | Port | Distinct from `discovery.DataVersion` (v2 shape) — disambiguate via `LegacyDataVersion` + `DataVersion` in TS |
| `_internal._stations.STATIONS` + `StationInfo` | Port | From codegen |
| `_internal.models.Observation` (30 fields + 2 computed) | Port | TS interface; computed fields derived in factory function |

---

## 9. Parity Strategy

### 9.1 Parity gate (Phase TS-W2)

Python tests already capture 5 byte-equivalent fixtures (`tests/fixtures/parity/`). For TS:

1. Re-export each fixture's **HTTP recordings** (already captured by `pytest-recording` if available; otherwise capture once via `msw recordHandlers` against a local Python run).
2. Re-export each fixture's **expected output** as JSON (one file per fixture, `tests/fixtures/parity/<name>.expected.json`).
3. TS parity test: load HTTP recording → start `msw` → call `research()` → compare row-by-row with `expected.json` using a structural equality + numeric-tolerance helper.

**Tolerance:** structural equality of all string/enum columns; for numeric columns: `Math.abs(a - b) <= 0` (exact) — JS Number IS float64, so this should hold. If it doesn't, investigate; do not loosen tolerance silently. (Document the one acceptable drift: `obs_max_wind_kt` etc. that pass through `kt → ms → kt` round-trip may show 1-ulp drift; we'd refactor to avoid the round-trip in that case rather than accept it.)

### 9.2 Continuous drift detection

Same two-tier fixture pattern as Python: `tests/fixtures/parity/` frozen, `tests/fixtures/drift/` weekly-rotated. The drift cron is a GitHub Actions job that runs the live `research()` for the 5 fixtures and emits a `drift-report.md`; soft-fail (never blocks CI), opens an issue on mismatch.

### 9.3 Cross-language fuzzing (post-v0.1)

A v0.2 idea: a property-based test that picks random (station, date_range) inputs, calls Python `research()` via subprocess and TS `research()`, asserts row-equivalent output. Catches divergence in edge cases not covered by the 5 frozen fixtures.

---

## 10. CI/CD

### 10.1 Workflows

- `test-ts.yml` — push/PR. pnpm install → codegen drift check → biome → typecheck → vitest with coverage → bundle size gate (`size-limit`).
- `test-python.yml` — existing, unchanged.
- `release-ts.yml` — fires on `vts-*` git tags (e.g., `vts-0.1.0`). Uses Changesets + npm OIDC (no long-lived `NPM_TOKEN` — npm now supports OIDC trusted publishing similar to PyPI).
- `release-python.yml` — existing, unchanged (PyPI trusted publishing already shipped in Python Phase 4).
- `schema-drift.yml` — push/PR. Runs `scripts/export_schemas.py` and `git diff --exit-code schemas/ packages-ts/*/src/**/generated/`. Fails build on drift.
- `drift-rotate-ts.yml` — weekly Mon 07:30 UTC. Live fixture rotation soft-fail.

### 10.2 npm trusted publishing

npm announced OIDC trusted publishing in late 2025 (mirrors PyPI's flow). Each TS package registers a pending publisher on npmjs.com pointing at `helloiamvu/tradewinds` + workflow `release-ts.yml` + environment `npm`. First publish unblocks the registration. Three pending publishers (`@tradewinds/core`, `@tradewinds/weather`, `@tradewinds/markets`) + one for `tradewinds` meta = four registrations.

If npm OIDC isn't viable for any reason, fallback is `NPM_TOKEN` secret with granular access tokens (one per package, scoped read+publish only).

### 10.3 Bundle-size gate

`size-limit` config per package:

| Package | Limit (min+gzip) |
|---|---|
| `@tradewinds/core` | 25 KB |
| `@tradewinds/weather` | 35 KB |
| `@tradewinds/markets` | 10 KB |
| `tradewinds` (meta) | 70 KB |

Generated validators are ajv-standalone (no runtime ajv). Date math uses native `Intl`. CSV parsing uses a hand-rolled minimal parser, not `papaparse` (if size-limit demands).

---

## 11. Phase Breakdown (detail)

### TS-W0 — Foundations

**Goal:** Working `pnpm install && pnpm -r build && pnpm -r test` from a clean clone; codegen pipeline runs; CORS matrix captured; CI green on a hello-world test in each package.

**Tasks:**
- `pnpm-workspace.yaml` + root `package.json` + `tsconfig.base.json`.
- Five package scaffolds with `package.json`, `tsup.config.ts`, `vitest.config.ts`, hello-world test each.
- `scripts/export_schemas.py` — walks Python schemas, emits `schemas/json/*.json` + station/Kalshi/priority JSONs. Plus a unit test that asserts the JSON output is stable across runs.
- `@tradewinds/codegen` — reads `schemas/` and emits TS types + ajv standalone validators + station/Kalshi/priority data modules.
- Pre-commit (`lefthook` or extend existing pre-commit).
- CI: `test-ts.yml`, `schema-drift.yml`.
- One-shot CORS test against AWC, IEM (both endpoints), GHCNh, Polymarket Gamma → `.planning/research/TS-CORS-MATRIX.md`.

**Success criteria:**
1. Clean clone → `pnpm install && pnpm codegen && pnpm -r build && pnpm -r test --run` exits 0.
2. `scripts/export_schemas.py` produces deterministic output (`diff` of two runs is empty).
3. `schemas/json/` contains 5 JSON-Schema files + `stations.json` + `kalshi-settlement-stations.json` + `source-priority.json`, all committed.
4. CORS matrix documents posture + workaround per endpoint.
5. CI green: codegen drift check + biome + typecheck + vitest pass.

### TS-W1 — Chrome-extension MVP

**Goal:** Unblock Rob's extension. Ship the smallest useful surface — station lookup, Kalshi resolver, AWC live observations, IEM CLI settlement — wired into a minimal `research()` that does what Mode 1 does but only with AWC + CLI (no IEM ASOS, no GHCNh, no cache yet).

**Tasks:**
- Exception hierarchy (`@tradewinds/core/exceptions`).
- `_internal._convert` unit conversions ported (pure functions).
- `_internal._bounds` constants + path validators ported.
- `_internal._http` retry wrapper around `fetch()`.
- Station registry ported (from codegen).
- Kalshi NHIGH/NLOW resolvers ported (from codegen + small resolver fns).
- AWC fetcher + parser (`_awc.awc_to_observation`).
- IEM CLI fetcher + parser (`_climate.parse_cli_record` + range fetcher).
- `_internal._pairs.market_close_utc` ported.
- `snapshot.settlement_date_for` + `settlement_window_utc` + `cli_available_at` ported.
- Minimal `research()` — AWC + CLI only, in-memory, no cache. Returns `ResearchRow[]` with the 19 columns (forecast columns null, GHCNh-derived obs columns may be null).

**Success criteria:**
1. `await research('NYC', '2025-01-01', '2025-01-07')` from a Node script returns rows with non-null `cliHighF`/`cliLowF` and `obsHighF`/`obsLowF`.
2. `resolve('KHIGHNYC', new Date('2025-01-06'))` returns `{ settlementSource: 'cli.archive', settlementStation: 'KNYC', cityTicker: 'NYC', contractDate: '2025-01-06' }`.
3. `KNOWN_WRONG_STATIONS` contract test passes (no Chicago resolves to KORD, etc.).
4. Chrome-extension smoke test: a one-page test extension can call `research()` from its service worker against AWC + IEM CLI live.
5. Bundle size for the W1 subset is ≤ 30 KB minified+gzipped.

### TS-W2 — Parity gate

**Goal:** Pass the 5-fixture parity gate against Python `research()` output.

**Tasks:**
- IEM ASOS fetcher (yearly chunks, leap-year safe — lifted from Python Phase 1.5).
- IEM ASOS CSV parser.
- GHCNh fetcher (with documented CORS workaround if blocked).
- GHCNh PSV parser.
- `_internal.merge.merge_observations` ported (strict `>`, first-seen wins, AWC=3 > IEM=2 > GHCNh=1).
- `_internal.merge.merge_climate` ported.
- `_internal._pairs.build_pairs` + `pairs_to_dataframe` ported.
- Update `research()` to include all four sources.
- Export 5 Python parity fixtures as JSON + msw HTTP recordings.
- TS parity test that loads each fixture, starts msw, calls `research()`, asserts row-equivalent output.

**Success criteria:**
1. All 5 parity fixtures pass with exact numeric equality (no tolerance loosening).
2. Drift detection cron job lands (`drift-rotate-ts.yml`).
3. ≥ 80% line coverage on weather package; ≥ 90% branch on core merge code.

### TS-W3 — Cache + temporal primitives + validator

**Goal:** Persistence + temporal safety + validation layer.

**Tasks:**
- `CacheStore` interface + `IndexedDBStore` + `FsStore` + `MemoryStore` + `defaultCacheStore()`.
- LST current-month-skip + `.live`-never-cached + 30-day volatile-window rules.
- Web Locks API wrapper (browser) + `proper-lockfile` wrapper (Node) for `withLock`.
- `TimePoint`, `KnowledgeView<T>`, `LeakageDetector` + `assertNoLeakage`.
- `validateRows(rows, schemaId, opts)` using ajv standalone validators.
- Property-based tests via `fast-check` for KnowledgeView/LeakageDetector/validator invariants.

**Success criteria:**
1. Second call to `research()` for cached month is ≤ 10% of first-call wall time.
2. `assertNoLeakage` throws `LeakageError` with `to_dict()` payload matching Python shape on a row with `knowledge_time > asOf`.
3. `validateRows` throws `SchemaValidationError` with `schema_id` + `violations` array matching Python rules vocabulary.
4. ≥ 90% branch coverage on `@tradewinds/core`.

### TS-W4 — Mode 2 + transforms + QC

**Goal:** Quality layer matching Python Phase 3 + 3.4 + 3.5.

**Tasks:**
- `researchBySource(station, source, fromDate, toDate)` dispatching to specific adapter; `assertSourceIdentity(rows, expectedSource)`.
- Transforms: `lag`, `diff`, `diff2`, `rolling`, `calendarFeatures`, `spread`, `windChill`, `heatIndex`, `clipOutliers`. Same column-naming convention as Python.
- QC alpha rules ported (5+ rules: temp/dewpoint/wind/pressure bounds, METAR-corruption signal).
- `QCEngine.apply(rows)` adds `obsQcStatus` bitfield (number) per row.
- `crosscheckIemGhcnh(iemRows, ghcnhRows, opts?)` returns disagreement rows.

**Success criteria:**
1. Round-trip property test: `rows` then `transforms.lag(rows, 'tempF', 3)` produces an array whose `tempFLag3` at index i equals `tempF` at index i-3 for i ≥ 3 and null otherwise.
2. Heat index for (90°F, 70%RH) matches NWS reference table within 1°F (Python and TS both).
3. QC alpha rules fire on the canonical bad-row fixtures shared with Python.

### TS-W5 — Markets

**Goal:** Kalshi resolver wired into events; Polymarket discover/settle live (no longer stub).

**Tasks:**
- Polymarket Gamma API client (rate-limited 0.2s, User-Agent, 429+5xx retries, pagination by offset, dedup by slug, max 10000 events).
- `polymarketDiscover()` + Tier 0/1/2/3 resolver (Wunderground/NOAA WRH regex + per-event station resolver).
- `polymarketSettle(eventId, { description? })` engine — uses (Python-parity) `dailyExtremes()` as resolution source, half-up rounding to whole-degree-native, bucket match, `TooEarlyToSettleError` for unfinalized.
- `polymarket_city_stations.json` codegen export consumed.

**Success criteria:**
1. `polymarketDiscover()` against live Gamma API returns ≥ 50 active weather events without rate-limit errors.
2. `polymarketSettle(eventId)` for a known-resolved historical event returns the same bucket Python `polymarket_settle` returns.
3. UUID4 regex + 16KB description cap + netloc allowlist all enforced (negative tests).

### TS-W6 — Discovery + Snapshot + DataVersion

**Goal:** Ergonomic surface for "what do I have for KNYC?" + reproducibility.

**Tasks:**
- `availability(station)` reads from `CacheStore`.
- `describe(schemaId)` reads from JSON-Schema description fields.
- `featureCatalog()` enumerates transforms surface.
- `internationalDailyExtremes(rows, { stationTz })` ported.
- `buildSnapshot(...)` + `DataSnapshot` interface + `.toDict()` + `.toToon()`.
- `DataVersion` (discovery v2 shape) using `crypto.subtle.digest('SHA-256')`.

**Success criteria:**
1. `availability('KNYC')` returns `{ station, monthsCached, firstMonth, lastMonth }`.
2. Same `(station, fromDate, toDate)` invocation across two runs produces the same `DataVersion.token`.
3. `internationalDailyExtremes` UTC-wrap edge cases (RJTT UTC+9, SAEZ UTC-3, NZWN UTC+12/13 DST) tested.

### TS-W7 — Docs + release

**Goal:** v0.1.0 to npm.

**Tasks:**
- README quickstart (`<5min` for fresh installer, timed by external person).
- Typedoc generation.
- `docs/chrome-extension-integration.md` — guide for Rob.
- Changesets + npm OIDC trusted publishing setup.
- `release-ts.yml` workflow.
- Tag `vts-0.1.0rc1` → publish to npm under `--tag next` for soak.
- Tag `vts-0.1.0` → publish to npm `latest`.

**Success criteria:**
1. `npm install @tradewinds/core @tradewinds/weather @tradewinds/markets` works in a clean directory.
2. `npm install tradewinds` (meta) works.
3. Chrome-extension smoke test runs end-to-end on `latest` package.
4. Bundle-size gate green.
5. Documentation passes external-reader timer.

---

## 12. Risks + Mitigations

| Risk | Mitigation |
|---|---|
| GHCNh blocks CORS, breaking GHCNh path in web-app consumers | Phase TS-W0 CORS matrix surfaces this; document Cloudflare Worker proxy template; treat GHCNh as optional in web-app docs |
| IEM ASOS endpoint changes, breaking parity (mirrors AWC Sept-2025 incident in Python) | Drift cron alerts within 1 week; URL constants live in one file (`@tradewinds/weather/src/_fetchers/iem-asos.ts`) for fast fix |
| JS `number` float64 drift from pandas `float64` on some operations (e.g., `Number.parseInt('1.0')`) | Parity gate uses exact equality; loosening tolerance requires explicit decision + memo |
| pnpm + npm OIDC setup is unfamiliar to user — registration friction | Document four pending-publisher registrations in TS-W7 launch checklist; mirror PyPI registration playbook from Python Phase 4 |
| Chrome-extension content-script CSP rejects ESM imports | Bundle to IIFE for content-script use case; service-worker bundle stays ESM; ship both via tsup |
| Bundle size balloons past 60KB gate as features land | `size-limit` enforced in CI; tree-shake-friendly exports; avoid pulling in `papaparse`/`luxon` unless tiny manual parser doesn't suffice |
| Schema drift between Python and TS goes undetected | `schema-drift.yml` CI workflow + version field check at validator-load time |
| Rob's extension launches before TS-W1 is ready | Phase TS-W1 success criteria explicitly includes "Chrome-extension smoke test"; coordinate via STATE.md |
| Two `DataVersion` shapes confuse consumers | Disambiguate in TS: `LegacyDataVersion` (from `@tradewinds/core/internal/versioning`) vs `DataVersion` (from `@tradewinds/core/discovery`); deprecate the legacy form in v0.2 if not needed |
| `NotImplementedError`-style stubs for forecast_nwp confuse users who expect feature parity | README clearly states v0.1.0 scope per language; add a "Feature parity matrix" page |

---

## 13. Open decisions to revisit before TS-W0

1. **npm scope ownership.** Is `@tradewinds` available on npm? If not, options: register a different org name, or use unscoped `tradewinds-core` / `tradewinds-weather` / `tradewinds-markets`. Decide before any `pnpm publish`.
2. **biome vs eslint+prettier.** Default to biome (one tool, fast); fall back to eslint+prettier if a needed rule isn't supported.
3. **Cache root naming.** `cache-ts/` vs `cache/typescript/` vs alongside Python in `cache/`. Default: separate root `~/.tradewinds/cache-ts/v1/` to avoid any chance of TS reading partial Python parquet writes.
4. **Meta package name.** `tradewinds` unscoped if available; otherwise `@tradewinds/sdk` or just skip meta and have users import from each scoped package.
5. **lockstep version cadence.** Python and TS lockstep on minor versions (`0.2.0` released together) or independent patches OK? Default: lockstep minors, independent patches; document in `CONTRIBUTING.md` once it exists.

None of these block planning — they get resolved early in TS-W0.

---

## 14. Ongoing Maintenance Workflow — Keeping Python and TS in Sync Long-Term

§§1-13 cover the **initial build** of `@tradewinds/*`. This section covers **what happens for every commit after TS v0.1.0 ships** — the long-tail discipline that prevents Python and TS from quietly diverging into two unrelated codebases sharing a name.

This section is a summary; the binding contract lives at [`.planning/CROSS-SDK-SYNC.md`](../CROSS-SDK-SYNC.md). Read that document for the parity-ticket template, ownership table, CI workflow inventory, and step-by-step recipes. The summary below is for orientation only.

### 14.1 The three sync surfaces

| Surface | Source of truth | How TS stays in sync | Enforcement |
|---|---|---|---|
| **Schemas + station/Kalshi/source-priority data** | Python (`tradewinds.core.schemas`, `_internal._stations`, `markets.catalog.kalshi_stations`, `_internal.merge.*`) | `scripts/export_schemas.py` regenerates `schemas/json/` + `schemas/*.json` on every PR that touches a schema source file; `@tradewinds/codegen` reads `schemas/` and regenerates TS `.d.ts` + ajv-standalone validators + typed data modules; both outputs are committed | `schema-drift.yml` CI workflow — runs exporter + codegen + `git diff --exit-code`. Hard-fail. |
| **Behavioral parity** (function signatures, transforms, parser fixes, settlement math, new endpoints) | Whichever lane lands the canonical change first (usually Python) | The author of the canonical PR either lands the paired-language diff in the same PR OR files a `parity-ts` (or `parity-py`) ticket using the CROSS-SDK-SYNC §2.2 template before merging | `parity-ticket-check.yml` CI workflow — inspects diff against the parity-trigger path list; fails if the PR touches a parity-required path without a `Parity-Ticket:` reference, paired diff, or `*_only` opt-out justification. Hard-fail. |
| **MCP surface** (Python Phase 5, v0.2+) | Python SDK as canonical implementation; `packages/mcp/` is a wrapper | MCP tool input/output schemas are reflected from SDK function type hints (no hand-written schemas). TS does NOT consume MCP. | `mcp-sdk-sync.yml` (ships Python Phase 5 PLAN-01) — reflection check + coverage assertion + behavioral parity (JSON-RPC subprocess vs direct SDK call). Hard-fail. |

### 14.2 The author's lifecycle — "I want to add a feature"

Common case: a Python lane author adds a new `tradewinds.transforms.X()` function.

```
   ┌──────────────────────────────────────────────────────────────────────────┐
   │ 1. Branch off main, implement Python (tests, docstring, parser).         │
   ├──────────────────────────────────────────────────────────────────────────┤
   │ 2. Open Python PR.                                                       │
   │    - If small + author can also do TS in same PR → land both together.   │
   │    - Otherwise: file parity ticket (template in CROSS-SDK-SYNC §2.2).    │
   │      Body line:  Parity-Ticket: #NNNN                                    │
   ├──────────────────────────────────────────────────────────────────────────┤
   │ 3. CI runs:                                                              │
   │    - test.yml         (Python tests — hard-fail)                         │
   │    - parity-ticket-check.yml   (detects missing parity ticket — hard)    │
   │    - schema-drift.yml          (if schemas touched — hard)               │
   │ 4. Two-reviewer loop per REVIEW-DISCIPLINE.md.                           │
   │ 5. Merge to main.                                                        │
   ├──────────────────────────────────────────────────────────────────────────┤
   │ 6. Parity ticket assigned to TS lane lead (Rob) for port.                │
   │    Within the milestone deadline (P0 = next release, P1 = next minor).   │
   ├──────────────────────────────────────────────────────────────────────────┤
   │ 7. Port PR opens against `packages-ts/`.                                 │
   │    Body line:  Resolves Parity-Ticket #NNNN                              │
   │ 8. CI runs:                                                              │
   │    - test-ts.yml      (TS tests + bundle gate — hard-fail)               │
   │    - schema-drift.yml (regenerated codegen — hard-fail)                  │
   │    - parity-ticket-check.yml (passes trivially — TS-side change)         │
   │ 9. Two-reviewer loop. Merge.                                             │
   │ 10. Parity ticket moves to `resolved`.                                   │
   └──────────────────────────────────────────────────────────────────────────┘
```

For the rare TS-first feature: same flow, mirror-symmetric. Use `python_only: true` / `typescript_only: true` PR-body labels for things that genuinely don't have a counterpart (e.g., a Chrome-extension UI helper).

### 14.3 The release-readiness gate

Before tagging any Python `v*` or TS `vts-*` release:

```bash
$ scripts/parity_status.py --milestone "TS v0.1.0"
P0 open: 0
P1 open: 2 (#NN, #NN)  ← reviewed; either resolve OR explicitly defer-to-next-milestone
P2 open: 5
─────────────────────────────
release-ready: YES
```

`release.yml` (Python) and `release-ts.yml` both call `parity_status.py` and refuse to publish on non-empty P0 list. P1/P2 are advisory.

### 14.4 The drift cron — watching the outside world

Two soft-fail watchdogs, one per lane, comparing live `research()` output against the SAME committed parity fixtures:

| Workflow | Lane | When | Action on mismatch |
|---|---|---|---|
| `drift-rotate.yml` | Python | Weekly Mon 07:00 UTC | Write `drift-report.md`; open GH issue with `drift-py` label; NEVER block CI |
| `drift-rotate-ts.yml` | TS | Weekly Mon 07:30 UTC | Same, with `drift-ts` label |

**Triage matrix** (auto-populated in each issue body):

| Python drift | TS drift | Diagnosis |
|---|---|---|
| Yes | Yes | Real upstream-API shape change. Both lanes fix. |
| Yes | No | Python-side fetcher/parser bug introduced since last green. |
| No | Yes | TS-side fetcher/parser bug introduced since last green. |
| No | No | Both green — close issue. |

### 14.5 Schema-version bumps (rare but routine)

- **Additive (`vN` stays)**: nullable column, new enum value, widened type. Regenerate, both lanes patch-bump.
- **Breaking (`vN` → `v(N+1)`)**: removed column, narrowed type, removed enum value, rename. Both versions coexist for one minor; consumers migrate; `vN` removed in the minor after that. Logged as Key Decision in PROJECT.md. Coordinated PR-pair across lanes.

### 14.6 What this prevents

- **Silent schema drift.** Without `schema-drift.yml`, a Python schema column rename could ship to PyPI while TS still believes the old name exists; users hitting Mode 2 dispatch would get inconsistent rows depending on SDK.
- **Forgotten ports.** Without `parity-ticket-check.yml`, Python-only fixes accumulate; six months later the TS port is functionally a different SDK.
- **MCP surface drift.** Without `mcp-sdk-sync.yml`, MCP tools and their wrapped SDK functions diverge; AI agents get stale schemas without the workflow noticing.
- **Loose tolerance in parity tests.** Hard rule: never loosen TS parity-test tolerance to make TS code pass. Either Python is wrong (fix in both), or TS is wrong (fix TS), or there's a genuine accepted-divergence (Key Decision + `accepted_drift` parity ticket).

### 14.7 What this DOES NOT do

- It does not eliminate human review. Two reviewers per PR, per REVIEW-DISCIPLINE.md.
- It does not catch logic bugs in parsers if both lanes have the same bug — the parity gate would pass while output is wrong. Drift cron against live upstream eventually catches this; user reports catch it sooner.
- It does not enforce per-language idiom (snake_case vs camelCase, error-class naming, async vs sync style). Those are documented conventions, reviewed by humans.
- It does not migrate cache files across language boundaries. Python writes `cache/v1/*.parquet`; TS writes `cache-ts/v1/*.json`. Cross-language read is a v0.2+ goal if at all.

### 14.8 Documentation entry points

| Purpose | File |
|---|---|
| Binding sync contract (read first) | [`.planning/CROSS-SDK-SYNC.md`](../CROSS-SDK-SYNC.md) |
| TS SDK design (this file) | `.planning/research/TS-SDK-DESIGN.md` |
| Python public surface inventory | [`.planning/research/PYTHON-SURFACE-INVENTORY.md`](./PYTHON-SURFACE-INVENTORY.md) |
| Release-readiness scripts | `scripts/parity_status.py` (ships TS-W0) |
| Schema export + manifest | `scripts/export_schemas.py` (ships TS-W0) |
| PR template + issue template | `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/parity_ticket.md` (ship TS-W0) |
| Review discipline | [`.planning/REVIEW-DISCIPLINE.md`](../REVIEW-DISCIPLINE.md) (existing; extended in TS-W0 for `ts-architect` reviewer) |

---

*Drafted by Claude under `/gsd-plan-phase`-equivalent freeform planning, 2026-05-23. §14 added 2026-05-23 alongside `.planning/CROSS-SDK-SYNC.md`.*
