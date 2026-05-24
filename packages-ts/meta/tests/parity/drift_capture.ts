/**
 * Capture current research() output for drift detection.
 *
 * Writes JSON rows to packages-ts/meta/tests/parity/drift/case_N_*.json.
 * Compared against tests/fixtures/parity/ts/ by drift_compare.ts.
 *
 * Hits LIVE public APIs — gated behind TRADEWINDS_TS_LIVE=1. Run weekly
 * by .github/workflows/drift-rotate-ts.yml.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import { research } from "../../src/research.js";

if (process.env.TRADEWINDS_TS_LIVE !== "1") {
  console.error("Refusing to run: TRADEWINDS_TS_LIVE=1 is required (hits live APIs).");
  process.exit(1);
}

const CASES = [
  { n: 1, station: "KNYC", from: "2025-01-06", to: "2025-01-12" },
  { n: 2, station: "KMDW", from: "2025-04-01", to: "2025-04-30" },
  { n: 3, station: "KLAX", from: "2025-03-01", to: "2025-03-31" },
  { n: 4, station: "KMIA", from: "2024-12-01", to: "2025-11-30" },
  { n: 5, station: "KMSY", from: "2024-09-08", to: "2024-09-22" },
] as const;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DRIFT_DIR = path.resolve(__dirname, "drift");

async function main(): Promise<void> {
  fs.mkdirSync(DRIFT_DIR, { recursive: true });
  for (const c of CASES) {
    console.log(`[drift] capturing case_${c.n} ${c.station} ${c.from} → ${c.to}`);
    const rows = await research(c.station, c.from, c.to);
    const outPath = path.join(DRIFT_DIR, `case_${c.n}_${c.station}_${c.from}_${c.to}.json`);
    const sorted = [...rows].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    fs.writeFileSync(outPath, `${JSON.stringify(sorted, null, 2)}\n`, "utf-8");
  }
  console.log("✓ drift capture complete");
}

main().catch((err) => {
  console.error("drift capture failed:", err);
  process.exit(2);
});
