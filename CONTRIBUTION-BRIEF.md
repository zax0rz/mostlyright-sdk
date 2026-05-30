# Contribution Brief — MostlyRight SDK Issue #16

## Context

You are working on a fork of `mostlyrightmd/mostlyright-sdk` at `~/.openclaw/workspace-chad/mostlyright-sdk`.
- **origin** = `zax0rz/mostlyright-sdk` (your fork, push PRs here)
- **upstream** = `mostlyrightmd/mostlyright-sdk` (Vu's repo, PR target)
- **Current upstream head:** `8c5a236` (v1.3.0, Phase 20 Open-Meteo)

**Target issue:** <https://github.com/mostlyrightmd/mostlyright-sdk/issues/16>
"SDK emits false-precision temp_f for U.S. ASOS observations (Tgroup is integer-°F native)"

**IMPORTANT READ FIRST:** `CLAUDE.md` in the repo root has detailed project conventions. Read it before writing any code. Key points:
- TDD mandatory: RED → GREEN → REFACTOR
- Pre-commit hooks: `uv run pre-commit install && uv run pre-commit install --hook-type pre-push`
- Lint: `uv run ruff check --fix . && uv run ruff format .`
- Tests: `uv run pytest -m "not live" -q`
- Branch naming: `fix/issue-16-tgroup-precision` or similar
- Two-reviewer loop for data semantics changes (this IS data semantics)
- Do NOT commit directly to main — branch + PR only
- TS Parity section required for any public API change (this fix is internal, but document it anyway)

## What's Already Done (Phase 18)

Vu already fixed the AWC path (Phase 18 PREC-01/02/03) in v1.1.0-v1.1.2:
- `_awc.py` now uses `float(round(temp_c * 9 / 5 + 32))` for Tgroup-bearing rows → integer °F
- `_iem.py` keeps raw `tmpf` as float (integer-valued) for temp_f, does NOT re-parse Tgroup
- `observation.json` schema updated with correct documentation
- `daily_extreme.json` schema updated with Phase 18 precision rationale
- `test_international.py` updated with realistic integer-°F lattice values
- Live anti-regression tests added (12 stations, 168h each)
- Property tests for Tgroup round-trip added
- TS parity ported

## What's Still Open (the actual gap)

### 1. GHCNh path — false precision on temp_f (HIGH)

**File:** `packages/weather/src/mostlyright/weather/_ghcnh.py:224-236`

The GHCNh path still uses raw `celsius_to_fahrenheit(temp_c)` without integer-°F recovery. The comment explicitly says this was deferred from Phase 18 because "whether NCEI publishes integer-°F native data converted server-side is NOT documented."

**Research needed:** NCEI's GHCNh documentation (https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily) — do they store temperature in °C or °F? The raw data fields are `HLY-TEMP-NORMAL` or similar. Check whether °F→°C conversion happens at NCEI's ingest pipeline (which would mean integer-°F recovery is valid) or whether NCEI stores native °C (which would mean the current path is correct).

**If NCEI stores integer °F converted to °C:** Apply the same `float(round(temp_c * 9 / 5 + 32))` pattern as AWC.
**If NCEI stores native °C:** Update the comment to document WHY this path is intentionally different, and close the deferral as "not applicable."

### 2. Acceptance criteria not yet met

From the issue, these are still open:
- [ ] "For every Tgroup-sourced observation, the SDK exposes an integer-valued °F field" — AWC ✓, IEM ✓, GHCNh ❓
- [ ] "AWC and IEM paths produce identical temp_c and temp_f values for the same raw METAR" — NOT done, and Vu explicitly chose NOT to do this (IEM keeps raw tmpf, doesn't re-parse Tgroup). This acceptance criterion may need updating.
- [ ] "No spec or test claims sub-°F precision for U.S. ASOS sources" — mostly done, but GHCNh path comment is ambiguous
- [ ] "Empirical test (the 4,594-reading round-trip check) is committed" — AWC has this; GHCNh does not

### 3. Documentation fixes (LOW)

- `international.py:297` comment still says "0.1°C for US" — technically correct per the Phase 18 rationale (0.1°C rounding for stability, no-op on lattice values), but could be clearer

## What We Bring (domain expertise)

We run a weather derivatives trading system (Kalshi NHIGH/NLOW markets) that hit this exact bug. Our settlement reconciliation found that `cli_high_f` (NWS CLI) sometimes disagreed with our forecast by 0.5°F at .5-threshold boundaries because the SDK was reporting 80.06°F instead of 80°F. This caused real P&L impact — we filed it internally as a settlement anchor issue.

We have empirical data from 21 cities, 30+ days of settlements, and 54 paper trades against Kalshi. If our fix makes the SDK more accurate for Kalshi settlement verification, that's our proof it works.

## Approach

1. **Research first** — determine whether NCEI/GHCNh stores integer-°F native or native °C. Check NCEI docs, check the raw GHCNh data for a known US ASOS station (e.g. KLGA) to see if the °C values land on the integer-°F lattice.

2. **Write failing tests first (RED):**
   - GHCNh-specific: fetch or construct test data for a US ASOS station, verify temp_f is integer-valued
   - Cross-source consistency: if same station has AWC + GHCNh data for same timestamp, verify temp_c and temp_f agree

3. **Implement fix (GREEN):**
   - If GHCNh is integer-°F derived: apply `float(round(temp_c * 9 / 5 + 32))` pattern
   - If not: document why and update acceptance criteria

4. **Refactor if needed (REFACTOR)**

5. **Run full test suite:** `uv run pytest -m "not live" -q`
6. **Run lint:** `uv run ruff check --fix . && uv run ruff format .`
7. **Commit, push to origin, open PR against upstream main**

## PR Description Template

```
## Fix GHCNh temp_f false precision for US ASOS stations (#16)

### What
GHCNh-sourced observations for US ASOS stations emitted `temp_f` with false precision (e.g. 80.06°F instead of 80°F) because the path used `celsius_to_fahrenheit()` without integer-°F recovery. This was the remaining gap after Phase 18 fixed AWC and IEM paths.

### Why
NCEI GHCNh stores [FINDING: integer-°F native / native °C]. [EXPLANATION].
This affected downstream consumers who compare `temp_f` against Kalshi NHIGH/NLOW settlement thresholds — a 0.06°F discrepancy at a .5-boundary market changes the settlement outcome.

### How
- [WHAT YOU DID]

### Tests
- [WHAT TESTS YOU WROTE]

### Parity impact
None — this change adds precision recovery (round to integer °F) for GHCNh-sourced US stations only. Existing parity fixtures remain byte-equivalent because they predate Phase 18 and the fix is additive.

### TS Parity
Same fix applies to `packages-ts/weather/src/awc.ts` (equivalent GHCNh path). [IMPLEMENT OR DEFER NOTE].
```

## DON'T

- Don't touch AWC or IEM paths — they're already fixed and tested
- Don't change `temp_c` values — the °C field should stay as-is (Tgroup-derived tenths °C is the source truth for that field)
- Don't modify parity fixtures without understanding the impact
- Don't change observation.json schema — it's already correct
- Don't bypass pre-commit hooks
- Don't commit directly to main
