"""Phase 17 FORECAST-10 — empirical concurrency / rate-limit probes for NWP mirrors.

Standalone spike scripts that hit live public mirrors (AWS BDP / NOMADS /
ECMWF Open Data / MSC Datamart) at N={1,2,4,8} concurrent and emit
markdown tables for `.planning/research/FORECAST-LIMITS.md`. Not a test
module — operator-gated; run pre-publish only. See README.md.
"""
