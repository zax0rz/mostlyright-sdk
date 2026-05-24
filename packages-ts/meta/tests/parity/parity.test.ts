// HARD parity gate — TS-W2 SC#1.
//
// For each of the 5 parity cases:
//   1. Load handlers.json (Plan 07 msw recordings).
//   2. Install msw setupServer with onUnhandledRequest: "error".
//   3. Call research(station, fromDate, toDate).
//   4. Assert row-equivalent to tests/fixtures/parity/ts/case_N_*.json
//      (Plan 03 JSON export of the Python parquet ground truth).
//
// Skips gracefully when recordings are absent (Plan 07 Task 2 is
// operator-gated). Once recordings land, this test becomes the HARD gate:
// any one case failing → vitest exits non-zero → CI fails.

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import { setupServer } from "msw/node";
import { afterAll, beforeAll, describe, it } from "vitest";

import { research } from "../../src/research.js";
import { assertRowsRowEqual } from "./_assertions.js";
import { type RecordedRequest, loadHandlers } from "./_load_handlers.js";

interface Case {
  n: number;
  station: string;
  from: string;
  to: string;
}

const CASES: ReadonlyArray<Case> = [
  { n: 1, station: "KNYC", from: "2025-01-06", to: "2025-01-12" },
  { n: 2, station: "KMDW", from: "2025-04-01", to: "2025-04-30" },
  { n: 3, station: "KLAX", from: "2025-03-01", to: "2025-03-31" },
  { n: 4, station: "KMIA", from: "2024-12-01", to: "2025-11-30" },
  { n: 5, station: "KMSY", from: "2024-09-08", to: "2024-09-22" },
];

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.resolve(__dirname, "../../../../tests/fixtures/parity/ts");
const RECORDINGS_DIR = path.resolve(__dirname, "recordings");

function fixturePath(c: Case): string {
  return path.join(FIXTURES_DIR, `case_${c.n}_${c.station}_${c.from}_${c.to}.json`);
}

function recordingPath(c: Case): string {
  return path.join(RECORDINGS_DIR, `case_${c.n}`, "handlers.json");
}

function loadFixture(c: Case): Array<Record<string, unknown>> {
  return JSON.parse(fs.readFileSync(fixturePath(c), "utf-8"));
}

function loadRecordings(c: Case): RecordedRequest[] {
  return JSON.parse(fs.readFileSync(recordingPath(c), "utf-8"));
}

describe("TS-W2 HARD parity gate (SC#1)", () => {
  for (const c of CASES) {
    const haveRecordings = fs.existsSync(recordingPath(c));
    const haveFixture = fs.existsSync(fixturePath(c));

    describe(`case ${c.n}: ${c.station} ${c.from} → ${c.to}`, () => {
      if (!haveRecordings || !haveFixture) {
        // Plan 07's recordings are operator-gated; until the operator runs
        // `TRADEWINDS_TS_LIVE=1 pnpm --filter tradewinds capture-parity`
        // this case skips. Use `it.todo` so the missing-recording case is
        // visible in test output (NOT silently green).
        it.todo(
          `recordings missing (${recordingPath(c)}) — operator must run capture-parity (Plan 07)`,
        );
        return;
      }

      const handlers = loadHandlers(loadRecordings(c));
      const server = setupServer(...handlers);
      beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
      afterAll(() => server.close());

      it("research() produces row-equivalent output to the JSON fixture", async () => {
        const expected = loadFixture(c);
        const actual = await research(c.station, c.from, c.to, {
          iemPolitenessMs: 0,
          ghcnhPolitenessMs: 0,
          cliPolitenessMs: 0,
          // No `now` override — let the AWC short-circuit fire identically to
          // capture-time AND Python fixture-generation time. All 5 cases are
          // historical (oldest in late 2024); AWC will skip in both places.
          // Forcing `now` here would make TS fetch AWC, hit msw's
          // onUnhandledRequest="error", and fail with no AWC recordings.
        });
        assertRowsRowEqual(actual, expected, `case_${c.n}`);
      }, 30_000);
    });
  }
});
