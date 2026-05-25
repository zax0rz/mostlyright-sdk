# spike/forecast_limits — empirical NWP-mirror concurrency probes

Mirrors `spike/source_limits/` but for forecast mirrors (Phase 17 FORECAST-10).
Probes AWS BDP, NOMADS, ECMWF Open Data, MSC Datamart, and the cross-cloud
HRRR triple (AWS / Google / Azure) at varying concurrency levels and
emits markdown tables for `.planning/research/FORECAST-LIMITS.md`.

## Why these are spikes, not tests

The same rationale as `spike/source_limits/`:

1. They hit **live public mirrors** at scale — running them in CI on every
   commit would be impolite and could trip rate limits, especially NOMADS
   (Herbie issue #371 IP-ban evidence).
2. The results characterize a moment in time — mirror operators rotate
   limits without notice; what we measure today may not hold next quarter.
3. Output is markdown for human review, not a pytest assertion. The number
   plugged into `_nwp_archive.NOMADS_CONCURRENCY_CAP` (currently `4`)
   should be re-verified against this output every few months.

## NOMADS warning

**Do not run `probe_nomads.py` with `--n-levels 8,16` or in tight loops.**
Herbie issue #371 documents that NOMADS bans IPs that fire mass-404
patterns from FastHerbie-style concurrent crawls. The probe has a
**`detect_403_and_abort`** guard that aborts the entire NOMADS sweep on
the first 403 — heed it. If the spike returns 403 on N=1, do not retry
until the operator can verify the IP is unblocked (typically requires
NOAA support contact; can take days).

## How to run

```bash
bash spike/forecast_limits/run_all.sh 2>&1 | tee /tmp/forecast_limits_output.txt
```

Expected wall-clock: ~20–30 min for the full sweep. Per-mirror scripts
can also run individually:

```bash
uv run python -m spike.forecast_limits.probe_aws_bdp --n-levels 1,2,4,8 --repeats 2
uv run python -m spike.forecast_limits.probe_nomads --n-levels 1,2,4 --repeats 2
uv run python -m spike.forecast_limits.probe_ecmwf_open --n-levels 1,2,4,8 --repeats 2
uv run python -m spike.forecast_limits.probe_msc --n-levels 1,2,4 --repeats 2
uv run python -m spike.forecast_limits.probe_aws_gcp_azure --n-levels 1,2,4 --repeats 2
```

## What to do with the output

Aggregate the per-probe markdown tables into
`.planning/research/FORECAST-LIMITS.md`. Required sections:

1. Header with spike date + re-run command + "valid until" note.
2. Per-mirror H2 sections: `## AWS BDP`, `## NOMADS`,
   `## ECMWF Open Data`, `## MSC Datamart`,
   `## Cross-cloud (AWS vs GCP vs Azure)`.
3. Per-section table from the probe stdout.
4. Per-mirror "Recommended max concurrent" + `httpx.Limits(...)` config.
5. NOMADS section MUST document 403 fail-fast posture + cite
   `NOMADS_CONCURRENCY_CAP=4` from `_nwp_archive.py` as the load-bearing
   constant.

## Re-run triggers

Re-run when:

- Phase 17 Wave 2 adds new mirror keys (ECMWF AWS eu-central-1 stops
  responding, etc.).
- A user reports rate-limit errors against `forecast_nwp()` in the wild.
- It's been >6 months since the last spike (mirror posture drift).
- `NOMADS_CONCURRENCY_CAP` is being adjusted in `_nwp_archive.py`.
