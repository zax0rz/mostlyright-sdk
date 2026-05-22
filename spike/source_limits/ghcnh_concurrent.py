"""GHCNh concurrent-request spike -- characterizes the NCEI static-PSV archive.

Fires N concurrent GET to the NCEI GHCNh per-year PSV endpoint across distinct
station-year tuples. Static-PSV is CDN-distributed -> expect high tolerance.

Output: markdown table to stdout, paste into ``.planning/research/SOURCE-LIMITS.md``
section ``## GHCNh static PSV archive``.

Run::

    uv run python -m spike.source_limits.ghcnh_concurrent --n-levels 1,2,4 --repeats 2

LOAD WARNING: each PSV is ~50-500 KB. N=16 x repeats=5 = 80 requests cumulative.
NCEI is a .gov public archive; this load is well below typical research-script
traffic. Polite by virtue of the spike being one-shot (re-run cadence: v0.2
milestone or policy change).
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

# Same URL pattern as packages/weather/src/tradewinds/weather/_fetchers/ghcnh.py
GHCNH_PSV_URL_TEMPLATE = (
    "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/"
    "hourly/access/by-year/{year}/psv/GHCNh_{station_id}_{year}.psv"
)

# A handful of well-known GHCNh station ids (USAF-WBAN joined form). These come
# from the v0.14.1 station registry -- picked for being long-history airports.
SPIKE_STATION_IDS = [
    "USW00094728",  # KNYC equiv (Central Park / LaGuardia history varies; OK for spike)
    "USW00094846",  # KMDW (Chicago Midway)
    "USW00023174",  # KLAX
    "USW00012839",  # KMIA
    "USW00012916",  # KMSY (New Orleans MSY)
]

SPIKE_YEARS = [2020, 2021, 2022, 2023, 2024]  # 5 x 5 = 25 distinct URLs -- covers N=16.


def _spike_urls(count: int) -> list[str]:
    """Build ``count`` distinct (station_id, year) URLs from the Cartesian product."""
    urls: list[str] = []
    for s in SPIKE_STATION_IDS:
        for y in SPIKE_YEARS:
            urls.append(GHCNH_PSV_URL_TEMPLATE.format(station_id=s, year=y))
            if len(urls) >= count:
                return urls
    return urls


def fetch_one(url: str) -> RequestResult:
    t0 = time.monotonic()
    try:
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
        urls = _spike_urls(n)
        batch = fan_out(urls, max_workers=n, fetch=fetch_one)
        result.per_request.extend(batch)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-levels", default="1,2,4,8,16", help="comma-separated N values")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()

    print("## GHCNh static PSV archive (`ncei.noaa.gov`)")
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
