---
phase: 05-mcp-data-platform
plan: 02
type: execute
wave: 2
duration: 2-3 days Claude execution; single lane
waves: 1
depends_on: [phase-05-mcp-data-platform/PLAN-01-mcp-server-skeleton-temporal-middleware]
branch_strategy: per-wave; one sub-branch off `main` (`phase-5/wave-2/catalog-format-weather`); 2-reviewer loop (codex `high` + python-architect); merges to `main` after Wave 2 in-process test confirms `list_sources` / `describe_source` / `query` / `ingest` all dispatch through the catalog
requirements:
  - MCP-02    # full — catalog stores 5-layer context (schema_semantics / temporal_rules / quality_notes / relationship_mappings / operational_context)
  - MCP-10    # PARTIAL (weather portion — 7 of 10 entries: iem.archive, iem.live, awc.live, ghcnh.archive, cli.archive, iem.forecasts, kalshi.weather). Macro 3-of-10 entries ship in PLAN-04.
autonomous: false   # Pre-merge requires human review of the 7 YAML catalog entries' `temporal_rules` formulas (load-bearing for MCP-04 enforcement) + the meta-schema's `additionalProperties: false` policy
files_modified:
  # Catalog meta-schema + loader
  - packages/mcp/catalog/_schema/catalog_entry.schema.json                            # NEW — JSON Schema 2020-12 validating shape of every per-source catalog YAML; defines 5-layer block
  - packages/mcp/catalog/_schema/__placeholder.md                                     # NEW — README pointing at the meta-schema; explains promotion gate
  - packages/mcp/src/tradewinds_mcp/catalog.py                                        # NEW — CatalogLoader.from_dir(); per-source YAML files; jsonschema validation on load; eager-build registry; CatalogEntry dataclass
  - packages/mcp/src/tradewinds_mcp/_catalog_entry_types.py                           # NEW — Pydantic models mirroring the meta-schema (TemporalRules / QualityNote / RelationshipMapping / OperationalContext / CatalogEntry); used at load time for type-safe access
  # 7 weather catalog YAML files (MCP-10 weather portion)
  - packages/mcp/catalog/iem.archive.yaml                                             # NEW — IEM ASOS archive (Phase 2 adapter), schema.observation.v1
  - packages/mcp/catalog/iem.live.yaml                                                # NEW — IEM ASOS live (Phase 2 adapter), schema.observation.v1
  - packages/mcp/catalog/awc.live.yaml                                                # NEW — AWC METAR JSON (Phase 2 adapter), schema.observation.v1
  - packages/mcp/catalog/ghcnh.archive.yaml                                           # NEW — GHCNh hourly historical (Phase 2 adapter), schema.observation.v1
  - packages/mcp/catalog/cli.archive.yaml                                             # NEW — NWS CLI daily settlement (Phase 2 adapter), schema.settlement.cli.v1
  - packages/mcp/catalog/iem.forecasts.yaml                                           # NEW — IEM MOS forecasts (Phase 2 adapter — note Phase 2 deferred MOS parser to Phase 3 per Phase 2 PLAN.md Wave 1 open Q1 resolution; if MOS not yet shipped, mark `status: "wip"` and leave full wiring for Phase 5 Wave-2-followup); schema.forecast.iem_mos.v1
  - packages/mcp/catalog/kalshi.weather.yaml                                          # NEW — Kalshi NHIGH/NLOW contract specs (Phase 2 markets); status: live; no schema (contract spec, not observation data)
  - packages/mcp/catalog/_generated/.gitkeep                                          # NEW — empty marker; Wave 3 fills this dir with agent-generated configs awaiting review
  # Adapter wiring — connect catalog entries to Phase 2 weather adapters
  - packages/mcp/src/tradewinds_mcp/_adapter_bridge.py                                # NEW — maps catalog entry's `extraction_config.adapter` to the Phase 2 catalog registry get_adapter(source_id); decouples MCP catalog from weather adapter import details
  # Tool wiring — Wave 1 stubs become real Wave 2 dispatch
  - packages/mcp/src/tradewinds_mcp/tools/list_sources.py                             # MODIFY — read from CatalogLoader instead of returning ['_placeholder']
  - packages/mcp/src/tradewinds_mcp/tools/describe_source.py                          # MODIFY — return real CatalogEntry; raise SourceUnavailableError for unknown
  - packages/mcp/src/tradewinds_mcp/tools/query.py                                    # MODIFY — call _adapter_bridge.fetch(source_id, filters) instead of empty placeholder df
  - packages/mcp/src/tradewinds_mcp/tools/ingest.py                                   # MODIFY — call _adapter_bridge.ingest(source_id, filters, dest_dir); writes to local cache via Phase 2 cache module
  - packages/mcp/src/tradewinds_mcp/server.py                                         # MODIFY — load CatalogLoader at module level; pass to tool register() calls
  # Tests
  - packages/mcp/tests/test_catalog_meta_schema.py                                    # NEW — meta-schema validates each weather YAML; rejects malformed entries
  - packages/mcp/tests/test_catalog_loader.py                                         # NEW — CatalogLoader.from_dir() reads all 7 entries; rejects malformed; ignores _generated/ subdir
  - packages/mcp/tests/test_catalog_entry_types.py                                    # NEW — CatalogEntry Pydantic models roundtrip YAML
  - packages/mcp/tests/test_tools_dispatch_real_catalog.py                            # NEW — list_sources returns the 7 real source IDs; describe_source('iem.archive') returns 5-layer entry; query('iem.archive', as_of=...) calls into Phase 2 adapter (recorded fixture replays)
  - packages/mcp/tests/test_yaml_safe_load.py                                         # NEW — CatalogLoader rejects YAML with !!python/object tags (security pitfall, per RESEARCH.md §B.2 yaml.safe_load only)
  # Optional Wave 2 helper: a single regression test that verifies sample-data round-trip for each weather entry (live; @pytest.mark.live)
  - packages/mcp/tests/test_catalog_sample_data_roundtrip.py                          # NEW — @pytest.mark.live; for each weather catalog entry, fetch 1 row, validate against declared schema, serialize TOON; CI skips, manual pre-publish runs
must_haves:
  truths:
    - "`packages/mcp/catalog/_schema/catalog_entry.schema.json` is a valid JSON Schema (2020-12 draft) that validates every per-source YAML file under `packages/mcp/catalog/*.yaml`."
    - "The meta-schema mandates 5 top-level blocks (`schema_semantics`, `temporal_rules`, `quality_notes`, `relationship_mappings`, `operational_context`) PLUS `source_id`, `display_name`, `status` — `additionalProperties: false` rejects any catalog entry with typos or extra fields."
    - "`additionalProperties: false` is enforced at the TOP level (catches typos like `temporal_rule` vs `temporal_rules`); within each block the policy is documented (RESEARCH.md §B leaves room for nested operational hints — top-level strict, nested permissive)."
    - "All 7 weather catalog YAML files validate against the meta-schema via `jsonschema` CLI — `jsonschema -i <yaml-as-json> _schema/catalog_entry.schema.json` returns success for each."
    - "Each YAML file is loaded via `yaml.safe_load` ONLY (per RESEARCH.md §B.2 security note). `test_yaml_safe_load_rejects_python_tags` asserts a YAML with `!!python/object/apply:os.system` is rejected before evaluation."
    - "`CatalogLoader.from_dir('packages/mcp/catalog/')` returns 7 entries (`iem.archive`, `iem.live`, `awc.live`, `ghcnh.archive`, `cli.archive`, `iem.forecasts`, `kalshi.weather`); the `_generated/` subdir is SKIPPED (Wave 3 territory); the `_schema/` subdir is SKIPPED."
    - "Each catalog entry's `schema_semantics.schema_id` resolves to a registered Phase 2 canonical schema (`schema.observation.v1` / `schema.forecast.iem_mos.v1` / `schema.settlement.cli.v1` / `n/a` for kalshi.weather contract spec). `test_catalog_schema_ids_resolve` asserts via the Phase 2 REGISTRY."
    - "Each catalog entry's `temporal_rules.knowledge_time_formula` is a human-readable string that documents the relationship between event_time and knowledge_time — for `iem.archive` it MUST cite ASOS report_delay (RESEARCH.md §B catalog skeleton)."
    - "`MCP server.py` loads `CatalogLoader.from_dir('packages/mcp/catalog')` at module-import time. `list_sources()` now returns `sorted(catalog.all_source_ids())` — 7 entries."
    - "`describe_source('iem.archive')` returns `DescribeSourceResponse(source_id='iem.archive', description=<from display_name + first quality_note>, schema_id='schema.observation.v1', catalog_entry=<full 5-layer YAML loaded as dict>)`. Unknown source → `SourceUnavailableError` with the list of known IDs."
    - "`describe_source('nonexistent')` raises `SourceUnavailableError` whose `.to_dict()` JSON-RPC payload includes the list of available sources (MCP-07 reuse of Phase 2 exception hierarchy)."
    - "`query('iem.archive', as_of=datetime(2024,1,15,tzinfo=UTC), filters={'station':'KNYC'})` calls into Phase 2's `tradewinds.weather.catalog.get_adapter('iem.archive').fetch(...)` via the `_adapter_bridge`, runs `Dataset.at_time(as_of)` filter (middleware-enforced), serializes via TOON, logs to audit. Result envelope has non-empty `data`. Tested via Phase 2 recorded fixtures."
    - "`ingest('iem.archive', as_of=datetime(2024,1,15,tzinfo=UTC), filters={'station':'KNYC'})` calls Phase 2 adapter; writes rows to local cache; returns `IngestResponse(rows_ingested=<N>)`. Cache lives at `$HOME/.tradewinds/cache/v1/observations/<station>/<year>/<month>.parquet` per Phase 1 CACHE-01."
    - "The `_adapter_bridge` does NOT directly import from `tradewinds.weather._fetchers` — it goes through the Phase 2 public catalog registry `tradewinds.weather.catalog.get_adapter(source_id)` (per RESEARCH.md §H.3 invariant: `packages/mcp/` must depend only on the canonical schemas + catalog registry, not internal fetcher paths)."
    - "META-TEST `test_meta_schema_top_level_strict`: the meta-schema's top-level `additionalProperties` is `false`. Asserted by loading the meta-schema and inspecting the literal value — guards against a future maintainer relaxing the schema and silently allowing typo'd field names."
    - "`uv run pytest packages/mcp/tests/ -m 'not live' -q` exits 0 with all tests passing (existing Wave 1 + new Wave 2 = ~30+ tests)."
    - "`uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m 'live' -q` runs successfully WHEN run with `-m live` (live tests excluded by default per CLAUDE.md CI-04)."
    - "Pre-commit hooks green (no `--no-verify`); ruff lint + format green."
  artifacts:
    - path: packages/mcp/catalog/_schema/catalog_entry.schema.json
      provides: "JSON Schema 2020-12 meta-schema validating per-source catalog YAML files; 5 mandatory blocks + source_id + display_name + status; top-level additionalProperties: false"
      contains: "\"additionalProperties\": false"
      min_lines: 80
    - path: packages/mcp/src/tradewinds_mcp/catalog.py
      provides: "CatalogLoader.from_dir(path); CatalogEntry dataclass; all_source_ids(); lookup(source_id) returning CatalogEntry; jsonschema validation on load; yaml.safe_load only"
      contains: "yaml.safe_load"
      min_lines: 80
    - path: packages/mcp/catalog/iem.archive.yaml
      provides: "IEM ASOS archive — 5-layer context entry; schema.observation.v1; knowledge_time_formula = 'observed_at + report_delay'; status: live"
      contains: "schema_id: schema.observation.v1"
    - path: packages/mcp/catalog/cli.archive.yaml
      provides: "NWS CLI daily settlement — 5-layer context entry; schema.settlement.cli.v1; quality_notes include CLI preliminary/final/correction dedup (Phase 2 CATALOG-03)"
      contains: "settlement_finality"
    - path: packages/mcp/catalog/kalshi.weather.yaml
      provides: "Kalshi NHIGH/NLOW contract spec catalog entry; references KALSHI_SETTLEMENT_STATIONS hard-coded list (Phase 2 MARKETS-01); status: live"
      contains: "kalshi_nhigh"
    - path: packages/mcp/src/tradewinds_mcp/_adapter_bridge.py
      provides: "Maps CatalogEntry.extraction_config.adapter → Phase 2 tradewinds.weather.catalog.get_adapter(source_id); zero dependency on tradewinds.weather._fetchers internals"
      contains: "from tradewinds.weather.catalog import get_adapter"
    - path: packages/mcp/tests/test_catalog_meta_schema.py
      provides: "Asserts meta-schema rejects malformed entries (missing block, typo'd field, extra field); validates all 7 real weather entries"
      contains: "additionalProperties"
    - path: packages/mcp/tests/test_tools_dispatch_real_catalog.py
      provides: "list_sources/describe_source/query/ingest now dispatch through the real catalog (not _placeholder); 7 source IDs visible; recorded-fixture-replay for iem.archive query"
      contains: "test_list_sources_returns_seven_weather_entries"
  key_links:
    - from: packages/mcp/catalog/iem.archive.yaml
      to: packages/core/src/tradewinds/core/schemas/observation.py
      via: "schema_semantics.schema_id field references the Phase 2 canonical schema by ID"
      pattern: "schema_id: schema\\.observation\\.v1"
    - from: packages/mcp/src/tradewinds_mcp/_adapter_bridge.py
      to: packages/weather/src/tradewinds/weather/catalog/__init__.py
      via: "get_adapter(source_id) dispatch through Phase 2 eager-registered catalog registry"
      pattern: "from tradewinds\\.weather\\.catalog import get_adapter"
    - from: packages/mcp/src/tradewinds_mcp/tools/query.py
      to: packages/mcp/src/tradewinds_mcp/_adapter_bridge.py
      via: "bridge.fetch(source_id, filters) is called inside the query tool body; returns DataFrame ready for Dataset.at_time"
      pattern: "bridge\\.fetch\\("
    - from: packages/mcp/src/tradewinds_mcp/catalog.py
      to: packages/mcp/catalog/_schema/catalog_entry.schema.json
      via: "jsonschema validation against the meta-schema on every load — load fails fast if any YAML is malformed"
      pattern: "jsonschema\\.validate"
---

<objective>
**Wave 2 wires the 5-layer per-source catalog into the running MCP server, replacing Wave 1's `_placeholder` stubs.**

This plan delivers:
1. **Catalog meta-schema** (`packages/mcp/catalog/_schema/catalog_entry.schema.json`) — a JSON Schema 2020-12 document defining the 5-layer shape (per RESEARCH.md §B). Strict at top-level (`additionalProperties: false` catches typo'd field names).
2. **CatalogLoader** (`packages/mcp/src/tradewinds_mcp/catalog.py`) — reads `packages/mcp/catalog/*.yaml` via `yaml.safe_load` (Pitfall: `yaml.load` is RCE-vulnerable per RESEARCH.md §B.2); validates each entry against the meta-schema; eagerly builds a registry keyed by `source_id`.
3. **7 weather catalog YAML files** (the MCP-10 weather portion — `iem.archive`, `iem.live`, `awc.live`, `ghcnh.archive`, `cli.archive`, `iem.forecasts`, `kalshi.weather`). Each has the 5-layer context per RESEARCH.md §B example: schema_semantics, temporal_rules, quality_notes, relationship_mappings, operational_context.
4. **`_adapter_bridge`** — maps catalog `extraction_config.adapter` references to Phase 2's `tradewinds.weather.catalog.get_adapter(source_id)`. This decouples the MCP catalog from weather-fetcher internals (RESEARCH.md §H.3 invariant: "`packages/mcp/` MUST NOT depend on `tradewinds.weather._fetchers` directly").
5. **Tool wiring** — Wave 1's `_placeholder` returns become real catalog-backed dispatch: `list_sources` returns 7 IDs, `describe_source` returns the full YAML entry, `query` and `ingest` route through `_adapter_bridge.fetch()`.

**The MCP-10 commitment:** 7 of 10 pre-indexed catalog entries land here (weather). The remaining 3 (`fred.archive`, `alfred.archive`, `kalshi.macro`) ship in PLAN-04 after the user confirms the macro-vertical choice in Wave 4's USER_DECISION_GATE.

**Key constraints honored:**
- CONTEXT.md catalog format lock: per-source files at `packages/mcp/catalog/`; `_generated/` subdir for agent-generated entries (Wave 3 territory).
- RESEARCH.md §B.2 lock: YAML + JSON-Schema meta-schema (not TOML, not custom DSL); `yaml.safe_load` only.
- RESEARCH.md §I.4 mitigation: catalog promotion requires sample-data round-trip — Wave 2 ships the `test_catalog_sample_data_roundtrip.py` infrastructure (`@pytest.mark.live`, CI-skipped, manual pre-publish run); Wave 3 makes this gate mandatory for `_generated/` → `catalog/` promotion.
- Phase 2 MOS forecast parser status: per Phase 2 Wave 1 Open Q1 resolution, MOS parser was deferred to Phase 3. If `tradewinds.weather.catalog.get_adapter('iem.forecasts')` is not yet shipped at the time Wave 2 runs, mark `iem.forecasts.yaml` `status: wip` and leave its `_adapter_bridge` wiring out — it can be promoted to `status: live` in a follow-up Phase 5 sub-task once Phase 3 ships MOS. Document the wip status in the catalog README.

**Out of scope (deferred):**
- Wave 3: agent-generated connector pipeline; `_generated/` → `catalog/` promotion CI gates.
- Wave 4: macro vertical catalog entries (`fred.archive`, `alfred.archive`, `kalshi.macro`).
- Wave 4: end-to-end JSON-RPC subprocess integration tests; deterministic-replay tests over real queries.

**Output:** The MCP server, after Wave 2 merges to `main`, is functionally complete for the 7 weather catalog entries: `list_sources`, `describe_source`, `query`, `ingest` all return real data through the temporal-safety middleware. Wave 3 builds the agent-connector pipeline on top of this catalog format.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phase-05-mcp-data-platform/VISION.md
@.planning/phase-05-mcp-data-platform/CONTEXT.md
@.planning/phase-05-mcp-data-platform/RESEARCH.md
@.planning/phase-05-mcp-data-platform/05-01-SUMMARY.md
@./CLAUDE.md
</execution_context>

<interfaces>
From Wave 1 (PLAN-01 output — at the time Wave 2 begins these exist):

```python
# tradewinds_mcp.server
mcp: FastMCP  # named "tradewinds"; 5 tools registered as stubs; temporal middleware attached
_audit: AuditLogger

# tradewinds_mcp.envelopes
class QueryResponse(BaseModel): format: str; data: str; schema_id: str; audit_id: str
class IngestResponse(BaseModel): format: str; data: str; schema_id: str; audit_id: str; rows_ingested: int
class ListSourcesResponse(BaseModel): sources: list[str]
class DescribeSourceResponse(BaseModel): source_id: str; description: str; schema_id: str; catalog_entry: dict
class SchemaResponse(BaseModel): schema_id: str; schema_json: dict

# tradewinds_mcp.tools.{query,ingest,list_sources,describe_source,get_schema}
def register(mcp, audit) -> None: ...  # each tool exposes this; Wave 2 may extend signature to accept catalog
```

From Phase 2 (`tradewinds.weather.catalog`):

```python
# tradewinds.weather.catalog (eager-import registry per Phase 2 PLAN.md Wave 3)
def get_adapter(source_id: str) -> WeatherAdapter: ...
# Returns instance of IEMAdapter / AWCAdapter / CLIAdapter / GHCNhAdapter

class WeatherAdapter(Protocol):
    SUPPORTED_SOURCES: list[str]  # class-level
    def fetch(self, *, station: str, start: date, end: date, **kwargs) -> pd.DataFrame: ...
    # Emits canonical schema rows with event_time / knowledge_time / source / retrieved_at columns
```

From Phase 2 markets (`tradewinds.markets.catalog`):
```python
from tradewinds.markets.catalog import KALSHI_SETTLEMENT_STATIONS
from tradewinds.markets.catalog import kalshi_nhigh, kalshi_nlow
# kalshi_nhigh.resolve(contract_id, date) -> (settlement_source, settlement_station)
```
</interfaces>

<phase_summary>

**Goal:** Land the 5-layer catalog meta-schema + loader + 7 weather YAML entries; wire Wave 1 tool stubs to dispatch through the catalog via `_adapter_bridge`.

**Branch:** `phase-5/wave-2/catalog-format-weather` off `main`.

**TDD order:** RED → GREEN → REFACTOR per task. Each task writes failing tests FIRST.

**Atomic commit boundaries:**
- Task 2.1 (meta-schema + 7 YAML files) → 2 commits (RED schema-validation tests + GREEN schema + YAMLs)
- Task 2.2 (CatalogLoader + Pydantic types) → 2 commits
- Task 2.3 (_adapter_bridge + tool wiring) → 2 commits
- Task 2.4 (sample-data live-test scaffolding) → 1 commit
- Task 2.5 (pre-merge gate + docs) → 1 commit

**2-reviewer loop per REVIEW-DISCIPLINE.md:** codex `high` + python-architect. Never-skip applies (catalog files are schema-fragment-bearing per REVIEW-DISCIPLINE.md "Never skip" list — wrong `schema_id` literal in iem.archive.yaml propagates straight to wrong-schema validation failures at runtime).

**Pre-merge gate (mandatory):**
1. All Wave 1 + Wave 2 tests green: `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0.
2. Meta-schema strict-mode test green: `test_meta_schema_top_level_strict` confirms `additionalProperties: false` at top level.
3. All 7 YAMLs validate against the meta-schema (Task 2.1 test).
4. `list_sources()` returns the 7 source IDs alphabetized.
5. `describe_source('iem.archive')` returns a non-empty `catalog_entry` dict.
6. `query('iem.archive', as_of=..., filters={'station':'KNYC'})` runs without raising; envelope `data` is non-empty TOON (recorded-fixture replay against Phase 2 adapter).
7. Pre-commit + pre-push hooks green.
8. 2-reviewer loop returns PASS x2 in ≤ 3 iterations.

</phase_summary>

<tasks>

<task type="auto" tdd="true">
  <name>Task 2.1: Meta-schema + 7 weather YAML catalog entries (RED tests FIRST)</name>
  <files>packages/mcp/catalog/_schema/catalog_entry.schema.json, packages/mcp/catalog/iem.archive.yaml, packages/mcp/catalog/iem.live.yaml, packages/mcp/catalog/awc.live.yaml, packages/mcp/catalog/ghcnh.archive.yaml, packages/mcp/catalog/cli.archive.yaml, packages/mcp/catalog/iem.forecasts.yaml, packages/mcp/catalog/kalshi.weather.yaml, packages/mcp/catalog/_generated/.gitkeep, packages/mcp/tests/test_catalog_meta_schema.py</files>
  <implements>MCP-02 (catalog format + 5-layer context), MCP-10 (weather portion)</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§B.1 Singer/dlt prior art; §B.2 YAML + JSON-Schema-meta recommendation; §B.2 yaml.safe_load only; full catalog YAML skeleton at lines 707-751; §E.3 top-10 pre-indexed entries — 7 weather + 3 macro)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — per-source files at packages/mcp/catalog/; _generated/ subdir; locked YAML format)
    - .planning/phase-02-core-primitives-catalog-adapters/PLAN.md (Wave 3 — weather adapter source IDs: iem.archive, iem.live, awc.live, cli.archive, ghcnh.archive, iem.forecasts; Wave 4 — Kalshi NHIGH/NLOW contract specs; KALSHI_SETTLEMENT_STATIONS list with 20 city tickers)
    - packages/core/src/tradewinds/core/schemas/observation.py + forecast.py + settlement.py (Phase 2 — confirm schema_id strings: schema.observation.v1, schema.forecast.iem_mos.v1, schema.settlement.cli.v1)
    - packages/weather/src/tradewinds/weather/catalog/iem.py + awc.py + cli.py + ghcnh.py (Phase 2 — adapter source IDs declared via SUPPORTED_SOURCES; cross-reference)
  </read_first>
  <behavior>
    Tests to write FIRST in `packages/mcp/tests/test_catalog_meta_schema.py` (RED, 10 tests):

    1. `test_meta_schema_loads_as_valid_jsonschema`: `import jsonschema; with open('packages/mcp/catalog/_schema/catalog_entry.schema.json') as f: schema = json.load(f); jsonschema.Draft202012Validator.check_schema(schema)` — does not raise.
    2. `test_meta_schema_top_level_strict`: `schema['additionalProperties'] is False` — top level rejects unknown fields (META-INVARIANT against typo'd block names).
    3. `test_meta_schema_required_fields`: `set(schema['required']) >= {'source_id', 'display_name', 'status', 'schema_semantics', 'temporal_rules', 'quality_notes', 'relationship_mappings', 'operational_context'}` — 8 required fields.
    4. `test_meta_schema_status_enum`: `schema['properties']['status']['enum'] == ['live', 'wip', 'retired']` — three states; `wip` is the iem.forecasts case if MOS not yet shipped.
    5. `test_all_seven_weather_yamls_validate`: For each of `iem.archive, iem.live, awc.live, ghcnh.archive, cli.archive, iem.forecasts, kalshi.weather`, load via `yaml.safe_load` and validate against the meta-schema. All 7 must pass.
    6. `test_malformed_entry_missing_block_rejected`: a hand-crafted YAML dict missing `temporal_rules` is rejected by jsonschema.validate with a clear error message naming `temporal_rules` as required.
    7. `test_malformed_entry_extra_top_level_field_rejected`: a YAML with a typo'd field `temporal_rule` (singular instead of plural) is rejected (additionalProperties: false catches it).
    8. `test_status_wip_allowed_for_iem_forecasts`: `iem.forecasts.yaml`'s status MAY be `wip` (if Phase 2 hasn't shipped MOS parser yet) OR `live` (if it has). Either is meta-schema-valid.
    9. `test_seven_yaml_source_ids_match_filenames`: For each YAML file, the file stem matches the `source_id` inside (e.g., `iem.archive.yaml` has `source_id: iem.archive`).
    10. `test_all_schema_ids_resolve_in_phase2_registry`: for each weather entry except `kalshi.weather`, `entry['schema_semantics']['schema_id']` is one of `schema.observation.v1` / `schema.forecast.iem_mos.v1` / `schema.settlement.cli.v1`. `kalshi.weather` is allowed `schema_id: contract_spec.kalshi_nhigh.v1` OR no schema_id (contract spec, not row schema).

    Run `uv run pytest packages/mcp/tests/test_catalog_meta_schema.py -x` — MUST fail (no schema, no YAMLs yet). Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 10 tests above. Commit RED.

    Step 2 — Create `packages/mcp/catalog/_schema/catalog_entry.schema.json` (JSON Schema 2020-12). The shape:

    ```json
    {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": "https://github.com/Tarabcak/tradewinds/blob/main/packages/mcp/catalog/_schema/catalog_entry.schema.json",
      "title": "tradewinds-mcp catalog entry",
      "description": "Per-source 5-layer context document; one file per source under packages/mcp/catalog/*.yaml. Strict top-level shape (additionalProperties: false) catches typo'd block names like 'temporal_rule' (singular). Nested blocks are permissive to allow domain-specific notes.",
      "type": "object",
      "additionalProperties": false,
      "required": [
        "source_id",
        "display_name",
        "status",
        "schema_semantics",
        "temporal_rules",
        "quality_notes",
        "relationship_mappings",
        "operational_context"
      ],
      "properties": {
        "$schema": { "type": "string", "description": "Optional schema-URI reference for editor support." },
        "source_id": { "type": "string", "pattern": "^[a-z][a-z0-9._-]*$", "description": "Stable canonical ID for this source. Matches the YAML filename stem. Examples: iem.archive, fred.archive, kalshi.macro." },
        "display_name": { "type": "string", "minLength": 1 },
        "status": { "type": "string", "enum": ["live", "wip", "retired"], "description": "live = production-ready; wip = under development; retired = no longer fetchable, query/ingest must error" },
        "schema_semantics": {
          "type": "object",
          "required": ["schema_id"],
          "properties": {
            "schema_id": { "type": "string", "description": "Canonical schema ID from tradewinds.core.schemas (or contract_spec.* for market specs)" },
            "fields": {
              "type": "object",
              "description": "Per-field human-readable semantics. Keys are field names; values describe what the field MEANS in domain terms (not just the type — the type lives in the schema_id-referenced canonical schema)."
            }
          }
        },
        "temporal_rules": {
          "type": "object",
          "required": ["event_time_field", "knowledge_time_field", "knowledge_time_formula", "backfill_behavior"],
          "properties": {
            "event_time_field": { "type": "string", "description": "Column name in the canonical schema that holds the event timestamp." },
            "knowledge_time_field": { "type": "string", "description": "Column name in the canonical schema that holds the knowledge timestamp." },
            "knowledge_time_formula": { "type": "string", "description": "Human-readable formula for how knowledge_time is computed from raw API response. Reviewed by humans during catalog promotion." },
            "backfill_behavior": { "type": "string", "description": "Does this source backfill past records? Critical for replay determinism." },
            "vintage_aware": { "type": "boolean", "description": "true for ALFRED-style vintage APIs; false for one-shot publishers." }
          }
        },
        "quality_notes": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 },
          "description": "Domain-knowledge notes a quant should know before using this source. E.g., known unit changes, sensor swaps, units-of-record."
        },
        "relationship_mappings": {
          "type": "object",
          "required": ["joins_to"],
          "properties": {
            "joins_to": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["source", "on"],
                "properties": {
                  "source": { "type": "string", "description": "Catalog source_id this source joins to" },
                  "on": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
                  "note": { "type": "string" }
                }
              },
              "description": "Pre-declared join keys (allow-list per RESEARCH.md §I.8 pitfall mitigation). Empty array means 'no pre-declared joins' (acceptable)."
            }
          }
        },
        "operational_context": {
          "type": "object",
          "required": ["auth"],
          "properties": {
            "endpoint": { "type": "string", "description": "Base URL or API host" },
            "rate_limit": { "type": "string", "description": "Documented or empirical rate limit" },
            "auth": { "type": "string", "description": "'none', 'api_key:ENV_VAR_NAME', or 'oauth'" },
            "pagination": { "type": "string", "description": "Pagination strategy if any" },
            "http_timeout_seconds": { "type": "number" }
          }
        },
        "extraction_config": {
          "type": "object",
          "description": "OPTIONAL: pointer to Phase 2 adapter or future agent-generated extraction config",
          "properties": {
            "adapter": { "type": "string", "description": "Phase 2 catalog adapter source ID (e.g., iem.archive) OR _generated/<filename>.yaml reference" },
            "config_file": { "type": "string", "description": "Optional path to generated extraction config" }
          }
        }
      }
    }
    ```

    Step 3 — Create the 7 weather YAML catalog entries. Use the verbatim example from RESEARCH.md lines 707-751 as the template for `iem.archive.yaml`; adapt for the other 6. Each MUST have all 5 layers populated (no empty arrays / no empty strings — quality_notes has at least 1 entry).

    Example for `packages/mcp/catalog/iem.archive.yaml` (verbatim from RESEARCH.md §B.2 example with tweaks for our exact field names):

    ```yaml
    $schema: ./_schema/catalog_entry.schema.json
    source_id: iem.archive
    display_name: "Iowa Environmental Mesonet — ASOS observations (archive)"
    status: live

    schema_semantics:
      schema_id: schema.observation.v1
      fields:
        tmpf: "Air temperature, instantaneous reading at observation_time. Fahrenheit. NOT a daily high/low — this is a point-in-time METAR observation."
        relh: "Relative humidity 0-100. NULL during station outages — do NOT impute from neighbors."
        observed_at: "Event time (UTC); when the sensor recorded the value"
        knowledge_time: "Knowledge time (UTC); when the record became available downstream of report_delay"

    temporal_rules:
      event_time_field: observed_at
      knowledge_time_field: knowledge_time
      knowledge_time_formula: "observed_at + report_delay (typically 5-15 min for ASOS METAR per FAA AC 150/5220-16D)"
      backfill_behavior: "Past records DO NOT change after first publish. ASOS is a one-shot publish; no vintage history."
      vintage_aware: false

    quality_notes:
      - "Pre-2007 records have inconsistent units across stations — handled in _vendor parser per Phase 1 lift."
      - "ASOS sensor changes documented in NOAA station history files; not surfaced in this stream."
      - "SPECI records (special observations triggered by weather changes) co-exist with METAR records at the same observed_at — merge policy uses observation_type priority (METAR > SPECI) per Phase 1 lift."

    relationship_mappings:
      joins_to:
        - source: ghcnh.archive
          on: ["station_id", "observed_at"]
          note: "ASOS uses ICAO codes (e.g. KNYC); GHCNh uses WBAN (e.g. 725030). station_id_map.csv resolves."
        - source: kalshi.weather
          on: ["station_id", "date"]
          note: "Kalshi NHIGH/NLOW settlement station whitelist hard-coded in tradewinds.markets.catalog.KALSHI_SETTLEMENT_STATIONS (20 entries)."

    operational_context:
      endpoint: "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
      rate_limit: "1 req/sec/IP (empirical per Phase 1.5 SOURCE-LIMITS spike)"
      auth: "none"
      pagination: "365-day calendar-aligned chunks via _iem_chunks helper (Phase 1.5)"
      http_timeout_seconds: 60

    extraction_config:
      adapter: iem.archive
    ```

    For each of the other 6 entries, adapt the same shape with the source-specific values:

    - `iem.live.yaml` (status: live, schema.observation.v1, knowledge_time_formula similar to archive but emphasizing the live cache-skip policy from CACHE-03)
    - `awc.live.yaml` (status: live, schema.observation.v1, references the Phase 1 AWC URL migration LIFT-FIX; quality_notes mention the Sept 2025 endpoint change)
    - `ghcnh.archive.yaml` (status: live, schema.observation.v1, joins_to: iem.archive on station_id + observed_at)
    - `cli.archive.yaml` (status: live, schema.settlement.cli.v1, quality_notes include preliminary/final/correction dedup + cli_data_quality enum from Phase 2 CATALOG-03 + Pitfall 16 settlement_finality)
    - `iem.forecasts.yaml` (status: **wip** if Phase 2 has NOT shipped MOS parser at the time Wave 2 runs; live if it has — verify by `python -c "from tradewinds.weather.catalog import get_adapter; get_adapter('iem.forecasts')"`; if ImportError or KeyError, set wip and document in CHANGELOG)
    - `kalshi.weather.yaml` (status: live, NO schema_semantics.schema_id pointing at a row schema; instead `schema_id: contract_spec.kalshi_nhigh.v1` (synthetic ID — see Task 2.3 for handling); quality_notes reference Kalshi's NHIGH/NLOW resolution rules + KALSHI_SETTLEMENT_STATIONS hard-coded list)

    Step 4 — Create `packages/mcp/catalog/_generated/.gitkeep` (empty marker so the dir exists in git even though Wave 2 doesn't populate it).

    Step 5 — Run `uv run pytest packages/mcp/tests/test_catalog_meta_schema.py -x -v` — all 10 tests MUST pass.

    Step 6 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Note: yaml files are not ruff-formatted but pre-commit may run yamllint. Confirm yamllint config allows multi-line strings used in quality_notes (the dash + indent pattern).

    Step 7 — Commit (GREEN): `feat(phase-5): catalog meta-schema + 7 weather YAML entries (MCP-02 + MCP-10 weather portion)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_catalog_meta_schema.py -x -v && ls packages/mcp/catalog/*.yaml | wc -l | grep -E "^7$" && ls packages/mcp/catalog/_schema/ | grep -c "catalog_entry.schema.json" | grep -E "^1$"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/catalog/_schema/catalog_entry.schema.json` returns 0
    - `python -c "import json, jsonschema; s = json.load(open('packages/mcp/catalog/_schema/catalog_entry.schema.json')); jsonschema.Draft202012Validator.check_schema(s)"` exits 0
    - `python -c "import json; s = json.load(open('packages/mcp/catalog/_schema/catalog_entry.schema.json')); assert s['additionalProperties'] is False"` exits 0
    - `ls packages/mcp/catalog/*.yaml | wc -l` returns 7
    - For each `src` in {iem.archive, iem.live, awc.live, ghcnh.archive, cli.archive, iem.forecasts, kalshi.weather}: `test -f packages/mcp/catalog/$src.yaml` returns 0
    - `grep -c "^source_id: iem.archive$" packages/mcp/catalog/iem.archive.yaml` returns 1
    - `grep -c "^status: live$" packages/mcp/catalog/iem.archive.yaml` returns 1
    - `grep -c "^source_id: cli.archive$" packages/mcp/catalog/cli.archive.yaml` returns 1
    - `grep -c "settlement_finality\|cli_data_quality" packages/mcp/catalog/cli.archive.yaml` returns ≥ 1
    - `test -f packages/mcp/catalog/_generated/.gitkeep` returns 0
    - `uv run pytest packages/mcp/tests/test_catalog_meta_schema.py -x -v` exits 0 with 10 passed
    - `uv run pre-commit run --all-files` exits 0
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    Meta-schema is valid Draft 2020-12; `additionalProperties: false` at top level. All 7 weather YAMLs exist + validate against the meta-schema. `_generated/` dir exists. 10 meta-schema tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2.2: CatalogLoader + Pydantic types + yaml.safe_load guard (RED tests FIRST)</name>
  <files>packages/mcp/src/tradewinds_mcp/catalog.py, packages/mcp/src/tradewinds_mcp/_catalog_entry_types.py, packages/mcp/tests/test_catalog_loader.py, packages/mcp/tests/test_catalog_entry_types.py, packages/mcp/tests/test_yaml_safe_load.py</files>
  <implements>MCP-02 (loader for the catalog format)</implements>
  <read_first>
    - Task 2.1 outputs (meta-schema + 7 YAML files exist)
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§B.2 yaml.safe_load only — never yaml.load; sample attack via !!python/object)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — _generated/ subdir is skipped on Wave 2 load; _schema/ subdir is skipped)
    - packages/mcp/catalog/_schema/catalog_entry.schema.json (Task 2.1 output — the validation target)
  </read_first>
  <behavior>
    Tests to write FIRST:

    `packages/mcp/tests/test_catalog_loader.py` (6 tests):

    1. `test_loader_finds_seven_entries`: `CatalogLoader.from_dir('packages/mcp/catalog/')` returns a loader whose `.all_source_ids()` is sorted and length 7. Contains `iem.archive, iem.live, awc.live, ghcnh.archive, cli.archive, iem.forecasts, kalshi.weather`.
    2. `test_loader_skips_generated_subdir`: place a malformed YAML under `tmp/_generated/bad.yaml`; loader skips it (doesn't try to validate; doesn't include in catalog).
    3. `test_loader_skips_schema_subdir`: `_schema/catalog_entry.schema.json` is NOT loaded as a catalog entry.
    4. `test_loader_validates_on_load`: place a malformed YAML (missing `temporal_rules` block) in a temp dir; `CatalogLoader.from_dir(tmp)` raises `SchemaValidationError` (Phase 2 exception) with the path of the offending file in the message.
    5. `test_loader_lookup_returns_catalog_entry`: `loader.lookup('iem.archive')` returns a `CatalogEntry` Pydantic instance whose `.source_id == 'iem.archive'`, `.status == 'live'`, `.schema_semantics.schema_id == 'schema.observation.v1'`.
    6. `test_loader_lookup_unknown_raises_source_unavailable`: `loader.lookup('does.not.exist')` raises `SourceUnavailableError` (Phase 2 exception) with `to_dict()` payload listing the 7 known sources.

    `packages/mcp/tests/test_catalog_entry_types.py` (4 tests):

    1. `test_catalog_entry_pydantic_construction`: build a `CatalogEntry` instance from a dict produced by `yaml.safe_load(open('iem.archive.yaml'))`; all fields populate.
    2. `test_catalog_entry_required_fields_enforced`: `CatalogEntry(**{...missing temporal_rules...})` raises `pydantic.ValidationError`.
    3. `test_catalog_entry_status_literal`: `CatalogEntry(..., status='unknown_state')` raises `pydantic.ValidationError`; allowed values are `Literal['live', 'wip', 'retired']`.
    4. `test_catalog_entry_join_mapping_shape`: nested `RelationshipMapping(source='x', on=['a','b'], note='y')` constructs.

    `packages/mcp/tests/test_yaml_safe_load.py` (2 tests):

    1. `test_loader_rejects_python_object_tag`: write a malicious YAML to a temp file containing `!!python/object/apply:os.system\nargs: ['echo pwned']`. `CatalogLoader.from_dir(tmp)` rejects (either raises `yaml.constructor.ConstructorError` directly from safe_load OR wraps it). Critical: confirm `os.system` was NOT called — Pitfall I.4 attack surface.
    2. `test_catalog_loader_uses_safe_load_not_load`: grep the catalog.py source — `grep "yaml.safe_load"` returns ≥ 1; `grep "yaml.load[^_]"` (i.e. `yaml.load` without `_yaml` prefix) returns 0. Static guard.

    Run `uv run pytest packages/mcp/tests/test_catalog_loader.py packages/mcp/tests/test_catalog_entry_types.py packages/mcp/tests/test_yaml_safe_load.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 12 tests. Commit RED.

    Step 2 — Implement `packages/mcp/src/tradewinds_mcp/_catalog_entry_types.py`:

    ```python
    """Pydantic types mirroring the catalog entry meta-schema.

    The meta-schema (packages/mcp/catalog/_schema/catalog_entry.schema.json) is
    the source-of-truth for the WIRE format; these Pydantic models are the
    PYTHON ergonomic surface. Both validate the same YAML — jsonschema validates
    against the JSON Schema (catches typos in field names), Pydantic validates
    against the Python type system (catches wrong types in field values).
    """

    from __future__ import annotations

    from typing import Literal
    from pydantic import BaseModel, Field

    __all__ = [
        "CatalogEntry",
        "SchemaSemantics",
        "TemporalRules",
        "RelationshipMapping",
        "RelationshipMappings",
        "OperationalContext",
        "ExtractionConfig",
    ]


    class SchemaSemantics(BaseModel):
        schema_id: str = Field(..., description="Phase 2 canonical schema ID or contract_spec.* synthetic ID")
        fields: dict[str, str] = Field(default_factory=dict)


    class TemporalRules(BaseModel):
        event_time_field: str
        knowledge_time_field: str
        knowledge_time_formula: str
        backfill_behavior: str
        vintage_aware: bool = False


    class RelationshipMapping(BaseModel):
        source: str
        on: list[str]
        note: str | None = None


    class RelationshipMappings(BaseModel):
        joins_to: list[RelationshipMapping] = Field(default_factory=list)


    class OperationalContext(BaseModel):
        endpoint: str | None = None
        rate_limit: str | None = None
        auth: str = Field(..., description="'none' | 'api_key:ENV_VAR_NAME' | 'oauth'")
        pagination: str | None = None
        http_timeout_seconds: float | None = None


    class ExtractionConfig(BaseModel):
        adapter: str | None = None
        config_file: str | None = None


    class CatalogEntry(BaseModel):
        source_id: str
        display_name: str
        status: Literal["live", "wip", "retired"]
        schema_semantics: SchemaSemantics
        temporal_rules: TemporalRules
        quality_notes: list[str]
        relationship_mappings: RelationshipMappings
        operational_context: OperationalContext
        extraction_config: ExtractionConfig | None = None
    ```

    Step 3 — Implement `packages/mcp/src/tradewinds_mcp/catalog.py`:

    ```python
    """CatalogLoader — eager-load + validate per-source YAML catalog files.

    Two validation passes per file:
    1. jsonschema validation against `catalog/_schema/catalog_entry.schema.json`
       — catches typo'd field names (additionalProperties: false at top level).
    2. Pydantic CatalogEntry construction — catches wrong-type field values.

    Both must pass. Files under `_generated/` and `_schema/` subdirectories are
    SKIPPED (Wave 3 promotes from _generated/ → catalog/ root; _schema/ is the
    meta-schema dir, not a catalog entry source).

    Security: yaml.safe_load only. yaml.load is RCE-vulnerable.
    """

    from __future__ import annotations

    import json
    from pathlib import Path
    from typing import Iterator

    import jsonschema
    import yaml

    from tradewinds.core.exceptions import SchemaValidationError, SourceUnavailableError
    from ._catalog_entry_types import CatalogEntry

    __all__ = ["CatalogLoader"]

    _SKIP_DIRS = {"_generated", "_schema"}


    class CatalogLoader:
        def __init__(self, entries: dict[str, CatalogEntry], schema_path: Path) -> None:
            self._entries = entries
            self._schema_path = schema_path

        @classmethod
        def from_dir(cls, catalog_dir: str | Path) -> "CatalogLoader":
            cdir = Path(catalog_dir)
            meta_schema_path = cdir / "_schema" / "catalog_entry.schema.json"
            if not meta_schema_path.exists():
                raise SchemaValidationError(
                    f"Catalog meta-schema not found at {meta_schema_path}"
                )
            with meta_schema_path.open("r", encoding="utf-8") as f:
                meta_schema = json.load(f)
            jsonschema.Draft202012Validator.check_schema(meta_schema)
            validator = jsonschema.Draft202012Validator(meta_schema)

            entries: dict[str, CatalogEntry] = {}
            for path in sorted(cdir.glob("*.yaml")):
                if path.parent.name in _SKIP_DIRS:
                    continue  # belt-and-suspenders; glob doesn't recurse but be defensive
                with path.open("r", encoding="utf-8") as f:
                    # Pitfall guard: safe_load ONLY
                    raw = yaml.safe_load(f)
                if not isinstance(raw, dict):
                    raise SchemaValidationError(
                        f"Catalog entry {path} did not parse to a dict (got {type(raw)!r})"
                    )
                # 1. jsonschema validation (catches typo'd field names)
                errors = sorted(validator.iter_errors(raw), key=lambda e: e.path)
                if errors:
                    msgs = "; ".join(f"{'.'.join(str(p) for p in e.path)}: {e.message}" for e in errors)
                    raise SchemaValidationError(
                        f"Catalog entry {path} fails meta-schema validation: {msgs}"
                    )
                # 2. Pydantic construction (catches wrong types)
                try:
                    entry = CatalogEntry(**raw)
                except Exception as exc:
                    raise SchemaValidationError(
                        f"Catalog entry {path} fails Pydantic type validation: {exc}"
                    ) from exc
                if entry.source_id != path.stem:
                    raise SchemaValidationError(
                        f"Catalog entry {path}: source_id={entry.source_id!r} != filename stem {path.stem!r}"
                    )
                entries[entry.source_id] = entry
            return cls(entries=entries, schema_path=meta_schema_path)

        def all_source_ids(self) -> list[str]:
            return sorted(self._entries.keys())

        def lookup(self, source_id: str) -> CatalogEntry:
            if source_id not in self._entries:
                raise SourceUnavailableError(
                    f"Unknown source_id '{source_id}'. Available sources: {self.all_source_ids()}"
                )
            return self._entries[source_id]

        def __iter__(self) -> Iterator[CatalogEntry]:
            return iter(self._entries.values())

        def __len__(self) -> int:
            return len(self._entries)
    ```

    Step 4 — Run `uv run pytest packages/mcp/tests/test_catalog_loader.py packages/mcp/tests/test_catalog_entry_types.py packages/mcp/tests/test_yaml_safe_load.py -x -v` — all 12 tests MUST pass.

    Step 5 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Commit (GREEN): `feat(phase-5): CatalogLoader + Pydantic types + yaml.safe_load guard (MCP-02 GREEN)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_catalog_loader.py packages/mcp/tests/test_catalog_entry_types.py packages/mcp/tests/test_yaml_safe_load.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/src/tradewinds_mcp/catalog.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/_catalog_entry_types.py` returns 0
    - `grep -c "yaml.safe_load" packages/mcp/src/tradewinds_mcp/catalog.py` returns ≥ 1
    - `grep -cE "yaml\\.load\\(" packages/mcp/src/tradewinds_mcp/catalog.py` returns 0 (NO unsafe yaml.load)
    - `grep -c "class CatalogLoader" packages/mcp/src/tradewinds_mcp/catalog.py` returns 1
    - `grep -c "def from_dir" packages/mcp/src/tradewinds_mcp/catalog.py` returns 1
    - `grep -c "SchemaValidationError" packages/mcp/src/tradewinds_mcp/catalog.py` returns ≥ 1
    - `grep -c "SourceUnavailableError" packages/mcp/src/tradewinds_mcp/catalog.py` returns ≥ 1
    - `grep -c "Literal\\[.live., .wip., .retired.\\]" packages/mcp/src/tradewinds_mcp/_catalog_entry_types.py` returns 1
    - `python -c "from tradewinds_mcp.catalog import CatalogLoader; loader = CatalogLoader.from_dir('packages/mcp/catalog/'); print(loader.all_source_ids())"` exits 0 and prints 7 source IDs
    - `uv run pytest packages/mcp/tests/test_catalog_loader.py packages/mcp/tests/test_catalog_entry_types.py packages/mcp/tests/test_yaml_safe_load.py -x -v` exits 0 with 12 passed
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    CatalogLoader.from_dir loads 7 weather entries, validates each against meta-schema + Pydantic, skips _generated/ and _schema/. yaml.safe_load only (RCE pitfall guarded). 12 tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2.3: _adapter_bridge + tool wiring (Wave 1 stubs → real catalog dispatch) (RED tests FIRST)</name>
  <files>packages/mcp/src/tradewinds_mcp/_adapter_bridge.py, packages/mcp/src/tradewinds_mcp/tools/list_sources.py, packages/mcp/src/tradewinds_mcp/tools/describe_source.py, packages/mcp/src/tradewinds_mcp/tools/query.py, packages/mcp/src/tradewinds_mcp/tools/ingest.py, packages/mcp/src/tradewinds_mcp/server.py, packages/mcp/tests/test_tools_dispatch_real_catalog.py</files>
  <implements>MCP-02 (real list_sources/describe_source); MCP-10 (real query/ingest for the 7 weather entries)</implements>
  <read_first>
    - Task 2.1 + 2.2 outputs (catalog + loader exist)
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§H.3 invariant — packages/mcp/ must depend on Phase 2 PUBLIC catalog registry, not private fetcher paths; §I.8 — cross-vertical join allow-list discipline)
    - .planning/phase-02-core-primitives-catalog-adapters/PLAN.md (Wave 3 — tradewinds.weather.catalog.get_adapter(source_id) returns WeatherAdapter Protocol instance; Wave 4 — KALSHI contract spec resolve API)
    - packages/weather/src/tradewinds/weather/catalog/__init__.py (Phase 2 — confirm get_adapter signature)
    - packages/mcp/src/tradewinds_mcp/tools/query.py + ingest.py (Wave 1 stubs — read to understand current shape; you are replacing the `_placeholder` DataFrame with a real catalog-backed fetch)
  </read_first>
  <behavior>
    Tests to write FIRST in `packages/mcp/tests/test_tools_dispatch_real_catalog.py` (8 tests):

    1. `test_list_sources_returns_seven_weather_entries`: in-process FastMCP `session.call_tool("list_sources", {})` returns `ListSourcesResponse(sources=[<7 sorted weather source IDs>])`.
    2. `test_describe_source_iem_archive_full_entry`: `session.call_tool("describe_source", {"source_id": "iem.archive"})` returns a `DescribeSourceResponse` with `catalog_entry` matching the full YAML dict.
    3. `test_describe_source_unknown_raises_source_unavailable`: `session.call_tool("describe_source", {"source_id": "fake.nonexistent"})` raises `SourceUnavailableError`-shaped JSON-RPC error.
    4. `test_query_iem_archive_dispatches_to_phase2_adapter` (mock Phase 2 adapter): patch `tradewinds.weather.catalog.get_adapter` to return a mock returning a 5-row DataFrame with `event_time`/`knowledge_time`/`source`/`retrieved_at` columns. Call `session.call_tool("query", {"source_id": "iem.archive", "as_of": "2024-01-15T00:00:00Z", "filters": {"station": "KNYC", "start": "2024-01-01", "end": "2024-01-14"}})`. Assert the mock was called with translated kwargs; assert envelope `data` non-empty TOON; `rows` field in audit log = 5 (or filtered count after `Dataset.at_time` applied).
    5. `test_query_temporal_safety_applied`: build a DataFrame with rows at 2024-01-10, 2024-01-15, 2024-01-20; `as_of=2024-01-15` should filter to 2 rows (rows with knowledge_time ≤ 2024-01-15). Hand-validate by counting newlines in TOON `data`.
    6. `test_ingest_iem_archive_writes_to_cache`: call `session.call_tool("ingest", {"source_id": "iem.archive", "as_of": ..., "filters": ...})`. Assert `IngestResponse.rows_ingested == <expected>`; cache file exists under `$HOME/.tradewinds/cache/v1/observations/KNYC/2024/01.parquet` (Phase 1 CACHE-01 pattern).
    7. `test_query_unknown_source_raises`: `session.call_tool("query", {"source_id": "fake.x", "as_of": ...})` raises with `SourceUnavailableError` payload.
    8. `test_query_wip_source_warns_or_errors`: `session.call_tool("query", {"source_id": "iem.forecasts", "as_of": ...})` — if `iem.forecasts.yaml` has `status: wip`, the tool MUST raise a clear `SourceUnavailableError` with a "WIP — not yet shipped" message. (If `status: live` because Phase 2 MOS parser landed: it dispatches normally.)

    Run `uv run pytest packages/mcp/tests/test_tools_dispatch_real_catalog.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 8 tests. Commit RED.

    Step 2 — Implement `packages/mcp/src/tradewinds_mcp/_adapter_bridge.py`:

    ```python
    """_adapter_bridge — translates CatalogEntry.extraction_config.adapter to Phase 2 adapter calls.

    The MCP catalog (packages/mcp/catalog/*.yaml) describes WHAT a source is and
    HOW its rows relate to the temporal-safety model. The actual fetching is
    delegated to Phase 2 weather adapters (tradewinds.weather.catalog.get_adapter).

    This indirection is per RESEARCH.md §H.3 invariant: 'packages/mcp/ MUST NOT
    depend on tradewinds.weather._fetchers directly — only through the catalog
    entries and the canonical schemas.' Wave 4 extends this bridge for the macro
    vertical (FRED+ALFRED+Kalshi macro contract specs) without changing this file's
    structure.
    """

    from __future__ import annotations

    from datetime import datetime
    from typing import Any
    import pandas as pd

    from tradewinds.core.exceptions import SourceUnavailableError
    from ._catalog_entry_types import CatalogEntry

    __all__ = ["AdapterBridge"]


    class AdapterBridge:
        """Resolves a CatalogEntry to a Phase 2 adapter; performs fetch/ingest."""

        def fetch(self, entry: CatalogEntry, filters: dict[str, Any] | None) -> pd.DataFrame:
            """Fetch rows for the given catalog entry. Returns canonical-schema DataFrame."""
            if entry.status == "wip":
                raise SourceUnavailableError(
                    f"Source '{entry.source_id}' has status='wip' — not yet shipped. "
                    f"Notes: {entry.quality_notes}"
                )
            if entry.status == "retired":
                raise SourceUnavailableError(
                    f"Source '{entry.source_id}' is retired and no longer fetchable."
                )
            adapter_id = (entry.extraction_config.adapter if entry.extraction_config else None) or entry.source_id
            # Late-bind imports — keep tradewinds.weather optional at server import time
            adapter = self._resolve_adapter(adapter_id)
            return adapter.fetch(**(filters or {}))

        def ingest(self, entry: CatalogEntry, filters: dict[str, Any] | None) -> tuple[pd.DataFrame, int]:
            """Fetch rows AND write to Phase 1 local cache. Returns (df, rows_ingested)."""
            df = self.fetch(entry, filters)
            # Phase 1 cache writes happen inside the Phase 2 adapter's fetch() — it caches by station/year/month.
            # The MCP layer does NOT re-cache; it just measures.
            return df, len(df)

        @staticmethod
        def _resolve_adapter(adapter_id: str) -> Any:
            # Weather adapters dispatched via Phase 2 eager registry.
            # If adapter_id has 'kalshi' prefix, dispatch to markets module instead.
            if adapter_id.startswith("kalshi."):
                # Kalshi entries are contract specs, not row data — return a wrapper that
                # exposes a fetch() returning the contract spec resolution as a 1-row DataFrame.
                # Implementation deferred to Task 2.3 follow-up if user wants kalshi.weather
                # to be queryable; for v0.2 ship, kalshi.weather.yaml exists as documentation
                # only and `describe_source` returns it but `query` raises SourceUnavailableError
                # with a "Kalshi contract specs are descriptive only in v0.2; use tradewinds.markets directly" message.
                raise SourceUnavailableError(
                    f"Source '{adapter_id}' is a contract spec; not queryable as row data in v0.2. "
                    f"Use tradewinds.markets.catalog.kalshi_nhigh.resolve(...) directly. "
                    f"See describe_source('{adapter_id}') for full catalog entry."
                )
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

    Step 3 — Modify `packages/mcp/src/tradewinds_mcp/tools/list_sources.py`:

    ```python
    """list_sources tool — returns real catalog source IDs (Wave 2)."""

    from ..envelopes import ListSourcesResponse


    def register(mcp, audit, catalog) -> None:
        @mcp.tool()
        async def list_sources() -> ListSourcesResponse:
            """Return all available source IDs from the catalog."""
            return ListSourcesResponse(sources=catalog.all_source_ids())
    ```

    Step 4 — Modify `packages/mcp/src/tradewinds_mcp/tools/describe_source.py`:

    ```python
    """describe_source tool — returns full 5-layer catalog entry (Wave 2)."""

    from ..envelopes import DescribeSourceResponse


    def register(mcp, audit, catalog) -> None:
        @mcp.tool()
        async def describe_source(source_id: str) -> DescribeSourceResponse:
            """Return the full 5-layer catalog entry for source_id."""
            entry = catalog.lookup(source_id)  # raises SourceUnavailableError if unknown
            desc = entry.display_name
            if entry.quality_notes:
                desc = f"{desc}. {entry.quality_notes[0]}"
            return DescribeSourceResponse(
                source_id=entry.source_id,
                description=desc,
                schema_id=entry.schema_semantics.schema_id,
                catalog_entry=entry.model_dump(),
            )
    ```

    Step 5 — Modify `packages/mcp/src/tradewinds_mcp/tools/query.py`:

    ```python
    """query tool — Wave 2: dispatches through catalog + _adapter_bridge."""

    from __future__ import annotations

    import hashlib
    from datetime import datetime

    from tradewinds.core.formats import toon as toon_fmt
    from tradewinds.core.temporal import Dataset

    from ..envelopes import QueryResponse
    from .._adapter_bridge import AdapterBridge


    def register(mcp, audit, catalog) -> None:
        bridge = AdapterBridge()

        @mcp.tool()
        async def query(
            source_id: str,
            as_of: datetime,
            filters: dict | None = None,
            format: str = "toon",
        ) -> QueryResponse:
            """Return rows from source_id knowable at `as_of`.

            Dispatches through the catalog: catalog.lookup → _adapter_bridge.fetch
            → Dataset.at_time(as_of) → TOON serialize → audit.log → return envelope.
            """
            entry = catalog.lookup(source_id)
            df = bridge.fetch(entry, filters)
            ds = Dataset(df, schema_id=entry.schema_semantics.schema_id)
            filtered = ds.at_time(as_of)
            toon_str = toon_fmt.serialize(filtered)
            hash_hex = hashlib.sha256(toon_str.encode("utf-8")).hexdigest()
            audit_id = audit.log(
                tool="query",
                source=source_id,
                as_of=as_of,
                rows=len(filtered),
                hash=hash_hex,
                schema_id=entry.schema_semantics.schema_id,
            )
            return QueryResponse(
                format="toon",
                data=toon_str,
                schema_id=entry.schema_semantics.schema_id,
                audit_id=audit_id,
            )
    ```

    Step 6 — Modify `packages/mcp/src/tradewinds_mcp/tools/ingest.py` similarly (calling `bridge.ingest()` which writes to Phase 1 cache via the adapter; returns `IngestResponse(..., rows_ingested=N)`).

    Step 7 — Modify `packages/mcp/src/tradewinds_mcp/server.py` to load the catalog at module level and pass it to each tool's `register(mcp, audit, catalog)`:

    ```python
    # ADD at module level:
    from .catalog import CatalogLoader
    _catalog = CatalogLoader.from_dir(_locate_catalog_dir())

    # Helper to find catalog/ — searches sibling to the running package
    def _locate_catalog_dir() -> str:
        from pathlib import Path
        here = Path(__file__).resolve().parent
        # In dev: packages/mcp/src/tradewinds_mcp/server.py → packages/mcp/catalog/
        candidate = here.parent.parent / "catalog"
        if candidate.exists():
            return str(candidate)
        # In installed wheel: catalog ships as package data
        candidate2 = here / "catalog"
        if candidate2.exists():
            return str(candidate2)
        raise FileNotFoundError(f"Cannot locate catalog dir; tried {candidate} and {candidate2}")

    # MODIFY register calls:
    query.register(mcp, _audit, _catalog)
    ingest.register(mcp, _audit, _catalog)
    list_sources.register(mcp, _audit, _catalog)
    describe_source.register(mcp, _audit, _catalog)
    get_schema.register(mcp, _audit)  # get_schema doesn't need catalog (reads Phase 2 registry directly)
    ```

    Also update `packages/mcp/pyproject.toml` to ship the catalog/ dir as package data:

    ```toml
    [tool.hatch.build.targets.wheel.force-include]
    "../../packages/mcp/catalog" = "tradewinds_mcp/catalog"
    ```

    (Confirm exact hatchling syntax — alternative is to use `[tool.hatch.build.targets.wheel.shared-data]` if force-include is wrong.)

    Step 8 — Run `uv run pytest packages/mcp/tests/ -m "not live" -x -v` — ALL tests (Wave 1 + Wave 2) MUST pass. Wave 2's 8 tests in `test_tools_dispatch_real_catalog.py` + 12 from Task 2.2 + 10 from Task 2.1 + Wave 1's ~25 = ~55 total.

    Step 9 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Commit: `feat(phase-5): _adapter_bridge + tool wiring for real catalog dispatch (MCP-02 + MCP-10 weather GREEN)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_tools_dispatch_real_catalog.py -x -v && uv run pytest packages/mcp/tests/ -m "not live" -q</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` returns 0
    - `grep -c "from tradewinds.weather.catalog import get_adapter" packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` returns 1
    - `grep -cE "from tradewinds\\.weather\\._fetchers" packages/mcp/src/tradewinds_mcp/_adapter_bridge.py` returns 0 (RESEARCH.md §H.3 invariant — no fetcher import)
    - `grep -cE "from tradewinds\\.weather\\._fetchers" packages/mcp/src/tradewinds_mcp/tools/*.py` returns 0 (invariant extended to tools)
    - `grep -c "catalog.lookup(source_id)" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1
    - `grep -c "bridge.fetch(entry" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1
    - `grep -c "Dataset(df, schema_id=entry.schema_semantics.schema_id)" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1
    - `grep -c "CatalogLoader.from_dir" packages/mcp/src/tradewinds_mcp/server.py` returns 1
    - `python -c "from tradewinds_mcp.server import mcp, _catalog; print(_catalog.all_source_ids())"` exits 0 and prints 7 sorted source IDs
    - `uv run pytest packages/mcp/tests/test_tools_dispatch_real_catalog.py -x -v` exits 0 with 8 passed
    - `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0 with all tests passing
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    `_adapter_bridge` translates CatalogEntry to Phase 2 adapter calls via the PUBLIC `get_adapter()` API only (no fetcher import). `list_sources`/`describe_source`/`query`/`ingest` now dispatch through the real catalog. WIP and retired statuses raise clear `SourceUnavailableError`. 8 tests pass + all prior Wave 1+2 tests stay green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2.4: Sample-data live-test infrastructure for catalog promotion gate (RED test FIRST)</name>
  <files>packages/mcp/tests/test_catalog_sample_data_roundtrip.py</files>
  <implements>MCP-02 (catalog promotion gate prerequisite — Wave 3 makes this mandatory for _generated/ → catalog/ promotion); RESEARCH.md §I.4 mitigation</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§C.2 — quality-review gate table; §I.4 — agent hallucinates a field that doesn't exist in the API; mitigation is sample-data round-trip)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — _generated/ → catalog/ promotion gate)
    - .planning/phase-01-v0-14-1-parity-lift/PLAN.md (Phase 1 Day 1 — @pytest.mark.live convention; CLAUDE.md CI-04 — live tests excluded from CI; manual pre-publish run)
    - CLAUDE.md (testing — @pytest.mark.live + uv run pytest -m "not live" default)
    - packages/mcp/src/tradewinds_mcp/_adapter_bridge.py (Task 2.3 output)
  </read_first>
  <behavior>
    Test to write FIRST in `packages/mcp/tests/test_catalog_sample_data_roundtrip.py` (1 parameterized test, @pytest.mark.live):

    1. `test_catalog_entry_sample_data_roundtrip` parameterized over the 7 weather entries (skip `wip` status). For each entry:
       - Call `_adapter_bridge.fetch(entry, filters={... minimal valid filter ...})`. For weather adapters, that means `station=KNYC, start=date(2024,1,1), end=date(2024,1,2)` (1-day window).
       - Assert returned `pd.DataFrame` is non-empty.
       - Assert every column listed in `entry.schema_semantics.fields` EXISTS in the DataFrame columns.
       - Run `tradewinds.core.validator.validate_dataframe(df, entry.schema_semantics.schema_id)` — Phase 2 validator confirms source-identity invariant. Returns SchemaRegistration; no exception.
       - Serialize via TOON; deserialize via TOON; assert byte-roundtrip semantically equivalent (Phase 2 already tests this; here it's an integration test that the catalog's claimed schema actually matches what comes out of the API).

    Use `pytest.mark.live` so CI doesn't run this (CI-04). Document in test docstring that this is the per-source quality-review gate that Wave 3 will require for promotion from `_generated/` to `catalog/`.

    Run `uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m live -x` (manual run; not CI). At first run, expect either:
      (a) all 6 live entries (excluding kalshi.weather + iem.forecasts if wip) pass — confirms each YAML's `schema_semantics.fields` matches reality.
      (b) one or more fail — surface to user. Examples: typo in field name in YAML; field renamed upstream since Phase 2 fixtures were captured. Per CONTEXT.md, the cure is to fix the YAML or open a `_generated/` PR with corrections.

    Commit RED (test exists, may or may not pass on the live run): `test(phase-5): add live sample-data roundtrip for catalog entries (MCP-02 promotion-gate scaffolding RED)`.
  </behavior>
  <action>
    Step 1 — Write the parameterized test:

    ```python
    """Sample-data round-trip test for catalog entries.

    Per RESEARCH.md §I.4 pitfall mitigation: an agent (or human) writing a catalog
    entry might claim a field name that doesn't exist in the real API (15% halluc
    rate on low-frequency APIs per LLM research 2026). This test fetches 1 row
    from each entry's adapter and validates that the YAML's claimed schema_id +
    declared fields match reality.

    Wave 3 makes this gate MANDATORY for _generated/ → catalog/ promotion. In
    Wave 2 it's a verification that the 7 weather entries are correct as shipped.

    @pytest.mark.live — runs against real public APIs; excluded from CI per CLAUDE.md
    CI-04. Run manually before each publish: `uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m live -v`.
    """
    from __future__ import annotations

    from datetime import date

    import pytest

    from tradewinds.core.validator import validate_dataframe
    from tradewinds.core.formats import toon as toon_fmt
    from tradewinds_mcp.catalog import CatalogLoader
    from tradewinds_mcp._adapter_bridge import AdapterBridge


    _CATALOG = CatalogLoader.from_dir("packages/mcp/catalog")
    _LIVE_ENTRIES = [
        e for e in _CATALOG
        if e.status == "live" and not e.source_id.startswith("kalshi.")
    ]


    @pytest.mark.live
    @pytest.mark.parametrize("entry", _LIVE_ENTRIES, ids=lambda e: e.source_id)
    def test_catalog_entry_sample_data_roundtrip(entry):
        bridge = AdapterBridge()
        # Minimal 1-day window for weather; can be tuned per source if needed
        filters = {"station": "KNYC", "start": date(2024, 1, 1), "end": date(2024, 1, 2)}
        df = bridge.fetch(entry, filters)
        assert not df.empty, f"{entry.source_id}: fetch returned empty DataFrame"

        # Verify every claimed field exists in the result
        claimed = set(entry.schema_semantics.fields.keys())
        actual = set(df.columns)
        missing = claimed - actual
        assert not missing, f"{entry.source_id}: YAML claims fields {missing} but adapter returned only {sorted(actual)}"

        # Validate against canonical schema (Phase 2 invariant)
        _registration = validate_dataframe(df, entry.schema_semantics.schema_id)

        # TOON roundtrip
        s = toon_fmt.serialize(df)
        df2 = toon_fmt.deserialize(s)
        # Phase 2 already tests strict equivalence; here we just confirm no exception
        assert not df2.empty
    ```

    Step 2 — Run the test in `-m "not live"` mode: `uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m "not live" -v`. Expected: 0 tests run (all skipped via `@pytest.mark.live`). This proves CI-04 compatibility.

    Step 3 — Document in `packages/mcp/CONTRIBUTING.md` (append a "Catalog promotion checklist" section): "Run `uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m live` before promoting a `_generated/` entry to `catalog/` root."

    Step 4 — Commit: `test(phase-5): add live sample-data roundtrip test for catalog promotion (MCP-02 scaffolding)`.

    Step 5 (optional, manual) — Run the live test manually if the human reviewer wants to validate that the 7 YAML entries are factually accurate against current API responses: `uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m live -v`. Document any field mismatches as follow-up tasks (typo fix PRs); don't block Wave 2 merge on this — Wave 3 makes it mandatory.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m "not live" -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/tests/test_catalog_sample_data_roundtrip.py` returns 0
    - `grep -c "@pytest.mark.live" packages/mcp/tests/test_catalog_sample_data_roundtrip.py` returns ≥ 1
    - `grep -c "validate_dataframe" packages/mcp/tests/test_catalog_sample_data_roundtrip.py` returns 1 (Phase 2 validator invocation)
    - `grep -c "toon_fmt.serialize" packages/mcp/tests/test_catalog_sample_data_roundtrip.py` returns 1
    - `uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m "not live" -v` exits 0 with 0 tests run (all live-marked, all skipped)
    - `grep -c "Catalog promotion checklist" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - One commit on the branch
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    Sample-data roundtrip test exists at `tests/test_catalog_sample_data_roundtrip.py`; runs in `-m live` mode only; documents the catalog-promotion checklist for Wave 3. CI-skipped per CLAUDE.md CI-04.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2.5: 2-reviewer loop + pre-merge gate + merge to main</name>
  <files>n/a (verification only)</files>
  <implements>Wave 2 closeout</implements>
  <read_first>
    - .planning/REVIEW-DISCIPLINE.md (never-skip applies — catalog YAML files contain schema-fragment-bearing content; reviewer prompt must explicitly cite RESEARCH.md §I.4 (hallucination guard) and §I.8 (cross-vertical join allow-list))
    - Plan-level success criteria below
  </read_first>
  <what-built>
    Tasks 2.1–2.4 complete: meta-schema + 7 weather YAML catalog entries; CatalogLoader + Pydantic types + yaml.safe_load guard; _adapter_bridge + real-catalog tool dispatch; live sample-data roundtrip scaffolding.
  </what-built>
  <how-to-verify>
    **Step A — Final tests pass:**

    ```bash
    uv run pytest packages/mcp/tests/ -m "not live" -v        # all Wave 1 + Wave 2 tests
    uv run pytest -m "not live" -q                              # full repo suite
    uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q | grep TOTAL  # ≥ 85% per Phase 5 bar
    ```

    Expected: all green; coverage ≥ 85% on tradewinds_mcp.

    **Step B — In-process smoke:**

    ```bash
    python -c "
    from tradewinds_mcp.server import mcp, _catalog
    print('Catalog entries:', _catalog.all_source_ids())
    assert len(_catalog) == 7
    print('OK — 7 weather entries loaded.')
    "
    ```

    **Step C — 2-reviewer loop per REVIEW-DISCIPLINE.md:**

    Reviewer prompts must reference:
    - RESEARCH.md §I.4 hallucination guard (sample-data roundtrip)
    - RESEARCH.md §I.8 cross-vertical join allow-list (joins_to is an allow-list, not a hint)
    - CONTEXT.md catalog format lock (per-source files, _generated/ subdir, yaml.safe_load)
    - REVIEW-DISCIPLINE.md never-skip — catalog YAML files have schema-fragment-bearing content

    PASS x2 in ≤ 3 iterations.

    **Step D — Merge:**

    ```bash
    git checkout main
    git merge --no-ff phase-5/wave-2/catalog-format-weather -m "Merge phase-5/wave-2/catalog-format-weather: 5-layer catalog + 7 weather entries (MCP-02 + MCP-10 weather)"
    ```

    **Step E — Confirm to user:**

    (1) All green: "Wave 2 merged to `main`. Catalog meta-schema + 7 weather YAML entries (iem.archive/live, awc.live, ghcnh.archive, cli.archive, iem.forecasts, kalshi.weather) shipped. CatalogLoader validates each YAML via jsonschema + Pydantic + yaml.safe_load. _adapter_bridge dispatches through Phase 2 public catalog registry only. Wave 3 (agent-generated connector pipeline) is unblocked. Type `approved` to continue."

    (2) Reviewer REVISE: "Codex / python-architect flagged [CRITICAL|HIGH]: [summary]. Fix on the branch and re-run the loop."

    (3) Sample-data live test failed for entry X: "YAML field mismatch on entry X. Surface for fix-up PR — Wave 2 still ships if the catalog is mostly correct; the offending entry can be marked `status: wip` until corrected."
  </how-to-verify>
  <resume-signal>
    Type `approved` once Wave 2 is merged to `main` (PLAN-03 is unblocked). Type `revise` for reviewer-driven changes. Type `field-fix` if sample-data live test surfaced a YAML field mismatch.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Per-source YAML files at `packages/mcp/catalog/*.yaml` | Source-controlled; same trust level as code. But agent-generated entries under `_generated/` are UNTRUSTED until human-reviewed + jsonschema-validated. |
| `yaml.safe_load` parsing | YAML can carry arbitrary Python objects via `!!python/object` tags if `yaml.load` is used; `safe_load` strictly rejects these. |
| `_adapter_bridge` → Phase 2 `tradewinds.weather.catalog.get_adapter` | In-process Python call; trust boundary if `get_adapter` is poisoned by an attacker-controlled source_id (e.g., path traversal in YAML's `extraction_config.adapter`). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-5.2-01 | Tampering / RCE | Malicious YAML uses `!!python/object/apply:os.system` for arbitrary code execution | mitigate | `yaml.safe_load` ONLY (rejects all `!!python/*` tags structurally). `test_loader_rejects_python_object_tag` proves this. Static guard via `grep -cE "yaml\\.load\\(" packages/mcp/src/tradewinds_mcp/catalog.py` returning 0. RESEARCH.md §B.2 pitfall. |
| T-5.2-02 | Tampering | Catalog YAML typo (e.g., `temporal_rule` instead of `temporal_rules`) silently disables the temporal_rules block at runtime | mitigate | Meta-schema's top-level `additionalProperties: false` rejects unknown fields; `test_meta_schema_top_level_strict` proves the policy. Loader validates every file at startup; the server fails fast on a typo. |
| T-5.2-03 | Tampering | Agent-generated catalog entry claims field that doesn't exist in the real API; query() returns rows with NaN columns silently | mitigate | Sample-data round-trip test (Task 2.4) compares claimed `schema_semantics.fields` against actual DataFrame columns. Wave 3 makes this gate MANDATORY for `_generated/` → `catalog/` promotion. RESEARCH.md §I.4. |
| T-5.2-04 | Information Disclosure | An untrusted `extraction_config.adapter` value triggers a path-traversal load (e.g., `adapter: "../../../etc/passwd"`) | mitigate | `_adapter_bridge._resolve_adapter` validates adapter_id against the Phase 2 public catalog registry — only known source IDs work. Unknown IDs raise `SourceUnavailableError`. No filesystem lookup based on adapter_id; `extraction_config.config_file` is reserved for Wave 3 generated-config promotion and not consumed in Wave 2. |
| T-5.2-05 | Tampering | An invalid cross-vertical join in YAML's `joins_to` is silently accepted by an agent / user, leading to wrong-rows joins at query time | mitigate | RESEARCH.md §I.8 — `joins_to` is the ALLOW-LIST. v0.2 hard-rejects cross-vertical joins not in the allow-list at query time (Wave 4 enforces; Wave 2 documents the contract in the meta-schema). For Wave 2, we ship the discipline (each YAML enumerates valid `joins_to`) without runtime enforcement; Wave 4 catches undeclared joins via audit log. |
| T-5.2-06 | Denial of Service | Catalog with hundreds of entries (Wave 3+ from agent-generated promotions) slows server boot via per-entry jsonschema validation | accept | v0.2 ships 10 entries (7 weather + 3 macro in Wave 4). Even 100 entries validate in < 1s. v0.3+ if catalog grows past 1000, lazy-load by source_id (defer; not a v0.2 problem). |
| T-5.2-07 | Repudiation | A user modifies a YAML in-place; loader has no provenance | accept | Catalog is under git; provenance is `git blame`. v0.2 doesn't sign YAML entries. Acceptable for local-first ship; v0.3+ hosted may add signature requirement. |
</threat_model>

<verification>
## Plan-Level Checks (auto + manual)

| Check | Command | Expected |
|-------|---------|----------|
| Meta-schema valid JSON Schema | `python -c "import json, jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('packages/mcp/catalog/_schema/catalog_entry.schema.json')))"` | exit 0 |
| Top-level additionalProperties: false | `python -c "import json; s = json.load(open('packages/mcp/catalog/_schema/catalog_entry.schema.json')); assert s['additionalProperties'] is False"` | exit 0 |
| All 7 YAML files present | `ls packages/mcp/catalog/*.yaml \| wc -l` | 7 |
| All 7 YAMLs validate against meta-schema | (Task 2.1 test) `uv run pytest packages/mcp/tests/test_catalog_meta_schema.py::test_all_seven_weather_yamls_validate -v` | PASS |
| Catalog loader returns 7 entries | `python -c "from tradewinds_mcp.catalog import CatalogLoader; print(len(CatalogLoader.from_dir('packages/mcp/catalog/')))"` | 7 |
| yaml.safe_load used; yaml.load absent | `grep -c "yaml.safe_load" packages/mcp/src/tradewinds_mcp/catalog.py; grep -cE "yaml\\.load\\(" packages/mcp/src/tradewinds_mcp/catalog.py` | ≥1, 0 |
| _adapter_bridge has no fetcher imports | `grep -cE "from tradewinds\\.weather\\._fetchers" packages/mcp/src/tradewinds_mcp/_adapter_bridge.py packages/mcp/src/tradewinds_mcp/tools/*.py` | 0 |
| Server loads catalog at module level | `python -c "from tradewinds_mcp.server import _catalog; print(_catalog.all_source_ids())"` | 7 sorted source IDs |
| Sample-data live test marked live | `grep -c "@pytest.mark.live" packages/mcp/tests/test_catalog_sample_data_roundtrip.py` | ≥1 |
| Full MCP fast suite | `uv run pytest packages/mcp/tests/ -m "not live" -q` | exit 0 |
| Full repo fast suite | `uv run pytest -m "not live" -q` | exit 0 |
| Branch coverage tradewinds_mcp | `uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q \| grep TOTAL` | ≥ 85% |
| Pre-commit hooks | `uv run pre-commit run --all-files` | exit 0 |
| 2-reviewer loop | (manual — codex high + python-architect) | both PASS |

## Static Regression Guards

```bash
# RESEARCH.md §B.2 — yaml.safe_load only
grep -rnE "yaml\\.load\\(" packages/mcp/ && echo "FAIL: unsafe yaml.load() somewhere" || echo "OK"

# RESEARCH.md §H.3 — no fetcher imports from MCP
grep -rnE "from tradewinds\\.weather\\._fetchers" packages/mcp/src/ && echo "FAIL: MCP imports weather fetcher internals" || echo "OK"

# Meta-schema strict top level
python -c "import json; s = json.load(open('packages/mcp/catalog/_schema/catalog_entry.schema.json')); exit(0 if s.get('additionalProperties') is False else 1)" || echo "FAIL: meta-schema top-level not strict"

# Status field allowed values
for f in packages/mcp/catalog/*.yaml; do
  status=$(grep "^status:" "$f" | awk '{print $2}')
  case "$status" in
    live|wip|retired) ;;
    *) echo "FAIL: $f has invalid status '$status'"; exit 1 ;;
  esac
done
echo "OK — all status fields valid"
```
</verification>

<success_criteria>
- [ ] MCP-02 (full): 5-layer catalog meta-schema at `packages/mcp/catalog/_schema/catalog_entry.schema.json` is valid Draft 2020-12; top-level `additionalProperties: false`; mandates 5 context blocks + source_id + display_name + status.
- [ ] MCP-10 (weather portion — 7 of 10): YAML files for `iem.archive`, `iem.live`, `awc.live`, `ghcnh.archive`, `cli.archive`, `iem.forecasts`, `kalshi.weather` exist, validate against meta-schema, populate all 5 layers with non-empty content.
- [ ] `CatalogLoader.from_dir('packages/mcp/catalog/')` loads 7 entries via `yaml.safe_load` ONLY; rejects malformed entries; skips `_generated/` and `_schema/` subdirs.
- [ ] `list_sources()` returns 7 sorted source IDs; `describe_source('iem.archive')` returns full 5-layer entry; `describe_source('nonexistent')` raises `SourceUnavailableError`.
- [ ] `query('iem.archive', as_of=..., filters=...)` dispatches through `_adapter_bridge` → Phase 2 `tradewinds.weather.catalog.get_adapter('iem.archive').fetch()` → `Dataset.at_time(as_of)` → TOON → audit.log → envelope. WIP / retired sources raise clear errors.
- [ ] `_adapter_bridge` does NOT import from `tradewinds.weather._fetchers` (RESEARCH.md §H.3 invariant enforced).
- [ ] Sample-data live-test infrastructure (`@pytest.mark.live`) exists; Wave 3 promotion gate is documented in CONTRIBUTING.md.
- [ ] Full MCP fast suite green: `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0 (Wave 1 + Wave 2 tests, ~55 total).
- [ ] Full repo fast suite green: `uv run pytest -m "not live" -q` exits 0.
- [ ] Branch coverage `tradewinds_mcp` ≥ 85%.
- [ ] Pre-commit + pre-push hooks green; no `--no-verify`.
- [ ] 2-reviewer loop (codex `high` + python-architect) PASS x2 in ≤ 3 iterations.
- [ ] Branch `phase-5/wave-2/catalog-format-weather` merged to `main` via `git merge --no-ff`.
</success_criteria>

<output>
After completion, create `.planning/phase-05-mcp-data-platform/05-02-SUMMARY.md` documenting:

- MCP-02 + MCP-10-weather shipped; iem.forecasts status (live or wip)
- Meta-schema file size, JSON Schema draft version
- 7 YAML files: source_id, status, schema_id, file size
- CatalogLoader behavior (validation passes, error messages)
- _adapter_bridge integration test results (recorded fixtures)
- Sample-data live test results (if run manually: pass/fail per entry)
- Coverage numbers (tradewinds_mcp branch %)
- 2-reviewer loop verdict (PASS x2 iteration N)
- Commit hashes on `phase-5/wave-2/catalog-format-weather`
- Merge commit hash on `main`
- Time spent
- Downstream signals for Wave 3 (agent-generated connectors): catalog meta-schema is the validation target for generated entries; `_generated/` dir exists empty; `CatalogLoader` skips this dir; promotion is `mv _generated/X.yaml catalog/X.yaml` + reviewer approval + sample-data live test green.
</output>
