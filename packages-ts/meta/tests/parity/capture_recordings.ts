/**
 * Capture HTTP request/response tapes for the 5 parity cases.
 *
 * Runs against REAL public APIs (AWC, IEM ASOS, IEM CLI, GHCNh). Gated
 * behind TRADEWINDS_TS_LIVE=1. One-shot: writes to
 * packages-ts/meta/tests/parity/recordings/.
 *
 * Re-run only if Python parquet fixtures change (see
 * `tests/fixtures/parity/README.md` §Re-capture). Recordings are
 * settlement-grade ground truth — committed to git, replayed in CI by
 * the parity test (Plan 08).
 *
 * Usage:
 *   TRADEWINDS_TS_LIVE=1 pnpm --filter mostlyright capture-parity
 */
import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

if (process.env.TRADEWINDS_TS_LIVE !== "1") {
  console.error(
    "Refusing to run: TRADEWINDS_TS_LIVE=1 is required for live recording capture.\n" +
      "This script hits real public APIs (AWC, IEM, GHCNh, NCEI) and writes\n" +
      "recordings to packages-ts/meta/tests/parity/recordings/. Set the env\n" +
      "var only when you've verified you intend to re-record (see README.md).",
  );
  process.exit(1);
}

interface RecordedRequest {
  method: string;
  url: string;
  responseStatus: number;
  responseBody: string;
  contentType: string;
}

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
const RECORDINGS_DIR = path.resolve(__dirname, "recordings");

const recorded: RecordedRequest[] = [];
const originalFetch = globalThis.fetch;

function startRecording(): void {
  recorded.length = 0;
  globalThis.fetch = async (input, init) => {
    const url =
      typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const method = init?.method ?? (input instanceof Request ? input.method : "GET");
    const response = await originalFetch(input, init);
    const clone = response.clone();
    const body = await clone.text();
    recorded.push({
      method: method.toUpperCase(),
      url,
      responseStatus: response.status,
      responseBody: body,
      contentType: response.headers.get("content-type") ?? "",
    });
    return response;
  };
}

function stopRecording(): ReadonlyArray<RecordedRequest> {
  globalThis.fetch = originalFetch;
  return [...recorded];
}

async function captureCase(
  c: Case,
): Promise<{ requestCount: number; sha256: string; sizeBytes: number }> {
  const caseDir = path.join(RECORDINGS_DIR, `case_${c.n}`);
  fs.mkdirSync(caseDir, { recursive: true });

  startRecording();
  try {
    // Dynamic import so the fetch patch is active when research() initializes.
    const { research } = await import("../../src/research.js");
    console.log(`[case_${c.n}] capturing ${c.station} ${c.from} → ${c.to} …`);
    await research(c.station, c.from, c.to);
  } finally {
    stopRecording();
  }

  const handlers = recorded.map((r) => ({ ...r }));
  const handlersPath = path.join(caseDir, "handlers.json");
  const json = `${JSON.stringify(handlers, null, 2)}\n`;
  fs.writeFileSync(handlersPath, json, "utf-8");
  const sha = crypto.createHash("sha256").update(json, "utf-8").digest("hex");
  console.log(
    `[case_${c.n}] wrote ${handlers.length} handlers, ${json.length} bytes, sha256=${sha.slice(0, 12)}…`,
  );
  return {
    requestCount: handlers.length,
    sha256: sha,
    sizeBytes: json.length,
  };
}

async function main(): Promise<void> {
  fs.mkdirSync(RECORDINGS_DIR, { recursive: true });
  const manifest: Record<string, unknown> = {};
  for (const c of CASES) {
    const meta = await captureCase(c);
    manifest[`case_${c.n}`] = {
      station: c.station,
      from: c.from,
      to: c.to,
      request_count: meta.requestCount,
      sha256: meta.sha256,
      size_bytes: meta.sizeBytes,
    };
  }
  const manifestPath = path.join(RECORDINGS_DIR, "manifest.json");
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf-8");
  console.log("✓ all 5 cases captured. manifest written to", manifestPath);
}

main().catch((err) => {
  console.error("✗ capture failed:", err);
  process.exit(1);
});
