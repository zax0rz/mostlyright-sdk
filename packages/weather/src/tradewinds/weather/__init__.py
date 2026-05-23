"""tradewinds.weather — direct public-API access for AWC, IEM, GHCNh, NWS CLI.

Local-first; no hosted backend; no API keys. Parsers are byte-faithful lifts
from ``monorepo-v0.14.1``; HTTP fetchers and the parquet cache are net-new
Sprint 0 code so the SDK can run without the v0.14.1 ingest service.

Lift inventory (provenance for parity-critical code). Source SHA refers to
the v0.14.1 release tag of ``Tarabcak/monorepo`` (commit
``514fcdab227e845145ca32b989355647466231d9``).

| Module                  | Source path                                            | Source SHA | Lift date  | Modifications                                                       |
|-------------------------|--------------------------------------------------------|------------|------------|---------------------------------------------------------------------|
| _awc.py                 | monorepo-v0.14.1/src/mostlyright/weather/_awc.py       | 514fcda    | 2026-05-21 | namespace rename only (imports point at ``tradewinds._internal``)   |
| _iem.py                 | monorepo-v0.14.1/src/mostlyright/weather/_iem.py       | 514fcda    | 2026-05-21 | namespace rename only                                               |
| _climate.py             | monorepo-v0.14.1/src/mostlyright/weather/_climate.py   | 514fcda    | 2026-05-21 | namespace rename only                                               |
| _ghcnh.py               | monorepo-v0.14.1/src/mostlyright/weather/_ghcnh.py     | 514fcda    | 2026-05-21 | namespace rename only                                               |
| _fetchers/__init__.py   | n/a (NEW)                                              | n/a        | 2026-05-21 | NEW (Sprint 0 Wave 1 Lane F) — fetcher package marker               |
| _fetchers/awc.py        | n/a (NEW)                                              | n/a        | 2026-05-21 | NEW (Sprint 0 Wave 1 Lane F) — historical AWC range fetcher         |
| _fetchers/iem_asos.py   | n/a (NEW)                                              | n/a        | 2026-05-21 | NEW (Sprint 0 Wave 1 Lane F) — monthly-chunked IEM ASOS METAR fetcher |
| _fetchers/iem_cli.py    | n/a (NEW)                                              | n/a        | 2026-05-21 | NEW (Sprint 0 Wave 1 Lane F) — IEM CLI settlement-grade fetcher     |
| _fetchers/ghcnh.py      | n/a (NEW)                                              | n/a        | 2026-05-21 | NEW (Sprint 0 Wave 1 Lane F) — per-year NCEI GHCNh PSV fetcher      |
| cache.py                | n/a (NEW)                                              | n/a        | 2026-05-21 | NEW (Sprint 0 Wave 1 Lane F) — local parquet cache, filelock-guarded |

``_bounds`` is imported from ``tradewinds._internal`` (lifted there from
``monorepo-v0.14.1/src/mostlyright/_bounds.py``) — see the parallel lift
inventory in ``tradewinds._internal.__init__``.

Public surface kept stable for Vojtech's existing ``mostlyright==0.14.1``
workflow: ``raw_metar`` is preserved on observation rows so MetPy re-parse
keeps working without preprocessing in v0.1.0.
"""

__version__ = "0.1.0rc1"
__all__ = ["__version__"]
