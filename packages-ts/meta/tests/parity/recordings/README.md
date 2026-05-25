# MSW recordings — TS parity gate (Plan 08 consumes)

**Status:** Operator-pending. The `capture_recordings.ts` script (Plan 07) is built
but the actual recordings have not been captured — Plan 07 Task 2 is
operator-gated (requires `MOSTLYRIGHT_TS_LIVE=1` env var + live network access).

**Source:** Live public APIs (AWC, IEM ASOS, IEM CLI, GHCNh).
**Consumed by:** `packages-ts/meta/tests/parity/parity.test.ts` (Plan 08).

## Layout (post-capture)

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

## How to capture (operator runs once)

From the repo root:

```bash
MOSTLYRIGHT_TS_LIVE=1 pnpm --filter mostlyright capture-parity
```

Expected runtime: 5–15 minutes (IEM ASOS rate-limited at 1 req/sec; case 4 spans
a full year). Total recordings size: ~5–50 MB depending on PSV content.

After capture completes:

```bash
ls packages-ts/meta/tests/parity/recordings/
# → manifest.json, case_1/, case_2/, case_3/, case_4/, case_5/
git add packages-ts/meta/tests/parity/recordings/
git commit -m "ts-w2-07: capture parity recordings (5 cases)"
```

## Replay (Plan 08 usage)

Each `handlers.json` is loaded by the parity test, converted to msw 2.x
handlers, and installed via `setupServer(...)`:

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

**`onUnhandledRequest: "error"`** is load-bearing: if the test issues a request
the recording doesn't cover, msw throws — catches regressions where the TS
fetcher emits a request shape that drifted from the captured URL.

## DO NOT EDIT THESE FILES BY HAND

Same discipline as `tests/fixtures/parity/case_*.parquet` (Python ground
truth). The recordings + the JSON fixtures (under `tests/fixtures/parity/ts/`)
are joined settlement-grade ground truth. They MUST be regenerated together
if regenerated at all.

## Regenerate

Only if the Python parquet fixtures change (see
`tests/fixtures/parity/README.md` §Re-capture):

1. Re-run the Python re-capture (operator-gated, requires MOSTLYRIGHT_API_KEY).
2. Re-run the JSON export: `uv run python tests/fixtures/parity/export_for_ts.py`.
3. Re-run the TS recording capture: `MOSTLYRIGHT_TS_LIVE=1 pnpm --filter mostlyright capture-parity`.
4. Verify manifest sha256s changed (and only as expected for the changes).
5. Commit all three sets together.

## Why this directory is checked into git

Settlement-grade ground truth. The bytes ARE the test. We accept the ~10–50 MB
git delta because:
1. Without recordings the test cannot replay deterministically.
2. msw recording-server modes that write to disk on each run break determinism
   + reproducibility.
3. Drift cron (Plan 08's `drift-rotate-ts.yml`) periodically re-captures and
   diffs against these recordings; mismatches indicate upstream-API drift.
