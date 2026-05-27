# TS Parity Gate

The cross-language trust mechanism: TS `research()` row output MUST
match Python `mostlyright.research()` byte-for-byte (per the 19-column
canonical surface) for 5 committed fixture cases.

## Status

| Component | Status | Source of Truth |
|---|---|---|
| Test runner | ✅ `parity.test.ts` (TS-W2; Phase 21 21-02) | this dir |
| Row-equivalence assertion | ✅ `_assertions.ts` (TS-W2 SC#1) | this dir |
| Python parity fixtures | ✅ 5 parquets + 5 JSON projections | `tests/fixtures/parity/` |
| TS expected JSON | ✅ 5 cases (re-exported via `export_for_ts.py`) | `tests/fixtures/parity/ts/` |
| msw recordings | ⏳ operator-gated (Phase 21 21-02 Task 1) | `recordings/` |
| CI wire-up | ✅ runs as part of `pnpm -r test` in `test-ts.yml` | `.github/workflows/test-ts.yml` |
| Drift watchdog | ✅ weekly cron, soft-fail | `.github/workflows/drift-rotate-ts.yml` |

When `recordings/case_N/handlers.json` exists for all 5 cases, the test
becomes a HARD gate: any case failing the row-equivalence assertion →
CI fails. Until then, missing recordings show as `it.todo` (visible in
test output, NOT silently green).

## What the gate enforces

Per Phase 21 D-02 (21-CONTEXT.md): "After Phase 21 W5, the TS parity
gate (5 msw recordings vs Python fixtures via row-equivalence
assertion) MUST be green on `main`."

The 5 fixture cases (mirror `tests/fixtures/parity/README.md`):

| # | Station | Window | Theme |
|---|---|---|---|
| 1 | KNYC | 2025-01-06 → 2025-01-12 | Winter — short window |
| 2 | KMDW | 2025-04-01 → 2025-04-30 | Shoulder — month window |
| 3 | KLAX | 2025-03-01 → 2025-03-31 | Spring — month window |
| 4 | KMIA | 2024-12-01 → 2025-11-30 | Year-wrap — multi-year |
| 5 | KMSY | 2024-09-08 → 2024-09-22 | Storm — irregular hourly |

Row equivalence asserts exact match on all 19 columns of
`research()` output (date / station / cli_* / obs_* / fcst_* /
market_close_utc) and identical row count.

## When to regenerate

Regenerate fixtures + recordings ONLY when:

1. **A Python parity fixture changes.** Run
   `python tests/fixtures/parity/capture_fixtures.py` to refresh
   parquets; then `python tests/fixtures/parity/export_for_ts.py` to
   refresh the TS JSON projections.
2. **The TS HTTP surface changes** (new fetcher, different URL, header
   tweak). Recapture msw recordings:
   ```bash
   MOSTLYRIGHT_TS_LIVE=1 pnpm --filter mostlyright capture-parity
   ```
   This is operator-gated (requires real network access to AWC/IEM/GHCNh).
3. **Bumping `_cache_schema_version`** (Phase 21 21-03). Drop and
   recapture — cached values from the old version won't replay.

DON'T regenerate as part of normal development. The point of the gate
is to catch drift; recapturing to "make the test pass" defeats the
gate.

## How to regenerate (operator workflow)

From repo root:

```bash
# 1. Refresh Python ground truth (only if Python output changed).
uv run python tests/fixtures/parity/capture_fixtures.py
uv run python tests/fixtures/parity/export_for_ts.py

# 2. Capture msw recordings (only if TS HTTP surface changed).
#    Requires real network access; sleeps respect polite floors.
MOSTLYRIGHT_TS_LIVE=1 pnpm --filter mostlyright capture-parity

# 3. Verify both sides converged.
pnpm --filter mostlyright test parity.test.ts

# 4. Commit recordings + (if changed) Python ground truth in ONE PR.
git add packages-ts/meta/tests/parity/recordings tests/fixtures/parity/
git commit -m "parity: refresh fixtures + msw recordings (reason)"
```

## How drift watchdog interacts

`.github/workflows/drift-rotate-ts.yml` runs weekly (Mondays 07:00 UTC)
+ on `workflow_dispatch`. It:

1. Runs `research()` against a fresh capture for each of the 5 cases.
2. Diffs the output against the committed JSON fixtures.
3. If any case drifts: posts a labelled GitHub issue (NEVER fails CI).

The watchdog is informational — it surfaces upstream API drift (IEM
schema changes, AWC adding/dropping fields, etc.) so we can refresh
fixtures intentionally instead of being surprised on the next manual
recapture.

## Cross-references

- Phase 21 21-CONTEXT.md D-02 + D-07 — locked decisions on the gate
  shape + recording layout
- `tests/fixtures/parity/README.md` — Python-side fixture details
- `packages-ts/meta/tests/parity/recordings/README.md` — capture script
  + status
- `.github/workflows/test-ts.yml` — CI wire-up
- `.github/workflows/drift-rotate-ts.yml` — drift watchdog
