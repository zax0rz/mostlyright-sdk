# tests/fixtures — Two-tier fixture structure (Phase 4 SC-5)

Tradewinds keeps two independent fixture trees, with strict policy on each:

| Tree | What it contains | Re-recording policy |
|---|---|---|
| `parity/` | The **5 byte-equivalent fixtures** captured Day 0.5 against `mostlyright==0.14.1`. | **FROZEN — never re-recorded.** Any drift here is a parity-gate failure (Phase 1 HARD GATE). The byte equivalence is the contract; refreshing the bytes would change the contract. |
| `drift/` | Weekly-rotated fixtures against the SAME 5 stations + windows, captured from the **current live upstream APIs**. | **Re-recorded weekly via cron.** Drift between `drift/` and `parity/` surfaces upstream API or parser changes; small numeric drift in `obs_mean_f` columns is tolerated within the Rung-3 tolerance band, structural drift fails the build. |

## Why two tiers?

- `parity/` is the **immutable reference** — proves mostlyright reproduces the
  v0.14.1 lift baseline byte-for-byte. The 5 captured DataFrames + the
  `expected_dtypes.json` checked in at Day 0.5 are the source of truth for
  Phase 1's parity test.
- `drift/` is the **upstream-change canary** — re-recorded every week so a
  regression in IEM's CSV column ordering, AWC's METAR JSON shape, or NCEI's
  PSV publication cadence is caught within ~7 days of upstream change rather
  than at the next user-visible bug report.

## How to refresh `drift/`

`drift/` is populated by the weekly cron in
`.github/workflows/drift-rotate.yml` (Mondays 07:00 UTC). The job runs:

    uv run python tests/fixtures/drift/capture_drift.py
    uv run python tests/fixtures/drift/compare.py

against the 5 stations + windows used by `parity/`, writes the result to
`drift/case_*.parquet`, then compares against `parity/case_*.parquet`.

**Soft-fail policy.** This watchdog NEVER fails CI:

- Structural drift (column set / dtype change) → `drift-report.md`
  written, GH issue opened with labels `drift`,`phase-4`.
- Numeric drift outside the Rung-3 tolerance band (`atol=1e-12` for float
  aggregates, exact equality elsewhere) → same: report + issue.
- Within-tolerance drift → silent OK; clean week.

Drift is a signal, not a gate. The hard parity gate lives at
`tests/test_parity.py` and is run pre-publish only. If `compare.py` finds
real regression, the FIX is on the mostlyright side — never refresh
`parity/`.

## How to NEVER refresh `parity/`

There is no automated workflow that writes to `parity/`. The directory is
guarded by a `# LIFT-LOCK` comment in `tests/test_parity.py` and by the
PROJECT.md Key Decision "Sprint 0 ships only if all 5 fixtures byte-match
mostlyright==0.14.1". Any PR that touches the bytes of a `case_*.parquet`
under `parity/` requires explicit "intentional parity baseline update"
approval, which Sprint 0 will never grant.

## Status

- `parity/`: 5 fixtures present + `expected_dtypes.json` (Phase 1 Day 0.5).
- `drift/`: capture + compare scripts shipped Phase 4 (`capture_drift.py`,
  `compare.py`). Weekly cron at `.github/workflows/drift-rotate.yml`. The
  `case_*.parquet` files themselves are populated by the cron at first
  run; fresh clones see an empty `drift/` and `tests/test_drift.py`
  skips the comparator until fixtures are present.
