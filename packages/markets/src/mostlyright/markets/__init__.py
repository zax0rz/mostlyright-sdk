"""mostlyright.markets — prediction market data (Kalshi, Polymarket).

v0.0.1 is a PLACEHOLDER only. Real functionality lands in v0.1.0 (Sprint 0.5)
when Lane V ports the Kalshi metadata client from
``therminal/therminal-ingest/src/sources/kalshi/`` (TypeScript reference)
using endpoints documented in ``therminal/research/notes/research-kalshi-api.md``
(no auth required for public market data).

Sprint 0 ships ONLY ``mostlyright`` + ``mostlyright-weather`` at v0.1.0;
``mostlyright-markets`` stays at v0.0.1 placeholder until Sprint 0.5.

Roadmap:
- Sprint 0.5: ``mostlyright.markets.kalshi.{series, events, markets, candles, research_by_market}``
- Sprint 3: ``mostlyright.markets.polymarket.*`` (port from
  ``monorepo-v0.14.1/src/mostlyright/_polymarket.py``)
"""

__version__ = "0.0.1"
__all__ = ["__version__"]
