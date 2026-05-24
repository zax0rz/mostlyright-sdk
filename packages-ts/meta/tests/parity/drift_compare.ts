/**
 * Compare packages-ts/meta/tests/parity/drift/ vs tests/fixtures/parity/ts/.
 *
 * On any mismatch: writes drift-report.md with a per-case mismatch table.
 * ALWAYS exits 0 — drift cron is SOFT-FAIL per TS-W2 stub SC#5.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FIXTURES_DIR = path.resolve(__dirname, "../../../../tests/fixtures/parity/ts");
const DRIFT_DIR = path.resolve(__dirname, "drift");
const REPORT_PATH = path.resolve(__dirname, "drift-report.md");

const CASES = [
  { n: 1, station: "KNYC", from: "2025-01-06", to: "2025-01-12" },
  { n: 2, station: "KMDW", from: "2025-04-01", to: "2025-04-30" },
  { n: 3, station: "KLAX", from: "2025-03-01", to: "2025-03-31" },
  { n: 4, station: "KMIA", from: "2024-12-01", to: "2025-11-30" },
  { n: 5, station: "KMSY", from: "2024-09-08", to: "2024-09-22" },
] as const;

interface Mismatch {
  case_n: number;
  rowIndex: number;
  column: string;
  expected: unknown;
  actual: unknown;
  date: string;
}

function diffCase(c: (typeof CASES)[number]): Mismatch[] {
  const filename = `case_${c.n}_${c.station}_${c.from}_${c.to}.json`;
  const expected = JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, filename), "utf-8")) as Array<
    Record<string, unknown>
  >;
  const driftPath = path.join(DRIFT_DIR, filename);
  if (!fs.existsSync(driftPath)) {
    return [
      {
        case_n: c.n,
        rowIndex: -1,
        column: "<missing-drift-file>",
        expected: filename,
        actual: null,
        date: "-",
      },
    ];
  }
  const actual = JSON.parse(fs.readFileSync(driftPath, "utf-8")) as Array<Record<string, unknown>>;
  const mismatches: Mismatch[] = [];
  if (actual.length !== expected.length) {
    mismatches.push({
      case_n: c.n,
      rowIndex: -1,
      column: "<row-count>",
      expected: expected.length,
      actual: actual.length,
      date: "-",
    });
    return mismatches;
  }
  for (let i = 0; i < expected.length; i++) {
    const e = expected[i] as Record<string, unknown>;
    const a = actual[i] as Record<string, unknown>;
    for (const k of Object.keys(e)) {
      if (JSON.stringify(a[k]) !== JSON.stringify(e[k])) {
        mismatches.push({
          case_n: c.n,
          rowIndex: i,
          column: k,
          expected: e[k],
          actual: a[k],
          date: String(e.date),
        });
      }
    }
  }
  return mismatches;
}

function main(): void {
  const allMismatches: Mismatch[] = [];
  for (const c of CASES) {
    try {
      allMismatches.push(...diffCase(c));
    } catch (err) {
      console.warn(`case_${c.n} diff failed:`, err);
    }
  }
  if (allMismatches.length === 0) {
    console.log("✓ no drift detected across 5 cases");
    if (fs.existsSync(REPORT_PATH)) fs.unlinkSync(REPORT_PATH);
    return;
  }
  const lines: string[] = ["# Drift detected — TS parity watchdog", ""];
  lines.push(`Runtime: ${new Date().toISOString()}`, "");
  lines.push("| Case | Row | Date | Column | Expected | Actual |");
  lines.push("|------|-----|------|--------|----------|--------|");
  for (const m of allMismatches.slice(0, 200)) {
    lines.push(
      `| ${m.case_n} | ${m.rowIndex} | ${m.date} | \`${m.column}\` | \`${JSON.stringify(
        m.expected,
      )}\` | \`${JSON.stringify(m.actual)}\` |`,
    );
  }
  if (allMismatches.length > 200) {
    lines.push("", `_Showing first 200 of ${allMismatches.length} total mismatches._`);
  }
  lines.push("", "## Triage", "");
  lines.push("Likely causes:");
  lines.push(
    "1. **Upstream API drift** (IEM/AWC/GHCNh/CLI changed response shape) — re-capture Plan 07 recordings + investigate.",
  );
  lines.push("2. **Plan 04 merge regression** — check mergeObservations / mergeClimate.");
  lines.push("3. **Plan 05 aggregation regression** — check _obsAggregates math.");
  lines.push(
    "4. **Plan 06 orchestrator regression** — check observation bucketing by settlementDateFor.",
  );
  lines.push("");
  lines.push("Cross-reference Python drift cron output (`.github/workflows/drift-rotate.yml`):");
  lines.push("- Python green + TS red → TS-side bug.");
  lines.push("- Both red → real upstream-shape drift.");
  lines.push(
    "- Python red + TS green → likely upstream change affecting only Python's fetcher path.",
  );
  fs.writeFileSync(REPORT_PATH, `${lines.join("\n")}\n`, "utf-8");
  console.log(`drift-report.md written with ${allMismatches.length} mismatches`);
  // SOFT-FAIL: still exit 0.
}

main();
