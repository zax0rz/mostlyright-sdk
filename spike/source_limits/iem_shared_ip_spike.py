"""IEM shared-IP throttle spike -- Pitfall 5 / Assumption A3 verifier.

Hypothesis: IEM 1-sec per-IP throttle (published 2026-04-21) at
``mesonet.agron.iastate.edu`` applies to BOTH ``asos.py`` and ``cli.py`` as a
SHARED budget. If true, then a PERF-04 design that fires concurrent IEM-ASOS +
IEM-CLI threads (each sleeping 1s between requests) emits 2 req/sec to the same
IP and risks 503s / endpoint slowdown.

Methodology
===========

- **Baseline** -- 1 IEM-ASOS thread, ``--repeats`` requests, 1 sec/req. Count 503s.
- **Treatment** -- 1 IEM-ASOS + 1 IEM-CLI thread concurrent, each ``--repeats``
  requests, each 1 sec/req. Count 503s per thread.

If treatment 503-rate >> baseline -> SHARED IP confirmed -> Option A (lock).
If treatment 503-rate ~ baseline -> separate per-endpoint budgets -> Option C (no lock).
Anything in between -> Option B (max_workers=3, serialize IEM ASOS+CLI).

Output: markdown table + an EXPLICIT recommendation for PERF-04. The
recommendation logic is deterministic -- no narrative override.

Run::

    uv run python -m spike.source_limits.iem_shared_ip_spike --repeats 4

LOAD WARNING: total requests = 3 x repeats (baseline + 2 treatment threads). At
``--repeats=10`` that's 30 cumulative requests, ~30s wall time including the
1-sec/req politeness. Re-run cadence: v0.2 milestone or IEM policy change.
"""

from __future__ import annotations

import argparse
import threading
import time

import httpx

from ._common import (
    RequestResult,
    SpikeResult,
    render_markdown_row,
)

# Mirror production constant (packages/weather/src/tradewinds/weather/_fetchers/iem_asos.py).
IEM_POLITE_DELAY = 1.0

# Distinct stations for each thread to avoid station-cache collisions IEM-side.
ASOS_STATIONS = [
    "NYC", "LAX", "MIA", "MDW", "ORD", "ATL", "DEN", "BOS", "SFO", "SEA",
]  # fmt: skip
CLI_STATIONS = [
    "KAUS", "KIAD", "KDFW", "KPHX", "KMCO", "KMSP", "KCLE", "KDTW", "KLAS", "KPDX",
]  # fmt: skip

# Same URL patterns as production fetchers; year=2024 for a stable historical window.
ASOS_URL_TEMPLATE = (
    "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
    "?station={station}&data=all&tz=Etc/UTC&format=comma&latlon=no&elev=no"
    "&missing=M&trace=T&direct=no&report_type=3"
    "&year1=2024&month1=1&day1=1"
    "&year2=2024&month2=1&day2=2"
)
CLI_URL_TEMPLATE = "https://mesonet.agron.iastate.edu/json/cli.py?station={station}&year=2024"


def _fetch(url: str) -> RequestResult:
    t0 = time.monotonic()
    try:
        r = httpx.get(url, timeout=60.0)
        return RequestResult(
            url=url,
            status_code=r.status_code,
            elapsed_s=time.monotonic() - t0,
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


def serial_thread(urls: list[str], delay: float) -> SpikeResult:
    result = SpikeResult(n=1, repeats=len(urls))
    for url in urls:
        result.per_request.append(_fetch(url))
        time.sleep(delay)
    return result


def measure_shared_ip(repeats: int) -> tuple[SpikeResult, SpikeResult, SpikeResult]:
    """Returns ``(baseline_asos, treatment_asos, treatment_cli)``."""
    urls_asos_baseline = [ASOS_URL_TEMPLATE.format(station=s) for s in ASOS_STATIONS[:repeats]]
    baseline = serial_thread(urls_asos_baseline, IEM_POLITE_DELAY)

    urls_asos = [ASOS_URL_TEMPLATE.format(station=s) for s in ASOS_STATIONS[:repeats]]
    urls_cli = [CLI_URL_TEMPLATE.format(station=s) for s in CLI_STATIONS[:repeats]]

    treatment_asos = SpikeResult(n=2, repeats=repeats)
    treatment_cli = SpikeResult(n=2, repeats=repeats)

    def run_asos() -> None:
        r = serial_thread(urls_asos, IEM_POLITE_DELAY)
        treatment_asos.per_request.extend(r.per_request)

    def run_cli() -> None:
        r = serial_thread(urls_cli, IEM_POLITE_DELAY)
        treatment_cli.per_request.extend(r.per_request)

    t1 = threading.Thread(target=run_asos)
    t2 = threading.Thread(target=run_cli)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    return baseline, treatment_asos, treatment_cli


def recommend_option(
    baseline: SpikeResult,
    treatment_asos: SpikeResult,
    treatment_cli: SpikeResult,
) -> str:
    """Deterministically map 503-count evidence to Option A/B/C."""
    baseline_503 = baseline.status_distribution.get(503, 0) + baseline.error_count
    treatment_503 = (
        treatment_asos.status_distribution.get(503, 0)
        + treatment_cli.status_distribution.get(503, 0)
        + treatment_asos.error_count
        + treatment_cli.error_count
    )

    # Threshold: treatment > 2 * max(baseline, 1) -> SHARED IP confirmed.
    if treatment_503 > 2 * max(baseline_503, 1):
        return (
            "**Option A (RECOMMENDED -- SHARED IP confirmed):** Use "
            "``threading.Lock()`` shared between IEM-ASOS and IEM-CLI workers "
            "in ``research.py``. Acquire the lock around ``download_with_retry`` "
            "calls in IEM fetchers only. Treatment 503/error rate "
            f"({treatment_503}) significantly exceeded baseline ({baseline_503})."
        )
    if treatment_503 <= baseline_503:
        return (
            "**Option C (RECOMMENDED -- separate per-endpoint budgets):** No "
            "additional synchronization needed. Treatment 503/error rate "
            f"({treatment_503}) ~ baseline ({baseline_503}). The IEM ``asos.py`` "
            "and ``cli.py`` endpoints appear to have separate throttle budgets; "
            "PERF-04's concurrent IEM threads are safe as-sketched."
        )
    return (
        f"**Option B (RECOMMENDED -- partial-share suspected):** Treatment 503/error "
        f"rate ({treatment_503}) is elevated over baseline ({baseline_503}) but not "
        "2x+. Use ``max_workers=3`` with serialized IEM ASOS+CLI in a single 'iem' "
        "worker function. Loses some parallelism but is structurally safe and avoids "
        "the lock-contention complexity of Option A."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=10, help="Requests per thread")
    args = parser.parse_args()

    print("## IEM shared-IP throttle test (Pitfall 5 / Assumption A3)")
    print()
    print(
        f"Methodology: baseline = 1 serial ASOS thread, {args.repeats} requests, "
        "1 sec/req. Treatment = 1 ASOS + 1 CLI thread concurrent, each "
        f"{args.repeats} requests, each 1 sec/req."
    )
    print()
    baseline, treatment_asos, treatment_cli = measure_shared_ip(args.repeats)

    print(
        "| Variant | requests | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | error_count |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    print(render_markdown_row("baseline (1 ASOS)", baseline))
    print(render_markdown_row("treatment (ASOS, concurrent w/ CLI)", treatment_asos))
    print(render_markdown_row("treatment (CLI, concurrent w/ ASOS)", treatment_cli))
    print()
    print("### Recommendation for Plan 03 PERF-04 design")
    print()
    print(recommend_option(baseline, treatment_asos, treatment_cli))


if __name__ == "__main__":
    main()
