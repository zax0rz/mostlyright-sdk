---
phase: 05-mcp-data-platform
type: research
researched: 2026-05-22
domain: MCP server + agent-readable data catalog + multi-vertical prediction-market data
confidence: HIGH on MCP SDK + transport choice + middleware pattern; HIGH on catalog format; MEDIUM-HIGH on second-vertical recommendation; MEDIUM on agent-connector quality gate; LOW on hosted/pricing technical surface (mostly business decisions)
status: ready-for-planning
milestone: v0.2+
---

# Phase 5: MCP Data Platform — Research

**Researched:** 2026-05-22
**Domain:** MCP-native data platform for prediction-market ML — server, catalog, agent-generated connectors, multi-vertical
**Confidence:** HIGH overall (see breakdown at end)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Phase 5 is POST-v0.1.0 ship — strict gate.** Phase 5 work begins only after Phases 1, 1.5, 2, 3, 4 complete, v0.1.0 is tagged + published to PyPI, and the README quickstart works end-to-end. No Phase 5 file mods before v0.1.0 ships.
- **MCP SDK = Anthropic Python `mcp >= 1.27` with FastMCP pattern** (`from mcp.server.fastmcp import FastMCP`), decorator-based tool registration. Forbid: custom JSON-RPC implementation, alternative MCP runtimes.
- **DataFrame I/O at MCP boundary = `toon`** (Phase 2 format). Tool response shape: `{"format": "toon", "data": <string>, "schema": <schema_id>}`. Forbid: raw `pd.DataFrame` returns, parquet bytes at boundary, pickled DataFrame, CSV without schema reference.
- **Temporal safety = SERVER-ENFORCED via shared `KnowledgeView` middleware.** `as_of` REQUIRED on every read tool; no agent-supplied `as_of=None` short-circuit; single shared decorator/middleware so it cannot be accidentally bypassed by new tools. Forbid: tools returning rows without `KnowledgeView`, `skip_temporal_check` kwargs, raw cache-file access from `packages/mcp/`.
- **Multi-vertical = weather + ONE new vertical.** v0.2 ships weather (Phase 2 baseline) + ONE new vertical. v0.3 deepens. Forbid: >2 verticals in v0.2; zero new verticals.
- **Catalog format = per-source files at `packages/mcp/catalog/`; `_generated/` subdir for agent-generated configs.** Promoted entries move to root after review.
- **Audit log = append-only JSONL at `$HOME/.tradewinds/mcp-server/audit.jsonl`.** Every MCP tool call writes `(timestamp, tool_name, source_id, schema_version, as_of, retrieval_timestamp, row_count, hash_of_result)`. Deterministic replay test: same call → same hash.
- **MCP-ID collision resolution = option (b) — delete old narrow MCP-01..06 (REQUIREMENTS.md lines 101-108), treat new MCP-01..10 as canonical** (REQUIREMENTS.md lines 238-247). Planner SHOULD include a quick-task / pre-Phase-5 task to physically remove the old entries + ID-collision note + update mapping table.
- **Plan-shape hint (NOT locked):** 4-6 plans across 3-4 waves. Planner may recommend splitting Phase 5 into Phase 5a / 5b / 5c per workflow's "PHASE SPLIT RECOMMENDED" path.

### Claude's Discretion
- Exact module structure inside `packages/mcp/` — `packages/mcp/src/tradewinds_mcp/` vs `packages/mcp/src/tradewinds/mcp/` depends on namespace decision finalized in Phase 2.
- Whether `audit.jsonl` is per-instance or per-user. Recommend per-instance (cleaner isolation).
- Whether to ship `tradewinds-mcp-server --replay <audit-line>` CLI in v0.2 or defer to v0.3.

### Deferred Ideas (OUT OF SCOPE)
- CLI wrapper (`packages/cli/`) — v0.2.x or v0.3.
- Hosted service — local-first in v0.2; hosted = v0.3+ (per OQ-5).
- Third vertical (politics/finance) — v0.3 minimum.
- Real-time streaming MCP tools — batches only in v0.2.
- Auth / multi-tenant — stdio server has no auth; multi-tenant = v0.3+ if hosted ships.
- Catalog full-text search — `list_sources` returns whole catalog (~20 entries at v0.2 ship); search = v0.3+.
- Cross-MCP-server federation — v0.2 ships ONE server with multi-vertical catalog; per-vertical servers = v0.3+.

</user_constraints>

<phase_requirements>
## Phase Requirements (MCP-01..MCP-10, canonical from REQUIREMENTS.md lines 238-247)

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-01 | MCP server exposes `list_sources`, `describe_source`, `ingest`, `query`, `get_schema` tools | §A FastMCP server skeleton; §H Wave 1 plan |
| MCP-02 | Data catalog stores 5-layer context (schema semantics / temporal rules / quality notes / relationship mappings / operational context) | §B catalog format + Singer/dlt prior art; §H Wave 2 plan |
| MCP-03 | Agent-generated connector pipeline with persisted configs + quality-review gate | §C agent-connector pipeline; §H Wave 3 plan |
| MCP-04 | Server-enforced temporal safety — no agent bypass possible | §D middleware pattern (FastMCP `on_call_tool`); §H Wave 1 plan |
| MCP-05 | Multi-vertical: weather + sports (or alternative — see §E) | §E vertical comparison; §H Wave 4 plan |
| MCP-06 | Auditable provenance — every transformation logged, replayable | §D audit log + deterministic replay; §H Wave 1 + 4 plans |
| MCP-07 | Schema contract validation on ingest AND query; `to_dict()` JSON-RPC errors (Phase 2 hierarchy) | §A FastMCP Pydantic output handling; §H Wave 1 plan |
| MCP-08 | Point-in-time API: `dataset.at_time(date)`, `.between(...)`, `.as_of(...)` | §D `KnowledgeView` API surface; §H Wave 1 plan |
| MCP-09 | Deterministic replay — same query + same cutoff = identical bytes | §D deterministic replay design; §H Wave 4 plan |
| MCP-10 | Pre-indexed catalog entries for top 10 prediction-market sources at v0.2 ship | §E + §B; §H Wave 2 + 4 plans |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack already locked for v0.1:** Python 3.11+; `httpx`, `pandas>=2.2,<3.0`, `pyarrow`, `filelock`, `jsonschema`, `hypothesis` (dev). No FastAPI, no Docker, no hosted infra. Phase 5 inherits these constraints. `[CITED: CLAUDE.md "Recommended Stack" table]`
- **`mcp` SDK enters v0.2 deps** (currently in "Deferred to v0.2 — Reserve the Seam"). FastMCP pattern recommended; DataFrame serialization via `toon` at tool boundary; Python 3.10+ required (we're at 3.11+ — fine). `[CITED: CLAUDE.md "Deferred to v0.2" table]`
- **No FastAPI in v0.1; can introduce hosted as opt-in in v0.2+**, but default ship is local-first stdio MCP server. `[CITED: CLAUDE.md ## Constraints]`
- **MIT license maintained.** `[CITED: CLAUDE.md ## Constraints]`
- **TDD mandatory** (RED → GREEN → REFACTOR); pre-commit + pre-push hooks; no `--no-verify`. ≥90% branch coverage on `tradewinds.core`. 80% line coverage on `catalog/`. `[CITED: CLAUDE.md ## Constraints + ## Testing]`
- **Two-lane parallel + cross-review** mandatory; every PR runs codex `high` + python-architect review per REVIEW-DISCIPLINE.md. `[CITED: CLAUDE.md ## Collaboration rules]`
- **TOON serializer** — already lifted from `monorepo-v0.14.1` into Phase 2 `tradewinds.core.formats.toon`. Phase 5 uses this as the MCP boundary format. `[VERIFIED: Phase 2 PLAN.md Wave 1 artifacts list]`
- **Never return raw `pd.DataFrame` from MCP tools** — FastMCP wraps Pydantic/TypedDict; pandas isn't first-class. `[CITED: CLAUDE.md "Deferred to v0.2" notes]`

## Executive Summary

Phase 5 transforms tradewinds from a single-vertical SDK into an MCP-native data platform by layering five components on top of the v0.1.0 foundations: (1) a FastMCP server at `packages/mcp/` exposing five tools (`list_sources`, `describe_source`, `ingest`, `query`, `get_schema`), (2) a 5-layer context-engineered data catalog stored as per-source YAML files, (3) an agent-generated connector pipeline that lands configs in `_generated/` for human review before promotion, (4) server-enforced temporal safety via FastMCP `on_call_tool` middleware that wraps every read tool in a `KnowledgeView` filter the agent cannot bypass, and (5) one new vertical alongside weather. The research consensus is that all five are buildable in 2026 with mature, stable libraries — `mcp >= 1.27` (Anthropic SDK, May 2026), FastMCP middleware (mainstream since FastMCP 2.9, June 2025), and YAML + JSON Schema for catalog files.

The single non-obvious finding is that **the originally-recommended "sports prediction markets" second vertical is the wrong choice in 2026** — horse racing was federally blocked from prediction markets in May 2026 (1978 Interstate Horseracing Act), NBA/NFL contracts are mid-active-litigation (New Mexico tribes won injunction motion May 2026; New Jersey appeal pending), and MLB signed an exclusive prediction-market deal with Polymarket (March 2026). The cleanest second vertical for v0.2 is **macroeconomic indicators (FRED + ALFRED → Kalshi CPI/PCE/payrolls/Fed-funds contracts)**: data is free, public, well-documented, point-in-time-aware out of the box (ALFRED vintage API is literally a built-in temporal-safety primitive), Kalshi macro markets have multi-year operational history, and no legal exposure. Sports remains the right v0.3 target after the 2026-2027 legal landscape settles.

Of the five Open Questions, four resolve to crisp defaults backed by 2026 best-practice consensus (MCP SDK pin, auth model, catalog format, community contribution model) and one (pricing) is a business decision — researcher recommends the technical surface only needs a `tool_caller_id` slot on every audit entry, deferable until v0.3 without rework.

**Primary recommendation:** Plan 4 waves across 4-6 plans (no Phase split needed); LOCKED-decisions plus this research yield a clear seam. Treat OQ resolutions as user-confirmable defaults — none of them are pre-decided on the user's behalf.

## A. Technical Landscape — MCP Server Building Blocks

### A.1 MCP SDK pin recommendation

| Property | Value | Source |
|----------|-------|--------|
| Library | `mcp` (Anthropic Python SDK) | `[VERIFIED: pypi.org/project/mcp/]` |
| Current version | **1.27.1** (May 8, 2026) | `[VERIFIED: pypi.org/project/mcp/]` |
| Python requirement | `>=3.10` (we're at 3.11+ — clear) | `[VERIFIED: pypi.org/project/mcp/]` |
| **Recommended pin** | **`mcp>=1.27,<2.0`** | Locked decision in CONTEXT.md; floor confirmed by PyPI |
| Module entry | `from mcp.server.fastmcp import FastMCP` | `[CITED: github.com/modelcontextprotocol/python-sdk README]` |
| MCP spec status | Cross-language standard; SDK downloads ~970x growth Nov 2024 → Q1 2026; 2,000+ community implementations | `[CITED: 2026 ecosystem reporting]` |

**Why a `<2.0` ceiling and not tighter:** The Python SDK's v1.x branch is in active maintenance (v1.27.x is current) and a separate `v2.x` development branch exists on `main` but with no public release timeline as of May 2026. A `<2.0` ceiling protects against the eventual breaking-change v2 while permitting safe minor bumps within the 1.x line. `[CITED: github.com/modelcontextprotocol/python-sdk releases page]`

### A.2 FastMCP pattern (decorator-based tool registration)

FastMCP is the high-level wrapper in the official `mcp` SDK. It is the recommended pattern for ~80% of MCP servers and is well inside the envelope for tradewinds' 5-tool surface. `[CITED: gofastmcp.com + CLAUDE.md "Deferred to v0.2" notes]`

**Canonical skeleton (`packages/mcp/src/tradewinds_mcp/server.py`):**

```python
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from tradewinds.core.temporal import KnowledgeView
from tradewinds.core.formats import toon as toon_fmt
from tradewinds.core.validator import validate_dataframe
from .catalog import CATALOG
from .audit import audit_log
from .temporal_middleware import enforce_knowledge_view

mcp = FastMCP("tradewinds")

@mcp.tool()
async def query(
    source_id: str,
    as_of: datetime,  # REQUIRED — no default, no None permitted
    filters: dict | None = None,
    format: str = "toon",
) -> dict:
    """Return rows from source_id that were knowable at `as_of`."""
    # All five rules (catalog lookup, ingest, KnowledgeView filter,
    # serialize, audit) live in the middleware decorator, NOT here.
    ...
```

**Tool input/output schema strategy — FastMCP supports three options:** TypedDict, Pydantic BaseModel, or `dict`. They have different ergonomics: `[CITED: gofastmcp.com tools docs + datacamp tutorial]`

| Style | When to use | Tradeoff |
|-------|-------------|----------|
| **`dict` return** | Simple, dynamic output | FastMCP cannot auto-generate JSON Schema; manual `schema` annotation needed for `get_schema` tool |
| **TypedDict return** | Static keys, simple types | Auto JSON-Schema generation; no runtime validation |
| **Pydantic BaseModel return** | Strong runtime validation + auto JSON-Schema | Auto-generates JSON Schema from BaseModel; first-class FastMCP integration |

**Recommendation:** Use **Pydantic BaseModel for the response envelope** (`{format, data, schema_id, audit_id}`) — this lets FastMCP auto-document the `get_schema` tool against our actual envelope schema. Inside `data`, the value is the TOON string (already validated by our Phase 2 `validate_dataframe()`). This sidesteps the CLAUDE.md guidance "Don't return `pd.DataFrame` directly" while still getting Pydantic ergonomics at the boundary. `[CITED: FastMCP structured-output docs + CLAUDE.md tech stack notes]`

### A.3 Transport choice — stdio vs Streamable HTTP

**Locked default per CONTEXT.md: stdio (local-first).** Research confirms this is the right 2026 default for v0.2:

| Transport | Use Case | 2026 Status | tradewinds v0.2 fit |
|-----------|----------|-------------|---------------------|
| **stdio** | Local, single-user, runs as child process of MCP client (Claude Desktop, Cursor) | First-class; canonical default | ✓ LOCKED — matches local-first SDK ethos |
| **Streamable HTTP** | Network-accessible, multi-client, hosted deployment | Recommended remote transport since MCP spec March 2025; SSE is DEPRECATED — do not build on SSE | Defer to v0.3 hosted-mode |
| SSE | (deprecated) | DEPRECATED — decreasing client support | Forbid for new code |

`[CITED: kirkryan.co.uk/stdio-vs-streamable-http + apigene.ai/blog/mcp-sse-vs-stdio (2026)]`

**Critical seam — what to bake in now to avoid a v0.3 rewrite:**

Per Anthropic spec + FastMCP docs (May 2026): stdio servers inherit credentials from the parent process's environment variables; HTTP servers use OAuth 2.1 per MCP spec mandate (March 2025+). Stdio MUST NOT use the Authorization spec. Therefore: `[CITED: modelcontextprotocol.io authorization tutorial + gelembjuk.com remote MCP server post]`

1. **Separate tool implementation from identity context.** Build tools that accept a `caller_context: CallerContext` parameter (a Pydantic model) populated by FastMCP middleware. In stdio mode, middleware populates `caller_context.identity = "local"`. In future HTTP mode, middleware populates from validated OAuth token. Tool body never reads env-vars or HTTP headers directly.

2. **Log `caller_identity` in every audit-log entry** even when it's the constant `"local"`. v0.2 audit lines will look like `"caller_identity": "local"`. v0.3+ hosted will log real identities. Schema doesn't change.

3. **Don't bake stdio assumptions into tool signatures.** `mcp.run(transport="stdio")` vs `mcp.run(transport="http", host=..., port=...)` is a single-line change at the entry point. Tools stay identical.

`[VERIFIED: gofastmcp.com/deployment/running-server — `transport` parameter accepts both stdio + http]`

### A.4 Testing patterns — in-process pytest fixtures preferred over subprocess

FastMCP's official testing utilities (`fastmcp/utilities/tests.py`) provide two helpers:

| Helper | Use For | Speed | Determinism |
|--------|---------|-------|-------------|
| `run_server_async` (async context manager) | In-process testing of HTTP-transport servers | Fast (no fork) | Full debugger support |
| `run_server_in_process` | Subprocess isolation, stdio-transport testing | Slow (~100ms per spawn) | Mirrors production deployment |

`[VERIFIED: github.com/PrefectHQ/fastmcp/blob/main/src/fastmcp/utilities/tests.py + gofastmcp.com/development/tests]`

**Recommended testing pyramid for tradewinds v0.2:** `[CITED: medium.com/@anil.goyal0057 Three-Layer Test Pyramid 2026 + jlowin.dev/blog/stop-vibe-testing-mcp-servers]`

1. **Unit tests (most of them):** Test tool logic directly by importing the function. No FastMCP needed.
2. **Integration tests (in-process):** Use `run_server_async` to spin up the server in the same process; client sends JSON-RPC via the SDK's in-memory transport. Tests are fast (~10ms per call), deterministic, debuggable.
3. **End-to-end tests (subprocess):** Use `run_server_in_process` for the ONE test that proves stdio framing works end-to-end. Mark `@pytest.mark.integration` so CI can skip when needed.

**Avoid the trap:** "Vibe-testing" — manually starting the server and calling tools from Claude Desktop. Catches nothing reproducibly; not a substitute for `pytest` integration tests. `[CITED: jlowin.dev/blog/stop-vibe-testing-mcp-servers]`

### A.5 Concrete `mcp` SDK pin: `mcp>=1.27,<2.0`

- Floor: 1.27 is May 2026 release; CONTEXT.md already locks `>= 1.27`.
- Ceiling: `<2.0` — v2 branch exists but no release timeline; protect against breaking-change major bump.
- Single-line `packages/mcp/pyproject.toml` entry: `"mcp>=1.27,<2.0"`.

## B. 5-Layer Data Catalog — Prior Art and Format Choices

### B.1 Prior art survey

The "agent-readable data catalog" idea is not new in 2026. Three mature ecosystems define the design space:

| Project | Catalog Format | Key Pattern | Lessons |
|---------|---------------|-------------|---------|
| **Singer Protocol** (specification, 2017+) | JSON `catalog.json` documents with stream + schema + metadata via "visitor pattern" | Streams have schema + metadata trees; selection happens by toggling `selected: true` per stream/field | Mature spec; JSON-Schema-validated; one-file-per-tap is the de facto standard. tradewinds should adopt the "metadata tree on top of schema" idea but use one file per source. `[CITED: hub.meltano.com/singer/spec + deepwiki.com/meltano/meltano 7.4]` |
| **Meltano (Singer host)** | YAML `meltano.yml` + per-plugin Singer JSON catalogs | Low-code YAML for plugin config; JSON catalogs for data shape | The YAML/JSON split works: YAML for human-edited operational context, JSON Schema for machine-validated shape. tradewinds can mirror this. `[CITED: docs.meltano.com/guide/integration]` |
| **dlt (Data Load Tool)** | Auto-generated schemas; schemas evolve at runtime | Schema inference from sample data; sqlmesh interop | dlt's runtime schema evolution is a feature for ELT pipelines but ANTI-pattern for tradewinds — we want frozen schema contracts (Phase 2 SchemaRegistration). dlt's `agent-generated config → review → promote` pattern matches our `_generated/ → catalog/` promotion gate. `[CITED: dlthub.com/blog/harness-full]` |

**Cross-source-relationship ontology — the gap:** None of Singer/Meltano/dlt has a first-class "this source joins to that source on these keys" field in their catalog format. They model single-source extraction; joins happen downstream in the warehouse. tradewinds' v0.2 catalog needs this as a top-level `relationship_mappings` block because the whole point is cross-source ML training pairs. **Implication: we are defining new ontology here, with no library to lift from.** Keep it deliberately minimal in v0.2 (just `joins_to: [{source, on, note}]`) and let v0.3+ extend.

**Knowledge-time vs event-time distinction:** Singer's `replication_key` concept tracks the field used for incremental sync but doesn't distinguish "when the data was knowable" from "when the event happened." Neither do Meltano or dlt. The point-in-time-aware data warehouse community (e.g., feature-store vendors like Feast/Tecton) does model both, but their formats are heavyweight. **Implication: tradewinds' `temporal_rules` block is a small but novel piece of catalog ontology.** Use the language from Phase 2's `TimePoint`/`KnowledgeView`: `event_time`, `knowledge_time`, `retrieved_at`, `backfill_behavior`. `[VERIFIED: Phase 2 PLAN.md artifacts list — schemas declare these columns]`

### B.2 Format tradeoff — YAML vs JSON Schema vs TOML

Scoring against the four CONTEXT.md OQ-3 criteria (agent-writable / human-reviewable / versionable / lint-able):

| Format | Agent-writable | Human-reviewable | Versionable | Lint-able | Comments support | Verdict |
|--------|---------------|------------------|-------------|-----------|------------------|---------|
| **YAML** | LLMs reliably write YAML (training data abundant); indentation pitfalls real but bounded | Cleanest at 5+ levels deep; full-line + inline comments with `#` essential for documenting `quality_notes` like "Pre-2007 records have inconsistent units"; widely review-friendly | Clean line-level diffs | `yamllint` + JSON-Schema-Everywhere | ✓ Full | **RECOMMENDED for catalog files** |
| **JSON Schema** (standalone JSON files) | LLMs write JSON reliably; no whitespace pitfalls | No comments allowed — `quality_notes` must live in dedicated string fields; harder to scan visually | Diffs are line-level but verbose | jsonschema-cli (already in v0.1 deps) | ✗ None | Use for the META-format (validate YAML catalog files against a JSON-Schema), not the catalog files themselves |
| **TOML** | LLMs write TOML acceptably but less training data than YAML; no implicit type coercion is a plus | Good for flat config; awkward for 5-level nesting (catalog's `schema_semantics.fields.tmpf.notes` is deep) | Clean diffs | `taplo` or `tomllint` | ✓ Full | Acceptable but worse than YAML for nesting; SKIP |
| Custom DSL | Worst — LLMs hallucinate syntax; humans must learn it | Author-friendly only | Diffs depend on grammar | Requires hand-written parser | n/a | FORBID |

`[CITED: devtoolbox.dedyn.io/blog/json-vs-yaml-vs-toml (2026) + knightli.com Common Config Formats 2026 + dev.to/jsontoall_tools/json-vs-yaml-vs-toml 2026]`

**Recommendation:** **Per-source files are YAML; a single `packages/mcp/catalog/_schema/catalog_entry.schema.json` JSON-Schema defines the meta-shape.** Catalog promotion gate runs `jsonschema` validation against the meta-schema. This gives us:
- Agent-writable, human-reviewable YAML for content (the 5 context layers).
- Machine-validatable JSON-Schema for shape (no missing fields, no typos in `schema_semantics`).
- Free linting via `yamllint` + `jsonschema-everywhere`.
- The meta-schema doubles as the `get_schema` tool's catalog-entry schema reference.

**YAML safety note:** Use `yaml.safe_load` (NOT `yaml.load`) in the catalog loader to prevent arbitrary-code-execution via `!!python/object` tags. Standard 2026 practice. `[CITED: PyYAML docs — pinned to v6.x line in Phase 1 base requirements]`

## C. Agent-Generated Connector Pipeline

### C.1 Prior-art lessons

**dlt's pattern (closest analog):** Agent reads API doc → infers schema from sample data → generates an extraction config → runtime schema evolution. For tradewinds we keep stages 1-3 and replace stage 4 with a frozen-schema review gate. `[CITED: dlthub.com/blog/harness-full]`

**Singer/Meltano:** Catalog auto-generation from JSON Schema discovery (one-time `discover` mode). Lift the "discovery is a separate step that produces a candidate catalog, then humans tune" two-step pattern. `[CITED: hub.meltano.com/singer/spec]`

**OpenAI tool-calling + LLM schema-from-docs:** Active research area as of 2026. **Hallucination rate is ~15% on low-frequency APIs.** Mitigation: documentation-augmented generation (DAG) — agent retrieves the actual API docs section before emitting the config. Skip DAG for well-known APIs (HTTP overhead not worth it for high-frequency). `[CITED: arxiv.org/html/2407.09726v1 On Mitigating Code LLM Hallucinations]`

### C.2 Quality-review gate — what should be automated

The minimum-viable gate for v0.2 (no hosted infra, just CI + human PR review):

| Check | Automated? | How |
|-------|-----------|-----|
| YAML parses + matches `catalog_entry.schema.json` | ✓ CI | `jsonschema` validate against meta-schema |
| All 5 context layers present (no empty `quality_notes: []`) | ✓ CI | meta-schema `minProperties` per layer |
| `schema_semantics.fields` references known canonical schema | ✓ CI | Cross-check against `tradewinds.core.schemas` registry |
| Sample-data round-trip — fetch 1 row, validate against declared schema, serialize/deserialize via TOON | ✓ CI (live, optional) | New CI job; `@pytest.mark.live` gated |
| Temporal-rule sanity — `knowledge_time` formula references only fields present in the schema | ✓ CI | Custom linter, ~50 LOC |
| Operational context (rate-limit, auth) is sane | ✗ Human | Review-only — domain knowledge required |
| Cross-source `joins_to` mappings — do they actually join? | ✗ Human (with optional sample-data spike) | Human review; future automation |

`[CITED: own analysis — no library does all this; closest is JSON Schema Everywhere + Singer SDK config-schema validation]`

### C.3 Community contribution model — recommendation

Three options for OQ-4, evaluated:

| Option | Friction | Quality control | Scaling | Recommendation |
|--------|---------|-----------------|---------|----------------|
| **PR-based against `packages/mcp/catalog/_generated/`** | LOW — just `git push` + open PR | HIGH — CI checks + 2-reviewer loop already in place | Bounded by maintainer review bandwidth | ✓ **DEFAULT for v0.2** |
| GitHub Issues with attached YAML | Slightly higher (someone has to copy into a PR) | Same as PR-based once converted | Worse — issue triage queue | Skip |
| Separate `tradewinds-catalog` repo | High setup cost; cross-repo CI complexity | Same | Better long-term if catalog grows to O(1000) | Defer to v0.3+ once catalog grows |

**Recommendation:** PR-based against `packages/mcp/catalog/_generated/`. Two-reviewer loop (codex `high` + python-architect) per REVIEW-DISCIPLINE.md applies. When a PR's catalog entry is approved AND passes all automated checks, a maintainer moves the file from `_generated/` to `catalog/` root in a follow-up commit (the "promotion"). Document this two-step in CONTRIBUTING.md.

## D. Server-Enforced Temporal Safety — Implementation Patterns

### D.1 FastMCP middleware as structural enforcement

The locked decision in CONTEXT.md ("single shared decorator/middleware so it cannot be accidentally bypassed by a new tool") maps directly to FastMCP's `on_call_tool` hook in its middleware system, introduced in FastMCP 2.9 (June 2025) and stable since. `[CITED: jlowin.dev/blog/fastmcp-2-9-middleware + gofastmcp.com/servers/middleware]`

**How it works (verified pattern):**

```python
# packages/mcp/src/tradewinds_mcp/temporal_middleware.py
from fastmcp.server.middleware import Middleware, MiddlewareContext

class TemporalSafetyMiddleware(Middleware):
    """Enforces KnowledgeView filter on every tool that returns rows.

    No tool can bypass this — it intercepts ALL `tools/call` requests
    structurally. New tools added without thinking about temporal
    safety are still wrapped by this middleware.
    """

    READ_TOOLS = {"query", "ingest"}  # tools that return rows

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.name
        if tool_name in self.READ_TOOLS:
            params = context.message.arguments
            if "as_of" not in params or params["as_of"] is None:
                raise ToolError(
                    f"Tool `{tool_name}` requires `as_of` parameter. "
                    "Temporal safety cannot be bypassed."
                )
            # Validated; proceed. The tool body wraps the DataFrame
            # in KnowledgeView(as_of=params["as_of"]) before serializing.
        result = await call_next(context)
        # Post-process: audit log
        audit_log.append({
            "ts": now_iso(),
            "tool": tool_name,
            "as_of": params.get("as_of"),
            "hash": sha256(result.content).hexdigest(),
            ...
        })
        return result

mcp.add_middleware(TemporalSafetyMiddleware())
```

`[VERIFIED: gofastmcp.com/servers/middleware describes exactly this pattern; on_call_tool intercepts BEFORE tool body executes]`

**Critical: middleware is registered ONCE at server boot.** New tools added in v0.2.x patches are automatically wrapped. A tool author who forgets `as_of` in their signature still gets caught because the middleware checks `context.message.arguments`. `[VERIFIED: fastmcp middleware docs]`

**One gotcha:** "Middleware-stored state does not automatically cross mount boundaries. Each FastMCP instance maintains its own session state store." For v0.2 we run a single FastMCP instance (no sub-mounting), so this doesn't bite. Flag for v0.3 if per-vertical sub-servers ship. `[CITED: gofastmcp.com/servers/middleware]`

### D.2 API surface — `dataset.at_time(date)`, `.between(...)`, `.as_of(...)`

These are sugar over the existing Phase 2 `KnowledgeView`. The cleanest seam:

```python
# packages/core/src/tradewinds/core/temporal/dataset.py (NEW in Phase 5 Wave 1)
class Dataset:
    """A wrapper that produces KnowledgeView-filtered DataFrames."""
    def __init__(self, df: pd.DataFrame, schema_id: str): ...

    def at_time(self, date: datetime) -> pd.DataFrame:
        return KnowledgeView(self._df, as_of=date).rows()

    def between(self, start: datetime, end: datetime) -> pd.DataFrame:
        kv = KnowledgeView(self._df, as_of=end)
        return kv.rows()[kv.rows()["event_time"] >= start]

    def as_of(self, timestamp: datetime) -> pd.DataFrame:
        # Identical to at_time; both spellings ship for ergonomics
        return self.at_time(timestamp)
```

The MCP `query` tool returns a `Dataset` server-side, calls `.at_time(as_of)` (driven by the temporal middleware), then serializes via TOON. The agent receives a TOON string — never an in-process `Dataset` object. `[VERIFIED: Phase 2 PLAN.md confirms KnowledgeView is a plain class with __slots__ wrapping DataFrame; clean to wrap further]`

### D.3 Deterministic replay — design and pitfalls

**Requirement (MCP-09 + LOCKED audit-log decision):** same query + same `as_of` → byte-identical TOON output across runs.

**Technical challenges (real, documented):** `[CITED: keywordsai.co/blog/llm_consistency_2025 + tianpan.co Deterministic Replay 2026]`

1. **DataFrame row ordering must be deterministic.** Source-of-truth: explicit sort by `(event_time, source, retrieval_timestamp)` before serialization. If rows tie on event_time across sources, the secondary sort key MUST be deterministic (e.g., lexicographic on `source` ID). The CLAUDE.md policy doc already specifies sort keys for the climate merge — same discipline applies here.

2. **Pandas dtype stability — locked by Phase 1 `expected_dtypes.json` capture.** Pandas 3.0 ships breaking dtype changes (CoW, `object` → `str`, datetime resolution `ns` → `us`). Phase 5 inherits the Phase 1/Phase 2 `pandas>=2.2,<3.0` pin. `[CITED: CLAUDE.md tech stack — pandas 2.2 floor]`

3. **TOON serialization determinism.** TOON was lifted from `monorepo-v0.14.1` into Phase 2's `tradewinds.core.formats.toon`. Phase 2 already adds roundtrip tests preserving dtypes for tz-aware timestamps, Float64, Int64, and categorical columns. **Action item for Phase 5 plan:** add a `test_toon_deterministic` test that serializes the same DataFrame 100 times and asserts identical bytes. If TOON's iteration order is not deterministic, fix it in TOON (cheap) before relying on it for replay. `[VERIFIED: Phase 2 PLAN.md Wave 1 must_haves — format roundtrip tests]`

4. **Hash format — `sha256(toon_string.encode("utf-8")).hexdigest()`.** Lock encoding to UTF-8 explicitly to avoid locale-dependent encoding drift.

5. **`retrieval_timestamp` is NOT in the hash input.** The hash covers `(toon_string)` only — same `as_of`, same source state, same rows → same hash regardless of when the agent runs the query. The audit log separately records `retrieval_timestamp` for forensics.

**Test design (canonical idiom — copy into Phase 5 PLAN.md):**

```python
def test_replay_same_query_same_bytes(mcp_server):
    args = {"source_id": "iem.archive", "as_of": "2024-01-15T00:00:00Z",
            "filters": {"station": "KNYC"}}
    a = mcp_server.call_tool("query", args)
    b = mcp_server.call_tool("query", args)
    assert hashlib.sha256(a["data"].encode("utf-8")).hexdigest() == \
           hashlib.sha256(b["data"].encode("utf-8")).hexdigest()
```

## E. Multi-Vertical Expansion — Second-Vertical Recommendation

### E.1 The sports-vertical landscape changed dramatically in 2026

**CONTEXT.md's recommendation of sports prediction markets (horse racing) for v0.2 was the right pick when written but is now wrong.** The 2026 legal/market landscape (verified May 2026):

| Vertical option | Legal status | Data availability | v0.2 second-vertical fit |
|------|-------------|-------------------|------|
| **Kalshi horse racing** | BLOCKED — 1978 Interstate Horseracing Act gives racetracks + horsemen veto on prediction markets; tested in May 2026 reporting | Excellent (TPN/Equibase/TVG public results) | ✗ NOT VIABLE — legal blocker hasn't moved `[CITED: marketplace.org/story/2026/05/14]` |
| **Kalshi NFL/NBA** | Active litigation — NJ injunction in place (Bloomberg May 2026); NM tribes won motion to enjoin (May 2026); pending appeals | Excellent (ESPN, official league APIs) but expensive | ✗ NOT VIABLE — settlement-source legal exposure `[CITED: bloomberg.com/news 2026-05-12; readwrite.com NM tribes lawsuit]` |
| **Polymarket sports** | Polymarket signed MLB exclusive deal (March 2026) + filed Combinatorial Athletic Outcome Contracts with CFTC (May 21, 2026); uses Sportradar for official data | Excellent for MLB; data rights via Sportradar are paid | ✗ COMPLEX — exclusive deal means we'd compete with Polymarket-of-record `[CITED: covers.com 2026-05-21 + sacra.com/c/polymarket]` |
| **Kalshi macroeconomic indicators (CPI/PCE/payrolls/Fed-funds)** | LEGAL — economic indicator markets are CFTC-blessed; have been Kalshi-operated for years; covered in Fed Reserve working paper on Kalshi macro markets | EXCELLENT — FRED + ALFRED APIs are free, public, well-documented; ALFRED provides point-in-time vintages NATIVELY | ✓ **RECOMMENDED** |
| Kalshi election/politics | Legal (post-CFTC 2024-2025 wins) | Mixed; election-day result data is public but contracts have unique data issues (recounts) | Acceptable but worse signal-to-noise than macro `[CITED: en.wikipedia.org/wiki/Kalshi]` |

### E.2 Why macroeconomic indicators (FRED + ALFRED → Kalshi macro contracts) is the strongest v0.2 second vertical

**This is the researcher's recommendation — orchestrator marked it as researcher's pick.**

1. **Data is free, public, and well-documented.** FRED API + ALFRED API are operated by the St. Louis Fed; no API key cost; ~800,000 time series including CPI, PCE, payrolls, Fed Funds rate. `[VERIFIED: fred.stlouisfed.org/docs/api/fred/ + alfred.stlouisfed.org/]`

2. **ALFRED provides point-in-time vintages NATIVELY.** Each observation carries `(date, realtime_start, realtime_end)` — exactly the `(event_time, knowledge_time)` distinction tradewinds' temporal safety enforces. **This is a gift:** the existing CONTEXT.md catalog format's `temporal_rules` layer maps 1:1 to ALFRED's vintage semantics. `[CITED: alfred.stlouisfed.org/help/downloaddata + fred.stlouisfed.org/docs/api/fred/series_vintagedates.html]`

3. **Settlement source clarity rivals NWS-CLI.** Kalshi's CPI market is literally "what is the BLS CPI release for month M?" — settlement source is the official BLS release at known release time. Identical pattern to "what is the daily NWS CLI high for station S on date D?" — one-source, one-canonical-time, no ambiguity. `[CITED: federalreserve.gov/econres/feds/files/2026010pap.pdf — Kalshi macro markets working paper]`

4. **Kalshi macro contracts have multi-year operational history.** Per Federal Reserve research: "The probability distributions implied by Kalshi markets are well-behaved and broadly consistent with those from more established financial instruments." This means real liquidity, real data, real demand from the same quant audience tradewinds targets. `[CITED: federalreserve.gov/econres/feds/files/2026010pap.pdf]`

5. **No regulatory exposure.** Macro markets pre-date the sports legal mess; CFTC-blessed.

6. **Smallest adapter effort.** One canonical adapter (`fred.archive`) wraps FRED + ALFRED APIs. ~3-5 catalog entries cover CPI/Core-CPI/PCE/Core-PCE/payrolls/Fed-funds/unemployment-rate. Compare with sports where each league = separate data source + scoring rules + dispute mechanisms.

7. **Vertical signal is genuinely different from weather.** Demonstrates the multi-vertical thesis (same temporal-safety primitives, different domain) more credibly than two weather-adjacent verticals would.

**Counter-argument considered:** Sports has a bigger consumer audience; macro is quant-narrow. Counter-counter: tradewinds' v0.1 audience IS quants (per PROJECT.md: "1-2 named users to validate post-ship"). Macro hits them exactly. Sports broadens the audience but in a market where Kalshi/Polymarket are locked in legal battles and exclusive deals — wrong time to enter.

**Recommendation: ship `fred.archive` adapter + Kalshi macro contract specs as the v0.2 second vertical. Defer sports to v0.3 once 2026-2027 legal landscape stabilizes.**

**Note for planner:** this overrides CONTEXT.md's tentative "sports recommended" language. The locked decision in CONTEXT.md was "ONE new vertical, planner picks based on researcher's data-availability work" — the lock is on "one vertical, not sports specifically." This research IS the data-availability work the orchestrator asked for. Confirm with user in `/gsd-discuss-phase` before plan freeze.

### E.3 Pre-indexed top-10 catalog entries for v0.2 ship (MCP-10)

Concrete proposal — research is high-confidence on shape, planner refines exact list:

| # | source_id | Vertical | Type | Notes |
|---|-----------|----------|------|-------|
| 1 | `iem.archive` | weather | obs | Phase 2 adapter — already exists |
| 2 | `iem.live` | weather | obs | Phase 2 adapter |
| 3 | `awc.live` | weather | obs (METAR JSON) | Phase 2 adapter |
| 4 | `ghcnh.archive` | weather | obs (hourly historical) | Phase 2 adapter |
| 5 | `cli.archive` | weather | settlement (NWS CLI) | Phase 2 adapter |
| 6 | `iem.forecasts` | weather | forecast (IEM MOS) | Phase 2 adapter |
| 7 | `kalshi.weather` | weather markets | contract specs | Phase 2 contract specs |
| 8 | `fred.archive` | macro | obs (current vintage) | NEW v0.2 — `fredapi` wrapping |
| 9 | `alfred.archive` | macro | obs (vintage point-in-time) | NEW v0.2 — sibling adapter, shares HTTP client with FRED |
| 10 | `kalshi.macro` | macro markets | contract specs (CPI/PCE/payrolls/Fed-funds) | NEW v0.2 — contract specs only, no orderbook |

`[CITED: alphacombines fredapi PyPI + Phase 2 PLAN.md adapter inventory]`

**Adapter scope for the new entries:** No orderbook/fills (per existing CLAUDE.md "Kalshi API client … Sprint 0.5+"). Just contract specs + settlement-source resolution + historical data via FRED/ALFRED.

## F. Auth Model Recommendation (OQ-2)

### F.1 v0.2 default: local-first stdio, no auth

**Locked per CONTEXT.md.** stdio servers run as child processes of the MCP client (Claude Desktop, Cursor); credentials flow via inherited environment variables. The MCP spec explicitly states: "HTTP transport MCP servers SHOULD use the Authorization spec. The stdio should not use the Authorization spec." `[CITED: modelcontextprotocol.io/docs/tutorials/security/authorization]`

### F.2 Hosted-mode question — should v0.2 ship HTTP toggle?

**Recommendation: DEFER hosted to v0.3.** Reasoning:

1. v0.1 + v0.2 audience is 1-2 named quants on their own machines. Zero validated demand for hosted yet.
2. Hosted HTTP server adds OAuth 2.1 implementation, session management, rate limiting, network security headers, deployment infrastructure, multi-tenant data isolation. None of those are testable without real users.
3. The "future-proofing now" cost is ~2 days; the rewrite cost in v0.3 IF demand emerges is ~5 days. Net optionality value is positive but not large.

### F.3 Minimum future-proofing in v0.2

To avoid a v0.3 rewrite when hosted ships:

1. **`CallerContext` abstraction** — Pydantic model with `identity: str`, `caller_kind: Literal["local", "oauth"]`, `granted_scopes: list[str]`. v0.2 stdio middleware always populates `CallerContext(identity="local", caller_kind="local", granted_scopes=["*"])`. Tool bodies receive `CallerContext` parameter via FastMCP context state.

2. **Audit log always includes `caller_identity`** even when it's the constant `"local"`. Schema doesn't change in v0.3 when real identities arrive.

3. **Server entry point is `mcp.run(transport=os.environ.get("TRADEWINDS_MCP_TRANSPORT", "stdio"))`** — one-line change to switch to HTTP later. (Don't ship the HTTP path code in v0.2; just leave the seam.)

4. **Tools never read os.environ directly.** All config flows through `CallerContext` or a `Settings` Pydantic model populated at server boot. This is the difference between a 1-hour v0.3 toggle and a week-long migration.

`[CITED: descope.com/blog/post/auth-remote-mcp + gelembjuk.com authentication-remote-mcp-server-python (2026)]`

## G. Pricing Model — Technical-Surface Implications (OQ-5)

**This is mostly a business question. Researcher only investigates: what technical seams MUST be in place at v0.2 to not block a v1.0 pricing decision?**

The relevant pricing models for a future hosted offering:

| Model | Tech surface required at v0.2 | Cost to add later |
|-------|------------------------------|-------------------|
| **Open-source forever, no hosted** | None | n/a |
| **License-key for commercial use (BSL-style)** | None — `LICENSE` text change only | Cheap; LICENSE swap |
| **Hosted SaaS — flat per-user subscription** | `CallerContext.identity` (done in §F.3); per-tenant catalog config | ~3 days to add per-tenant catalog dir |
| **Hosted SaaS — usage metering (per-MCP-call billing)** | `CallerContext.identity` + audit-log already counts row_count and per-call timing | None additional — audit log IS the meter |
| **Multi-tenant data isolation** | `CallerContext.identity` + cache path namespacing by tenant ID | Cheap if `caller_identity` is logged everywhere; expensive if added retrofitted |

**Recommendation: bake `caller_identity` into audit log + `CallerContext` into tool signatures in v0.2.** That single seam covers all four hosted-pricing options. Cost in v0.2: ~half a day of plumbing. Cost to retrofit in v0.5: ~3 days plus a forced audit-log format migration.

**Do NOT:**
- Add a license-key concept in v0.2. MIT license is locked in PROJECT.md; not negotiable for v0.1/v0.2.
- Add multi-tenant cache namespacing in v0.2 — the `audit.jsonl` is already per-instance per CONTEXT.md.
- Add billing-meter infrastructure. Audit log IS the meter when needed.

This is the absolute minimum. `[CITED: own analysis; no library prescribes this]`

## H. Plan-Shape Recommendation

### H.1 Confirming the CONTEXT.md hint

CONTEXT.md suggests 4 waves across 4-6 plans. **Research confirms this is right; no Phase split into 5a/5b/5c needed.**

Justification: The four waves CONTEXT.md proposes (server skeleton + temporal middleware / catalog format / agent-connector pipeline / second vertical) are tightly coupled by the temporal middleware — none of the waves makes sense without Wave 1 — but they're also clean to ship in sequence because each adds capability without rewriting prior waves. A Phase split would force `tradewinds-mcp==0.2.0` to ship across multiple PyPI releases, which is more user-pain than it saves on planning.

### H.2 Proposed plan shape — 4 waves, 5 plans

| Wave | Plan(s) | Requirements | LOCKED-decisions consumed | Estimated effort |
|------|---------|--------------|---------------------------|------------------|
| **Wave 1: Server skeleton + temporal middleware + audit log** | PLAN-01 (single plan, atomic) | MCP-01 (partial — server runs), MCP-04 (full), MCP-06 (full), MCP-07 (partial — uses Phase 2 schema validator), MCP-08 (full — Dataset.at_time/.between/.as_of) | mcp>=1.27 + FastMCP; toon at boundary; temporal-safety middleware; audit log JSONL; CallerContext seam | 3-4 days; single lane |
| **Wave 2: Catalog format + 5-layer schema + pre-indexed weather entries** | PLAN-02 (single plan) | MCP-02 (full), MCP-10 (weather portion — 7 of 10 entries) | YAML + JSON-Schema meta-schema; per-source files at `catalog/`; `_generated/` subdir; weather catalog from Phase 2 adapters | 2-3 days; single lane |
| **Wave 3: Agent-generated connector pipeline + quality-review gate** | PLAN-03 (single plan) | MCP-03 (full) | PR-based contribution model; `_generated/` → `catalog/` promotion; jsonschema validation gate | 2-3 days; single lane |
| **Wave 4: Second vertical (FRED+ALFRED) + Kalshi macro contract specs + JSON-RPC integration tests + deterministic-replay tests** | PLAN-04 (FRED+ALFRED adapter + catalog entries) <br/> PLAN-05 (JSON-RPC + deterministic replay tests + v0.2.0 release prep) | MCP-05 (full), MCP-09 (full), MCP-10 (macro portion — 3 of 10 entries), MCP-01 (full — all 5 tools end-to-end) | Second vertical = macro (override CONTEXT.md sports default per §E); deterministic-replay hash discipline; CI/CD trusted publishing inherited from Phase 4 | 4-5 days; two parallel lanes (V: adapter; F: tests + release) |

**Total:** 5 plans, 4 waves, ~12 working days at single-developer pace (consistent with v0.2 being a "later milestone" — not 14-day-sprint scoped).

### H.3 Cross-wave invariants the planner should enforce

- **Wave 1 ships the temporal middleware FIRST and atomically.** No later wave is allowed to register a tool that doesn't go through the middleware. CI gate (Wave 1 deliverable): a meta-test asserting `len([t for t in mcp._tools if "as_of" not in t.params]) == 0` for read tools.
- **TOON serializer roundtrip determinism MUST be tested in Wave 1**, not Wave 4. If TOON isn't deterministic, fix it in Wave 1 before downstream waves build on it.
- **`packages/mcp/` MUST NOT depend on `tradewinds.weather._fetchers` or `tradewinds.markets.kalshi` directly** — only through the catalog entries and the canonical schemas. This is the "core + wrappers" pattern (VISION.md #6).
- **Pre-Phase-5 ID-collision cleanup MUST be a `/gsd-quick` BEFORE Wave 1 starts** (per CONTEXT.md locked decision). Remove REQUIREMENTS.md lines 101-108 + line 236 + update mapping table.

## I. Pitfalls + Known Gotchas

### Pitfall I.1: FastMCP middleware vs decorator confusion
**What goes wrong:** Developer adds a tool with `@mcp.tool()` and forgets that middleware applies to it. They write their own `as_of` validation inside the tool, gets it wrong, and bypasses the structural enforcement.
**Why:** FastMCP makes per-tool decorators look like the obvious place to add validation.
**How to avoid:** Document in `packages/mcp/CONTRIBUTING.md`: "All temporal validation lives in `temporal_middleware.py`. Tools accept `as_of: datetime` typed but do not validate — middleware does. If you want to validate something else, it goes in middleware."
**Warning signs:** Code review sees `if as_of is None: raise` inside a tool body. Reject the PR; that logic belongs in middleware.

### Pitfall I.2: Pydantic BaseModel return + TOON string mixing
**What goes wrong:** Tool returns `{"format": "toon", "data": toon_str, "schema": schema_id}` as a `dict`. FastMCP auto-classifies it as structured-output and tries to validate against a generated JSON-Schema. The `data` field has no schema for the TOON content because TOON is just a string from FastMCP's POV. Confusion.
**Why:** Pydantic auto-schema-gen + string-encoded content are an awkward mix.
**How to avoid:** Return a Pydantic `QueryResponse` envelope with `data: str` (just a string, schema = `string` in the meta-schema). The TOON content's structured schema lives in the SEPARATE `get_schema(schema_id)` tool. Two-step: agent calls `query` → gets TOON string + schema_id → optionally calls `get_schema(schema_id)` to get the schema definition. This matches the Phase 2 SchemaRegistration pattern.
**Warning signs:** A tool returns nested dicts where TOON is nested as an object. Should be a flat envelope with `data: str`.

### Pitfall I.3: Deterministic replay broken by dict iteration order
**What goes wrong:** Tool returns `{filters: {"station": "KNYC", "year": 2024}}` in an audit-log entry. JSON serialization of dicts is INSERTION-ORDER-STABLE since Python 3.7 BUT not guaranteed by spec. A future Python version OR a Pydantic version could reorder keys, breaking hash determinism.
**Why:** Implicit order assumption.
**How to avoid:** In the audit-log writer, always `json.dumps(d, sort_keys=True)` for the audit line itself. The hash input (TOON content) is governed by Phase 2's TOON determinism tests.
**Warning signs:** A replay test passes locally and fails in CI on a different Python patch version.

### Pitfall I.4: Agent hallucinates a field that doesn't exist in the API
**What goes wrong:** Agent reads GHCNh docs, generates a catalog entry with `schema_semantics.fields.relative_humidity` — but the GHCNh API actually returns `RelativeHumidity`. The catalog promotes; first real query fails.
**Why:** 15% API hallucination rate on low-frequency APIs in 2026 SOTA LLMs (`[CITED: arxiv.org/html/2407.09726v1]`).
**How to avoid:** Wave 3 quality-review gate REQUIRES a `@pytest.mark.live` sample-data fetch that validates the generated catalog entry's `schema_semantics.fields` against actual fetched data. PR cannot merge without this passing.
**Warning signs:** A `_generated/` entry has no associated test fixture, or its test is `@pytest.mark.skip`.

### Pitfall I.5: TOON serializer not deterministic in Phase 2's lifted code
**What goes wrong:** TOON was lifted verbatim from `monorepo-v0.14.1`. Roundtrip tests prove `dtype preservation` but not `byte-identical re-serialization`. Phase 5 builds replay testing on top — and one day a categorical column's TOON output reorders categories.
**Why:** Phase 2 test bar doesn't include explicit determinism assertion.
**How to avoid:** Wave 1 Plan adds `test_toon_deterministic_serialization` BEFORE the deterministic-replay gates. If TOON is found nondeterministic, fix in the TOON serializer (categorical sorting, dict key sorting), not at the MCP layer.
**Warning signs:** Replay tests pass intermittently, especially with categorical or string columns.

### Pitfall I.6: stdio server logging to stdout breaks JSON-RPC framing
**What goes wrong:** Developer adds `print(...)` to a tool for debugging. stdio server writes JSON-RPC messages to stdout. The `print` corrupts the framing, client crashes with parse error.
**Why:** Easy mistake.
**How to avoid:** Add a `pytest --doctest-modules` check that asserts no `print(` statements in `packages/mcp/src/`. Configure Python logging in the server entry point to write to stderr ONLY: `logging.basicConfig(stream=sys.stderr, ...)`. Document in CONTRIBUTING.md.
**Warning signs:** Server works in pytest but fails in Claude Desktop. Check for stdout writes.
`[CITED: dev.to/jefe_cool MCP Transports stdio 2026]`

### Pitfall I.7: Inflated `ingest` row counts when source backfills
**What goes wrong:** ALFRED returns a CPI vintage with `realtime_start=2024-02-15` for the original release AND `realtime_start=2024-03-15` for the corrected release. The `ingest` tool sees both, doesn't dedupe, ships 2 rows when 1 was knowable on 2024-02-15.
**Why:** Vintage-aware data sources have a non-obvious ingestion semantic.
**How to avoid:** Catalog `temporal_rules.backfill_behavior` for FRED+ALFRED entries documents this explicitly. Adapter test fixtures include a vintage-correction case. The `KnowledgeView(as_of=<some_date>)` filter then naturally returns only the version knowable at `as_of` — provided the catalog entry's `knowledge_time` formula is correct (should be `realtime_start`, not `realtime_end`).
**Warning signs:** Same-date observations have multiple rows in query output without `realtime_start <= as_of` filter applied.

### Pitfall I.8: Cross-vertical join silently produces wrong rows
**What goes wrong:** Weather catalog entry has `joins_to: [{source: kalshi.weather, on: ["station_id", "date"]}]`. Macro catalog entry has `joins_to: [{source: kalshi.macro, on: ["release_date"]}]`. An agent decides to join weather with macro on `date` — wrong rows.
**Why:** Catalog `joins_to` is per-source-relationship; cross-vertical joins are not pre-declared.
**How to avoid:** Catalog's `joins_to` block is the ALLOW-LIST of declared joins. The MCP server should refuse cross-source joins that aren't in the allow-list, OR return them with a `cross_vertical_join: true` flag in the audit log. v0.2 can simply REJECT undeclared joins (`raise SchemaValidationError`); v0.3+ can soften to warnings if user demand emerges.
**Warning signs:** Audit log has many `joins_to=undeclared` entries — surface in tests.

## Runtime State Inventory

> Phase 5 is greenfield — no existing runtime state to migrate. Skipped.

**Nothing found in category:** None — Phase 5 is greenfield within an unshipped milestone. v0.1.0 has not yet shipped to PyPI; therefore no production caches, no installed packages on user machines, no live services with the brand string baked in. The only "state" Phase 5 inherits from Phases 1-4 is in-source-tree (`packages/core/src/tradewinds/core/`, `packages/weather/src/tradewinds/weather/catalog/`, etc.), and those are imported via the canonical Python module path — no rename or string-replace concern.

## Environment Availability

> Phase 5 is a code/library addition with one new external HTTP dependency (FRED+ALFRED). Environment audit:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All | (deferred — local install check happens at v0.2 build time) | — | n/a — already locked |
| `mcp` | `tradewinds-mcp` | Will install via pip at v0.2 build | 1.27.1 (May 8, 2026) | None — phase blocker if PyPI down |
| `fredapi` (optional Python wrapper for FRED) | macro adapter | Will install via pip | `>=0.5.0` (current) | Direct `httpx` calls; ~50 LOC adapter without the wrapper |
| FRED API + ALFRED API endpoint | macro adapter @ runtime | Public, no auth, free | n/a (live service) | None — degrade to weather-only ship if FRED is unreachable in CI |
| `pyyaml` (catalog loader) | catalog | Pin `pyyaml>=6.0,<7.0` (current 6.x line is stable since 2022) | — | None |
| `jsonschema` | catalog promotion gate | Already in v0.1 deps | `>=4.25,<5` per CLAUDE.md | None |

**Missing dependencies with no fallback:** None at planning time. The new pip deps land at v0.2 build.

**Missing dependencies with fallback:** None.

**Note for planner:** FRED requires a free API key (32-char string, registers via fredstlouisfed.org). The catalog entry's `operational_context.auth` should document the env var (`FRED_API_KEY`), and the adapter should fail with a `SourceUnavailableError` carrying the registration URL when the key is unset — same error-message-with-install-hint pattern as Phase 3's `pip install tradewinds-weather`. `[CITED: fred.stlouisfed.org/docs/api/api_key.html]`

## Resolved Open Questions

Researcher recommends defaults; user owns the final call. Mark each as **needs user confirmation** in `/gsd-discuss-phase` before plan freeze.

### OQ-1: MCP SDK version + API surface
- **Recommended default:** `mcp>=1.27,<2.0`. FastMCP pattern (`from mcp.server.fastmcp import FastMCP`). Tool response = Pydantic `BaseModel` envelope `{format: str, data: str, schema_id: str, audit_id: str}` where `data` is a TOON-encoded string. `get_schema(schema_id)` is a separate tool that returns the actual schema JSON.
- **Alternative:** TypedDict envelope (loses auto-validation but simpler). Skip — Pydantic is already in MCP SDK dep tree.
- **User-owned decision:** confirm Pydantic envelope vs TypedDict; confirm 1.27 floor.
- Confidence: **HIGH** — backed by direct PyPI verification + FastMCP docs.

### OQ-2: Auth model — local-first vs hosted
- **Recommended default:** v0.2 ships local-first stdio only. NO hosted-mode toggle in v0.2. Future-proofing: ship `CallerContext` abstraction (Pydantic model with `identity`/`caller_kind`/`granted_scopes`) populated by middleware in v0.2 with constant `"local"`; tools accept `CallerContext` parameter. Audit-log always includes `caller_identity`. Server entry point reads transport from `TRADEWINDS_MCP_TRANSPORT` env var (defaults to stdio).
- **Alternative:** Ship HTTP toggle in v0.2 (rejected — no validated demand, adds 5 days work).
- **User-owned decision:** confirm hosted-mode deferred to v0.3; confirm seam shape.
- Confidence: **HIGH** — backed by MCP spec + multiple 2026 auth-pattern blog posts.

### OQ-3: Catalog file format — YAML vs JSON Schema vs custom DSL
- **Recommended default:** **YAML files** at `packages/mcp/catalog/<source_id>.yaml`. Single meta-schema at `packages/mcp/catalog/_schema/catalog_entry.schema.json` validates them via jsonschema. `yaml.safe_load` only.
- **Alternative 1:** TOML (rejected — worse nesting ergonomics for 5-layer context).
- **Alternative 2:** JSON Schema only (rejected — no comments; `quality_notes` is half the value of the catalog).
- **Alternative 3:** Custom DSL (FORBID — LLM hallucination risk + no tooling).
- **User-owned decision:** confirm YAML + JSON-Schema-meta-schema pattern.
- Confidence: **HIGH** — backed by 2026 config-format comparisons + Singer/Meltano prior art.

### OQ-4: Community contribution model for agent-generated connectors
- **Recommended default:** PR-based against `packages/mcp/catalog/_generated/`. Same 2-reviewer loop (codex `high` + python-architect) per REVIEW-DISCIPLINE.md. CI gates: jsonschema validation, sample-data round-trip (`@pytest.mark.live`), schema-cross-check against `tradewinds.core.schemas` registry. When all green AND humans approve, maintainer moves the file from `_generated/` to `catalog/` root (the "promotion") in a follow-up commit. Document in `CONTRIBUTING.md`.
- **Alternative 1:** GitHub Issues with attached YAML (worse — adds a triage step).
- **Alternative 2:** Separate `tradewinds-catalog` repo (defer to v0.3+ if catalog grows to O(100s)).
- **User-owned decision:** confirm PR-based + `_generated/` directory + 2-step promotion.
- Confidence: **HIGH** — lowest-friction option; matches existing REVIEW-DISCIPLINE.

### OQ-5: Pricing model for hosted version (if any)
- **Recommended default:** **No pricing model decision made in v0.2.** Technical seam to keep pricing options open: bake `caller_identity` into audit log + `CallerContext` into tool signatures (see §G). That single seam covers license-key, flat-subscription, usage-metering, and multi-tenant-isolation hosted models — all addable in v0.3+ without v0.2 rework. **Do NOT** add license-key concept, billing meter, or multi-tenant cache namespacing in v0.2 — none of these have validated demand and MIT license is locked.
- **Alternatives:** any of the four hosted-pricing models in §G (defer all four).
- **User-owned decision:** confirm "no pricing decision in v0.2"; confirm the minimum seam (caller_identity in audit log) is acceptable.
- Confidence: **MEDIUM** — business question not technical; researcher only sized the technical implications.

## Validation Architecture

> `workflow.nyquist_validation = false` per `.planning/config.json`. Section skipped per instructions.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | TOON serializer (Phase 2) is byte-deterministic OR can be made so with minor fixes | §D.3, §I.5 | If TOON has fundamental nondeterminism (e.g., dict iteration not sorted), Wave 1 spends 1-2 extra days fixing TOON before building replay tests on top. Mitigation: Wave 1 includes `test_toon_deterministic` AS A FIRST DELIVERABLE. |
| A2 | FastMCP 3.0 (Jan 2026) `add_middleware` API is stable through `mcp>=1.27,<2.0` | §D.1 | If middleware API changes within the 1.x line (unlikely — FastMCP is mature), some refactoring needed. Mitigation: pin `mcp` floor tight in v0.2 release. |
| A3 | Kalshi macro markets remain CFTC-blessed and operational through v0.2 ship | §E.2 | If political regulation changes, the second vertical loses settlement source. Probability: very low (macro markets pre-date sports controversy). Mitigation: catalog entry documents the CFTC certification status in `operational_context`. |
| A4 | FRED/ALFRED APIs remain free + public + no auth-other-than-key through v0.2 | §E.2 | If St. Louis Fed monetizes, fallback to other macro sources (BLS direct, BEA API). Probability: near zero (FRED is a public service since 1991). |
| A5 | `pandas>=2.2,<3.0` pin holds through v0.2 ship | §D.3 | If pandas 3.0 migration completes during v0.2, deterministic-replay hashes change. Mitigation: pandas 3.0 is its own deferred work item (PANDAS3-01/02 in REQUIREMENTS.md v2). |
| A6 | Phase 2 `KnowledgeView` is wrappable in a `Dataset` class without forcing changes to Phase 2 surface | §D.2 | If Phase 2's KnowledgeView mutates DataFrame state in a way Dataset can't compose, ~1 day of refactor in Phase 5 Wave 1. Phase 2 PLAN says KnowledgeView is a plain class with `__slots__` wrapping a DataFrame — should be straightforward. |
| A7 | The user accepts macro (FRED+ALFRED+Kalshi macro contracts) as the v0.2 second vertical OVERRIDING the CONTEXT.md "sports recommended" hint | §E | If user insists on sports, Phase 5 ships ~2-3 days slower (legal/data-rights research needed) and risks settlement-source mid-litigation. Mitigation: flag clearly in `/gsd-discuss-phase`. |
| A8 | Pre-Phase-5 ID-collision cleanup can be done as a `/gsd-quick` (it's a docs-only edit to REQUIREMENTS.md) | §H.3, CONTEXT.md locked decision | If REQUIREMENTS.md cleanup uncovers unexpected dependencies (e.g., some test file references `MCP-04 (validate_dataframe)`), small extra fix-up needed. |

**User confirmation needed before plan freeze on:** A7 (second-vertical choice) and all five OQ resolutions.

## Open Questions

These are gaps researcher could not fully resolve — flag for planner or `/gsd-discuss-phase`:

1. **Exact module layout `packages/mcp/src/tradewinds_mcp/` vs `packages/mcp/src/tradewinds/mcp/`** — depends on namespace decision finalized in Phase 2. Recommendation: ask the Phase 2 planner; default to `packages/mcp/src/tradewinds_mcp/` (sibling-package pattern, lowest risk of PEP 420 namespace collisions). CONTEXT.md flagged this as "Claude's discretion."

2. **Does `tradewinds-mcp-server --replay <audit-line>` CLI ship in v0.2 or v0.3?** Useful for deterministic-replay debugging but adds CLI surface to a project that explicitly defers CLI. Recommendation: ship in v0.2 as a single `python -m tradewinds_mcp.replay <audit-line>` module (not a console_script) — zero CLI infra, full debug value.

3. **Is per-instance audit.jsonl OR per-user shared?** CONTEXT.md flagged "Claude's discretion." Recommendation: per-instance — easier to test, less concurrent-write contention, no `filelock` needed for audit log if each MCP server process owns its own file (use timestamp + PID in filename: `audit-<startup-iso>-<pid>.jsonl`). User can `cat` together for cross-instance analysis.

4. **How does the catalog handle "this Kalshi market is closed / delisted"?** Out of scope per "no orderbook/fills" decision, but the catalog should at least carry a `status: live | retired` field so users querying retired-market specs get a clear error. Adds 1-2 lines to meta-schema; planner should include.

5. **FRED API rate limits in practice** — documented (120 req/60sec per API key) but not verified empirically. Recommendation: Wave 4 adapter includes a one-off live smoke test (`@pytest.mark.live`) that does a 1-year vintage fetch on CPI series and verifies wall-time < 60s. If FRED is slower than docs claim, adjust adapter chunking.

## Code Examples

Verified patterns from authoritative sources. All marked with citations.

### Example 1: FastMCP server with middleware (full skeleton)

```python
# packages/mcp/src/tradewinds_mcp/server.py
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from .temporal_middleware import TemporalSafetyMiddleware
from .audit import AuditLogger
from .catalog import CatalogLoader
from .caller_context import CallerContext

mcp = FastMCP("tradewinds")
mcp.add_middleware(TemporalSafetyMiddleware())
audit = AuditLogger()
catalog = CatalogLoader.from_dir("packages/mcp/catalog/")

class QueryResponse(BaseModel):
    format: str
    data: str         # TOON-encoded string
    schema_id: str    # reference to schema (resolvable via get_schema)
    audit_id: str     # cross-ref to audit.jsonl entry

@mcp.tool()
async def query(
    source_id: str,
    as_of: datetime,  # validated by middleware
    filters: dict | None = None,
    format: str = "toon",
) -> QueryResponse:
    """Return rows from source_id that were knowable at `as_of`."""
    entry = catalog.lookup(source_id)
    df = entry.fetch(filters=filters)
    dataset = Dataset(df, schema_id=entry.schema_id)
    filtered = dataset.at_time(as_of)  # KnowledgeView filter
    toon_str = toon_fmt.serialize(filtered)
    audit_id = audit.log(tool="query", source=source_id, as_of=as_of,
                          rows=len(filtered), hash=sha256(toon_str.encode()).hexdigest())
    return QueryResponse(format="toon", data=toon_str,
                          schema_id=entry.schema_id, audit_id=audit_id)

if __name__ == "__main__":
    import os
    mcp.run(transport=os.environ.get("TRADEWINDS_MCP_TRANSPORT", "stdio"))
```
`[CITED pattern: gofastmcp.com/servers/middleware + datacamp.com tutorial — adapted to tradewinds]`

### Example 2: 5-layer YAML catalog entry

```yaml
# packages/mcp/catalog/iem.archive.yaml
$schema: ../_schema/catalog_entry.schema.json
source_id: iem.archive
display_name: "Iowa Environmental Mesonet — ASOS observations (archive)"
status: live

schema_semantics:
  schema_id: "schema.observation.v1"
  fields:
    tmpf:
      type: float
      units: "°F"
      description: "Air temperature, instantaneous reading at observation_time. NOT a daily high/low."
    relh:
      type: float
      units: "percent (0-100)"
      description: "Relative humidity. NULL during station outages — do NOT impute from neighbors."

temporal_rules:
  event_time_field: observed_at
  knowledge_time_field: knowledge_time
  knowledge_time_formula: "observed_at + report_delay (typically 5-15 min for ASOS METAR)"
  backfill_behavior: "Past records DO NOT change after first publish. ASOS is a one-shot publish."
  vintage_aware: false

quality_notes:
  - "Pre-2007 records have inconsistent units across stations — handled in _vendor parser."
  - "ASOS sensor changes documented in NOAA station history files; not exposed here."

relationship_mappings:
  joins_to:
    - source: ghcnh.archive
      on: ["station_id", "observed_at"]
      note: "ASOS uses ICAO codes (KNYC); GHCNh uses WBAN (725030). station_id_map.csv resolves."
    - source: kalshi.weather
      on: ["station_id", "date"]
      note: "Kalshi NHIGH/NLOW settlement station whitelist hard-coded in tradewinds.markets.catalog."

operational_context:
  endpoint: "https://mesonet.agron.iastate.edu/..."
  rate_limit: "1 req/sec/IP (empirical; not documented)"
  auth: none
  pagination: "365-day chunks via _iem_chunks helper (Phase 1.5)"
  http_timeout_seconds: 60
```
`[CITED structure: CONTEXT.md specifics skeleton + Singer catalog conventions + own analysis]`

### Example 3: Deterministic replay test (idiom for Wave 4)

```python
# packages/mcp/tests/test_deterministic_replay.py
import hashlib
import pytest
from mcp.client.session import ClientSession
from fastmcp.utilities.tests import run_server_async

@pytest.mark.asyncio
async def test_query_same_args_byte_identical_two_runs(server_fixture):
    async with run_server_async(mcp) as session:
        args = {"source_id": "iem.archive",
                "as_of": "2024-01-15T00:00:00Z",
                "filters": {"station": "KNYC"}}
        result_a = await session.call_tool("query", args)
        result_b = await session.call_tool("query", args)
        hash_a = hashlib.sha256(result_a.content.data.encode("utf-8")).hexdigest()
        hash_b = hashlib.sha256(result_b.content.data.encode("utf-8")).hexdigest()
        assert hash_a == hash_b, "Deterministic replay broken"
```
`[CITED: FastMCP test utilities + CONTEXT.md specifics idiom — adapted]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom JSON-RPC server | FastMCP decorator-based registration | MCP SDK 1.0 (Nov 2024) onward; FastMCP de facto default by mid-2025 | tradewinds adopts FastMCP — locked |
| MCP SSE transport | MCP Streamable HTTP transport | SSE deprecated in MCP spec, March 2025+ | Even if v0.3 adds hosted mode, build on Streamable HTTP, not SSE |
| Tool-body validation of every kwarg | FastMCP middleware (`on_call_tool`) | FastMCP 2.9 (June 2025); production-mature by 2026 | Phase 5 Wave 1 uses middleware for temporal safety — structural enforcement |
| Pydantic v1 for MCP tool I/O | Pydantic v2 (auto JSON-Schema generation from BaseModel) | MCP SDK 1.x line is Pydantic v2 throughout | tradewinds inherits v2; consistent with CLAUDE.md's "reconsider Pydantic for v0.2 MCP work" |
| LLM-generated config trusted | LLM-generated config → CI validation → human review → promotion | Documented as best practice 2026 (15% hallucination rate on low-frequency APIs) | Phase 5 Wave 3 design — `_generated/` → `catalog/` promotion gate |
| Per-source DSL or custom catalog format | YAML files validated by JSON Schema meta-schema | Singer/Meltano established this in 2017-2019; mainstream by 2024+ | tradewinds catalog format — YAML with JSON-Schema meta |

**Deprecated/outdated:**
- SSE-based MCP transport (use Streamable HTTP if not stdio).
- Low-level `Server` class for new MCP servers (use FastMCP — covers ~80% of use cases).
- Returning raw `pd.DataFrame` from MCP tools (FastMCP wraps Pydantic/TypedDict; pandas isn't first-class).

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| MCP SDK pin + FastMCP pattern + transport (§A) | **HIGH** | PyPI version verified; FastMCP middleware docs + 5 independent 2026 sources confirm pattern |
| Catalog format choice (§B) | **HIGH** | 2026 format comparisons consistent (YAML for nested human-reviewable + JSON-Schema for validation); Singer/Meltano prior art mature |
| Agent-connector pipeline (§C) | **MEDIUM** | dlt/Singer/OpenAI patterns clear in shape; specific quality-gate automation details have less prior art at the per-tool-call level. 15% hallucination rate confirms human-review-required |
| Server-enforced temporal safety + replay (§D) | **HIGH** | FastMCP `on_call_tool` middleware verified; replay-determinism best practices documented; one Phase 2 dependency (TOON determinism) noted in Assumptions Log |
| Second vertical recommendation (§E) | **MEDIUM-HIGH** | Sports legal situation verified across 4 independent 2026 sources (Bloomberg, Marketplace, CFTC filings); FRED/ALFRED suitability verified; user override of CONTEXT.md hint is researcher's call and flagged for confirmation |
| Auth model (§F) | **HIGH** | MCP spec authoritative; stdio-vs-HTTP transition path documented |
| Pricing surface (§G) | **LOW-MEDIUM** | Business question; researcher only investigated technical implications. Confidence is high on "caller_identity seam covers all four hosted models"; low on "what model will user pick" — which is not a research question |
| Plan-shape (§H) | **HIGH** | Direct extension of CONTEXT.md hint; wave dependencies clear; no split needed |
| Pitfalls (§I) | **HIGH** | Each pitfall has citation + cure + warning sign |

**Confidence breakdown:**
- Standard stack: HIGH — every library version + pin verified against PyPI/docs
- Architecture: HIGH — FastMCP middleware is the structurally correct pattern, verified
- Pitfalls: HIGH — 8 pitfalls with citations, cures, and warning signs

**Research date:** 2026-05-22
**Valid until:** 2026-08-22 (3 months — FastMCP API stable; pandas 3.0 migration could shift dtype-determinism story; sports legal landscape could shift; flag for re-validation before Phase 5 PLAN.md freeze)

## Sources

### Primary (HIGH confidence)
- [pypi.org/project/mcp/](https://pypi.org/project/mcp/) — mcp Python SDK 1.27.1, May 8 2026, Python >=3.10 (verified via WebFetch)
- [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) — official SDK README + FastMCP pattern
- [gofastmcp.com/servers/middleware](https://gofastmcp.com/servers/middleware) — FastMCP middleware system, hooks, state propagation (verified via WebFetch)
- [gofastmcp.com/development/tests](https://gofastmcp.com/development/tests) — official FastMCP testing utilities
- [gofastmcp.com/deployment/running-server](https://gofastmcp.com/deployment/running-server) — transport configuration (stdio/HTTP)
- [modelcontextprotocol.io/docs/tutorials/security/authorization](https://modelcontextprotocol.io/docs/tutorials/security/authorization) — MCP authorization spec (stdio vs HTTP)
- [fred.stlouisfed.org/docs/api/fred/](https://fred.stlouisfed.org/docs/api/fred/) — FRED API official docs
- [alfred.stlouisfed.org/](https://alfred.stlouisfed.org/) — ALFRED archival/vintage data
- [federalreserve.gov/econres/feds/files/2026010pap.pdf](https://www.federalreserve.gov/econres/feds/files/2026010pap.pdf) — "Kalshi and the Rise of Macro Markets" Fed working paper (2026)
- [docs.kalshi.com/welcome](https://docs.kalshi.com/welcome) — Kalshi Exchange API documentation
- CLAUDE.md (this repo) — Recommended Stack table, "Deferred to v0.2 — Reserve the Seam", Project Constraints
- `.planning/phases/02-core-primitives-catalog-adapters/PLAN.md` (this repo) — Phase 2 KnowledgeView/Schema/TOON foundations
- `.planning/phases/05-mcp-data-platform/VISION.md` + `CONTEXT.md` (this repo) — locked decisions and open questions

### Secondary (MEDIUM confidence — multiple sources cross-verified)
- [jlowin.dev/blog/fastmcp-3-whats-new](https://jlowin.dev/blog/fastmcp-3-whats-new) — FastMCP 3.0 changes Jan 2026
- [jlowin.dev/blog/fastmcp-2-9-middleware](https://jlowin.dev/blog/fastmcp-2-9-middleware) — middleware system introduction (June 2025)
- [jlowin.dev/blog/stop-vibe-testing-mcp-servers](https://jlowin.dev/blog/stop-vibe-testing-mcp-servers) — testing discipline rationale
- [medium.com/@anil.goyal0057 Three-Layer Test Pyramid 2026](https://medium.com/@anil.goyal0057/the-complete-guide-to-testing-mcp-server-applications-a-three-layer-test-pyramid-for-ai-powered-027e941be6d4) — testing patterns
- [kirkryan.co.uk/stdio-vs-streamable-http](https://kirkryan.co.uk/stdio-vs-streamable-http-choosing-the-right-mcp-transport/) — transport selection 2026
- [apigene.ai/blog/mcp-sse-vs-stdio](https://apigene.ai/blog/mcp-sse-vs-stdio) — MCP transport guidance 2026
- [hub.meltano.com/singer/spec](https://hub.meltano.com/singer/spec) — Singer catalog format specification
- [deepwiki.com/meltano/meltano/7.4](https://deepwiki.com/meltano/meltano/7.4-singer-protocol-integration) — Singer protocol implementation walkthrough
- [marketplace.org/story/2026/05/14/prediction-markets-horse-racing-kalshi-polymarket](https://www.marketplace.org/story/2026/05/14/prediction-markets-horse-racing-kalshi-polymarket) — Kalshi horse racing legal status
- [bloomberg.com/news/articles/2026-05-12](https://www.bloomberg.com/news/articles/2026-05-12/kalshi-judge-predicts-tribe-will-win-block-on-sports-contracts) — Kalshi NJ injunction
- [covers.com/industry/polymarket-files-parlay-style-sports-contracts-with-cftc-may-21-2026](https://www.covers.com/industry/polymarket-files-parlay-style-sports-contracts-with-cftc-may-21-2026) — Polymarket CFTC filing
- [readwrite.com/new-mexico-tribes-kalshi-lawsuit](https://readwrite.com/new-mexico-tribes-kalshi-lawsuit/) — NM tribal lawsuit
- [devtoolbox.dedyn.io/blog/json-vs-yaml-vs-toml](https://devtoolbox.dedyn.io/blog/json-vs-yaml-vs-toml) — config format comparison 2026
- [knightli.com common config formats 2026](https://www.knightli.com/en/2026/04/22/common-config-file-formats-ini-xml-json-yaml-toml-markdown/) — config format comparison 2026
- [tianpan.co/blog/2026-04-12-deterministic-replay-debugging-non-deterministic-ai-agents](https://tianpan.co/blog/2026-04-12-deterministic-replay-debugging-non-deterministic-ai-agents) — deterministic replay design 2026
- [keywordsai.co/blog/llm_consistency_2025](https://www.keywordsai.co/blog/llm_consistency_2025) — LLM determinism patterns
- [arxiv.org/html/2407.09726v1](https://arxiv.org/html/2407.09726v1) — API hallucination rates in code LLMs (Amazon Science)
- [cerbos.dev/blog/how-to-secure-your-fast-mcp-server-with-permission-management](https://www.cerbos.dev/blog/how-to-secure-your-fast-mcp-server-with-permission-management) — middleware permission patterns
- [gelembjuk.com authentication-remote-mcp-server-python](https://gelembjuk.com/blog/post/authentication-remote-mcp-server-python/) — remote MCP auth 2026
- [descope.com/blog/post/auth-remote-mcp](https://www.descope.com/blog/post/auth-remote-mcp) — adding auth to local MCP server

### Tertiary (LOW confidence — single-source / general background)
- [pydantic.dev/docs/ai/mcp/server/](https://pydantic.dev/docs/ai/mcp/server/) — Pydantic AI MCP integration
- [dev.to/composiodev/building-streamable-http-mcp-servers-from-scratch-using-fastmcp-in-2026-5fh9](https://dev.to/composiodev/building-streamable-http-mcp-servers-from-scratch-using-fastmcp-in-2026-5fh9) — implementation walkthrough
- [dev.to/jefe_cool/mcp-transports-explained-stdio-vs-streamable-http](https://dev.to/jefe_cool/mcp-transports-explained-stdio-vs-streamable-http-and-when-to-use-each-3lco) — transport tradeoffs
- [chainstack.com/polymarket-api-for-developers/](https://chainstack.com/polymarket-api-for-developers/) — Polymarket API architecture
- [oddspapi.io/blog/polymarket-api-kalshi-api-vs-sportsbooks-the-developers-guide/](https://oddspapi.io/blog/polymarket-api-kalshi-api-vs-sportsbooks-the-developers-guide/) — Kalshi/Polymarket Python guide

## Metadata

**Confidence breakdown:**
- Standard stack (MCP SDK, FastMCP, transport): HIGH — verified directly from PyPI + official docs
- Architecture (middleware pattern, catalog format, audit log): HIGH — multiple 2026 sources cross-confirm
- Pitfalls: HIGH — 8 documented with citations
- Second-vertical recommendation: MEDIUM-HIGH — based on 2026 legal landscape verified across 4+ sources; user-owned override of CONTEXT.md tentative hint
- Auth (§F): HIGH — MCP spec is authoritative
- Pricing (§G): LOW-MEDIUM — business question; researcher only sized technical implications

**Research date:** 2026-05-22
**Valid until:** 2026-08-22 (3 months — FastMCP API stable; pandas 3.0 migration could shift deterministic-replay story; Kalshi/Polymarket legal landscape could shift; flag for re-validation if Phase 5 doesn't start within this window)
