"""MSC Datamart HRDPS concurrent-fetch spike (Phase 17 FORECAST-10).

MSC throttle is undocumented — be polite (default N≤4). Probes the
HRDPS continental TMP TGL_2 fxx=001 file (small per-variable GRIB2,
typically <500 KB).

Output: markdown table to stdout, paste into FORECAST-LIMITS.md section
``## MSC Datamart``.

Run::

    uv run python -m spike.forecast_limits.probe_msc --n-levels 1,2,4 --repeats 2
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
    hh = cycle.strftime("%H")
    dt_hms = cycle.strftime("%Y%m%dT%H")
    return [
        Trial(
            label="hrdps_tmp_tgl2",
            description="HRDPS continental 2.5km TMP TGL_2 fxx=001",
            url=(
                f"https://dd.weather.gc.ca/{date}/WXO-DD/model_hrdps/"
                f"continental/2.5km/{hh}/001/{dt_hms}Z_MSC_HRDPS_TMP_TGL_2_"
                "RLatLon0.0225_PT001H.grib2"
            ),
            expected_bytes_floor=100_000,
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

    print("## MSC Datamart")
    print()
    print("_Undocumented throttle — keep N≤4 by default. Remember the 24h retention._")
    print()
    print("| Trial | N | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in [int(x) for x in args.n_levels.split(",")]:
        for trial in _trials():
            r = run_spike(trial, n, args.repeats)
            print(render_markdown_row(trial.label, r), flush=True)


if __name__ == "__main__":
    main()
