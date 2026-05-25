"""mostlyright._internal — shared utilities lifted from monorepo-v0.14.1.

NOT a public API. Module names start with underscore to discourage downstream
use; rely on ``mostlyright.research()`` / ``mostlyright.snapshot.*`` instead.

Lift inventory (provenance for parity-critical code). Source SHA refers to the
v0.14.1 release tag of ``Tarabcak/monorepo`` (commit
``514fcdab227e845145ca32b989355647466231d9``); ``_pairs.py`` additionally
pins the exact source-file blob SHA from that tree.

| Module                | Source path                                              | Source SHA   | Lift date  | Modifications                                                          |
|-----------------------|----------------------------------------------------------|--------------|------------|------------------------------------------------------------------------|
| _http.py              | monorepo-v0.14.1/src/mostlyright/_http.py                | 514fcda      | 2026-05-21 | namespace rename only (mostlyright -> mostlyright._internal)            |
| _convert.py           | monorepo-v0.14.1/src/mostlyright/_convert.py             | 514fcda      | 2026-05-21 | namespace rename only                                                  |
| _bounds.py            | monorepo-v0.14.1/src/mostlyright/_bounds.py              | 514fcda      | 2026-05-21 | namespace rename only                                                  |
| _capabilities.py      | monorepo-v0.14.1/src/mostlyright/_capabilities.py        | 514fcda      | 2026-05-21 | namespace rename only                                                  |
| _toon.py              | monorepo-v0.14.1/src/mostlyright/_toon.py                | 514fcda      | 2026-05-22 | ruff-clean RUF002/003 (replace EN DASH in inline comments); body identical |
| exceptions.py         | monorepo-v0.14.1/src/mostlyright/exceptions.py           | 514fcda      | 2026-05-21 | namespace rename only                                                  |
| versioning.py         | monorepo-v0.14.1/src/mostlyright/versioning.py           | 514fcda      | 2026-05-21 | namespace rename only                                                  |
| models/               | monorepo-v0.14.1/src/mostlyright/models/                 | 514fcda      | 2026-05-21 | namespace rename only                                                  |
| specs/*.json          | monorepo-v0.14.1/src/mostlyright/specs/                  | 514fcda      | 2026-05-21 | none (data-only)                                                       |
| _stations.py          | monorepo-v0.14.1/src/mostlyright/_stations.py            | 514fcda      | 2026-05-22 | none (pure-data module; no imports to rename)                          |
| _pairs.py             | monorepo-v0.14.1/src/mostlyright/pairs.py                | e78eed5 (blob, in tree 514fcda) | 2026-05-22 | TOON imports + ``to_toon`` function excised; namespace rename          |
| merge/observations.py | monorepo-v0.14.1/ingest/storage/parquet.py:47-48,246-261 | 514fcda      | 2026-05-21 | rename ``_dedup_rows`` -> ``merge_observations`` (public API)          |
| merge/climate.py      | monorepo-v0.14.1/ingest/storage/parquet.py:477-494       | 514fcda      | 2026-05-21 | rename ``_dedup_climate_rows`` -> ``merge_climate`` (public API)       |
| merge/_schemas.py     | monorepo-v0.14.1/ingest/storage/parquet.py:50-103        | 514fcda      | 2026-05-21 | none (verbatim lift; field order + dtypes preserved)                   |

Any drift in ``merge/`` or ``_pairs.py`` invalidates every historical Kalshi
NHIGH/NLOW settlement — treat as load-bearing and re-run the parity gate
(``tests/test_parity.py``) before merging changes here.
"""
