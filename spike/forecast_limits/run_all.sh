#!/usr/bin/env bash
# Phase 17 FORECAST-10 — run all forecast-mirror probes and tee output.
#
# Each individual probe gets a per-probe timeout cap. Total wall-clock
# stays under ~30 min for the full sweep. Failures + timeouts are caught
# so a single mirror outage does not abort the rest.
#
# NOMADS 403 → exits the NOMADS step with code 2; the trap below logs
# it but lets the sweep continue with the remaining mirrors.

set -uo pipefail
cd "$(dirname "$0")/../.."

echo "=== AWS BDP ==="
timeout 600 uv run python -m spike.forecast_limits.probe_aws_bdp --n-levels 1,2,4,8 --repeats 2 \
    || echo "AWS BDP failed/timed out"

echo
echo "=== NOMADS (with 403 fail-fast) ==="
timeout 300 uv run python -m spike.forecast_limits.probe_nomads --n-levels 1,2,4 --repeats 2 \
    || echo "NOMADS failed/timed out (403 abort expected on banned IPs)"

echo
echo "=== ECMWF Open Data ==="
timeout 600 uv run python -m spike.forecast_limits.probe_ecmwf_open --n-levels 1,2,4,8 --repeats 2 \
    || echo "ECMWF failed/timed out"

echo
echo "=== MSC Datamart ==="
timeout 300 uv run python -m spike.forecast_limits.probe_msc --n-levels 1,2,4 --repeats 2 \
    || echo "MSC failed/timed out"

echo
echo "=== Cross-cloud (AWS / GCP / Azure) ==="
timeout 300 uv run python -m spike.forecast_limits.probe_aws_gcp_azure --n-levels 1,2,4 --repeats 2 \
    || echo "Cross-cloud failed/timed out"

echo
echo "=== ALL DONE ==="
echo "Aggregate JSON-style markdown rows into .planning/research/FORECAST-LIMITS.md"
