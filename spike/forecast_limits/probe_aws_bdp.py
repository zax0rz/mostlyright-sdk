"""AWS Big Data Program HRRR / GFS / NBM concurrent-fetch spike.

Fires N concurrent GETs against the canonical AWS BDP mirrors. Two trial
shapes per cycle:

- ``*_idx``: tiny ``.idx`` companion (~10-30 KB). Probes mirror
  throughput at small-object sizes (the production hot path).
- ``*_byterange``: 1 MB ``Range:`` byte-range against the GRIB2 file.
  Probes mirror behaviour under realistic byte-range traffic — what
  ``forecast_nwp()`` actually does.

LOAD WARNING: NOT pulling full ~135 MB / ~450 MB GRIB2 files. Byte-range
sizes intentionally capped at 1 MB so the spike's cumulative footprint
stays under ~50 MB.

Output: markdown table to stdout, paste into FORECAST-LIMITS.md section
``## AWS BDP``.

Run::

    uv run python -m spike.forecast_limits.probe_aws_bdp --n-levels 1,2,4,8 --repeats 2
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

_BYTERANGE_END = 1_048_575  # 1 MB - 1 byte (inclusive)


def _trials() -> list[Trial]:
    cycle = recent_cycle_utc(hours_back=6, frequency_hours=6)
    cycle_hourly = recent_cycle_utc(hours_back=2, frequency_hours=1)
    date_hrrr = cycle_hourly.strftime("%Y%m%d")
    hh_hrrr = cycle_hourly.strftime("%H")
    date_gfs = cycle.strftime("%Y%m%d")
    hh_gfs = cycle.strftime("%H")
    return [
        Trial(
            label="hrrr_idx",
            description="HRRR sfcf01 .idx (~10 KB)",
            url=(
                f"https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{date_hrrr}/"
                f"conus/hrrr.t{hh_hrrr}z.wrfsfcf01.grib2.idx"
            ),
            expected_bytes_floor=2_000,
        ),
        Trial(
            label="hrrr_byterange_1mb",
            description="HRRR sfcf01 1 MB byte-range",
            url=(
                f"https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{date_hrrr}/"
                f"conus/hrrr.t{hh_hrrr}z.wrfsfcf01.grib2"
            ),
            expected_bytes_floor=900_000,
        ),
        Trial(
            label="gfs_idx",
            description="GFS pgrb2 f006 .idx (~20 KB)",
            url=(
                f"https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{date_gfs}/"
                f"{hh_gfs}/atmos/gfs.t{hh_gfs}z.pgrb2.0p25.f006.idx"
            ),
            expected_bytes_floor=10_000,
        ),
        Trial(
            label="nbm_idx",
            description="NBM CO f001 .idx (~5 KB)",
            url=(
                f"https://noaa-nbm-pds.s3.amazonaws.com/blend.{date_hrrr}/"
                f"{hh_hrrr}/core/blend.t{hh_hrrr}z.core.f001.co.grib2.idx"
            ),
            expected_bytes_floor=1_000,
        ),
    ]


def _fetch_one(trial: Trial) -> RequestResult:
    headers: dict[str, str] = {}
    if "byterange" in trial.label:
        headers["Range"] = f"bytes=0-{_BYTERANGE_END}"
    t0 = time.monotonic()
    try:
        r = httpx.get(trial.url, timeout=60.0, headers=headers)
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

    print("## AWS BDP")
    print()
    print("| Trial | N | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in [int(x) for x in args.n_levels.split(",")]:
        for trial in _trials():
            r = run_spike(trial, n, args.repeats)
            print(render_markdown_row(trial.label, r), flush=True)


if __name__ == "__main__":
    main()
