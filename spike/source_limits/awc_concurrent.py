"""AWC concurrent-request spike -- characterizes ``aviationweather.gov`` tolerance.

Fires N concurrent GET to the AWC METAR endpoint for distinct stations.
Measures p50/p95/p99 + status-code distribution + body size.

Output: markdown table to stdout, paste into ``.planning/research/SOURCE-LIMITS.md``
section ``## AWC METAR live endpoint``.

Run::

    uv run python -m spike.source_limits.awc_concurrent --n-levels 1,2,4 --repeats 2

LOAD WARNING: each request returns ~7 days of METARs for one station (~10-50 KB).
N=16 x repeats=5 = 80 cumulative requests; well below typical scraper traffic but
respectful. Politeness: AWC has no published rate limit. PERF-05 spike documents
the empirical limit. See module README for re-run cadence.
"""

from __future__ import annotations

import argparse
import time

import httpx

from ._common import (
    RequestResult,
    SpikeResult,
    fan_out,
    render_markdown_row,
)

# Same URL pattern as packages/weather/src/tradewinds/weather/_fetchers/awc.py
AWC_METAR_URL = "https://aviationweather.gov/api/data/metar?ids={station}&format=json&hours=168"

# 20 distinct stations -- large enough for N=16 without repeats.
SPIKE_STATIONS = [
    "KNYC", "KLAX", "KMIA", "KMDW", "KORD", "KATL", "KDEN", "KBOS",
    "KSFO", "KSEA", "KAUS", "KIAD", "KDFW", "KPHX", "KMCO", "KMSP",
    "KCLE", "KDTW", "KLAS", "KPDX",
]  # fmt: skip


def fetch_one(url: str) -> RequestResult:
    t0 = time.monotonic()
    try:
        # 60s timeout matches Plan 01 PERF-03 HTTP_TIMEOUT -- measure under the
        # same client posture production code will use.
        r = httpx.get(url, timeout=60.0)
        elapsed = time.monotonic() - t0
        return RequestResult(
            url=url,
            status_code=r.status_code,
            elapsed_s=elapsed,
            body_size_bytes=len(r.content),
        )
    except Exception as exc:
        return RequestResult(
            url=url,
            status_code=0,
            elapsed_s=time.monotonic() - t0,
            body_size_bytes=0,
            error=str(exc),
        )


def run_spike(n: int, repeats: int) -> SpikeResult:
    result = SpikeResult(n=n, repeats=repeats)
    for _ in range(repeats):
        urls = [AWC_METAR_URL.format(station=s) for s in SPIKE_STATIONS[:n]]
        batch = fan_out(urls, max_workers=n, fetch=fetch_one)
        result.per_request.extend(batch)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-levels", default="1,2,4,8,16", help="comma-separated N values")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    print("## AWC METAR live endpoint (`/api/data/metar`)")
    print()
    print(
        "| N (concurrent) | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | error_count |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for n in [int(x) for x in args.n_levels.split(",")]:
        r = run_spike(n, args.repeats)
        print(render_markdown_row(f"N={n}", r), flush=True)


if __name__ == "__main__":
    main()
