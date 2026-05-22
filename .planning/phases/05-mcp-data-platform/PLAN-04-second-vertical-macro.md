---
phase: 05-mcp-data-platform
plan: 04
type: execute
wave: 4
duration: 2-3 days Claude execution; single lane (V) for adapter build; checkpoint:decision at the start gates the entire wave
waves: 1
depends_on: [phase-05-mcp-data-platform/PLAN-03-agent-generated-connector-pipeline]
branch_strategy: per-wave; one sub-branch off `main` (`phase-5/wave-4/vertical-{macro|sports|other}`); 2-reviewer loop (codex `high` + python-architect); merges to `main` after the second-vertical query test green + the 3 new catalog entries pass the catalog-promotion-gate CI; PLAN-05 (integration + release) is the parallel sibling plan in Wave 4
requirements:
  - MCP-05    # full — multi-vertical proof; v0.2 ships weather + ONE new vertical
  - MCP-10    # PARTIAL (macro portion — 3 of 10 entries: fred.archive, alfred.archive, kalshi.macro); weather portion shipped in PLAN-02
autonomous: false   # USER_DECISION_GATE at task start — vertical choice is high-stakes and contradicts CONTEXT.md sports default; researcher recommends macro override but user owns the final call
status: VERTICAL_CHOICE_PENDING_USER_CONFIRMATION   # blocks Wave 4 until task 4.0 resolves
files_modified:
  # NEW Python distribution (parallel to packages/weather, packages/markets) — depends on vertical choice
  # IF macro confirmed: packages/macro/* (NEW)
  # IF sports overridden: packages/sports/* (NEW) — note: legal blockers per RESEARCH.md §E.1; surface to user
  # IF other: user-specified vertical at packages/<vertical>/*
  - packages/macro/pyproject.toml                                                     # CONDITIONAL on Task 4.0 decision = macro; declares tradewinds-macro==0.2.0; deps include tradewinds>=0.2.0,<0.3 + httpx + fredapi (optional convenience wrapper)
  - packages/macro/src/tradewinds_macro/__init__.py                                   # CONDITIONAL
  - packages/macro/src/tradewinds_macro/catalog/__init__.py                           # CONDITIONAL — eager-import registry: get_adapter('fred.archive') / get_adapter('alfred.archive') / get_adapter('kalshi.macro')
  - packages/macro/src/tradewinds_macro/catalog/fred.py                               # CONDITIONAL — FREDAdapter wrapping fredapi or direct httpx; SUPPORTED_SOURCES = ['fred.archive']; emits canonical schema.observation.v1-like rows (event_time, knowledge_time, source, retrieved_at, value, series_id, ...)
  - packages/macro/src/tradewinds_macro/catalog/alfred.py                             # CONDITIONAL — ALFREDAdapter for vintage-aware fetches; SUPPORTED_SOURCES = ['alfred.archive']
  - packages/macro/src/tradewinds_macro/catalog/kalshi_macro.py                       # CONDITIONAL — KalshiMacroContractSpec; resolves CPI / Core-CPI / PCE / Core-PCE / payrolls / Fed-funds / unemployment-rate contract IDs to settlement source (BLS / BEA / Fed direct)
  - packages/macro/tests/__init__.py                                                  # CONDITIONAL
  - packages/macro/tests/test_fred_adapter.py                                         # CONDITIONAL — recorded-fixture tests (pytest-recording / VCR.py) for fred.archive
  - packages/macro/tests/test_alfred_adapter.py                                       # CONDITIONAL — vintage-aware fetch test (verifies knowledge_time = realtime_start)
  - packages/macro/tests/test_kalshi_macro_specs.py                                   # CONDITIONAL — contract spec resolution; every supported ticker maps to a known settlement source
  # NEW catalog entries (MCP-10 macro portion)
  - packages/mcp/catalog/_generated/fred.archive.yaml                                 # NEW — generated via scaffold + PR; promoted to packages/mcp/catalog/fred.archive.yaml after gate
  - packages/mcp/catalog/_generated/alfred.archive.yaml                               # NEW — same workflow
  - packages/mcp/catalog/_generated/kalshi.macro.yaml                                 # NEW — same workflow
  # After Task 4.5 promotion (file moves):
  - packages/mcp/catalog/fred.archive.yaml                                            # PROMOTED — final destination after CI gate green
  - packages/mcp/catalog/alfred.archive.yaml                                          # PROMOTED
  - packages/mcp/catalog/kalshi.macro.yaml                                            # PROMOTED
  # MCP adapter bridge extension
  - packages/mcp/src/tradewinds_mcp/_adapter_bridge.py                                # MODIFY — dispatch fred./alfred./kalshi.macro source IDs to tradewinds_macro.catalog.get_adapter (alongside existing weather dispatch)
  # Tests for the bridge extension
  - packages/mcp/tests/test_adapter_bridge_macro_dispatch.py                          # NEW — bridge.fetch(entry) for fred.archive dispatches to tradewinds_macro adapter; kalshi.macro raises "use markets module directly" like kalshi.weather
must_haves:
  truths:
    - "**USER_DECISION_GATE resolved BEFORE adapter/catalog work begins.** User has explicitly confirmed one of: (a) macro indicators per RESEARCH.md §E researcher recommendation, (b) sports prediction markets — overriding the 2026 legal-blocker finding with the user's risk acceptance, or (c) another vertical (user-specified). The decision is recorded in `.planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md`."
    - "If macro chosen: `packages/macro/` distribution exists; `tradewinds_macro.catalog.get_adapter('fred.archive')` returns a FREDAdapter; `get_adapter('alfred.archive')` returns an ALFREDAdapter; `get_adapter('kalshi.macro')` returns a contract spec resolver."
    - "If macro chosen: `FREDAdapter.fetch(series_id='CPIAUCSL', start=..., end=..., as_of=...)` returns a `pd.DataFrame` with canonical columns (event_time, knowledge_time, source='fred.archive', retrieved_at, value, series_id). For non-vintage-aware FRED, knowledge_time defaults to event_time + FRED publish-delay per series (documented per series in the catalog entry); for vintage-aware ALFRED, knowledge_time = `realtime_start` (the natural vintage primitive per RESEARCH.md §E.2)."
    - "If macro chosen: `ALFREDAdapter.fetch(...)` honors vintage semantics — same `as_of` produces the same row set (deterministic replay; RESEARCH.md §I.7 pitfall mitigated: dedup logic uses `realtime_start <= as_of`)."
    - "If macro chosen: 3 catalog YAML files (`fred.archive.yaml`, `alfred.archive.yaml`, `kalshi.macro.yaml`) exist FIRST in `packages/mcp/catalog/_generated/`, pass the `catalog-promotion-gate` CI workflow (validator green; sample-data live test green when run manually), then are PROMOTED to `packages/mcp/catalog/` root via `promote_generated_entry.py --execute`."
    - "If macro chosen: `alfred.archive.yaml` declares `vintage_aware: true` AND `knowledge_time_formula` cites `realtime_start` (the field that maps event_time→knowledge_time for vintage data); `temporal_rules.backfill_behavior` documents that ALFRED maintains historical vintages without overwriting (RESEARCH.md §E.2)."
    - "If macro chosen: `kalshi.macro.yaml` declares status=live; references KALSHI_MACRO_SETTLEMENT_SOURCES dict in tradewinds_macro.catalog.kalshi_macro (analogous to Phase 2's KALSHI_SETTLEMENT_STATIONS); quality_notes cite the Fed working paper (RESEARCH.md §E.2 citation `federalreserve.gov/econres/feds/files/2026010pap.pdf`); operational_context.auth = 'api_key:KALSHI_API_KEY' (matching Phase 2 pattern)."
    - "`packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` modified to dispatch `fred.*` and `alfred.*` source IDs to `tradewinds_macro.catalog.get_adapter`; falls back to weather dispatch for non-macro source IDs. `kalshi.macro` raises `SourceUnavailableError` with the 'use markets module directly' message (consistent with kalshi.weather behavior in PLAN-02)."
    - "After promotion: `from tradewinds_mcp.catalog import CatalogLoader; loader = CatalogLoader.from_dir('packages/mcp/catalog/'); len(loader) == 10` — the MCP-10 commitment delivered (7 weather + 3 macro)."
    - "RESEARCH.md §I.7 pitfall (ALFRED inflated row counts when source backfills) mitigated: `ALFREDAdapter.fetch(..., as_of=...)` filters `realtime_start <= as_of` BEFORE returning; same `as_of` produces same row count + same hash; tested in `test_alfred_adapter.py`."
    - "If macro chosen + FRED_API_KEY not set: `FREDAdapter` raises `SourceUnavailableError` with the registration URL `https://fred.stlouisfed.org/docs/api/api_key.html` — mirrors Phase 3 `pip install tradewinds-weather` pattern per RESEARCH.md §E.4 'Environment Availability'."
    - "Full MCP suite green: `uv run pytest packages/mcp/tests/ packages/macro/tests/ -m 'not live' -q` exits 0 (Wave 1+2+3 tests + new Wave 4 tests; macro adapter tests use recorded fixtures via pytest-recording per CLAUDE.md tech-stack research)."
    - "Pre-commit + pre-push hooks green (no `--no-verify`)."
  artifacts:
    - path: .planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md
      provides: "User-confirmed decision: which vertical, rationale, any deviation from RESEARCH.md §E recommendation, risk acceptance for sports if chosen"
      contains: "Vertical:"
    - path: packages/macro/pyproject.toml
      provides: "tradewinds-macro PyPI distribution; Requires-Dist tradewinds>=0.2.0,<0.3 + httpx + (optional) fredapi"
      contains: "name = \"tradewinds-macro\""
    - path: packages/macro/src/tradewinds_macro/catalog/__init__.py
      provides: "Eager-import registry: get_adapter('fred.archive') / get_adapter('alfred.archive') / get_adapter('kalshi.macro')"
      contains: "def get_adapter"
    - path: packages/macro/src/tradewinds_macro/catalog/fred.py
      provides: "FREDAdapter wrapping fred.stlouisfed.org/fred/series/observations; emits canonical schema.observation.v1-like rows"
      contains: "class FREDAdapter"
      min_lines: 60
    - path: packages/macro/src/tradewinds_macro/catalog/alfred.py
      provides: "ALFREDAdapter for vintage-aware fetches; knowledge_time = realtime_start; dedup by (date, realtime_start <= as_of)"
      contains: "class ALFREDAdapter"
      min_lines: 60
    - path: packages/macro/src/tradewinds_macro/catalog/kalshi_macro.py
      provides: "KalshiMacroContractSpec + KALSHI_MACRO_SETTLEMENT_SOURCES dict (CPI/PCE/payrolls/Fed-funds → settlement source)"
      contains: "KALSHI_MACRO_SETTLEMENT_SOURCES"
    - path: packages/mcp/catalog/fred.archive.yaml
      provides: "FRED catalog entry — schema.observation.v1, status: live, knowledge_time_formula documents FRED publish-delay per series"
      contains: "source_id: fred.archive"
    - path: packages/mcp/catalog/alfred.archive.yaml
      provides: "ALFRED catalog entry — vintage_aware: true; knowledge_time_formula: 'realtime_start' (vintage primitive per RESEARCH.md §E.2)"
      contains: "vintage_aware: true"
    - path: packages/mcp/catalog/kalshi.macro.yaml
      provides: "Kalshi macro contract spec catalog entry; status: live; references KALSHI_MACRO_SETTLEMENT_SOURCES + Fed working paper"
      contains: "federalreserve.gov"
  key_links:
    - from: packages/mcp/src/tradewinds_mcp/_adapter_bridge.py
      to: packages/macro/src/tradewinds_macro/catalog/__init__.py
      via: "bridge dispatches fred./alfred./kalshi.macro source IDs to tradewinds_macro.catalog.get_adapter; kalshi.macro raises like kalshi.weather"
      pattern: "from tradewinds_macro\\.catalog import get_adapter"
    - from: packages/macro/src/tradewinds_macro/catalog/alfred.py
      to: "realtime_start <= as_of"
      via: "vintage dedup using realtime_start; RESEARCH.md §I.7 mitigation"
      pattern: "realtime_start.*<=.*as_of"
    - from: packages/mcp/catalog/fred.archive.yaml
      to: tradewinds_macro.catalog.get_adapter('fred.archive')
      via: "extraction_config.adapter: fred.archive; adapter_resolves check passes"
      pattern: "adapter: fred.archive"
    - from: packages/mcp/catalog/_generated/fred.archive.yaml
      to: packages/mcp/catalog/fred.archive.yaml
      via: "promote_generated_entry.py --execute moves the file after catalog-promotion-gate CI green + manual live test green"
      pattern: "fred.archive.yaml"
---

<objective>
**Wave 4a — Second vertical adapter (macro recommended; user decides).**

This plan delivers tradewinds' first non-weather vertical, proving the multi-vertical thesis (MCP-05) and completing the MCP-10 commitment (10 pre-indexed catalog entries: 7 weather from PLAN-02 + 3 macro from this plan).

**Task 4.0 is a hard `[USER_DECISION_GATE]` checkpoint:** the second-vertical choice is HIGH-STAKES per CONTEXT.md (researcher OVERRIDE of the initial "sports" recommendation based on 2026 legal evidence — RESEARCH.md §E.1). The default recommendation is **macroeconomic indicators (FRED + ALFRED → Kalshi macro contracts)** per RESEARCH.md §E.2. Wave 4 work CANNOT BEGIN until the user confirms.

**Three reasons the gate is structural:**
1. Phases 1-3 are vertical-agnostic — server skeleton, catalog format, agent-connector pipeline — all work for any second vertical.
2. The specific adapter code, catalog YAML content, and example contracts are vertical-specific. Wrong choice here = days of throwaway work.
3. The user's brief originally said "sports prediction markets, horse racing, etc." — RESEARCH.md §E found this is no longer viable in 2026. Honoring the user's lock requires explicit confirmation OR explicit override.

**If macro confirmed (default — researcher recommendation):**
- New `packages/macro/` PyPI distribution at `tradewinds-macro==0.2.0`.
- `FREDAdapter` wrapping the FRED API (CPIAUCSL / PAYEMS / DFF / UNRATE / PCE / CORECPI / CORECPI / FEDFUNDS series).
- `ALFREDAdapter` for vintage-aware fetches (knowledge_time = realtime_start — the natural vintage primitive that maps 1:1 to tradewinds' temporal-safety contract).
- `KalshiMacroContractSpec` for CPI / PCE / payrolls / Fed-funds Kalshi markets (analogous to Phase 2 Kalshi NHIGH/NLOW weather specs).
- 3 new MCP catalog entries (`fred.archive`, `alfred.archive`, `kalshi.macro`), going through the Wave 3 agent-connector pipeline: scaffold → fill in 5 layers → local validate → PR → catalog-promotion-gate CI → manual sample-data live test → maintainer promotes.

**If sports overridden (user accepts legal-blocker risk):**
- New `packages/sports/` PyPI distribution.
- Adapter for whichever sports source the user picks (Sportradar, ESPN public API, or Polymarket if user signs the exclusive-deal acknowledgment).
- Catalog entries for the chosen contracts.
- This path is documented but NOT detailed in this plan — if the user goes here, planner does a quick follow-up to fill in sports-specific adapter requirements.

**If other (user-specified):**
- The structure is the same: new `packages/<vertical>/` distribution; adapters in `packages/<vertical>/src/tradewinds_<vertical>/`; 1-3 MCP catalog entries via Wave 3 pipeline.

**Key invariants honored regardless of choice:**
- RESEARCH.md §H.3: `packages/mcp/` MUST depend on the new vertical's PUBLIC catalog registry only, not internal fetcher paths. `_adapter_bridge` extension follows the same pattern as Phase 2 weather dispatch.
- Wave 3 pipeline used end-to-end: catalog entries start in `_generated/`, pass CI gate, get promoted. Demonstrates the pipeline works on real (not example-fixture) data.
- Deterministic replay (MCP-09) still applies — vintage-aware sources need careful knowledge_time formulas; PLAN-05 runs the full replay test suite over the second vertical's queries.

**Out of scope (deferred to PLAN-05):**
- End-to-end JSON-RPC subprocess integration tests.
- Deterministic-replay test running across both verticals.
- v0.2.0 release prep (CHANGELOG, version bump, trusted publishing rehearsal).

**Output:** A second-vertical adapter + 3 promoted catalog entries. The MCP server now exposes 10 source IDs across 2 verticals. PLAN-05 wraps everything in integration tests and ships v0.2.0.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/05-mcp-data-platform/CONTEXT.md
@.planning/phases/05-mcp-data-platform/RESEARCH.md
@.planning/phases/05-mcp-data-platform/05-03-SUMMARY.md
@./CLAUDE.md
</execution_context>

<interfaces>
From Wave 3 (PLAN-03 output — pipeline that this plan USES):

```python
# tradewinds_mcp._generated_scaffold.scaffold_catalog_entry(source_id, api_doc_url=None) -> dict
# tradewinds_mcp._generated_validator.validate_generated_entry(path: Path) -> ValidationReport
# packages/mcp/scripts/promote_generated_entry.py --dry-run | --execute
# .github/workflows/catalog-promotion-gate.yml — runs on PRs touching catalog YAMLs
```

From Wave 2 (PLAN-02 output — `_adapter_bridge` is extended here):

```python
# tradewinds_mcp._adapter_bridge.AdapterBridge
#   .fetch(entry: CatalogEntry, filters) -> pd.DataFrame   # dispatches to Phase 2 weather adapters
#   ._resolve_adapter(adapter_id: str) -> WeatherAdapter
# This plan extends _resolve_adapter to dispatch fred.* / alfred.* / kalshi.macro to tradewinds_macro
```

From CLAUDE.md tech stack:
- `httpx>=0.28,<1.0` for the FRED/ALFRED HTTP client (already in v0.1 deps via tradewinds-weather)
- `pytest-recording>=0.13.4` for VCR-style recorded fixtures (already in v0.1 dev deps)
- Optional `fredapi>=0.5.0` Python wrapper — convenient but the adapter can use direct httpx (RESEARCH.md "Environment Availability" calls this out as optional with a ~50 LOC fallback)

FRED API:
- Base URL: `https://api.stlouisfed.org/fred/`
- Required: `FRED_API_KEY` env var; registration at `https://fred.stlouisfed.org/docs/api/api_key.html` (free, 32-char string)
- Rate limit: 120 req/60sec per API key (documented)
- Series IDs: `CPIAUCSL` (CPI All Urban Consumers), `CORECPI` (Core CPI), `PCEPI` (PCE Price Index), `CORE PCE` (`PCEPILFE`), `PAYEMS` (Total Nonfarm Payrolls), `DFF` (Federal Funds Effective Rate), `UNRATE` (Unemployment Rate)

ALFRED API (sibling to FRED for vintage data):
- Same base URL family; vintage-aware endpoints like `/fred/series/observations` with `realtime_start` + `realtime_end` params
- Each observation has `(date, realtime_start, realtime_end, value)` — `realtime_start` = when the value became knowable (THIS IS THE NATIVE TEMPORAL-SAFETY PRIMITIVE)
</interfaces>

<phase_summary>

**Goal:** Decide the second vertical (USER_DECISION_GATE), then ship the adapter + 3 catalog entries via the Wave 3 pipeline.

**Branch:** `phase-5/wave-4/vertical-{macro|sports|other}` off `main` (name finalized after Task 4.0).

**Atomic commit boundaries (assuming macro chosen):**
- Task 4.0 (USER_DECISION_GATE + decision record) → 1 commit (.planning/.../05-04-VERTICAL-DECISION.md)
- Task 4.1 (packages/macro scaffold + FREDAdapter) → 2 commits (RED + GREEN)
- Task 4.2 (ALFREDAdapter + vintage dedup) → 2 commits
- Task 4.3 (KalshiMacroContractSpec) → 2 commits
- Task 4.4 (3 _generated/ catalog YAML entries) → 1 commit
- Task 4.5 (promotion via CLI + verify MCP server sees 10 entries + _adapter_bridge extension) → 2 commits
- Task 4.6 (pre-merge gate) → 1 commit

**2-reviewer loop:** codex `high` + python-architect. Never-skip applies (new package distribution; catalog YAML schema-fragment-bearing; macro contract spec — wrong settlement source = silent corruption analogous to Phase 2 KALSHI_SETTLEMENT_STATIONS).

**Pre-merge gate:**
1. All MCP + macro tests green.
2. 3 macro catalog entries promoted (in `packages/mcp/catalog/`, not `_generated/`).
3. `CatalogLoader.from_dir('packages/mcp/catalog/')` returns 10 entries.
4. `query('fred.archive', as_of=..., filters={'series_id':'CPIAUCSL'})` works in-process (recorded fixture).
5. `query('alfred.archive', as_of=...)` deterministic — same call, same hash (preview for PLAN-05 replay tests).
6. `kalshi.macro` query raises with the documented "use markets module directly" message.
7. `uv build packages/macro/` produces a wheel with no `tradewinds/__init__.py` collision.
8. Pre-commit + pre-push hooks green.
9. 2-reviewer loop PASS x2.

</phase_summary>

<tasks>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 4.0: [USER_DECISION_GATE] Second-vertical choice — confirm or override</name>
  <files>.planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md (NEW after user input)</files>
  <implements>RESEARCH.md §E vertical recommendation; CONTEXT.md "MUST NOT silently choose"; original brief language honored via explicit confirmation</implements>
  <read_first>
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§E full section — 2026 sports legal landscape, macro rationale, top-10 entries)
    - .planning/phases/05-mcp-data-platform/CONTEXT.md (decisions — "Multi-vertical proof — second-vertical SELECTION is a user-owned decision")
    - .planning/REQUIREMENTS.md (line 242 — MCP-05: "Multi-vertical catalog expansion: v0.2 = weather + MCP server; v0.3 = sports prediction markets; v0.4 = politics + finance" — sports was the initial v0.3 target; researcher recommends macro as v0.2 second vertical with sports deferred to v0.3+)
  </read_first>
  <decision>
    **Which vertical ships as the v0.2 second vertical, alongside weather?**
  </decision>
  <context>
    The original product brief language was "sports prediction markets, horse racing, etc." Researcher's 2026 finding (RESEARCH.md §E.1) is that this is NOT VIABLE in 2026:

    - **Horse racing**: federally blocked from prediction markets as of May 2026 (Interstate Horseracing Act §3001 et seq.; tested in TVG v. Kalshi 2026).
    - **NFL/NBA**: active litigation. NJ injunction in place; NM tribes won motion to enjoin May 2026; appeals pending.
    - **MLB**: Polymarket signed exclusive deal March 2026; tradewinds would be a downstream consumer in a market with a single licensed primary.

    **Researcher recommendation (RESEARCH.md §E.2):** macroeconomic indicators (FRED + ALFRED → Kalshi CPI / PCE / payrolls / Fed-funds contracts). Reasons:
    1. Data is free, public, well-documented (FRED + ALFRED APIs from St. Louis Fed).
    2. ALFRED's vintage API is a native `(event_time, knowledge_time)` primitive — maps 1:1 to tradewinds' temporal safety.
    3. Kalshi macro markets are CFTC-blessed; multi-year operational history.
    4. Fed working paper documents Kalshi macro markets as quant-grade.
    5. Smallest adapter effort (FRED + ALFRED share HTTP base; one combined package).
    6. No legal exposure.

    **Counter-arguments to consider:**
    - Sports has bigger consumer audience. Macro is quant-narrow. tradewinds' v0.1 audience is quants (per PROJECT.md), but sports broadens the funnel.
    - Sports might unlock in late 2026 if NJ appeal succeeds or new federal framework emerges.
    - User may have a specific vertical not on either list.
  </context>
  <options>
    <option id="macro">
      <name>Macroeconomic indicators (FRED + ALFRED + Kalshi macro)</name>
      <pros>
        - Researcher's recommendation. Lowest risk path.
        - Vintage-aware data (ALFRED `realtime_start`) is a perfect match for tradewinds' temporal safety thesis.
        - No legal exposure.
        - Smallest adapter scope (1 combined `tradewinds-macro` package).
        - Strong quant-audience signal — Kalshi macro markets are real, liquid, and have a multi-year track record per Fed research.
      </pros>
      <cons>
        - Narrower audience than sports.
        - Doesn't match the brief's "sports prediction markets, horse racing" language — explicit override.
      </cons>
    </option>
    <option id="sports">
      <name>Sports prediction markets (sports-specific vendor TBD — Sportradar / ESPN / Polymarket)</name>
      <pros>
        - Matches original brief language.
        - Broader consumer audience; tradewinds visibility wins.
      </pros>
      <cons>
        - **2026 legal landscape blocks the most natural targets** (horse racing federally blocked; NFL/NBA in active litigation; MLB exclusive to Polymarket).
        - Data rights cost: Sportradar is paid; ESPN public API is rate-limited and not contract-resolution-grade.
        - Settlement source ambiguity — sports outcomes can be disputed (overturns, suspensions, postponements) in ways macro indicators are not.
        - **Risk acceptance required** — if user picks this, document the legal-blocker awareness in the decision file.
      </cons>
    </option>
    <option id="other">
      <name>Other (user-specified)</name>
      <pros>
        - User-defined.
      </pros>
      <cons>
        - Requires user to specify the vertical, data source(s), and contract market.
        - Planner will need to do a quick follow-up to flesh out the specific adapter requirements before Task 4.1 begins.
      </cons>
    </option>
    <option id="defer">
      <name>Defer v0.2 second vertical entirely; ship v0.2 as weather-only + MCP server</name>
      <pros>
        - Ships v0.2 faster — skip Wave 4 adapter work; PLAN-05 still runs integration tests + release.
        - MCP-05 (multi-vertical proof) deferred to v0.3.
        - Re-evaluate 2026-2027 legal landscape before committing.
      </pros>
      <cons>
        - **Violates MCP-05 requirement** as stated. Requires REQUIREMENTS.md amendment to soften the requirement (e.g., "MCP-05: multi-vertical FRAMEWORK in v0.2; first new vertical in v0.3").
        - User may want to fast-track the macro vertical anyway given researcher's positive ROI assessment.
      </cons>
    </option>
  </options>
  <resume-signal>
    Type one of:
    - `macro` (researcher recommendation; default; lowest risk)
    - `sports` (override researcher's legal finding; specify which sport / vendor; risk acceptance recorded)
    - `other:<vertical-name>` (e.g., `other:fixed-income` or `other:supply-chain`)
    - `defer` (skip second vertical in v0.2; requires REQUIREMENTS.md amendment to MCP-05)

    Whatever the choice, the planner will create `.planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md` documenting the decision + rationale + any deviations from RESEARCH.md.
  </resume-signal>
</task>

<task type="auto" tdd="true">
  <name>Task 4.1: packages/macro/ scaffold + FREDAdapter (CONDITIONAL on Task 4.0 = macro; RED tests FIRST)</name>
  <files>packages/macro/pyproject.toml, packages/macro/README.md, packages/macro/src/tradewinds_macro/__init__.py, packages/macro/src/tradewinds_macro/catalog/__init__.py, packages/macro/src/tradewinds_macro/catalog/fred.py, packages/macro/tests/__init__.py, packages/macro/tests/test_fred_adapter.py, packages/macro/tests/conftest.py</files>
  <implements>MCP-05 (multi-vertical foundation), MCP-10 (fred.archive component)</implements>
  <conditional>If Task 4.0 resolved to `sports` or `other`, planner re-scopes this task to `packages/sports/` or `packages/<vertical>/` with vertical-specific adapter requirements. The structure below assumes macro.</conditional>
  <read_first>
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§E.2 — FRED API rationale; series IDs CPIAUCSL/CORECPI/PCEPI/CORE PCE/PAYEMS/DFF/UNRATE; §I.4 hallucination mitigation; §I.7 — vintage backfill pitfall — ONLY ALFRED is vintage-aware; FRED is one-shot publish)
    - Task 4.0 output (.planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md)
    - .planning/phases/01-v0-14-1-parity-lift/PLAN.md (Wave 1 — pyproject.toml + hatch build pattern for tradewinds-* packages; sibling-package layout under packages/<name>/src/tradewinds_<name>/)
    - .planning/phases/02-core-primitives-catalog-adapters/PLAN.md (Wave 3 — WeatherAdapter Protocol + eager registry pattern; mirror this for macro adapters)
    - packages/weather/src/tradewinds/weather/catalog/__init__.py (existing — confirm registry structure to mirror)
    - CLAUDE.md (pytest-recording for VCR; httpx for HTTP; ≥80% line coverage on adapter wrappers)
  </read_first>
  <behavior>
    Tests in `packages/macro/tests/test_fred_adapter.py` (8 tests; use pytest-recording cassettes for FRED API responses):

    1. `test_fred_adapter_requires_api_key_env_var`: with `FRED_API_KEY` unset, `FREDAdapter().fetch(series_id='CPIAUCSL', start=date(2024,1,1), end=date(2024,12,31))` raises `SourceUnavailableError` whose message contains the registration URL `https://fred.stlouisfed.org/docs/api/api_key.html`.
    2. `test_fred_adapter_supported_sources`: `FREDAdapter.SUPPORTED_SOURCES == ['fred.archive']` (class attribute per Phase 2 CATALOG-05 convention).
    3. `test_fred_adapter_fetch_cpi_recorded`: with cassette `tests/cassettes/test_fred_cpi.yaml`, `FREDAdapter().fetch(series_id='CPIAUCSL', start=date(2024,1,1), end=date(2024,3,31))` returns a DataFrame with at least 3 rows (Jan/Feb/Mar CPI), canonical columns `event_time` (date of observation), `knowledge_time` (event_time + FRED publish-delay — per-series; CPI is BLS-released ~2 weeks after month-end), `source='fred.archive'`, `retrieved_at`, `value`, `series_id`.
    4. `test_fred_adapter_knowledge_time_lags_event_time`: for every row, `knowledge_time > event_time` (BLS releases lag the observation period). Document delays in the catalog YAML per series.
    5. `test_fred_adapter_value_is_float`: result `df['value'].dtype` is float64 (or Float64 nullable).
    6. `test_fred_adapter_session_reused`: `FREDAdapter` reuses an `httpx.Client` across calls (mock the client; assert 2 calls = 1 client construction).
    7. `test_fred_adapter_rate_limit_documented`: the adapter docstring documents the 120 req/60sec rate limit; in v0.2 we don't actively rate-limit but the operational_context YAML will record it.
    8. `test_fred_adapter_emits_canonical_observation_v1_columns`: result columns include all required `schema.observation.v1` columns (event_time, knowledge_time, source, retrieved_at) per Phase 2 schema definition.

    Use `pytest-recording` cassettes (`@pytest.mark.vcr`) to capture real FRED API responses; cassettes stored at `packages/macro/tests/cassettes/`. Filter the `api_key` query parameter via VCR config (don't commit secrets — per CLAUDE.md tech-stack research VCR cassette filter pattern).

    Run `uv run pytest packages/macro/tests/test_fred_adapter.py -x` — MUST fail (no FREDAdapter yet). Commit RED.
  </behavior>
  <action>
    Step 1 — Create `packages/macro/pyproject.toml`:

    ```toml
    [build-system]
    requires = ["hatchling>=1.27"]
    build-backend = "hatchling.build"

    [project]
    name = "tradewinds-macro"
    version = "0.2.0"
    description = "Macroeconomic indicator adapters for tradewinds — FRED + ALFRED + Kalshi macro contract specs"
    readme = "README.md"
    license = "MIT"
    requires-python = ">=3.11"
    authors = [{ name = "tradewinds maintainers" }]
    classifiers = [
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering",
    ]
    dependencies = [
        "tradewinds>=0.2.0,<0.3",
        "httpx>=0.28,<1.0",
        "pandas>=2.2,<3.0",  # match Phase 1 floor
    ]

    [project.optional-dependencies]
    fredapi = ["fredapi>=0.5.0"]  # convenience wrapper; adapter works without it via direct httpx

    [project.urls]
    Homepage = "https://github.com/Tarabcak/tradewinds"
    Repository = "https://github.com/Tarabcak/tradewinds"

    [tool.hatch.build.targets.wheel]
    packages = ["src/tradewinds_macro"]
    ```

    Step 2 — Create `packages/macro/src/tradewinds_macro/__init__.py`:

    ```python
    """tradewinds-macro — macroeconomic indicator adapters for the tradewinds data platform."""
    __version__ = "0.2.0"
    ```

    Step 3 — Create `packages/macro/src/tradewinds_macro/catalog/__init__.py` with the eager registry pattern (mirror Phase 2 weather):

    ```python
    """Macro adapter registry (eager import); get_adapter(source_id) dispatches."""

    from __future__ import annotations

    from typing import Protocol

    from tradewinds.core.exceptions import SourceUnavailableError

    from .fred import FREDAdapter
    from .alfred import ALFREDAdapter  # Task 4.2
    from .kalshi_macro import KalshiMacroContractSpec  # Task 4.3

    __all__ = ["get_adapter", "MacroAdapter", "FREDAdapter", "ALFREDAdapter", "KalshiMacroContractSpec"]


    class MacroAdapter(Protocol):
        SUPPORTED_SOURCES: list[str]
        def fetch(self, **kwargs): ...


    _REGISTRY: dict[str, MacroAdapter] = {
        "fred.archive": FREDAdapter(),
        "alfred.archive": ALFREDAdapter(),
        "kalshi.macro": KalshiMacroContractSpec(),  # contract spec; returns 1-row DataFrame on resolve
    }


    def get_adapter(source_id: str) -> MacroAdapter:
        if source_id not in _REGISTRY:
            raise SourceUnavailableError(
                f"Unknown macro source_id '{source_id}'. Available: {sorted(_REGISTRY.keys())}"
            )
        return _REGISTRY[source_id]
    ```

    Step 4 — Implement `packages/macro/src/tradewinds_macro/catalog/fred.py`:

    ```python
    """FREDAdapter — wraps FRED API for one-shot economic indicators.

    NOT vintage-aware. For vintage data (knowledge_time = realtime_start), use ALFREDAdapter.

    Series IDs supported in v0.2:
      - CPIAUCSL: Consumer Price Index for All Urban Consumers
      - CORECPI: Core CPI (excl. food + energy)
      - PCEPI: PCE Price Index
      - PCEPILFE: Core PCE Price Index
      - PAYEMS: Total Nonfarm Payrolls
      - DFF: Federal Funds Effective Rate (daily)
      - UNRATE: Unemployment Rate
    """

    from __future__ import annotations

    import os
    from datetime import date, datetime, timezone, timedelta
    from typing import ClassVar

    import httpx
    import pandas as pd

    from tradewinds.core.exceptions import SourceUnavailableError

    __all__ = ["FREDAdapter"]

    _FRED_BASE = "https://api.stlouisfed.org/fred"

    # Per-series publish delay (event_time → knowledge_time): documented from BLS/BEA/Fed release calendars
    # These are CONSERVATIVE upper bounds. Catalog YAML quality_notes will reference the live calendars.
    _PUBLISH_DELAYS: dict[str, timedelta] = {
        "CPIAUCSL": timedelta(days=15),       # BLS CPI: released ~mid-month for prior month
        "CORECPI": timedelta(days=15),
        "PCEPI": timedelta(days=30),          # BEA PCE: released ~1 month after observation period
        "PCEPILFE": timedelta(days=30),
        "PAYEMS": timedelta(days=7),          # BLS jobs report: first Friday of following month
        "DFF": timedelta(days=1),             # Fed Funds: published next business day
        "UNRATE": timedelta(days=7),
    }


    class FREDAdapter:
        SUPPORTED_SOURCES: ClassVar[list[str]] = ["fred.archive"]

        def __init__(self, client: httpx.Client | None = None) -> None:
            self._client = client  # lazy-init in fetch()

        def _get_client(self) -> httpx.Client:
            if self._client is None:
                self._client = httpx.Client(timeout=60.0)  # matches Phase 1.5 HTTP_TIMEOUT
            return self._client

        def fetch(
            self,
            *,
            series_id: str,
            start: date,
            end: date,
            as_of: datetime | None = None,
        ) -> pd.DataFrame:
            """Fetch a FRED series. Returns canonical schema.observation.v1-shaped rows.

            FRED is NOT vintage-aware; knowledge_time = event_time + publish_delay[series_id].
            For vintage data, use ALFREDAdapter.
            """
            api_key = os.environ.get("FRED_API_KEY")
            if not api_key:
                raise SourceUnavailableError(
                    "FRED_API_KEY environment variable is not set. "
                    "Register a free API key at https://fred.stlouisfed.org/docs/api/api_key.html "
                    "and export FRED_API_KEY=<32-char-string>."
                )

            url = f"{_FRED_BASE}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
            }
            resp = self._get_client().get(url, params=params)
            resp.raise_for_status()
            observations = resp.json().get("observations", [])
            now_utc = datetime.now(timezone.utc)
            delay = _PUBLISH_DELAYS.get(series_id, timedelta(days=15))
            rows = []
            for obs in observations:
                event_dt = datetime.fromisoformat(obs["date"]).replace(tzinfo=timezone.utc)
                rows.append({
                    "event_time": event_dt,
                    "knowledge_time": event_dt + delay,
                    "source": "fred.archive",
                    "retrieved_at": now_utc,
                    "series_id": series_id,
                    "value": float(obs["value"]) if obs["value"] not in (".", "") else None,
                })
            df = pd.DataFrame(rows)
            # Phase 2 schema convention: dtypes
            if not df.empty:
                df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
                df["knowledge_time"] = pd.to_datetime(df["knowledge_time"], utc=True)
                df["retrieved_at"] = pd.to_datetime(df["retrieved_at"], utc=True)
                df["value"] = df["value"].astype("Float64")
            return df

        def close(self) -> None:
            if self._client is not None:
                self._client.close()
    ```

    Step 5 — Create `packages/macro/tests/conftest.py` for VCR configuration:

    ```python
    """pytest-recording config for FRED/ALFRED cassettes."""

    import pytest


    @pytest.fixture(scope="module")
    def vcr_config():
        return {
            "filter_query_parameters": [("api_key", "REDACTED_API_KEY")],
            "record_mode": "once",  # record on first run, replay thereafter
        }
    ```

    Step 6 — Write the 8 tests from `<behavior>`. Use `@pytest.mark.vcr` decorator on tests that hit the real API; the first run requires `FRED_API_KEY` set; subsequent runs replay from cassette.

    Step 7 — Capture cassettes ONCE locally (developer environment): `FRED_API_KEY=<key> uv run pytest packages/macro/tests/test_fred_adapter.py -v --record-mode=once`. Commit the cassettes under `packages/macro/tests/cassettes/` (api_key already filtered). After cassettes exist, the tests run offline in CI.

    Step 8 — Build the wheel: `uv build packages/macro/`. Verify with `unzip -l packages/macro/dist/tradewinds_macro-0.2.0-py3-none-any.whl`. Expected: `tradewinds_macro/__init__.py`, `tradewinds_macro/catalog/fred.py`, etc. NO `tradewinds/__init__.py` (sibling-package layout per PKG-02).

    Step 9 — Run `uv run pytest packages/macro/tests/test_fred_adapter.py -m "not live" -x -v`. With cassettes in place, all 8 tests pass.

    Step 10 — Commit (GREEN): `feat(phase-5): packages/macro + FREDAdapter (MCP-05 + MCP-10 fred.archive)`.
  </action>
  <verify>
    <automated>uv build packages/macro/ && unzip -l packages/macro/dist/tradewinds_macro-0.2.0-py3-none-any.whl | grep -c "tradewinds_macro/" | awk '$1 >= 3 {exit 0} {exit 1}' && (unzip -l packages/macro/dist/tradewinds_macro-0.2.0-py3-none-any.whl | grep "^.*tradewinds/__init__.py$" && exit 1 || exit 0) && uv run pytest packages/macro/tests/test_fred_adapter.py -m "not live" -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/macro/pyproject.toml` returns 0
    - `grep 'name = "tradewinds-macro"' packages/macro/pyproject.toml` non-empty
    - `grep 'tradewinds>=0.2.0,<0.3' packages/macro/pyproject.toml` non-empty
    - `test -f packages/macro/src/tradewinds_macro/catalog/fred.py` returns 0
    - `grep -c "class FREDAdapter" packages/macro/src/tradewinds_macro/catalog/fred.py` returns 1
    - `grep -c "SUPPORTED_SOURCES" packages/macro/src/tradewinds_macro/catalog/fred.py` returns 1
    - `grep -c "FRED_API_KEY" packages/macro/src/tradewinds_macro/catalog/fred.py` returns ≥ 1
    - `grep -c "raise SourceUnavailableError" packages/macro/src/tradewinds_macro/catalog/fred.py` returns ≥ 1
    - `grep -c "fred.stlouisfed.org/docs/api/api_key.html" packages/macro/src/tradewinds_macro/catalog/fred.py` returns 1 (registration URL in error)
    - `grep -c "_PUBLISH_DELAYS" packages/macro/src/tradewinds_macro/catalog/fred.py` returns ≥ 1
    - `uv build packages/macro/` exits 0 and produces wheel
    - Wheel does NOT contain `tradewinds/__init__.py` (PKG-02 compliance)
    - `uv run pytest packages/macro/tests/test_fred_adapter.py -x -v` exits 0 with 8 passed (cassettes in place)
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    `packages/macro/` distribution exists; FREDAdapter wraps FRED API with API-key registration error path; emits canonical observation columns + per-series publish-delay knowledge_time. 8 tests pass (recorded fixtures).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 4.2: ALFREDAdapter — vintage-aware (RED tests FIRST)</name>
  <files>packages/macro/src/tradewinds_macro/catalog/alfred.py, packages/macro/tests/test_alfred_adapter.py</files>
  <implements>MCP-05 (vintage-aware temporal safety); MCP-10 (alfred.archive component)</implements>
  <read_first>
    - Task 4.1 outputs (FREDAdapter pattern)
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§E.2 — ALFRED vintage API is the temporal-safety primitive; §I.7 — pitfall: ALFRED inflated row counts; mitigation: filter realtime_start <= as_of BEFORE returning)
    - alfred.stlouisfed.org docs (linked in RESEARCH.md sources) — confirm endpoint shape for vintage-aware fetches; the `/fred/series/observations` endpoint accepts `realtime_start` + `realtime_end` query params
  </read_first>
  <behavior>
    Tests in `packages/macro/tests/test_alfred_adapter.py` (6 tests):

    1. `test_alfred_adapter_supported_sources`: `ALFREDAdapter.SUPPORTED_SOURCES == ['alfred.archive']`.
    2. `test_alfred_fetch_vintage_aware_recorded`: with cassette, `ALFREDAdapter().fetch(series_id='CPIAUCSL', start=date(2024,1,1), end=date(2024,3,31), as_of=datetime(2024,2,15,tzinfo=UTC))` returns rows where `realtime_start <= as_of`. NO ROWS with `realtime_start > as_of` (these are future vintage revisions).
    3. `test_alfred_knowledge_time_equals_realtime_start`: for every returned row, `df['knowledge_time'] == df['realtime_start']`. This is the vintage primitive — when the value became knowable.
    4. `test_alfred_deterministic_replay`: call `fetch(...)` twice with the same args; result DataFrames are byte-equal (same row count, same values). Preview for PLAN-05 replay tests.
    5. `test_alfred_corrected_release_dedup` (RESEARCH.md §I.7 pitfall): cassette with a CPI value that has TWO vintages (original Feb-15 release + Mar-15 correction). With `as_of=datetime(2024,2,15)`, only the original (realtime_start=2024-02-15) appears; the correction (realtime_start=2024-03-15) is filtered out. Row count = 1, not 2.
    6. `test_alfred_emits_realtime_start_column`: result DataFrame has a `realtime_start` column (in addition to event_time / knowledge_time / source / retrieved_at / value / series_id).

    Run `uv run pytest packages/macro/tests/test_alfred_adapter.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 6 tests. Commit RED.

    Step 2 — Implement `packages/macro/src/tradewinds_macro/catalog/alfred.py`:

    ```python
    """ALFREDAdapter — vintage-aware fetches for FRED-tracked series.

    The ALFRED API returns observations with (date, realtime_start, realtime_end)
    triples — each observation has potentially multiple vintages over time.

    knowledge_time = realtime_start (when the value became knowable; the natural
    temporal-safety primitive per RESEARCH.md §E.2).

    Vintage dedup: fetch returns ONE row per (date, latest vintage with realtime_start <= as_of).
    Pitfall I.7 (inflated row counts when source backfills) hard-defended.
    """

    from __future__ import annotations

    import os
    from datetime import date, datetime, timezone
    from typing import ClassVar

    import httpx
    import pandas as pd

    from tradewinds.core.exceptions import SourceUnavailableError

    __all__ = ["ALFREDAdapter"]

    _ALFRED_BASE = "https://api.stlouisfed.org/fred"  # ALFRED endpoints share base with FRED


    class ALFREDAdapter:
        SUPPORTED_SOURCES: ClassVar[list[str]] = ["alfred.archive"]

        def __init__(self, client: httpx.Client | None = None) -> None:
            self._client = client

        def _get_client(self) -> httpx.Client:
            if self._client is None:
                self._client = httpx.Client(timeout=60.0)
            return self._client

        def fetch(
            self,
            *,
            series_id: str,
            start: date,
            end: date,
            as_of: datetime,
        ) -> pd.DataFrame:
            """Fetch ALFRED vintage-aware observations.

            Returns ONE row per (date, latest vintage with realtime_start <= as_of).
            knowledge_time == realtime_start.
            """
            api_key = os.environ.get("FRED_API_KEY")
            if not api_key:
                raise SourceUnavailableError(
                    "FRED_API_KEY environment variable required for ALFRED. "
                    "Register at https://fred.stlouisfed.org/docs/api/api_key.html"
                )
            url = f"{_ALFRED_BASE}/series/observations"
            # ALFRED-mode: request all vintages by setting realtime_start to a very old date
            # and realtime_end to as_of (we filter further client-side for safety).
            params = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start.isoformat(),
                "observation_end": end.isoformat(),
                "realtime_start": "1776-07-04",  # all of US economic history :)
                "realtime_end": as_of.date().isoformat(),
            }
            resp = self._get_client().get(url, params=params)
            resp.raise_for_status()
            observations = resp.json().get("observations", [])
            now_utc = datetime.now(timezone.utc)

            rows = []
            for obs in observations:
                event_dt = datetime.fromisoformat(obs["date"]).replace(tzinfo=timezone.utc)
                rt_start = datetime.fromisoformat(obs["realtime_start"]).replace(tzinfo=timezone.utc)
                rt_end_str = obs["realtime_end"]
                rt_end = datetime.fromisoformat(rt_end_str).replace(tzinfo=timezone.utc) if rt_end_str != "9999-12-31" else None
                # RESEARCH.md §I.7 mitigation: filter realtime_start <= as_of BEFORE adding to rows
                if rt_start > as_of:
                    continue
                rows.append({
                    "event_time": event_dt,
                    "knowledge_time": rt_start,  # ← THE vintage primitive
                    "source": "alfred.archive",
                    "retrieved_at": now_utc,
                    "series_id": series_id,
                    "value": float(obs["value"]) if obs["value"] not in (".", "") else None,
                    "realtime_start": rt_start,
                    "realtime_end": rt_end,
                })
            df = pd.DataFrame(rows)
            if df.empty:
                return df
            # Dedup: per (event_time, series_id), keep the row with the LATEST realtime_start <= as_of
            df = df.sort_values(by=["event_time", "realtime_start"]).drop_duplicates(
                subset=["event_time", "series_id"], keep="last"
            ).reset_index(drop=True)
            # Dtype conventions
            for col in ("event_time", "knowledge_time", "retrieved_at", "realtime_start"):
                df[col] = pd.to_datetime(df[col], utc=True)
            df["realtime_end"] = pd.to_datetime(df["realtime_end"], utc=True, errors="coerce")
            df["value"] = df["value"].astype("Float64")
            return df

        def close(self) -> None:
            if self._client is not None:
                self._client.close()
    ```

    Step 3 — Capture ALFRED cassettes (`packages/macro/tests/cassettes/test_alfred_*.yaml`); commit them.

    Step 4 — Run `uv run pytest packages/macro/tests/test_alfred_adapter.py -x -v` — all 6 tests MUST pass.

    Step 5 — Commit GREEN: `feat(phase-5): ALFREDAdapter — vintage-aware fetches; knowledge_time = realtime_start (MCP-05 + MCP-10 alfred.archive)`.
  </action>
  <verify>
    <automated>uv run pytest packages/macro/tests/test_alfred_adapter.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/macro/src/tradewinds_macro/catalog/alfred.py` returns 0
    - `grep -c "class ALFREDAdapter" packages/macro/src/tradewinds_macro/catalog/alfred.py` returns 1
    - `grep -c "knowledge_time.*realtime_start" packages/macro/src/tradewinds_macro/catalog/alfred.py` returns ≥ 1
    - `grep -c "rt_start > as_of" packages/macro/src/tradewinds_macro/catalog/alfred.py` returns ≥ 1 (Pitfall I.7 filter)
    - `grep -c "drop_duplicates" packages/macro/src/tradewinds_macro/catalog/alfred.py` returns 1 (latest-vintage dedup)
    - `uv run pytest packages/macro/tests/test_alfred_adapter.py -x -v` exits 0 with 6 passed
    - Cassettes committed under `packages/macro/tests/cassettes/`
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    ALFREDAdapter implements vintage-aware fetch; knowledge_time = realtime_start; Pitfall I.7 (inflated row counts) hard-filtered. 6 tests pass including deterministic-replay preview.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 4.3: KalshiMacroContractSpec (RED tests FIRST)</name>
  <files>packages/macro/src/tradewinds_macro/catalog/kalshi_macro.py, packages/macro/tests/test_kalshi_macro_specs.py</files>
  <implements>MCP-05 (macro market contract specs); MCP-10 (kalshi.macro component)</implements>
  <read_first>
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§E.2 — Kalshi macro markets; settlement sources are BLS / BEA / Fed direct; §E.3 — kalshi.macro is contract specs only, no orderbook)
    - .planning/phases/02-core-primitives-catalog-adapters/PLAN.md (Wave 4 — Kalshi NHIGH/NLOW contract spec pattern; KALSHI_SETTLEMENT_STATIONS hard-coded dict; mirror this for macro)
    - packages/markets/src/tradewinds/markets/catalog/ (Phase 2 — existing kalshi_nhigh/kalshi_nlow contract spec implementations to mirror; KALSHI_SETTLEMENT_STATIONS pattern with citation URLs)
  </read_first>
  <behavior>
    Tests in `packages/macro/tests/test_kalshi_macro_specs.py` (5 tests):

    1. `test_kalshi_macro_settlement_sources_dict`: `KALSHI_MACRO_SETTLEMENT_SOURCES` is a dict mapping Kalshi macro contract tickers (e.g. `KXCPIYOY`, `KXPCEYOY`, `KXNFP`, `KXFFR`) to `(settlement_source, citation_url)` tuples. Source values are `bls.direct` / `bea.direct` / `fed.direct`. At least 5 entries.
    2. `test_kalshi_macro_no_unexpected_sources`: every settlement_source value is in `{'bls.direct', 'bea.direct', 'fed.direct'}` — no Sportradar / ESPN / other third-party (sports legal-blocker discipline applied to macro too).
    3. `test_kalshi_macro_contract_spec_resolve`: `KalshiMacroContractSpec().resolve('KXCPIYOY', date(2024,1,1))` returns a dict-like `{'settlement_source': 'bls.direct', 'settlement_release_date': <date>, 'settlement_value_field': 'cpi_yoy_pct'}`.
    4. `test_kalshi_macro_supported_sources`: `KalshiMacroContractSpec.SUPPORTED_SOURCES == ['kalshi.macro']`.
    5. `test_kalshi_macro_unknown_ticker_raises`: `resolve('FAKE_TICKER', date(2024,1,1))` raises `SourceUnavailableError` with the list of supported tickers.

    Run `uv run pytest packages/macro/tests/test_kalshi_macro_specs.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 5 tests. Commit RED.

    Step 2 — Implement `packages/macro/src/tradewinds_macro/catalog/kalshi_macro.py`:

    ```python
    """KalshiMacroContractSpec — contract specs for Kalshi macro markets.

    v0.2 ships contract spec resolution only — no orderbook, no fills, no trading.
    Mirrors Phase 2 Kalshi NHIGH/NLOW weather contract pattern.

    Settlement sources are first-party: BLS (CPI / payrolls / unemployment),
    BEA (PCE), Fed (Fed Funds rate). NO third-party data — per RESEARCH.md §E.2
    these markets are CFTC-blessed and use official release data.

    Reference: Fed working paper on Kalshi macro markets
    https://www.federalreserve.gov/econres/feds/files/2026010pap.pdf
    """

    from __future__ import annotations

    from datetime import date
    from typing import ClassVar

    from tradewinds.core.exceptions import SourceUnavailableError

    __all__ = ["KalshiMacroContractSpec", "KALSHI_MACRO_SETTLEMENT_SOURCES"]


    # Ticker → (settlement_source, citation_url, settlement_value_field)
    # Citation URLs link to Kalshi market pages or BLS/BEA/Fed release calendars.
    KALSHI_MACRO_SETTLEMENT_SOURCES: dict[str, tuple[str, str, str]] = {
        "KXCPIYOY": (
            "bls.direct",
            "https://www.kalshi.com/markets/kxcpiyoy",
            "cpi_yoy_pct",
        ),
        "KXCPICORE": (
            "bls.direct",
            "https://www.kalshi.com/markets/kxcpicore",
            "core_cpi_yoy_pct",
        ),
        "KXPCEYOY": (
            "bea.direct",
            "https://www.kalshi.com/markets/kxpceyoy",
            "pce_yoy_pct",
        ),
        "KXNFP": (
            "bls.direct",
            "https://www.kalshi.com/markets/kxnfp",
            "nonfarm_payrolls",
        ),
        "KXFFR": (
            "fed.direct",
            "https://www.kalshi.com/markets/kxffr",
            "fed_funds_rate_target_upper",
        ),
        "KXUNEMP": (
            "bls.direct",
            "https://www.kalshi.com/markets/kxunemp",
            "unemployment_rate_pct",
        ),
    }

    _ALLOWED_SOURCES = {"bls.direct", "bea.direct", "fed.direct"}
    # Verify at import time — fast-fail if a future maintainer adds an unexpected source
    _bad = {t: src for t, (src, _, _) in KALSHI_MACRO_SETTLEMENT_SOURCES.items() if src not in _ALLOWED_SOURCES}
    assert not _bad, f"KALSHI_MACRO_SETTLEMENT_SOURCES has unexpected source(s): {_bad}"


    class KalshiMacroContractSpec:
        """Resolves Kalshi macro contract tickers to settlement sources + value fields."""

        SUPPORTED_SOURCES: ClassVar[list[str]] = ["kalshi.macro"]

        def resolve(self, ticker: str, settlement_date: date) -> dict:
            """Return {settlement_source, settlement_value_field, citation_url} for ticker on date."""
            if ticker not in KALSHI_MACRO_SETTLEMENT_SOURCES:
                raise SourceUnavailableError(
                    f"Unknown Kalshi macro ticker '{ticker}'. "
                    f"Supported: {sorted(KALSHI_MACRO_SETTLEMENT_SOURCES.keys())}"
                )
            src, citation, field = KALSHI_MACRO_SETTLEMENT_SOURCES[ticker]
            return {
                "settlement_source": src,
                "settlement_value_field": field,
                "citation_url": citation,
                "ticker": ticker,
                "settlement_date": settlement_date.isoformat(),
            }

        # Compatibility shim: callers (like _adapter_bridge) expect fetch(); contract specs
        # don't fetch rows — raise the documented "use markets module directly" error.
        def fetch(self, **kwargs):
            raise SourceUnavailableError(
                "kalshi.macro is a contract spec, not row data. "
                "Use tradewinds_macro.catalog.KalshiMacroContractSpec().resolve(ticker, date) directly. "
                "Catalog describe_source('kalshi.macro') returns the full contract spec metadata."
            )
    ```

    Step 3 — Run `uv run pytest packages/macro/tests/test_kalshi_macro_specs.py -x -v` — all 5 tests MUST pass.

    Step 4 — Commit GREEN: `feat(phase-5): KalshiMacroContractSpec + KALSHI_MACRO_SETTLEMENT_SOURCES (MCP-05 + MCP-10 kalshi.macro)`.
  </action>
  <verify>
    <automated>uv run pytest packages/macro/tests/test_kalshi_macro_specs.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/macro/src/tradewinds_macro/catalog/kalshi_macro.py` returns 0
    - `grep -c "class KalshiMacroContractSpec" packages/macro/src/tradewinds_macro/catalog/kalshi_macro.py` returns 1
    - `grep -c "KALSHI_MACRO_SETTLEMENT_SOURCES" packages/macro/src/tradewinds_macro/catalog/kalshi_macro.py` returns ≥ 2
    - `python -c "from tradewinds_macro.catalog.kalshi_macro import KALSHI_MACRO_SETTLEMENT_SOURCES; assert len(KALSHI_MACRO_SETTLEMENT_SOURCES) >= 5"` exits 0
    - `python -c "from tradewinds_macro.catalog.kalshi_macro import KALSHI_MACRO_SETTLEMENT_SOURCES; sources = set(v[0] for v in KALSHI_MACRO_SETTLEMENT_SOURCES.values()); assert sources <= {'bls.direct', 'bea.direct', 'fed.direct'}, sources"` exits 0
    - `uv run pytest packages/macro/tests/test_kalshi_macro_specs.py -x -v` exits 0 with 5 passed
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    KalshiMacroContractSpec + KALSHI_MACRO_SETTLEMENT_SOURCES dict (≥ 5 tickers; only bls/bea/fed sources). resolve() returns settlement metadata; fetch() raises with "use markets module directly". 5 tests pass.
  </done>
</task>

<task type="auto">
  <name>Task 4.4: 3 macro catalog YAML entries (in `_generated/`); scaffold + fill in 5 layers + local validate</name>
  <files>packages/mcp/catalog/_generated/fred.archive.yaml, packages/mcp/catalog/_generated/alfred.archive.yaml, packages/mcp/catalog/_generated/kalshi.macro.yaml</files>
  <implements>MCP-02 (catalog entries for second vertical); MCP-10 macro portion (still in _generated/; promotion in Task 4.5)</implements>
  <read_first>
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§E.2 — FRED+ALFRED+Kalshi macro rationale; §B.2 — YAML catalog skeleton)
    - packages/mcp/AGENT-CONNECTOR-GUIDE.md (Wave 3 — worked example for filling in 5 layers)
    - packages/mcp/src/tradewinds_mcp/_generated_scaffold.py (Wave 3 — use this to scaffold)
    - packages/mcp/src/tradewinds_mcp/_generated_validator.py (Wave 3 — use this to validate)
    - packages/mcp/catalog/iem.archive.yaml (PLAN-02 — reference for 5-layer structure)
    - Tasks 4.1 + 4.2 + 4.3 outputs (adapter behavior for extraction_config + temporal_rules)
  </read_first>
  <action>
    Step 1 — Scaffold each entry using the Wave 3 tooling:

    ```python
    uv run python -c "
    from tradewinds_mcp._generated_scaffold import scaffold_catalog_entry
    import yaml
    for sid, url in [('fred.archive', 'https://fred.stlouisfed.org/docs/api/fred/'),
                      ('alfred.archive', 'https://alfred.stlouisfed.org/help/downloaddata'),
                      ('kalshi.macro', 'https://docs.kalshi.com/welcome')]:
        entry = scaffold_catalog_entry(sid, api_doc_url=url)
        with open(f'packages/mcp/catalog/_generated/{sid}.yaml', 'w') as f:
            yaml.safe_dump(entry, f, sort_keys=False, default_flow_style=False)
    "
    ```

    Step 2 — Fill in each entry's 5 layers. Use the AGENT-CONNECTOR-GUIDE worked example as the template. Here's the target content for `packages/mcp/catalog/_generated/fred.archive.yaml`:

    ```yaml
    $schema: ../_schema/catalog_entry.schema.json
    source_id: fred.archive
    display_name: "FRED — Federal Reserve Economic Data (US macro indicators)"
    status: live

    schema_semantics:
      schema_id: schema.observation.v1
      fields:
        series_id: "FRED series identifier (e.g. CPIAUCSL, PAYEMS, DFF). Each series has its own units + release calendar."
        value: "Observed value for the series on event_time. Units depend on series_id (CPI = index 1982-84=100; UNRATE = percent; DFF = percent; etc.)."
        event_time: "Observation date (UTC midnight). Granularity varies: monthly for CPI/PCE/PAYEMS; daily for DFF."
        knowledge_time: "When the observation became available. event_time + per-series publish delay (BLS releases CPI mid-month for prior month; etc.)."

    temporal_rules:
      event_time_field: event_time
      knowledge_time_field: knowledge_time
      knowledge_time_formula: "event_time + per-series publish delay (e.g. CPIAUCSL = +15 days; PAYEMS = +7 days; DFF = +1 day) — see tradewinds_macro.catalog.fred._PUBLISH_DELAYS for the exact mapping per series"
      backfill_behavior: "FRED itself is one-shot publish — past values DO NOT change once published. For VINTAGE-AWARE access (knowledge_time = realtime_start), use the sibling alfred.archive catalog entry."
      vintage_aware: false

    quality_notes:
      - "FRED is NOT vintage-aware — knowledge_time is computed as event_time + publish_delay. For point-in-time backtests against revised data, use alfred.archive."
      - "BLS / BEA / Fed release calendars are documented; the per-series _PUBLISH_DELAYS table in tradewinds_macro is conservative (slightly later than actual releases to avoid leakage)."
      - "Series IDs that have a Kalshi macro contract counterpart (CPIAUCSL → KXCPIYOY, etc.) are listed in tradewinds_macro.catalog.kalshi_macro.KALSHI_MACRO_SETTLEMENT_SOURCES."
      - "Rate limit: 120 req/60sec per FRED_API_KEY (documented at fred.stlouisfed.org/docs/api/api_key.html). Adapter does NOT actively rate-limit in v0.2; user is responsible."

    relationship_mappings:
      joins_to:
        - source: alfred.archive
          on: ["series_id", "event_time"]
          note: "ALFRED provides vintage history for the same series_id; join to get knowledge_time = realtime_start instead of conservative publish-delay."
        - source: kalshi.macro
          on: ["series_id"]
          note: "Series IDs map to Kalshi contract tickers via KALSHI_MACRO_SETTLEMENT_SOURCES (e.g. CPIAUCSL → KXCPIYOY)."

    operational_context:
      endpoint: "https://api.stlouisfed.org/fred/series/observations"
      rate_limit: "120 req/60sec per FRED_API_KEY"
      auth: "api_key:FRED_API_KEY"
      pagination: "single response per (series_id, observation_start, observation_end); large date ranges are returned in one payload (no client-side pagination needed)"
      http_timeout_seconds: 60

    extraction_config:
      adapter: fred.archive
    ```

    Step 3 — Similar content for `alfred.archive.yaml` (vintage_aware: true; knowledge_time_formula = "realtime_start"; backfill_behavior documents the vintage history) and `kalshi.macro.yaml` (status: live; schema_semantics.schema_id: contract_spec.kalshi_macro.v1 — synthetic ID since this is contract spec, not row data; quality_notes cite Fed working paper).

    Step 4 — Locally validate each entry:

    ```bash
    for src in fred.archive alfred.archive kalshi.macro; do
      echo "=== $src ==="
      uv run python -c "
      from pathlib import Path
      from tradewinds_mcp._generated_validator import validate_generated_entry
      r = validate_generated_entry(Path('packages/mcp/catalog/_generated/$src.yaml'))
      print(r.model_dump_json(indent=2))
      import sys
      sys.exit(0 if r.all_green else 1)
      " || echo "FAIL: $src"
    done
    ```

    Each must report `all_green: True`. Iterate on the YAML if any check fails. For `kalshi.macro`, the validator may complain about `schema_id_resolves` because `contract_spec.kalshi_macro.v1` is not in the Phase 2 REGISTRY. Two options:
    - (a) Add a `contract_spec.*` namespace to the Phase 2 REGISTRY in a sibling task (tiny — just register synthetic schemas as documentation entries).
    - (b) Special-case `kalshi.*` source IDs in the validator (already done for kalshi.weather in PLAN-02; verify by re-reading PLAN-02's validator behavior).

    The plan defaults to (b) — `kalshi.*` source IDs skip the schema_id-resolves check per `if entry.source_id.startswith("kalshi.")` in the validator (already present from Wave 3 PLAN-03 Task 3.1 implementation).

    Step 5 — Run `uv run pre-commit run --all-files`. Expected green.

    Step 6 — Commit: `feat(phase-5): 3 macro catalog YAML entries in _generated/ (MCP-10 macro portion candidate)`.

    NOTE: at this point, `CatalogLoader.from_dir('packages/mcp/catalog/')` STILL returns 7 entries — the _generated/ subdir is skipped. The promotion happens in Task 4.5.
  </action>
  <verify>
    <automated>for src in fred.archive alfred.archive kalshi.macro; do uv run python -c "from pathlib import Path; from tradewinds_mcp._generated_validator import validate_generated_entry; r = validate_generated_entry(Path('packages/mcp/catalog/_generated/$src.yaml')); import sys; sys.exit(0 if r.all_green else 1)" || exit 1; done</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/catalog/_generated/fred.archive.yaml` returns 0
    - `test -f packages/mcp/catalog/_generated/alfred.archive.yaml` returns 0
    - `test -f packages/mcp/catalog/_generated/kalshi.macro.yaml` returns 0
    - `grep -c "^status: live$" packages/mcp/catalog/_generated/fred.archive.yaml` returns 1
    - `grep -c "^vintage_aware: true$" packages/mcp/catalog/_generated/alfred.archive.yaml` returns 1
    - `grep -c "federalreserve.gov" packages/mcp/catalog/_generated/kalshi.macro.yaml` returns ≥ 1 (Fed working paper citation)
    - For each src in {fred.archive, alfred.archive, kalshi.macro}: validator reports `all_green: True`
    - CatalogLoader still returns 7 entries (the _generated/ subdir is skipped): `python -c "from tradewinds_mcp.catalog import CatalogLoader; assert len(CatalogLoader.from_dir('packages/mcp/catalog/')) == 7"` exits 0
    - One commit on the branch
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    3 macro catalog YAML entries exist in `_generated/`, each meta-schema-valid + Pydantic-valid + (for fred/alfred) schema_id-resolves + temporal-rules-lint-green. CatalogLoader still returns 7 entries (promotion is next task).
  </done>
</task>

<task type="auto">
  <name>Task 4.5: Promote 3 entries + extend _adapter_bridge for macro dispatch + in-process verification (RED test FIRST for bridge extension)</name>
  <files>packages/mcp/src/tradewinds_mcp/_adapter_bridge.py, packages/mcp/tests/test_adapter_bridge_macro_dispatch.py, packages/mcp/catalog/fred.archive.yaml, packages/mcp/catalog/alfred.archive.yaml, packages/mcp/catalog/kalshi.macro.yaml</files>
  <implements>MCP-05 (full — multi-vertical proof), MCP-10 (10 entries in catalog/)</implements>
  <read_first>
    - Tasks 4.1 + 4.2 + 4.3 + 4.4 outputs
    - packages/mcp/scripts/promote_generated_entry.py (Wave 3 — the promotion CLI)
    - packages/mcp/src/tradewinds_mcp/_adapter_bridge.py (Wave 2 — current dispatch logic for weather; extending for macro)
  </read_first>
  <behavior>
    Tests in `packages/mcp/tests/test_adapter_bridge_macro_dispatch.py` (4 tests):

    1. `test_bridge_dispatches_fred_archive_to_macro`: `AdapterBridge()._resolve_adapter('fred.archive')` returns an instance from `tradewinds_macro.catalog._REGISTRY`, NOT from `tradewinds.weather.catalog`. Mock both registries to confirm.
    2. `test_bridge_dispatches_alfred_archive_to_macro`: same as above for `alfred.archive`.
    3. `test_bridge_raises_for_kalshi_macro`: `_resolve_adapter('kalshi.macro')` raises `SourceUnavailableError` with the "use markets module directly" pattern (mirror of kalshi.weather behavior in PLAN-02).
    4. `test_bridge_still_dispatches_weather`: `_resolve_adapter('iem.archive')` still dispatches to `tradewinds.weather.catalog.get_adapter('iem.archive')` — no regression.

    Run `uv run pytest packages/mcp/tests/test_adapter_bridge_macro_dispatch.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 4 bridge tests. Commit RED.

    Step 2 — Modify `packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` to add macro dispatch alongside weather. The `_resolve_adapter` method becomes:

    ```python
    @staticmethod
    def _resolve_adapter(adapter_id: str) -> Any:
        # Kalshi contract specs (both weather + macro): not row data
        if adapter_id.startswith("kalshi."):
            raise SourceUnavailableError(
                f"Source '{adapter_id}' is a contract spec; not queryable as row data in v0.2. "
                f"Use tradewinds.markets.catalog or tradewinds_macro.catalog directly. "
                f"See describe_source('{adapter_id}') for full catalog entry."
            )
        # Macro dispatch (fred.*, alfred.*)
        if adapter_id.startswith("fred.") or adapter_id.startswith("alfred."):
            try:
                from tradewinds_macro.catalog import get_adapter as macro_get_adapter
            except ImportError as exc:
                raise SourceUnavailableError(
                    f"tradewinds-macro is not installed. Run `pip install tradewinds-macro` to use source '{adapter_id}'."
                ) from exc
            try:
                return macro_get_adapter(adapter_id)
            except KeyError as exc:
                raise SourceUnavailableError(
                    f"Adapter for source_id '{adapter_id}' not found in tradewinds_macro.catalog registry."
                ) from exc
        # Default: weather dispatch (unchanged from PLAN-02)
        try:
            from tradewinds.weather.catalog import get_adapter
        except ImportError as exc:
            raise SourceUnavailableError(
                f"tradewinds-weather is not installed. Run `pip install tradewinds-weather` to use source '{adapter_id}'."
            ) from exc
        try:
            return get_adapter(adapter_id)
        except KeyError as exc:
            raise SourceUnavailableError(
                f"Adapter for source_id '{adapter_id}' not found in tradewinds.weather.catalog registry."
            ) from exc
    ```

    Step 3 — Run `uv run pytest packages/mcp/tests/test_adapter_bridge_macro_dispatch.py -x -v` — 4 tests MUST pass.

    Step 4 — Add `tradewinds-macro>=0.2.0,<0.3` as a soft dependency to `packages/mcp/pyproject.toml` (under `[project.optional-dependencies]` so vanilla MCP installs don't require the macro distribution):

    ```toml
    [project.optional-dependencies]
    macro = ["tradewinds-macro>=0.2.0,<0.3"]
    ```

    Step 5 — Promote each generated entry using the Wave 3 CLI:

    ```bash
    # Dry-run first to surface any last-minute issues
    for src in fred.archive alfred.archive kalshi.macro; do
      uv run python packages/mcp/scripts/promote_generated_entry.py --dry-run packages/mcp/catalog/_generated/$src.yaml
    done

    # If all 3 dry-runs report all_green=True, execute (skip-live for unit-test contexts;
    # for production runs, omit --skip-live and run with FRED_API_KEY set + KALSHI_API_KEY if applicable)
    for src in fred.archive alfred.archive kalshi.macro; do
      uv run python packages/mcp/scripts/promote_generated_entry.py --execute --skip-live packages/mcp/catalog/_generated/$src.yaml
    done
    ```

    After promotion, the 3 files have moved from `_generated/` to `catalog/` root.

    Step 6 — Verify the MCP server now sees 10 entries:

    ```bash
    uv run python -c "
    from tradewinds_mcp.catalog import CatalogLoader
    loader = CatalogLoader.from_dir('packages/mcp/catalog/')
    print(f'Catalog entries: {len(loader)}')
    print(f'Source IDs: {loader.all_source_ids()}')
    assert len(loader) == 10, f'Expected 10, got {len(loader)}'
    "
    ```

    Expected output: 10 entries; source IDs = `['alfred.archive', 'awc.live', 'cli.archive', 'fred.archive', 'ghcnh.archive', 'iem.archive', 'iem.forecasts', 'iem.live', 'kalshi.macro', 'kalshi.weather']` (sorted).

    Step 7 — In-process smoke against the MCP server:

    ```bash
    uv run python -c "
    import asyncio
    from datetime import datetime, timezone
    from tradewinds_mcp.server import mcp

    # Confirm middleware still attached + 10 entries via list_sources tool
    # (In a real test we'd use run_server_async; here we use a quick assertion path)
    print('Server name:', mcp.name)
    print('Tools registered:', sorted(mcp._tool_manager._tools.keys()))
    "
    ```

    Step 8 — Run `uv run pytest packages/mcp/tests/ -m "not live" -q` — full Wave 1+2+3+4 suite. Expected green.

    Step 9 — Commit GREEN: `feat(phase-5): promote 3 macro catalog entries + extend _adapter_bridge (MCP-05 + MCP-10 macro)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_adapter_bridge_macro_dispatch.py -x -v && uv run python -c "from tradewinds_mcp.catalog import CatalogLoader; loader = CatalogLoader.from_dir('packages/mcp/catalog/'); assert len(loader) == 10, f'Expected 10, got {len(loader)}'; assert set(loader.all_source_ids()) == {'alfred.archive', 'awc.live', 'cli.archive', 'fred.archive', 'ghcnh.archive', 'iem.archive', 'iem.forecasts', 'iem.live', 'kalshi.macro', 'kalshi.weather'}" && uv run pytest packages/mcp/tests/ -m "not live" -q</automated>
  </verify>
  <acceptance_criteria>
    - 3 entries moved from `_generated/` to `catalog/` root: `test -f packages/mcp/catalog/fred.archive.yaml`, `test -f packages/mcp/catalog/alfred.archive.yaml`, `test -f packages/mcp/catalog/kalshi.macro.yaml` all return 0
    - 3 entries removed from `_generated/`: `test ! -f packages/mcp/catalog/_generated/fred.archive.yaml`, etc., all return 0
    - `CatalogLoader.from_dir('packages/mcp/catalog/')` returns 10 entries (MCP-10 commitment delivered)
    - `grep -c "fred.archive\|alfred.archive" packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` returns ≥ 2 (macro dispatch added)
    - `grep -c "from tradewinds_macro.catalog import" packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` returns 1
    - `uv run pytest packages/mcp/tests/test_adapter_bridge_macro_dispatch.py -x -v` exits 0 with 4 passed
    - Promotion audit entries in `$HOME/.tradewinds/mcp-server/catalog-promotions.jsonl` for all 3 sources
    - `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0
    - Two commits on the branch (RED + GREEN; promotion is a separate task in the workflow but lands in the same commit boundary as the bridge change for atomicity)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    3 macro catalog entries promoted from _generated/ to catalog/ root (MCP-10 = 10 entries total). _adapter_bridge dispatches macro source IDs to tradewinds_macro.catalog. kalshi.macro raises consistent error message. 4 bridge tests pass. Full MCP suite green.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 4.6: 2-reviewer loop + pre-merge gate + merge to main</name>
  <files>n/a (verification only)</files>
  <implements>Wave 4a closeout</implements>
  <read_first>
    - .planning/REVIEW-DISCIPLINE.md (never-skip — new package distribution + Kalshi contract spec literal table + catalog YAML — three reviewer-flagged surfaces)
    - .planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md (the user's decision artifact)
    - Plan-level success criteria below
  </read_first>
  <what-built>
    Tasks 4.0–4.5 complete: USER_DECISION_GATE resolved (macro confirmed in default path); `tradewinds-macro` distribution shipped with FREDAdapter / ALFREDAdapter / KalshiMacroContractSpec; 3 catalog YAML entries promoted to catalog/; _adapter_bridge extended for macro dispatch. MCP server now sees 10 entries across 2 verticals (weather + macro).
  </what-built>
  <how-to-verify>
    **Step A — Final test pass:**

    ```bash
    uv run pytest packages/mcp/tests/ packages/macro/tests/ -m "not live" -v
    uv run pytest -m "not live" -q
    uv run pytest --cov=tradewinds_mcp --cov=tradewinds_macro --cov-branch packages/mcp/tests/ packages/macro/tests/ -q | grep TOTAL
    ```

    Expected: all green; coverage ≥ 85% on tradewinds_mcp; ≥ 80% on tradewinds_macro (adapter wrappers — CLAUDE.md bar).

    **Step B — Manual sample-data live test (FRED/ALFRED) — optional, pre-publish:**

    ```bash
    FRED_API_KEY=<key> uv run pytest packages/macro/tests/ -m "live" -v
    # AND
    FRED_API_KEY=<key> uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m "live" -v -k "fred.archive or alfred.archive"
    ```

    Expected: real FRED/ALFRED responses match the claimed schema. If any field mismatch, surface as a follow-up YAML fix.

    **Step C — Multi-vertical proof check:**

    ```bash
    uv run python -c "
    from tradewinds_mcp.catalog import CatalogLoader
    loader = CatalogLoader.from_dir('packages/mcp/catalog/')
    verticals = set()
    for entry in loader:
        if entry.source_id.startswith(('iem.', 'awc.', 'ghcnh.', 'cli.', 'kalshi.weather')):
            verticals.add('weather')
        elif entry.source_id.startswith(('fred.', 'alfred.', 'kalshi.macro')):
            verticals.add('macro')
    assert verticals == {'weather', 'macro'}, f'Expected 2 verticals, got {verticals}'
    print('MCP-05 multi-vertical proof: confirmed', sorted(verticals))
    "
    ```

    **Step D — 2-reviewer loop per REVIEW-DISCIPLINE.md:**

    Reviewer prompts MUST reference:
    - CONTEXT.md USER_DECISION_GATE lock (researcher's macro recommendation; sports legal blockers)
    - RESEARCH.md §E.2 vintage semantics (ALFRED `realtime_start` = `knowledge_time`)
    - RESEARCH.md §I.7 pitfall (ALFRED row-count inflation — verify the dedup filter is in place)
    - KALSHI_MACRO_SETTLEMENT_SOURCES dict — analogous to Phase 2's KALSHI_SETTLEMENT_STATIONS where a typo would corrupt settlement
    - REVIEW-DISCIPLINE.md never-skip — new packages/, YAML schema fragments, contract-spec literal tables

    PASS x2 in ≤ 3 iterations.

    **Step E — Merge to main:**

    ```bash
    git checkout main
    git merge --no-ff phase-5/wave-4/vertical-macro -m "Merge phase-5/wave-4/vertical-macro: FRED+ALFRED+Kalshi macro adapter + 3 catalog entries (MCP-05 + MCP-10 macro). Wave 4a complete."
    ```

    **Step F — Confirm to user:**

    (1) All green: "Wave 4a (second vertical) merged to `main`. tradewinds-macro distribution shipped with FRED+ALFRED+Kalshi macro adapters; 3 catalog entries promoted (10 total). MCP-05 multi-vertical proof: weather + macro. PLAN-05 (integration tests + deterministic-replay + v0.2.0 release) is unblocked. Type `approved` to continue."

    (2) Sports / Other / Defer chosen at Task 4.0: planner reports the specific path taken + any deviations from this PLAN's structure; PLAN-05 may need a re-scope.

    (3) Reviewer REVISE: standard cycle.
  </how-to-verify>
  <resume-signal>
    Type `approved` once Wave 4a is merged to `main` (PLAN-05 is unblocked). Type `revise` for reviewer-driven changes. Type `field-fix` if the live sample-data test surfaced a YAML field mismatch.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| FRED API + ALFRED API HTTP boundary | Outbound HTTPS to `api.stlouisfed.org`; FRED_API_KEY is the auth token (env var). |
| KALSHI_MACRO_SETTLEMENT_SOURCES literal table | Hard-coded mapping ticker → settlement source. Wrong literal = silent settlement corruption (analogous to Phase 2 KALSHI_SETTLEMENT_STATIONS risk). |
| `_adapter_bridge` dispatch extension | New code path for fred./alfred./kalshi.macro source IDs; must not regress weather dispatch. |
| VCR cassettes under `packages/macro/tests/cassettes/` | Captured FRED/ALFRED responses; api_key filtered. If api_key leaks into a cassette, security exposure. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-5.4-01 | Information Disclosure | API key leak in committed VCR cassette | mitigate | `conftest.py` vcr_config filters `api_key` query parameter → `REDACTED_API_KEY` in cassettes. Pre-commit grep for `api_key=[0-9a-f]{32}` in committed cassettes fails the build. |
| T-5.4-02 | Tampering | Wrong KALSHI_MACRO_SETTLEMENT_SOURCES entry (e.g., KXCPIYOY → bea.direct instead of bls.direct) silently corrupts settlement | mitigate | Assertion at module-import time: `_bad = {t: src for ... if src not in _ALLOWED_SOURCES}; assert not _bad` — fails at import if any source is wrong. Catalog YAML quality_notes cite the Fed working paper + Kalshi market pages with citation_url. 2-reviewer loop double-checks the literal table. |
| T-5.4-03 | Tampering | ALFRED row-count inflation (Pitfall I.7) — same `as_of` returns different row counts as vintages are added upstream | mitigate | `ALFREDAdapter.fetch()` filters `realtime_start <= as_of` BEFORE returning rows; `drop_duplicates(subset=['event_time', 'series_id'], keep='last')` deduplicates by event+series, keeping latest vintage within the as_of window. `test_alfred_corrected_release_dedup` proves the filter works. |
| T-5.4-04 | Repudiation | Promotion audit log (`catalog-promotions.jsonl`) missing entries for macro entries | mitigate | Task 4.5 uses `promote_generated_entry.py --execute` which atomically: (a) re-runs validator; (b) optionally runs live test; (c) moves the file; (d) emits audit JSONL line. All-or-nothing — if step (c) fails, step (d) is not reached. |
| T-5.4-05 | Denial of Service | FRED rate limit (120 req/60sec) exhausted by a single client; subsequent queries fail | accept | v0.2 local-first stdio server with a single user → unlikely to hit. Adapter does not actively rate-limit. Catalog YAML documents the limit; v0.3+ hosted mode adds backoff. |
| T-5.4-06 | Tampering | Wrong vertical chosen at Task 4.0 (sports despite legal blockers) | mitigate | USER_DECISION_GATE checkpoint surfaces all evidence; user explicitly confirms; `.planning/.../05-04-VERTICAL-DECISION.md` records the decision + risk acceptance language if sports chosen. Reviewer prompt references this decision file. |
| T-5.4-07 | Tampering | New `tradewinds-macro` distribution accidentally ships `tradewinds/__init__.py` (PKG-02 violation) | mitigate | `uv build packages/macro/` + `unzip -l` check in Task 4.1; static guard via grep in pre-merge. Same pattern as packages/mcp PKG-02 enforcement in PLAN-01. |
| T-5.4-08 | Elevation of Privilege | n/a | accept | No new privilege boundaries; FRED_API_KEY is a single-scope token. |
</threat_model>

<verification>
## Plan-Level Checks

| Check | Command | Expected |
|-------|---------|----------|
| Vertical decision recorded | `test -f .planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md` | exit 0 |
| packages/macro/ built | `uv build packages/macro/` | exit 0 |
| Wheel does NOT contain tradewinds/__init__.py | `unzip -l packages/macro/dist/*.whl \| grep -c "^.*tradewinds/__init__.py$"` | 0 |
| FREDAdapter registers required env var | `grep -c "FRED_API_KEY" packages/macro/src/tradewinds_macro/catalog/fred.py` | ≥ 1 |
| ALFRED vintage filter applied | `grep -c "realtime_start.*as_of" packages/macro/src/tradewinds_macro/catalog/alfred.py` | ≥ 1 |
| KALSHI_MACRO_SETTLEMENT_SOURCES has ≥ 5 entries | `python -c "from tradewinds_macro.catalog.kalshi_macro import KALSHI_MACRO_SETTLEMENT_SOURCES; assert len(KALSHI_MACRO_SETTLEMENT_SOURCES) >= 5"` | exit 0 |
| KALSHI_MACRO only uses first-party sources | `python -c "from tradewinds_macro.catalog.kalshi_macro import KALSHI_MACRO_SETTLEMENT_SOURCES; sources = set(v[0] for v in KALSHI_MACRO_SETTLEMENT_SOURCES.values()); assert sources <= {'bls.direct', 'bea.direct', 'fed.direct'}"` | exit 0 |
| 10 catalog entries in catalog/ | `python -c "from tradewinds_mcp.catalog import CatalogLoader; assert len(CatalogLoader.from_dir('packages/mcp/catalog/')) == 10"` | exit 0 |
| 0 entries remaining in _generated/ | `ls packages/mcp/catalog/_generated/*.yaml 2>/dev/null \| wc -l` | 0 |
| Bridge dispatches macro source IDs | `grep -c "from tradewinds_macro.catalog import" packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` | 1 |
| Full MCP + macro fast suite | `uv run pytest packages/mcp/tests/ packages/macro/tests/ -m "not live" -q` | exit 0 |
| Coverage tradewinds_mcp ≥ 85% | `uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q \| grep TOTAL` | ≥ 85% |
| Coverage tradewinds_macro ≥ 80% | `uv run pytest --cov=tradewinds_macro --cov-branch packages/macro/tests/ -q \| grep TOTAL` | ≥ 80% |
| Pre-commit hooks | `uv run pre-commit run --all-files` | exit 0 |
| 2-reviewer loop | (manual) | PASS x2 |

## Static Regression Guards

```bash
# api_key never leaks into committed cassettes
grep -rE "api_key=[a-f0-9]{32}" packages/macro/tests/cassettes/ && echo "FAIL: API key leaked into cassette" || echo "OK"

# Vintage filter present
grep -E "rt_start > as_of" packages/macro/src/tradewinds_macro/catalog/alfred.py || echo "FAIL: ALFRED vintage filter missing"

# Promotion left no _generated/ residue
test -z "$(ls packages/mcp/catalog/_generated/*.yaml 2>/dev/null)" || echo "FAIL: catalog/_generated/ still has unpromoted entries"

# kalshi.macro source pattern matches kalshi.weather behavior (raises SourceUnavailableError)
grep -c "kalshi\\." packages/mcp/src/tradewinds_mcp/_adapter_bridge.py | grep -E "^[2-9]" || echo "FAIL: kalshi prefix dispatch missing"
```
</verification>

<success_criteria>
- [ ] Task 4.0 USER_DECISION_GATE resolved; `.planning/phases/05-mcp-data-platform/05-04-VERTICAL-DECISION.md` records the choice + rationale.
- [ ] MCP-05 (full): multi-vertical proof shipped — weather + macro (or user-chosen alternative). At least one non-weather vertical exists as a catalog entries + adapter atop the same temporal-safety layer.
- [ ] MCP-10 (full, with PLAN-02): 10 catalog entries in `packages/mcp/catalog/` (7 weather from PLAN-02 + 3 macro from this plan: fred.archive, alfred.archive, kalshi.macro).
- [ ] `tradewinds-macro==0.2.0` distribution builds with no PKG-02 namespace collision; ships FREDAdapter + ALFREDAdapter + KalshiMacroContractSpec.
- [ ] `FREDAdapter.fetch(series_id, start, end)` returns canonical schema.observation.v1 rows; raises `SourceUnavailableError` with registration URL when `FRED_API_KEY` missing.
- [ ] `ALFREDAdapter.fetch(series_id, start, end, as_of)` is vintage-aware: `knowledge_time == realtime_start`; filters `realtime_start <= as_of`; dedup by `(event_time, series_id)` keeping latest vintage in-window (Pitfall I.7 mitigated).
- [ ] `KalshiMacroContractSpec.resolve(ticker, date)` returns settlement source from `KALSHI_MACRO_SETTLEMENT_SOURCES` dict (only `{bls.direct, bea.direct, fed.direct}` sources allowed; assertion at import time).
- [ ] `_adapter_bridge` extension: `fred.*` / `alfred.*` dispatch to `tradewinds_macro.catalog.get_adapter`; `kalshi.macro` raises with consistent "use markets module directly" message; weather dispatch unchanged.
- [ ] 3 catalog YAMLs went through Wave 3 pipeline: scaffold → fill 5 layers → local validator green → promotion via `promote_generated_entry.py --execute` → audit JSONL entry → file moved from `_generated/` to `catalog/`.
- [ ] Full MCP + macro fast suite green: `uv run pytest packages/mcp/tests/ packages/macro/tests/ -m "not live" -q` exits 0.
- [ ] Branch coverage `tradewinds_mcp` ≥ 85%; `tradewinds_macro` ≥ 80%.
- [ ] Pre-commit + pre-push hooks green; no `--no-verify`.
- [ ] 2-reviewer loop PASS x2 in ≤ 3 iterations.
- [ ] Branch `phase-5/wave-4/vertical-macro` merged to `main` via `git merge --no-ff`.
</success_criteria>

<output>
After completion, create `.planning/phases/05-mcp-data-platform/05-04-SUMMARY.md` documenting:

- USER_DECISION_GATE outcome — which vertical, deviation from researcher recommendation (if any)
- MCP-05 + MCP-10 (macro portion) delivered
- 3 catalog entries promoted (paths, sha256 from promotion audit)
- _adapter_bridge extension diff summary
- Coverage tradewinds_mcp / tradewinds_macro
- 2-reviewer loop verdict
- Sample-data live test results (if run manually pre-publish)
- Commit hashes
- Merge commit hash on `main`
- Time spent
- Downstream signal for PLAN-05 (integration + release): all 10 catalog entries are queryable; multi-vertical proof complete; PLAN-05 runs JSON-RPC subprocess + deterministic-replay over the full 10-entry surface; v0.2.0 ship gate.
</output>
