# Technical Review: mostlyright-sdk Issue #63

**Repo:** mostlyrightmd/mostlyright-sdk
**Issue:** [#63 — feat(weather): expose cloud_cover_pct / visibility_m / ceiling_m in forecast_nwp](https://github.com/mostlyrightmd/mostlyright-sdk/issues/63)
**Reviewer:** Blenda (subagent for zach/zax0rz)
**Date:** 2026-06-05
**Reviewed against:** fork at `zax0rz/mostlyright-sdk` (commit `9148d10` — v1.4.0)

---

## a) Issue Accuracy Assessment

**Verdict: The empirical analysis in issue #63 is accurate and thorough. No wrong conclusions found.**

### Specific claims verified against source code:

1. **`pressure_pa_surface` and `pressure_pa_mslp` already ship.** ✅ Confirmed.
   - HRRR map (`hrrr.py`): `PRES:surface` → `pressure_pa_surface`, `MSLMA:mean sea level` → `pressure_pa_mslp` (lines 30-31).
   - GFS map (`gfs.py`): `PRES:surface` → `pressure_pa_surface`, `PRMSL:mean sea level` → `pressure_pa_mslp` (lines 24-25).
   - Schema (`forecast_nwp.py`): Both columns declared as `float64`, nullable=True (schema lines 166-167).

2. **`visibility_m` and `ceiling_m` are cleanly single-record on both HRRR and GFS.** ✅ Plausible. The issue's .idx analysis shows unique `(variable, level)` pairs: `(VIS, surface)` and `(HGT, cloud ceiling)` each match exactly one record on both models. The code path through `filter_records()` (`_nwp_idx.py` line 212) would keep exactly one per key since `record_groups` would have `len(group) == 1`. Adding these to the maps is safe mechanical work.

3. **`cloud_cover_pct` is blocked by GFS ambiguity.** ✅ Confirmed by code logic.
   - The issue claims `(TCDC, entire atmosphere)` returns two GFS .idx records (record #636 "1 hour fcst" and #637 "0-1 hour ave fcst").
   - In `_extract_records()` (`forecast_nwp.py`), the post-Phase-24 refactored ambiguity check (line ~405-420 in the current version) groups records by `(variable, level)` and **raises `GribIntegrityError` if `len(group) > 1`**:
     ```python
     if len(group) > 1:
         raise GribIntegrityError(
             f"ambiguous .idx records for {key}: "
             f"{[r.forecast_period for r in group]} — ...",
             model=model,
             variable=key[0],
         )
     ```
   - `filter_records()` (`_nwp_idx.py` line 212) deduplicates by `record_no` but **does NOT** filter on `forecast_period` — it only checks `(variable, level)`. So both TCDC records would pass filtering and both would appear in `record_groups[("TCDC", "entire atmosphere")]`, triggering the guard.
   - **HRRR is unaffected** because HRRR publishes only one TCDC record per level.

4. **`.idx` record counts match.** Not independently re-fetched (would require live HTTP), but the methodology is sound — the issue used the SDK's own `parse_idx` + `compute_byte_end` + `filter_records` against real AWS BDP data, which is the correct approach.

### Minor gaps in the issue:

- **cfgrib short-name verification is acknowledged as unverified.** The issue explicitly notes the `[nwp]` extra wasn't installed. The proposed cfgrib mappings (`vis`, `tcc`, and something for `HGT:cloud ceiling`) need one real decode run to confirm. This is a real gap — if cfgrib decodes `HGT` at "cloud ceiling" to a short-name other than what's expected (e.g. `gh` instead of a hypothetical `ceil`), the `_GRIB_VAR_TO_CFGRIB_NAME` lookup would miss and fall through to the single-data-var heuristic (which works but is fragile).
- **NBM availability is explicitly unverified** — acceptable scope cut for the issue but must be addressed before extending `nbm.py`.

---

## b) The Latent GFS Precip Bug

### Does `forecast_nwp(station, "gfs")` crash at the default fxx=1?

**Yes, it does.** Here's the exact code path:

1. **Default `fxx`**: `forecast_nwp()` at line 581-582:
   ```python
   if fxx is None:
       fxx = 0 if model in {"rtma", "urma"} else 1
   ```
   For `"gfs"`, `fxx` defaults to `1`.

2. **`.idx` fetch and parse**: `_try_fetch_records_for_mirror()` calls `filter_records()` with the GFS variable map which includes `"precip_mm_1h": ("APCP", "surface")`.

3. **Record grouping**: In `_extract_records()`, `record_groups` for key `("APCP", "surface")` would contain **two records** (both `0-1 hour acc fcst` — a well-known GFS quirk where APCP is emitted twice at the same level with identical forecast periods but different `record_no` values, e.g. #596 and #597).

4. **Ambiguity guard fires**: The check at line ~405-420:
   ```python
   if len(group) > 1:
       raise GribIntegrityError(...)
   ```
   This raises `GribIntegrityError` and aborts the entire mirror attempt. Since both mirrors (AWS BDP and NOMADS) carry the same GFS GRIB2 inventory, the second mirror would also fail identically.

5. **Final exception**: `NoLiveForNwpError` would NOT be raised (mirrors didn't fail HTTP-wise — the GRIB was structurally valid). Instead, `GribIntegrityError` propagates directly to the caller.

### Why is this invisible today?

- **Live tests are skipped in CI**: The `test_forecast_nwp_live_hrrr_knyc_one_hour` test is gated by `@pytest.mark.live` and only tests HRRR, not GFS. No live GFS test exists.
- **Unit tests don't exercise this path**: The existing "ambiguous .idx" test scenario (`test_cfgrib_variable_name` tests) exercises `_cfgrib_variable_name` — the cfgrib short-name table lookup — not the duplicate-record grouping path in `_extract_records`. The `TestCodexP2Followups` class tests transport failures and mirror fallback but never constructs a two-record group for the same `(variable, level)`.

### Is this already known?

No evidence in the git history (`grep` for "GribIntegrity", "ambiguous", "disambig", "precip", "APCP" in commit messages returned no relevant hits). Web search for "mostlyright-sdk GFS GribIntegrityError APCP" returned no results. **This is a genuinely latent bug first surfaced by issue #63.**

### Why does fxx=0 mask it?

At fxx=0 (analysis hour), GFS typically omits APCP entirely (there's no accumulation window at hour 0). So `filter_records()` finds zero records for `("APCP", "surface")`, the group is empty, and the ambiguity check is never reached. The precip column gets `float("nan")` silently. Only fxx≥1 triggers the duplicate.

---

## c) Disambiguation Strategy

### The problem in detail

The current `VARIABLE_MAP` is `dict[str, tuple[str, str]]` — `{column_name: (variable, level)}`. The `.idx` records for a given `(variable, level)` can be non-unique on GFS when:
- The same variable appears with different statistical processing types (instantaneous vs. time-averaged vs. time-accumulated)
- The same variable appears with identical statistical processing but different GRIB2 internal ordering (the APCP twin case)

### Proposed approach: Option A (modified) — prefer instantaneous, then lowest `record_no`

This is the issue's recommended Option A with one refinement:

**Rule:** Given multiple records sharing `(variable, level)`:
1. If any record's `forecast_period` matches a window pattern (`acc`, `ave`, `max`, `min`), **prefer records that do NOT match a window pattern** (instantaneous/"N hour fcst").
2. Among records that survive step 1 (or if all match / none match a window pattern), pick the one with the lowest `record_no`.

**Implementation location:** Inside `_extract_records()`, replacing the current `raise GribIntegrityError` block (~lines 405-420). The `forecast_period` string is already available on every `IdxRecord`.

```python
import re

_WINDOW_RE = re.compile(r"\b(ave|acc|max|min)\b")

def _pick_record(group: list[IdxRecord]) -> IdxRecord:
    """Disambiguate multiple .idx records for the same (variable, level).

    Prefer instantaneous over window-aggregated; break ties by lowest record_no.
    """
    # Partition into non-window vs window
    non_window = [r for r in group if not _WINDOW_RE.search(r.forecast_period)]
    if non_window:
        return min(non_window, key=lambda r: r.record_no)
    # All are windows (e.g. APCP twins) — pick first by record_no
    return min(group, key=lambda r: r.record_no)
```

**In `_extract_records`, replace:**
```python
if len(group) > 1:
    raise GribIntegrityError(...)
```
**with:**
```python
if len(group) > 1:
    rec = _pick_record(group)
    log.warning(
        "ambiguous .idx records for %s: %s — picked record_no=%d (%s)",
        key,
        [r.forecast_period for r in group],
        rec.record_no,
        rec.forecast_period,
    )
```

### Why not Option B (extend map to 3-tuple)?

Option B would change `VARIABLE_MAP` from `dict[str, tuple[str, str]]` to `dict[str, tuple[str, str, str]]` (adding a `forecast_period` matcher). This:
- Touches every model's variable map file (11+ files after Phase 17 expansion)
- Still needs a tiebreak rule for GFS APCP's identical twins (both "0-1 hour acc fcst")
- Makes the map harder to maintain for future model additions

Option A keeps all map files unchanged and solves the problem in one place. The `forecast_period` heuristic is well-understood (NCEP .idx files use consistent naming conventions) and the log warning ensures the disambiguation is observable.

### Preserving the loud-fail guard

The current `GribIntegrityError` is valuable for detecting genuinely unexpected upstream layout changes. The fix should **preserve loud-fail for true ambiguity** — but the current definition ("any `len(group) > 1`") is too broad. With the `_pick_record` heuristic, the only remaining ambiguity would be if someone wanted a specific window type (e.g., "give me the 6-hour accumulated precip, not the 1-hour"). That's a future concern; for now, the heuristic handles all known cases correctly.

**Recommendation:** Change the `GribIntegrityError` to a `log.warning` with the pick logged. If the team prefers a stricter guard, raise the error only when all records in the group have identical `forecast_period` AND identical `record_no` (which would indicate a corrupt .idx — impossible in practice). The current `raise` is a false positive on legitimate NCEP output.

### What this fixes simultaneously

- **GFS `cloud_cover_pct`**: Picks #636 ("1 hour fcst") over #637 ("0-1 hour ave fcst"). Correct — instantaneous total cloud cover is the desired field.
- **GFS `precip_mm_1h`**: Both #596 and #597 are "0-1 hour acc fcst" (identical forecast_period, different record_no). The `_WINDOW_RE` doesn't help here since both match `acc`. Falls through to `min(record_no)` → picks #596. Both records carry the same data (GFS APCP quirk), so this is correct.
- **HRRR**: Unaffected — single records per key, no disambiguation needed.

### Minimal change that fixes both

The minimal diff is:
1. Add `_pick_record()` helper function (~10 lines)
2. Replace the `raise GribIntegrityError(...)` block in `_extract_records` with `_pick_record(group)` + `log.warning` (~5 lines changed)
3. Add `cloud_cover_pct`, `visibility_m`, `ceiling_m` to HRRR and GFS variable maps
4. Add entries to `_GRIB_VAR_TO_CFGRIB_NAME`
5. Add columns to schema, `nullable_numeric_cols`, `_empty_dataframe`
6. Add QC rules

Steps 1-2 fix the latent precip bug. Steps 3-6 add the new fields. They can be done in one PR.

---

## d) Risk Assessment

### What could break

1. **HRRR: Zero risk.** HRRR has single records for all three new fields. The disambiguation code path is never reached. Adding map entries is purely additive.

2. **GFS `precip_mm_1h`: Behavioral change.** Currently raises `GribIntegrityError` (which means the column is absent and the entire fetch fails). After the fix, it returns data. This is strictly an improvement (bug fix), but any caller that was **catching** `GribIntegrityError` and treating it as "GFS unavailable" will now get a DataFrame with precip values instead. This is unlikely (the error message explicitly says "ambiguous .idx records", not "model unavailable") but worth noting.

3. **GFS `cloud_cover_pct`: New column.** Additive + nullable. No existing caller expects this column, so no breakage. The only risk is if the cfgrib decode produces an unexpected short-name, which would hit the `_cfgrib_variable_name` fallback (single data-var heuristic) — this works but is untested.

4. **GFS `visibility_m` and `ceiling_m`: New columns, single record.** Lowest risk addition.

5. **Schema backward compatibility:** Adding nullable float64 columns to `NwpForecastSchema` is backward-compatible. Existing DataFrames validate against a column superset; new columns default to NaN. No `schema_id` bump needed (the schema contract allows nullable additions).

6. **`_empty_dataframe` and `nullable_numeric_cols`:** Must be updated to include the three new columns. If missed, the empty-result path would return a DataFrame missing these columns, causing a schema validation failure. **This is the most likely omission in a PR.**

7. **Parallelization (Phase 24):** The disambiguation check runs **before** the thread pool fan-out (lines ~405-420 in current code), so it's not affected by the parallel extraction. The `_pick_record` call would happen in the serial pre-flight section. No race condition risk.

### Test coverage gaps

1. **No unit test for the ambiguity path.** The existing tests never construct a `filtered_records` list where two records share the same `(variable, level)`. A test fixture with a synthetic `.idx` containing duplicate TCDC and APCP records is essential.

2. **No live GFS test.** The only live test (`test_forecast_nwp_live_hrrr_knyc_one_hour`) tests HRRR. A `@pytest.mark.live` GFS test would have caught the precip bug. Adding one (even as a smoke test that just confirms no exception) is strongly recommended.

3. **No test for `_pick_record` heuristic.** The regex-based window detection should have its own unit tests covering:
   - "1 hour fcst" (instantaneous — preferred)
   - "0-1 hour ave fcst" (window — deprioritized)
   - "0-1 hour acc fcst" (window — deprioritized)
   - Two identical "0-1 hour acc fcst" (tiebreak by record_no)
   - Edge cases: empty group (shouldn't happen but defensive), single record (passthrough)

4. **cfgrib decode of new records untested.** Without a live decode run, the cfgrib short-name for `HGT:cloud ceiling` is uncertain. The `_cfgrib_variable_name` fallback handles this, but an explicit table entry is preferred for robustness.

---

## e) Recommended Implementation Order

### Phase 1: Fix the latent precip bug (urgent, standalone PR)

**Rationale:** This is a pre-existing bug that makes `forecast_nwp(station, "gfs")` crash on the default call. It's broken for any user who hasn't explicitly set `fxx=0`. The fix is tiny (replace `raise` with `_pick_record` + warning) and unblocks GFS entirely.

1. Add `_pick_record()` to `forecast_nwp.py`
2. Replace the ambiguity `raise` in `_extract_records()`
3. Add unit test with synthetic 2-record GFS .idx fixture
4. Add `@pytest.mark.live` GFS smoke test
5. File as fix PR referencing issue #63

### Phase 2: Add the three new fields (feature PR, depends on Phase 1)

**Rationale:** Depends on Phase 1 because GFS `cloud_cover_pct` needs the disambiguation to work. Can't ship cloud_cover_pct for GFS without the fix.

1. Add three ColumnSpecs to `NwpForecastSchema` (cloud_cover_pct, visibility_m, ceiling_m — all float64, nullable)
2. Regenerate JSON schema + EXPORT_MANIFEST; update `test_schemas_codegen.py`
3. Add entries to HRRR and GFS VARIABLE_MAPs
4. Add entries to `_GRIB_VAR_TO_CFGRIB_NAME` (confirm cfgrib short-names via one decode run)
5. Add to `nullable_numeric_cols` tuple and `_empty_dataframe()`
6. Add QC rules to `RULES_NWP_NCEP` (cloud_cover_pct ∈ [0,100], visibility_m ≥ 0, ceiling_m ≥ 0)
7. Document ceiling_m "no ceiling" encoding (NaN expected, confirm with cfgrib)
8. Update docs + CHANGELOG
9. Add unit tests (single-record HRRR path, disambiguated GFS path)
10. Add `@pytest.mark.live` tests for both models

### Phase 3: Naming decision + NBM verification (follow-up)

- Resolve `ceiling_m` vs `cloud_ceiling_m` naming (issue notes IEM adapters use `cloud_ceiling_m`)
- Verify NBM `.idx` availability for all three fields before extending `nbm.py`
- File TS parity ticket per `CROSS-SDK-SYNC.md`

### Prerequisites

- **No new dependencies required.** The disambiguation uses only the `forecast_period` string already available on `IdxRecord`. No cfgrib/xarray/sklearn changes needed.
- **One cfgrib decode verification run** is needed to confirm short-names. This requires the `[nwp]` extra installed. Suggested: decode one GRIB2 message for each of `(TCDC, entire atmosphere)`, `(VIS, surface)`, and `(HGT, cloud ceiling)` from a real HRRR cycle and inspect `ds.data_vars`.

### Bundle vs. split?

The issue author suggests potentially splitting the GFS precip fix into its own bug. **I recommend bundling both in one PR** because:
- The fix is the same code change (the disambiguation logic)
- Phase 1 alone doesn't add the new map entries that exercise the disambiguation for `cloud_cover_pct`
- Keeping them together ensures the disambiguation is tested against real GFS cases, not just synthetic fixtures
- The risk profile is identical (both touch the same ambiguity code path)

If the team prefers strict separation, Phase 1 can ship first as a bugfix with the synthetic fixture, and Phase 2 adds the fields with a live GFS test that exercises the real ambiguity.

---

## Appendix: Key File Locations (commit 9148d10)

| File | Purpose |
|------|---------|
| `packages/weather/src/mostlyright/weather/forecast_nwp.py` | Main module: `_extract_records` (line ~405 ambiguity guard), `_GRIB_VAR_TO_CFGRIB_NAME` (line ~120), `nullable_numeric_cols` (line ~931), `_empty_dataframe` (line ~1035) |
| `packages/weather/src/mostlyright/weather/_fetchers/_nwp_idx.py` | `.idx` parser: `filter_records` (line 212), `IdxRecord` dataclass (line 52) |
| `packages/weather/src/mostlyright/weather/_fetchers/_nwp_grids/hrrr.py` | HRRR VARIABLE_MAP (line 22) |
| `packages/weather/src/mostlyright/weather/_fetchers/_nwp_grids/gfs.py` | GFS VARIABLE_MAP (line 16) |
| `packages/core/src/mostlyright/core/schemas/forecast_nwp.py` | Schema columns (line 101), COLUMNS list |
| `packages/weather/src/mostlyright/weather/qc/rules_nwp.py` | QC rules: `RULES_NWP_NCEP` (line ~285) |
| `packages/weather/tests/test_forecast_nwp.py` | Tests: no ambiguity-path coverage, no live GFS test |

## Appendix: Issue's Naming Suggestion

The issue proposes `ceiling_m` to match the user's request, but notes that IEM adapters use `cloud_ceiling_m`. **Recommend `cloud_ceiling_m`** for cross-source join consistency — quant users joining NWP forecasts with IEM observations on column name is a primary use case. This should be resolved in the naming decision phase before the feature PR lands.
