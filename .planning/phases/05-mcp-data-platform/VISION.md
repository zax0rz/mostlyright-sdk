# Phase 5: MCP Data Platform (v0.2+)

## Vision
Tradewinds becomes an MCP-native data platform for prediction market ML. The SDK already handles weather data ingestion and temporal safety — the MCP layer exposes this to AI agents so domain experts don't need to become data engineers.

## 1. MCP Server Layer
- Lives at `packages/mcp/` (seam already exists)
- Exposes tradewinds tools via MCP protocol: `list_sources`, `describe_source`, `ingest`, `query`, `get_schema`
- AI agents (Claude, Cursor, any MCP client) connect and orchestrate data pipelines
- Each data vertical (weather, sports, politics) can be its own MCP server

## 2. Data Catalog with Context Engineering
The secret sauce. Each pre-indexed data source gets rich 5-layer context, not just API configs:
- **Schema semantics** — what each field actually means. "close" could be closing price, closing odds, or market close time
- **Temporal rules** — when data is actually "known". API might return record timestamped 3pm but wasn't available until 5pm. Critical for leakage prevention
- **Quality notes** — "this source backfills and changes past values" or "odds before 2023 unreliable"
- **Relationship mappings** — how source A's market_id joins to source B's event_id. Cross-source joins are where most pipelines break
- **Operational context** — rate limits, auth, pagination, retry behavior

Think of catalog entries as onboarding docs for each data source, except the "new hire" is an AI agent.

## 3. Agent-Generated Connectors
For sources not in the pre-indexed catalog:
- Agent reads API docs/HTML/PDF, builds mental model of schema, generates extraction config
- Generated configs stored so next person using same source doesn't start from scratch
- Catalog grows organically — community contributions via generated configs
- Quality review before promotion to pre-indexed status

## 4. Temporal Safety as Trust Architecture
Already partially built in tradewinds core (TimePoint, KnowledgeView from Phase 2). Key for quant adoption:
- SERVER-ENFORCED, not agent-enforced. Agent literally cannot bypass it
- `dataset.at_time("2024-01-15")` returns exactly and only what was knowable on that date
- No honor system, no "the agent promised it filtered correctly" — constraint is structural
- Auditable provenance, schema contracts, deterministic replay
- This is why quants will trust it — they distrust AI agents because of leakage risk

## 5. Multi-Vertical Expansion
- v0.2: Weather (what we have) + MCP server
- v0.3: Sports prediction markets (horse racing, etc.)
- v0.4: Politics, finance
- Each vertical = new catalog entries + adapters, same temporal safety layer

## 6. Architecture: Core + Wrappers
- Core Python library (tradewinds — what we're building now)
- MCP server wrapper (packages/mcp/ — new in v0.2)
- CLI wrapper (already planned v1.1+)
- Python SDK for direct use (already what tradewinds is)

## Dependencies on v0.1
- Phase 2's TimePoint/KnowledgeView/LeakageDetector are the foundation for temporal safety
- Phase 2's catalog adapters + canonical schemas are the foundation for the data catalog
- Phase 4's CI/CD pipeline carries forward

## Open Questions
- MCP SDK version to target (Python `mcp` package version)
- Auth model for MCP server (local-first vs hosted)
- Catalog format: YAML vs JSON Schema vs custom DSL
- Community contribution model for agent-generated connectors
- Pricing model for hosted version (if any)
