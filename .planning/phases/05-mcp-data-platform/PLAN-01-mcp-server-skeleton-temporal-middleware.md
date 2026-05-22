---
phase: 05-mcp-data-platform
plan: 01
type: execute
wave: 1
duration: 3-4 days Claude execution; single lane
waves: 1
depends_on: [phase-05-mcp-data-platform/PLAN-00-requirements-id-cleanup, phase-02-core-primitives-catalog-adapters, phase-04-coverage-docs-cicd-release]
branch_strategy: per-wave; one sub-branch off `main` (`phase-5/wave-1/mcp-server-skeleton`); 2-reviewer loop (codex `high` + python-architect) per REVIEW-DISCIPLINE.md; never-skip applies (touches `tradewinds.core.*` Dataset API + new `packages/mcp/` distribution); merges to `main` ONLY after temporal-middleware bypass meta-test + TOON determinism test + in-process FastMCP integration test are all green
requirements:
  - MCP-01    # partial — server runs, 5 tools defined as stubs; end-to-end JSON-RPC validation is PLAN-05
  - MCP-04    # full — server-enforced temporal safety via TemporalSafetyMiddleware (structural, no agent bypass)
  - MCP-06    # full — auditable provenance via AuditLogger (append-only JSONL at $HOME/.tradewinds/mcp-server/audit-<startup-iso>-<pid>.jsonl)
  - MCP-07    # full — schema contract validation on ingest+query reuses Phase 2's validate_dataframe + TradewindsError.to_dict() JSON-RPC payloads
  - MCP-08    # full — Dataset.at_time(date) / .between(start,end) / .as_of(timestamp) point-in-time API on top of Phase 2 KnowledgeView
autonomous: false   # Pre-merge requires manual run of the in-process FastMCP integration test (Task 1.4) + visual confirmation of the audit.jsonl format on a real query; if TOON nondeterminism is discovered, post-discovery decision between (a) fix TOON in tradewinds.core.formats vs (b) defer determinism work into PLAN-05 is post-spike per CONTEXT.md
files_modified:
  # NEW Python distribution at packages/mcp/ (parallel to packages/core, packages/weather, packages/markets)
  - packages/mcp/pyproject.toml                                                       # NEW — tradewinds-mcp distribution; depends on tradewinds>=0.2.0,<0.3 + mcp>=1.27,<2.0 + pydantic>=2.7,<3.0
  - packages/mcp/README.md                                                            # NEW — local-first stdio MCP server quickstart (Claude Desktop config + uv run example)
  - packages/mcp/src/tradewinds_mcp/__init__.py                                       # NEW — top-level package marker + version
  - packages/mcp/src/tradewinds_mcp/server.py                                         # NEW — FastMCP instance + 5 tool stubs + main entry point reading TRADEWINDS_MCP_TRANSPORT
  - packages/mcp/src/tradewinds_mcp/temporal_middleware.py                            # NEW — TemporalSafetyMiddleware (on_call_tool hook); READ_TOOLS = {"query","ingest"}
  - packages/mcp/src/tradewinds_mcp/audit.py                                          # NEW — AuditLogger writing JSONL to $HOME/.tradewinds/mcp-server/audit-<startup-iso>-<pid>.jsonl
  - packages/mcp/src/tradewinds_mcp/caller_context.py                                 # NEW — CallerContext Pydantic model (identity / caller_kind / granted_scopes) — v0.3 auth seam
  - packages/mcp/src/tradewinds_mcp/envelopes.py                                      # NEW — QueryResponse / IngestResponse / SchemaResponse / ListSourcesResponse / DescribeSourceResponse Pydantic envelopes (data: str = TOON-encoded)
  - packages/mcp/src/tradewinds_mcp/tools/__init__.py                                 # NEW — package marker; re-exports the 5 tool registration functions
  - packages/mcp/src/tradewinds_mcp/tools/query.py                                    # NEW — query(source_id, as_of, filters, format) stub returning QueryResponse with PLACEHOLDER catalog (real catalog in Wave 2)
  - packages/mcp/src/tradewinds_mcp/tools/ingest.py                                   # NEW — ingest(source_id, as_of, ...) stub
  - packages/mcp/src/tradewinds_mcp/tools/list_sources.py                             # NEW — list_sources() stub returning placeholder source list (real catalog in Wave 2)
  - packages/mcp/src/tradewinds_mcp/tools/describe_source.py                          # NEW — describe_source(source_id) stub returning placeholder description
  - packages/mcp/src/tradewinds_mcp/tools/get_schema.py                               # NEW — get_schema(schema_id) returns the canonical schema JSON from Phase 2 tradewinds.core.schemas registry
  # Tests
  - packages/mcp/tests/__init__.py                                                    # NEW
  - packages/mcp/tests/test_server_smoke.py                                           # NEW — FastMCP instance constructs, all 5 tools registered, transport defaults to stdio
  - packages/mcp/tests/test_temporal_middleware.py                                    # NEW — middleware rejects missing as_of, accepts present as_of, can't be bypassed by new tool registration
  - packages/mcp/tests/test_audit.py                                                  # NEW — AuditLogger appends sort_keys-stable JSON, hash deterministic over same input
  - packages/mcp/tests/test_caller_context.py                                         # NEW — CallerContext defaults to identity="local", schema serializable
  - packages/mcp/tests/test_envelopes.py                                              # NEW — QueryResponse/IngestResponse roundtrip via Pydantic; data: str not pd.DataFrame
  - packages/mcp/tests/test_meta_temporal_bypass_guard.py                             # NEW (CRITICAL META-TEST) — assert every tool registered with @mcp.tool() that returns rows declares as_of param; this is the structural guard against future drift
  - packages/mcp/tests/test_toon_deterministic.py                                     # NEW — test_toon_serializer_byte_deterministic_100_runs (RESEARCH.md §I.5 pitfall guard)
  - packages/mcp/tests/test_in_process_query.py                                       # NEW — run_server_async + ClientSession; call query/list_sources/get_schema in-process; assert envelope shape
  # Phase 2 surface extension (small, additive; no rename)
  - packages/core/src/tradewinds/core/temporal/dataset.py                             # NEW — Dataset class with .at_time(date) / .between(start, end) / .as_of(timestamp); wraps Phase 2 KnowledgeView
  - packages/core/tests/core/temporal/test_dataset.py                                 # NEW — at_time/between/as_of return KnowledgeView-filtered rows
  - packages/core/src/tradewinds/core/temporal/__init__.py                            # MODIFY — re-export Dataset alongside TimePoint, KnowledgeView, LeakageDetector
must_haves:
  truths:
    - "`from tradewinds_mcp.server import mcp` returns a `FastMCP` instance named 'tradewinds' (per `mcp.name == 'tradewinds'`)."
    - "`mcp.run(transport=os.environ.get('TRADEWINDS_MCP_TRANSPORT', 'stdio'))` is the literal entry-point line in `server.py` `__main__` block — one-line transport swap for v0.3 hosted mode (per RESEARCH.md §A.3 + §F.3 seam)."
    - "All 5 tools (`query`, `ingest`, `list_sources`, `describe_source`, `get_schema`) are registered via `@mcp.tool()` decorators on import of `server.py` — verified by `len([t for t in mcp._tool_manager._tools]) == 5`."
    - "`TemporalSafetyMiddleware.READ_TOOLS == {'query', 'ingest'}` — exactly these two tools require `as_of`. `list_sources`/`describe_source`/`get_schema` do NOT (they don't return rows)."
    - "`TemporalSafetyMiddleware.on_call_tool(context, call_next)` raises `ToolError` (FastMCP exception) when `params.get('as_of') is None or 'as_of' not in params` for any tool name in `READ_TOOLS`. Tested by `test_temporal_middleware_rejects_missing_as_of`."
    - "`mcp.add_middleware(TemporalSafetyMiddleware())` is called at module-level in `server.py` BEFORE any tool decorator runs — verified by `test_middleware_attached_before_tools` reading `mcp._middleware`."
    - "META-TEST `test_no_read_tool_lacks_as_of`: iterating `mcp._tool_manager._tools.values()`, every tool whose name is in `TemporalSafetyMiddleware.READ_TOOLS` has a parameter named `as_of` with type `datetime` and no default value. This is the structural anti-bypass guard (Pitfall I.1 + RESEARCH.md §H.3 invariant)."
    - "`QueryResponse(format: str, data: str, schema_id: str, audit_id: str)` is a Pydantic BaseModel — `data` field has annotation `str` (NOT `pd.DataFrame`, NOT `dict`); the TOON-encoded payload lives inside `data` as a string (RESEARCH.md §A.2 envelope + §I.2 pitfall guard)."
    - "`AuditLogger.log(tool, source, as_of, rows, hash, ...)` appends ONE JSON object per call, terminated by `\\n`, to `$HOME/.tradewinds/mcp-server/audit-<startup-iso>-<pid>.jsonl`. JSON keys are alphabetized (`json.dumps(d, sort_keys=True)`) — guard against Pitfall I.3 (dict iteration order)."
    - "Every audit-log entry contains `caller_identity` field — v0.2 always populates with `'local'` (RESEARCH.md §F.3 hosted-mode seam). Tested by `test_audit_includes_caller_identity_local`."
    - "Audit entry hash format is `sha256(toon_string.encode('utf-8')).hexdigest()` — encoding pinned to UTF-8 explicitly to avoid locale drift (RESEARCH.md §D.3 point 4)."
    - "`CallerContext` Pydantic model has fields `identity: str`, `caller_kind: Literal['local', 'oauth']`, `granted_scopes: list[str]`; v0.2 default factory returns `CallerContext(identity='local', caller_kind='local', granted_scopes=['*'])`."
    - "`Dataset.at_time(date)`, `.between(start, end)`, `.as_of(timestamp)` all delegate to `KnowledgeView(self._df, as_of=...).rows()` and return `pd.DataFrame` — verified by 3 unit tests."
    - "`Dataset.as_of(t) == Dataset.at_time(t)` for every t (both spellings are sugar — RESEARCH.md §D.2)."
    - "`test_toon_serializer_byte_deterministic_100_runs`: serialize the same DataFrame (with categorical, Int64 nullable, tz-aware timestamp columns) 100 times via `tradewinds.core.formats.toon`. All 100 outputs are byte-identical (`hashlib.sha256(out).hexdigest()` identical 100 times). If NOT deterministic, surface to user — Wave 1 cannot ship until TOON is deterministic."
    - "In-process integration test `test_in_process_query_envelope_shape`: spin up `mcp` in-process via `run_server_async`, call `query(source_id='_placeholder', as_of='2024-01-15T00:00:00Z')` — returns a `QueryResponse`-shaped dict with `format=='toon'`, `data` is a string, `schema_id` is a string, `audit_id` is a string."
    - "`packages/mcp/pyproject.toml` declares `Requires-Dist`: `tradewinds>=0.2.0,<0.3`, `mcp>=1.27,<2.0`, `pydantic>=2.7,<3.0`, `pyyaml>=6.0,<7` (PyYAML reserved for Wave 2 catalog loader — pinned here so Wave 2 doesn't need a pyproject bump)."
    - "`uv build packages/mcp` produces `tradewinds_mcp-0.2.0-py3-none-any.whl` with no `tradewinds/__init__.py` collision against the other three packages (verify via `unzip -l` + grep)."
    - "`uv run pytest packages/mcp/tests/ -m 'not live' -q` exits 0 with all tests passing."
    - "`uv run ruff check .` and `uv run ruff format --check .` return 0 errors / 0 diffs."
    - "Pre-commit + pre-push hooks pass (no `--no-verify`)."
  artifacts:
    - path: packages/mcp/pyproject.toml
      provides: "tradewinds-mcp PyPI distribution declaration; pins mcp>=1.27,<2.0 + tradewinds>=0.2.0,<0.3 + pydantic>=2.7,<3.0 + pyyaml>=6.0,<7"
      contains: "name = \"tradewinds-mcp\""
    - path: packages/mcp/src/tradewinds_mcp/server.py
      provides: "FastMCP instance + 5 tool registrations + temporal-middleware attachment + main() entry reading TRADEWINDS_MCP_TRANSPORT"
      contains: "from mcp.server.fastmcp import FastMCP"
      min_lines: 50
    - path: packages/mcp/src/tradewinds_mcp/temporal_middleware.py
      provides: "TemporalSafetyMiddleware(Middleware) with on_call_tool hook; READ_TOOLS={'query','ingest'}"
      contains: "class TemporalSafetyMiddleware"
      min_lines: 40
    - path: packages/mcp/src/tradewinds_mcp/audit.py
      provides: "AuditLogger writing append-only JSONL at $HOME/.tradewinds/mcp-server/audit-<startup-iso>-<pid>.jsonl; sort_keys=True"
      contains: "class AuditLogger"
      min_lines: 50
    - path: packages/mcp/src/tradewinds_mcp/caller_context.py
      provides: "CallerContext Pydantic BaseModel (identity / caller_kind / granted_scopes); v0.3 hosted-auth seam"
      contains: "class CallerContext"
    - path: packages/mcp/src/tradewinds_mcp/envelopes.py
      provides: "QueryResponse / IngestResponse / SchemaResponse / ListSourcesResponse / DescribeSourceResponse Pydantic BaseModels (data: str — TOON-encoded)"
      contains: "class QueryResponse"
    - path: packages/mcp/src/tradewinds_mcp/tools/query.py
      provides: "query(source_id, as_of: datetime, filters: dict | None, format: str = 'toon') -> QueryResponse stub returning empty placeholder DataFrame; real catalog wired in Wave 2"
      contains: "@mcp.tool()"
    - path: packages/mcp/src/tradewinds_mcp/tools/get_schema.py
      provides: "get_schema(schema_id) returns canonical schema JSON from tradewinds.core.schemas registry"
      contains: "from tradewinds.core.schemas"
    - path: packages/mcp/tests/test_meta_temporal_bypass_guard.py
      provides: "Structural anti-bypass meta-test — iterates mcp._tool_manager._tools, asserts every READ tool has as_of param with no default"
      contains: "def test_no_read_tool_lacks_as_of"
    - path: packages/mcp/tests/test_toon_deterministic.py
      provides: "test_toon_serializer_byte_deterministic_100_runs over categorical + Int64 + tz-aware columns"
      contains: "def test_toon_serializer_byte_deterministic_100_runs"
    - path: packages/mcp/tests/test_in_process_query.py
      provides: "FastMCP run_server_async + ClientSession in-process integration test"
      contains: "from fastmcp.utilities.tests import run_server_async"
    - path: packages/core/src/tradewinds/core/temporal/dataset.py
      provides: "Dataset wrapper with at_time / between / as_of point-in-time API (MCP-08)"
      contains: "class Dataset"
      min_lines: 40
  key_links:
    - from: packages/mcp/src/tradewinds_mcp/server.py
      to: packages/mcp/src/tradewinds_mcp/temporal_middleware.py
      via: "mcp.add_middleware(TemporalSafetyMiddleware()) at module-level BEFORE tool decorator imports (RESEARCH.md §D.1)"
      pattern: "mcp\\.add_middleware\\(TemporalSafetyMiddleware\\(\\)\\)"
    - from: packages/mcp/src/tradewinds_mcp/tools/query.py
      to: packages/core/src/tradewinds/core/temporal/dataset.py
      via: "Dataset(df, schema_id=...).at_time(as_of) is the canonical point-in-time call inside the query tool body"
      pattern: "Dataset\\([^)]+\\)\\.at_time\\(as_of\\)"
    - from: packages/mcp/src/tradewinds_mcp/tools/query.py
      to: packages/core/src/tradewinds/core/formats/toon.py
      via: "toon serializer is the boundary format — toon_fmt.serialize(filtered_df) produces the data: str field of QueryResponse (CONTEXT.md locked decision)"
      pattern: "from tradewinds\\.core\\.formats import toon"
    - from: packages/mcp/src/tradewinds_mcp/audit.py
      to: $HOME/.tradewinds/mcp-server/audit-<startup-iso>-<pid>.jsonl
      via: "per-instance audit log; filename includes startup ISO timestamp + pid for clean isolation (per RESEARCH.md Open Question #3 recommendation)"
      pattern: "audit-.*\\.jsonl"
    - from: packages/mcp/src/tradewinds_mcp/server.py
      to: os.environ.get('TRADEWINDS_MCP_TRANSPORT', 'stdio')
      via: "transport seam — v0.3 hosted-mode is a one-line env-var change (RESEARCH.md §A.3 + §F.3)"
      pattern: "TRADEWINDS_MCP_TRANSPORT"
    - from: packages/mcp/src/tradewinds_mcp/tools/get_schema.py
      to: packages/core/src/tradewinds/core/schemas/__init__.py
      via: "get_schema(schema_id) reads from Phase 2's eager-registered SchemaRegistration registry"
      pattern: "from tradewinds\\.core\\.schemas import"
---

<objective>
**Wave 1 ships the structural foundation of the MCP server: a runnable FastMCP instance with five tools, a temporal-safety middleware that no future tool can bypass, an append-only audit log, the `CallerContext` v0.3 auth seam, and the `Dataset` point-in-time API on top of Phase 2's `KnowledgeView`.**

This plan is THE load-bearing plan of Phase 5. Waves 2 (catalog), 3 (agent-generated connectors), and 4 (second vertical) all attach to interfaces this plan defines. The middleware in particular is structural — if it leaks (i.e., a future tool registers without going through the bypass guard), the whole "agent literally cannot bypass temporal safety" thesis collapses (MCP-04). Therefore this plan ships with a META-TEST that walks the FastMCP tool registry and proves no read tool can ever drop the `as_of` parameter.

**Five tools shipped as STUBS:**
- `query(source_id, as_of: datetime, filters, format)` → returns a `QueryResponse` envelope with a TOON-encoded empty placeholder DataFrame; real catalog wired in Wave 2.
- `ingest(source_id, as_of: datetime, ...)` → stub; real fetch logic in Wave 2/4.
- `list_sources()` → returns a placeholder list (`["_placeholder"]`); real list in Wave 2.
- `describe_source(source_id)` → returns a placeholder description; real catalog in Wave 2.
- `get_schema(schema_id)` → REAL implementation, reads from Phase 2's `tradewinds.core.schemas` registry. This is the only tool that's fully functional in Wave 1 because Phase 2 already shipped the canonical schemas.

**Five LOCKED decisions consumed in Wave 1:**
1. `mcp>=1.27,<2.0` + FastMCP pattern (`from mcp.server.fastmcp import FastMCP`) — RESEARCH.md §A.5
2. `toon` at MCP boundary (Pydantic envelope `{format, data: str, schema_id, audit_id}`; NEVER raw `pd.DataFrame`) — CONTEXT.md locked + RESEARCH.md §A.2 + §I.2
3. Temporal safety via single `on_call_tool` middleware (structural, can't be bypassed by new tools) — CONTEXT.md locked + RESEARCH.md §D.1
4. Audit log JSONL at `$HOME/.tradewinds/mcp-server/audit-<startup-iso>-<pid>.jsonl` (per-instance, sort_keys=True for replay determinism) — CONTEXT.md locked + RESEARCH.md §I.3 mitigation
5. `CallerContext` seam for v0.3 hosted compatibility (always `identity='local'` in v0.2) — RESEARCH.md §F.3 + §G

**Two RESEARCH.md pitfalls hard-mitigated in Wave 1:**
- **I.1 — middleware-vs-decorator confusion:** all `as_of` validation lives in `temporal_middleware.py`. Tool bodies do NOT re-validate. Documented in `packages/mcp/CONTRIBUTING.md` (Task 1.6).
- **I.3 — deterministic replay broken by dict iteration order:** `AuditLogger.log` uses `json.dumps(d, sort_keys=True)`. Tested by `test_audit_serialization_alphabetized`.
- **I.5 — TOON not deterministic in Phase 2's lifted code:** Wave 1 ships `test_toon_serializer_byte_deterministic_100_runs` as a FIRST-ORDER deliverable (Task 1.5). If TOON is found nondeterministic, surface to user BEFORE Wave 4 builds replay tests on top.
- **I.6 — stdio server logging to stdout breaks JSON-RPC framing:** server entry-point configures `logging.basicConfig(stream=sys.stderr)` explicitly + `packages/mcp/CONTRIBUTING.md` documents the rule (Task 1.6).

**Out of scope (deferred to other Phase 5 waves):**
- Wave 2: per-source YAML catalog files; real `list_sources`/`describe_source`/`query`/`ingest` wiring to the catalog; 7 weather catalog entries.
- Wave 3: agent-generated connector pipeline + `_generated/` → `catalog/` promotion CI.
- Wave 4: second vertical (FRED+ALFRED+Kalshi macro per RESEARCH.md §E recommendation, pending user confirmation at the start of Wave 4); end-to-end JSON-RPC subprocess integration tests; deterministic-replay tests over real query results; v0.2.0 release.

**Output:** A runnable `tradewinds-mcp` PyPI distribution that exposes a FastMCP server with five tools, a structurally-enforced temporal-safety middleware, an audit log, and a `Dataset` point-in-time API in `tradewinds.core`. After this plan merges to `main`, Waves 2-4 can build on top.
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
@.planning/phase-05-mcp-data-platform/05-00-SUMMARY.md
@./CLAUDE.md
</execution_context>

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from Phase 2 PLAN.md. -->
<!-- These exist (or will exist) at the time Phase 5 Wave 1 begins. -->

From Phase 2 (`packages/core/src/tradewinds/core/`):

```python
# tradewinds.core.temporal.timepoint
class TimePoint:  # plain class with __slots__
    event_time: datetime
    knowledge_time: datetime
    source: str
    retrieved_at: datetime | None

# tradewinds.core.temporal.knowledge_view
class KnowledgeView:  # plain class with __slots__, NOT a pandas accessor, NOT a DataFrame subclass
    def __init__(self, df: pd.DataFrame, *, as_of: datetime): ...
    def rows(self) -> pd.DataFrame: ...  # returns rows where knowledge_time <= as_of

# tradewinds.core.exceptions
class TradewindsError(Exception):
    def to_dict(self) -> dict: ...  # for JSON-RPC serialization (MCP-07 reuse)

class SchemaValidationError(TradewindsError): ...
class SourceMismatchError(TradewindsError): ...
class LeakageError(TradewindsError): ...
class SourceUnavailableError(TradewindsError): ...

# tradewinds.core.schema
class Schema: ...
class ColumnSpec: ...
class SchemaRegistration: ...

# tradewinds.core.validator
def validate_dataframe(df: pd.DataFrame, schema_id: str, allow_source_drift: bool | None = None) -> SchemaRegistration: ...

# tradewinds.core.schemas — eager-registered canonical schemas
# Available IDs: "schema.observation.v1", "schema.forecast.iem_mos.v1", "schema.settlement.cli.v1"

# tradewinds.core.formats.toon
def serialize(df: pd.DataFrame) -> str: ...  # TOON-encoded; Wave 1 test asserts byte-determinism
def deserialize(s: str) -> pd.DataFrame: ...
```

From `mcp>=1.27,<2.0` (Anthropic Python SDK):

```python
# mcp.server.fastmcp
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("server-name")

@mcp.tool()
async def my_tool(param: type) -> ReturnType: ...

mcp.add_middleware(some_middleware)
mcp.run(transport="stdio")  # or "http"

# fastmcp.server.middleware (the middleware base class)
from fastmcp.server.middleware import Middleware, MiddlewareContext

class MyMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # context.message.name = tool name
        # context.message.arguments = dict of tool args
        result = await call_next(context)
        return result

# mcp.types.ToolError — raise to surface tool failures via JSON-RPC error path
from mcp.types import ToolError

# fastmcp.utilities.tests (in-process testing helpers — RESEARCH.md §A.4)
from fastmcp.utilities.tests import run_server_async, run_server_in_process
```
</interfaces>

<phase_summary>

**Goal:** Build the FastMCP server skeleton + temporal-safety middleware + audit log + Dataset API + CallerContext seam, atomically and shipped together. The meta-test that proves no future tool can bypass the middleware is a Wave 1 deliverable, not a follow-up.

**Branch:** `phase-5/wave-1/mcp-server-skeleton` off `main`.

**TDD order (mandatory per CLAUDE.md):** RED → GREEN → REFACTOR per task. Each task writes failing tests FIRST, then implementation.

**Atomic commit boundaries (one RED commit + one GREEN commit per task; refactor commits as needed):**
- Task 1.1 (pyproject + package scaffold) → 1 commit (scaffolding; no tests yet)
- Task 1.2 (Dataset class in tradewinds.core.temporal) → 2 commits (RED + GREEN)
- Task 1.3 (CallerContext + envelopes) → 2 commits
- Task 1.4 (TemporalSafetyMiddleware + AuditLogger + meta-test) → 3 commits (RED + GREEN + meta-test commit)
- Task 1.5 (5 tool stubs + server.py + TOON determinism + in-process integration test) → 3 commits
- Task 1.6 (CONTRIBUTING.md + threat-model doc + pre-merge wheel build check) → 1 commit

**2-reviewer loop per REVIEW-DISCIPLINE.md:** codex `high` + python-architect. Never-skip applies (new `packages/mcp/` distribution + Phase 2 surface extension `tradewinds.core.temporal.Dataset`).

**Pre-merge gate (mandatory):**
1. All tests green: `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0.
2. META-TEST `test_no_read_tool_lacks_as_of` is in the green pytest output — explicit grep on the pytest output line.
3. TOON determinism test `test_toon_serializer_byte_deterministic_100_runs` is green.
4. In-process integration test `test_in_process_query_envelope_shape` is green.
5. Wheel build: `uv build packages/mcp` succeeds; `unzip -l dist/tradewinds_mcp-0.2.0-py3-none-any.whl` shows no `tradewinds/__init__.py` collision (PEP 420 namespace honored).
6. Pre-commit + pre-push hooks green.
7. 2-reviewer loop returns PASS x2 in ≤ 3 iterations.

</phase_summary>

<tasks>

<task type="auto">
  <name>Task 1.1: Scaffold packages/mcp/ distribution + pyproject.toml + namespace package layout (PEP 420)</name>
  <files>packages/mcp/pyproject.toml, packages/mcp/README.md, packages/mcp/src/tradewinds_mcp/__init__.py, packages/mcp/tests/__init__.py</files>
  <implements>MCP-01 (partial — distribution exists; tools come in 1.5)</implements>
  <read_first>
    - .planning/phase-02-core-primitives-catalog-adapters/PLAN.md (Wave 5 — pyproject.toml pattern for tradewinds + tradewinds-weather + tradewinds-markets; PEP 420 namespace handling per CLAUDE.md PKG-02; cross-package version pin via Requires-Dist per PKG-03)
    - .planning/phase-01-v0-14-1-parity-lift/PLAN.md (Day 1 scaffold-prep — wheel build verification via `uv build --all` + unzip check; same pattern applies to new packages/mcp/)
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§A.5 — exact mcp SDK pin; §A.3 — transport configuration; §F.3 — TRADEWINDS_MCP_TRANSPORT env var seam)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — "Catalog entries live at packages/mcp/catalog/"; "Claude's discretion — exact module structure inside packages/mcp/" — we pick packages/mcp/src/tradewinds_mcp/ sibling-package layout per RESEARCH.md Open Question #1, NOT tradewinds/mcp/ which would conflict with PEP 420 namespace)
    - CLAUDE.md (Recommended Stack — pin floors for mcp, pydantic, pyyaml; PKG-02 PEP 420 rule; PKG-03 cross-package version pin enforcement)
    - existing packages/core/pyproject.toml + packages/weather/pyproject.toml + packages/markets/pyproject.toml (reference for naming conventions, build-system table, hatch build config — DO NOT copy verbatim because tradewinds-mcp uses sibling-package layout, not namespace-shared layout)
  </read_first>
  <action>
    Step 1 — Create `packages/mcp/pyproject.toml` with:

    ```toml
    [build-system]
    requires = ["hatchling>=1.27"]
    build-backend = "hatchling.build"

    [project]
    name = "tradewinds-mcp"
    version = "0.2.0"
    description = "MCP server layer for tradewinds — local-first stdio MCP server exposing list_sources, describe_source, ingest, query, get_schema tools to AI agents"
    readme = "README.md"
    license = "MIT"
    requires-python = ">=3.11"
    authors = [{ name = "tradewinds maintainers" }]
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering",
    ]
    dependencies = [
        # Phase 5 inherits Phase 2's tradewinds.core (KnowledgeView, Schema, formats.toon, exceptions)
        "tradewinds>=0.2.0,<0.3",
        # mcp Python SDK — pin per RESEARCH.md §A.5
        "mcp>=1.27,<2.0",
        # Pydantic v2 for envelope BaseModels — already a transitive dep of mcp but explicit for safety
        "pydantic>=2.7,<3.0",
        # PyYAML for the Wave 2 catalog loader — pinned here so Wave 2 doesn't bump pyproject
        "pyyaml>=6.0,<7",
    ]

    [project.scripts]
    # Console script name parallels project name; main() lives in server.py
    tradewinds-mcp-server = "tradewinds_mcp.server:main"

    [project.urls]
    Homepage = "https://github.com/Tarabcak/tradewinds"
    Documentation = "https://github.com/Tarabcak/tradewinds/tree/main/packages/mcp"
    Repository = "https://github.com/Tarabcak/tradewinds"
    Issues = "https://github.com/Tarabcak/tradewinds/issues"

    [tool.hatch.build.targets.wheel]
    packages = ["src/tradewinds_mcp"]

    [tool.hatch.build.targets.sdist]
    include = ["src/", "README.md", "LICENSE"]
    ```

    **Important:** the layout is `packages/mcp/src/tradewinds_mcp/` (sibling-package, NOT a `tradewinds.mcp` subpackage). This is the RESEARCH.md Open Question #1 default: lowest risk of PEP 420 namespace collisions with the other three packages which all live under `tradewinds.*`. The console-script and import path both use `tradewinds_mcp` (underscore-separated, parallel to `tradewinds-mcp` PyPI name).

    Step 2 — Create `packages/mcp/README.md` (terse — full docs come in Phase 4 follow-up):

    ```markdown
    # tradewinds-mcp

    Local-first stdio MCP server exposing tradewinds tools to AI agents.

    Five tools: `list_sources`, `describe_source`, `ingest`, `query`, `get_schema`.

    Temporal safety is server-enforced — agents cannot bypass `KnowledgeView` filtering on `query`/`ingest`.

    ## Install

    `pip install tradewinds-mcp` (alpha — v0.2.0)

    ## Run

    ```bash
    tradewinds-mcp-server  # defaults to stdio transport
    ```

    Or via env var: `TRADEWINDS_MCP_TRANSPORT=stdio tradewinds-mcp-server`.

    ## Claude Desktop config

    ```json
    {
      "mcpServers": {
        "tradewinds": {
          "command": "tradewinds-mcp-server"
        }
      }
    }
    ```

    ## License

    MIT.
    ```

    Step 3 — Create `packages/mcp/src/tradewinds_mcp/__init__.py` with just:

    ```python
    """tradewinds-mcp — MCP server layer for the tradewinds data platform."""

    __version__ = "0.2.0"
    ```

    Step 4 — Create `packages/mcp/tests/__init__.py` (empty file — pytest package marker).

    Step 5 — Verify the new package builds. Run `uv build packages/mcp/`. Expected: produces `packages/mcp/dist/tradewinds_mcp-0.2.0-*.whl` + `*.tar.gz`. Open the wheel: `unzip -l packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl`. Expected contents: `tradewinds_mcp/__init__.py`, `tradewinds_mcp/-info/METADATA`, etc. CRITICAL — confirm NO `tradewinds/__init__.py` inside this wheel (it would collide with the core distribution per CLAUDE.md PKG-02).

    Step 6 — Run `uv sync` at repo root. Expected: `tradewinds-mcp` is added to the workspace; new deps `mcp>=1.27,<2.0` + `pydantic>=2.7,<3.0` + `pyyaml>=6.0,<7` are resolved into the lockfile.

    Step 7 — Run `uv run pre-commit run --all-files`. Expected green; pyproject TOML is valid; README markdown lints clean.

    Step 8 — Commit: `feat(phase-5): scaffold packages/mcp/ distribution + pyproject (MCP-01 PARTIAL — distribution exists, tools come in 1.5)`.
  </action>
  <verify>
    <automated>uv build packages/mcp/ && unzip -l packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl | grep -E "tradewinds_mcp/__init__.py"; test $? -eq 0 && (unzip -l packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl | grep -E "tradewinds/__init__.py" && exit 1 || exit 0) && uv sync && uv run pre-commit run --all-files</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/pyproject.toml` returns 0
    - `grep -c 'name = "tradewinds-mcp"' packages/mcp/pyproject.toml` returns 1
    - `grep -c 'mcp>=1.27,<2.0' packages/mcp/pyproject.toml` returns 1
    - `grep -c 'tradewinds>=0.2.0,<0.3' packages/mcp/pyproject.toml` returns 1
    - `grep -c 'pydantic>=2.7,<3.0' packages/mcp/pyproject.toml` returns 1
    - `grep -c 'pyyaml>=6.0,<7' packages/mcp/pyproject.toml` returns 1
    - `grep -c 'tradewinds-mcp-server = "tradewinds_mcp.server:main"' packages/mcp/pyproject.toml` returns 1
    - `test -f packages/mcp/src/tradewinds_mcp/__init__.py` returns 0
    - `test -f packages/mcp/README.md` returns 0
    - `test -f packages/mcp/tests/__init__.py` returns 0
    - `uv build packages/mcp/` exits 0 and produces `packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl`
    - `unzip -l packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl | grep -c "tradewinds/__init__.py"` returns 0 (PKG-02 PEP 420 — NO collision)
    - `unzip -l packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl | grep -c "tradewinds_mcp/__init__.py"` returns 1
    - `uv sync` exits 0
    - `uv run pre-commit run --all-files` exits 0
    - One commit on `phase-5/wave-1/mcp-server-skeleton`; commit message references MCP-01 + PARTIAL
  </acceptance_criteria>
  <done>
    `packages/mcp/` is a buildable PyPI distribution `tradewinds-mcp==0.2.0` with hatchling backend, `tradewinds_mcp` sibling-package layout (PEP 420 safe), and the four pinned deps. Wheel builds with no namespace collision. Workspace recognizes it.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 1.2: Dataset class in tradewinds.core.temporal (point-in-time API on top of Phase 2 KnowledgeView) (RED tests FIRST)</name>
  <files>packages/core/src/tradewinds/core/temporal/dataset.py, packages/core/src/tradewinds/core/temporal/__init__.py, packages/core/tests/core/temporal/test_dataset.py</files>
  <implements>MCP-08 (full — `dataset.at_time(date)`, `.between(start, end)`, `.as_of(timestamp)`)</implements>
  <read_first>
    - .planning/phase-02-core-primitives-catalog-adapters/PLAN.md (Wave 1 — KnowledgeView is a plain class with __slots__ wrapping pd.DataFrame; constructor signature `KnowledgeView(df, *, as_of: datetime)`; `.rows()` returns filtered pd.DataFrame)
    - packages/core/src/tradewinds/core/temporal/knowledge_view.py (POST-Phase-2 file — CRITICAL read; confirm the public surface matches the interfaces block above; if KnowledgeView returned by `rows()` is a copy, .between() can safely filter further without mutating; if it's a view, defensive copy in Dataset.between())
    - packages/core/src/tradewinds/core/temporal/__init__.py (existing re-exports — Dataset must be added without breaking imports from Phase 2)
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§D.2 — Dataset API design; at_time/between/as_of semantics; both spellings ship for ergonomics; key contract: as_of(t) == at_time(t))
    - CLAUDE.md (TDD mandatory; ≥90% branch coverage on tradewinds.core — Dataset is core, applies)
  </read_first>
  <behavior>
    Tests to write FIRST in `packages/core/tests/core/temporal/test_dataset.py` (RED):

    1. `test_dataset_constructor_stores_df_and_schema_id`: `Dataset(pd.DataFrame({"x":[1,2]}), schema_id="schema.observation.v1")` — assert `._df.equals(input_df)`, `._schema_id == "schema.observation.v1"`.
    2. `test_at_time_returns_knowledge_view_filtered`: construct a 4-row DataFrame with `knowledge_time` column = `[2024-01-01, 2024-01-15, 2024-02-01, 2024-03-01]`. `Dataset(df, "schema.observation.v1").at_time(datetime(2024, 2, 1, tzinfo=UTC))` returns a 3-row DataFrame (rows where knowledge_time <= 2024-02-01).
    3. `test_at_time_returns_pd_dataframe_not_knowledge_view`: result type is `pd.DataFrame` (NOT a `KnowledgeView` instance — Dataset returns rows, not the view object).
    4. `test_as_of_is_alias_for_at_time`: for the same input, `Dataset(df, sid).as_of(t).equals(Dataset(df, sid).at_time(t))` is True for `t in [..., 2024-01-15, 2024-02-01, 2025-01-01]`. Property-style test (3+ values).
    5. `test_between_returns_subrange`: with the 4-row DataFrame from test 2 + an `event_time` column = `[2024-01-01, 2024-01-15, 2024-02-01, 2024-03-01]`, `Dataset(df, sid).between(start=datetime(2024,1,10,tzinfo=UTC), end=datetime(2024,2,15,tzinfo=UTC))` returns the 2 rows with event_time in [2024-01-15, 2024-02-01]. Knowledge_time filter (`<= end=2024-02-15`) AND event_time filter (`>= start=2024-01-10`).
    6. `test_between_inclusive_boundaries`: `between(start=t1, end=t2)` where the data has rows exactly at t1 and t2 — both rows are included. Boundary semantics: `event_time >= start` AND `knowledge_time <= end`. Document in Dataset docstring.
    7. `test_between_empty_when_start_after_end`: `between(start=t2, end=t1)` where t1 < t2 returns an empty DataFrame.
    8. `test_constructor_rejects_non_dataframe`: `Dataset("not a df", "schema.observation.v1")` raises `TypeError`.
    9. `test_constructor_rejects_empty_schema_id`: `Dataset(df, schema_id="")` raises `ValueError`.
    10. `test_at_time_requires_tzaware_datetime`: `Dataset(df, sid).at_time(datetime(2024, 1, 15))` (NO tzinfo) raises `ValueError` (per Phase 2 KnowledgeView convention — all timestamps tz-aware UTC).

    Run `uv run pytest packages/core/tests/core/temporal/test_dataset.py -x` — MUST fail with `ImportError` (no Dataset class yet). Commit: `test(phase-5): add failing Dataset point-in-time API tests (MCP-08 RED)`.
  </behavior>
  <action>
    Step 1 — Write the 10 tests above into `packages/core/tests/core/temporal/test_dataset.py`. Import: `from tradewinds.core.temporal import Dataset` (Dataset will be re-exported via `__init__.py` in Step 3). Use `pytz.UTC` or `datetime.timezone.utc` consistently with Phase 2 convention (check `knowledge_view.py` to match). Run `uv run pytest packages/core/tests/core/temporal/test_dataset.py -x` — MUST FAIL on import. Commit RED.

    Step 2 — Implement `packages/core/src/tradewinds/core/temporal/dataset.py`:

    ```python
    """Dataset — point-in-time wrapper over a DataFrame.

    The Dataset class provides three sugar methods over Phase 2 KnowledgeView:
    - at_time(date) — rows knowable at the given timestamp
    - as_of(timestamp) — alias for at_time; both spellings ship for ergonomics
    - between(start, end) — rows where start <= event_time AND knowledge_time <= end

    Used by the MCP server's query tool (packages/mcp) to enforce temporal safety
    server-side. The MCP middleware passes the agent-supplied `as_of` through here
    BEFORE serializing — agent cannot bypass.

    All inputs MUST be tz-aware (UTC convention per Phase 2 KnowledgeView).
    """

    from __future__ import annotations

    from datetime import datetime
    import pandas as pd

    from .knowledge_view import KnowledgeView

    __all__ = ["Dataset"]


    class Dataset:
        """Wraps a DataFrame + schema_id; produces KnowledgeView-filtered rows."""

        __slots__ = ("_df", "_schema_id")

        def __init__(self, df: pd.DataFrame, schema_id: str) -> None:
            if not isinstance(df, pd.DataFrame):
                raise TypeError(f"Dataset df must be pd.DataFrame, got {type(df)!r}")
            if not isinstance(schema_id, str) or not schema_id:
                raise ValueError(f"Dataset schema_id must be non-empty str, got {schema_id!r}")
            self._df = df
            self._schema_id = schema_id

        @property
        def schema_id(self) -> str:
            return self._schema_id

        def at_time(self, date: datetime) -> pd.DataFrame:
            """Return rows whose knowledge_time <= date.

            Raises ValueError if date is not tz-aware (UTC convention).
            """
            self._require_tzaware(date, "at_time")
            return KnowledgeView(self._df, as_of=date).rows()

        def as_of(self, timestamp: datetime) -> pd.DataFrame:
            """Alias for at_time; both spellings ship for ergonomics."""
            return self.at_time(timestamp)

        def between(self, start: datetime, end: datetime) -> pd.DataFrame:
            """Return rows where event_time >= start AND knowledge_time <= end."""
            self._require_tzaware(start, "between(start)")
            self._require_tzaware(end, "between(end)")
            if start > end:
                return self._df.iloc[0:0]  # empty df preserving columns + dtypes
            rows = KnowledgeView(self._df, as_of=end).rows()
            return rows[rows["event_time"] >= start]

        @staticmethod
        def _require_tzaware(t: datetime, label: str) -> None:
            if t.tzinfo is None:
                raise ValueError(
                    f"Dataset.{label} requires tz-aware datetime (UTC convention); "
                    f"got naive {t!r}"
                )
    ```

    Step 3 — Modify `packages/core/src/tradewinds/core/temporal/__init__.py` to re-export Dataset:

    ```python
    """Public surface for tradewinds.core.temporal."""

    from .timepoint import TimePoint  # existing
    from .knowledge_view import KnowledgeView  # existing
    from .leakage import LeakageDetector  # existing
    from .dataset import Dataset  # NEW (Phase 5 Wave 1)

    __all__ = ["TimePoint", "KnowledgeView", "LeakageDetector", "Dataset"]
    ```

    (Adapt to whatever exact pattern Phase 2 used — preserve existing exports.)

    Step 4 — Run `uv run pytest packages/core/tests/core/temporal/test_dataset.py -x -v` — all 10 tests MUST pass.

    Step 5 — Run `uv run pytest -m "not live" -q` (full fast suite) to catch any regression in Phase 2's KnowledgeView/LeakageDetector tests. Expected green.

    Step 6 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Commit: `feat(phase-5): add tradewinds.core.temporal.Dataset point-in-time API (MCP-08 GREEN)`.

    Step 7 — Verify branch-coverage gate stays ≥ 90% on tradewinds.core (CLAUDE.md): `uv run pytest --cov=tradewinds.core --cov-branch packages/core/tests/ | grep TOTAL`. The Dataset class adds ~30 LOC; tests cover all branches (constructor validation, both at_time/as_of paths, between subrange + empty + boundary).
  </action>
  <verify>
    <automated>uv run pytest packages/core/tests/core/temporal/test_dataset.py -x -v && uv run pytest -m "not live" -q && uv run pytest --cov=tradewinds.core --cov-branch packages/core/tests/ -q | tee /tmp/cov.txt && grep TOTAL /tmp/cov.txt | awk '{print $NF}' | sed 's/%//' | awk '$1+0 >= 90 {exit 0} {exit 1}'</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/core/src/tradewinds/core/temporal/dataset.py` returns 0
    - `grep -c "class Dataset" packages/core/src/tradewinds/core/temporal/dataset.py` returns 1
    - `grep -c "__slots__" packages/core/src/tradewinds/core/temporal/dataset.py` returns 1 (plain class with slots, per Phase 2 pattern)
    - `grep -c "def at_time" packages/core/src/tradewinds/core/temporal/dataset.py` returns 1
    - `grep -c "def as_of" packages/core/src/tradewinds/core/temporal/dataset.py` returns 1
    - `grep -c "def between" packages/core/src/tradewinds/core/temporal/dataset.py` returns 1
    - `grep -c "KnowledgeView(self._df, as_of=" packages/core/src/tradewinds/core/temporal/dataset.py` returns ≥ 2 (at_time + between use the same wrapper)
    - `grep "from .dataset import Dataset" packages/core/src/tradewinds/core/temporal/__init__.py` returns non-empty
    - `grep "\"Dataset\"" packages/core/src/tradewinds/core/temporal/__init__.py` returns non-empty (in __all__)
    - `uv run pytest packages/core/tests/core/temporal/test_dataset.py -x -v` exits 0 with 10 passed
    - `uv run pytest -m "not live" -q` exits 0 (no Phase 2 regression)
    - `uv run pytest --cov=tradewinds.core --cov-branch packages/core/tests/` reports TOTAL ≥ 90% branch coverage
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify` used
  </acceptance_criteria>
  <done>
    `Dataset(df, schema_id).at_time(date)`, `.as_of(timestamp)`, `.between(start, end)` work, validated by 10 tests. as_of == at_time. Tz-aware required. Re-exported from `tradewinds.core.temporal`. Branch coverage on tradewinds.core remains ≥ 90%.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 1.3: CallerContext (v0.3 auth seam) + 5 Pydantic response envelopes (RED tests FIRST)</name>
  <files>packages/mcp/src/tradewinds_mcp/caller_context.py, packages/mcp/src/tradewinds_mcp/envelopes.py, packages/mcp/tests/test_caller_context.py, packages/mcp/tests/test_envelopes.py</files>
  <implements>MCP-01 (partial — envelope shapes), MCP-06 (partial — caller_identity field in audit log will reference CallerContext.identity in Task 1.4)</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§A.2 — Pydantic BaseModel envelope rationale; §F.3 — CallerContext shape: identity / caller_kind / granted_scopes; §G — caller_identity is the seam covering all 4 hosted-pricing models; §I.2 — pitfall: do NOT nest TOON inside structured dicts; flat envelope with `data: str`)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — "toon at MCP boundary"; forbid raw pd.DataFrame returns; forbid parquet bytes; forbid pickled DataFrame)
    - packages/core/src/tradewinds/core/exceptions.py (Phase 2 — TradewindsError.to_dict() shape for JSON-RPC error envelopes; envelope failure mode reuses this)
    - mcp SDK docs (already loaded transitively — Pydantic v2 is the official runtime; BaseModel is fine; auto-validates input/output)
  </read_first>
  <behavior>
    Tests to write FIRST in `packages/mcp/tests/test_caller_context.py` (RED, 4 tests):

    1. `test_caller_context_default_factory`: `CallerContext.local()` (classmethod factory) returns `identity="local"`, `caller_kind="local"`, `granted_scopes=["*"]`.
    2. `test_caller_context_oauth_kind`: `CallerContext(identity="user@example.com", caller_kind="oauth", granted_scopes=["read:query"])` constructs without error.
    3. `test_caller_context_invalid_kind_rejected`: `CallerContext(identity="x", caller_kind="something_else", granted_scopes=[])` raises `pydantic.ValidationError`.
    4. `test_caller_context_serializable`: `CallerContext.local().model_dump()` returns a dict `{"identity": "local", "caller_kind": "local", "granted_scopes": ["*"]}` — serializable for audit-log inclusion.

    Tests to write FIRST in `packages/mcp/tests/test_envelopes.py` (RED, 6 tests):

    1. `test_query_response_fields`: `QueryResponse(format="toon", data="some_toon_string", schema_id="schema.observation.v1", audit_id="audit-2026-06-01T14:00:00Z-12345-007")` constructs; `.data` is `str` (NOT dict, NOT DataFrame).
    2. `test_query_response_rejects_dataframe_data`: `QueryResponse(format="toon", data=pd.DataFrame({"x":[1]}), schema_id="x", audit_id="x")` raises `pydantic.ValidationError` — `data` field annotation `str` enforced.
    3. `test_query_response_serializable`: `QueryResponse(...).model_dump()` returns a dict that survives `json.dumps` roundtrip (CONTEXT.md TOON-at-boundary lock).
    4. `test_ingest_response_shape`: `IngestResponse(format="toon", data="...", schema_id="...", audit_id="...", rows_ingested=42)` constructs; has `rows_ingested: int` field in addition to QueryResponse fields.
    5. `test_list_sources_response_shape`: `ListSourcesResponse(sources=["iem.archive", "awc.live"])` constructs; `.sources: list[str]`.
    6. `test_describe_source_response_shape`: `DescribeSourceResponse(source_id="iem.archive", description="...", schema_id="...", catalog_entry={"foo": "bar"})` constructs; `catalog_entry: dict` is the structured 5-layer context (Wave 2 fills it in).

    Run `uv run pytest packages/mcp/tests/test_caller_context.py packages/mcp/tests/test_envelopes.py -x` — MUST fail (no module yet). Commit: `test(phase-5): add failing CallerContext + envelope tests (MCP-01 partial + MCP-06 seam RED)`.
  </behavior>
  <action>
    Step 1 — Write the 10 tests above. Commit RED.

    Step 2 — Implement `packages/mcp/src/tradewinds_mcp/caller_context.py`:

    ```python
    """CallerContext — v0.3 auth seam.

    v0.2 always populates identity='local' (stdio server inherits parent process
    environment; no auth). v0.3+ hosted-mode middleware will populate from a
    validated OAuth token. Tool bodies receive CallerContext via FastMCP context
    state — they NEVER read os.environ or HTTP headers directly.

    Per RESEARCH.md §F.3 + §G: this single seam covers all four hosted-pricing
    models (license-key, flat-subscription, usage-metering, multi-tenant-isolation)
    without v0.2 rework.
    """

    from __future__ import annotations

    from typing import Literal
    from pydantic import BaseModel, Field

    __all__ = ["CallerContext"]


    class CallerContext(BaseModel):
        identity: str = Field(..., description="Identifier for the calling agent / user. 'local' for v0.2 stdio servers; OAuth subject in v0.3+ hosted.")
        caller_kind: Literal["local", "oauth"] = Field(..., description="Auth source. v0.2 = always 'local'.")
        granted_scopes: list[str] = Field(default_factory=lambda: ["*"], description="Scopes the caller is authorized for. v0.2 always ['*']; v0.3+ enforces scope checks per tool.")

        @classmethod
        def local(cls) -> "CallerContext":
            """Factory for v0.2 stdio mode — local caller, all scopes granted."""
            return cls(identity="local", caller_kind="local", granted_scopes=["*"])
    ```

    Step 3 — Implement `packages/mcp/src/tradewinds_mcp/envelopes.py`:

    ```python
    """Pydantic response envelopes for the 5 MCP tools.

    Envelope shape is flat (per RESEARCH.md §I.2 pitfall): `data: str` carries
    the TOON-encoded payload as a string; structured fields live OUTSIDE `data`.
    FastMCP auto-generates JSON Schema from these BaseModels — the meta-schema
    is what the get_schema(schema_id) tool returns for the envelope itself.
    The schema OF the data (column types of the inner DataFrame) is separate —
    referenced by `schema_id` and resolvable via get_schema(schema_id).
    """

    from __future__ import annotations

    from pydantic import BaseModel, Field

    __all__ = [
        "QueryResponse",
        "IngestResponse",
        "ListSourcesResponse",
        "DescribeSourceResponse",
        "SchemaResponse",
    ]


    class QueryResponse(BaseModel):
        format: str = Field(..., description="Wire format of `data`. v0.2 is always 'toon'.")
        data: str = Field(..., description="TOON-encoded DataFrame as a string. NEVER a dict/dataframe — flat envelope per RESEARCH.md §I.2.")
        schema_id: str = Field(..., description="Canonical schema ID; resolvable via get_schema(schema_id).")
        audit_id: str = Field(..., description="Cross-reference to the audit.jsonl entry recorded for this call.")


    class IngestResponse(BaseModel):
        format: str
        data: str
        schema_id: str
        audit_id: str
        rows_ingested: int = Field(..., description="Number of rows ingested into the local cache (after temporal-safety filter).")


    class ListSourcesResponse(BaseModel):
        sources: list[str] = Field(..., description="Source IDs available in the catalog. Wave 2 wires this to the real catalog; Wave 1 returns a placeholder.")


    class DescribeSourceResponse(BaseModel):
        source_id: str
        description: str = Field(..., description="Human-readable summary; Wave 2 pulls from catalog entry display_name + first quality_note.")
        schema_id: str
        catalog_entry: dict = Field(..., description="Full 5-layer catalog entry (Wave 2 populates; Wave 1 returns empty dict placeholder).")


    class SchemaResponse(BaseModel):
        schema_id: str
        schema_json: dict = Field(..., description="JSON Schema for the named schema_id; v0.2 reads from tradewinds.core.schemas registry.")
    ```

    Step 4 — Run `uv run pytest packages/mcp/tests/test_caller_context.py packages/mcp/tests/test_envelopes.py -x -v` — all 10 tests MUST pass.

    Step 5 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Commit: `feat(phase-5): CallerContext + 5 Pydantic response envelopes (MCP-01 partial + MCP-06 seam GREEN)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_caller_context.py packages/mcp/tests/test_envelopes.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/src/tradewinds_mcp/caller_context.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/envelopes.py` returns 0
    - `grep -c "class CallerContext" packages/mcp/src/tradewinds_mcp/caller_context.py` returns 1
    - `grep -c "Literal\\[.local., .oauth.\\]" packages/mcp/src/tradewinds_mcp/caller_context.py` returns 1
    - `grep -c "def local" packages/mcp/src/tradewinds_mcp/caller_context.py` returns 1 (factory method)
    - `grep -c "class QueryResponse" packages/mcp/src/tradewinds_mcp/envelopes.py` returns 1
    - `grep -c "class IngestResponse" packages/mcp/src/tradewinds_mcp/envelopes.py` returns 1
    - `grep -c "class ListSourcesResponse" packages/mcp/src/tradewinds_mcp/envelopes.py` returns 1
    - `grep -c "class DescribeSourceResponse" packages/mcp/src/tradewinds_mcp/envelopes.py` returns 1
    - `grep -c "class SchemaResponse" packages/mcp/src/tradewinds_mcp/envelopes.py` returns 1
    - `grep -E "data: str = Field" packages/mcp/src/tradewinds_mcp/envelopes.py | wc -l | awk '$1 >= 2 {exit 0} {exit 1}'` (at least QueryResponse + IngestResponse have flat `data: str`, per Pitfall I.2)
    - `uv run pytest packages/mcp/tests/test_caller_context.py packages/mcp/tests/test_envelopes.py -x -v` exits 0 with 10 passed
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    `CallerContext.local()` produces the v0.2 caller. Five Pydantic envelopes (QueryResponse/IngestResponse/ListSourcesResponse/DescribeSourceResponse/SchemaResponse) have flat `data: str` shape per RESEARCH.md §I.2 pitfall guard. 10 tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 1.4: TemporalSafetyMiddleware + AuditLogger + META-TEST against bypass (RED tests FIRST)</name>
  <files>packages/mcp/src/tradewinds_mcp/temporal_middleware.py, packages/mcp/src/tradewinds_mcp/audit.py, packages/mcp/tests/test_temporal_middleware.py, packages/mcp/tests/test_audit.py, packages/mcp/tests/test_meta_temporal_bypass_guard.py</files>
  <implements>MCP-04 (full — server-enforced temporal safety, structural anti-bypass), MCP-06 (full — auditable provenance JSONL)</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§D.1 — FastMCP `on_call_tool` middleware pattern; verbatim TemporalSafetyMiddleware skeleton at lines 274-310; §D.3 — deterministic replay design + hash format `sha256(toon_string.encode("utf-8")).hexdigest()`; §I.1 — pitfall: middleware vs decorator confusion; §I.3 — pitfall: dict iteration order broken by missing sort_keys=True; §I.6 — pitfall: stdio stdout corruption; §I.8 — pitfall: cross-vertical join — audit log records joins_to=undeclared for later analysis)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — audit format `(timestamp, tool_name, source_id, schema_version, as_of, retrieval_timestamp, row_count, hash_of_result)`; per-instance file naming; deterministic replay test idiom)
    - mcp + fastmcp middleware docs (already covered in interfaces block; key: `Middleware` base class, `on_call_tool(context, call_next)` hook, `context.message.name` + `context.message.arguments`, `ToolError` to raise)
    - packages/mcp/src/tradewinds_mcp/caller_context.py (Task 1.3 — AuditLogger.log() must accept a `caller_identity: str` field per RESEARCH.md §G)
  </read_first>
  <behavior>
    Tests to write FIRST in `packages/mcp/tests/test_temporal_middleware.py` (RED, 6 tests):

    1. `test_middleware_read_tools_set`: `from tradewinds_mcp.temporal_middleware import TemporalSafetyMiddleware; assert TemporalSafetyMiddleware.READ_TOOLS == frozenset({"query", "ingest"})` — exact set, immutable. (Use `frozenset`, not `set` — RESEARCH.md §D.1 implies immutability; a future tool author can't accidentally `READ_TOOLS.add("new_tool")` in another module.)
    2. `test_middleware_rejects_missing_as_of`: Build a fake `MiddlewareContext` with `message.name="query"`, `message.arguments={"source_id": "x"}` (no as_of). Call `await middleware.on_call_tool(ctx, call_next=AsyncMock())`. Asserts that `ToolError` is raised; error message contains "as_of" and "query".
    3. `test_middleware_rejects_none_as_of`: same as above but `arguments={"source_id":"x", "as_of": None}`. `ToolError` raised.
    4. `test_middleware_accepts_present_as_of`: `arguments={"source_id":"x", "as_of": datetime(2024,1,1,tzinfo=UTC)}`. `await middleware.on_call_tool(ctx, call_next)` returns the result of `call_next(ctx)` — no error.
    5. `test_middleware_skips_non_read_tools`: `message.name="list_sources"`, `arguments={}`. No `as_of` check; `call_next` runs; result returned. List/describe/get_schema are NOT in READ_TOOLS, so the middleware is a pass-through.
    6. `test_middleware_calls_audit_log_on_success`: Configure middleware with `AuditLogger` instance; `arguments={"source_id":"x", "as_of": datetime(2024,1,1,tzinfo=UTC), "_caller_context": CallerContext.local()}`. After `on_call_tool` returns, verify `audit_logger.log` was called with `tool="query"`, `as_of=...`, `caller_identity="local"`.

    Tests to write FIRST in `packages/mcp/tests/test_audit.py` (RED, 7 tests):

    1. `test_audit_logger_default_path`: `AuditLogger()` writes to `$HOME/.tradewinds/mcp-server/audit-<iso>-<pid>.jsonl` — exact pattern `audit-2026-MM-DDTHH:MM:SS-NNNNN.jsonl`. Verify with regex.
    2. `test_audit_logger_appends_one_line_per_call`: `log(tool="query", source="iem.archive", as_of=t, rows=42, hash="sha256:abc", caller_identity="local", schema_id="schema.observation.v1", retrieval_timestamp=t2)` writes ONE line (terminated by `\n`) to the file. Three calls → 3 lines.
    3. `test_audit_logger_sort_keys_alphabetized` (Pitfall I.3 guard): Call `log(...)` with kwargs in a specific order; read the line back; assert it parses as JSON and `list(parsed.keys()) == sorted(parsed.keys())` — the JSON key order is alphabetic, NOT insertion order. This catches dict-iteration-order regressions.
    4. `test_audit_logger_includes_caller_identity` (RESEARCH.md §G v0.3 seam): every log entry has a `caller_identity` field. v0.2 always `"local"`. Even if `caller_identity` is not passed, default to `"local"`.
    5. `test_audit_logger_hash_format`: hash field value matches regex `^[a-f0-9]{64}$` (SHA-256 hex). The hash is computed externally (the tool body) and PASSED to AuditLogger; AuditLogger does NOT compute the hash itself (separation of concerns).
    6. `test_audit_logger_returns_audit_id`: `log(...)` returns a stable string ID (e.g., `audit-<iso>-<pid>-<seq>` where `seq` increments per call). Used in `QueryResponse.audit_id`.
    7. `test_audit_logger_concurrent_writes_dont_corrupt`: spawn 4 threads each calling `log(...)` 10 times. Read the resulting file — 40 valid JSON lines, no corruption, no partial writes. (Per-instance file means no cross-instance contention; but threads within one instance still need atomic appends — use a `threading.Lock` around `f.write`.)

    Tests to write FIRST in `packages/mcp/tests/test_meta_temporal_bypass_guard.py` (CRITICAL META-TEST, 1 test):

    1. `test_no_read_tool_lacks_as_of`: This is the structural anti-bypass guard. Import `tradewinds_mcp.server` (this side-effects all tool registrations). Iterate `mcp._tool_manager._tools.values()` (or the equivalent public-ish API FastMCP exposes — verify via FastMCP source at the time of writing). For every tool whose name is in `TemporalSafetyMiddleware.READ_TOOLS`, assert:
       - The tool's signature has a parameter named `as_of`.
       - That parameter's annotation is `datetime` (or a subclass).
       - That parameter has NO default value (forces caller to pass it).

       If a future maintainer adds a new tool name to `READ_TOOLS` without giving the tool an `as_of: datetime` parameter, this test FAILS at CI time. Document the test's purpose in a docstring referencing CONTEXT.md MCP-04 lock + RESEARCH.md §I.1 pitfall.

    Run `uv run pytest packages/mcp/tests/test_temporal_middleware.py packages/mcp/tests/test_audit.py packages/mcp/tests/test_meta_temporal_bypass_guard.py -x` — MUST fail. Commit: `test(phase-5): add failing temporal middleware + audit + meta-bypass-guard tests (MCP-04 + MCP-06 RED)`.
  </behavior>
  <action>
    Step 1 — Write the 14 tests above. Use FastMCP's test utilities for the middleware context fakes if available; otherwise hand-roll a `SimpleNamespace`-based mock for `MiddlewareContext` matching the actual FastMCP shape (verify against the installed `fastmcp` source). Commit RED.

    Step 2 — Implement `packages/mcp/src/tradewinds_mcp/audit.py`:

    ```python
    """Append-only JSONL audit logger for the MCP server.

    Per-instance file at $HOME/.tradewinds/mcp-server/audit-<iso>-<pid>.jsonl.
    Each MCP-tool call appends ONE JSON object (terminated by \\n).
    JSON keys are alphabetized (`sort_keys=True`) — guard against Pitfall I.3
    (dict iteration order broken by Pydantic / Python patch upgrade).

    The audit log doubles as the deterministic-replay log (RESEARCH.md §D.3).
    Wave 4 builds replay tests on top.
    """

    from __future__ import annotations

    import json
    import os
    import threading
    from datetime import datetime, timezone
    from pathlib import Path

    __all__ = ["AuditLogger"]


    class AuditLogger:
        def __init__(self, base_dir: Path | None = None) -> None:
            self._base_dir = base_dir or Path.home() / ".tradewinds" / "mcp-server"
            self._base_dir.mkdir(parents=True, exist_ok=True)
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            pid = os.getpid()
            self._path = self._base_dir / f"audit-{now_iso}-{pid}.jsonl"
            self._seq = 0
            self._lock = threading.Lock()
            # Create empty file so first read doesn't fail
            self._path.touch(exist_ok=True)

        @property
        def path(self) -> Path:
            return self._path

        def log(
            self,
            *,
            tool: str,
            source: str,
            as_of: datetime | str,
            rows: int,
            hash: str,
            schema_id: str,
            retrieval_timestamp: datetime | str | None = None,
            caller_identity: str = "local",
            extra: dict | None = None,
        ) -> str:
            """Append one JSONL entry; return a stable audit_id for cross-reference."""
            with self._lock:
                self._seq += 1
                audit_id = f"{self._path.stem}-{self._seq:06d}"
                entry: dict = {
                    "audit_id": audit_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "tool": tool,
                    "source": source,
                    "as_of": as_of.isoformat() if isinstance(as_of, datetime) else as_of,
                    "rows": rows,
                    "hash": hash,
                    "schema_id": schema_id,
                    "caller_identity": caller_identity,
                }
                if retrieval_timestamp is not None:
                    entry["retrieval_timestamp"] = (
                        retrieval_timestamp.isoformat()
                        if isinstance(retrieval_timestamp, datetime)
                        else retrieval_timestamp
                    )
                if extra:
                    # Caller-supplied extras (e.g., joins_to_undeclared per Pitfall I.8)
                    # alphabetize via sort_keys=True below
                    entry.update(extra)
                line = json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n"
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(line)
                return audit_id
    ```

    Step 3 — Implement `packages/mcp/src/tradewinds_mcp/temporal_middleware.py`:

    ```python
    """TemporalSafetyMiddleware — structural enforcement of as_of on every read tool.

    Per CONTEXT.md MCP-04 lock: "Every MCP tool that returns rows runs a server-side
    KnowledgeView(as_of=...) filter BEFORE serializing. The as_of parameter is
    REQUIRED on every read tool (query, ingest). No agent-supplied as_of=None
    short-circuit. The constraint lives in a single shared decorator/middleware so
    it cannot be accidentally bypassed by a new tool."

    Per RESEARCH.md §D.1: FastMCP's `on_call_tool` hook intercepts BEFORE the tool
    body executes. Tools authored without thinking about temporal safety are STILL
    wrapped — the middleware checks `context.message.arguments` directly.

    The META-TEST in test_meta_temporal_bypass_guard.py walks the tool registry
    and asserts every READ tool has `as_of: datetime` with no default. CI-enforced.
    """

    from __future__ import annotations

    import hashlib
    from typing import Any
    from fastmcp.server.middleware import Middleware, MiddlewareContext
    from mcp.types import ToolError  # FastMCP raises this; surfaces via JSON-RPC error path

    from .audit import AuditLogger
    from .caller_context import CallerContext

    __all__ = ["TemporalSafetyMiddleware"]


    class TemporalSafetyMiddleware(Middleware):
        """Enforces KnowledgeView filter on every tool that returns rows.

        READ_TOOLS is frozen — to add a new read tool, edit the set HERE and ensure
        the new tool has `as_of: datetime` parameter (META-TEST enforces).
        """

        READ_TOOLS: frozenset[str] = frozenset({"query", "ingest"})

        def __init__(self, audit_logger: AuditLogger | None = None) -> None:
            self._audit = audit_logger or AuditLogger()

        async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
            tool_name = context.message.name
            params = context.message.arguments or {}

            if tool_name in self.READ_TOOLS:
                if "as_of" not in params or params.get("as_of") is None:
                    raise ToolError(
                        f"Tool '{tool_name}' requires `as_of` parameter "
                        f"(temporal safety cannot be bypassed). "
                        f"Received params: {sorted(params.keys())}"
                    )

            result = await call_next(context)

            # Best-effort audit for read tools that returned a hashable envelope
            if tool_name in self.READ_TOOLS:
                try:
                    data_field = self._extract_data_str(result)
                    hash_hex = hashlib.sha256(data_field.encode("utf-8")).hexdigest() if data_field else ""
                    caller_ident = self._extract_caller_identity(params)
                    self._audit.log(
                        tool=tool_name,
                        source=str(params.get("source_id", "unknown")),
                        as_of=params.get("as_of"),
                        rows=self._extract_rows(result),
                        hash=hash_hex,
                        schema_id=self._extract_schema_id(result),
                        caller_identity=caller_ident,
                    )
                except Exception:
                    # Audit failure MUST NOT fail the tool call.
                    # Logged via stderr (NOT stdout — Pitfall I.6) for debugging.
                    import sys, traceback
                    print(f"[tradewinds-mcp audit] WARNING — audit failure: {traceback.format_exc()}", file=sys.stderr)

            return result

        @staticmethod
        def _extract_data_str(result: Any) -> str:
            """Extract the `data` string from a QueryResponse / IngestResponse envelope."""
            if hasattr(result, "data"):
                return getattr(result, "data") or ""
            if isinstance(result, dict) and "data" in result:
                return str(result["data"] or "")
            return ""

        @staticmethod
        def _extract_rows(result: Any) -> int:
            if hasattr(result, "rows_ingested"):
                return int(result.rows_ingested)
            # For query, we don't have rows count in the envelope directly; approximate
            # via TOON line count (Wave 2 may pass rows explicitly via extra={}).
            data = TemporalSafetyMiddleware._extract_data_str(result)
            return data.count("\n") if data else 0

        @staticmethod
        def _extract_schema_id(result: Any) -> str:
            if hasattr(result, "schema_id"):
                return getattr(result, "schema_id") or ""
            if isinstance(result, dict):
                return str(result.get("schema_id", ""))
            return ""

        @staticmethod
        def _extract_caller_identity(params: dict) -> str:
            cc = params.get("_caller_context")
            if isinstance(cc, CallerContext):
                return cc.identity
            return "local"
    ```

    Step 4 — Run `uv run pytest packages/mcp/tests/test_temporal_middleware.py packages/mcp/tests/test_audit.py -x -v` — all 13 tests (6 middleware + 7 audit) MUST pass.

    Step 5 — Implement the meta-test in `packages/mcp/tests/test_meta_temporal_bypass_guard.py`:

    ```python
    """META-TEST: structural anti-bypass guard for temporal safety.

    Per CONTEXT.md MCP-04 lock + RESEARCH.md §I.1 pitfall: a future tool author
    might add a tool to READ_TOOLS without giving it `as_of: datetime` — silently
    bypassing the middleware enforcement (middleware checks args, but a tool
    without as_of in its signature means the agent has no way to pass it).

    This test walks the live FastMCP tool registry AT IMPORT TIME and asserts
    every tool in TemporalSafetyMiddleware.READ_TOOLS has the required `as_of`
    parameter with no default. CI enforces this on every PR.
    """

    import inspect
    from datetime import datetime

    import pytest

    from tradewinds_mcp.server import mcp
    from tradewinds_mcp.temporal_middleware import TemporalSafetyMiddleware


    def test_no_read_tool_lacks_as_of():
        # FastMCP exposes registered tools via _tool_manager._tools.
        # If the internal API name changes between mcp SDK versions, update here.
        tools = mcp._tool_manager._tools  # dict[str, Tool-like]
        violators = []
        for tool_name in TemporalSafetyMiddleware.READ_TOOLS:
            if tool_name not in tools:
                violators.append(f"{tool_name}: not registered as a @mcp.tool() — does the server module register it?")
                continue
            tool = tools[tool_name]
            # The tool's underlying function lives at .fn (FastMCP convention as of mcp>=1.27).
            fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
            assert fn is not None, f"{tool_name}: cannot resolve underlying function"
            sig = inspect.signature(fn)
            if "as_of" not in sig.parameters:
                violators.append(f"{tool_name}: missing required `as_of` parameter")
                continue
            param = sig.parameters["as_of"]
            if param.default is not inspect.Parameter.empty:
                violators.append(f"{tool_name}: `as_of` has a default ({param.default!r}); must be required")
            if param.annotation is inspect.Parameter.empty:
                violators.append(f"{tool_name}: `as_of` has no type annotation; should be `datetime`")
        assert not violators, "Temporal-safety bypass guard FAILED:\n  - " + "\n  - ".join(violators)
    ```

    NOTE: this test depends on Task 1.5's `server.py` registering the 5 tools. Until Task 1.5 lands, this test will fail on import. That's intentional — it commits as part of this task (RED for now), then goes GREEN once Task 1.5 ships. Document in the test's docstring that the test order is `1.4 RED → 1.5 GREEN`.

    Step 6 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Commit (GREEN for tests 1-13; meta-test still RED until Task 1.5): `feat(phase-5): TemporalSafetyMiddleware + AuditLogger + meta-bypass-guard test (MCP-04 + MCP-06 GREEN)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_temporal_middleware.py packages/mcp/tests/test_audit.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/src/tradewinds_mcp/temporal_middleware.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/audit.py` returns 0
    - `grep -c "class TemporalSafetyMiddleware" packages/mcp/src/tradewinds_mcp/temporal_middleware.py` returns 1
    - `grep -c "frozenset({\"query\", \"ingest\"})" packages/mcp/src/tradewinds_mcp/temporal_middleware.py` returns 1
    - `grep -c "raise ToolError" packages/mcp/src/tradewinds_mcp/temporal_middleware.py` returns ≥ 1
    - `grep -c "sort_keys=True" packages/mcp/src/tradewinds_mcp/audit.py` returns 1 (Pitfall I.3 mitigation)
    - `grep -c "threading.Lock" packages/mcp/src/tradewinds_mcp/audit.py` returns 1 (concurrent-write safety)
    - `grep -c "audit-{now_iso}-{pid}" packages/mcp/src/tradewinds_mcp/audit.py` returns 1 (per-instance file naming per CONTEXT.md)
    - `grep -c "caller_identity" packages/mcp/src/tradewinds_mcp/audit.py` returns ≥ 2 (param + entry field)
    - `grep -c "encode(\"utf-8\")" packages/mcp/src/tradewinds_mcp/temporal_middleware.py` returns 1 (RESEARCH.md §D.3 — UTF-8 encoding locked for replay determinism)
    - `grep -c "stream=sys.stderr\\|file=sys.stderr" packages/mcp/src/tradewinds_mcp/temporal_middleware.py` returns ≥ 1 (Pitfall I.6 — never stdout)
    - `uv run pytest packages/mcp/tests/test_temporal_middleware.py packages/mcp/tests/test_audit.py -x -v` exits 0 with all 13 tests passing
    - Meta-test file `packages/mcp/tests/test_meta_temporal_bypass_guard.py` exists; running it standalone fails with `ImportError` (server.py not built yet — green in Task 1.5)
    - Three commits on the branch (RED + GREEN + meta-test)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    TemporalSafetyMiddleware rejects missing/None as_of for read tools, calls audit logger on success. AuditLogger writes per-instance sort_keys-stable JSONL with caller_identity. Meta-test scaffolding is in place (will go green when Task 1.5 registers the tools). 13 tests pass; meta-test pending.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 1.5: server.py + 5 tool stubs + TOON determinism test + in-process FastMCP integration test (RED tests FIRST)</name>
  <files>packages/mcp/src/tradewinds_mcp/server.py, packages/mcp/src/tradewinds_mcp/tools/__init__.py, packages/mcp/src/tradewinds_mcp/tools/query.py, packages/mcp/src/tradewinds_mcp/tools/ingest.py, packages/mcp/src/tradewinds_mcp/tools/list_sources.py, packages/mcp/src/tradewinds_mcp/tools/describe_source.py, packages/mcp/src/tradewinds_mcp/tools/get_schema.py, packages/mcp/tests/test_server_smoke.py, packages/mcp/tests/test_toon_deterministic.py, packages/mcp/tests/test_in_process_query.py</files>
  <implements>MCP-01 (server runs + all 5 tools registered), MCP-07 (get_schema reads Phase 2 registry), MCP-08 (query stub calls Dataset.at_time)</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§A — full server skeleton at lines 657-701; §A.3 — transport configuration; §A.4 — in-process FastMCP testing pattern via run_server_async; §D.3 — TOON determinism is mandatory; §I.5 — pitfall: TOON not deterministic in Phase 2 lifted code, fix in Wave 1)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — server returns Pydantic envelope with `data: str` TOON-encoded; logging.basicConfig stream=sys.stderr; never print() to stdout)
    - packages/core/src/tradewinds/core/schemas/__init__.py (Phase 2 — eager-registered SchemaRegistration; get_schema reads from here)
    - packages/core/src/tradewinds/core/temporal/dataset.py (Task 1.2 — Dataset.at_time is the canonical filter call in query tool body)
    - packages/core/src/tradewinds/core/formats/toon.py (Phase 2 — serializer signature; this task TESTS its determinism)
    - packages/mcp/src/tradewinds_mcp/temporal_middleware.py + audit.py + envelopes.py + caller_context.py (Tasks 1.3 + 1.4 — wire them in)
    - fastmcp.utilities.tests source (`from fastmcp.utilities.tests import run_server_async, run_server_in_process` — RESEARCH.md §A.4)
  </read_first>
  <behavior>
    Tests to write FIRST:

    `packages/mcp/tests/test_server_smoke.py` (4 tests):

    1. `test_server_module_imports`: `from tradewinds_mcp.server import mcp` succeeds; `mcp.name == "tradewinds"`.
    2. `test_five_tools_registered`: `len(mcp._tool_manager._tools) == 5`; the tool names are exactly `{"query", "ingest", "list_sources", "describe_source", "get_schema"}`.
    3. `test_temporal_middleware_attached`: `any(isinstance(m, TemporalSafetyMiddleware) for m in mcp._middleware)` — true. The middleware is attached at module-import time.
    4. `test_main_reads_transport_env_var`: spy on `mcp.run`; call `from tradewinds_mcp.server import main; with patch.dict(os.environ, {"TRADEWINDS_MCP_TRANSPORT": "stdio"}): main()`. Assert `mcp.run` called with `transport="stdio"`. Also test the default: with the env var unset, `mcp.run` called with `transport="stdio"` (the default). (Don't actually start the server in tests — mock `mcp.run`.)

    `packages/mcp/tests/test_toon_deterministic.py` (1 critical test):

    1. `test_toon_serializer_byte_deterministic_100_runs`: Construct a DataFrame with 50 rows containing one column of each tricky dtype — `tz-aware DatetimeIndex` (or column), `pd.Int64` nullable with NAs, `pd.Float64` nullable with NAs, `pd.CategoricalDtype` with 5 categories not in alphabetical order, plus plain `object` strings. Serialize via `from tradewinds.core.formats.toon import serialize`. Run 100 times in a loop; collect each output's `hashlib.sha256(out.encode("utf-8")).hexdigest()`. Assert all 100 hashes are identical. If they're not, FAIL with a message listing how many distinct hashes were observed and which columns most likely caused drift.

    `packages/mcp/tests/test_in_process_query.py` (2 tests):

    1. `test_in_process_get_schema_returns_observation_schema`: Use `run_server_async` to spin up the server in-process. Open a `ClientSession`. Call `await session.call_tool("get_schema", {"schema_id": "schema.observation.v1"})`. Assert the result's `.content` (or `.structured_content` per FastMCP convention) contains the canonical observation schema with at least the field names registered by Phase 2.
    2. `test_in_process_query_envelope_shape`: Call `await session.call_tool("query", {"source_id": "_placeholder", "as_of": "2024-01-15T00:00:00Z", "filters": {}})`. Assert the response has `format == "toon"`, `data` is a string (may be empty placeholder TOON), `schema_id` is a string, `audit_id` matches `audit-.*-\d{6}`. This is the end-to-end smoke that the middleware + envelope + audit pipeline works in-process.

    Run `uv run pytest packages/mcp/tests/test_server_smoke.py packages/mcp/tests/test_toon_deterministic.py packages/mcp/tests/test_in_process_query.py -x` — MUST fail. Commit: `test(phase-5): add failing server smoke + TOON determinism + in-process integration tests (MCP-01/07/08 RED)`.
  </behavior>
  <action>
    Step 1 — Write the 7 tests above. Commit RED.

    Step 2 — Implement the 5 tool stub files. Each lives in `packages/mcp/src/tradewinds_mcp/tools/`. They are wired into `server.py` via import side-effects (FastMCP's `@mcp.tool()` decorator registers on import).

    `packages/mcp/src/tradewinds_mcp/tools/query.py`:

    ```python
    """query tool — point-in-time DataFrame return via Dataset.at_time(as_of).

    Wave 1: stub returns an empty placeholder DataFrame from a hard-coded
    `_placeholder` catalog entry. Wave 2 wires this to the real per-source
    YAML catalog. The middleware + audit + envelope plumbing IS LIVE in Wave 1.
    """

    from __future__ import annotations

    from datetime import datetime
    import pandas as pd

    from tradewinds.core.formats import toon as toon_fmt
    from tradewinds.core.temporal import Dataset

    from ..envelopes import QueryResponse
    from .._registry import mcp_instance, audit_logger  # injected by server.py at module load


    def register(mcp, audit) -> None:
        """Register the query tool against the given FastMCP instance.

        Called once from server.py at import time.
        """

        @mcp.tool()
        async def query(
            source_id: str,
            as_of: datetime,
            filters: dict | None = None,
            format: str = "toon",
        ) -> QueryResponse:
            """Return rows from source_id knowable at as_of.

            Temporal safety is server-enforced via the TemporalSafetyMiddleware
            (cannot be bypassed). The `as_of` parameter is REQUIRED.
            """
            # Wave 1 stub: empty placeholder DataFrame.
            # Wave 2: catalog.lookup(source_id).fetch(filters=filters)
            df = pd.DataFrame({
                "event_time": pd.Series([], dtype="datetime64[ns, UTC]"),
                "knowledge_time": pd.Series([], dtype="datetime64[ns, UTC]"),
            })
            ds = Dataset(df, schema_id="schema.observation.v1")
            filtered = ds.at_time(as_of)
            toon_str = toon_fmt.serialize(filtered)
            audit_id = audit.log(
                tool="query",
                source=source_id,
                as_of=as_of,
                rows=len(filtered),
                hash=__import__("hashlib").sha256(toon_str.encode("utf-8")).hexdigest(),
                schema_id="schema.observation.v1",
            )
            return QueryResponse(
                format="toon",
                data=toon_str,
                schema_id="schema.observation.v1",
                audit_id=audit_id,
            )
    ```

    `packages/mcp/src/tradewinds_mcp/tools/ingest.py`: similar stub returning `IngestResponse(rows_ingested=0, ...)`; signature `ingest(source_id: str, as_of: datetime, filters: dict | None = None)`; same middleware enforcement.

    `packages/mcp/src/tradewinds_mcp/tools/list_sources.py`:

    ```python
    """list_sources tool — Wave 1 returns placeholder list; Wave 2 wires real catalog."""
    from ..envelopes import ListSourcesResponse

    def register(mcp, audit) -> None:
        @mcp.tool()
        async def list_sources() -> ListSourcesResponse:
            """Return source IDs available in the catalog."""
            # Wave 2: catalog.all_source_ids()
            return ListSourcesResponse(sources=["_placeholder"])
    ```

    `packages/mcp/src/tradewinds_mcp/tools/describe_source.py`: stub returning a `DescribeSourceResponse` with empty `catalog_entry={}` for `_placeholder`; raises `SourceUnavailableError` (Phase 2) for unknown source_ids — surfaces as JSON-RPC error per the TradewindsError.to_dict() contract (MCP-07 reuse).

    `packages/mcp/src/tradewinds_mcp/tools/get_schema.py`:

    ```python
    """get_schema tool — REAL Wave 1 implementation; reads Phase 2 schema registry."""

    from tradewinds.core.exceptions import SchemaValidationError
    from tradewinds.core.schemas import REGISTRY  # Phase 2 eager-registered dict-like

    from ..envelopes import SchemaResponse


    def register(mcp, audit) -> None:
        @mcp.tool()
        async def get_schema(schema_id: str) -> SchemaResponse:
            """Return the JSON Schema for the named schema_id.

            Resolves against the Phase 2 canonical schema registry
            (schema.observation.v1, schema.forecast.iem_mos.v1, schema.settlement.cli.v1).
            """
            if schema_id not in REGISTRY:
                raise SchemaValidationError(
                    f"Unknown schema_id '{schema_id}'. "
                    f"Available: {sorted(REGISTRY.keys())}"
                )
            schema_obj = REGISTRY[schema_id]
            return SchemaResponse(
                schema_id=schema_id,
                schema_json=schema_obj.to_json_schema() if hasattr(schema_obj, "to_json_schema") else dict(schema_obj),
            )
    ```

    (Adapt `REGISTRY` lookup to the actual Phase 2 API — verify by reading `packages/core/src/tradewinds/core/schemas/__init__.py` after Phase 2 ships.)

    Step 3 — Implement `packages/mcp/src/tradewinds_mcp/server.py`:

    ```python
    """tradewinds-mcp server entry point.

    Builds the FastMCP instance, attaches TemporalSafetyMiddleware, registers
    the 5 tools, and exposes a main() entry that reads TRADEWINDS_MCP_TRANSPORT
    (defaults to stdio). The transport env-var is the v0.3 hosted-mode seam
    (RESEARCH.md §A.3 + §F.3).

    Logging configured to stderr ONLY (Pitfall I.6 — stdout breaks JSON-RPC framing).
    """

    from __future__ import annotations

    import logging
    import os
    import sys

    from mcp.server.fastmcp import FastMCP

    from .audit import AuditLogger
    from .temporal_middleware import TemporalSafetyMiddleware
    from .tools import query, ingest, list_sources, describe_source, get_schema

    # Pitfall I.6 — stdio servers MUST NOT write to stdout
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Module-level singletons
    mcp = FastMCP("tradewinds")
    _audit = AuditLogger()

    # Attach middleware BEFORE tool registration so the bypass-guard meta-test
    # observes the live state at import time.
    mcp.add_middleware(TemporalSafetyMiddleware(audit_logger=_audit))

    # Register the 5 tools (side-effect: each register() calls @mcp.tool()).
    query.register(mcp, _audit)
    ingest.register(mcp, _audit)
    list_sources.register(mcp, _audit)
    describe_source.register(mcp, _audit)
    get_schema.register(mcp, _audit)


    def main() -> None:
        """Console-script entry point. Reads transport from TRADEWINDS_MCP_TRANSPORT env var."""
        transport = os.environ.get("TRADEWINDS_MCP_TRANSPORT", "stdio")
        # Future v0.3 hosted-mode: transport='http' branch wires host/port from env vars.
        # For v0.2, stdio is the only supported transport.
        if transport != "stdio":
            raise NotImplementedError(
                f"transport={transport!r} is not supported in v0.2 (only 'stdio'). "
                f"Hosted mode (HTTP transport) ships in v0.3."
            )
        mcp.run(transport=transport)


    if __name__ == "__main__":
        main()
    ```

    `packages/mcp/src/tradewinds_mcp/tools/__init__.py`:

    ```python
    """Tool modules — each exposes a `register(mcp, audit)` function called from server.py."""
    from . import query, ingest, list_sources, describe_source, get_schema
    __all__ = ["query", "ingest", "list_sources", "describe_source", "get_schema"]
    ```

    Step 4 — Run `uv run pytest packages/mcp/tests/ -m "not live" -x -v` — all tests including the meta-test from Task 1.4 + the 7 new tests MUST pass.

    Step 5 — If `test_toon_serializer_byte_deterministic_100_runs` FAILS, surface to user with a count of distinct hashes + a column-by-column hypothesis (categorical reorder? dict-key reorder?). DO NOT silently patch TOON without user input — per CONTEXT.md, deterministic replay is the core trust contract for MCP-09. The fix lives in `packages/core/src/tradewinds/core/formats/toon.py` (Phase 2 surface), not at the MCP layer.

       Likely fix path (if needed): sort dict keys before serializing; sort categorical levels alphabetically before emitting; explicit `df.sort_index()` on the input. Each is a 1-2 line change in `toon.py`. After fix, re-run all Phase 2 format roundtrip tests to ensure no regression.

    Step 6 — Confirm the META-TEST from Task 1.4 now passes (`test_no_read_tool_lacks_as_of`). Both `query` and `ingest` have `as_of: datetime` with no default per their signatures above.

    Step 7 — Run `uv run ruff check --fix .` + `uv run ruff format .`. Commit: `feat(phase-5): server.py + 5 tool stubs + TOON determinism + in-process integration (MCP-01/07/08 GREEN)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/ -m "not live" -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/src/tradewinds_mcp/server.py` returns 0
    - `grep -c 'mcp = FastMCP("tradewinds")' packages/mcp/src/tradewinds_mcp/server.py` returns 1
    - `grep -c "mcp.add_middleware(TemporalSafetyMiddleware" packages/mcp/src/tradewinds_mcp/server.py` returns 1
    - `grep -c "TRADEWINDS_MCP_TRANSPORT" packages/mcp/src/tradewinds_mcp/server.py` returns 1
    - `grep -c "stream=sys.stderr" packages/mcp/src/tradewinds_mcp/server.py` returns 1 (Pitfall I.6 mitigation)
    - `grep -c "register(mcp, _audit)" packages/mcp/src/tradewinds_mcp/server.py` returns 5 (one per tool)
    - `test -f packages/mcp/src/tradewinds_mcp/tools/query.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/tools/ingest.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/tools/list_sources.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/tools/describe_source.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/tools/get_schema.py` returns 0
    - `grep -c "@mcp.tool()" packages/mcp/src/tradewinds_mcp/tools/*.py` returns 5
    - `grep -c "Dataset(df, schema_id=" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1
    - `grep -c "ds.at_time(as_of)" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1
    - `grep -c "from tradewinds.core.formats import toon" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1
    - `grep -c "from tradewinds.core.schemas import" packages/mcp/src/tradewinds_mcp/tools/get_schema.py` returns 1
    - `uv run pytest packages/mcp/tests/ -m "not live" -x -v` exits 0 with all tests passing INCLUDING `test_no_read_tool_lacks_as_of` and `test_toon_serializer_byte_deterministic_100_runs`
    - If TOON determinism test fails: user-confirmed fix path applied; re-run green
    - 3 commits on the branch (RED + GREEN + possible TOON-fix follow-up)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    Server.py builds a FastMCP instance, attaches TemporalSafetyMiddleware, registers 5 tools, exposes main() reading TRADEWINDS_MCP_TRANSPORT. All 5 tools have `@mcp.tool()` decoration. The query tool wires through Dataset.at_time + toon.serialize + audit.log. get_schema reads Phase 2 registry. META-TEST green. TOON determinism test green (with TOON fix in Phase 2 surface if discovered nondeterministic). In-process integration test green.
  </done>
</task>

<task type="auto">
  <name>Task 1.6: CONTRIBUTING.md + Phase 5 threat-model documentation + wheel-build verification</name>
  <files>packages/mcp/CONTRIBUTING.md, packages/mcp/THREAT-MODEL.md</files>
  <implements>Wave 1 closeout — durable engineering hygiene</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§I — all 8 pitfalls; CONTRIBUTING.md memorializes each as a "do/don't" rule)
    - .planning/phase-05-mcp-data-platform/CONTEXT.md (decisions — auth model, audit log, temporal middleware lock)
    - .planning/REVIEW-DISCIPLINE.md (2-reviewer loop applies; reviewer prompt rules)
    - packages/mcp/src/tradewinds_mcp/temporal_middleware.py (Task 1.4 — referenced in CONTRIBUTING rule "all temporal validation lives in temporal_middleware.py")
    - packages/mcp/src/tradewinds_mcp/server.py (Task 1.5 — referenced in CONTRIBUTING rule "stderr only; never print() to stdout")
  </read_first>
  <action>
    Step 1 — Create `packages/mcp/CONTRIBUTING.md`:

    ```markdown
    # Contributing to tradewinds-mcp

    Local-first MCP server. Five tools. Server-enforced temporal safety. Audit log JSONL.

    ## Five hard rules

    ### Rule 1: All temporal validation lives in `temporal_middleware.py`. NOT in tool bodies.
    Tools accept `as_of: datetime` typed; they DO NOT validate (the middleware does, structurally).
    Adding `if as_of is None: raise` inside a tool body is a code-review reject per RESEARCH.md §I.1.

    ### Rule 2: Never print() to stdout. Stdio server framing breaks if you do.
    Use `logging.getLogger(__name__).info(...)`. Logging is configured for stderr in server.py.
    If a test asserts stdout content, the production server will corrupt JSON-RPC. CI runs
    `grep -rn "^\\s*print(" packages/mcp/src/` and fails the build if any matches found.
    See RESEARCH.md §I.6.

    ### Rule 3: New read tools (returning rows) MUST be added to `TemporalSafetyMiddleware.READ_TOOLS`
    AND have `as_of: datetime` with no default in their signature.
    The META-TEST `test_no_read_tool_lacks_as_of` enforces this on every PR.

    ### Rule 4: Audit log entries are alphabetized via `json.dumps(d, sort_keys=True)`.
    Do NOT bypass — Pitfall I.3 (Pydantic / Python patch upgrades can reorder dict keys).
    The hash field is computed externally (by the tool body) over the TOON `data` field encoded
    UTF-8 — `sha256(data.encode("utf-8")).hexdigest()`. Encoding is pinned; do not change.

    ### Rule 5: Tool return type is a Pydantic envelope from `envelopes.py` with `data: str`.
    Never return raw `pd.DataFrame`. Never nest TOON inside a dict — flat envelope (Pitfall I.2).
    The TOON content's schema is described by `schema_id` and resolvable via `get_schema(schema_id)`.

    ## Two-reviewer loop (per .planning/REVIEW-DISCIPLINE.md)
    Every PR runs codex `high` + python-architect. Never-skip applies to packages/mcp/ (new
    distribution, MCP-04 trust-architecture surface).

    ## Local dev quickstart
    ```bash
    uv sync
    uv run pytest packages/mcp/tests/ -m "not live" -q
    uv run tradewinds-mcp-server  # stdio mode
    ```
    Test against Claude Desktop by adding the JSON snippet from README.md to your Claude Desktop config.
    ```

    Step 2 — Create `packages/mcp/THREAT-MODEL.md`. Pull from the `<threat_model>` block below into this file as the durable team-facing version. This is the long-form companion to PLAN-01's threat register — future PRs touching `packages/mcp/` reference this for trust boundary updates.

    Step 3 — Run the wheel-build verification end-to-end:

    ```bash
    uv build packages/mcp/
    # Inspect contents
    unzip -l packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl
    # Verify METADATA Requires-Dist includes pinned versions per CLAUDE.md PKG-03
    unzip -p packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl tradewinds_mcp-0.2.0.dist-info/METADATA | grep -E "Requires-Dist"
    ```

    Expected: `Requires-Dist: tradewinds>=0.2.0,<0.3`, `Requires-Dist: mcp>=1.27,<2.0`, `Requires-Dist: pydantic>=2.7,<3.0`, `Requires-Dist: pyyaml>=6.0,<7`. If any range is wrong (e.g., `tradewinds` without explicit upper bound), fix `pyproject.toml` and rebuild.

    Step 4 — Confirm console-script entry: `uv run tradewinds-mcp-server --help` — should print FastMCP's auto-generated help or just start the stdio loop. (FastMCP may not have `--help`; in that case run with `printf '' | uv run tradewinds-mcp-server` and verify it doesn't crash on empty stdin.)

    Step 5 — Run final pre-merge gates:

    ```bash
    uv run pytest packages/mcp/tests/ -m "not live" -q
    uv run pytest -m "not live" -q  # full repo suite
    uv run ruff check . && uv run ruff format --check .
    uv run pre-commit run --all-files
    # Static guard: no print() in production code
    grep -rn "^\\s*print(" packages/mcp/src/ && echo "FAIL: print() in production" || echo "OK"
    ```

    All green.

    Step 6 — Commit: `docs(phase-5): CONTRIBUTING + THREAT-MODEL + wheel verification (PLAN-01 closeout)`.
  </action>
  <verify>
    <automated>test -f packages/mcp/CONTRIBUTING.md && test -f packages/mcp/THREAT-MODEL.md && uv build packages/mcp/ && unzip -p packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl tradewinds_mcp-0.2.0.dist-info/METADATA | grep -E "Requires-Dist: tradewinds>=0.2.0,<0.3" && unzip -p packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl tradewinds_mcp-0.2.0.dist-info/METADATA | grep -E "Requires-Dist: mcp>=1.27,<2.0" && uv run pytest packages/mcp/tests/ -m "not live" -q && grep -rn "^\s*print(" packages/mcp/src/; test $? -eq 1 && uv run pre-commit run --all-files</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/CONTRIBUTING.md` returns 0
    - `test -f packages/mcp/THREAT-MODEL.md` returns 0
    - `grep -c "All temporal validation lives in .temporal_middleware.py." packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `grep -c "Never print() to stdout" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `grep -c "READ_TOOLS" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `grep -c "sort_keys=True" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `grep -c "data: str" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `uv build packages/mcp/` exits 0
    - `unzip -p packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl tradewinds_mcp-0.2.0.dist-info/METADATA | grep -c "Requires-Dist: tradewinds>=0.2.0,<0.3"` returns 1
    - `unzip -p packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl tradewinds_mcp-0.2.0.dist-info/METADATA | grep -c "Requires-Dist: mcp>=1.27,<2.0"` returns 1
    - `unzip -p packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl tradewinds_mcp-0.2.0.dist-info/METADATA | grep -c "Requires-Dist: pydantic>=2.7,<3.0"` returns 1
    - `unzip -p packages/mcp/dist/tradewinds_mcp-0.2.0-py3-none-any.whl tradewinds_mcp-0.2.0.dist-info/METADATA | grep -c "Requires-Dist: pyyaml>=6.0,<7"` returns 1
    - `grep -rn "^\s*print(" packages/mcp/src/` returns exit 1 (no print() in production)
    - `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0
    - `uv run pytest -m "not live" -q` exits 0 (full repo suite still green)
    - `uv run ruff check . && uv run ruff format --check .` exits 0
    - `uv run pre-commit run --all-files` exits 0
    - One commit on the branch
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    CONTRIBUTING.md memorializes 5 hard rules from RESEARCH.md pitfalls. THREAT-MODEL.md mirrors the plan's threat register for ongoing team reference. Wheel build verified; Requires-Dist correct. No print() statements in production code.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1.7: 2-reviewer loop + pre-merge gate + merge to main</name>
  <files>n/a (verification only)</files>
  <implements>Wave 1 closeout — REVIEW-DISCIPLINE.md 2-reviewer loop + merge gate</implements>
  <read_first>
    - .planning/REVIEW-DISCIPLINE.md (2-reviewer loop, never-skip list, severity gate)
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§I.5 — TOON determinism is a HARD prerequisite; if it failed in Task 1.5, escalate)
    - Plan-level success criteria below
  </read_first>
  <what-built>
    Tasks 1.1–1.6 complete: `packages/mcp/` distribution scaffolded; `tradewinds.core.temporal.Dataset` shipped; CallerContext + 5 envelopes; TemporalSafetyMiddleware + AuditLogger; server.py + 5 tool stubs; META-TEST + TOON determinism test + in-process integration test all green; CONTRIBUTING.md + THREAT-MODEL.md committed; wheel build clean.
  </what-built>
  <how-to-verify>
    **Step A — Final test pass:**

    ```bash
    uv run pytest packages/mcp/tests/ -m "not live" -v
    uv run pytest -m "not live" -q          # full repo suite — confirm no Phase 2 regression
    ```

    Expected: all green. Critical tests to eyeball in output:
    - `test_no_read_tool_lacks_as_of` (META-TEST) — PASS
    - `test_toon_serializer_byte_deterministic_100_runs` — PASS
    - `test_in_process_query_envelope_shape` — PASS
    - `test_audit_logger_sort_keys_alphabetized` — PASS

    **Step B — Branch coverage check on tradewinds.core:**

    ```bash
    uv run pytest --cov=tradewinds.core --cov-branch packages/core/tests/ -q | grep TOTAL
    ```

    Expected: ≥ 90% per CLAUDE.md (Dataset is core, must hold the bar).

    **Step C — Branch coverage check on tradewinds_mcp (new floor: 85% per Phase 5 deep_work_rules):**

    ```bash
    uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q | grep TOTAL
    ```

    Expected: ≥ 85%.

    **Step D — Run the 2-reviewer loop per REVIEW-DISCIPLINE.md:**

    ```bash
    codex review --base main -c 'model_reasoning_effort="high"'
    # AND in parallel
    # Python Architect (Claude general-purpose agent, "Senior Python Architect" persona)
    ```

    Severity gate: CRITICAL or HIGH only. PASS or REVISE verdict. Reviewer prompts must explicitly reference:
    - CONTEXT.md MCP-04 lock (temporal middleware is structural)
    - RESEARCH.md §I.1, §I.2, §I.3, §I.5, §I.6 (the 5 pitfalls hard-mitigated in Wave 1)
    - The META-TEST as the long-term anti-bypass guard

    If REVISE: fix on the branch, re-run both reviewers. Loop until PASS x2 or 3 iterations (escalate to user on 3).

    **Step E — Merge to main:**

    ```bash
    git checkout main
    git merge --no-ff phase-5/wave-1/mcp-server-skeleton -m "Merge phase-5/wave-1/mcp-server-skeleton: MCP server foundation (MCP-01 partial + MCP-04 + MCP-06 + MCP-07 + MCP-08) [reviewer loop: PASS x2 iter N]"
    ```

    **Step F — Confirm to user:**

    (1) All green: "Wave 1 merged to `main`. tradewinds-mcp distribution exists with FastMCP server skeleton, 5 tool stubs, server-enforced temporal middleware (anti-bypass meta-test green), append-only audit JSONL, CallerContext v0.3 auth seam, Dataset point-in-time API. TOON determinism verified. Wave 2 (catalog format + per-source YAML + 7 weather entries) is unblocked. Type `approved` to continue."

    (2) TOON nondeterminism discovered: "TOON serializer is nondeterministic — N distinct hashes in 100 runs. Likely cause: [categorical reorder | dict key ordering | datetime resolution drift]. Proposed fix in `packages/core/src/tradewinds/core/formats/toon.py`: [describe]. This is a Phase 2 surface fix, not an MCP-layer fix. Approve fix or revisit Phase 2 PLAN."

    (3) Reviewer REVISE: "Codex [or python-architect] flagged [CRITICAL|HIGH] issue: [summary]. Fix on the branch and re-run the loop."
  </how-to-verify>
  <resume-signal>
    Type `approved` once Wave 1 is merged to `main` (PLAN-02 is unblocked). Type `toon-fix` if TOON nondeterminism requires a Phase 2-surface patch. Type `revise` for reviewer-driven changes.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Agent (MCP client) → tradewinds-mcp-server (stdio child process) | Inbound JSON-RPC tool calls; agent is untrusted (CONTEXT.md MCP-04 trust thesis: agents can lie to themselves about leakage; server cannot lie to a structural filter). |
| tradewinds-mcp-server → tradewinds.core (Phase 2 KnowledgeView + Validator + schemas) | In-process Python call; trust boundary for source-identity invariants. |
| tradewinds-mcp-server → audit.jsonl (filesystem) | Outbound write to `$HOME/.tradewinds/mcp-server/audit-*.jsonl`. Trust boundary if home dir is shared (rare; documented per-instance file mitigates contention). |
| FastMCP transport (stdio in v0.2) | Inbound: JSON-RPC frames on stdin; Outbound: JSON-RPC frames on stdout. Stdout corruption (Pitfall I.6) is a self-inflicted DoS — server crashes the client. |
| Local Python environment | Tools call into `tradewinds.core` + `tradewinds.weather` + `tradewinds.markets`; no additional auth (stdio mode inherits parent process env). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-5.1-01 | Tampering / Information Disclosure | Agent passes `as_of=None` or omits `as_of`, hoping to bypass temporal filter and read future data | mitigate | `TemporalSafetyMiddleware.on_call_tool` raises `ToolError` BEFORE the tool body runs. Tested by `test_middleware_rejects_missing_as_of` + `test_middleware_rejects_none_as_of`. The META-TEST `test_no_read_tool_lacks_as_of` ensures the structural guard cannot be silently weakened by a future tool author. |
| T-5.1-02 | Tampering | Future tool author adds new read tool to READ_TOOLS without `as_of: datetime` in signature | mitigate | META-TEST `test_no_read_tool_lacks_as_of` walks `mcp._tool_manager._tools` at CI time and asserts every READ tool has `as_of: datetime` with no default. CI gate blocks the PR. Documented in CONTRIBUTING.md Rule 3. |
| T-5.1-03 | Repudiation | Audit log is missing entries OR entries are reordered to hide a leakage event | mitigate | Append-only JSONL file (filename per-instance with timestamp + pid so cross-instance contention is eliminated); single `threading.Lock` for in-process concurrent writes; `sort_keys=True` so dict-iteration-order regressions cannot reorder fields silently (Pitfall I.3). Audit failure does NOT fail the tool (logged to stderr). |
| T-5.1-04 | Information Disclosure | Stdout corrupted by inadvertent `print()` in a tool, breaking JSON-RPC framing and leaking partial responses | mitigate | `logging.basicConfig(stream=sys.stderr)` at server entry; CONTRIBUTING.md Rule 2; CI grep `grep -rn "^\\s*print(" packages/mcp/src/` returns exit 1. Pitfall I.6 hard-defended. |
| T-5.1-05 | Tampering | TOON serializer is nondeterministic — agent gets different bytes for same query, breaking auditability (MCP-09) | mitigate | `test_toon_serializer_byte_deterministic_100_runs` runs 100 serializations of a tricky-dtype DataFrame at Wave 1 ship time; if not deterministic, fix lives in `tradewinds.core.formats.toon` (Phase 2 surface) BEFORE Wave 4 builds replay tests. Pitfall I.5 hard-defended. |
| T-5.1-06 | Information Disclosure | TOON content nested inside a structured envelope leaks a field a future Pydantic version auto-validates against an unexpected schema | mitigate | Flat envelope per Pitfall I.2: `QueryResponse.data: str` (the TOON string itself); structured fields live OUTSIDE `data`. `test_query_response_rejects_dataframe_data` enforces. |
| T-5.1-07 | Elevation of Privilege | v0.3 hosted mode ships and tools read `os.environ` directly, bypassing the `CallerContext` auth check | mitigate | RESEARCH.md §F.3 + CONTRIBUTING.md hint: tools NEVER read `os.environ`; all config flows through `CallerContext` populated by middleware. v0.2 enforcement is by convention + code review; v0.3 will add a lint rule. |
| T-5.1-08 | Denial of Service | Agent floods the server with `query` calls; each appends to audit log; disk fills | accept | v0.2 is local-first stdio (single user). Disk fill = local user problem, not multi-tenant exposure. v0.3+ hosted mode adds rate-limiting at the middleware layer (already a documented seam — middleware is the right surface). |
| T-5.1-09 | Tampering | Concurrent threads within one MCP server instance corrupt audit.jsonl with interleaved partial writes | mitigate | `AuditLogger._lock = threading.Lock()` guards the entire append; `test_audit_logger_concurrent_writes_dont_corrupt` runs 4 threads × 10 calls + asserts 40 valid JSON lines. |
| T-5.1-10 | Information Disclosure | Schema registry exposed via `get_schema(any_id)` lets agent enumerate schemas / probe internal IDs | accept | Schemas are public canonical definitions (already documented in Phase 2 PLAN); not sensitive. `get_schema(unknown_id)` raises `SchemaValidationError` with the list of available IDs — that's public info, not a leak. |
</threat_model>

<verification>
## Plan-Level Checks (auto + manual)

| Check | Command | Expected |
|-------|---------|----------|
| `packages/mcp/` distribution builds | `uv build packages/mcp/` | exit 0, wheel produced |
| No `tradewinds/__init__.py` collision in wheel | `unzip -l packages/mcp/dist/*.whl \| grep -c "^.*tradewinds/__init__.py$"` | 0 |
| `tradewinds_mcp/__init__.py` in wheel | `unzip -l packages/mcp/dist/*.whl \| grep -c "tradewinds_mcp/__init__.py"` | 1 |
| METADATA Requires-Dist correct | `unzip -p packages/mcp/dist/*.whl tradewinds_mcp-0.2.0.dist-info/METADATA \| grep -E "Requires-Dist"` | 4 lines (tradewinds, mcp, pydantic, pyyaml) all with explicit ranges |
| Dataset class exists in tradewinds.core | `python -c "from tradewinds.core.temporal import Dataset; print(Dataset.__name__)"` | "Dataset" |
| FastMCP server constructs | `python -c "from tradewinds_mcp.server import mcp; print(mcp.name)"` | "tradewinds" |
| 5 tools registered | `python -c "from tradewinds_mcp.server import mcp; print(sorted(mcp._tool_manager._tools.keys()))"` | `['describe_source', 'get_schema', 'ingest', 'list_sources', 'query']` |
| TemporalSafetyMiddleware attached | `python -c "from tradewinds_mcp.server import mcp; from tradewinds_mcp.temporal_middleware import TemporalSafetyMiddleware; print(any(isinstance(m, TemporalSafetyMiddleware) for m in mcp._middleware))"` | True |
| Full MCP tests | `uv run pytest packages/mcp/tests/ -m "not live" -v` | all passing |
| Full repo fast suite | `uv run pytest -m "not live" -q` | 0 failures |
| Branch coverage tradewinds.core | `uv run pytest --cov=tradewinds.core --cov-branch packages/core/tests/ -q` | ≥ 90% |
| Branch coverage tradewinds_mcp | `uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q` | ≥ 85% |
| Ruff lint | `uv run ruff check .` | 0 errors |
| Ruff format | `uv run ruff format --check .` | 0 diffs |
| Pre-commit hooks | `uv run pre-commit run --all-files` | exit 0 |
| No print() in production | `grep -rn "^\s*print(" packages/mcp/src/` | exit 1 (no matches) |
| 2-reviewer loop | (manual — codex high + python-architect) | both PASS |

## Static Regression Guards (grep-based)

```bash
# Pitfall I.1 — no tool body re-validates as_of
grep -rn "if as_of is None" packages/mcp/src/tradewinds_mcp/tools/ && echo "FAIL: as_of validation in tool body (belongs in middleware)" || echo "OK"

# Pitfall I.2 — no nested TOON inside dict envelopes
grep -rn "data: dict" packages/mcp/src/tradewinds_mcp/envelopes.py && echo "FAIL: envelope has data: dict (must be data: str)" || echo "OK"

# Pitfall I.3 — sort_keys=True is present in audit.py
grep -c "sort_keys=True" packages/mcp/src/tradewinds_mcp/audit.py | grep -E "^[1-9]" || echo "FAIL: audit.py missing sort_keys=True"

# Pitfall I.5 — TOON determinism test exists and passes
grep -c "def test_toon_serializer_byte_deterministic_100_runs" packages/mcp/tests/test_toon_deterministic.py | grep -E "^1$" || echo "FAIL: TOON determinism test missing"

# Pitfall I.6 — no print() to stdout
grep -rn "^\s*print(" packages/mcp/src/ && echo "FAIL: print() statement in production" || echo "OK"

# MCP-04 — meta-test exists
grep -c "def test_no_read_tool_lacks_as_of" packages/mcp/tests/test_meta_temporal_bypass_guard.py | grep -E "^1$" || echo "FAIL: meta-test missing"

# CONTEXT.md lock — caller_identity in audit log
grep -c "caller_identity" packages/mcp/src/tradewinds_mcp/audit.py | grep -E "^[2-9]|[0-9]{2}" || echo "FAIL: caller_identity not in audit.py"

# CONTEXT.md lock — TRADEWINDS_MCP_TRANSPORT seam in server.py
grep -c "TRADEWINDS_MCP_TRANSPORT" packages/mcp/src/tradewinds_mcp/server.py | grep -E "^1$" || echo "FAIL: TRADEWINDS_MCP_TRANSPORT seam missing"
```
</verification>

<success_criteria>
- [ ] MCP-01 (partial): `packages/mcp/` distribution exists; FastMCP server instance named "tradewinds"; 5 tools (`query`, `ingest`, `list_sources`, `describe_source`, `get_schema`) registered via `@mcp.tool()`; server runs via `tradewinds-mcp-server` console script with stdio transport.
- [ ] MCP-04 (full): `TemporalSafetyMiddleware` attached at module-import time; raises `ToolError` when `as_of` missing/None for read tools; structural — META-TEST `test_no_read_tool_lacks_as_of` proves no read tool can bypass.
- [ ] MCP-06 (full): `AuditLogger` writes append-only JSONL at `$HOME/.tradewinds/mcp-server/audit-<iso>-<pid>.jsonl`; entries are sort_keys-alphabetized; include `caller_identity` (v0.2: "local"); hash format `sha256(toon.encode("utf-8")).hexdigest()`; concurrent-write safe.
- [ ] MCP-07 (full): `get_schema(schema_id)` reads from Phase 2 `tradewinds.core.schemas.REGISTRY`; raises `SchemaValidationError` (with `.to_dict()` JSON-RPC payload per Phase 2) for unknown IDs.
- [ ] MCP-08 (full): `tradewinds.core.temporal.Dataset` ships with `.at_time(date)`, `.as_of(timestamp)`, `.between(start, end)`; `as_of == at_time`; tz-aware required; 10 unit tests green.
- [ ] CallerContext (`identity` / `caller_kind` / `granted_scopes`) shipped; v0.2 factory returns local; threaded through audit log — v0.3 hosted-mode seam in place.
- [ ] TOON determinism: `test_toon_serializer_byte_deterministic_100_runs` green (100 byte-identical serializations). If nondeterministic, fix landed in Phase 2 surface before merge.
- [ ] In-process FastMCP integration test green: `run_server_async` + `ClientSession`, call `get_schema` + `query`, validate envelope shape.
- [ ] CONTRIBUTING.md + THREAT-MODEL.md committed.
- [ ] Wheel verification: `Requires-Dist` includes `tradewinds>=0.2.0,<0.3` + `mcp>=1.27,<2.0` + `pydantic>=2.7,<3.0` + `pyyaml>=6.0,<7`.
- [ ] No `print()` in `packages/mcp/src/` (Pitfall I.6 mitigated).
- [ ] Full repo fast suite green: `uv run pytest -m "not live" -q` exits 0.
- [ ] Branch coverage `tradewinds.core` ≥ 90%; `tradewinds_mcp` ≥ 85%.
- [ ] 2-reviewer loop (codex `high` + python-architect) PASS x2 in ≤ 3 iterations.
- [ ] No `--no-verify` used at any commit boundary.
- [ ] Branch `phase-5/wave-1/mcp-server-skeleton` merged to `main` via `git merge --no-ff`.
</success_criteria>

<output>
After completion, create `.planning/phase-05-mcp-data-platform/05-01-SUMMARY.md` documenting:

- All 5 MCP-XX requirements (MCP-01 partial / MCP-04 / MCP-06 / MCP-07 / MCP-08) shipped with the code that implements each
- TOON determinism verdict (PASS / required Phase 2 fix / count of distinct hashes if it failed)
- META-TEST status (green at merge)
- Wheel build outputs (filename, size, METADATA Requires-Dist excerpt)
- Coverage numbers: tradewinds.core branch %, tradewinds_mcp branch %
- 2-reviewer loop verdict (PASS x2 iteration N)
- Commit hashes on `phase-5/wave-1/mcp-server-skeleton` (one per task RED + GREEN)
- Merge commit hash on `main`
- Time spent (Claude execution wall time + human pre-merge verification time)
- Downstream signals for Wave 2: server skeleton stable; 5 tools registered as stubs; catalog wiring is the next layer; `_placeholder` source_id must be replaced by real per-source YAML files; `list_sources` / `describe_source` / `query` / `ingest` all expect catalog-backed dispatch.
</output>
