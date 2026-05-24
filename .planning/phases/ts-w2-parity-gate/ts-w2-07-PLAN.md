---
phase: ts-w2-parity-gate
plan: 07
type: execute
wave: 5
depends_on:
  - ts-w2-06
files_modified:
  - packages-ts/meta/tests/parity/capture_recordings.ts
  - packages-ts/meta/tests/parity/recordings/case_1/handlers.json
  - packages-ts/meta/tests/parity/recordings/case_2/handlers.json
  - packages-ts/meta/tests/parity/recordings/case_3/handlers.json
  - packages-ts/meta/tests/parity/recordings/case_4/handlers.json
  - packages-ts/meta/tests/parity/recordings/case_5/handlers.json
  - packages-ts/meta/tests/parity/recordings/README.md
  - packages-ts/meta/tests/parity/recordings/manifest.json
  - packages-ts/meta/package.json
autonomous: true
requirements:
  - TS-PARITY-01

must_haves:
  truths:
    - "capture_recordings.ts is a node-only script (NOT a vitest test) that runs research() against the 5 parity cases with REAL HTTP enabled (no msw) and dumps every observed request/response to handlers.json."
    - "Each case directory under recordings/case_N/ contains handlers.json with the full request/response tape."
    - "handlers.json format: array of {method, url, requestHeaders?, responseStatus, responseBody, contentType} — sufficient for msw 2.x to replay via http.get/http.post handlers."
    - "manifest.json at recordings/ root lists per-case sha256 + request_count + total_size_bytes."
    - "Capture is one-shot: writes are gated behind TRADEWINDS_TS_LIVE=1 env var. Without the env var the script refuses to run (prevents accidental re-recording in CI)."
    - "Recording responses preserve body bytes verbatim (no UTF-8 munging on the PSV binary-ish chunks; use base64 for non-text content if necessary — but PSV/CSV are text)."
    - "Each handler entry's URL includes all query parameters in the captured order (msw matches on exact URL by default)."
    - "Recordings are committed to git — they're settlement-grade ground truth, same discipline as parquet fixtures."
  artifacts:
    - path: "packages-ts/meta/tests/parity/capture_recordings.ts"
      provides: "TS script that runs research() with HTTP tracing on; writes recordings"
      contains: "TRADEWINDS_TS_LIVE"
    - path: "packages-ts/meta/tests/parity/recordings/manifest.json"
      provides: "Per-case sha256 + counts"
      contains: "case_1"
    - path: "packages-ts/meta/tests/parity/recordings/README.md"
      provides: "Replay-side instructions for Plan 08"
      contains: "## Replay"
  key_links:
    - from: "capture_recordings.ts"
      to: "research() from @tradewinds/meta"
      via: "import + invoke with all 5 case windows"
      pattern: "import.*research"
    - from: "capture_recordings.ts"
      to: "global fetch (intercepted)"
      via: "monkey-patch globalThis.fetch with a recording wrapper BEFORE importing fetchers"
      pattern: "globalThis\\.fetch"
---

<objective>
Capture HTTP request/response tapes for the 5 parity cases by running the TS `research()` against the real public APIs (AWC, IEM ASOS, IEM CLI, GHCNh) ONCE, with a fetch-interceptor wrapping every request. Persist the tapes as msw-replayable JSON under `packages-ts/meta/tests/parity/recordings/case_N/handlers.json`.

**Why this matters:** Plan 08's parity test needs deterministic offline inputs. Without recordings the parity test would either (a) hit live APIs in CI (unacceptable: noisy, slow, AWC has no CORS in browser-targeted tests but works in node — still bad practice), or (b) skip entirely. Recordings make the test pure-deterministic and offline-safe.

**One-shot operation:** captures are gated behind `TRADEWINDS_TS_LIVE=1`. Operator (vuhcze@gmail.com) runs the capture once locally; commits the recordings; CI replays.

**Output:** One TS script + 5 case directories of recordings + manifest + README.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/ts-w2-parity-gate/PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-06-PLAN.md
@.planning/phases/ts-w2-parity-gate/ts-w2-03-PLAN.md
@packages-ts/meta/tests/parity/capture_recordings.md
@tests/fixtures/parity/README.md
@packages-ts/meta/src/research.ts

<interfaces>
After Plan 06, `research()` calls `globalThis.fetch` directly (via `@tradewinds/core/internal/http::fetchWithRetry`). The fetch-interceptor pattern:

```typescript
// capture_recordings.ts (pseudo-code)
const recorded: Array<{method, url, responseStatus, responseBody, contentType}> = [];
const originalFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const response = await originalFetch(input, init);
  const clone = response.clone();
  const body = await clone.text();
  recorded.push({
    method: init?.method ?? "GET",
    url: typeof input === "string" ? input : input.toString(),
    responseStatus: response.status,
    responseBody: body,
    contentType: response.headers.get("content-type") ?? "",
  });
  return response;
};
```

Cases (mirror `tests/fixtures/parity/README.md`):
1. KNYC, 2025-01-06, 2025-01-12
2. KMDW, 2025-04-01, 2025-04-30
3. KLAX, 2025-03-01, 2025-03-31
4. KMIA, 2024-12-01, 2025-11-30
5. KMSY, 2024-09-08, 2024-09-22
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build capture_recordings.ts script</name>
  <files>packages-ts/meta/tests/parity/capture_recordings.ts, packages-ts/meta/package.json</files>
  <action>
    Create `packages-ts/meta/tests/parity/capture_recordings.ts`:

    ```typescript
    /**
     * Capture HTTP request/response tapes for the 5 parity cases.
     *
     * Runs against REAL public APIs. Gated behind TRADEWINDS_TS_LIVE=1.
     * One-shot: writes to packages-ts/meta/tests/parity/recordings/.
     *
     * Re-run only if Python parquet fixtures change (see
     * `tests/fixtures/parity/README.md` §Re-capture). Recordings are
     * settlement-grade ground truth — committed to git, replayed in CI.
     *
     * Usage:
     *   TRADEWINDS_TS_LIVE=1 pnpm --filter tradewinds tsx tests/parity/capture_recordings.ts
     */
    import * as fs from "node:fs";
    import * as path from "node:path";
    import * as crypto from "node:crypto";

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

    const RECORDINGS_DIR = path.resolve(__dirname, "recordings");

    // Patch fetch BEFORE importing research (so the import-time module
    // initialization doesn't capture the original fetch reference).
    const recorded: RecordedRequest[] = [];
    const originalFetch = globalThis.fetch;

    function startRecording(): void {
      recorded.length = 0;
      globalThis.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
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

    async function captureCase(c: Case): Promise<{ requestCount: number; sha256: string; sizeBytes: number }> {
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
      // Deterministic JSON: sort keys, 2-space indent, trailing newline.
      const json = JSON.stringify(handlers, null, 2) + "\n";
      fs.writeFileSync(handlersPath, json, "utf-8");
      const sha = crypto.createHash("sha256").update(json, "utf-8").digest("hex");
      console.log(
        `[case_${c.n}] wrote ${handlers.length} handlers, ${json.length} bytes, sha256=${sha.slice(0, 12)}…`,
      );
      return { requestCount: handlers.length, sha256: sha, sizeBytes: json.length };
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
      fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf-8");
      console.log("✓ all 5 cases captured. manifest written to", manifestPath);
    }

    main().catch((err) => {
      console.error("✗ capture failed:", err);
      process.exit(1);
    });
    ```

    **Important details:**
    1. **Dynamic import** of `research()` AFTER `startRecording()` runs — otherwise the fetcher modules may capture a reference to the original fetch.
    2. **`globalThis.fetch` patch** — works in Node 20+ where fetch is global.
    3. **Determinism:** JSON output uses 2-space indent + trailing newline. Sort-keys is NOT used at the top level (would re-order request fields like method/url/responseStatus — destabilizes structure); inner objects ARE serialized in declared key order which is consistent.
    4. **One case at a time** — caches between cases (if any) would persist across cases; in TS-W2 there's no disk cache (lands in TS-W3) so this is moot.

    Add to `packages-ts/meta/package.json`:
    - `"capture-parity": "tsx tests/parity/capture_recordings.ts"` under `scripts`.
    - Add `tsx` to `devDependencies` if not already present (`pnpm --filter tradewinds add -D tsx`).
  </action>
  <verify>
    <automated>pnpm --filter tradewinds typecheck</automated>
  </verify>
  <done>
    `capture_recordings.ts` compiles cleanly; the env-var gate works (running without TRADEWINDS_TS_LIVE=1 exits with code 1); the script is invocable via `pnpm --filter tradewinds capture-parity`.
  </done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 2: Operator runs capture script to produce recordings</name>
  <what-needs-human>
    The capture script hits real public APIs (AWC, IEM, GHCNh, NCEI). Running it requires network access and produces ~10-50 MB of recordings. The operator (vuhcze@gmail.com) is the only one who should run this — same operational discipline as the parquet fixture capture (`tests/fixtures/parity/capture_fixtures.py`).
  </what-needs-human>
  <instructions>
    Run from the repo root:

    ```bash
    TRADEWINDS_TS_LIVE=1 pnpm --filter tradewinds capture-parity
    ```

    Expected: console prints "[case_N] captured ..." for each of the 5 cases. Total runtime ~5-15 minutes (IEM ASOS is rate-limited at 1 req/sec; case 4 spans a full year × 2 report_types = 2-4 requests; GHCNh PSVs are large so transfer time dominates).

    After capture completes, verify:

    ```bash
    ls packages-ts/meta/tests/parity/recordings/
    # Should show: manifest.json, case_1/, case_2/, case_3/, case_4/, case_5/
    cat packages-ts/meta/tests/parity/recordings/manifest.json
    # Should show 5 cases with request_count, sha256, size_bytes
    ```

    Spot-check one handlers.json:

    ```bash
    head -100 packages-ts/meta/tests/parity/recordings/case_1/handlers.json
    # Should show array of {method, url, responseStatus, responseBody, contentType}
    ```

    Commit the recordings to git:

    ```bash
    git add packages-ts/meta/tests/parity/recordings/
    git commit -m "ts-w2-07: capture parity recordings (5 cases)"
    ```

    If a case fails to capture (e.g. NCEI 503), retry just that case by editing CASES in capture_recordings.ts temporarily — or accept the partial capture and re-run only the failing case manually. AWC may return 0 records for historical windows older than 168h; that's expected (case 1-5 are all historical) — the recording will still contain the AWC request + empty-array response.
  </instructions>
  <resume-signal>
    Type "captured" once all 5 case directories exist + manifest.json is populated + git commit recorded. If any case requires re-capture or shows anomalies, describe and we'll iterate.
  </resume-signal>
</task>

<task type="auto">
  <name>Task 3: Write recordings/README.md with replay-side instructions</name>
  <files>packages-ts/meta/tests/parity/recordings/README.md</files>
  <action>
    Create `packages-ts/meta/tests/parity/recordings/README.md`:

    ```markdown
    # MSW recordings — TS parity gate (Plan 08 consumes)

    **Status:** Captured by Plan 07 via `capture_recordings.ts`.
    **Source:** Live public APIs (AWC, IEM ASOS, IEM CLI, GHCNh).
    **Consumed by:** `packages-ts/meta/tests/parity/parity.test.ts` (Plan 08).

    ## Layout

    ```
    recordings/
    ├── manifest.json                  # per-case sha256 + request_count + size_bytes
    ├── case_1/
    │   └── handlers.json              # array of {method, url, responseStatus, responseBody, contentType}
    ├── case_2/
    │   └── handlers.json
    ├── case_3/
    │   └── handlers.json
    ├── case_4/
    │   └── handlers.json
    └── case_5/
        └── handlers.json
    ```

    ## Replay (Plan 08 usage)

    Each `handlers.json` is loaded by the parity test, converted to msw 2.x handlers, and installed via `setupServer(...)`:

    ```typescript
    import { http, HttpResponse } from "msw";
    import { setupServer } from "msw/node";
    import handlersRaw from "./recordings/case_1/handlers.json" with { type: "json" };

    const handlers = handlersRaw.map((r) =>
      http[r.method.toLowerCase() as "get"](r.url, () => {
        return new HttpResponse(r.responseBody, {
          status: r.responseStatus,
          headers: { "content-type": r.contentType },
        });
      }),
    );

    const server = setupServer(...handlers);
    beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
    afterEach(() => server.resetHandlers());
    afterAll(() => server.close());
    ```

    **`onUnhandledRequest: "error"`** is load-bearing: if the test issues a request the recording doesn't cover, msw throws — catches regressions where the TS fetcher emits a request shape that drifted from the captured URL.

    ## DO NOT EDIT THESE FILES BY HAND

    Same discipline as `tests/fixtures/parity/case_*.parquet` (Python ground truth). The recordings + the JSON fixtures (under `tests/fixtures/parity/ts/`) are joined settlement-grade ground truth. They MUST be regenerated together if regenerated at all.

    ## Regenerate

    Only if the Python parquet fixtures change (see `tests/fixtures/parity/README.md` §Re-capture):

    1. Re-run the Python re-capture (operator-gated, requires MOSTLYRIGHT_API_KEY).
    2. Re-run the JSON export: `uv run python tests/fixtures/parity/export_for_ts.py`.
    3. Re-run the TS recording capture: `TRADEWINDS_TS_LIVE=1 pnpm --filter tradewinds capture-parity`.
    4. Verify manifest sha256s changed (and only as expected for the changes).
    5. Commit all three sets together.

    ## Why this directory is checked into git

    Settlement-grade ground truth. The bytes ARE the test. We accept the ~10-50 MB git delta because:
    1. Without recordings the test cannot replay deterministically.
    2. msw recording-server modes that write to disk on each run break determinism + reproducibility.
    3. Drift cron (Plan 08's `drift-rotate-ts.yml`) periodically re-captures and diffs against these recordings; mismatches indicate upstream-API drift.
    ```
  </action>
  <verify>
    <automated>test -f packages-ts/meta/tests/parity/recordings/README.md &amp;&amp; test -f packages-ts/meta/tests/parity/recordings/manifest.json</automated>
  </verify>
  <done>
    README.md exists and documents the replay-side msw setup pattern Plan 08 will use; manifest.json exists from Task 2; the recordings directory is committed to git.
  </done>
</task>

</tasks>

<verification>
- `capture_recordings.ts` exists and compiles.
- All 5 `case_N/handlers.json` files exist.
- `manifest.json` lists all 5 cases with sha256.
- README.md documents the replay protocol.
- The whole directory is committed to git.
- Running `tsx capture_recordings.ts` WITHOUT `TRADEWINDS_TS_LIVE=1` exits 1 (gate works).
</verification>

<success_criteria>
Maps to TS-W2 stub Wave 7 (recordings half — fixture-JSON half is Plan 03): "Export 5 Python parity fixtures as JSON + capture HTTP recordings via msw recordHandlers OR replay vcrpy cassettes."

- 5/5 case recordings captured.
- Replay protocol documented for Plan 08.
- Determinism gate via env-var prevents accidental re-capture.
</success_criteria>

<output>
After completion, create `.planning/phases/ts-w2-parity-gate/ts-w2-07-SUMMARY.md` documenting:
- Total recording size in MB.
- Per-case request count.
- Any cases that required retry (network failures during capture).
- Confirmation that recordings + manifest are committed to git.
- Pointer to Plan 08 for replay-side wiring.
</output>
