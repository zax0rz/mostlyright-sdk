"""Capture parity fixtures from ``mostlyright==0.14.1``.

This script is **the** reproducible recipe for regenerating the Day 3
hard-gate parity fixtures. It is **not** intended to be re-run on every
build — the captured ``.parquet`` files committed alongside it ARE the
ground truth. Re-run only when:

1. The published ``mostlyright`` SDK changes its ``client.pairs(...)``
   contract (then a new fixture set is captured under a new directory
   matching the new contract version, e.g. ``parity_v0_15/``).
2. A case query was marked ``FAILED — REGEN NEEDED`` in
   ``README.md`` and now has the necessary credentials / access.

Prerequisites
-------------
1. A clean Python 3.11+ venv (NOT this workspace's ``.venv``):

    python3.11 -m venv /tmp/mostlyright-v14-venv
    /tmp/mostlyright-v14-venv/bin/pip install --upgrade pip
    /tmp/mostlyright-v14-venv/bin/pip install "mostlyright[parquet]==0.14.1"
    /tmp/mostlyright-v14-venv/bin/pip install "pandas>=2.2,<3.0" "pyarrow>=18,<25"

   The pandas pin is **PARITY-CRITICAL** (see tradewinds CLAUDE.md):
   pandas 3.0 introduces CoW + dtype-shift changes that break
   byte-equivalence against the 2.x-era fixtures.

2. A valid ``MOSTLYRIGHT_API_KEY`` for ``api.mostlyright.md``. As of
   2026-05-21, the published v0.14.1 SDK does **not** forward this
   value as a header (see README.md "Capture blocker"); the script
   below patches ``HttpSession`` at runtime to send ``X-API-Key`` so
   the existing 0.14.1 client surface stays a pure import.

3. Run from the repo root:

    MOSTLYRIGHT_API_KEY=<key> \\
      /tmp/mostlyright-v14-venv/bin/python tests/fixtures/parity/capture_fixtures.py

Cases
-----
1. KNYC 2025-01-06 → 2025-01-12 (single-week NYC baseline)
2. KORD 2025-04-01 → 2025-04-30 (single-month Chicago)
3. KLAX 2025-03-01 → 2025-03-31 (PST/PDT transition)
4. KMIA 2024-12-01 → 2025-11-30 (full-year Miami, year boundary)
5. KMSY 2024-09-08 → 2024-09-22 (Hurricane Francine recovery —
   real-world AWC gaps filled by IEM; see README.md for picking
   rationale and tie-back to test_merge_scheduler.test_awc_gap_filled_by_iem.)

Output
------
``tests/fixtures/parity/case_<N>_<STATION>_<FROM>_<TO>.parquet``

Each parquet is the DataFrame returned by ``client.pairs(...,
as_dataframe=True)`` written via ``df.to_parquet()``. Sort order and
column set match v0.14.1's ``pairs.pairs_to_dataframe(...)`` output —
Day 3 ``test_parity.py`` re-reads, sorts canonically, and runs
``assert_frame_equal`` per design.md Amendments §G.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Any

# Patch the v0.14.1 HttpSession to forward MOSTLYRIGHT_API_KEY as
# X-API-Key. The published SDK does not do this on its own — the auth
# layer landed server-side without an SDK release. We monkeypatch
# before the first MostlyRightClient() so all subsequent requests carry
# the header. If MOSTLYRIGHT_API_KEY is unset, requests will fail at
# /observations with AuthenticationError (matches production behaviour).
import httpx
from mostlyright import MostlyRightClient
from mostlyright import _http as _mr_http


def _install_api_key_shim() -> None:
    """Wrap HttpSession.__init__ to inject X-API-Key from env."""
    original_init = _mr_http.HttpSession.__init__

    def patched_init(self: Any, config: Any = None) -> None:
        original_init(self, config)
        api_key = os.environ.get("MOSTLYRIGHT_API_KEY") or os.environ.get(
            "THERMINAL_API_KEY"
        )
        if api_key:
            # Rebuild httpx.Client with the header. The SDK stores the
            # client as ``self._client`` and never reassigns it after
            # __init__, so this is the single mutation point.
            self._client.close()
            self._client = httpx.Client(
                base_url=self._config.base_url,
                timeout=self._config.timeout,
                headers={
                    "User-Agent": self._client.headers.get(
                        "User-Agent", "mostlyright-py"
                    ),
                    "X-API-Key": api_key,
                },
            )

    _mr_http.HttpSession.__init__ = patched_init


def main() -> int:
    _install_api_key_shim()

    cases: list[tuple[int, str, str, str, str]] = [
        (1, "KNYC", "2025-01-06", "2025-01-12", "Single-week NYC baseline"),
        (2, "KORD", "2025-04-01", "2025-04-30", "Single-month Chicago"),
        (3, "KLAX", "2025-03-01", "2025-03-31", "PST/PDT transition"),
        (4, "KMIA", "2024-12-01", "2025-11-30", "Full-year Miami, year boundary"),
        (
            5,
            "KMSY",
            "2024-09-08",
            "2024-09-22",
            "Hurricane Francine recovery — AWC gap, IEM fills",
        ),
    ]

    outdir = Path(__file__).resolve().parent
    outdir.mkdir(parents=True, exist_ok=True)

    client = MostlyRightClient()
    results: list[tuple[int, str, int, int, str]] = []
    failures = 0

    for n, station, frm, to, _why in cases:
        fname = outdir / f"case_{n}_{station}_{frm}_{to}.parquet"
        try:
            df = client.pairs(station, frm, to, as_dataframe=True)
            df.to_parquet(fname)
            rows = len(df)
            size = fname.stat().st_size
            print(f"case {n}: {fname.name} — {rows} rows, {size} bytes")
            results.append((n, "OK", rows, size, str(fname)))
        except Exception as exc:  # noqa: BLE001 — best-effort, surface all
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

    return failures


if __name__ == "__main__":
    sys.exit(main())
