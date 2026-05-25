"""NOMADS concurrent-idx-fetch spike with 403 fail-fast (Herbie #371).

NOMADS bans IPs that fire mass-404 patterns from FastHerbie-style
concurrent crawls. This probe stays small (idx files only, never full
GRIB2) and aborts on the first 403 via :class:`NomadsAbusiveUserBlocked`.

LOAD WARNING: Default ``--n-levels 1,2,4`` — do NOT pass ``8`` or higher.
If the probe returns 403 on N=1, do not retry; the IP is probably already
on a banlist.

Output: markdown table to stdout, paste into FORECAST-LIMITS.md section
``## NOMADS``.

Run::

    uv run python -m spike.forecast_limits.probe_nomads --n-levels 1,2,4 --repeats 2
"""

from __future__ import annotations

import argparse
import sys
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


class NomadsAbusiveUserBlocked(Exception):
    """NOMADS returned 403 — abort the entire sweep.

    Per Herbie issue #371, NOMADS bans IPs whose access pattern matches
    abusive crawls. The fix is operator-side (contact NOAA support); the
    probe MUST abort hard rather than continue and dig the ban deeper.
    """


def detect_403_and_abort(status_code: int, url: str) -> None:
    """Raise :class:`NomadsAbusiveUserBlocked` if ``status_code == 403``."""
    if status_code == 403:
        print(
            f"\n!!! NOMADS returned 403 for {url} — IP-ban posture per Herbie #371. "
            "Aborting NOMADS sweep. See FORECAST-LIMITS.md NOMADS section.\n",
            file=sys.stderr,
        )
        raise NomadsAbusiveUserBlocked(url)


def _trials() -> list[Trial]:
    cycle_hourly = recent_cycle_utc(hours_back=2, frequency_hours=1)
    cycle_6h = recent_cycle_utc(hours_back=6, frequency_hours=6)
    date_hrrr = cycle_hourly.strftime("%Y%m%d")
    hh_hrrr = cycle_hourly.strftime("%H")
    date_gfs = cycle_6h.strftime("%Y%m%d")
    hh_gfs = cycle_6h.strftime("%H")
    return [
        Trial(
            label="hrrr_idx",
            description="HRRR sfcf01 .idx via NOMADS",
            url=(
                f"https://nomads.ncep.noaa.gov/pub/data/nccf/com/hrrr/prod/"
                f"hrrr.{date_hrrr}/conus/hrrr.t{hh_hrrr}z.wrfsfcf01.grib2.idx"
            ),
            expected_bytes_floor=2_000,
        ),
        Trial(
            label="gfs_idx",
            description="GFS pgrb2 f006 .idx via NOMADS",
            url=(
                f"https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/"
                f"gfs.{date_gfs}/{hh_gfs}/atmos/gfs.t{hh_gfs}z.pgrb2.0p25.f006.idx"
            ),
            expected_bytes_floor=10_000,
        ),
    ]


def _fetch_one(trial: Trial) -> RequestResult:
    t0 = time.monotonic()
    try:
        r = httpx.get(trial.url, timeout=60.0)
        detect_403_and_abort(r.status_code, trial.url)
        return RequestResult(
            url=trial.url,
            status_code=r.status_code,
            elapsed_s=time.monotonic() - t0,
            body_size_bytes=len(r.content),
        )
    except NomadsAbusiveUserBlocked:
        raise
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
        # detect_403 may have been raised inside fan_out's executor; surface it.
        for res in batch:
            if res.status_code == 403:
                detect_403_and_abort(res.status_code, res.url)
        result.per_request.extend(batch)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-levels", default="1,2,4")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()

    print("## NOMADS")
    print()
    print(
        "_403 fail-fast active per Herbie issue #371. Default cap "
        "`NOMADS_CONCURRENCY_CAP=4` lives in `_nwp_archive.py`._"
    )
    print()
    print("| Trial | N | p50_s | p95_s | p99_s | status_dist | mean_size_b | max_size_b | err |")
    print("|---|---|---|---|---|---|---|---|---|")
    try:
        for n in [int(x) for x in args.n_levels.split(",")]:
            for trial in _trials():
                r = run_spike(trial, n, args.repeats)
                print(render_markdown_row(trial.label, r), flush=True)
    except NomadsAbusiveUserBlocked as exc:
        print(f"\n!!! ABORTED — NOMADS 403 on {exc}. See stderr above.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
