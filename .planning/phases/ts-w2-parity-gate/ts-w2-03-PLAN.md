---
phase: ts-w2-parity-gate
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/fixtures/parity/export_for_ts.py
  - tests/fixtures/parity/ts/case_1_KNYC_2025-01-06_2025-01-12.json
  - tests/fixtures/parity/ts/case_2_KMDW_2025-04-01_2025-04-30.json
  - tests/fixtures/parity/ts/case_3_KLAX_2025-03-01_2025-03-31.json
  - tests/fixtures/parity/ts/case_4_KMIA_2024-12-01_2025-11-30.json
  - tests/fixtures/parity/ts/case_5_KMSY_2024-09-08_2024-09-22.json
  - tests/fixtures/parity/ts/manifest.json
  - tests/fixtures/parity/ts/README.md
  - tests/test_parity_ts_export.py
  - packages-ts/meta/tests/parity/recordings/.gitkeep
  - packages-ts/meta/tests/parity/capture_recordings.md
autonomous: true
requirements:
  - TS-PARITY-01

must_haves:
  truths:
    - "Each of the 5 Python parquet fixtures has a corresponding JSON file under tests/fixtures/parity/ts/ with row-equivalent contents."
    - "JSON shape: array of objects, one per settlement date row, with EXACTLY 19 columns matching Python output (date, station, cli_high_f, cli_low_f, cli_report_type, obs_high_f, obs_low_f, obs_mean_f, obs_mean_dewpoint_f, obs_max_wind_kt, obs_max_gust_kt, obs_total_precip_in, obs_count, fcst_high_f, fcst_low_f, fcst_model, fcst_issued_at, fcst_pop_6hr_pct, fcst_qpf_6hr_in, market_close_utc)."
    - "Date column is ISO YYYY-MM-DD string (NOT datetime64[ns] — JSON-serializable)."
    - "Integer columns (cli_high_f when dtype=int64, obs_count, obs_max_wind_kt when int64) emit as JSON numbers WITHOUT trailing .0."
    - "Float columns (obs_high_f, obs_low_f, obs_mean_f, etc.) emit as JSON numbers with sufficient precision (IEEE float64 roundtrip-safe)."
    - "NaN/None cells emit as JSON `null`."
    - "All `fcst_*` columns are present with null values (Mode 1: forecast disabled)."
    - "manifest.json lists case metadata (station, from, to, row_count, sha256 of JSON file)."
    - "Export script is deterministic — running twice produces byte-identical JSON output (sorted keys, fixed precision, no wall-clock fields)."
    - "Recordings README documents the manual `msw` recording workflow Plan 08 will execute pre-flight (this plan does NOT capture HTTP recordings — that needs the TS fetchers, which are produced by Plans 01+02; recording happens in Plan 08)."
  artifacts:
    - path: "tests/fixtures/parity/export_for_ts.py"
      provides: "Python script — reads 5 parquet fixtures, emits 5 JSON files + manifest.json"
      contains: "def export_case_to_json"
    - path: "tests/fixtures/parity/ts/manifest.json"
      provides: "Per-case metadata (station, from, to, row_count, sha256, dtype hints)"
      contains: "case_1"
    - path: "tests/fixtures/parity/ts/case_1_KNYC_2025-01-06_2025-01-12.json"
      provides: "Row-equivalent JSON export of case 1 (7 rows × 19 cols)"
      contains: "KNYC"
    - path: "tests/test_parity_ts_export.py"
      provides: "Python pytest: re-runs export, asserts byte-identical output (determinism gate)"
      contains: "test_export_deterministic"
    - path: "packages-ts/meta/tests/parity/capture_recordings.md"
      provides: "Manual instructions for Plan 08 to capture msw HTTP recordings against the 5 fixture queries"
      contains: "## Recording workflow"
  key_links:
    - from: "tests/fixtures/parity/export_for_ts.py"
      to: "tests/fixtures/parity/case_*.parquet"
      via: "pd.read_parquet"
      pattern: "pd\\.read_parquet"
    - from: "tests/fixtures/parity/ts/manifest.json"
      to: "tests/fixtures/parity/ts/case_*.json"
      via: "sha256 reference per case"
      pattern: "sha256"
    - from: "tests/test_parity_ts_export.py"
      to: "tests/fixtures/parity/export_for_ts.py"
      via: "imports + re-runs"
      pattern: "from.*export_for_ts"
---

<objective>
Export the 5 Python parity parquet fixtures (`tests/fixtures/parity/case_*.parquet`) as JSON files consumable by the TS parity test (Plan 08). This is a Python-side artifact production task — no TS code is produced. Runs PARALLEL to Plans 01-02 because it touches only Python and fixture files.

**Why this matters:** The TS parity test cannot read parquet without `parquet-wasm` (deferred to v0.2 per TS-SDK-DESIGN §1). The fixtures must be projected into JSON Mode 1 once, deterministically, with type fidelity preserved (date as ISO string, ints as ints, floats as floats, NaN/None as JSON null). Plan 08 then loads these JSON files and asserts row-equivalence against the TS `research()` output.

**Why now and not Plan 08:** the Python parquet fixtures and the Python schema (`expected_dtypes.json`) are stable; nothing about the TS-W2 implementation changes them. Exporting now lets Plan 08 focus only on the TS-side assertion harness. Also unblocks downstream debugging: contributors can `cat case_5_KMSY_*.json` to see expected output without firing up parquet tooling.

**Two-part scope:**
1. Python exporter + JSON fixtures + determinism test.
2. Capture-recordings documentation (NOT the recordings themselves — those need the TS fetchers, captured in Plan 08).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/ts-w2-parity-gate/PLAN.md
@.planning/research/TS-SDK-DESIGN.md
@.planning/CROSS-SDK-SYNC.md
@tests/fixtures/parity/README.md
@tests/fixtures/parity/expected_dtypes.json
@tests/fixtures/parity/capture_fixtures.py
@packages/core/src/tradewinds/research.py

<interfaces>
Python parquet → JSON conversion semantics:

```python
# Source parquet columns + dtypes (from expected_dtypes.json):
# date: datetime64[ns]           → JSON: "YYYY-MM-DD" (string)
# station: object                → JSON: string
# cli_high_f: int64 or float64   → JSON: integer (int64) or float
# cli_low_f: int64 or float64    → JSON: integer or float
# cli_report_type: object        → JSON: string or null
# obs_high_f: float64            → JSON: float or null (NaN → null)
# obs_low_f: float64             → JSON: float or null
# obs_mean_f: float64            → JSON: float or null
# obs_mean_dewpoint_f: float64   → JSON: float or null
# obs_max_wind_kt: int64 or fl   → JSON: integer or float
# obs_max_gust_kt: int64 or fl   → JSON: integer or float
# obs_total_precip_in: float64   → JSON: float or null
# obs_count: int64               → JSON: integer
# fcst_high_f: object            → JSON: null (Mode 1: forecast disabled)
# fcst_low_f: object             → JSON: null
# fcst_model: object             → JSON: null
# fcst_issued_at: object         → JSON: null
# fcst_pop_6hr_pct: object       → JSON: null
# fcst_qpf_6hr_in: object        → JSON: null
# market_close_utc: object       → JSON: string ("YYYY-MM-DDTHH:MM:SSZ")
```

**Note on dtype variance across cases:** `expected_dtypes.json` shows that cases 1, 4, 5 have `cli_high_f: int64` while case 4 has `cli_high_f: float64` (caused by NaN cells when CLI data is missing for some dates). The exporter MUST preserve numeric type — int64 → JSON integer, float64 → JSON float — to keep downstream type-comparison assertions truthful.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Build the Python export script with determinism gate</name>
  <files>tests/fixtures/parity/export_for_ts.py, tests/test_parity_ts_export.py</files>
  <behavior>
    - `export_case_to_json(parquet_path, output_path)` reads a Phase 1 parquet fixture and writes a JSON array of row objects.
    - Deterministic: two consecutive runs produce byte-identical output (sorted keys per object, fixed `indent=2`, no wall-clock fields).
    - Type preservation: int64 columns emit JSON integers; float64 columns emit JSON floats; date column emits ISO YYYY-MM-DD strings; NaN cells emit JSON null; `fcst_*` object columns with all-None values emit JSON null.
    - `python tests/fixtures/parity/export_for_ts.py` (CLI mode) runs all 5 cases and writes manifest.json with `{"case_N": {"station", "from", "to", "row_count", "sha256", "dtypes"}}`.
    - `pytest tests/test_parity_ts_export.py::test_export_deterministic` runs the export twice and asserts identical output bytes.
  </behavior>
  <action>
    Create `tests/fixtures/parity/export_for_ts.py`:

    1. Imports: `json`, `hashlib`, `math`, `sys`, `pathlib.Path`, `pandas as pd`.

    2. Define `CASES = [(1, "KNYC", "2025-01-06", "2025-01-12"), (2, "KMDW", "2025-04-01", "2025-04-30"), (3, "KLAX", "2025-03-01", "2025-03-31"), (4, "KMIA", "2024-12-01", "2025-11-30"), (5, "KMSY", "2024-09-08", "2024-09-22")]` (mirror README.md table — KMDW per the README's API-whitelist note).

    3. `def row_to_dict(row: pd.Series, dtypes: dict[str, str]) -> dict[str, Any]`:
       - For each column in row.index:
         - Date column: convert pd.Timestamp → `f"{ts.year:04d}-{ts.month:02d}-{ts.day:02d}"` (ISO without time).
         - NaN check: `pd.isna(val) → None`.
         - Int dtype (int64): `int(val)`.
         - Float dtype (float64): `float(val)` (preserves IEEE precision through JSON).
         - Object dtype: pass through (str or None).
       - Return dict with native Python types.

    4. `def export_case_to_json(case_num: int, station: str, frm: str, to: str, parity_dir: Path, output_dir: Path) -> dict[str, Any]`:
       - `parquet_path = parity_dir / f"case_{case_num}_{station}_{frm}_{to}.parquet"`.
       - `df = pd.read_parquet(parquet_path)`.
       - `df = df.reset_index()` (parquet stores date as index per `pairs_to_dataframe`).
       - `df = df.sort_values(by=["date", "station"]).reset_index(drop=True)` — matches the `_canon` helper in `tests/fixtures/parity/README.md` Day 3 contract.
       - `dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}`.
       - Build `rows = [row_to_dict(row, dtypes) for _, row in df.iterrows()]`.
       - `output_path = output_dir / f"case_{case_num}_{station}_{frm}_{to}.json"`.
       - Write with `json.dump(rows, f, indent=2, sort_keys=True, separators=(",", ": "))` — `sort_keys=True` is the determinism enforcement.
       - Trailing newline + `\n` writer mode `"w"` (text mode).
       - Compute `sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()`.
       - Return `{"station": station, "from": frm, "to": to, "row_count": len(rows), "sha256": sha256, "dtypes": dtypes}`.

    5. `def main() -> int`:
       - `parity_dir = Path(__file__).parent`.
       - `output_dir = parity_dir / "ts"`. `output_dir.mkdir(exist_ok=True)`.
       - `manifest = {}`.
       - For each case: `manifest[f"case_{n}"] = export_case_to_json(...)`.
       - `manifest_path = output_dir / "manifest.json"`.
       - Write `manifest` with same `indent=2, sort_keys=True`.
       - Print summary to stdout (case → row_count + sha256 prefix).
       - Return 0.

    6. `if __name__ == "__main__": sys.exit(main())`.

    Create `tests/test_parity_ts_export.py`:

    ```python
    """Determinism gate for the TS parity-fixture exporter.

    Re-runs export_for_ts.py twice; asserts byte-identical output.
    Critical: if this drifts, the TS parity gate (Plan 08) starts comparing
    against moving ground truth and downstream debugging gets impossible.
    """
    import json
    import subprocess
    import sys
    from pathlib import Path


    PARITY_DIR = Path(__file__).parent / "fixtures" / "parity"
    EXPORTER = PARITY_DIR / "export_for_ts.py"


    def test_exporter_exists():
        assert EXPORTER.exists()


    def test_export_deterministic(tmp_path: Path):
        """Two runs of the exporter MUST produce byte-identical output."""
        # Run twice into different tmp dirs, compare every file.
        for run_dir_name in ("run1", "run2"):
            run_dir = tmp_path / run_dir_name
            run_dir.mkdir()
            # Copy parquet fixtures into a parity dir under run_dir
            # so the script reads from a controlled location.
            local_parity = run_dir / "parity"
            local_parity.mkdir()
            for case_pq in PARITY_DIR.glob("case_*.parquet"):
                (local_parity / case_pq.name).write_bytes(case_pq.read_bytes())
            # Patch exporter run by invoking it with the patched dir as cwd
            # … OR refactor exporter to accept --parity-dir / --output-dir
            # CLI flags. Choose the refactor — cleaner, testable.
            subprocess.run(
                [sys.executable, str(EXPORTER), "--parity-dir", str(local_parity), "--output-dir", str(run_dir / "ts")],
                check=True,
            )
        run1_ts = tmp_path / "run1" / "ts"
        run2_ts = tmp_path / "run2" / "ts"
        for f in sorted(run1_ts.iterdir()):
            assert (run2_ts / f.name).read_bytes() == f.read_bytes(), (
                f"Non-deterministic output: {f.name} differs between runs"
            )


    def test_manifest_contains_all_5_cases():
        manifest_path = PARITY_DIR / "ts" / "manifest.json"
        assert manifest_path.exists(), (
            "Run `python tests/fixtures/parity/export_for_ts.py` to populate ts/"
        )
        manifest = json.loads(manifest_path.read_text())
        assert sorted(manifest.keys()) == [f"case_{n}" for n in range(1, 6)]


    def test_case_jsons_match_manifest_sha256():
        manifest = json.loads((PARITY_DIR / "ts" / "manifest.json").read_text())
        for case_key, meta in manifest.items():
            json_name = f"{case_key}_{meta['station']}_{meta['from']}_{meta['to']}.json"
            json_path = PARITY_DIR / "ts" / json_name
            assert json_path.exists(), f"Missing JSON for {case_key}: {json_path}"
            import hashlib
            actual_sha = hashlib.sha256(json_path.read_bytes()).hexdigest()
            assert actual_sha == meta["sha256"], (
                f"SHA mismatch for {case_key}: manifest={meta['sha256']} actual={actual_sha}"
            )
    ```

    Add `--parity-dir` and `--output-dir` CLI args to the exporter via `argparse` (defaults match the production paths).

    Run the exporter ONCE manually to materialize the 5 JSON files and manifest.json:
    ```bash
    uv run python tests/fixtures/parity/export_for_ts.py
    ```

    Verify the test passes:
    ```bash
    uv run pytest tests/test_parity_ts_export.py -v
    ```
  </action>
  <verify>
    <automated>uv run pytest tests/test_parity_ts_export.py -v</automated>
  </verify>
  <done>
    All 4 tests in `test_parity_ts_export.py` pass; 5 JSON files materialized under `tests/fixtures/parity/ts/`; manifest.json present with valid sha256 per case; determinism gate confirms two runs produce identical bytes.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create README + recording-capture instructions for Plan 08</name>
  <files>tests/fixtures/parity/ts/README.md, packages-ts/meta/tests/parity/recordings/.gitkeep, packages-ts/meta/tests/parity/capture_recordings.md</files>
  <behavior>
    - `tests/fixtures/parity/ts/README.md` documents: source of truth (Python parquet fixtures), JSON projection rules, how to regenerate, when to regenerate (NEVER except if Python parquet fixtures change — same discipline as the parent `parity/README.md`).
    - `packages-ts/meta/tests/parity/recordings/.gitkeep` is an empty file that keeps the directory in git for Plan 08 to populate.
    - `packages-ts/meta/tests/parity/capture_recordings.md` documents the msw recording workflow Plan 08 will execute pre-test-write. Key fact: HTTP recordings are captured against IEM/AWC/GHCNh upstream APIs at fixture-equivalent date ranges; they're committed to the repo so the parity test runs deterministically without network.
  </behavior>
  <action>
    Create `tests/fixtures/parity/ts/README.md` with sections:

    ```markdown
    # TS parity fixtures — JSON projection

    **Source:** `tests/fixtures/parity/case_*.parquet` (the canonical v0.14.1 ground truth).
    **Produced by:** `tests/fixtures/parity/export_for_ts.py`.
    **Consumed by:** `packages-ts/meta/tests/parity/*.test.ts` (Plan 08).

    ## What is in this directory

    | File | Purpose |
    |------|---------|
    | `case_N_<STATION>_<FROM>_<TO>.json` | Row-equivalent JSON projection of the matching parquet fixture |
    | `manifest.json` | Per-case metadata (station, dates, row_count, sha256, dtypes) |

    ## DO NOT EDIT THESE FILES BY HAND

    Same discipline as the parent `parity/README.md`. The JSON files are derived
    artifacts from the parquet fixtures — regenerate via the exporter only.

    ## Regenerate

    Re-run only if the parquet fixtures change (which itself only happens on a
    fresh v0.14.1 re-capture — see parent README §Re-capture):

    ```bash
    uv run python tests/fixtures/parity/export_for_ts.py
    ```

    The determinism gate (`tests/test_parity_ts_export.py::test_export_deterministic`)
    asserts two consecutive runs produce byte-identical output.

    ## JSON shape

    Each `case_N_*.json` is an array of objects. Each object is one settlement-date
    row with 19 fields:

    - `date`: ISO YYYY-MM-DD string
    - `station`: string (3-letter NWS code)
    - `cli_high_f`, `cli_low_f`: integer (or float if NaN-coerced in case 4)
    - `cli_report_type`: string or null
    - `obs_high_f`, `obs_low_f`, `obs_mean_f`, `obs_mean_dewpoint_f`, `obs_total_precip_in`: float or null (NaN → null)
    - `obs_max_wind_kt`, `obs_max_gust_kt`, `obs_count`: integer (or float if NaN-coerced)
    - `fcst_*` (6 columns): all null (Mode 1: forecast disabled)
    - `market_close_utc`: string `"YYYY-MM-DDTHH:MM:SSZ"`

    ## Type-fidelity rules

    The exporter MUST preserve numeric type:
    - int64 columns → JSON integers (no trailing `.0`)
    - float64 columns → JSON floats (full IEEE precision)
    - NaN cells → JSON null
    - Date column → ISO YYYY-MM-DD string (parquet stores `datetime64[ns]`)

    Plan 08's parity test uses `JSON.parse` + per-column numeric-equality
    assertions; integer-vs-float drift is a parity break, not noise.

    ## Why JSON instead of replaying parquet

    `parquet-wasm` is deferred to v0.2 per TS-SDK-DESIGN.md §1 (NON-GOALS).
    JSON is the only cross-language settlement-grade format the TS SDK can
    consume without a binary dep in v0.1.0.
    ```

    Create `packages-ts/meta/tests/parity/recordings/.gitkeep` (empty file). Add a one-line comment via a co-located README pointing to capture_recordings.md.

    Create `packages-ts/meta/tests/parity/capture_recordings.md` with sections:

    ```markdown
    # MSW recording workflow (Plan 08 pre-flight)

    The TS parity test (`packages-ts/meta/tests/parity/parity.test.ts`, written
    in Plan 08) loads these recordings as `msw` handlers to replay the IEM ASOS,
    IEM CLI, GHCNh, and AWC HTTP traffic that the 5 parity-case `research()` calls
    issue. The recordings make the parity test deterministic and offline-safe.

    ## Why recordings (not live HTTP)

    1. Parity is settlement-grade. We need byte-stable inputs OR we cannot
       distinguish a TS-side bug from an upstream API drift. Recordings freeze
       the inputs.
    2. CI is offline.
    3. AWC has NO CORS — a live test in a browser-targeted suite would fail.

    ## When to (re-)record

    - **First-time recording for TS-W2:** Plan 08 captures all 4 sources per case.
    - **After Python parity fixtures change:** the parquet fixtures and recordings
      are joined ground truth; re-record both together.
    - **Otherwise: NEVER.** The recordings are immutable settlement-grade ground
      truth, same discipline as the parquet fixtures.

    ## Recording procedure (Plan 08 owns the actual capture)

    1. Set `TRADEWINDS_TS_LIVE=1` in env (gates a live-capture vitest suite).
    2. Run the capture script that wraps `research()` for each case and writes
       msw-format JSON handlers to `recordings/case_N_*/handlers.json`.
    3. Each handler entry: `{ method, url (with query params), response_status, response_body, content_type }`.
    4. Commit the recordings dir to git.

    ## Recording shape per case

    Per case, expect ~30-365 outbound requests:
    - IEM ASOS: 1-2 yearly chunks × 2 report_types = 2-4 requests.
    - IEM CLI: 1-2 station-years × 1 request = 1-2 requests.
    - GHCNh: 1-2 station-years × 1 request = 1-2 requests.
    - AWC: 1 request (if any date in range overlaps last 168h — likely zero for cases 1-5 because they are historical).

    The recordings directory will balloon to ~10-50 MB total (PSV bodies are large).
    That's accepted — it's settlement-grade ground truth.

    ## Outstanding for Plan 08

    - [ ] Build `capture_recordings.ts` script.
    - [ ] Capture 5 case recordings.
    - [ ] Wire them into `parity.test.ts` via msw's `setupServer(...handlers)`.
    - [ ] Add `recordings/README.md` listing per-case sha256 of `handlers.json`.
    ```

    `packages-ts/meta/tests/parity/recordings/.gitkeep`: empty file. `mkdir -p` the parent path first.
  </action>
  <verify>
    <automated>test -f tests/fixtures/parity/ts/README.md && test -f packages-ts/meta/tests/parity/capture_recordings.md && test -f packages-ts/meta/tests/parity/recordings/.gitkeep</automated>
  </verify>
  <done>
    All 3 files exist; README contents accurately describe the JSON projection contract; capture_recordings.md is a complete blueprint Plan 08 can execute against.
  </done>
</task>

</tasks>

<verification>
- `tests/fixtures/parity/ts/` contains 6 files (5 case JSONs + manifest.json + README.md).
- `tests/test_parity_ts_export.py` passes (4 tests).
- `packages-ts/meta/tests/parity/` exists with `.gitkeep` and `capture_recordings.md`.
- Re-running the exporter produces byte-identical output (determinism gate).
- The 5 JSON files are valid JSON (parseable by `python -c "import json; json.load(open(f))"` for each).
- `tests/fixtures/parity/ts/case_1_KNYC_2025-01-06_2025-01-12.json` has exactly 7 row objects (matches parent README "OK (7 rows)").
- Case 4 JSON has 365 row objects, case 5 has 15, case 3 has 31, case 2 has 30 (matches parent README counts).
</verification>

<success_criteria>
Maps to TS-W2 stub Wave 7: "Export 5 Python parity fixtures as JSON + capture HTTP recordings via msw recordHandlers OR replay vcrpy cassettes."

- 5/5 JSON fixtures materialized (HALF of Wave 7).
- HTTP recording capture is handled by Plan 08 (the other half of Wave 7) — split this way because recordings need the TS fetchers to exist, and the fetchers ship in Plans 01-02. This plan blocks ONLY on fixture export, which only needs Python.
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-03-SUMMARY.md` documenting:
- 5 JSON file paths + row counts.
- Manifest.json contents (sha256 per case).
- Dtype variance across cases (cli_high_f int64 vs float64 in case 4).
- Pointer to Plan 08's recording capture obligation.
</output>
