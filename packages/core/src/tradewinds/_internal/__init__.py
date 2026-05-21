"""Private shared SDK utilities used by tradewinds-weather and tradewinds-markets.

NOT a public API. Module names start with underscore to discourage downstream use.

Sprint 0 Day 1 (Lane V) lifts:
- ``_http``, ``_live_http`` — HTTP session + retry logic from monorepo-v0.14.1/src/mostlyright/
- ``_convert`` — unit conversions (F/C, hPa/inHg) from monorepo-v0.14.1
- ``_types`` — shared type aliases (LIVE_CAPABLE_SOURCES, etc.) from monorepo-v0.14.1
- ``config`` — Config (renamed from TherminalConfig) from monorepo-v0.14.1
- ``exceptions`` — NoLiveForSourceError, etc. from monorepo-v0.14.1
- ``models`` — Observation, Station, etc. from monorepo-v0.14.1/src/mostlyright/models/
- ``versioning`` — DataVersion from monorepo-v0.14.1

Sprint 0 Day 2 (Lane V) lifts:
- ``merge`` — both LIVE_V1 merge policies (observation + climate) from monorepo-v0.14.1/ingest/merge/
"""
