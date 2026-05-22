---
phase: 05-mcp-data-platform
plan: 05
type: execute
wave: 4
duration: "2-3 days Claude execution; parallel to PLAN-04 (lane F — tests + release) once Task 4.0 USER_DECISION_GATE resolves"
waves: 1
depends_on: [phase-05-mcp-data-platform/PLAN-04-second-vertical-macro]
branch_strategy: per-wave; one sub-branch off `main` (`phase-5/wave-4/integration-replay-release`); 2-reviewer loop (codex `high` + python-architect); merges to `main` after end-to-end JSON-RPC subprocess tests + deterministic-replay suite + v0.2.0 wheel build verification all pass; THIS PLAN IS THE v0.2.0 SHIP GATE
requirements:
  - MCP-01    # full — all 5 tools end-to-end via real JSON-RPC subprocess transport (Wave 1 in-process tests + Wave 4 subprocess tests = full coverage)
  - MCP-04    # re-run end-to-end — middleware enforcement verified via JSON-RPC (agent literally cannot bypass even when talking to a subprocess server)
  - MCP-06    # re-run end-to-end — auditable provenance verified over a real query session; audit JSONL entries match the JSON-RPC call sequence
  - MCP-09    # full — deterministic replay; same query + same cutoff = identical bytes; tested via property-based fixtures (Hypothesis)
autonomous: false   # Pre-merge requires manual: (a) v0.2.0 wheel build verification + METADATA inspection; (b) trusted-publishing dry-run rehearsal; (c) tag v0.2.0 only after user explicit confirmation
files_modified:
  # JSON-RPC subprocess integration tests
  - packages/mcp/tests/test_jsonrpc_subprocess_integration.py                         # NEW — uses fastmcp.utilities.tests.run_server_in_process; spawns real stdio server; calls all 5 tools end-to-end; verifies envelope shape, audit log, middleware enforcement, SchemaValidationError JSON-RPC payload for unknown source
  - packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py                            # NEW — agent passes as_of=None over JSON-RPC; server returns JSON-RPC error (NOT silent success); SchemaValidationError.to_dict() payload visible to client
  # Deterministic replay tests (MCP-09)
  - packages/mcp/tests/test_deterministic_replay.py                                   # NEW — same query + same as_of + same filters → identical TOON bytes; hash-stability over 10 repetitions; tested for weather (iem.archive) AND macro (alfred.archive — vintage-aware)
  - packages/mcp/tests/test_replay_audit_consistency.py                               # NEW — audit JSONL hash field matches sha256(toon_data) recomputed by the test; cross-instance replay using audit-log line as the spec
  - packages/mcp/tests/test_deterministic_replay_property.py                          # NEW — Hypothesis property test: for any (source_id, as_of, filters) in valid space, two consecutive calls produce identical bytes
  # Cross-vertical join allow-list enforcement (RESEARCH.md §I.8)
  - packages/mcp/src/tradewinds_mcp/_join_validator.py                                # NEW — checks that any cross-source join in a query filter is in the calling source's catalog `joins_to` allow-list; raises SchemaValidationError on undeclared joins
  - packages/mcp/tests/test_cross_vertical_join_rejection.py                          # NEW — query('iem.archive', filters={'join': {'source':'fred.archive', 'on':['x']}}) is REJECTED (not in iem.archive.yaml joins_to allow-list); audit log records 'joins_to=undeclared'
  # Release artifacts
  - CHANGELOG.md                                                                      # MODIFY — add `[v0.2.0]` section documenting MCP-01..MCP-10 deliverables (or NEW if file doesn't exist post-Phase-4)
  - packages/mcp/pyproject.toml                                                       # MODIFY — bump version to 0.2.0 (already there from PLAN-01; verify and update Release-Date classifier if needed)
  - packages/macro/pyproject.toml                                                     # MODIFY — version stays at 0.2.0
  - .github/workflows/release.yml                                                     # MODIFY (or NEW if Phase 4 didn't ship) — add tradewinds-mcp + tradewinds-macro to the trusted-publishing release workflow
  - .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md                   # NEW — pre-publish checklist documenting exact commands to run + verifications + sign-off
  # Coverage gate updates
  - .github/workflows/mcp-tests.yml                                                   # MODIFY — extend matrix to include macro test runs alongside mcp tests; coverage bar stays at 85% mcp + 80% macro
must_haves:
  truths:
    - "`test_jsonrpc_subprocess_all_five_tools_e2e`: spawns the FastMCP server via `run_server_in_process` (subprocess + stdio JSON-RPC); ClientSession calls each of `list_sources` / `describe_source` / `query` / `ingest` / `get_schema` against a real subprocess; each returns a well-shaped envelope per Wave 1 Pydantic models."
    - "`test_jsonrpc_temporal_safety_e2e_missing_as_of`: agent submits `query` JSON-RPC request without `as_of`; server responds with JSON-RPC error envelope whose body matches `TradewindsError.to_dict()` shape from Phase 2 — class name = 'ToolError' (or `SchemaValidationError` if the middleware wraps differently); message contains 'as_of' and 'temporal safety'."
    - "`test_jsonrpc_get_schema_returns_phase2_schema`: subprocess query for `schema.observation.v1` returns the canonical Phase 2 schema; field names match Phase 2 ColumnSpec list."
    - "`test_deterministic_replay_same_bytes_identical_hash_iem`: call `query('iem.archive', as_of=datetime(2024,1,15,tzinfo=UTC), filters={'station':'KNYC'})` twice (in-process or subprocess); both return TOON `data` strings; `sha256(a.encode('utf-8')) == sha256(b.encode('utf-8'))`. RESEARCH.md §D.3 idiom verbatim."
    - "`test_deterministic_replay_same_bytes_identical_hash_alfred`: same for `query('alfred.archive', as_of=datetime(2024,3,15,tzinfo=UTC), filters={'series_id':'CPIAUCSL'})` — vintage-aware case; same as_of always picks same vintages."
    - "`test_deterministic_replay_audit_hash_matches_recomputed`: read the audit.jsonl entry for a query; re-compute `sha256(toon_data.encode('utf-8'))` from the returned envelope; equal to the stored hash. Replay can be reconstructed from the audit log alone."
    - "`test_deterministic_replay_property` (Hypothesis): `@given(source_id=sampled_from(['iem.archive','alfred.archive']), as_of=datetimes(min_value=..., max_value=..., timezones=just(UTC)))`; call query twice; bytes identical. Bounded date range to avoid Hypothesis shrinking pathology per Phase 2 CORE-08 pattern."
    - "`test_jsonrpc_cross_vertical_join_rejection`: query with a join filter referencing a source NOT in the catalog's `joins_to` allow-list raises a JSON-RPC error with `joins_to=undeclared` info; audit log records the rejected attempt (RESEARCH.md §I.8 pitfall mitigation)."
    - "`packages/mcp/tests/test_jsonrpc_subprocess_integration.py` runs in CI (`uv run pytest packages/mcp/tests/test_jsonrpc_subprocess_integration.py -m 'not live' -q` exits 0). NOTE: subprocess tests are SLOWER than in-process tests (~100ms per spawn per RESEARCH.md §A.4); the in-process tests from Wave 1 stay as the fast pyramid; subprocess tests run on every PR but are bounded to ≤ 6 tests."
    - "CHANGELOG.md has a `[v0.2.0]` section listing all 10 MCP-XX requirements as 'Added' + the new packages (`tradewinds-mcp`, `tradewinds-macro`) under 'Added' + dependency bumps (`mcp>=1.27,<2.0`) under 'Changed' + the migration note that Phase 2 surface added `tradewinds.core.temporal.Dataset` under 'Added'."
    - "`.github/workflows/release.yml` is configured to publish 5 PyPI distributions on v0.2.0 tag: tradewinds, tradewinds-weather, tradewinds-markets (carried from Phase 4), PLUS tradewinds-mcp, tradewinds-macro. Each via trusted publishing (PyPI 'pending publisher' pre-registered before first publish, per CLAUDE.md CI section + Phase 4 PKG-01)."
    - "`.planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md` exists with: (a) the exact `uv build --all` + wheel-METADATA grep commands; (b) trusted-publishing rehearsal steps; (c) manual sample-data live tests for all 10 catalog entries; (d) the deterministic-replay test running over real network calls; (e) sign-off line for user explicit approval before tagging v0.2.0."
    - "Full repo suite green: `uv run pytest -m 'not live' -q` exits 0 (Wave 1+2+3+4 tests + new Wave 4b tests = ~110+ MCP tests + Phase 2/3/4 baseline)."
    - "Wheel build dry-run for all 5 packages: `uv build --all` succeeds; `for whl in dist/*.whl; do unzip -l \"$whl\" | grep -c '/__init__.py'; done` — no whl ships two `tradewinds/__init__.py` (PKG-02)."
    - "PRE-PUBLISH ONLY: trusted-publishing dry-run via `.github/workflows/release.yml` against TestPyPI (configured in workflow as an optional pre-release rehearsal). Documented in 05-05-RELEASE-CHECKLIST.md; not run as part of this plan's automation — manual step before tagging."
  artifacts:
    - path: packages/mcp/tests/test_jsonrpc_subprocess_integration.py
      provides: "End-to-end JSON-RPC subprocess tests for all 5 tools using run_server_in_process; ~6 tests; full envelope-shape verification"
      contains: "from fastmcp.utilities.tests import run_server_in_process"
      min_lines: 100
    - path: packages/mcp/tests/test_deterministic_replay.py
      provides: "MCP-09 deterministic-replay tests for weather + macro source; hash-stability over 10 reps; RESEARCH.md §D.3 idiom"
      contains: "sha256.*hexdigest"
      min_lines: 80
    - path: packages/mcp/tests/test_deterministic_replay_property.py
      provides: "Hypothesis property test bounding (source_id, as_of) range per CORE-08 pattern; bytes-identical assertion"
      contains: "@given"
      min_lines: 40
    - path: packages/mcp/src/tradewinds_mcp/_join_validator.py
      provides: "Cross-source join allow-list enforcement (RESEARCH.md §I.8); raises SchemaValidationError for undeclared joins"
      contains: "joins_to allow-list"
      min_lines: 40
    - path: CHANGELOG.md
      provides: "[v0.2.0] section listing MCP-01..MCP-10 deliverables + new packages + dependency bumps"
      contains: "## [v0.2.0]"
    - path: .github/workflows/release.yml
      provides: "Trusted-publishing workflow extended for tradewinds-mcp + tradewinds-macro"
      contains: "tradewinds-mcp"
    - path: .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md
      provides: "Pre-publish checklist with explicit commands, verifications, sign-off line"
      contains: "Sign-off"
  key_links:
    - from: packages/mcp/tests/test_jsonrpc_subprocess_integration.py
      to: fastmcp.utilities.tests.run_server_in_process
      via: "subprocess transport for end-to-end verification per RESEARCH.md §A.4"
      pattern: "run_server_in_process"
    - from: packages/mcp/tests/test_deterministic_replay.py
      to: hashlib.sha256
      via: "RESEARCH.md §D.3 idiom — sha256(data.encode('utf-8')).hexdigest()"
      pattern: "sha256.*encode\\(.utf-8.\\)"
    - from: packages/mcp/tests/test_replay_audit_consistency.py
      to: $HOME/.tradewinds/mcp-server/audit-*.jsonl
      via: "test reads audit log, verifies hash field equals re-computed sha256"
      pattern: "audit.*\\.jsonl"
    - from: .github/workflows/release.yml
      to: tradewinds-mcp + tradewinds-macro
      via: "trusted publishing adds new distributions alongside Phase 4's tradewinds + tradewinds-weather + tradewinds-markets"
      pattern: "tradewinds-(mcp|macro)"
---

<objective>
**Wave 4b ships v0.2.0 — end-to-end JSON-RPC integration tests + deterministic replay + release.**

This plan is the v0.2.0 ship gate. Wave 1 shipped the server skeleton with in-process tests; Wave 4b verifies the same server works END-TO-END across a real JSON-RPC subprocess boundary (the way an AI agent actually talks to it). Plus the MCP-09 deterministic-replay guarantee, the RESEARCH.md §I.8 cross-vertical-join enforcement, and the trusted-publishing release for tradewinds-mcp + tradewinds-macro.

**Four deliverables:**

1. **End-to-end JSON-RPC subprocess tests** (`test_jsonrpc_subprocess_integration.py`). Uses `fastmcp.utilities.tests.run_server_in_process` per RESEARCH.md §A.4. Spawns the actual stdio server in a subprocess; opens a ClientSession; calls each of the 5 tools end-to-end. Verifies envelope shape, audit log behavior, middleware enforcement (missing as_of → JSON-RPC error), and schema retrieval. Bounded to ~6 tests (subprocess tests are ~100ms each; we don't run the full suite this way).

2. **Deterministic replay** (`test_deterministic_replay*.py`). MCP-09. Same query + same as_of + same filters → byte-identical TOON `data`. Tested for weather (iem.archive) AND vintage-aware macro (alfred.archive). Plus a Hypothesis property test bounding the (source_id, as_of) space per Phase 2 CORE-08 pattern (constrained UTC range to avoid shrinking pathology). The audit-log hash must match the re-computed sha256, so a replay can be reconstructed from the audit log alone.

3. **Cross-vertical join enforcement** (`_join_validator.py` + `test_cross_vertical_join_rejection.py`). RESEARCH.md §I.8 pitfall mitigation: catalog `joins_to` blocks are the ALLOW-LIST. v0.2 hard-rejects undeclared cross-source joins at query time. Per RESEARCH.md §I.8: "v0.2 can simply REJECT undeclared joins" — that's what we ship.

4. **v0.2.0 release artifacts** (CHANGELOG, release.yml workflow extension, RELEASE-CHECKLIST). Phase 4 shipped the trusted-publishing workflow for 3 distributions; Wave 4b extends it for 2 more (tradewinds-mcp + tradewinds-macro). The actual `git tag v0.2.0 && git push --tags` is OUT OF SCOPE for this plan — it's the manual sign-off step after the user reviews the checklist. The plan ships the infrastructure + the checklist; the user pulls the trigger.

**Why this is a single plan, not two:** Per RESEARCH.md §H.2 plan-shape recommendation, PLAN-05 lane F runs in parallel with PLAN-04 lane V once Task 4.0 USER_DECISION_GATE resolves. The integration + release work is ALL test + release infrastructure; the adapter work is lane V. Same Wave 4. Both merge to main; the v0.2.0 tag is the last action after both lanes are green.

**Three pitfalls hard-mitigated in Wave 4b:**
- **RESEARCH.md §I.5 TOON nondeterminism:** already mitigated in Wave 1 via `test_toon_serializer_byte_deterministic_100_runs`. Wave 4b runs the replay tests as the production verification.
- **RESEARCH.md §I.7 ALFRED row-count inflation:** already mitigated in PLAN-04 ALFREDAdapter; Wave 4b's deterministic-replay test confirms the mitigation holds end-to-end.
- **RESEARCH.md §I.8 cross-vertical join silently producing wrong rows:** Wave 4b ships the `_join_validator` + audit-log "joins_to=undeclared" tracking.

**Out of scope:**
- Actually tagging v0.2.0 and pushing — that's a user sign-off step per RELEASE-CHECKLIST.md.
- v0.3+ features (hosted mode, third vertical, third-vertical adapter, agent-DAG enhancement, full-text catalog search).
- Pandas 3.0 migration — explicitly deferred per Phase 5 dependency on `pandas>=2.2,<3.0` lock.

**Output:** A complete v0.2.0 ship-ready milestone. All 10 MCP-XX requirements verified end-to-end. Deterministic replay proven. Trusted-publishing workflow extended. The last action — `git tag v0.2.0` — is a user decision, not an automation step.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phase-05-mcp-data-platform/CONTEXT.md
@.planning/phase-05-mcp-data-platform/RESEARCH.md
@.planning/phase-05-mcp-data-platform/05-04-SUMMARY.md
@.planning/phase-05-mcp-data-platform/05-04-VERTICAL-DECISION.md
@./CLAUDE.md
</execution_context>

<interfaces>
From Waves 1-4a (everything required exists at this point):

```python
# Server, middleware, audit, envelopes (Wave 1)
from tradewinds_mcp.server import mcp
from tradewinds_mcp.temporal_middleware import TemporalSafetyMiddleware
from tradewinds_mcp.audit import AuditLogger
from tradewinds_mcp.envelopes import QueryResponse, IngestResponse, ...

# Catalog + adapter bridge (Wave 2 + 4a)
from tradewinds_mcp.catalog import CatalogLoader
from tradewinds_mcp._adapter_bridge import AdapterBridge

# Agent-connector pipeline (Wave 3 — used in this plan? NO — pipeline is for adding entries; this plan tests the entries we already have)

# Macro adapters (Wave 4a)
from tradewinds_macro.catalog import get_adapter as macro_get_adapter
from tradewinds_macro.catalog.kalshi_macro import KALSHI_MACRO_SETTLEMENT_SOURCES

# FastMCP test utilities (RESEARCH.md §A.4)
from fastmcp.utilities.tests import run_server_async, run_server_in_process

# Hypothesis (Phase 2 CORE-08 — bounded datetime ranges to avoid shrinking pathology)
from hypothesis import given, strategies as st
from datetime import datetime, timezone
```

Phase 4 (when shipped) provides:
- `.github/workflows/release.yml` trusted-publishing pattern for tradewinds + tradewinds-weather + tradewinds-markets
- `CHANGELOG.md` if it exists; otherwise create
- PyPI "pending publisher" registration process for first publish

CLAUDE.md tech stack confirms:
- `mcp>=1.27,<2.0` (locked)
- `hypothesis>=6.140,<7` (Phase 2 dev dep)
- trusted-publishing pattern via astral-sh/trusted-publishing-examples
</interfaces>

<phase_summary>

**Goal:** Verify end-to-end JSON-RPC behavior; prove deterministic replay; ship cross-vertical-join enforcement; extend release workflow; document the v0.2.0 ship checklist.

**Branch:** `phase-5/wave-4/integration-replay-release` off `main` (in PARALLEL with PLAN-04's branch once Task 4.0 resolves; merge order: PLAN-04 first, then PLAN-05).

**Atomic commit boundaries:**
- Task 5.1 (JSON-RPC subprocess integration tests) → 2 commits (RED + GREEN)
- Task 5.2 (deterministic-replay tests + property test) → 2 commits
- Task 5.3 (cross-vertical-join allow-list enforcement) → 2 commits
- Task 5.4 (CHANGELOG + release.yml extension + RELEASE-CHECKLIST) → 1 commit
- Task 5.5 (pre-merge gate + wheel verification + 2-reviewer loop) → 1 commit

**2-reviewer loop:** codex `high` + python-architect. Never-skip applies (CHANGELOG ships the public release narrative; release.yml is schema-fragment-bearing; deterministic-replay tests are load-bearing for the trust thesis).

**Pre-merge gate:**
1. Full repo suite green INCLUDING new Wave 4b tests.
2. All 6 JSON-RPC subprocess tests pass.
3. All 5 deterministic-replay tests pass (including the Hypothesis property test).
4. All cross-vertical-join tests pass.
5. Wheel build for all 5 distributions succeeds; no PKG-02 collisions; METADATA pins correct.
6. `.github/workflows/release.yml` is valid YAML and references tradewinds-mcp + tradewinds-macro.
7. CHANGELOG [v0.2.0] section is complete and accurate.
8. RELEASE-CHECKLIST.md is committed and surfaces the sign-off line.
9. Pre-commit + pre-push hooks green.
10. 2-reviewer loop PASS x2.

**v0.2.0 tagging is NOT part of this plan.** This plan ships the gate; the user pulls the trigger.

</phase_summary>

<tasks>

<task type="auto" tdd="true">
  <name>Task 5.1: JSON-RPC subprocess integration tests (RED tests FIRST)</name>
  <files>packages/mcp/tests/test_jsonrpc_subprocess_integration.py, packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py</files>
  <implements>MCP-01 (end-to-end via real subprocess transport); MCP-04 (E2E temporal safety); MCP-07 (E2E schema validation errors)</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§A.4 — testing pyramid; run_server_in_process for stdio subprocess; jlowin.dev/blog/stop-vibe-testing-mcp-servers — don't manually test via Claude Desktop; §I.6 — stdout corruption pitfall — these tests catch it because subprocess framing is real)
    - Wave 1 + 2 + 4a tests in packages/mcp/tests/ for context on tool surface and envelope shapes
    - packages/mcp/src/tradewinds_mcp/server.py (entry point for the subprocess)
  </read_first>
  <behavior>
    Tests in `packages/mcp/tests/test_jsonrpc_subprocess_integration.py` (6 tests):

    1. `test_jsonrpc_subprocess_list_sources_returns_ten_entries`: spawn server via `run_server_in_process(mcp)`; open ClientSession over stdio; call `list_sources`; assert response.content (or whatever FastMCP names it) contains a structured envelope with `sources=[<10 sorted IDs>]`.
    2. `test_jsonrpc_subprocess_describe_source_iem_archive`: same setup; call `describe_source('iem.archive')`; assert envelope has `catalog_entry` populated with the full 5-layer YAML content.
    3. `test_jsonrpc_subprocess_query_iem_archive_returns_envelope`: same setup; call `query('iem.archive', as_of='2024-01-15T00:00:00Z', filters={'station':'KNYC'})`; assert envelope has `format='toon'`, `data` is non-empty string, `schema_id='schema.observation.v1'`, `audit_id` matches expected pattern.
    4. `test_jsonrpc_subprocess_query_alfred_archive_envelope`: same for `alfred.archive` (vintage-aware macro source); verify envelope shape; verify `data` content includes `realtime_start` column data when deserialized.
    5. `test_jsonrpc_subprocess_get_schema_returns_phase2_schema`: call `get_schema('schema.observation.v1')`; envelope `schema_json` matches Phase 2 ColumnSpec list (field names + types).
    6. `test_jsonrpc_subprocess_audit_log_appended_per_call`: count audit.jsonl lines before and after a query; difference = 1.

    Tests in `packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py` (4 tests):

    1. `test_jsonrpc_query_missing_as_of_returns_error`: agent submits `query` JSON-RPC without `as_of`; client receives a JSON-RPC error response; error body's message contains "as_of" and "temporal safety".
    2. `test_jsonrpc_query_none_as_of_returns_error`: same with `as_of=None` explicitly.
    3. `test_jsonrpc_query_unknown_source_returns_error`: `query('fake.nonexistent', as_of='2024-01-15T00:00:00Z')` → JSON-RPC error; body matches `SourceUnavailableError.to_dict()` shape (Phase 2 pattern).
    4. `test_jsonrpc_get_schema_unknown_id_returns_error`: `get_schema('schema.fake.v99')` → JSON-RPC error; body matches `SchemaValidationError.to_dict()` shape; available IDs listed.

    Run `uv run pytest packages/mcp/tests/test_jsonrpc_subprocess_integration.py packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 10 tests. Use `run_server_in_process` per RESEARCH.md §A.4. Example skeleton (adapt to actual FastMCP test-utility API as of mcp>=1.27):

    ```python
    """End-to-end JSON-RPC subprocess tests.

    These tests spawn the real FastMCP stdio server in a subprocess and talk to it
    over JSON-RPC. They verify the server works end-to-end, not just in-process.

    Per RESEARCH.md §A.4: subprocess tests are slower (~100ms per spawn) than in-process
    tests. Bound to ~6 tests; in-process tests from Wave 1 stay as the fast pyramid.
    """
    import json
    import pytest
    from fastmcp.utilities.tests import run_server_in_process
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client


    @pytest.mark.asyncio
    async def test_jsonrpc_subprocess_list_sources_returns_ten_entries():
        from tradewinds_mcp.server import mcp
        # FastMCP test utility — exact API depends on mcp version; adapt as needed.
        # The general pattern: run server in subprocess, get a session, call tools.
        async with run_server_in_process(mcp) as server_handle:
            async with stdio_client(server_handle) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("list_sources", {})
                    # FastMCP wraps the Pydantic envelope; assert against structured content
                    content = result.structured_content or json.loads(result.content[0].text)
                    sources = content.get("sources", [])
                    assert len(sources) == 10
                    assert sorted(sources) == sources  # sorted
                    assert "fred.archive" in sources
                    assert "iem.archive" in sources
    ```

    Step 2 — Adapt to actual FastMCP API. The exact method names (`call_tool`, `structured_content`) depend on mcp SDK version 1.27+. If the API has shifted, consult `fastmcp.utilities.tests` source at install time. If `run_server_in_process` isn't the right helper name, use whatever the current docs (gofastmcp.com/development/tests) document.

    Step 3 — Implement supporting helpers if needed (e.g., a fixture that ensures a clean audit dir per test to make `test_jsonrpc_subprocess_audit_log_appended_per_call` deterministic — use `tmp_path` for audit base_dir).

    Step 4 — Run `uv run pytest packages/mcp/tests/test_jsonrpc_subprocess_integration.py packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py -x -v` — all 10 tests MUST pass.

    Step 5 — Commit GREEN: `feat(phase-5): JSON-RPC subprocess integration tests for all 5 tools (MCP-01 + MCP-04 + MCP-07 E2E)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_jsonrpc_subprocess_integration.py packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/tests/test_jsonrpc_subprocess_integration.py` returns 0
    - `test -f packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py` returns 0
    - `grep -c "from fastmcp.utilities.tests import run_server_in_process" packages/mcp/tests/test_jsonrpc_subprocess_integration.py` returns 1
    - `grep -c "ClientSession" packages/mcp/tests/test_jsonrpc_subprocess_integration.py` returns ≥ 1
    - `grep -c "def test_" packages/mcp/tests/test_jsonrpc_subprocess_integration.py` returns 6
    - `grep -c "def test_" packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py` returns 4
    - `uv run pytest packages/mcp/tests/test_jsonrpc_subprocess_integration.py packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py -x -v` exits 0 with 10 passed
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    10 end-to-end JSON-RPC subprocess tests pass; all 5 tools verified across a real subprocess + stdio transport; temporal-safety middleware rejection visible at the JSON-RPC error envelope level (MCP-04 end-to-end); schema validation errors surface with Phase 2 `to_dict()` payload (MCP-07 end-to-end).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 5.2: Deterministic-replay tests + Hypothesis property test (RED tests FIRST)</name>
  <files>packages/mcp/tests/test_deterministic_replay.py, packages/mcp/tests/test_replay_audit_consistency.py, packages/mcp/tests/test_deterministic_replay_property.py</files>
  <implements>MCP-09 (deterministic replay — same query + same cutoff = identical bytes)</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§D.3 — deterministic replay design + 5 technical challenges; idiom at lines 754-775; §I.5 — TOON determinism guard from Wave 1)
    - packages/mcp/tests/test_toon_deterministic.py (Wave 1 — TOON determinism prerequisite — should be green; if not, fix before Wave 4b)
    - packages/macro/src/tradewinds_macro/catalog/alfred.py (PLAN-04 — vintage dedup logic; replay test verifies it holds)
    - Phase 2 CORE-08 (Hypothesis pattern — constrained datetime ranges to avoid shrinking pathology; `from hypothesis.strategies import datetimes, just`; range [2018-01-01, 2027-12-31] UTC)
  </read_first>
  <behavior>
    Tests in `packages/mcp/tests/test_deterministic_replay.py` (4 tests):

    1. `test_replay_iem_archive_byte_identical_10x`: in-process query with `{source_id: 'iem.archive', as_of: '2024-01-15T00:00:00Z', filters: {station: 'KNYC'}}`; call 10 times in a loop; collect each `data` string; assert all 10 `sha256(d.encode("utf-8")).hexdigest()` are identical. Uses recorded fixtures so the underlying adapter is deterministic.
    2. `test_replay_alfred_archive_byte_identical_10x`: same for `alfred.archive` with `series_id='CPIAUCSL'`. Vintage-aware semantics: same as_of always picks same vintages.
    3. `test_replay_two_consecutive_calls_identical_iem`: more explicit version per RESEARCH.md §D.3 idiom — just 2 calls; verifies the basic hash equality contract.
    4. `test_replay_two_consecutive_calls_identical_alfred_vintage`: same for alfred; ensures vintage dedup doesn't produce different row sets across calls.

    Tests in `packages/mcp/tests/test_replay_audit_consistency.py` (2 tests):

    1. `test_audit_hash_matches_recomputed_envelope_data`: query a source; read the audit.jsonl entry that was just appended; verify `entry['hash'] == sha256(envelope.data.encode('utf-8')).hexdigest()`.
    2. `test_replay_from_audit_log_reconstructs_query`: read an audit entry; re-issue the same query (source_id, as_of from the entry); compare `data` field — bytes-identical.

    Tests in `packages/mcp/tests/test_deterministic_replay_property.py` (1 Hypothesis property test):

    1. `test_replay_property_bytes_identical`:
       ```python
       @given(
           source_id=sampled_from(["iem.archive", "alfred.archive"]),
           as_of=datetimes(
               min_value=datetime(2018, 1, 1),
               max_value=datetime(2027, 12, 31),
               timezones=just(timezone.utc),
           ),
       )
       @settings(max_examples=20, deadline=None)
       def test_replay_property_bytes_identical(source_id, as_of):
           # Use recorded fixtures (cassettes) so we don't hammer real APIs
           # If as_of pre-dates the cassette window, the fetch returns empty — also acceptable
           args = {"source_id": source_id, "as_of": as_of, "filters": {}}
           # Call twice in-process; assert hashes equal
           ...
       ```
       Constrained datetime range to avoid Phase 2 CORE-08 shrinking pathology. `max_examples=20` is a reasonable bound (full Hypothesis runs are slow; 20 is enough to catch nondeterminism in this surface).

    Run `uv run pytest packages/mcp/tests/test_deterministic_replay*.py packages/mcp/tests/test_replay_audit_consistency.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 7 tests. The pattern (from RESEARCH.md §D.3):

    ```python
    """MCP-09 deterministic replay tests.

    Per CONTEXT.md MCP-09 lock: same query + same as_of + same filters → byte-identical
    TOON output across runs. Verified by hash equality over 10 repetitions for both
    a non-vintage source (iem.archive) and a vintage-aware source (alfred.archive).

    Builds on Wave 1's TOON determinism guard (test_toon_deterministic.py). If TOON
    is found nondeterministic at this stage, the fix lives in tradewinds.core.formats.toon
    and propagates here; this plan does NOT patch around it.
    """

    import hashlib
    import pytest


    @pytest.mark.asyncio
    async def test_replay_iem_archive_byte_identical_10x(in_process_mcp):
        args = {
            "source_id": "iem.archive",
            "as_of": "2024-01-15T00:00:00Z",
            "filters": {"station": "KNYC"},
        }
        hashes = []
        for _ in range(10):
            result = await in_process_mcp.call_tool("query", args)
            data = result.structured_content["data"] if hasattr(result, "structured_content") else json.loads(result.content[0].text)["data"]
            h = hashlib.sha256(data.encode("utf-8")).hexdigest()
            hashes.append(h)
        assert len(set(hashes)) == 1, f"Nondeterministic: {len(set(hashes))} distinct hashes in 10 runs"
    ```

    Step 2 — Run `uv run pytest packages/mcp/tests/test_deterministic_replay*.py packages/mcp/tests/test_replay_audit_consistency.py -x -v` — all 7 tests MUST pass.

    Step 3 — If ANY fail: surface to user. Likely causes:
    - Pandas dtype drift (Phase 1 `pandas>=2.2,<3.0` pin should prevent this).
    - Categorical column reorder (Phase 2 TOON test should have caught — but Wave 4b's replay over real data may surface a case Wave 1's synthetic test didn't).
    - ALFRED vintage filter regressions (PLAN-04 Task 4.2 should prevent).

    Fix the root cause in the appropriate package; re-run.

    Step 4 — Commit GREEN: `feat(phase-5): MCP-09 deterministic-replay tests (weather + macro + Hypothesis property)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_deterministic_replay.py packages/mcp/tests/test_replay_audit_consistency.py packages/mcp/tests/test_deterministic_replay_property.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/tests/test_deterministic_replay.py` returns 0
    - `test -f packages/mcp/tests/test_replay_audit_consistency.py` returns 0
    - `test -f packages/mcp/tests/test_deterministic_replay_property.py` returns 0
    - `grep -c "hashlib.sha256" packages/mcp/tests/test_deterministic_replay.py` returns ≥ 2 (replay idiom present)
    - `grep -c '"utf-8"' packages/mcp/tests/test_deterministic_replay.py` returns ≥ 2 (encoding pinned)
    - `grep -c "@given" packages/mcp/tests/test_deterministic_replay_property.py` returns 1 (Hypothesis used)
    - `grep -c "timezones=just(timezone.utc)" packages/mcp/tests/test_deterministic_replay_property.py` returns 1 (CORE-08 shrinking-pathology mitigation)
    - `uv run pytest packages/mcp/tests/test_deterministic_replay.py -x -v` exits 0 with 4 passed
    - `uv run pytest packages/mcp/tests/test_replay_audit_consistency.py -x -v` exits 0 with 2 passed
    - `uv run pytest packages/mcp/tests/test_deterministic_replay_property.py -x -v` exits 0 with 1 passed (≥ 20 example runs)
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    7 deterministic-replay tests pass. Hash equality verified over 10 iterations for both weather (iem.archive) and macro (alfred.archive) sources. Audit log hash matches recomputed sha256. Hypothesis property test covers (source_id, as_of) space with CORE-08-bounded ranges.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 5.3: Cross-vertical join allow-list enforcement (RED tests FIRST)</name>
  <files>packages/mcp/src/tradewinds_mcp/_join_validator.py, packages/mcp/tests/test_cross_vertical_join_rejection.py, packages/mcp/src/tradewinds_mcp/tools/query.py</files>
  <implements>RESEARCH.md §I.8 pitfall mitigation; reinforces MCP-04 trust thesis (agent literally cannot do undeclared joins)</implements>
  <read_first>
    - .planning/phase-05-mcp-data-platform/RESEARCH.md (§I.8 — cross-vertical join silently produces wrong rows; mitigation: `joins_to` is allow-list, v0.2 hard-rejects)
    - packages/mcp/catalog/iem.archive.yaml (PLAN-02 — its `relationship_mappings.joins_to` is the allow-list; verify it lists `ghcnh.archive` + `kalshi.weather` but NOT macro sources)
    - packages/mcp/catalog/fred.archive.yaml (PLAN-04 — its joins_to lists `alfred.archive` + `kalshi.macro` but NOT weather sources)
    - packages/mcp/src/tradewinds_mcp/tools/query.py (Wave 2 — extending to call the join validator before fetching)
    - packages/mcp/src/tradewinds_mcp/_catalog_entry_types.py (RelationshipMapping shape)
  </read_first>
  <behavior>
    Tests in `packages/mcp/tests/test_cross_vertical_join_rejection.py` (5 tests):

    1. `test_join_validator_accepts_declared_join`: catalog entry `iem.archive` has `joins_to: [{source: ghcnh.archive, on: [station_id, observed_at]}]`. `JoinValidator(iem_entry).validate({'join': {'source': 'ghcnh.archive', 'on': ['station_id']}})` returns True (no error).
    2. `test_join_validator_rejects_undeclared_cross_vertical`: same iem.archive entry; `validate({'join': {'source': 'fred.archive', 'on': ['date']}})` raises `SchemaValidationError` (Phase 2 exception) with message containing 'undeclared join' + 'fred.archive' + the list of declared joins.
    3. `test_join_validator_rejects_undeclared_intra_vertical`: iem.archive doesn't declare a join to `awc.live`; `validate({'join': {'source': 'awc.live', 'on': ['station_id']}})` raises.
    4. `test_query_tool_invokes_join_validator`: in-process query with a filter containing a `join` block; verify `JoinValidator` was called (mock); verify SchemaValidationError surfaces as JSON-RPC error.
    5. `test_query_tool_audit_logs_undeclared_join_attempt`: rejected join still emits an audit log entry with `joins_to=undeclared` + the attempted source. RESEARCH.md §I.8: "audit log records 'joins_to=undeclared' entries — surface in tests."

    Run `uv run pytest packages/mcp/tests/test_cross_vertical_join_rejection.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 5 tests. Commit RED.

    Step 2 — Implement `packages/mcp/src/tradewinds_mcp/_join_validator.py`:

    ```python
    """JoinValidator — enforce catalog `joins_to` allow-list at query time.

    Per RESEARCH.md §I.8: undeclared cross-source joins silently produce wrong rows
    (joining weather event_time to macro release_date on a `date` column gives garbage).
    v0.2 mitigation: catalog `relationship_mappings.joins_to` is the ALLOW-LIST;
    any join not in this list is rejected at query time with SchemaValidationError.

    v0.3+ may soften to warnings + opt-in `allow_undeclared_joins=True` if user demand
    emerges.
    """

    from __future__ import annotations

    from tradewinds.core.exceptions import SchemaValidationError
    from ._catalog_entry_types import CatalogEntry

    __all__ = ["JoinValidator"]


    class JoinValidator:
        def __init__(self, entry: CatalogEntry) -> None:
            self._entry = entry
            self._declared = {jm.source for jm in entry.relationship_mappings.joins_to}

        def validate(self, filters: dict | None) -> None:
            """Inspect filters for a 'join' block; raise if it's not in joins_to allow-list."""
            if not filters:
                return
            join = filters.get("join")
            if not join:
                return
            target_source = join.get("source")
            if not target_source:
                return
            if target_source not in self._declared:
                raise SchemaValidationError(
                    f"Undeclared cross-source join from '{self._entry.source_id}' to '{target_source}'. "
                    f"Per RESEARCH.md §I.8, joins_to is an allow-list. "
                    f"Declared joins for {self._entry.source_id}: {sorted(self._declared)}. "
                    f"v0.3 may soften this to a warning; v0.2 hard-rejects."
                )
    ```

    Step 3 — Modify `packages/mcp/src/tradewinds_mcp/tools/query.py` to invoke the join validator BEFORE fetching:

    ```python
    # Inside the register() function's query tool body:
    from .._join_validator import JoinValidator

    @mcp.tool()
    async def query(source_id, as_of, filters=None, format="toon") -> QueryResponse:
        entry = catalog.lookup(source_id)
        # NEW: validate joins before fetching
        try:
            JoinValidator(entry).validate(filters)
        except SchemaValidationError as exc:
            # Audit the rejection per RESEARCH.md §I.8
            audit.log(
                tool="query",
                source=source_id,
                as_of=as_of,
                rows=0,
                hash="",
                schema_id=entry.schema_semantics.schema_id,
                extra={"joins_to_status": "undeclared", "attempted_source": filters.get("join", {}).get("source", "")},
            )
            raise
        # ... rest unchanged
    ```

    Step 4 — Run `uv run pytest packages/mcp/tests/test_cross_vertical_join_rejection.py -x -v` — all 5 tests MUST pass.

    Step 5 — Verify no regression in Wave 1+2+4a tests: `uv run pytest packages/mcp/tests/ -m "not live" -q`. Expected green.

    Step 6 — Commit GREEN: `feat(phase-5): cross-vertical join allow-list enforcement (RESEARCH.md §I.8 mitigation)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_cross_vertical_join_rejection.py -x -v && uv run pytest packages/mcp/tests/ -m "not live" -q</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/src/tradewinds_mcp/_join_validator.py` returns 0
    - `grep -c "class JoinValidator" packages/mcp/src/tradewinds_mcp/_join_validator.py` returns 1
    - `grep -c "SchemaValidationError" packages/mcp/src/tradewinds_mcp/_join_validator.py` returns ≥ 1
    - `grep -c "joins_to is an allow-list" packages/mcp/src/tradewinds_mcp/_join_validator.py` returns ≥ 1
    - `grep -c "JoinValidator(entry).validate" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1
    - `grep -c "joins_to_status" packages/mcp/src/tradewinds_mcp/tools/query.py` returns 1 (audit rejection logging)
    - `uv run pytest packages/mcp/tests/test_cross_vertical_join_rejection.py -x -v` exits 0 with 5 passed
    - `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0 (no Wave 1+2+4a regression)
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    JoinValidator enforces catalog `joins_to` allow-list; undeclared cross-source joins raise SchemaValidationError BEFORE the fetch runs; audit log records rejected attempts with `joins_to_status=undeclared`. 5 tests pass; no Wave 1+2+4a regression.
  </done>
</task>

<task type="auto">
  <name>Task 5.4: CHANGELOG [v0.2.0] + release.yml extension + RELEASE-CHECKLIST</name>
  <files>CHANGELOG.md, .github/workflows/release.yml, .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md, .github/workflows/mcp-tests.yml</files>
  <implements>v0.2.0 release infrastructure</implements>
  <read_first>
    - .planning/phase-04-coverage-docs-cicd-release/PLAN.md (when shipped — pattern for release.yml; PyPI trusted publishing per CI-01)
    - .github/workflows/release.yml (post-Phase-4 — base file to extend; if missing, Phase 4 deliverable hasn't shipped and this task needs to coordinate)
    - existing CHANGELOG.md (post-Phase-1.5+Phase-4 — base section structure; if missing, create with the Keep-a-Changelog template)
    - CLAUDE.md (CI section — astral-sh/trusted-publishing-examples pattern; PKG-01 — three PyPI registrations, now extending to 5)
    - .planning/phase-05-mcp-data-platform/05-04-SUMMARY.md (PLAN-04 outputs — what shipped + the vertical decision)
  </read_first>
  <action>
    Step 1 — Modify (or create) `CHANGELOG.md`. Append a `[v0.2.0]` section:

    ```markdown
    ## [v0.2.0] — YYYY-MM-DD (TBD when user signs off on release)

    ### Added — MCP Data Platform

    Phase 5 ships the MCP-native data platform for prediction-market ML. Six top-line capabilities, ten requirements (MCP-01..MCP-10):

    - **MCP server layer** (`tradewinds-mcp` distribution) — FastMCP-based local-first stdio server exposing five tools: `list_sources`, `describe_source`, `ingest`, `query`, `get_schema`. Any MCP client (Claude Desktop, Cursor, custom) can connect via `tradewinds-mcp-server` console script. (MCP-01)
    - **5-layer data catalog** at `packages/mcp/catalog/` — per-source YAML files describing schema semantics, temporal rules, quality notes, relationship mappings, and operational context. Validated by JSON Schema 2020-12 meta-schema. (MCP-02)
    - **Agent-generated connector pipeline** — scaffold helper (`scaffold_catalog_entry`), validator (`validate_generated_entry` with 4 checks + 3 warnings), promotion CLI (`promote_generated_entry.py`), CI gate (`catalog-promotion-gate` workflow). Community contributions via PR against `_generated/`, gated by validator + sample-data live test + maintainer review. (MCP-03)
    - **Server-enforced temporal safety** via `TemporalSafetyMiddleware` (FastMCP `on_call_tool` hook). `as_of` parameter REQUIRED on every read tool; meta-test `test_no_read_tool_lacks_as_of` walks the live tool registry and asserts no future tool can bypass. (MCP-04)
    - **Multi-vertical proof** — new `tradewinds-macro` distribution adds FRED + ALFRED + Kalshi macro contract specs alongside Phase 2 weather. Both verticals share the same temporal-safety + catalog primitives. (MCP-05)
    - **Auditable provenance** — every MCP tool call writes a sort_keys-stable JSONL entry to `$HOME/.tradewinds/mcp-server/audit-<iso>-<pid>.jsonl`. Entries include `caller_identity` (v0.3 hosted-mode seam), hash of result, timestamps, source ID. (MCP-06)
    - **Schema contract validation on ingest + query** — reuses Phase 2 `validate_dataframe`; errors surface as JSON-RPC error envelopes via `TradewindsError.to_dict()`. (MCP-07)
    - **Point-in-time API** — `tradewinds.core.temporal.Dataset.at_time(date)` / `.between(start, end)` / `.as_of(timestamp)` (MCP-08)
    - **Deterministic replay** — same query + same `as_of` + same filters = byte-identical TOON `data`. Tested via 10-iteration hash-stability for both weather (`iem.archive`) and vintage-aware macro (`alfred.archive`) sources + Hypothesis property test. (MCP-09)
    - **10 pre-indexed catalog entries** — 7 weather (`iem.archive`, `iem.live`, `awc.live`, `ghcnh.archive`, `cli.archive`, `iem.forecasts`, `kalshi.weather`) + 3 macro (`fred.archive`, `alfred.archive`, `kalshi.macro`). (MCP-10)

    ### Added — Distributions

    - `tradewinds-mcp==0.2.0` — MCP server layer (NEW)
    - `tradewinds-macro==0.2.0` — Macroeconomic adapters: FRED + ALFRED + Kalshi macro contract specs (NEW)
    - `tradewinds.core.temporal.Dataset` — point-in-time wrapper over Phase 2 `KnowledgeView` (NEW)

    ### Added — Cross-vertical safety

    - `JoinValidator` enforces catalog `joins_to` allow-list — undeclared cross-source joins (e.g. weather → macro on a generic `date` column) raise `SchemaValidationError` at query time. RESEARCH.md §I.8 pitfall mitigated.

    ### Changed — Dependencies

    - Added: `mcp>=1.27,<2.0` (Anthropic Python SDK, FastMCP pattern)
    - Added: `pydantic>=2.7,<3.0` (envelope BaseModels; was a transitive dep, now explicit)
    - Added: `pyyaml>=6.0,<7` (catalog loader; `yaml.safe_load` only)
    - Added: `tradewinds-macro` optional dep for the macro vertical
    - Unchanged: `pandas>=2.2,<3.0` (Pandas 3.0 migration still deferred per PANDAS3-01)

    ### Vertical decision

    The v0.2 second vertical is **macro indicators** (FRED + ALFRED + Kalshi macro). The original brief language suggested sports prediction markets; 2026 legal landscape (horse racing federally blocked May 2026; NFL/NBA in active litigation; MLB exclusive deal Polymarket) made sports non-viable in v0.2 timeframe. Sports deferred to v0.3+ pending 2026-2027 legal landscape settlement. See `.planning/phase-05-mcp-data-platform/05-04-VERTICAL-DECISION.md` for full rationale.

    ### Migration notes

    - `tradewinds-mcp` is local-first stdio in v0.2. Hosted mode (HTTP transport + OAuth) deferred to v0.3 — the `CallerContext` seam is in place to avoid v0.3 rewrite.
    - `from tradewinds.core.temporal import Dataset` is the new MCP-08 point-in-time API; existing `KnowledgeView` usage is unchanged.

    ### Acknowledgments

    Kalshi macro markets analysis informed by Federal Reserve working paper "Kalshi and the Rise of Macro Markets" (federalreserve.gov/econres/feds/files/2026010pap.pdf).
    ```

    Step 2 — Modify `.github/workflows/release.yml` to extend trusted publishing for 2 new distributions. The pattern (per CLAUDE.md CI section) adds steps for `uv build packages/mcp/` + `uv publish --publish-url` for tradewinds-mcp and tradewinds-macro:

    ```yaml
    # ADD a job per new distribution; share the trusted-publishing-examples pattern from Phase 4
    publish-mcp:
      needs: [test]
      if: startsWith(github.ref, 'refs/tags/v')
      runs-on: ubuntu-latest
      environment: pypi
      permissions:
        id-token: write
      steps:
        - uses: actions/checkout@v4
        - uses: astral-sh/setup-uv@v3
        - run: uv build packages/mcp/
        - uses: pypa/gh-action-pypi-publish@release/v1
          with:
            packages-dir: packages/mcp/dist/

    publish-macro:
      needs: [test]
      if: startsWith(github.ref, 'refs/tags/v')
      runs-on: ubuntu-latest
      environment: pypi
      permissions:
        id-token: write
      steps:
        - uses: actions/checkout@v4
        - uses: astral-sh/setup-uv@v3
        - run: uv build packages/macro/
        - uses: pypa/gh-action-pypi-publish@release/v1
          with:
            packages-dir: packages/macro/dist/
    ```

    Confirm Phase 4 already established the `test` job, `environment: pypi`, and trusted-publishing OIDC setup; if not, this task coordinates with Phase 4 (which should be complete by now since Phase 5 depends on Phase 4 — see ROADMAP.md). Document any deviations.

    Step 3 — Modify `.github/workflows/mcp-tests.yml` to also test the macro distribution:

    ```yaml
    # Already runs packages/mcp/tests/ — extend to packages/macro/tests/
    - name: Run MCP + macro fast tests
      run: |
        uv run pytest packages/mcp/tests/ packages/macro/tests/ -m "not live" -v
    ```

    Step 4 — Create `.planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md`:

    ```markdown
    # v0.2.0 Release Checklist — Phase 5 MCP Data Platform

    This checklist is the LAST gate before tagging v0.2.0. The user runs this manually after PLAN-04 + PLAN-05 are both merged to `main`.

    ## 1. Pre-publish verification

    ```bash
    # Full test suite green (excl. live)
    uv run pytest -m "not live" -q  # expects exit 0

    # Coverage gates
    uv run pytest --cov=tradewinds.core --cov-branch packages/core/tests/ -q | grep TOTAL  # ≥ 90%
    uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q | grep TOTAL    # ≥ 85%
    uv run pytest --cov=tradewinds_macro --cov-branch packages/macro/tests/ -q | grep TOTAL  # ≥ 80%

    # All 5 wheels build cleanly
    uv build --all
    ls dist/
    # Expected: tradewinds-0.2.0-*.whl, tradewinds_weather-0.2.0-*.whl, tradewinds_markets-0.2.0-*.whl,
    #           tradewinds_mcp-0.2.0-*.whl, tradewinds_macro-0.2.0-*.whl

    # PEP 420 namespace — no two wheels ship tradewinds/__init__.py
    for whl in dist/*.whl; do
      count=$(unzip -l "$whl" | grep -c "^.*tradewinds/__init__.py$")
      echo "$(basename "$whl"): tradewinds/__init__.py count = $count"
    done
    # Expected: only tradewinds-0.2.0-*.whl has count 1; all others have count 0

    # METADATA cross-package version pins (PKG-03)
    for whl in dist/*.whl; do
      echo "=== $(basename "$whl") ==="
      unzip -p "$whl" "*.dist-info/METADATA" | grep -E "^Requires-Dist: tradewinds"
    done
    # Expected: tradewinds-weather/markets/mcp/macro all have `Requires-Dist: tradewinds>=0.2.0,<0.3`
    ```

    Sign-off: [ ] All pre-publish verification green

    ## 2. Live sample-data checks (manual; requires real API keys)

    ```bash
    export FRED_API_KEY=<your-fred-api-key>  # required for FRED + ALFRED

    # Weather sample-data live (cassettes refresh if needed)
    uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m live -v -k "iem.archive or awc.live or ghcnh.archive or cli.archive"

    # Macro sample-data live
    uv run pytest packages/macro/tests/ -m live -v
    uv run pytest packages/mcp/tests/test_catalog_sample_data_roundtrip.py -m live -v -k "fred.archive or alfred.archive"
    ```

    Sign-off: [ ] All 10 catalog entries return real data matching their declared schemas

    ## 3. Trusted-publishing rehearsal (TestPyPI)

    Before tagging v0.2.0, push to TestPyPI to verify the workflow.

    ```bash
    # On a temp branch
    git checkout -b release-rehearsal-v0.2.0
    git tag v0.2.0-rc1
    git push origin release-rehearsal-v0.2.0 --tags
    ```

    The release workflow will fire if configured for TestPyPI (see release.yml `--publish-url` parameter; toggle to TestPyPI for the rehearsal). Verify all 5 distributions appear at https://test.pypi.org/project/tradewinds-mcp/ etc.

    Cleanup: `git tag -d v0.2.0-rc1` + delete the rehearsal branch + delete TestPyPI versions.

    Sign-off: [ ] TestPyPI publication successful for all 5 distributions

    ## 4. PyPI "pending publisher" registration

    Per CLAUDE.md CI section: first publish requires pre-registering "pending publishers" at https://pypi.org/manage/account/publishing/ for:
    - `tradewinds` (Phase 4 — should already be registered)
    - `tradewinds-weather` (Phase 4)
    - `tradewinds-markets` (Phase 4)
    - `tradewinds-mcp` (NEW v0.2 — register before tagging)
    - `tradewinds-macro` (NEW v0.2 — register before tagging)

    Sign-off: [ ] 5 pending publishers registered at PyPI

    ## 5. User sign-off + v0.2.0 tag

    User MUST explicitly confirm:
    - [ ] CHANGELOG.md [v0.2.0] section is accurate and complete
    - [ ] All success criteria in PLAN-01..PLAN-05 are met
    - [ ] 2-reviewer loop PASS x2 on every Wave 4 PR
    - [ ] No outstanding TODO / known-issue blockers

    Once signed off:

    ```bash
    # On main, after PLAN-04 + PLAN-05 are merged:
    git checkout main
    git pull origin main
    git tag v0.2.0
    git push origin v0.2.0
    ```

    Release workflow fires automatically; trusted publishing pushes all 5 wheels to PyPI.

    Sign-off: [ ] v0.2.0 tagged and pushed

    ## 6. Post-publish verification

    ```bash
    # Wait ~5 min for PyPI to index, then:
    pip install --dry-run "tradewinds-mcp==0.2.0"
    pip install --dry-run "tradewinds-macro==0.2.0"

    # Smoke test in a fresh venv
    python -m venv /tmp/v020-smoke
    /tmp/v020-smoke/bin/pip install tradewinds-mcp[macro]==0.2.0
    /tmp/v020-smoke/bin/python -c "from tradewinds_mcp.server import mcp; print('OK')"
    /tmp/v020-smoke/bin/python -c "from tradewinds_macro.catalog import get_adapter; print('OK')"
    ```

    Sign-off: [ ] Fresh-venv smoke test passes

    ---

    **Final sign-off (user signature/date below):** _______________________
    ```

    Step 5 — Run `uv run pre-commit run --all-files`. Expected green.

    Step 6 — Commit: `release(phase-5): CHANGELOG v0.2.0 + release workflow extension + RELEASE-CHECKLIST`.
  </action>
  <verify>
    <automated>grep -c "## \\[v0.2.0\\]" CHANGELOG.md | grep -E "^1$" && grep -c "tradewinds-mcp" .github/workflows/release.yml | awk '$1 >= 1 {exit 0} {exit 1}' && grep -c "tradewinds-macro" .github/workflows/release.yml | awk '$1 >= 1 {exit 0} {exit 1}' && test -f .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md && grep -c "Sign-off" .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md | awk '$1 >= 5 {exit 0} {exit 1}' && uv run pre-commit run --all-files</automated>
  </verify>
  <acceptance_criteria>
    - `grep "## \\[v0.2.0\\]" CHANGELOG.md` returns non-empty
    - `grep -c "MCP-10" CHANGELOG.md` returns ≥ 1
    - `grep -c "tradewinds-mcp" CHANGELOG.md` returns ≥ 1
    - `grep -c "tradewinds-macro" CHANGELOG.md` returns ≥ 1
    - `grep -c "mcp>=1.27,<2.0" CHANGELOG.md` returns ≥ 1
    - `grep -c "vertical decision" CHANGELOG.md | grep -E "^[1-9]"` (case-insensitive; vertical decision section present)
    - `grep -c "publish-mcp:\|publish-macro:" .github/workflows/release.yml` returns ≥ 2 (jobs added)
    - `python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"` exits 0
    - `test -f .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md` returns 0
    - `grep -c "Sign-off" .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md` returns ≥ 5 (multiple sign-off checkpoints)
    - `grep -c "git tag v0.2.0" .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md` returns ≥ 1
    - `grep -c "pip install" .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md` returns ≥ 1 (post-publish smoke)
    - `uv run pre-commit run --all-files` exits 0
    - One commit on the branch
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    CHANGELOG [v0.2.0] section documents all 10 MCP-XX requirements + new distributions + vertical decision. release.yml extended for tradewinds-mcp + tradewinds-macro. mcp-tests workflow tests macro alongside mcp. RELEASE-CHECKLIST.md is a complete pre-publish runbook with 5+ sign-off lines.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 5.5: Final 2-reviewer loop + pre-merge gate + merge to main (v0.2.0 SHIP-GATE READY)</name>
  <files>n/a (verification only)</files>
  <implements>Wave 4b closeout; v0.2.0 ship gate (the tag itself is the user's action per RELEASE-CHECKLIST.md)</implements>
  <read_first>
    - .planning/REVIEW-DISCIPLINE.md
    - Plan-level success criteria below
    - .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md (Task 5.4 output)
  </read_first>
  <what-built>
    Tasks 5.1–5.4 complete: 10 JSON-RPC subprocess tests; 7 deterministic-replay tests (+ Hypothesis property); 5 cross-vertical-join enforcement tests; CHANGELOG [v0.2.0] section; release workflow extended; RELEASE-CHECKLIST.md committed. The infrastructure for v0.2.0 release is COMPLETE; tagging is the user's next manual step.
  </what-built>
  <how-to-verify>
    **Step A — Final test pass (full repo):**

    ```bash
    uv run pytest -m "not live" -v  # full suite, all phases
    uv run pytest --cov=tradewinds.core --cov=tradewinds_mcp --cov=tradewinds_macro --cov-branch -q | grep TOTAL
    ```

    Expected: all green; coverage targets met (≥90% on tradewinds.core, ≥85% on tradewinds_mcp, ≥80% on tradewinds_macro).

    **Step B — Wheel-build verification (Phase 5 final):**

    ```bash
    uv build --all
    ls dist/
    # Should list: tradewinds-0.2.0-*.whl, tradewinds_weather-0.2.0-*.whl, tradewinds_markets-0.2.0-*.whl,
    #              tradewinds_mcp-0.2.0-*.whl, tradewinds_macro-0.2.0-*.whl

    # PEP 420 namespace check
    for whl in dist/*.whl; do
      collisions=$(unzip -l "$whl" | grep -c "^.*tradewinds/__init__.py$" || true)
      echo "$(basename "$whl"): namespace collisions = $collisions"
    done
    # Expected: only tradewinds-0.2.0-*.whl has 1; all others have 0
    ```

    **Step C — METADATA cross-pin check (PKG-03):**

    ```bash
    for whl in dist/tradewinds_*.whl; do
      echo "=== $(basename "$whl") ==="
      unzip -p "$whl" "*.dist-info/METADATA" | grep -E "Requires-Dist: tradewinds"
    done
    # Expected: each sibling Requires-Dist references tradewinds with explicit upper bound (<0.3)
    ```

    **Step D — 2-reviewer loop per REVIEW-DISCIPLINE.md:**

    Reviewer prompts must reference:
    - CONTEXT.md MCP-04 + MCP-06 + MCP-09 (full end-to-end verification at this stage)
    - RESEARCH.md §D.3 deterministic-replay design
    - RESEARCH.md §I.8 cross-vertical join allow-list enforcement
    - REVIEW-DISCIPLINE.md never-skip (CHANGELOG ships the release narrative; release.yml schema-fragment-bearing)
    - 05-05-RELEASE-CHECKLIST.md is the user's runbook — accuracy critical

    PASS x2 in ≤ 3 iterations.

    **Step E — Merge to main:**

    ```bash
    git checkout main
    git merge --no-ff phase-5/wave-4/integration-replay-release -m "Merge phase-5/wave-4/integration-replay-release: JSON-RPC E2E + deterministic-replay + v0.2.0 release infrastructure. Phase 5 COMPLETE. Ready for v0.2.0 tag."
    ```

    **Step F — Confirm to user:**

    "Wave 4b merged to `main`. Phase 5 is COMPLETE.

    All 10 MCP-XX requirements verified end-to-end:
    - MCP-01: ✓ 5 tools registered + JSON-RPC subprocess tests
    - MCP-02: ✓ 5-layer catalog + 10 entries
    - MCP-03: ✓ Agent-connector pipeline (scaffold + validator + CLI + CI gate)
    - MCP-04: ✓ Server-enforced temporal middleware (E2E verified; META-TEST guards)
    - MCP-05: ✓ Multi-vertical (weather + macro)
    - MCP-06: ✓ Audit JSONL (E2E verified; hash matches recomputed sha256)
    - MCP-07: ✓ Schema validation on ingest+query (E2E error envelopes)
    - MCP-08: ✓ Dataset.at_time / .between / .as_of
    - MCP-09: ✓ Deterministic replay (10-iteration hash stability + Hypothesis property)
    - MCP-10: ✓ 10 pre-indexed catalog entries (7 weather + 3 macro)

    Next step (USER ACTION): Run through `.planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md` and, when all sign-off lines green, run:
        git tag v0.2.0 && git push origin v0.2.0

    The release.yml workflow fires automatically; trusted publishing ships all 5 distributions to PyPI."
  </how-to-verify>
  <resume-signal>
    Type `approved` once Wave 4b is merged to `main` AND user has acknowledged the RELEASE-CHECKLIST is the next step. Type `revise` for reviewer-driven changes.

    NOTE: this checkpoint completes Phase 5 PLANNING. The actual v0.2.0 tagging is a user action per the checklist, not an automation step in this plan.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| JSON-RPC subprocess boundary (stdio) | Real subprocess + stdio framing tested end-to-end; surfaces stdout corruption (Pitfall I.6) if any. |
| Deterministic-replay contract | Same query → same bytes; the trust thesis for quants. Breaks = silent leakage signal. |
| Cross-vertical join allow-list | `joins_to` is the structural defense against agents joining sources that don't actually join (e.g., weather event_time vs macro release_date). |
| Release workflow + PyPI trusted publishing | OIDC-based authentication; "pending publisher" registration is a one-time setup. |
| CHANGELOG narrative | Public-facing release notes; misleading or inaccurate language is a reputation risk. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-5.5-01 | Tampering | TOON serializer becomes nondeterministic after a Pandas / Pydantic patch upgrade | mitigate | `test_replay_property` Hypothesis test catches nondeterminism on every CI run with 20 examples bounded over the (source_id, as_of) space. Plus the standalone replay tests run on every PR. Wave 1's TOON determinism test (test_toon_deterministic.py) is the first-order guard; Wave 4b's replay tests are the production-level guard. |
| T-5.5-02 | Tampering | Cross-vertical join silently producing wrong rows (Pitfall I.8) | mitigate | `JoinValidator` enforces catalog `joins_to` allow-list; undeclared joins raise `SchemaValidationError` BEFORE fetch; rejected attempts logged with `joins_to_status=undeclared` to audit JSONL for analysis. Tested by 5 tests in `test_cross_vertical_join_rejection.py`. |
| T-5.5-03 | Information Disclosure | stdout corruption (Pitfall I.6) — JSON-RPC frame broken by inadvertent `print()` | mitigate | Wave 1 enforced `stream=sys.stderr` in server.py + CI grep guard; Wave 4b's subprocess tests catch any remaining corruption end-to-end (subprocess framing is real, not mocked). |
| T-5.5-04 | Repudiation | Audit log can be tampered with after-the-fact | accept | v0.2 audit log is a plain JSONL file; integrity is git-blame-level (user-controlled local fs). v0.3+ may add hash-chaining if hosted multi-tenant ships. Documented as v0.2 limitation. |
| T-5.5-05 | Tampering | Wrong CHANGELOG narrative misleads downstream users | mitigate | 2-reviewer loop reviews CHANGELOG diff specifically (REVIEW-DISCIPLINE.md never-skip — release narrative is load-bearing). User signs off via 05-05-RELEASE-CHECKLIST.md final sign-off line. |
| T-5.5-06 | Elevation of Privilege | Trusted-publishing workflow leaks OIDC token / publishes wrong package | mitigate | `pypa/gh-action-pypi-publish@release/v1` is the official Pythonista action; OIDC token is single-use per workflow run; "pending publisher" registration ties the GitHub repo to the PyPI package name before first publish. CLAUDE.md CI section + Phase 4 PKG-01 set this up; Wave 4b extends the same pattern to 2 new distributions. |
| T-5.5-07 | Tampering | First publish hits the wrong PyPI account due to misconfigured trusted publishing | mitigate | TestPyPI rehearsal step in 05-05-RELEASE-CHECKLIST.md catches this before production tag; user reviews the published artifacts before running `git tag v0.2.0` on real PyPI. |
| T-5.5-08 | Information Disclosure | API keys leak via subprocess test fixtures or release artifacts | accept | Wave 4a already filters api_key from VCR cassettes; Wave 4b subprocess tests run without real API keys (in-process tests use cassettes; subprocess tests can use cassettes too); release artifacts are wheels — no test fixtures shipped to PyPI. |
</threat_model>

<verification>
## Plan-Level Checks

| Check | Command | Expected |
|-------|---------|----------|
| JSON-RPC subprocess tests | `uv run pytest packages/mcp/tests/test_jsonrpc_subprocess_integration.py packages/mcp/tests/test_jsonrpc_temporal_safety_e2e.py -x -v` | 10 passed |
| Deterministic-replay tests | `uv run pytest packages/mcp/tests/test_deterministic_replay.py packages/mcp/tests/test_replay_audit_consistency.py packages/mcp/tests/test_deterministic_replay_property.py -x -v` | 7 passed |
| Cross-vertical join enforcement | `uv run pytest packages/mcp/tests/test_cross_vertical_join_rejection.py -x -v` | 5 passed |
| Full repo fast suite | `uv run pytest -m "not live" -q` | exit 0 |
| Coverage tradewinds.core | `uv run pytest --cov=tradewinds.core --cov-branch packages/core/tests/ -q \| grep TOTAL` | ≥ 90% |
| Coverage tradewinds_mcp | `uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q \| grep TOTAL` | ≥ 85% |
| Coverage tradewinds_macro | `uv run pytest --cov=tradewinds_macro --cov-branch packages/macro/tests/ -q \| grep TOTAL` | ≥ 80% |
| 5-wheel build | `uv build --all && ls dist/*.whl \| wc -l` | 5 |
| PEP 420 namespace | `for whl in dist/*.whl; do unzip -l "$whl" \| grep -c "^.*tradewinds/__init__.py$"; done` | only one wheel has count 1 |
| Cross-package version pins | `unzip -p dist/tradewinds_mcp-0.2.0-*.whl "*/METADATA" \| grep "Requires-Dist: tradewinds>=0.2.0,<0.3"` | non-empty |
| CHANGELOG v0.2.0 section | `grep "## \\[v0.2.0\\]" CHANGELOG.md` | non-empty |
| release.yml extended | `grep -c "publish-mcp:\\|publish-macro:" .github/workflows/release.yml` | ≥ 2 |
| RELEASE-CHECKLIST.md | `test -f .planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md && grep -c "Sign-off" $_` | ≥ 5 |
| 2-reviewer loop | (manual) | PASS x2 |

## Static Regression Guards

```bash
# RESEARCH.md §I.5 — TOON determinism guard from Wave 1 still passes
uv run pytest packages/mcp/tests/test_toon_deterministic.py -x -v || echo "FAIL: TOON determinism regressed"

# RESEARCH.md §I.6 — no print() to stdout
grep -rn "^\s*print(" packages/mcp/src/ packages/macro/src/ && echo "FAIL: print() in production code" || echo "OK"

# RESEARCH.md §I.8 — JoinValidator integrated in query tool
grep -c "JoinValidator" packages/mcp/src/tradewinds_mcp/tools/query.py | grep -E "^[1-9]" || echo "FAIL: query tool doesn't invoke JoinValidator"

# Phase 5 wheels build cleanly
for whl in dist/tradewinds_mcp-0.2.0-*.whl dist/tradewinds_macro-0.2.0-*.whl; do
  [ -f "$whl" ] || (echo "FAIL: $whl missing" && exit 1)
done
echo "OK"
```
</verification>

<success_criteria>
- [ ] MCP-01 (full, end-to-end): all 5 tools verified across real JSON-RPC subprocess transport.
- [ ] MCP-04 (full, end-to-end): missing/None `as_of` rejected at the JSON-RPC error envelope level; META-TEST from Wave 1 still green.
- [ ] MCP-06 (full, end-to-end): audit JSONL hash matches recomputed sha256 in test; replay reconstructable from audit log.
- [ ] MCP-07 (full, end-to-end): unknown source / unknown schema raise `SourceUnavailableError` / `SchemaValidationError` whose `to_dict()` payload appears in the JSON-RPC error body.
- [ ] MCP-09 (full): same query + same `as_of` = byte-identical TOON for both weather (iem.archive, 10x) and vintage-aware macro (alfred.archive, 10x); Hypothesis property test runs ≥ 20 examples over bounded (source_id, as_of) space.
- [ ] RESEARCH.md §I.8 cross-vertical join enforcement: `JoinValidator` rejects undeclared joins; audit log records rejection with `joins_to_status=undeclared`.
- [ ] CHANGELOG [v0.2.0] section documents all 10 MCP-XX requirements + 2 new distributions + dependency bumps + vertical decision.
- [ ] `.github/workflows/release.yml` extended for `tradewinds-mcp` + `tradewinds-macro` via trusted publishing.
- [ ] `.github/workflows/mcp-tests.yml` extended to test `packages/macro/tests/` alongside `packages/mcp/tests/`.
- [ ] `.planning/phase-05-mcp-data-platform/05-05-RELEASE-CHECKLIST.md` is a complete runbook with ≥ 5 sign-off lines.
- [ ] All 5 distributions build cleanly via `uv build --all`: tradewinds, tradewinds-weather, tradewinds-markets, tradewinds-mcp, tradewinds-macro. No PEP 420 namespace collisions.
- [ ] METADATA `Requires-Dist` for tradewinds-mcp + tradewinds-macro pins `tradewinds>=0.2.0,<0.3` (PKG-03 enforced for new distributions too).
- [ ] Coverage gates: `tradewinds.core` ≥ 90%; `tradewinds_mcp` ≥ 85%; `tradewinds_macro` ≥ 80%.
- [ ] Pre-commit + pre-push hooks green; no `--no-verify`.
- [ ] 2-reviewer loop PASS x2 in ≤ 3 iterations.
- [ ] Branch `phase-5/wave-4/integration-replay-release` merged to `main` via `git merge --no-ff`.
- [ ] User informed: next step is to walk through `05-05-RELEASE-CHECKLIST.md` and run `git tag v0.2.0` manually.
</success_criteria>

<output>
After completion, create `.planning/phase-05-mcp-data-platform/05-05-SUMMARY.md` documenting:

- All 10 MCP-XX requirements verified end-to-end (each with link to the test that proves it)
- JSON-RPC subprocess test outcomes (6 + 4 = 10)
- Deterministic-replay verdict (10 reps + Hypothesis 20 examples = byte-identical)
- Cross-vertical join enforcement working (5 tests)
- Coverage numbers final
- 2-reviewer loop verdict
- Wheel build verification outcomes (5 wheels, no PKG-02 collisions, PKG-03 pins correct)
- Commit hashes
- Merge commit hash on `main`
- v0.2.0 ship-gate status: READY (the user-action tag step is documented in RELEASE-CHECKLIST.md)
- Phase 5 completion: SUMMARY of Phase 5 as a whole (Plans 00-05; total commits; total tests added; new packages; new tools; new catalog entries)
- Downstream signal for v0.3+: hosted-mode (HTTP transport + OAuth) via CallerContext seam; third vertical decision; sports re-evaluation pending 2026-2027 legal landscape; pandas 3.0 migration; agent-DAG enhancement to validator.

After this summary commits, the planner ALSO bumps STATE.md to reflect:
- milestone: v0.2+
- status: planning_complete
- stopped_at: "Phase 5 planning + execution complete; v0.2.0 ship-gate READY; user runs RELEASE-CHECKLIST.md to tag v0.2.0"
- last_activity: "<DATE> -- Phase 5 PLAN-00..PLAN-05 all merged to main; v0.2.0 ready for tag"
</output>
