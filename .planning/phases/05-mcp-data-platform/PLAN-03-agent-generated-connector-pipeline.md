---
phase: 05-mcp-data-platform
plan: 03
type: execute
wave: 3
duration: 2-3 days Claude execution; single lane
waves: 1
depends_on: [phase-05-mcp-data-platform/PLAN-02-catalog-format-weather-entries]
branch_strategy: per-wave; one sub-branch off `main` (`phase-5/wave-3/agent-connector-pipeline`); 2-reviewer loop (codex `high` + python-architect); merges to `main` after promotion CI workflow + dry-run example are both verified end-to-end
requirements:
  - MCP-03    # full — agent-generated connector pipeline + `_generated/` → `catalog/` promotion with CI quality-review gate
autonomous: false   # Pre-merge requires human review of (a) the CONTRIBUTING.md contributor workflow language (it will be the public-facing community contract) AND (b) the CI workflow's gate logic (false positives = legit PRs fail; false negatives = hallucinated entries promote)
files_modified:
  # Connector-generation tooling (helps agents produce well-formed _generated/ entries)
  - packages/mcp/src/tradewinds_mcp/_generated_scaffold.py                            # NEW — scaffold_catalog_entry(source_id, api_doc_url=None) -> dict; produces a meta-schema-valid YAML skeleton with TODO markers for the 5 layers
  - packages/mcp/src/tradewinds_mcp/_generated_validator.py                           # NEW — validate_generated_entry(path: Path) -> ValidationReport; runs jsonschema + Pydantic + schema-id-cross-check + a custom temporal-rules linter
  - packages/mcp/scripts/promote_generated_entry.py                                   # NEW — CLI: mv _generated/X.yaml catalog/X.yaml after running all CI checks locally; for maintainer use
  # CI workflow gating _generated/ promotions
  - .github/workflows/catalog-promotion-gate.yml                                      # NEW — runs on PRs that touch packages/mcp/catalog/*.yaml (excluding _schema/); enforces meta-schema validation + sample-data round-trip (with @pytest.mark.live) + schema-id-resolves-in-registry + temporal-rules linter
  - .github/workflows/mcp-tests.yml                                                   # NEW — runs Wave 1 + 2 + 3 mcp tests on every PR touching packages/mcp/; not live; coverage gate ≥ 85%
  # Docs
  - packages/mcp/CONTRIBUTING.md                                                      # MODIFY — add "How to contribute a generated catalog entry" section (workflow steps, what the gates check, common rejection reasons)
  - packages/mcp/AGENT-CONNECTOR-GUIDE.md                                             # NEW — practical guide for an AI agent producing a `_generated/` entry: scaffold a skeleton, fill the 5 layers, run the local validator, open a PR; includes a concrete worked example from a public API
  - packages/mcp/catalog/_generated/README.md                                         # NEW — terse "this dir holds candidate catalog entries awaiting promotion review"
  # Tests
  - packages/mcp/tests/test_generated_scaffold.py                                     # NEW — scaffold function produces meta-schema-valid YAML skeletons; required fields present with TODO markers
  - packages/mcp/tests/test_generated_validator.py                                    # NEW — validator catches missing field cross-references, schema_id not in Phase 2 REGISTRY, knowledge_time_formula referencing fields not in schema_semantics.fields
  - packages/mcp/tests/test_promotion_script.py                                       # NEW — dry-run mode of promote_generated_entry.py reports what it WOULD do without moving files; --execute moves the file and runs sample-data round-trip live test
  - packages/mcp/tests/test_promotion_gate_workflow_yaml.py                           # NEW — parses .github/workflows/catalog-promotion-gate.yml + asserts it triggers on the expected paths, runs the expected pytest selector, has correct gate jobs
  # Example end-to-end demo (committed as a fixture, not actual catalog content)
  - packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml              # NEW — hand-crafted example "agent-generated" entry for a hypothetical Open-Meteo adapter (NOTE: Open-Meteo is OUT OF SCOPE for v0.1 per CLAUDE.md "Avoid Open-Meteo" — this is purely a fixture; the file lives in tests/fixtures, NOT in catalog/_generated/, to avoid implying we ship a real Open-Meteo adapter)
must_haves:
  truths:
    - "`from tradewinds_mcp._generated_scaffold import scaffold_catalog_entry` returns a dict that, when written to YAML and validated against the meta-schema, PASSES — i.e., the scaffold is meta-schema-valid out of the box (with TODO markers in string fields)."
    - "Scaffold has all 8 top-level fields (source_id, display_name, status, schema_semantics, temporal_rules, quality_notes, relationship_mappings, operational_context) populated with placeholder content."
    - "`validate_generated_entry(path)` returns a `ValidationReport` Pydantic model with fields: `path: Path`, `meta_schema_ok: bool`, `pydantic_ok: bool`, `schema_id_resolves: bool`, `temporal_rules_lint_ok: bool`, `errors: list[str]` (one per failed check), `warnings: list[str]` (advisory)."
    - "Validator catches: schema_id not in Phase 2 REGISTRY (returns `schema_id_resolves: false`); knowledge_time_formula references a field that doesn't appear in `schema_semantics.fields` (returns `temporal_rules_lint_ok: false`); status is `live` but `extraction_config.adapter` doesn't resolve via `tradewinds.weather.catalog.get_adapter` (returns `errors` entry)."
    - "Validator emits WARNINGS (not errors) for: `quality_notes` has fewer than 2 entries; `relationship_mappings.joins_to` is empty (cross-vertical joins not declared); endpoint URL doesn't use HTTPS."
    - "`promote_generated_entry.py --dry-run packages/mcp/catalog/_generated/X.yaml` prints the planned move (`mv _generated/X.yaml catalog/X.yaml`) + the list of CI checks that would run + their expected outcomes."
    - "`promote_generated_entry.py --execute packages/mcp/catalog/_generated/X.yaml` (a) re-runs all validator checks; (b) runs the sample-data live test (`@pytest.mark.live`) against the generated entry; (c) moves the file from `_generated/` to `catalog/` root; (d) emits a one-line audit entry to `$HOME/.tradewinds/mcp-server/catalog-promotions.jsonl` documenting the promotion (date, source_id, promoting user, sha256 of the YAML)."
    - "`.github/workflows/catalog-promotion-gate.yml` triggers on `pull_request` events whose changed files match `packages/mcp/catalog/**/*.yaml` (excluding `_schema/**`). Runs 4 gate jobs: (1) meta-schema validate; (2) Pydantic construct; (3) schema_id-resolves-in-Phase2-registry; (4) temporal-rules lint."
    - "Promotion CI workflow does NOT auto-merge — it runs the gates, surfaces results in PR comments, and BLOCKS merge until all gates green. Human maintainer reviews + clicks merge after the manual sample-data live test (per CONTRIBUTING checklist)."
    - "`packages/mcp/AGENT-CONNECTOR-GUIDE.md` includes a worked example: how an agent would have generated `iem.archive.yaml` from the IEM API docs (using the scaffold helper, then filling in the 5 layers; emphasizes documentation-augmented generation per RESEARCH.md §C.1)."
    - "`packages/mcp/CONTRIBUTING.md` has an expanded 'Contributing a generated catalog entry' section listing: (a) when to use the scaffold; (b) the 5-layer fill-in checklist; (c) running the local validator; (d) opening a PR; (e) what the CI gates check; (f) common rejection reasons (hallucinated field names, missing temporal_rules detail, broken cross-vertical join allow-list)."
    - "`packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml` is a complete, meta-schema-valid example entry that lives in tests/fixtures (NOT in `packages/mcp/catalog/_generated/`) — used by `test_generated_validator.py` as a known-good fixture. CLAUDE.md 'Avoid Open-Meteo' policy is honored: this fixture is for documentation/testing only."
    - "`uv run pytest packages/mcp/tests/ -m \"not live\" -q` exits 0 with all tests passing (Wave 1 + 2 + 3 = ~70 tests)."
  artifacts:
    - path: packages/mcp/src/tradewinds_mcp/_generated_scaffold.py
      provides: "scaffold_catalog_entry(source_id, api_doc_url=None) -> dict — produces a meta-schema-valid YAML skeleton with TODO markers"
      contains: "def scaffold_catalog_entry"
      min_lines: 40
    - path: packages/mcp/src/tradewinds_mcp/_generated_validator.py
      provides: "validate_generated_entry(path) -> ValidationReport; 4 checks (meta-schema / Pydantic / schema-id-resolves / temporal-lint) + warnings"
      contains: "class ValidationReport"
      min_lines: 60
    - path: packages/mcp/scripts/promote_generated_entry.py
      provides: "CLI: re-run validator + live sample-data test + mv file + emit promotion audit"
      contains: "argparse"
    - path: .github/workflows/catalog-promotion-gate.yml
      provides: "Triggers on PRs changing catalog YAMLs; runs 4 gate jobs; blocks merge on gate failure"
      contains: "name: catalog-promotion-gate"
    - path: .github/workflows/mcp-tests.yml
      provides: "Runs MCP fast tests on PRs touching packages/mcp/; coverage gate ≥ 85%"
      contains: "name: mcp-tests"
    - path: packages/mcp/AGENT-CONNECTOR-GUIDE.md
      provides: "Worked example + 5-layer fill-in checklist + when to use scaffold vs when to write by hand"
      contains: "## Worked example"
    - path: packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml
      provides: "Hand-crafted example for known-good fixture testing; NOT a real adapter"
      contains: "source_id: openmeteo.example"
  key_links:
    - from: packages/mcp/src/tradewinds_mcp/_generated_validator.py
      to: packages/core/src/tradewinds/core/schemas/__init__.py
      via: "schema_id_resolves check imports REGISTRY and asserts membership"
      pattern: "from tradewinds\\.core\\.schemas import"
    - from: packages/mcp/scripts/promote_generated_entry.py
      to: packages/mcp/tests/test_catalog_sample_data_roundtrip.py
      via: "promote --execute runs the live sample-data test against the candidate entry"
      pattern: "pytest .* -m live"
    - from: .github/workflows/catalog-promotion-gate.yml
      to: packages/mcp/src/tradewinds_mcp/_generated_validator.py
      via: "CI gate jobs invoke validate_generated_entry; PR blocks until report is all-green"
      pattern: "validate_generated_entry"
---

<objective>
**Wave 3 ships the agent-generated connector pipeline: tooling, a CI gate, and a written community contract.**

Per MCP-03, an AI agent (or a human) can produce a YAML catalog entry from an API doc, drop it into `packages/mcp/catalog/_generated/`, open a PR. The PR runs the 4-check CI gate (meta-schema valid / Pydantic typed / schema_id resolves / temporal-rules linted). If green, a maintainer runs the sample-data live test manually, approves, and the file moves from `_generated/` to `catalog/` root in a follow-up commit. The promotion is logged to a JSONL file for provenance.

**Three deliverables:**

1. **Scaffold helper** — `scaffold_catalog_entry(source_id)` returns a meta-schema-valid YAML skeleton with TODO markers. An agent calls this first, then fills in real content. Reduces hallucination of field names because the scaffold matches the meta-schema exactly.

2. **Validator** — `validate_generated_entry(path)` runs 4 checks: jsonschema meta-schema validation, Pydantic typing, schema_id resolves in Phase 2 REGISTRY, temporal-rules linter (knowledge_time_formula references only fields declared in `schema_semantics.fields`). Plus 3 warnings (sparse quality_notes, empty joins_to, non-HTTPS endpoint).

3. **Promotion machinery** — a CI workflow that runs the validator on every PR touching catalog YAMLs (`.github/workflows/catalog-promotion-gate.yml`) + a maintainer-side CLI (`promote_generated_entry.py`) that re-runs everything plus the live sample-data round-trip + emits a promotion audit entry.

**Why a Wave on its own?** Wave 2 ships the catalog and 7 hand-curated entries. Wave 3 turns the catalog into something that GROWS — community contributions, agent-generated additions, all going through a real gate. Without this gate, RESEARCH.md §I.4's 15% hallucination rate kills the catalog's signal-to-noise within a few PRs.

**The community-contract piece (CONTRIBUTING.md + AGENT-CONNECTOR-GUIDE.md):** equally important as the code. The pipeline is only useful if contributors understand it. The guide includes a worked example (re-deriving iem.archive.yaml from IEM docs) so a human or agent reading it has a concrete template.

**Out of scope (deferred):**
- Wave 4: second-vertical adapter (FRED+ALFRED+Kalshi macro) — Wave 3's pipeline will be the way that ships, but the actual PRs land in Wave 4.
- Wave 4: end-to-end JSON-RPC subprocess + deterministic-replay tests.
- v0.3+: separate `tradewinds-catalog` repo if catalog grows past O(100) entries; documentation-augmented generation (DAG) embedded in the agent flow; automated cross-source join validation.

**Out of scope (FORBIDDEN — clarified):**
- No actual Open-Meteo adapter (CLAUDE.md "Avoid Open-Meteo" — licensing). The Open-Meteo example in `tests/fixtures/example_generated/` is documentation only; NOT a catalog entry. Reviewers must verify this file's location during the review.

**Output:** A community-grade catalog contribution pipeline ready for Wave 4's macro vertical to use as its delivery vehicle. After Wave 3 merges, generating a new catalog entry is a documented, gated workflow rather than a hand-curated artifact.
</objective>

<execution_context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/REVIEW-DISCIPLINE.md
@.planning/phases/05-mcp-data-platform/CONTEXT.md
@.planning/phases/05-mcp-data-platform/RESEARCH.md
@.planning/phases/05-mcp-data-platform/05-02-SUMMARY.md
@./CLAUDE.md
</execution_context>

<interfaces>
From Wave 2 (PLAN-02 output):

```python
# tradewinds_mcp.catalog
class CatalogLoader:
    @classmethod
    def from_dir(cls, path) -> "CatalogLoader": ...
    def all_source_ids(self) -> list[str]: ...
    def lookup(self, source_id: str) -> CatalogEntry: ...

# tradewinds_mcp._catalog_entry_types
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

# Meta-schema location
# packages/mcp/catalog/_schema/catalog_entry.schema.json (JSON Schema 2020-12)

# Phase 2 schema registry (for schema_id-resolves check)
from tradewinds.core.schemas import REGISTRY  # dict[str, Schema]
# Available IDs: "schema.observation.v1", "schema.forecast.iem_mos.v1", "schema.settlement.cli.v1"
```

GitHub Actions context:
- Repo uses `astral-sh/setup-uv` action (Phase 4 establishes; mirror that)
- `uv sync` + `uv run pytest -m "not live" -q` is the standard pattern
- PR check name `catalog-promotion-gate` must appear in branch protection rules (post-Wave-3 task for repo admin)
</interfaces>

<phase_summary>

**Goal:** Ship the agent-connector pipeline: scaffold + validator + promotion CLI + CI gate + contributor docs.

**Branch:** `phase-5/wave-3/agent-connector-pipeline` off `main`.

**Atomic commit boundaries:**
- Task 3.1 (scaffold + validator + 4 checks) → 2 commits (RED + GREEN)
- Task 3.2 (promotion CLI + audit log) → 2 commits
- Task 3.3 (CI workflows + branch-protection note) → 1 commit
- Task 3.4 (CONTRIBUTING + AGENT-CONNECTOR-GUIDE + example fixture) → 1 commit
- Task 3.5 (pre-merge gate) → 1 commit

**2-reviewer loop:** codex `high` + python-architect. The CI workflow YAML is schema-fragment-bearing per REVIEW-DISCIPLINE.md never-skip list (a typo in `runs-on:` value silently disables the gate).

**Pre-merge gate:**
1. All MCP tests green (Wave 1 + 2 + 3).
2. CI workflow YAMLs validate (e.g., via `actionlint` or `yamllint`).
3. Dry-run promotion against the example fixture (`promote_generated_entry.py --dry-run tests/fixtures/example_generated/openmeteo.example.yaml`) outputs the expected plan.
4. End-to-end smoke: scaffold → fill in 1 layer → validator reports the missing layers → fill in all 5 → validator green → mock-promote.
5. Pre-commit + pre-push hooks green.
6. 2-reviewer loop PASS x2.

</phase_summary>

<tasks>

<task type="auto" tdd="true">
  <name>Task 3.1: Scaffold + Validator with 4 checks + 3 warnings (RED tests FIRST)</name>
  <files>packages/mcp/src/tradewinds_mcp/_generated_scaffold.py, packages/mcp/src/tradewinds_mcp/_generated_validator.py, packages/mcp/tests/test_generated_scaffold.py, packages/mcp/tests/test_generated_validator.py, packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml</files>
  <implements>MCP-03 (partial — generation + validation tooling)</implements>
  <read_first>
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§C.2 — quality-review gate table; columns "Automated? + How" map directly to the 4 checks; §I.4 — hallucination mitigation via sample-data round-trip; §C.1 — dlt's discover-then-tune pattern)
    - packages/mcp/catalog/_schema/catalog_entry.schema.json (Task 2.1 output — meta-schema; the scaffold must produce a dict that validates against this)
    - packages/mcp/src/tradewinds_mcp/catalog.py (Task 2.2 output — CatalogLoader; the validator reuses jsonschema + Pydantic logic)
    - packages/core/src/tradewinds/core/schemas/__init__.py (Phase 2 — REGISTRY for schema_id-resolves check)
    - CLAUDE.md (TDD; "Avoid Open-Meteo" — the fixture is documentation, not a catalog entry)
  </read_first>
  <behavior>
    Tests to write FIRST:

    `packages/mcp/tests/test_generated_scaffold.py` (5 tests):

    1. `test_scaffold_produces_meta_schema_valid_dict`: `scaffold_catalog_entry("acme.example")` returns a dict; when serialized to YAML and re-parsed, it validates against `catalog_entry.schema.json`.
    2. `test_scaffold_has_all_top_level_fields`: result dict has keys `{source_id, display_name, status, schema_semantics, temporal_rules, quality_notes, relationship_mappings, operational_context}`.
    3. `test_scaffold_source_id_passes_through`: `scaffold_catalog_entry("acme.example")["source_id"] == "acme.example"`.
    4. `test_scaffold_status_defaults_to_wip`: `result["status"] == "wip"` (new entries default to WIP; promotion moves them to `live`).
    5. `test_scaffold_strings_have_todo_markers`: every string field (display_name, knowledge_time_formula, etc.) contains the string `TODO` or `<...>` to make missing fills obvious to the agent / contributor.

    `packages/mcp/tests/test_generated_validator.py` (10 tests):

    1. `test_validator_returns_validation_report`: `validate_generated_entry(Path("tests/fixtures/example_generated/openmeteo.example.yaml"))` returns a `ValidationReport` instance.
    2. `test_validator_known_good_fixture_all_green`: the openmeteo.example.yaml fixture (hand-crafted to be meta-schema-perfect, schema_id-resolving, temporal-rules-consistent) produces a report with `meta_schema_ok=True`, `pydantic_ok=True`, `schema_id_resolves=True`, `temporal_rules_lint_ok=True`, `errors=[]`.
    3. `test_validator_catches_missing_block`: produce a malformed entry by deep-copying the fixture and removing `temporal_rules`; validator returns `meta_schema_ok=False` with an error message naming `temporal_rules`.
    4. `test_validator_catches_typo_field_name`: deep-copy fixture, rename `temporal_rules` → `temporal_rule` (typo). `meta_schema_ok=False`; error message names the typo.
    5. `test_validator_catches_unknown_schema_id`: set `schema_semantics.schema_id = "schema.fake.v99"`. `schema_id_resolves=False`; error message lists the available IDs from the Phase 2 REGISTRY.
    6. `test_validator_catches_temporal_rules_lint_failure`: set `knowledge_time_formula = "phantom_field + some_delay"` while `schema_semantics.fields` contains only `tmpf`, `relh`, `observed_at`, `knowledge_time`. The linter scans the formula for field names and asserts each cited field appears in `fields`. Returns `temporal_rules_lint_ok=False`.
    7. `test_validator_warns_on_sparse_quality_notes`: fixture with `quality_notes: ["only one note"]` (< 2 entries) produces `warnings` entry; errors stay empty (still passes).
    8. `test_validator_warns_on_empty_joins_to`: fixture with `relationship_mappings.joins_to: []` produces a warning ("cross-vertical joins not declared — agent may produce wrong rows"); errors stay empty.
    9. `test_validator_warns_on_non_https_endpoint`: fixture with `operational_context.endpoint: "http://example.com"` produces a warning; errors stay empty.
    10. `test_validator_errors_on_live_status_without_adapter`: fixture with `status: live` but no `extraction_config.adapter` (or one that doesn't resolve via Phase 2's `get_adapter`) returns an error.

    Run `uv run pytest packages/mcp/tests/test_generated_scaffold.py packages/mcp/tests/test_generated_validator.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Create the example fixture `packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml`. This file is meta-schema-perfect, status=wip (because Open-Meteo is forbidden in v0.1 per CLAUDE.md), schema_id references something that DOES NOT need to be in Phase 2 REGISTRY (use a synthetic `schema.observation.v1` reference — the file is purely a test fixture, NOT a real adapter). Document in the file's YAML comment header that this is a test fixture, not a real catalog entry.

    ```yaml
    # NOTE: This file is a TEST FIXTURE for tradewinds_mcp._generated_validator.
    # It is NOT a real catalog entry. Open-Meteo is OUT OF SCOPE for v0.1 per CLAUDE.md
    # (licensing). This fixture demonstrates the meta-schema shape only — DO NOT copy
    # it to packages/mcp/catalog/_generated/.
    $schema: ../../../catalog/_schema/catalog_entry.schema.json
    source_id: openmeteo.example
    display_name: "Open-Meteo — EXAMPLE TEST FIXTURE (not a real adapter)"
    status: wip

    schema_semantics:
      schema_id: schema.observation.v1
      fields:
        temperature_2m: "Air temperature at 2m AGL, Celsius. Hourly granularity."
        observed_at: "Event time (UTC); hour of observation"
        knowledge_time: "Knowledge time (UTC); observed_at + Open-Meteo publish delay (typically 30 min)"

    temporal_rules:
      event_time_field: observed_at
      knowledge_time_field: knowledge_time
      knowledge_time_formula: "observed_at + 30min publish delay (test-fixture value)"
      backfill_behavior: "Open-Meteo backfills past records with new ERA5 reanalysis cycles; mark vintage_aware: true if used in production (DO NOT use in v0.1 — licensing)"
      vintage_aware: false

    quality_notes:
      - "TEST FIXTURE — do not treat as real catalog content. Open-Meteo licensing forbids redistribution in tradewinds v0.1."
      - "Real Open-Meteo adapter would need licensing clearance + a v0.x+ scoping decision."

    relationship_mappings:
      joins_to: []

    operational_context:
      endpoint: "https://api.open-meteo.com/v1/forecast"
      rate_limit: "10000 req/day (free tier; documented)"
      auth: "none"
      pagination: "single response; no pagination"
      http_timeout_seconds: 30

    extraction_config:
      adapter: openmeteo.example
    ```

    Step 2 — Write the 15 tests above. Commit RED.

    Step 3 — Implement `packages/mcp/src/tradewinds_mcp/_generated_scaffold.py`:

    ```python
    """Scaffold for agent-generated catalog entries.

    Produces a meta-schema-valid YAML skeleton an agent can fill in.
    All string fields carry TODO markers so missing fills are visually obvious.
    Defaults to status=wip — promotion moves it to status=live after review.
    """

    from __future__ import annotations

    from typing import Any

    __all__ = ["scaffold_catalog_entry"]


    def scaffold_catalog_entry(source_id: str, api_doc_url: str | None = None) -> dict[str, Any]:
        """Return a meta-schema-valid catalog-entry skeleton."""
        return {
            "source_id": source_id,
            "display_name": f"TODO: human-readable name for {source_id}",
            "status": "wip",
            "schema_semantics": {
                "schema_id": "TODO: schema ID from tradewinds.core.schemas (e.g. schema.observation.v1)",
                "fields": {
                    "TODO_field_name": "TODO: per-field human-readable description — what does this field MEAN in domain terms?",
                },
            },
            "temporal_rules": {
                "event_time_field": "TODO: column name holding the event timestamp",
                "knowledge_time_field": "TODO: column name holding the knowledge timestamp",
                "knowledge_time_formula": "TODO: human-readable formula for how knowledge_time is computed from raw API response",
                "backfill_behavior": "TODO: does this source backfill past records? Critical for replay determinism",
                "vintage_aware": False,
            },
            "quality_notes": [
                "TODO: at least 2 domain-knowledge notes a quant should know before using this source",
                "TODO: known unit changes, sensor swaps, units-of-record, latency caveats",
            ],
            "relationship_mappings": {
                "joins_to": [
                    # Empty by default — agent fills in pre-declared joins from the catalog's allow-list pattern
                ],
            },
            "operational_context": {
                "endpoint": api_doc_url or "TODO: base URL or API host",
                "rate_limit": "TODO: documented or empirical rate limit",
                "auth": "TODO: 'none' | 'api_key:ENV_VAR_NAME' | 'oauth'",
                "pagination": "TODO: pagination strategy",
                "http_timeout_seconds": 60,
            },
            "extraction_config": {
                "adapter": "TODO: Phase 2 catalog adapter source ID or _generated/X.yaml reference",
            },
        }
    ```

    Step 4 — Implement `packages/mcp/src/tradewinds_mcp/_generated_validator.py`:

    ```python
    """Validator for agent-generated catalog entries.

    4 checks (errors block promotion):
    1. meta_schema_ok — jsonschema validation against catalog_entry.schema.json
    2. pydantic_ok — CatalogEntry Pydantic construction
    3. schema_id_resolves — schema_semantics.schema_id is in tradewinds.core.schemas.REGISTRY
    4. temporal_rules_lint_ok — knowledge_time_formula references only fields in schema_semantics.fields

    3 warnings (advisory):
    - sparse_quality_notes — < 2 entries
    - empty_joins_to — relationship_mappings.joins_to is empty (cross-vertical joins not declared)
    - non_https_endpoint — endpoint URL does not start with https://

    Used both by the local CLI (promote_generated_entry.py) and the CI gate.
    """

    from __future__ import annotations

    import json
    import re
    from pathlib import Path
    from typing import Any

    import jsonschema
    import yaml
    from pydantic import BaseModel

    from tradewinds.core.schemas import REGISTRY as SCHEMA_REGISTRY
    from ._catalog_entry_types import CatalogEntry

    __all__ = ["ValidationReport", "validate_generated_entry"]


    _META_SCHEMA_PATH = Path("packages/mcp/catalog/_schema/catalog_entry.schema.json")


    class ValidationReport(BaseModel):
        path: Path
        meta_schema_ok: bool
        pydantic_ok: bool
        schema_id_resolves: bool
        temporal_rules_lint_ok: bool
        adapter_resolves: bool   # true if status=live and adapter resolves; or status=wip (vacuously true)
        errors: list[str]
        warnings: list[str]

        @property
        def all_green(self) -> bool:
            return (
                self.meta_schema_ok
                and self.pydantic_ok
                and self.schema_id_resolves
                and self.temporal_rules_lint_ok
                and self.adapter_resolves
                and not self.errors
            )


    def validate_generated_entry(path: Path) -> ValidationReport:
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            raw: Any = yaml.safe_load(f)

        errors: list[str] = []
        warnings: list[str] = []

        # 1. meta-schema validation
        meta_schema_ok = True
        with _META_SCHEMA_PATH.open("r", encoding="utf-8") as f:
            meta_schema = json.load(f)
        validator = jsonschema.Draft202012Validator(meta_schema)
        ms_errors = list(validator.iter_errors(raw))
        if ms_errors:
            meta_schema_ok = False
            for e in ms_errors:
                errors.append(f"meta-schema: {'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}")

        # 2. Pydantic construction
        pydantic_ok = True
        entry: CatalogEntry | None = None
        try:
            entry = CatalogEntry(**raw)
        except Exception as exc:
            pydantic_ok = False
            errors.append(f"pydantic: {exc}")

        # 3. schema_id resolves in Phase 2 REGISTRY
        schema_id_resolves = True
        if entry is not None and not entry.source_id.startswith("kalshi."):
            sid = entry.schema_semantics.schema_id
            if sid not in SCHEMA_REGISTRY:
                schema_id_resolves = False
                errors.append(
                    f"schema_id_resolves: '{sid}' not in tradewinds.core.schemas.REGISTRY. "
                    f"Available: {sorted(SCHEMA_REGISTRY.keys())}"
                )

        # 4. temporal_rules linter: knowledge_time_formula references only fields in schema_semantics.fields
        temporal_rules_lint_ok = True
        if entry is not None:
            formula = entry.temporal_rules.knowledge_time_formula
            declared_fields = set(entry.schema_semantics.fields.keys())
            # Heuristic: extract identifier-shaped tokens; check that each token that looks like a field is declared.
            # We deliberately don't try full expression parsing — false positives surface as warnings.
            tokens = set(re.findall(r"\b[a-z_][a-z_0-9]*\b", formula))
            field_like_tokens = {t for t in tokens if "_" in t or len(t) > 3}  # heuristic
            # Skip common English words
            ENGLISH = {"after", "before", "and", "or", "the", "per", "min", "sec", "hour", "day",
                       "delay", "publish", "typical", "typically", "report", "delta", "for", "asof",
                       "true", "false", "vintage", "knowledge", "event"}
            undeclared = (field_like_tokens - ENGLISH) - declared_fields
            # Also subtract well-known Phase 2 column names that may appear without being in the per-source `fields` declaration
            PHASE2_COLUMNS = {"source", "retrieved_at", "event_time", "knowledge_time"}
            undeclared -= PHASE2_COLUMNS
            if undeclared:
                temporal_rules_lint_ok = False
                errors.append(
                    f"temporal_rules_lint: knowledge_time_formula references fields not declared in schema_semantics.fields: {sorted(undeclared)}"
                )

        # 5. adapter resolves (only if status=live)
        adapter_resolves = True
        if entry is not None and entry.status == "live":
            adapter_id = (entry.extraction_config.adapter if entry.extraction_config else None) or entry.source_id
            if not adapter_id.startswith("kalshi."):
                try:
                    from tradewinds.weather.catalog import get_adapter
                    get_adapter(adapter_id)
                except Exception as exc:
                    adapter_resolves = False
                    errors.append(f"adapter_resolves: status=live but adapter '{adapter_id}' does not resolve: {exc}")

        # WARNINGS (advisory)
        if entry is not None:
            if len(entry.quality_notes) < 2:
                warnings.append(f"sparse_quality_notes: only {len(entry.quality_notes)} entries (recommend ≥2)")
            if not entry.relationship_mappings.joins_to:
                warnings.append("empty_joins_to: relationship_mappings.joins_to is empty (cross-vertical joins not declared)")
            endpoint = entry.operational_context.endpoint or ""
            if endpoint and not endpoint.startswith("https://"):
                warnings.append(f"non_https_endpoint: {endpoint!r} should use https://")

        return ValidationReport(
            path=path,
            meta_schema_ok=meta_schema_ok,
            pydantic_ok=pydantic_ok,
            schema_id_resolves=schema_id_resolves,
            temporal_rules_lint_ok=temporal_rules_lint_ok,
            adapter_resolves=adapter_resolves,
            errors=errors,
            warnings=warnings,
        )
    ```

    Step 5 — Run `uv run pytest packages/mcp/tests/test_generated_scaffold.py packages/mcp/tests/test_generated_validator.py -x -v` — all 15 tests MUST pass.

    Step 6 — Commit (GREEN): `feat(phase-5): scaffold + validator (4 checks + 3 warnings) for agent-generated catalog entries (MCP-03 partial GREEN)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_generated_scaffold.py packages/mcp/tests/test_generated_validator.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/src/tradewinds_mcp/_generated_scaffold.py` returns 0
    - `test -f packages/mcp/src/tradewinds_mcp/_generated_validator.py` returns 0
    - `test -f packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml` returns 0
    - `grep -c "def scaffold_catalog_entry" packages/mcp/src/tradewinds_mcp/_generated_scaffold.py` returns 1
    - `grep -c "class ValidationReport" packages/mcp/src/tradewinds_mcp/_generated_validator.py` returns 1
    - `grep -c "def validate_generated_entry" packages/mcp/src/tradewinds_mcp/_generated_validator.py` returns 1
    - `grep -c "from tradewinds.core.schemas import REGISTRY" packages/mcp/src/tradewinds_mcp/_generated_validator.py` returns 1
    - `grep -c "from tradewinds.weather.catalog import get_adapter" packages/mcp/src/tradewinds_mcp/_generated_validator.py` returns 1
    - `grep -c "TEST FIXTURE" packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml` returns ≥ 1 (Open-Meteo policy honored)
    - `grep -c "status: wip" packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml` returns 1 (cannot be live per CLAUDE.md)
    - Fixture is NOT in catalog/_generated/: `test ! -f packages/mcp/catalog/_generated/openmeteo.example.yaml` exit 0
    - `uv run pytest packages/mcp/tests/test_generated_scaffold.py packages/mcp/tests/test_generated_validator.py -x -v` exits 0 with 15 passed
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    Scaffold produces meta-schema-valid skeleton with TODO markers. Validator runs 4 checks + 3 warnings against `tests/fixtures/example_generated/openmeteo.example.yaml` (status=wip; Open-Meteo policy honored). 15 tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3.2: Promotion CLI (promote_generated_entry.py) + audit log (RED tests FIRST)</name>
  <files>packages/mcp/scripts/promote_generated_entry.py, packages/mcp/tests/test_promotion_script.py</files>
  <implements>MCP-03 (promotion step)</implements>
  <read_first>
    - Task 3.1 outputs (scaffold + validator)
    - packages/mcp/src/tradewinds_mcp/audit.py (Wave 1 — AuditLogger pattern for the new catalog-promotions.jsonl)
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§C.3 — PR-based contribution model, two-step promotion: CI gates green → maintainer moves file)
  </read_first>
  <behavior>
    Tests in `packages/mcp/tests/test_promotion_script.py` (5 tests):

    1. `test_dry_run_reports_planned_move`: copy fixture to a temp _generated/ dir; run `promote_generated_entry.py --dry-run <path>` (via subprocess or direct function call); stdout contains "would move" + source path + dest path; no actual `mv` happens.
    2. `test_dry_run_lists_gates_to_run`: dry-run output mentions all 4 gates by name (`meta_schema_ok, pydantic_ok, schema_id_resolves, temporal_rules_lint_ok`).
    3. `test_execute_blocks_on_validator_error`: deep-copy fixture, set status=live without adapter (forces `adapter_resolves=False`); run `--execute`. Script returns non-zero exit code; emits an error message naming the failing gate; does NOT move the file.
    4. `test_execute_moves_file_when_all_green`: hand-craft a known-good entry that does pass all 4 gates (use a known Phase 2 source like `iem.archive` with status=live + adapter=iem.archive); place at temp _generated/; run `--execute --skip-live` (don't actually hit the network for the live sample-data test in unit-test context). File moves; promotion audit entry appears in `$HOME/.tradewinds/mcp-server/catalog-promotions.jsonl`.
    5. `test_audit_entry_format`: after a successful promotion, the JSONL line has fields `{ts, source_id, sha256_of_yaml, promoting_user, validator_summary}`; sort_keys-alphabetized.

    Run `uv run pytest packages/mcp/tests/test_promotion_script.py -x` — MUST fail. Commit RED.
  </behavior>
  <action>
    Step 1 — Write the 5 tests. Commit RED.

    Step 2 — Implement `packages/mcp/scripts/promote_generated_entry.py`:

    ```python
    #!/usr/bin/env python3
    """promote_generated_entry — move a catalog entry from _generated/ to catalog/ root.

    Usage:
      promote_generated_entry.py --dry-run <path-to-_generated-yaml>
      promote_generated_entry.py --execute <path-to-_generated-yaml> [--skip-live]

    Workflow:
      1. Run validator (4 checks + 3 warnings).
      2. If --execute: also run sample-data live test (unless --skip-live).
      3. If all green: move file from _generated/ to catalog/ root.
      4. Emit promotion audit entry to ~/.tradewinds/mcp-server/catalog-promotions.jsonl.
    """

    from __future__ import annotations

    import argparse
    import getpass
    import hashlib
    import json
    import os
    import shutil
    import subprocess
    import sys
    from datetime import datetime, timezone
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

    from tradewinds_mcp._generated_validator import validate_generated_entry  # noqa: E402


    def main() -> int:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("path", type=Path, help="Path to candidate YAML in _generated/")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--dry-run", action="store_true")
        group.add_argument("--execute", action="store_true")
        parser.add_argument("--skip-live", action="store_true",
                            help="Skip the live sample-data round-trip test (used in unit tests; FORBIDDEN for real promotions)")
        args = parser.parse_args()

        report = validate_generated_entry(args.path)
        print(f"Validation report for {args.path}:")
        print(f"  meta_schema_ok       : {report.meta_schema_ok}")
        print(f"  pydantic_ok          : {report.pydantic_ok}")
        print(f"  schema_id_resolves   : {report.schema_id_resolves}")
        print(f"  temporal_rules_lint  : {report.temporal_rules_lint_ok}")
        print(f"  adapter_resolves     : {report.adapter_resolves}")
        if report.errors:
            print("ERRORS:")
            for e in report.errors:
                print(f"  - {e}")
        if report.warnings:
            print("WARNINGS:")
            for w in report.warnings:
                print(f"  - {w}")

        if not report.all_green:
            print("Promotion BLOCKED — fix errors above.")
            return 1

        # Plan the move
        src = args.path
        dest = src.parent.parent / src.name  # _generated/X.yaml -> catalog/X.yaml
        print(f"Planned move: {src} -> {dest}")
        print("Gates to run on --execute: meta_schema, pydantic, schema_id_resolves, temporal_rules_lint, adapter_resolves, sample-data-live (unless --skip-live)")

        if args.dry_run:
            print("--dry-run; no changes made.")
            return 0

        # --execute path
        if not args.skip_live:
            print("Running sample-data live test ...")
            result = subprocess.run(
                ["uv", "run", "pytest",
                 "packages/mcp/tests/test_catalog_sample_data_roundtrip.py",
                 "-m", "live", "-v", "-k", src.stem],
                check=False,
            )
            if result.returncode != 0:
                print("Live sample-data test FAILED — promotion blocked.")
                return 2

        # Move the file
        shutil.move(str(src), str(dest))

        # Emit promotion audit
        audit_dir = Path.home() / ".tradewinds" / "mcp-server"
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / "catalog-promotions.jsonl"
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source_id": dest.stem,
            "sha256_of_yaml": sha,
            "promoting_user": os.environ.get("USER", "") or getpass.getuser(),
            "validator_summary": report.model_dump(mode="json"),
        }
        line = json.dumps(entry, sort_keys=True) + "\n"
        with audit_path.open("a", encoding="utf-8") as f:
            f.write(line)
        print(f"Promotion audit emitted to {audit_path}")
        print(f"Moved {src.name} from _generated/ to catalog/ root.")
        return 0


    if __name__ == "__main__":
        sys.exit(main())
    ```

    Step 3 — Make the script executable: `chmod +x packages/mcp/scripts/promote_generated_entry.py`. Add a `[tool.hatch.build.targets.wheel.force-include]` entry to the mcp pyproject if we want this shipped with the wheel (probably YES — maintainer-facing tool).

    Step 4 — Run `uv run pytest packages/mcp/tests/test_promotion_script.py -x -v` — all 5 tests MUST pass.

    Step 5 — Commit (GREEN): `feat(phase-5): promote_generated_entry CLI + catalog-promotions.jsonl audit log (MCP-03 promotion-step GREEN)`.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_promotion_script.py -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/scripts/promote_generated_entry.py` returns 0
    - `test -x packages/mcp/scripts/promote_generated_entry.py` returns 0 (executable bit set)
    - `grep -c "validate_generated_entry" packages/mcp/scripts/promote_generated_entry.py` returns ≥ 1
    - `grep -c "catalog-promotions.jsonl" packages/mcp/scripts/promote_generated_entry.py` returns 1
    - `grep -c "sort_keys=True" packages/mcp/scripts/promote_generated_entry.py` returns 1
    - `grep -c "--dry-run" packages/mcp/scripts/promote_generated_entry.py` returns ≥ 1
    - `grep -c "--execute" packages/mcp/scripts/promote_generated_entry.py` returns ≥ 1
    - `grep -c "--skip-live" packages/mcp/scripts/promote_generated_entry.py` returns ≥ 1
    - `uv run python packages/mcp/scripts/promote_generated_entry.py --dry-run packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml` exits 0 (or with the expected error report; either way it does not crash)
    - `uv run pytest packages/mcp/tests/test_promotion_script.py -x -v` exits 0 with 5 passed
    - Two commits on the branch (RED + GREEN)
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    `promote_generated_entry.py` runs validator + (optional) live test + mv + audit. --dry-run is safe; --execute requires all-green report. Promotion audit JSONL alphabetized. 5 tests pass.
  </done>
</task>

<task type="auto">
  <name>Task 3.3: CI workflows — catalog-promotion-gate + mcp-tests</name>
  <files>.github/workflows/catalog-promotion-gate.yml, .github/workflows/mcp-tests.yml, packages/mcp/tests/test_promotion_gate_workflow_yaml.py</files>
  <implements>MCP-03 (CI gate)</implements>
  <read_first>
    - Task 3.1 + 3.2 outputs (validator + promotion CLI)
    - .planning/phase-04-coverage-docs-cicd-release/ — TBD; if Phase 4 hasn't shipped, base workflow on the astral-sh trusted-publishing-examples pattern referenced in CLAUDE.md CI section
    - .planning/REVIEW-DISCIPLINE.md (CI YAML is schema-fragment-bearing — typos disable gates silently)
    - CLAUDE.md (CI-04 — live tests excluded from CI; CI-03 — pre-commit hooks; CI uses `uv` toolchain)
  </read_first>
  <action>
    Step 1 — Create `.github/workflows/catalog-promotion-gate.yml`:

    ```yaml
    name: catalog-promotion-gate

    on:
      pull_request:
        paths:
          - "packages/mcp/catalog/**/*.yaml"
          - "!packages/mcp/catalog/_schema/**"

    jobs:
      validate-catalog-changes:
        name: Validate catalog YAML changes
        runs-on: ubuntu-latest
        steps:
          - name: Checkout
            uses: actions/checkout@v4
            with:
              fetch-depth: 0  # need history for git diff vs base

          - name: Install uv
            uses: astral-sh/setup-uv@v3
            with:
              version: "latest"

          - name: Set up Python
            run: uv python install 3.11

          - name: Install workspace
            run: uv sync

          - name: List changed catalog YAML files
            id: changed
            run: |
              # Compare to PR base (origin/${{ github.base_ref }}); fall back to HEAD~1 if missing
              git fetch origin "${{ github.base_ref }}" --depth=1 || true
              base="origin/${{ github.base_ref }}"
              if ! git rev-parse --verify "$base" >/dev/null 2>&1; then
                base="HEAD~1"
              fi
              files=$(git diff --name-only "$base" -- 'packages/mcp/catalog/**/*.yaml' | grep -v '_schema/' || true)
              if [ -z "$files" ]; then
                echo "No catalog YAML changes; skipping."
                echo "files=" >> "$GITHUB_OUTPUT"
              else
                # Newline-escape for the matrix consumer
                {
                  echo "files<<EOF"
                  echo "$files"
                  echo "EOF"
                } >> "$GITHUB_OUTPUT"
              fi

          - name: Run validator on each changed file
            if: steps.changed.outputs.files != ''
            run: |
              echo "Changed files:"
              echo "${{ steps.changed.outputs.files }}"
              echo
              failed=0
              while IFS= read -r f; do
                [ -z "$f" ] && continue
                echo "=== Validating $f ==="
                if ! uv run python -c "
              import sys
              from pathlib import Path
              from tradewinds_mcp._generated_validator import validate_generated_entry
              r = validate_generated_entry(Path('$f'))
              print(r.model_dump_json(indent=2))
              sys.exit(0 if r.all_green else 1)
              "; then
                  failed=1
                fi
              done <<< "${{ steps.changed.outputs.files }}"
              exit $failed

          - name: Comment on PR with validator report
            if: failure() && steps.changed.outputs.files != ''
            uses: actions/github-script@v7
            with:
              script: |
                github.rest.issues.createComment({
                  issue_number: context.issue.number,
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  body: '`catalog-promotion-gate` failed. See the workflow log for the full validator report. Common fixes: ensure all 5 layers are populated; verify schema_id is in tradewinds.core.schemas registry; check that knowledge_time_formula only references fields in schema_semantics.fields.'
                })
    ```

    Step 2 — Create `.github/workflows/mcp-tests.yml`:

    ```yaml
    name: mcp-tests

    on:
      pull_request:
        paths:
          - "packages/mcp/**"
          - "packages/core/**"   # KnowledgeView / Schema / formats — MCP depends on these
          - ".github/workflows/mcp-tests.yml"
      push:
        branches:
          - main

    jobs:
      test:
        runs-on: ubuntu-latest
        strategy:
          matrix:
            python-version: ["3.11", "3.12", "3.13"]
        steps:
          - uses: actions/checkout@v4

          - name: Install uv
            uses: astral-sh/setup-uv@v3

          - name: Set up Python ${{ matrix.python-version }}
            run: uv python install ${{ matrix.python-version }}

          - name: Sync workspace
            run: uv sync

          - name: Run MCP fast tests
            run: uv run pytest packages/mcp/tests/ -m "not live" -v

          - name: Coverage on tradewinds_mcp
            run: |
              uv run pytest --cov=tradewinds_mcp --cov-branch --cov-report=term-missing packages/mcp/tests/ -q
              # Phase 5 deep_work_rules: bar is 85% on packages/mcp/
              coverage_pct=$(uv run python -c "
              import re, subprocess
              out = subprocess.check_output(['uv','run','pytest','--cov=tradewinds_mcp','--cov-branch','-q','--no-header','--no-summary','packages/mcp/tests/'], text=True, stderr=subprocess.STDOUT)
              m = re.search(r'TOTAL.*?(\d+)%', out)
              print(m.group(1) if m else '0')
              ")
              echo "Coverage: ${coverage_pct}%"
              if [ "${coverage_pct}" -lt 85 ]; then
                echo "Coverage ${coverage_pct}% < 85% bar"
                exit 1
              fi
    ```

    Step 3 — Write `packages/mcp/tests/test_promotion_gate_workflow_yaml.py` (4 tests):

    ```python
    """Test that the CI workflow YAML files are well-formed and trigger correctly.

    These are static checks against the YAML — actual CI runs are not invoked here.
    """
    from pathlib import Path
    import yaml

    _PROMOTION_GATE = Path(".github/workflows/catalog-promotion-gate.yml")
    _MCP_TESTS = Path(".github/workflows/mcp-tests.yml")


    def test_promotion_gate_workflow_exists():
        assert _PROMOTION_GATE.exists()


    def test_promotion_gate_triggers_on_catalog_yaml_changes():
        with _PROMOTION_GATE.open("r", encoding="utf-8") as f:
            wf = yaml.safe_load(f)
        triggers = wf.get(True) or wf.get("on")  # PyYAML quirk: bare `on:` parses as True
        assert "pull_request" in triggers
        paths = triggers["pull_request"]["paths"]
        assert any("packages/mcp/catalog/**" in p for p in paths)
        assert any("_schema" in p and p.startswith("!") for p in paths), "schema dir excluded"


    def test_promotion_gate_runs_validator():
        text = _PROMOTION_GATE.read_text(encoding="utf-8")
        assert "validate_generated_entry" in text, "workflow must invoke the validator"


    def test_mcp_tests_workflow_runs_pytest():
        text = _MCP_TESTS.read_text(encoding="utf-8")
        assert "pytest packages/mcp/tests/" in text
        assert 'm "not live"' in text or "m 'not live'" in text, "live tests excluded from CI per CI-04"
    ```

    Step 4 — Optional: install `actionlint` to lint the workflows locally (`brew install actionlint` or skip if not available). Run `actionlint .github/workflows/*.yml` and fix any issues. Even without actionlint, `yamllint` from pre-commit will catch obvious YAML mistakes.

    Step 5 — Test the workflow locally as far as we can (without actually triggering GitHub Actions):

    ```bash
    # Run the validator subprocess invocation locally to confirm the python code works
    uv run python -c "
    from pathlib import Path
    from tradewinds_mcp._generated_validator import validate_generated_entry
    r = validate_generated_entry(Path('packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml'))
    print(r.model_dump_json(indent=2))
    import sys
    sys.exit(0 if r.all_green else 1)
    "
    ```

    Expected: validator runs; the fixture's `status: wip` means `adapter_resolves` is vacuously true; meta-schema + Pydantic should pass; `schema_id_resolves` should pass since fixture uses `schema.observation.v1`. `all_green` = True. (If False, fix the fixture before merge.)

    Step 6 — Run `uv run pytest packages/mcp/tests/test_promotion_gate_workflow_yaml.py -x -v` — 4 tests MUST pass.

    Step 7 — Commit: `ci(phase-5): catalog-promotion-gate + mcp-tests workflows (MCP-03 CI gate)`.

    Step 8 — Document a branch-protection requirement: after Wave 3 merges, repo admin must add `catalog-promotion-gate` and `mcp-tests / test (3.11)` to required status checks. Add a note to the PLAN-03 SUMMARY.
  </action>
  <verify>
    <automated>uv run pytest packages/mcp/tests/test_promotion_gate_workflow_yaml.py -x -v && uv run python -c "from pathlib import Path; from tradewinds_mcp._generated_validator import validate_generated_entry; import sys; r = validate_generated_entry(Path('packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml')); sys.exit(0 if r.all_green else 1)"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f .github/workflows/catalog-promotion-gate.yml` returns 0
    - `test -f .github/workflows/mcp-tests.yml` returns 0
    - `grep -c "catalog-promotion-gate" .github/workflows/catalog-promotion-gate.yml` returns ≥ 1
    - `grep -c "validate_generated_entry" .github/workflows/catalog-promotion-gate.yml` returns ≥ 1
    - `grep -c "packages/mcp/catalog/\\*\\*/\\*.yaml" .github/workflows/catalog-promotion-gate.yml` returns ≥ 1
    - `grep -c "!packages/mcp/catalog/_schema" .github/workflows/catalog-promotion-gate.yml` returns ≥ 1 (excluded path)
    - `grep -c "mcp-tests" .github/workflows/mcp-tests.yml` returns ≥ 1
    - `grep -E 'm "not live"|m '"'"'not live'"'"'' .github/workflows/mcp-tests.yml | wc -l | awk '$1 >= 1 {exit 0} {exit 1}'` (live tests excluded per CI-04)
    - `grep -c "85" .github/workflows/mcp-tests.yml` returns ≥ 1 (coverage bar)
    - `python -c "import yaml; yaml.safe_load(open('.github/workflows/catalog-promotion-gate.yml'))"` exits 0 (workflow is valid YAML)
    - `python -c "import yaml; yaml.safe_load(open('.github/workflows/mcp-tests.yml'))"` exits 0
    - `uv run pytest packages/mcp/tests/test_promotion_gate_workflow_yaml.py -x -v` exits 0 with 4 passed
    - One commit on the branch
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    Two CI workflows shipped: catalog-promotion-gate (triggered on catalog YAML PRs; runs validator; comments on failure) and mcp-tests (runs MCP fast tests + coverage gate on every MCP-touching PR). Both are valid YAML. 4 workflow-shape tests pass. Branch-protection requirement noted for repo admin follow-up.
  </done>
</task>

<task type="auto">
  <name>Task 3.4: CONTRIBUTING.md + AGENT-CONNECTOR-GUIDE.md + _generated/README.md</name>
  <files>packages/mcp/CONTRIBUTING.md, packages/mcp/AGENT-CONNECTOR-GUIDE.md, packages/mcp/catalog/_generated/README.md</files>
  <implements>MCP-03 (community contract / public-facing documentation)</implements>
  <read_first>
    - Tasks 3.1 + 3.2 + 3.3 outputs
    - .planning/phases/05-mcp-data-platform/RESEARCH.md (§C.3 — PR-based contribution model; documentation-augmented generation; 15% hallucination rate)
    - existing packages/mcp/CONTRIBUTING.md (Wave 1 — the 5 hard rules; extend with the Wave 3 contributor workflow)
  </read_first>
  <action>
    Step 1 — Modify `packages/mcp/CONTRIBUTING.md`. Append a new section after the "Five hard rules":

    ```markdown
    ## Contributing a catalog entry

    Generated by an AI agent, or hand-written by a human — same workflow.

    ### Step 1: Scaffold

    ```python
    from tradewinds_mcp._generated_scaffold import scaffold_catalog_entry
    import yaml
    entry = scaffold_catalog_entry("acme.example")
    # Write to _generated/
    with open("packages/mcp/catalog/_generated/acme.example.yaml", "w") as f:
        yaml.safe_dump(entry, f, sort_keys=False)
    ```

    The scaffold is meta-schema-valid out of the box, with TODO markers everywhere a real value is needed.

    ### Step 2: Fill in the 5 layers

    Replace every `TODO:` marker with real content. Read AGENT-CONNECTOR-GUIDE.md for a worked example.

    Critical checklist:
    - [ ] `schema_semantics.schema_id` references an existing entry in `tradewinds.core.schemas.REGISTRY` (one of `schema.observation.v1`, `schema.forecast.iem_mos.v1`, `schema.settlement.cli.v1`) OR a synthetic `contract_spec.*` ID.
    - [ ] `schema_semantics.fields` lists EVERY field a query consumer would see — with domain-meaningful descriptions (not "the X field").
    - [ ] `temporal_rules.knowledge_time_formula` is a human-readable formula. Every field name in the formula MUST appear in `schema_semantics.fields`. Linter enforces.
    - [ ] `quality_notes` has at least 2 entries. These are domain-knowledge tripwires a quant needs to know.
    - [ ] `relationship_mappings.joins_to` enumerates pre-declared joins. Cross-vertical joins NOT listed here will be rejected at query time.
    - [ ] `operational_context.auth` is `none`, `api_key:ENV_VAR_NAME`, or `oauth`.
    - [ ] `status: wip` for new entries. Promotion to `live` happens after review.

    ### Step 3: Validate locally

    ```bash
    uv run python -c "
    from pathlib import Path
    from tradewinds_mcp._generated_validator import validate_generated_entry
    r = validate_generated_entry(Path('packages/mcp/catalog/_generated/acme.example.yaml'))
    print(r.model_dump_json(indent=2))
    "
    ```

    Fix every error. Address warnings if you can. Open the PR only when `all_green` is True.

    ### Step 4: Open a PR

    The CI workflow `catalog-promotion-gate` runs automatically on PRs touching catalog YAML files. It runs the same 4 validator checks. The PR is BLOCKED until they pass.

    ### Step 5: Maintainer review + manual live test + promotion

    A maintainer reviews the YAML, runs the sample-data live test, and (if green) runs:

    ```bash
    uv run python packages/mcp/scripts/promote_generated_entry.py --execute packages/mcp/catalog/_generated/acme.example.yaml
    ```

    This re-runs all checks, runs the live sample-data test, moves the file from `_generated/` to `catalog/` root, and emits a promotion audit entry to `$HOME/.tradewinds/mcp-server/catalog-promotions.jsonl`.

    ### Common rejection reasons

    - **`schema_id_resolves: false`** — typo in `schema_semantics.schema_id`, or the schema you referenced doesn't exist in Phase 2.
    - **`temporal_rules_lint_ok: false`** — knowledge_time_formula references a field that's not declared in schema_semantics.fields. Either add the field to `fields`, or remove the reference from the formula.
    - **`adapter_resolves: false`** — status is `live` but extraction_config.adapter doesn't dispatch via `tradewinds.weather.catalog.get_adapter`. Either set status to `wip` until the adapter ships, or fix the adapter reference.
    - **sparse `quality_notes`** — only 1 entry. Reviewers expect ≥ 2 domain-knowledge notes.
    - **empty `joins_to`** — no pre-declared cross-source joins. Acceptable but advisory; cross-vertical joins not in the allow-list will be rejected at query time.
    ```

    Step 2 — Create `packages/mcp/AGENT-CONNECTOR-GUIDE.md`:

    ```markdown
    # Agent Connector Guide

    Practical instructions for an AI agent (or human contributor) producing a catalog entry for a new data source.

    ## Workflow overview

    1. Read the API documentation. Extract: endpoint URL, auth, rate limits, response shape, temporal semantics.
    2. Scaffold a YAML skeleton with `tradewinds_mcp._generated_scaffold.scaffold_catalog_entry`.
    3. Fill in the 5 layers (schema_semantics, temporal_rules, quality_notes, relationship_mappings, operational_context).
    4. Run the local validator. Fix errors and warnings.
    5. Open a PR. CI gate enforces validation. Maintainer reviews + runs live test + promotes.

    ## Worked example: deriving `iem.archive.yaml` from IEM docs

    Suppose iem.archive.yaml didn't exist yet. Here's how an agent would generate it.

    ### Step A — Read docs

    The IEM ASOS Mesonet API documentation is at https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help — agent reads it and notes:
    - Endpoint: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`
    - Auth: none
    - Rate limit: ~1 req/sec per IP (empirical, not documented — agent flags this as a "operational_context warning to surface in quality_notes")
    - Response: CSV with one row per observation; columns include `station`, `valid` (timestamp UTC), `tmpf`, `relh`, `metar`, etc.

    ### Step B — Scaffold

    ```python
    from tradewinds_mcp._generated_scaffold import scaffold_catalog_entry
    entry = scaffold_catalog_entry("iem.archive", api_doc_url="https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py")
    ```

    ### Step C — Fill in each layer

    **schema_semantics**: agent maps the API's CSV columns to a known Phase 2 schema. ASOS observations are point-in-time temperatures with humidity → maps to `schema.observation.v1`. The `fields` block describes what each column MEANS (not its type — type is in the canonical schema):

    ```yaml
    schema_semantics:
      schema_id: schema.observation.v1
      fields:
        tmpf: "Air temperature, instantaneous reading. Fahrenheit. NOT a daily high/low — this is point-in-time METAR."
        relh: "Relative humidity 0-100. NULL during station outages — do NOT impute from neighbors."
    ```

    **temporal_rules**: this is the layer that prevents future leakage. For ASOS, the observation timestamp (`valid` in the API; mapped to `observed_at` in our schema) is when the sensor recorded the value. The knowledge_time (when the record became available) lags by the FAA-documented "report_delay" of 5-15 minutes. Agent encodes this:

    ```yaml
    temporal_rules:
      event_time_field: observed_at
      knowledge_time_field: knowledge_time
      knowledge_time_formula: "observed_at + report_delay (typically 5-15 min for ASOS METAR per FAA AC 150/5220-16D)"
      backfill_behavior: "Past records DO NOT change after first publish. ASOS is a one-shot publish; no vintage history."
      vintage_aware: false
    ```

    Critical: every field name in the formula (`observed_at`, `report_delay`) is either declared in `fields` above OR is a Phase-2-standard column (event_time, knowledge_time, source, retrieved_at). The validator's temporal-rules linter checks this.

    **quality_notes**: agent surfaces domain knowledge the quant needs:

    ```yaml
    quality_notes:
      - "Pre-2007 records have inconsistent units across stations — handled in _vendor parser per Phase 1 lift."
      - "ASOS sensor changes documented in NOAA station history files; not surfaced in this stream."
      - "SPECI records co-exist with METAR records at the same observed_at — merge policy uses observation_type priority per Phase 1 lift."
    ```

    Three notes ≥ 2 threshold; no warnings.

    **relationship_mappings**: agent pre-declares allowed joins:

    ```yaml
    relationship_mappings:
      joins_to:
        - source: ghcnh.archive
          on: ["station_id", "observed_at"]
          note: "ASOS uses ICAO (KNYC); GHCNh uses WBAN. station_id_map.csv resolves."
    ```

    **operational_context**:

    ```yaml
    operational_context:
      endpoint: "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
      rate_limit: "1 req/sec/IP (empirical per Phase 1.5 SOURCE-LIMITS spike)"
      auth: "none"
      pagination: "365-day calendar-aligned chunks via _iem_chunks helper (Phase 1.5)"
      http_timeout_seconds: 60
    ```

    ### Step D — Validate

    ```bash
    uv run python -c "
    from pathlib import Path
    from tradewinds_mcp._generated_validator import validate_generated_entry
    r = validate_generated_entry(Path('packages/mcp/catalog/_generated/iem.archive.yaml'))
    print(r.model_dump_json(indent=2))
    "
    ```

    All-green output. No warnings. Ready to PR.

    ## Common pitfalls

    ### Pitfall: making up a field name

    LLMs occasionally invent fields that don't exist in the real API (15% rate on low-frequency APIs per arxiv.org/html/2407.09726v1). MITIGATION: the catalog-promotion-gate CI runs the sample-data live test on every PR — if your claimed `fields` doesn't match what the API returns, the test fails. Fix: re-read the API response shape; correct the YAML.

    ### Pitfall: knowledge_time formula references a phantom field

    The temporal-rules linter scans the formula for identifier-shaped tokens and asserts each token that looks like a field is declared. If you write `knowledge_time_formula: "observed_at + ml_smoothing_delay"`, the linter flags `ml_smoothing_delay` as undeclared. Fix: either add the field to `schema_semantics.fields`, or remove the reference from the formula.

    ### Pitfall: status=live without a working adapter

    `adapter_resolves` check ensures that if you mark status=live, the `extraction_config.adapter` actually dispatches via `tradewinds.weather.catalog.get_adapter`. For new sources without a Phase 2 adapter, set `status: wip` until the adapter ships. WIP entries are visible in describe_source but not queryable (raise SourceUnavailableError).

    ### Pitfall: cross-vertical joins not pre-declared

    Per RESEARCH.md §I.8, the `joins_to` block is the ALLOW-LIST for cross-source joins. If your source genuinely joins to a source in a different vertical (weather → macro, e.g.), declare it. Wave 4 enforces by rejecting undeclared joins at query time.
    ```

    Step 3 — Create `packages/mcp/catalog/_generated/README.md`:

    ```markdown
    # `_generated/` — candidate catalog entries awaiting review

    Entries in this directory are CANDIDATE catalog entries — produced by an agent or human contributor, pending validator green + maintainer review.

    See `packages/mcp/AGENT-CONNECTOR-GUIDE.md` for how to add one.

    The `CatalogLoader` SKIPS this directory at server boot. Entries here are NOT queryable. They become queryable only after promotion to `packages/mcp/catalog/` root via `packages/mcp/scripts/promote_generated_entry.py --execute`.

    Maintainers: the promotion script logs every promotion to `$HOME/.tradewinds/mcp-server/catalog-promotions.jsonl`.
    ```

    Step 4 — Run `uv run pre-commit run --all-files`. Expected green.

    Step 5 — Commit: `docs(phase-5): CONTRIBUTING workflow + AGENT-CONNECTOR-GUIDE worked example + _generated/README (MCP-03 community contract)`.
  </action>
  <verify>
    <automated>test -f packages/mcp/AGENT-CONNECTOR-GUIDE.md && test -f packages/mcp/catalog/_generated/README.md && grep -c "Contributing a catalog entry" packages/mcp/CONTRIBUTING.md | grep -E "^[1-9]" && grep -c "Worked example" packages/mcp/AGENT-CONNECTOR-GUIDE.md | grep -E "^[1-9]"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f packages/mcp/AGENT-CONNECTOR-GUIDE.md` returns 0
    - `test -f packages/mcp/catalog/_generated/README.md` returns 0
    - `grep -c "## Contributing a catalog entry" packages/mcp/CONTRIBUTING.md` returns 1
    - `grep -c "scaffold_catalog_entry" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `grep -c "promote_generated_entry" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `grep -c "validate_generated_entry" packages/mcp/CONTRIBUTING.md` returns ≥ 1
    - `grep -c "Worked example" packages/mcp/AGENT-CONNECTOR-GUIDE.md` returns ≥ 1
    - `grep -c "iem.archive" packages/mcp/AGENT-CONNECTOR-GUIDE.md` returns ≥ 1
    - `grep -c "knowledge_time_formula" packages/mcp/AGENT-CONNECTOR-GUIDE.md` returns ≥ 1
    - `uv run pre-commit run --all-files` exits 0
    - One commit on the branch
    - No `--no-verify`
  </acceptance_criteria>
  <done>
    CONTRIBUTING.md has a complete catalog-contribution workflow with rejection-reason list. AGENT-CONNECTOR-GUIDE.md provides a concrete worked example (iem.archive). _generated/README.md explains the dir's role.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3.5: 2-reviewer loop + pre-merge gate + merge to main</name>
  <files>n/a (verification only)</files>
  <implements>Wave 3 closeout</implements>
  <read_first>
    - .planning/REVIEW-DISCIPLINE.md (never-skip — CI YAML is schema-fragment-bearing)
    - Plan-level success criteria below
  </read_first>
  <what-built>
    Tasks 3.1–3.4 complete: scaffold helper + validator (4 checks + 3 warnings); promotion CLI + catalog-promotions.jsonl audit; two CI workflows; CONTRIBUTING workflow expansion + AGENT-CONNECTOR-GUIDE worked example + _generated/README.
  </what-built>
  <how-to-verify>
    **Step A — Final tests pass:**

    ```bash
    uv run pytest packages/mcp/tests/ -m "not live" -v
    uv run pytest -m "not live" -q
    uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q | grep TOTAL  # ≥ 85%
    ```

    **Step B — End-to-end manual smoke (scaffold → validate → promote dry-run):**

    ```bash
    mkdir -p /tmp/promote_smoke
    cd /tmp/promote_smoke
    uv run python -c "
    import sys; sys.path.insert(0, '/path/to/tradewinds/packages/mcp/src')
    from tradewinds_mcp._generated_scaffold import scaffold_catalog_entry
    import yaml
    e = scaffold_catalog_entry('smoke.example')
    with open('smoke.example.yaml', 'w') as f:
        yaml.safe_dump(e, f, sort_keys=False)
    print('Scaffolded smoke.example.yaml')
    "
    # Verify scaffold output is meta-schema-valid
    uv run python -c "
    from pathlib import Path
    from tradewinds_mcp._generated_validator import validate_generated_entry
    r = validate_generated_entry(Path('/tmp/promote_smoke/smoke.example.yaml'))
    print('all_green:', r.all_green)
    print('errors:', r.errors)
    print('warnings:', r.warnings)
    "
    ```

    Expected: scaffold output has all 8 top-level fields; validator reports `meta_schema_ok=True`, `pydantic_ok=True`, but `schema_id_resolves=False` (because scaffold has `TODO: schema ID...` placeholder); errors lists the schema_id issue. This confirms the validator catches the most common error type.

    **Step C — Dry-run promotion against the example fixture:**

    ```bash
    uv run python packages/mcp/scripts/promote_generated_entry.py --dry-run packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml
    ```

    Expected: prints the validator report; the fixture has status=wip (Open-Meteo policy honored) so `adapter_resolves` is vacuously true; all gates green; planned move printed; no file moved.

    **Step D — Workflow YAML lint:**

    ```bash
    # If actionlint available
    actionlint .github/workflows/*.yml || true
    # YAML parses
    python -c "import yaml; yaml.safe_load(open('.github/workflows/catalog-promotion-gate.yml')); yaml.safe_load(open('.github/workflows/mcp-tests.yml'))"
    ```

    Expected: no errors.

    **Step E — 2-reviewer loop:**

    Reviewer prompts must explicitly reference:
    - RESEARCH.md §I.4 (15% hallucination rate) — validator + sample-data round-trip gate it
    - REVIEW-DISCIPLINE.md never-skip (CI YAML has schema-fragment-bearing literals)
    - The branch-protection follow-up (repo admin must add `catalog-promotion-gate` and `mcp-tests` to required status checks)

    PASS x2 in ≤ 3 iterations.

    **Step F — Merge to main:**

    ```bash
    git checkout main
    git merge --no-ff phase-5/wave-3/agent-connector-pipeline -m "Merge phase-5/wave-3/agent-connector-pipeline: agent-generated connector pipeline + CI promotion gate (MCP-03)"
    ```

    **Step G — Post-merge follow-up (manual):**

    Repo admin adds `catalog-promotion-gate` and `mcp-tests / test (3.11)` to the `main` branch protection rule's required status checks. Document this as a one-line action item in 05-03-SUMMARY.md.

    **Step H — Confirm to user:**

    (1) All green: "Wave 3 merged to `main`. Agent-connector pipeline shipped: scaffold + validator + promotion CLI + 2 CI workflows + CONTRIBUTING + AGENT-CONNECTOR-GUIDE. Branch-protection update required (manual): add `catalog-promotion-gate` and `mcp-tests` to `main` required checks. Wave 4 (USER_DECISION_GATE + second-vertical adapter + integration tests + v0.2.0 release) is unblocked. Type `approved` to continue."

    (2) Reviewer REVISE: standard cycle.
  </how-to-verify>
  <resume-signal>
    Type `approved` once Wave 3 is merged to `main` AND branch-protection has been updated (PLAN-04 is unblocked). Type `revise` for reviewer-driven changes.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Untrusted YAML in `_generated/` | Contributor-supplied; same trust level as a feature-branch commit; CI gate is the structural defense. |
| Catalog promotion CLI (maintainer-run) | Runs validator + live test + filesystem move. Trust boundary: the maintainer's local environment. |
| CI workflow (.github/workflows/) | GitHub-hosted; trust boundary if a malicious PR can modify the workflow itself to bypass gates. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-5.3-01 | Tampering | Hallucinated field name in generated YAML | mitigate | Sample-data live test (Task 2.4 + Task 3.2 invocation) fetches real data and asserts claimed fields exist; catalog-promotion-gate CI runs validator on every PR. RESEARCH.md §I.4 mitigated. |
| T-5.3-02 | Tampering | Knowledge_time formula references phantom fields, silently breaking temporal safety | mitigate | `temporal_rules_lint_ok` check scans the formula and asserts each cited token is declared. False positives surface as visible failures, fixable in the YAML. |
| T-5.3-03 | Tampering | Status=live entry with broken adapter | mitigate | `adapter_resolves` check imports `tradewinds.weather.catalog.get_adapter` and dispatches; failure blocks promotion. WIP status is the safe default. |
| T-5.3-04 | Elevation of Privilege | Malicious PR modifies the catalog-promotion-gate workflow to skip the validator | mitigate | Branch-protection rule requires `catalog-promotion-gate` AND `mcp-tests` as required status checks before merge to main; PRs that change `.github/workflows/*.yml` STILL require the gate to pass (CI runs the new workflow). Plus: REVIEW-DISCIPLINE.md never-skip applies to `.github/workflows/` changes — codex + python-architect review mandatory. |
| T-5.3-05 | Information Disclosure | Generated YAML contains a credential token in `operational_context.auth` | accept | The auth field is documented as `none | api_key:ENV_VAR_NAME | oauth` — it should reference an env var name, not the token itself. CONTRIBUTING.md documents this; code review catches violations. |
| T-5.3-06 | Repudiation | A maintainer promotes an entry that later turns out to be wrong; no record of who promoted | mitigate | `catalog-promotions.jsonl` audit log records `promoting_user`, `ts`, `sha256_of_yaml`. Git history is the secondary record. |
| T-5.3-07 | Tampering | Open-Meteo example fixture is accidentally moved from `tests/fixtures/` to `catalog/_generated/`, signaling we ship an Open-Meteo adapter | mitigate | The fixture file has a top-of-file comment block warning "TEST FIXTURE — do not treat as real catalog content. Open-Meteo licensing forbids redistribution in tradewinds v0.1." Reviewers also check via the static guard `test ! -f packages/mcp/catalog/_generated/openmeteo.example.yaml`. CLAUDE.md "Avoid Open-Meteo" policy enforced. |
</threat_model>

<verification>
## Plan-Level Checks

| Check | Command | Expected |
|-------|---------|----------|
| Scaffold produces meta-schema-valid output | Task 3.1 test `test_scaffold_produces_meta_schema_valid_dict` | PASS |
| Validator catches 4 failure modes | Task 3.1 tests 3-6 | PASS |
| Promotion CLI dry-run | `uv run python packages/mcp/scripts/promote_generated_entry.py --dry-run packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml` | exit 0, prints plan |
| CI workflow YAMLs valid | `python -c "import yaml; yaml.safe_load(open('.github/workflows/catalog-promotion-gate.yml'))"` | exit 0 |
| Promotion CI triggers on catalog YAML | `grep "packages/mcp/catalog/\*\*/\*.yaml" .github/workflows/catalog-promotion-gate.yml` | non-empty |
| mcp-tests CI excludes live | `grep -E 'm "not live"|m '"'"'not live'"'"'' .github/workflows/mcp-tests.yml` | ≥ 1 |
| CONTRIBUTING expanded | `grep "## Contributing a catalog entry" packages/mcp/CONTRIBUTING.md` | non-empty |
| AGENT-CONNECTOR-GUIDE worked example | `grep "Worked example" packages/mcp/AGENT-CONNECTOR-GUIDE.md` | non-empty |
| Open-Meteo example NOT in _generated/ | `test ! -f packages/mcp/catalog/_generated/openmeteo.example.yaml` | exit 0 |
| Full MCP fast suite green | `uv run pytest packages/mcp/tests/ -m "not live" -q` | exit 0 |
| Coverage ≥ 85% | `uv run pytest --cov=tradewinds_mcp --cov-branch packages/mcp/tests/ -q \| grep TOTAL` | ≥ 85% |
| 2-reviewer loop | (manual) | PASS x2 |

## Static Regression Guards

```bash
# Open-Meteo fixture lives in tests/fixtures, NOT in catalog
test ! -f packages/mcp/catalog/_generated/openmeteo.example.yaml || (echo "FAIL: Open-Meteo fixture promoted incorrectly" && exit 1)
test -f packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml || (echo "FAIL: Open-Meteo fixture missing" && exit 1)

# Open-Meteo fixture's status is wip (not live)
grep -c "^status: wip$" packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml | grep -E "^1$" || echo "FAIL: Open-Meteo fixture must be status:wip"

# CI workflow excludes _schema/ from promotion gate
grep "!packages/mcp/catalog/_schema" .github/workflows/catalog-promotion-gate.yml || echo "FAIL: schema dir not excluded from promotion gate"

# CI workflow runs validate_generated_entry, not just yaml lint
grep "validate_generated_entry" .github/workflows/catalog-promotion-gate.yml || echo "FAIL: promotion gate doesn't run the validator"
```
</verification>

<success_criteria>
- [ ] MCP-03 (full): scaffold + validator (4 checks + 3 warnings) + promotion CLI + 2 CI workflows + CONTRIBUTING expansion + AGENT-CONNECTOR-GUIDE worked example.
- [ ] `scaffold_catalog_entry(source_id)` returns a meta-schema-valid skeleton with TODO markers.
- [ ] `validate_generated_entry(path)` runs 4 checks: meta_schema_ok, pydantic_ok, schema_id_resolves, temporal_rules_lint_ok, adapter_resolves; emits 3 advisory warnings.
- [ ] `promote_generated_entry.py --dry-run` is safe; `--execute` re-runs validator + (optionally) live test, moves the file, emits audit JSONL.
- [ ] CI workflow `catalog-promotion-gate` triggers on PRs touching `packages/mcp/catalog/**/*.yaml` (excluding `_schema/`); runs `validate_generated_entry` on each changed file; blocks merge on validator failure.
- [ ] CI workflow `mcp-tests` runs MCP fast tests on `packages/mcp/**` PRs across Python 3.11 / 3.12 / 3.13; enforces ≥ 85% coverage.
- [ ] CONTRIBUTING.md has a "Contributing a catalog entry" section listing the 5-step workflow + common rejection reasons.
- [ ] AGENT-CONNECTOR-GUIDE.md has a worked example deriving `iem.archive.yaml` from IEM docs.
- [ ] Open-Meteo example fixture is at `packages/mcp/tests/fixtures/example_generated/openmeteo.example.yaml` (status=wip) — NOT in `packages/mcp/catalog/_generated/`.
- [ ] Full MCP fast suite green: `uv run pytest packages/mcp/tests/ -m "not live" -q` exits 0 (~70 tests).
- [ ] Full repo fast suite green.
- [ ] Branch coverage `tradewinds_mcp` ≥ 85%.
- [ ] Pre-commit + pre-push hooks green; no `--no-verify`.
- [ ] 2-reviewer loop PASS x2 in ≤ 3 iterations.
- [ ] Branch `phase-5/wave-3/agent-connector-pipeline` merged to `main` via `git merge --no-ff`.
- [ ] Post-merge: repo admin notified to add `catalog-promotion-gate` + `mcp-tests / test (3.11)` to `main` branch protection required status checks (documented as follow-up in SUMMARY).
</success_criteria>

<output>
After completion, create `.planning/phases/05-mcp-data-platform/05-03-SUMMARY.md` documenting:

- MCP-03 shipped end-to-end: scaffold + validator + CLI + CI gate + docs
- Validator-check breakdown: 4 errors-block + 3 warnings-advisory; what each catches
- CI workflows: trigger paths, gate job names, coverage bar
- Example fixture location (tests/fixtures, NOT catalog/_generated; Open-Meteo policy compliance)
- Coverage on tradewinds_mcp (target ≥ 85%)
- 2-reviewer loop verdict (PASS x2 iteration N)
- Commit hashes
- Merge commit hash on `main`
- Time spent
- Post-merge follow-up: branch-protection rule update (manual; repo admin task)
- Downstream signal for Wave 4: macro vertical (FRED+ALFRED+Kalshi macro) catalog entries will be the FIRST users of this pipeline. Their YAML files will go through `_generated/` first, then promote to `catalog/` via the CLI. Validator + CI gate will catch hallucinated field names if the agent producing the macro entries makes mistakes.
</output>
