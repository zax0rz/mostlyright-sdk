"""ECMWF Open Data concurrent-index-fetch spike (Phase 17 FORECAST-10).

Probes the three published mirrors for the IFS HRES ``.index`` companion:

- ECMWF origin: ``data.ecmwf.int``
- Google CDN: ``storage.googleapis.com/ecmwf-open-data``
- AWS eu-central-1: ``ecmwf-forecasts.s3.eu-central-1.amazonaws.com``

ECMWF docs cap simultaneous connections at 500/IP — we stay well below.

Output: markdown table to stdout, paste into FORECAST-LIMITS.md section
``## ECMWF Open Data``.

Run::

    uv run python -m spike.forecast_limits.probe_ecmwf_open --n-levels 1,2,4,8 --repeats 2
"""

from __future__ import annotations

import argparse
import time

import httpx

from ._common import (
    RequestResult,
    SpikeResult,
    Trial,
    fan_out,
    recent_cycle_utc,
    render_markdown_row,
)


def _trials() -> list[Trial]:
    cycle = recent_cycle_utc(hours_back=6, frequency_hours=6)
    date = cycle.strftime("%Y%m%d")
    hhz = cycle.strftime("%Hz")
    dtstamp = cycle.strftime("%Y%m%d%H%M%S")
    post_root = f"{date}/{hhz}/ifs/0p25/oper/{dtstamp}-0h-oper-fc.index"
    return [
        Trial(
            label="ecmwf_origin",
            description="data.ecmwf.int IFS HRES .index",
            url=f"https://data.ecmwf.int/forecasts/{post_root}",
            expected_bytes_floor=50_000,
        ),
        Trial(
            label="ecmwf_gcp",
            description="Google CDN IFS HRES .index",
            url=f"https://storage.googleapis.com/ecmwf-open-data/{post_root}",
            expected_bytes_floor=50_000,
        ),
        Trial(
            label="ecmwf_aws",
            description="AWS eu-central-1 IFS HRES .index",
            url=(f"https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com/{post_root}"),
            expected_bytes_floor=50_000,
        ),
    ]


def _fetch_one(trial: Trial) -> RequestResult:
    t0 = time.monotonic()
    try:
        r = httpx.get(trial.url, timeout=60.0)
        return RequestResult(
            url=trial.url,
            status_code=r.status_code,
            elapsed_s=time.monotonic() - t0,
            body_size_bytes=len(r.content),
        )
    except Exception as exc:
        return RequestResult(
            url=trial.url,
            status_code=0,
            elapsed_s=time.monotonic() - t0,
            body_size_bytes=0,
            error=str(exc),
        )


def run_spike(trial: Trial, n: int, repeats: int) -> SpikeResult:
    result = SpikeResult(n=n, repeats=repeats)
    for _ in range(repeats):
        batch = fan_out([trial.url] * n, max_workers=n, fetch=lambda _u: _fetch_one(trial))
        result.per_request.extend(batch)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-levels", default="1,2,4,8")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()

    print("## ECMWF Open Data")
    print()
    print("| Trial | N | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in [int(x) for x in args.n_levels.split(",")]:
        for trial in _trials():
            r = run_spike(trial, n, args.repeats)
            print(render_markdown_row(trial.label, r), flush=True)


if __name__ == "__main__":
    main()
