"""Capture drift fixtures from the **current** mostlyright.research() build.

This is the Phase 4 CI-05 watchdog complement to
``tests/fixtures/parity/capture_fixtures.py``. Where ``parity/`` is the
**frozen** v0.14.1 ground truth (captured Day 0.5, never re-recorded), the
``drift/`` tier is **rotated weekly** by ``.github/workflows/drift-rotate.yml``
against the same 5 case inputs.

Two-tier policy (see ``tests/fixtures/README.md``):

- ``parity/`` — immutable. Any byte drift = parity gate fails =
  v0.14.1 byte-equivalence contract is broken. Never re-record without
  bumping the contract version (e.g. capturing a fresh ``parity_v0_15/``
  set behind a new flag).
- ``drift/`` — mutable, rotated. Capture each Monday 07:00 UTC, diff
  against ``parity/`` via ``compare.py``. Mismatches open a GH issue
  but DO NOT fail CI — drift is a watchdog signal, not a hard gate.

Usage
-----

    uv run python tests/fixtures/drift/capture_drift.py

Hits the live AWC + IEM + GHCNh + NWS CLI endpoints (network-bound). Not
guarded by ``@pytest.mark.live`` because this is a script, not a test —
the workflow that calls it runs on a schedule, not on every push.

Cases (mirror of ``parity/capture_fixtures.py``):

1. KNYC 2025-01-06 → 2025-01-12 (single-week NYC baseline)
2. KMDW 2025-04-01 → 2025-04-30 (single-month Chicago / Midway)
3. KLAX 2025-03-01 → 2025-03-31 (PST/PDT transition)
4. KMIA 2024-12-01 → 2025-11-30 (full-year Miami, year boundary)
5. KMSY 2024-09-08 → 2024-09-22 (Hurricane Francine — AWC gap, IEM fills)

Output: ``tests/fixtures/drift/case_<N>_<STATION>_<FROM>_<TO>.parquet``,
one file per case. Same naming convention as ``parity/`` for direct diff.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

#: Mirror of CASES in tests/test_parity.py and tests/fixtures/parity/capture_fixtures.py.
#: Any change to the case list MUST land in all three locations in the same commit.
CASES: list[tuple[int, str, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12", "Single-week NYC baseline"),
    (2, "KMDW", "2025-04-01", "2025-04-30", "Single-month Chicago (Midway)"),
    (3, "KLAX", "2025-03-01", "2025-03-31", "PST/PDT transition"),
    (4, "KMIA", "2024-12-01", "2025-11-30", "Full-year Miami, year boundary"),
    (5, "KMSY", "2024-09-08", "2024-09-22", "Hurricane Francine — AWC gap, IEM fills"),
]


def main() -> int:
    outdir = Path(__file__).resolve().parent
    outdir.mkdir(parents=True, exist_ok=True)

    results: list[tuple[int, str, int, int, str]] = []
    failures = 0

    for n, station, frm, to, _why in CASES:
        fname = outdir / f"case_{n}_{station}_{frm}_{to}.parquet"
        try:
            df = mostlyright.research(station, frm, to)
            df.to_parquet(fname)
            rows = len(df)
            size = fname.stat().st_size
            print(f"case {n}: {fname.name} — {rows} rows, {size} bytes")
            results.append((n, "OK", rows, size, str(fname)))
        except Exception as exc:
            failures += 1
            print(
                f"case {n}: FAILED — {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc()
            results.append((n, "FAILED", 0, 0, f"{type(exc).__name__}: {exc}"))

    print("\n--- summary ---")
    for n, status, rows, size, info in results:
        print(f"  case {n}: {status} | rows={rows} | bytes={size} | {info}")

    # Soft-fail: even if some cases failed, write what we got. Upstream API
    # outages are exactly the kind of thing the drift watchdog catches —
    # do not bail before compare.py runs.
    return 0 if failures == 0 else 0  # noqa: RUF034 — intentional: even on failure, soft-success so compare.py runs


if __name__ == "__main__":
    sys.exit(main())
