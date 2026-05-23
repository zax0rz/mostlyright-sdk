"""tradewinds._v02 — foundations from the wave-1-core port (mostlyright-mcp design doc).

Self-contained primitives ported from mostlyright-mcp's feat/wave-1-core branch:
- exceptions: MCP-shaped exception hierarchy with JSON-safe encoder
- timepoint: UTC-aware timestamp wrapper with DST + ns truncation handling
- schema: declarative schema framework with audit_log + 3 canonical schemas
- formats: TOON / parquet / json / csv / dataframe serializers

NOT used by Sprint 0 (which lifts v0.14.1 internals into _internal/). Available
here as a v0.2+ reference for the MCP-native vision; safe to ignore until then.
"""
