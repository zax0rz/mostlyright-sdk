"""HRRR cross-cloud concurrent-fetch spike (AWS / GCP / Azure).

Same HRRR sfcf01 ``.idx`` file across the three CDN mirrors. Probes
inter-cloud latency and stability — useful for tuning the per-model
mirror priority order in :data:`mostlyright.weather._fetchers._nwp_archive.SOURCES_BY_MODEL`.

Output: markdown table to stdout, paste into FORECAST-LIMITS.md section
``## Cross-cloud (AWS vs GCP vs Azure)``.

Run::

    uv run python -m spike.forecast_limits.probe_aws_gcp_azure --n-levels 1,2,4 --repeats 2
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
    cycle_hourly = recent_cycle_utc(hours_back=2, frequency_hours=1)
    date = cycle_hourly.strftime("%Y%m%d")
    hh = cycle_hourly.strftime("%H")
    tail = f"hrrr.{date}/conus/hrrr.t{hh}z.wrfsfcf01.grib2.idx"
    return [
        Trial(
            label="hrrr_aws",
            description="HRRR sfcf01 .idx via AWS BDP",
            url=f"https://noaa-hrrr-bdp-pds.s3.amazonaws.com/{tail}",
            expected_bytes_floor=2_000,
        ),
        Trial(
            label="hrrr_gcp",
            description="HRRR sfcf01 .idx via Google",
            url=f"https://storage.googleapis.com/high-resolution-rapid-refresh/{tail}",
            expected_bytes_floor=2_000,
        ),
        Trial(
            label="hrrr_azure",
            description="HRRR sfcf01 .idx via Azure",
            url=f"https://noaahrrr.blob.core.windows.net/hrrr/{tail}",
            expected_bytes_floor=2_000,
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
    parser.add_argument("--n-levels", default="1,2,4")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()

    print("## Cross-cloud (AWS vs GCP vs Azure)")
    print()
    print("| Trial | N | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in [int(x) for x in args.n_levels.split(",")]:
        for trial in _trials():
            r = run_spike(trial, n, args.repeats)
            print(render_markdown_row(trial.label, r), flush=True)


if __name__ == "__main__":
    main()
