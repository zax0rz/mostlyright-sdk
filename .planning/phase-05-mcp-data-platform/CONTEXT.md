---
phase: 05-mcp-data-platform
type: context
gathered: 2026-05-22
status: ready-for-planning
source: VISION.md + orchestrator-brief
milestone: v0.2+
---

# Phase 5: MCP Data Platform — Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Source:** [`.planning/phase-05-mcp-data-platform/VISION.md`](VISION.md) + inline orchestrator brief (2026-05-22)
**Milestone:** v0.2+ (POST-v0.1.0 ship — runs strictly after Phases 1, 1.5, 2, 3, 4 complete and v0.1.0 ships to PyPI)

<domain>
## Phase Boundary

Transform tradewinds from a single-vertical Python SDK into an **MCP-native data platform for prediction-market ML**. v0.2's job is to make tradewinds the way an AI agent talks to weather + (one second vertical) data with structural temporal safety, instead of a Python-only library you import. The strategic bet: quants will not let agents touch a Python notebook directly, but they WILL let agents call an MCP server that cannot bypass temporal safety.

**Six components (LOCKED — from VISION.md):**

1. **MCP Server Layer** at `packages/mcp/` — Python `mcp` SDK (FastMCP pattern). Tools: `list_sources`, `describe_source`, `ingest`, `query`, `get_schema`. Each data vertical can be its own MCP server long-term, but v0.2 ships ONE server with multi-vertical catalog entries.
2. **Data Catalog with Context Engineering** — 5-layer context per source: schema semantics / temporal rules / quality notes / relationship mappings / operational context. Catalog entries function as agent-readable onboarding docs.
3. **Agent-Generated Connectors** — agents read docs/HTML/PDF, build schema mental model, generate extraction configs. Configs persisted for re-use. Quality review gate before promotion to pre-indexed.
4. **Temporal Safety as Trust Architecture** — **SERVER-ENFORCED**, not agent-enforced. Constraint is structural — `dataset.at_time(date)`, `.between(start, end)`, `.as_of(timestamp)`. Auditable provenance, deterministic replay (same query + same cutoff = identical bytes).
5. **Multi-vertical expansion** — v0.2 ships weather (extends Phase 2 adapters) + at least one new vertical (sports prediction markets recommended in VISION.md). v0.3 = sports deeper, v0.4 = politics/finance.
6. **Core library + wrappers pattern** — Python SDK (already what tradewinds is), MCP server wrapper at `packages/mcp/`, CLI wrapper (v0.2.x). Same `tradewinds.core` is the load-bearing temporal-safety layer everyone calls into.

**Subsumes earlier narrow MCP requirements:** The 10 broader MCP-01..MCP-10 requirements in REQUIREMENTS.md (line 238-247) are the canonical Phase 5 acceptance set. The earlier narrow `MCP-01..MCP-06` block (REQUIREMENTS.md line 101-108) is SUPERSEDED — see `<id_collision>` below.

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Phase 5 is POST-v0.1.0 ship — strict gate
- **Locked:** Phase 5 work begins only after Phases 1, 1.5, 2, 3, 4 complete, v0.1.0 is tagged and published to PyPI, and the README quickstart works end-to-end (per Phase 4 success criterion #2). No Phase 5 file mods before v0.1.0 ships.
- **Rationale:** v0.1.0 ship gate is the empirical proof the core SDK works. Building MCP layer on top of unstable core wastes effort.
- **Implication for planner:** plan timeline begins at "v0.2.0-dev0" tag, not Day 14. No competition for resources with Phase 1-4 execution.

### MCP SDK = Anthropic Python `mcp` (FastMCP pattern)
- **Locked:** `mcp >= 1.27` (current as of 2026-05). FastMCP API (`from mcp.server.fastmcp import FastMCP`), NOT the lower-level Server class. Decorator-based tool registration. Python 3.10+ required — we're on 3.11+ so fine.
- **Rationale:** CLAUDE.md tech stack research already pinned this for v0.2. FastMCP recommended for ~80% of cases; our 5-tool surface is well inside that envelope.
- **Forbid:** custom JSON-RPC implementation, alternative MCP runtimes.

### DataFrame I/O at the MCP boundary = `toon` format (NOT raw `pd.DataFrame`)
- **Locked:** MCP tool returns serialize DataFrames to `toon` strings (Phase 2 format), tool response shape: `{"format": "toon", "data": <string>, "schema": <schema_id>}`. The tool consumer (agent) calls a separate validate/dehydrate step.
- **Rationale:** FastMCP returns Pydantic/TypedDict shapes; pandas isn't first-class. From CLAUDE.md tech-stack research: "Serialize DataFrames at the tool boundary using one of our existing formats (`toon` is compact, JSON-compatible). Don't return `pd.DataFrame` directly from MCP tools."
- **Forbid:** parquet bytes at the MCP boundary (too large for default JSON-RPC framing); pickled DataFrame; CSV with no schema reference.

### Temporal safety enforced inside the MCP server (not at agent layer)
- **Locked:** Every MCP tool that returns rows runs a server-side `KnowledgeView(as_of=...)` filter BEFORE serializing. The `as_of` parameter is REQUIRED on every read tool (`query`, `ingest`). No agent-supplied `as_of=None` short-circuit. The constraint lives in a single shared decorator/middleware so it cannot be accidentally bypassed by a new tool.
- **Rationale:** This is THE differentiator from "agent calls Python SDK directly" — agents can lie to themselves about leakage. They cannot lie to a structural filter.
- **Forbid:** any tool returning rows without going through the `KnowledgeView` filter; any "skip_temporal_check" kwarg; any way for the agent to read raw cache files (`packages/mcp/` MUST NOT expose `cache.py` or filesystem paths).

### Multi-vertical proof = sports prediction markets (recommended), one vertical only in v0.2
- **Locked:** v0.2 ships weather (Phase 2 baseline) + ONE new vertical. Recommendation: sports prediction markets (horse-racing settlements have clean public data — Kalshi/Polymarket has horse-racing contracts). v0.3 deepens sports + adds politics/finance.
- **Open in planning:** sports specifically vs another low-friction vertical. Planner picks based on data-availability research (researcher should answer: which non-weather vertical has the cleanest public-data story for first ship?).
- **Forbid:** shipping >2 verticals in v0.2 (scope explosion); shipping zero new verticals (defeats the "multi-vertical" success criterion).

### Catalog entries live at `packages/mcp/catalog/` with one file per source
- **Locked:** Catalog format is one file per source (NOT one giant DB). File extension: pending research (see Open Question — YAML vs JSON Schema vs custom DSL). Each catalog entry contains the 5-layer context + the extraction config (or a pointer to a generated-config file). Agent-generated configs go to `packages/mcp/catalog/_generated/` subdirectory; promoted entries move to `packages/mcp/catalog/` root after review.
- **Rationale:** per-source files = clean diffs, agent-generated additions are PRs, version control gives provenance for free.

### Server-enforced provenance — log every transformation
- **Locked:** Every MCP tool call writes a structured log entry: `(timestamp, tool_name, source_id, schema_version, as_of, retrieval_timestamp, row_count, hash_of_result)`. Logs go to `$HOME/.tradewinds/mcp-server/audit.jsonl` (append-only). Deterministic replay test: same tool call with same `as_of` produces same `hash_of_result`.
- **Rationale:** auditability is a major sell to quant adopters. Cheap to add at MCP layer (intercept in the same decorator that enforces `KnowledgeView`).

### MCP ID collision must be resolved BEFORE Phase 5 PLAN.md merges
- **Locked:** Option (b) from REQUIREMENTS.md line 236 ID-collision note: "delete the old MCP-01..06 entries and treat Phase 5 MCP-01..10 as canonical." The Phase 5 vision strictly subsumes the narrow tools list (catalog_search is now part of `list_sources`/`describe_source`; pull_pairs is now `query`; validate_dataframe is now server-internal + exposed via `get_schema`; JSON-RPC tests, TOON serialization, console script all still apply but under the broader MCP-01..MCP-10 umbrella).
- **How to apply:** Planner SHOULD include a task (or recommend a `/gsd-quick`) to physically remove REQUIREMENTS.md lines 103-108 + line 236 ID-collision note + update REQUIREMENTS.md mapping table + footer count BEFORE Phase 5 execution begins. Phase 5 plans use only MCP-01..MCP-10 from REQUIREMENTS.md line 238-247.

### Phase 5 is likely 4-6 plans across 3-4 waves (planner confirms)
- **Hint, not lock:** Phase 5 has 5 success criteria, 10 requirements, 6 components. It's the largest phase in the roadmap. Planner should consider splitting into:
  - Wave 1: MCP server skeleton + temporal-safety middleware (the structural foundation)
  - Wave 2: Catalog + 5-layer context schema + pre-indexed weather entries (reuse Phase 2 adapters)
  - Wave 3: Agent-generated connectors + quality-review gate
  - Wave 4: Second-vertical proof (sports) + multi-vertical catalog + audit log + JSON-RPC integration tests
- Planner MAY recommend splitting Phase 5 into Phase 5a / 5b / 5c if the plan-budget analysis warrants (per the workflow's "PHASE SPLIT RECOMMENDED" return path).

### Claude's Discretion
- Exact module structure inside `packages/mcp/` (`packages/mcp/src/tradewinds_mcp/server.py` vs `packages/mcp/src/tradewinds/mcp/server.py` — depends on namespace decision in Phase 2). Planner picks once Phase 2 structure is concrete.
- Whether `audit.jsonl` is per-MCP-server-instance or per-user (single shared file). Recommend per-instance (cleaner isolation).
- Whether to ship a `tradewinds-mcp-server --replay <audit-line>` CLI for deterministic-replay testing in v0.2 or defer to v0.3.

</decisions>

<open_questions>
## Open Questions — Researcher MUST Answer

These are the Open Questions block from [VISION.md](VISION.md) lines 54-59, expanded with what the researcher should investigate. None of these are pre-decided; the researcher should propose options + tradeoffs, and the planner should treat the outcome as input.

### OQ-1: MCP SDK version + API surface
- Target `mcp >= ?.??`. Current is 1.27.1 (May 2026). Pin floor + ceiling.
- FastMCP vs lower-level `Server` class — confirm FastMCP covers our 5 tools + streaming + Pydantic output. If not, document the gap.
- Tool input/output schema strategy: TypedDict, Pydantic BaseModel, or `dict`? FastMCP supports all three but they have different ergonomics.

### OQ-2: Auth model — local-first vs hosted
- v0.2 default: local-first stdio MCP server (no auth, runs on user's machine). Document this clearly.
- Hosted-server question: Anthropic's MCP spec includes OAuth/bearer-token guidance for remote servers. Should v0.2 ship a hosted-mode toggle, or defer to v0.3?
- Recommendation (researcher provides): if hosted is deferred, what's the minimal "future-proofing" we should bake into the local-first server now to avoid v0.3 rewrite?

### OQ-3: Catalog file format — YAML vs JSON Schema vs custom DSL
- Per-source catalog files: which format?
- Constraints: agent-writable (so agent-generated connectors can produce them), human-reviewable (for the quality-gate before promotion), versionable (clean git diffs), and lint-able (so malformed entries get caught at promotion).
- Researcher proposes 2-3 options with tradeoffs.

### OQ-4: Community contribution model for agent-generated connectors
- Are generated configs PRs? GitHub Issues with attached files? A separate `tradewinds-catalog` repo?
- How does the quality-review gate work in practice — automated tests + human review? Just human review?
- Researcher proposes the lightest-weight model that doesn't add infra (no hosted service in v0.2).

### OQ-5: Pricing model for hosted version (if any)
- v0.2 ships open-source local-first. Is there a hosted offering by v0.3? v1.0?
- This is a business decision more than a technical one. Researcher should flag what the technical surface needs to support each option (e.g., "if we ever sell hosted, we need a license-key concept now" vs "no, we can add that in v0.5 cleanly").

</open_questions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + vision
- [`.planning/phase-05-mcp-data-platform/VISION.md`](VISION.md) — the user-authored vision document (6 components + 5 Open Questions)
- `.planning/ROADMAP.md` (lines 21, 94-110) — Phase 5 section, success criteria, depends-on, execution-order note (Phase 5 starts the v0.2+ milestone)
- `.planning/REQUIREMENTS.md` (lines 101-108 SUPERSEDED, lines 236 ID-collision-note, lines 238-247 canonical MCP-01..MCP-10) — formal requirements text

### Foundations from v0.1 (LOAD-BEARING)
- Phase 2 `tradewinds.core.temporal.TimePoint`, `KnowledgeView`, `LeakageDetector` (when Phase 2 ships) — the temporal-safety primitives Phase 5 wraps
- Phase 2 canonical schemas (`schema.observation.v1`, `schema.forecast.iem_mos.v1`, `schema.settlement.cli.v1`) — the catalog's "schema semantics" layer starts here
- Phase 2 `TradewindsError` hierarchy + `to_dict()` for JSON-RPC serialization
- Phase 2 format serializers (`dataframe`, `json`, `parquet`, `toon`, `csv`) — `toon` is the v0.2 MCP boundary format
- Phase 4 trusted publishing + GH Actions release workflow (Phase 5 publishes `tradewinds-mcp` package via the same pattern)
- Phase 4 `pre-commit` + `pytest -m "not live"` CI pattern (Phase 5 inherits)

### MCP / Anthropic Python SDK
- `mcp` package on PyPI (currently 1.27.1) — pin to be decided in research
- [`modelcontextprotocol/python-sdk`](https://github.com/modelcontextprotocol/python-sdk) — FastMCP pattern, Pydantic integration
- [MCP spec](https://modelcontextprotocol.io/specification) — server protocol; researcher reads to confirm FastMCP coverage

### Constraints from CLAUDE.md
- Tech stack: `mcp >= 1.27.1` (currently in "Deferred to v0.2" section — moves into v0.2 deps for Phase 5)
- No FastAPI / no Docker / no hosted infra by default (Phase 5 can introduce hosted as opt-in, but the default ship is local-first stdio MCP server)
- MIT license maintained
- TDD mandatory (RED → GREEN → REFACTOR), pre-commit + pre-push hooks; no `--no-verify`

### Files that WILL be created (forewarning to planner)
- `packages/mcp/src/tradewinds_mcp/server.py` (or `packages/mcp/src/tradewinds/mcp/server.py` — namespace decision)
- `packages/mcp/src/tradewinds_mcp/tools/` — 5 tools (`list_sources`, `describe_source`, `ingest`, `query`, `get_schema`)
- `packages/mcp/src/tradewinds_mcp/temporal_middleware.py` — the structural KnowledgeView enforcement
- `packages/mcp/src/tradewinds_mcp/audit.py` — append-only JSONL audit logger
- `packages/mcp/catalog/` — per-source catalog files (pre-indexed)
- `packages/mcp/catalog/_generated/` — agent-generated configs awaiting review
- `packages/mcp/pyproject.toml` — `tradewinds-mcp` PyPI distribution
- New repo skeleton for the second-vertical adapter (under `packages/<vertical>/`)

### Files that MAY be modified (forewarning)
- `.planning/REQUIREMENTS.md` — MCP-ID collision cleanup (per LOCKED decision above)
- `packages/markets/` — sports adapter additions if Kalshi horse-racing is the v0.2 second vertical
- `packages/core/src/tradewinds/_v02/` — already exists; v0.2 foundations land here from Phase 2

</canonical_refs>

<specifics>
## Specific Ideas

- **MCP tool surface skeleton (researcher to refine):**
  ```python
  @mcp.tool()
  async def query(
      source_id: str,
      as_of: datetime,  # REQUIRED — no default
      filters: dict | None = None,
      format: Literal["toon", "json"] = "toon",
  ) -> dict:
      """Return rows from source_id knowable at as_of."""
      # 1. Look up source in catalog
      # 2. Run server-side ingest if needed
      # 3. Apply KnowledgeView(as_of=as_of) — STRUCTURAL, can't be bypassed
      # 4. Serialize via format
      # 5. Log to audit.jsonl
      # 6. Return {"format": format, "data": <serialized>, "schema": schema_id}
  ```
- **Catalog entry skeleton (5-layer):**
  ```yaml
  source_id: iem-asos
  display_name: Iowa Environmental Mesonet — ASOS observations
  schema_semantics:
    fields:
      tmpf: "Air temperature, Fahrenheit, °F. NOT 'closing temperature' — instantaneous reading at observation time."
      relh: "Relative humidity 0-100. NULL on station outages."
  temporal_rules:
    knowledge_time: "report_time + report_delay (typically 5-15 min after observed_at for ASOS)"
    backfill_behavior: "Past records DO NOT change after first publish."
  quality_notes:
    - "Pre-2007 records have inconsistent units across stations."
  relationship_mappings:
    joins_to:
      - source: ghcnh
        on: ["station_id", "observed_at"]
        note: "ASOS uses ICAO codes (KNYC), GHCNh uses WBAN (725030). See station_id_map.csv."
  operational_context:
    rate_limit: "1 req/sec per IP (as of 2026-04-21)"
    auth: "none"
    pagination: "year-chunked via _iem_chunks helper"
  ```
- **Audit log entry format (`audit.jsonl`):**
  ```json
  {"ts":"2026-06-01T14:00:00Z","tool":"query","source":"iem-asos","schema":"schema.observation.v1","as_of":"2024-01-15T00:00:00Z","retrieval":"2026-06-01T13:59:59Z","rows":5234,"hash":"sha256:abc..."}
  ```
- **Deterministic-replay test idiom:**
  ```python
  def test_replay_same_query_same_bytes(mcp_server):
      a = mcp_server.call_tool("query", {"source_id": "iem-asos", "as_of": "2024-01-15T00:00:00Z", "filters": {"station": "KNYC"}})
      b = mcp_server.call_tool("query", {"source_id": "iem-asos", "as_of": "2024-01-15T00:00:00Z", "filters": {"station": "KNYC"}})
      assert hashlib.sha256(a["data"].encode()).hexdigest() == hashlib.sha256(b["data"].encode()).hexdigest()
  ```

</specifics>

<deferred>
## Deferred Ideas (NOT in Phase 5)

- **CLI wrapper (`packages/cli/`)** — VISION.md component 6 mentions "CLI wrapper (already planned v1.1+)". v0.2 ships SDK + MCP server only. CLI = v0.2.x or v0.3.
- **Hosted service** — explicitly local-first in v0.2. Hosted = v0.3+ decision (per OQ-5).
- **Third vertical (politics/finance)** — v0.3 minimum. v0.2 ships weather + ONE new vertical only.
- **Real-time streaming MCP tools** — server returns batches, not streams. Streaming is an MCP-protocol feature but adds a layer of complexity (cancellation, backpressure) not needed for ML training-pair extraction.
- **Auth / multi-tenant** — local-first stdio server has no auth. Multi-tenant + auth = v0.3+ if hosted ships.
- **Catalog-entry IDE-style search** — `list_sources` returns the whole catalog (small, ~20 entries at v0.2 ship). Full-text search across catalog = v0.3+ if catalog grows past O(100).
- **Cross-MCP-server federation** — v0.2 ships ONE server with multi-vertical catalog. Per-vertical MCP servers (VISION.md component 1 hint: "Each data vertical … can be its own MCP server") = v0.3+.

</deferred>

<id_collision>
## CRITICAL: MCP-ID Collision Resolution

Per REQUIREMENTS.md line 236 ID-collision note: two sets of MCP-XX identifiers exist in REQUIREMENTS.md:

- **OLD (line 103-108):** `MCP-01..MCP-06` — narrow v0.2 placeholders covering console script, `catalog_search`, `pull_pairs`, `validate_dataframe`, JSON-RPC tests, TOON serialization.
- **NEW (line 238-247):** `MCP-01..MCP-10` — broad Phase 5 vision.

**Decision:** option (b) — DELETE the old narrow MCP-01..MCP-06 entries and treat Phase 5 MCP-01..MCP-10 as canonical. The vision strictly subsumes the narrow list:
- Old MCP-01 (console script) → covered by new MCP-01 (server exposes tools via MCP protocol)
- Old MCP-02 (catalog_search) → covered by new MCP-01 (`list_sources` tool) + new MCP-02 (catalog with 5-layer context)
- Old MCP-03 (pull_pairs) → covered by new MCP-01 (`query` tool) + new MCP-08 (point-in-time API)
- Old MCP-04 (validate_dataframe) → covered by new MCP-07 (schema contract validation on ingest+query)
- Old MCP-05 (JSON-RPC integration tests) → covered by new MCP-06 (auditable provenance — tested via JSON-RPC) + new MCP-09 (deterministic replay)
- Old MCP-06 (TOON serialization) → covered by new MCP-07 (schema contracts) + the LOCKED decision above (toon at boundary)

**Action item for planner:** include a task (OR recommend a `/gsd-quick`) BEFORE Phase 5 execution that:
1. Removes REQUIREMENTS.md lines 101-108 (the OLD MCP Server section under "## v2 Requirements (Deferred)")
2. Removes REQUIREMENTS.md line 236 (the ID-collision note — no longer needed once cleanup is done)
3. Updates REQUIREMENTS.md mapping table — removes `MCP-01..MCP-06` from "Phase 5 / Pending" rows that duplicate the canonical entries; updates footer count.
4. Updates ROADMAP.md if it references the old narrow MCP-XX IDs anywhere (it currently cites only "MCP-01..MCP-10" — should be fine after cleanup).

</id_collision>

---

*Phase: 05-mcp-data-platform*
*Context gathered: 2026-05-22 from VISION.md + inline orchestrator brief*
*Milestone: v0.2+ (post-v0.1.0 ship)*
