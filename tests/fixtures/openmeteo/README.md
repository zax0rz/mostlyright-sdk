# OM-08 Leakage Regression Fixtures (Phase 20)

**Purpose:** Reproduce and prevent the
[Tarabcak/mostlyright#70](https://github.com/Tarabcak/mostlyright/issues/70)
corner case where the legacy seamless feed silently used post-snapshot
model runs in training data.

## The 5 fixtures

| # | Station | Date | Snapshot (as_of) | Why |
|---|---------|------|------------------|-----|
| 1 | KNYC | 2024-06-01 | 2024-06-01T17:00Z (h13 EDT) | The exact #70 reproduction |
| 2 | KORD | 2024-07-15 | 2024-07-15T12:00Z (h07 CDT) | Pre-noon snapshot |
| 3 | KDEN | 2024-08-22 | 2024-08-22T22:00Z (h16 MDT) | Post-cycle-publish snapshot |
| 4 | KMIA | 2024-09-10 | 2024-09-10T00:00Z | Midnight UTC boundary |
| 5 | KSEA | 2024-10-05 | 2024-10-05T20:00Z (h13 PDT) | Pacific timezone |

## Format

Each fixture is a synthesized Open-Meteo Previous Runs API response with
the day's full 24-hour `temperature_2m_previous_day1` series. The
regression suite asserts the conservative-floor formula's correctness,
not the exact upstream values — see
[20-RESEARCH.md §Endpoint reference §Endpoint 1](../../../.planning/phases/20-open-meteo-forecast-source-integration-leakage-safe-40-model/20-RESEARCH.md)
for the canonical response shape.

## How to re-capture against the live API (optional)

```bash
curl 'https://previous-runs-api.open-meteo.com/v1/forecast?latitude=40.78&longitude=-73.97&start_date=2024-06-01&end_date=2024-06-01&hourly=temperature_2m_previous_day1&models=gfs_global&timezone=UTC' \
  > tests/fixtures/openmeteo/case_1_KNYC_2024-06-01_h13.json
```

Synthesized fixtures suffice for the regression because the test
asserts formula correctness (`issued_at = floor_to_cycle(valid_at − 24h, cycles)`)
against deterministic outputs from PLAN-03's `cycle_math.py` rather
than against any specific upstream value.

## Acceptance check

`tests/test_open_meteo_leakage_regression.py` loads each fixture and
asserts (per case):

1. Every row in the output has `issued_at ≤ as_of` (no leakage)
2. `LeakageDetector(as_of=...).check_issued_at(df)` does not raise
3. `assert_issued_at_populated(df)` does not raise
4. No row has `source = "open_meteo.seamless"`
5. (case_1 only) The 23:00 UTC `valid_at` row has `issued_at == 2024-05-31T18:00Z`

If any assertion fails, that fixture's case is broken and the
regression suite blocks the phase from shipping.

## Origin

Tarabcak/mostlyright#70 — see the phase research document
(`.planning/phases/.../20-RESEARCH.md`) §Legacy bug reproduction for the
full post-mortem including the exact 6 tainted features and the
apparent +6pp MCAGE-OM lift attribution.
