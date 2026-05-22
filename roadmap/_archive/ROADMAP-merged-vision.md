# tradewinds — Merged Roadmap (mostlyright-mcp vision + tradewinds discipline)

**Branch:** `merged-vision`
**Generated:** 2026-05-21
**Status:** DRAFT — pending review before code starts

## What this is

This roadmap merges two prior plans:

- **mostlyright-mcp** (`~/Documents/GitHub/mostlyright-mcp/docs/design.md`, APPROVED 2026-05-21) — the architectural ambition: three-layer build (`core` temporal safety + `catalog` adapters + `mcp` server) with source-identity invariants, canonical schemas, leakage detection.
- **tradewinds Sprint 0** (`roadmap/sprint0.md`) — the execution discipline: uv workspace, parquet cache with `filelock`, byte-equivalent parity gate against `mostlyright==0.14.1`, two-lane plan with cross-review.

The MCP server surface is **deferred to v0.2**. Everything else from the mostlyright-mcp design — temporal primitives, source identity, schemas, validators — comes forward into v0.1, layered on top of tradewinds' workspace and parity-test scaffolding.

**One-line bet:** ship a Python SDK that is byte-equivalent to `mostlyright==0.14.1`'s `client.pairs()` AND structurally prevents temporal leakage AND enforces source identity AND has the seam for an MCP server later — in one release, not three.

## Why merged (vs picking one)

| | mostlyright-mcp alone | tradewinds alone | Merged |
|---|---|---|---|
| Temporal safety as load-bearing primitive | ✓ | ✗ (lifted as-is from v0.14.1) | ✓ |
| Source-identity invariant | ✓ | ✗ (`research()` has no `source` param) | ✓ |
| Canonical schemas + `validate_dataframe` | ✓ | ✗ | ✓ |
| Byte-equivalent parity to v0.14.1 as hard gate | ✗ ("integration parity criterion" only) | ✓ | ✓ |
| Local parquet cache with `filelock` + LST skip | ✗ | ✓ | ✓ |
| GHCNh in v0.1 | ✗ (deferred to v0.2) | ✓ | ✓ |
| MCP server | ✓ (v0.1) | ✗ | Deferred to v0.2 |
| Two-lane Vu/Founder execution with cross-review | ✗ | ✓ | ✓ |
| Pinned lift source (v0.14.1 tag, not head) | ✗ | ✓ | ✓ |
| ≥90% branch coverage on core | ✓ | ✗ (80% line) | ✓ on `core/`, 80% line elsewhere |
| Property-based tests for temporal invariants (Hypothesis) | ✓ | ✗ | ✓ |

The merged plan **takes the strict bar from whichever side had it**. No averaging.

## Architecture (three layers, MCP slot reserved)

```
packages/
  core/                          # tradewinds  (PyPI: tradewinds)
    src/tradewinds/
      __init__.py                # exports: research(), TimePoint, KnowledgeView, Schema, Validator, LeakageDetector
      core/
        temporal.py              # TimePoint, KnowledgeView
        schema.py                # Schema, schema registry
        validator.py             # Validator (incl. source-identity + temporal-drift checks)
        leakage.py               # LeakageDetector (audit tool, not structural)
        exceptions.py            # MostlyRightMCPError hierarchy (renamed: TradewindsError)
        formats/                 # dataframe | json | parquet | toon | csv serializers
      research.py                # top-level research() — pull_pairs equivalent
      _internal/                 # shared HTTP, cache, config (lifted from monorepo-v0.14.1)

  weather/                       # tradewinds-weather  (PyPI: tradewinds-weather)
    src/tradewinds/weather/
      __init__.py
      catalog/                   # NEW (mostlyright-mcp's catalog layer, namespaced under weather)
        __init__.py              # SUPPORTED_SOURCES dispatch
        iem.py                   # source IDs: iem.archive, iem.live (obs + forecasts)
        awc.py                   # source ID: awc.live
        cli.py                   # source ID: cli.archive
        ghcnh.py                 # source ID: ghcnh.archive  (tradewinds' v0.1 add; mostlyright-mcp deferred)
      _vendor/                   # lifted parsers from monorepo-v0.14.1 (verbatim, then re-wrapped)
        _iem.py                  # IEM observations + forecast parsing
        _awc.py                  # AWC METAR JSON parsing
        _climate.py              # NWS CLI settlement parsing (incl. _parse_product_timestamp)
        _ghcnh.py                # GHCNh parser
        _forecast_parse.py
        _forecast_columns.py
        _forecast_schema.py
        _convert.py              # unit conversions
        _bounds.py               # value range checks
        specs/                   # JSON specs
      cache.py                   # parquet cache, filelock-guarded, LST current-month-skip

  markets/                       # tradewinds-markets  (PyPI: tradewinds-markets)
    src/tradewinds/markets/
      __init__.py
      catalog/
        kalshi_nhigh.py          # Kalshi NHIGH/NLOW contract spec → settlement source resolution
        kalshi_nlow.py
      _kalshi_api.py             # (Sprint 0.5+; v0.1 ships contract specs only)

  mcp/                           # tradewinds-mcp  (PyPI: tradewinds-mcp)  — v0.2, scaffolded only in v0.1
    src/tradewinds/mcp/
      __init__.py
      __main__.py                # `tradewinds-mcp-server` console script (stub in v0.1)
      tools/
        catalog_search.py        # stub
        pull_pairs.py            # stub (wraps research())
        validate_dataframe.py    # stub (wraps Validator)
```

**Key change vs current tradewinds scaffold:**
- Adds `packages/core/src/tradewinds/core/` (temporal safety primitives).
- Adds `packages/weather/src/tradewinds/weather/catalog/` (adapter layer on top of `_vendor/`).
- Adds `packages/markets/src/tradewinds/markets/catalog/` (contract specs).
- Adds `packages/mcp/` as a new workspace member (stub only in v0.1; real in v0.2).

**Key change vs mostlyright-mcp design:**
- Distribution split into three packages (tradewinds / tradewinds-weather / tradewinds-markets) instead of one. Reason: lets a notebook user `pip install tradewinds-weather` without dragging in Kalshi market code, mirrors the current scaffold, and pre-shapes for verticals N+1.
- `tradewinds.weather.catalog.iem` instead of `tradewinds.catalog.weather.iem`. Reason: namespace is owned by the vertical package, not a top-level `catalog` that would force cross-package coupling.

## v0.1.0 deliverables

### Core (`packages/core/src/tradewinds/core/`)

Lifted intent from mostlyright-mcp design §"Layer responsibilities" (lines 170-178):

- `TimePoint` — UTC timestamp wrapper with explicit timezone + DST handling.
- `KnowledgeView` — query interface filtering rows by `knowledge_time <= as_of`. **Structural** leakage prevention.
- `Schema` — declarative, with `event_time`, `knowledge_time`, `source`, `retrieved_at` columns required. Records training-time source provenance. Includes `Schema.from_dataframe(df, ...)` for BYO.
- `Validator` — schema contract checks + source-identity invariant + temporal-drift (Amendments §B). Quarantines bad rows; surfaces lineage.
- `LeakageDetector` — audit tool for user-built training sets that did NOT come through `KnowledgeView`.
- Canonical schemas pinned:
  - `schema.observation.v1` (Amendments §A, lines 373-411)
  - `schema.forecast.iem_mos.v1` (Amendments §A, lines 413-429)
  - `schema.settlement.cli.v1` (Amendments §A, lines 431-446)
- Exception hierarchy (Amendments §D, lines 472-499) — renamed root from `MostlyRightMCPError` → `TradewindsError`. Subclasses keep their semantics: `SourceUnavailableError`, `SchemaValidationError`, `SourceMismatchError`, `LeakageError`.
- Format serializers: `dataframe`, `json`, `parquet`, `toon`, `csv` (TOON lifted from `monorepo-v0.14.1/.../_toon.py`).

**Bar:** ≥90% **branch** coverage. Property-based tests (Hypothesis) for `KnowledgeView` + `LeakageDetector` temporal invariants and source-identity invariant. Roundtrip tests for each format.

### Catalog adapters (`packages/weather/src/tradewinds/weather/catalog/`)

Four adapters in v0.1.0 (one more than mostlyright-mcp's plan, matching tradewinds' GHCNh-in-v0.1 bet):

| Adapter | Source IDs | Provides | Lift source (v0.14.1) |
|---|---|---|---|
| `iem` | `iem.archive`, `iem.live` | Observations (METAR/SPECI) + MOS forecasts | `_iem.py`, `_forecast_parse.py` |
| `awc` | `awc.live` | METAR JSON observations | `_awc.py` |
| `cli` | `cli.archive` | NWS CLI settlement (preliminary/final/correction dedup) | `_climate.py` (incl. `_parse_product_timestamp`, `REPORT_TYPE_PRIORITY`) |
| `ghcnh` | `ghcnh.archive` | GHCN-hourly historical | `_ghcnh.py` |

Each adapter:
- Declares `SUPPORTED_SOURCES: list[str]` at class level.
- Emits canonical schema columns (per Amendments §A).
- Stamps every row with `event_time`, `knowledge_time` (per-source rule from design.md lines 96-108), `source`, `retrieved_at`.
- Recorded-fixture integration test: saved HTTP responses replayed.

**Bar:** each adapter pulls last 30 days for ≥3 stations, all rows pass schema validation, knowledge_time matches the documented rule. 80% line coverage on `catalog/` modules; lifted `_vendor/` code retains its monorepo-v0.14.1 coverage.

### Markets (`packages/markets/src/tradewinds/markets/catalog/`)

- `kalshi_nhigh.py` — contract spec for NHIGH (daily high temp ≥ N). Maps settlement source → contract resolution.
- `kalshi_nlow.py` — symmetric for NLOW.
- **NOT in v0.1.0:** Kalshi API client (orderbook, fills). Sprint 0.5+.

### `research()` — the top-level join

Public API at `tradewinds.research()`:

```python
def research(
    contract: str,                          # e.g. "KXHIGHNYC"
    station: str,                            # e.g. "KORD"
    from_date: str,
    to_date: str,
    sources: dict[str, str] | None = None,   # {"observations": "iem.archive", "forecasts": "iem.archive", "settlement": "cli.archive"}; required for new code, defaulted for v0.14.1-parity callers
    include_forecast: bool = True,
    units: str = "imperial",                 # default imperial for v0.14.1 parity; new callers should pass "metric"
    format: str = "dataframe",               # "dataframe" | "json" | "parquet" | "toon" | "csv"
) -> pd.DataFrame | list[dict] | bytes | str: ...
```

**Two-mode behavior:**

1. **v0.14.1 parity mode** (`sources=None`, `units="imperial"`): byte-equivalent to `mostlyright==0.14.1`'s `client.pairs(station, from_date, to_date)`. Source defaults applied silently: `{obs: "iem.archive", fcst: "iem.archive", settle: "cli.archive"}`. Output columns: `date, station, cli_high_f, cli_low_f, obs_high_f, obs_low_f, obs_high_at, obs_low_at` (+ `fcst_*` if `include_forecast`).

2. **Source-explicit mode** (`sources={...}`): full mostlyright-mcp semantics. Output carries `obs_source`, `obs_retrieved_at`, `fcst_source`, `fcst_retrieved_at`, `settle_source`, `settle_retrieved_at` (per Amendments §C). `validate_dataframe` against a paired schema enforces each role independently.

A deprecation warning fires on mode 1 starting v0.2; mode 1 is removed in v0.3. This preserves the v0.14.1 lift gate while training the user base toward source-explicit calls.

### Cache (`packages/weather/src/tradewinds/weather/cache.py`)

Lifted policy from tradewinds CLAUDE.md line 46:

- Path: `$HOME/.tradewinds/cache/observations/{station}/{year}/{month}.parquet`.
- `filelock`-guarded for concurrent writes.
- Cache-skip when queried month equals current LST month for that station (current month is incomplete; elapsed months are stable).
- No user-visible `fresh=` kwarg.
- Cache rows carry the same `source` ID as the source-of-record. Cache is a speedup, not a different source ID (mostlyright-mcp design.md line 263).
- `*.live` endpoints are never cached. Archive data within the last 30 days stays direct-from-source (Amendments §B volatile window).

### Parity test (HARD GATE)

Lifted verbatim from tradewinds `roadmap/sprint0.md`:

- `tests/test_parity.py` — 5 fixtures captured against `mostlyright==0.14.1`'s `client.pairs(...)`.
- Sprint 0 / v0.1.0 ships only if all 5 fixtures byte-match.
- Fixtures captured at Day 0.5 (Lane V).
- **Mode 1 (v0.14.1 parity) is what's tested.** Mode 2 (source-explicit) has its own contract tests against canonical schemas.

## Out of scope for v0.1.0

- **MCP server.** Scaffolded as `packages/mcp/` with stub tools; not wired, not published. v0.2 deliverable.
- **Hosted R2 cache.** mostlyright-mcp design §"v0.2 — transparent read-through cache". Deferred unless 60-day validation gate passes.
- **`as_of_query` MCP tool.** Generic query passthrough; design.md line 222 says "ship only when a named user requests it."
- **Sports/politics/finance verticals.** v0.1 is weather only.
- **Preprocessing (RH, feels_like, MetPy re-parse).** Raw `metar_raw` is preserved in observation rows; preprocessing is Sprint 0.5+.
- **Open-Meteo adapter.** Licensing blocks redistribution; not in any v0.x.
- **CLI surface.** Python SDK only; CLI is v1.1+.
- **`pyproject.toml` for `packages/mcp/`** beyond a minimal stub. Real packaging arrives with v0.2.

## Sprint plan

This is a **two-phase** plan. Phase A is tradewinds Sprint 0 mostly as-written (the parity lift), Phase B is the mostlyright-mcp core layer + adapter refactor on top of it.

### Phase A — v0.14.1 parity lift (Days 1-4, two lanes)

Lifted from `roadmap/sprint0.md` and `roadmap/lanes/{founder,vu}-*-lane.md`. No changes to the day-by-day plan except:

- **Day 1 morning sync** (10 min): instead of agreeing on `_internal/` shape only, also agree on the `tradewinds.core` public surface — the names that Phase B will populate. This is a tiny addition; it costs nothing now and saves rework later.
- **Day 3 (HARD GATE):** parity test green. **No change.**
- **Day 4:** PyPI v0.1.0-alpha1 published as `tradewinds==0.1.0a1` and `tradewinds-weather==0.1.0a1`. Markets is `0.0.1` placeholder. **Mode 1 only at this point.** Mode 2 (source-explicit) lands in Phase B.

Day 4 exit state:
- `research(station, from_date, to_date)` works in mode 1, byte-equivalent to v0.14.1.
- `_internal/` shared utils lifted.
- Parsers lifted into `_vendor/`.
- Cache works.
- 5 parity fixtures pass.
- N=2 outreach sent (per `sprint0-validation.md`).

### Phase B — core + catalog refactor (Days 5-14)

This is the mostlyright-mcp work, layered onto the v0.14.1 lift now safely in place.

| Day | Lane V (Vu) | Lane F (Founder) | Gate |
|---|---|---|---|
| 5 | Stand up `tradewinds.core.temporal` (`TimePoint`, `KnowledgeView`) + property tests | Stand up `tradewinds.core.schema` + `Schema.from_dataframe()` | Both modules importable; basic tests green |
| 6 | `tradewinds.core.validator` incl. source-identity invariant + temporal-drift (Amendments §B) | Wrap `_vendor/_iem.py` with `catalog.iem` adapter emitting canonical `schema.observation.v1` rows + `knowledge_time` stamping | Adapter recorded-fixture test green |
| 7 | `tradewinds.core.leakage` (`LeakageDetector`) + Hypothesis property tests | `catalog.awc` + `catalog.cli` adapters, same pattern | Both adapter tests green |
| 8 | `tradewinds.core.formats.toon` (lift from v0.14.1 `_toon.py` + `_toon_list_codec.py`) + roundtrip tests for all 5 formats | `catalog.ghcnh` adapter | GHCNh adapter tests green |
| 9 | `tradewinds.core.exceptions` full hierarchy with structured payloads (Amendments §D) | `tradewinds.markets.catalog.kalshi_nhigh` + `kalshi_nlow` contract specs | All exception classes used in code paths |
| 10 | `research()` Mode 2 (source-explicit) implementation against `KnowledgeView` | `cache.py` updates: record `retrieved_at`, honor 30-day volatile window (no-cache for archive < 30d) | Mode 2 returns 6 source/retrieved_at columns per Amendments §C |
| 11 | Contract tests: `tests/contracts/test_schema_observation.py`, `test_schema_forecast.py`, `test_schema_settlement.py` | Migration test: `mostly-light/strategies/kxhigh` dry-run against tradewinds (editable install) matches therminal-py baseline | Both green |
| 12 | ≥90% branch coverage check on `core/`; add negative tests where missing (Amendments §H) | Performance smoke: `research()` for 1 station × 30 days finishes in <30s cold cache, <5s warm | Coverage gate met |
| 13 | README quickstart (<5min for fresh installer; timed by external person) | CI/CD: GitHub Actions, trusted publishing | Quickstart timed green; CI green |
| 14 | v0.1.0 release tag | Announcement to /r/algotrading + Kalshi Discord + DM the 2 named users | **v0.1.0 published with full design** |

### Phase C — MCP server (v0.2, weeks 3-4 post-v0.1)

Not in this roadmap's scope. The seam exists (`packages/mcp/` scaffolded). When v0.2 starts: real `pyproject.toml`, three tools wired (`catalog_search`, `pull_pairs`, `validate_dataframe`), `tradewinds-mcp-server` console script, JSON-RPC subprocess integration tests. mostlyright-mcp design.md §"`mostlyright_mcp.mcp`" (lines 202-226) is the spec.

## Hard gates (non-negotiable)

| Gate | Where | When |
|---|---|---|
| Mode 1 byte-parity with `mostlyright==0.14.1` (5 fixtures) | `tests/test_parity.py` | Day 3 |
| ≥90% branch coverage on `tradewinds.core` | CI | Day 12 |
| Property-based tests pass for `KnowledgeView`, `LeakageDetector`, source-identity invariant | `tests/property/` | Day 12 |
| All three canonical schemas have green contract tests | `tests/contracts/` | Day 11 |
| `mostly-light/kxhigh` dry-run matches therminal-py baseline (executable ship test, design.md line 316) | manual run | Day 11 |
| README quickstart timed <5min by external person | manual | Day 13 |
| No direct commits to main; every change goes through PR + cross-lane review | git history | continuous |
| Codex `model_reasoning_effort=high` on any PR touching `core/`, `_internal/merge/`, or `research.py` | CI label check | continuous |

## What's lifted from where

| From | What | To |
|---|---|---|
| `monorepo-v0.14.1/.../_iem.py` | IEM fetch + parse | `packages/weather/src/tradewinds/weather/_vendor/_iem.py`, wrapped by `catalog/iem.py` |
| `monorepo-v0.14.1/.../_awc.py` | AWC METAR JSON parse | `_vendor/_awc.py`, wrapped by `catalog/awc.py` |
| `monorepo-v0.14.1/.../_climate.py` | NWS CLI settlement parse | `_vendor/_climate.py`, wrapped by `catalog/cli.py` |
| `monorepo-v0.14.1/.../_ghcnh.py` | GHCNh parse | `_vendor/_ghcnh.py`, wrapped by `catalog/ghcnh.py` |
| `monorepo-v0.14.1/.../_forecast_parse.py` + `_forecast_columns.py` + `_forecast_schema.py` + `specs/*.json` | IEM MOS forecasts | `_vendor/`, wrapped by `catalog/iem.py` |
| `monorepo-v0.14.1/.../_convert.py` + `_bounds.py` | Unit conversions + range checks | `_vendor/` |
| `monorepo-v0.14.1/.../_toon.py` + `_toon_list_codec.py` | TOON serializer | `packages/core/src/tradewinds/core/formats/toon.py` |
| `monorepo-v0.14.1/.../policies_climate.py` + `pairs.py` | Merge logic + join | `research.py` Mode 1 + Phase B refactor for Mode 2 |
| mostlyright-mcp `docs/design.md` Amendments §A | Canonical schemas | `tradewinds.core.schemas.*` |
| mostlyright-mcp `docs/design.md` Amendments §D | Exception payloads | `tradewinds.core.exceptions` |
| mostlyright-mcp `docs/design.md` §"Definitions" lines 96-108 | `knowledge_time` rules per source | Each adapter's `_stamp_knowledge_time()` method |

## Open questions (not blocking start of work)

1. **Naming carryover.** Repo is `tradewinds`. Exception root is `TradewindsError`. mostlyright-mcp design used `MostlyRightMCPError`. **Resolution proposed:** keep `TradewindsError`. Document the rename in CHANGELOG; provide `MostlyRightMCPError = TradewindsError` alias in `core/exceptions.py` for one release, then remove.
2. **Mode 1 deprecation timing.** Sunset in v0.2 (warning) or v0.3 (removal)? Proposal above is "warn in v0.2, remove in v0.3" — this gives one minor cycle of overlap. Revisit at v0.2 planning.
3. **Cross-source divergence diff job** (mostlyright-mcp design Open Question 4, line 271). Numbers for `catalog_search` warnings. **Not a v0.1 blocker** — ships with `"status": "unmeasured"` placeholders. v0.1.1 follow-up.
4. **Per-source publication lag constants** (Open Question 5, line 272). Empirical calibration of `IEM_METAR_LAG`. Ships with conservative `15min` default; user-overridable per call.
5. **Should `tradewinds-markets` ship at v0.1.0 with the Kalshi contract specs only, or stay at v0.0.1 placeholder until Sprint 0.5?** Proposal: ship at `0.1.0` since the contract specs are required for `research(contract=...)` to resolve settlement sources. The API client (orderbook/fills) is what waits for Sprint 0.5.
6. **The 2 named external users.** Same gate as mostlyright-mcp design (lines 352-363). Phase B Day 14 outreach reuses the work already done in tradewinds Sprint 0 Day 4. If both say no, **Phase B still ships** — the temporal-safety + source-identity work is useful to the user personally even with zero external adopters (sunk-cost insurance clause, mostlyright-mcp design line 51).

## Bottom line

This branch keeps tradewinds' execution discipline (lanes, parity gate, cross-review, pinned lift source) and adds mostlyright-mcp's architectural spine (temporal primitives, source identity, schemas, validators). MCP server is a v0.2 deliverable with the seam already cut.

**Day 1 starts the same as tradewinds Sprint 0.** Phase B kicks off at Day 5 with the v0.14.1 parity gate already crossed. Nothing in Phase B can break Mode 1; Mode 2 is additive.

If the 60-day validation gate passes after v0.1.0, v0.2 builds the MCP server on top of an already-correct core. If it fails, the user has a substantially better local-first SDK than `mostlyright==0.14.1` for their own use, with no wasted MCP work.
