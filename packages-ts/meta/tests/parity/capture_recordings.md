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

- **First-time recording for TS-W2:** Plan 07 captures all 4 sources per case.
- **After Python parity fixtures change:** the parquet fixtures and recordings
  are joined ground truth; re-record both together.
- **Otherwise: NEVER.** The recordings are immutable settlement-grade ground
  truth, same discipline as the parquet fixtures.

## Recording procedure (Plan 07 owns the actual capture)

1. Set `MOSTLYRIGHT_TS_LIVE=1` in env (gates a live-capture vitest suite).
2. Run the capture script that wraps `research()` for each case and writes
   msw-format JSON handlers to `recordings/case_N_<station>_<from>_<to>/handlers.json`.
3. Each handler entry shape:
   ```json
   {
     "method": "GET",
     "url": "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=...",
     "response_status": 200,
     "response_body": "<csv body>",
     "content_type": "text/plain"
   }
   ```
4. Commit the recordings dir to git.

## Recording shape per case

Per case, expect ~3-365 outbound requests:
- IEM ASOS: 1-2 yearly chunks × 2 report_types = 2-4 requests.
- IEM CLI: 1-2 station-years × 1 request = 1-2 requests.
- GHCNh: 1-2 station-years × 1 request = 1-2 requests (skipped for non-US stations).
- AWC: 1 request (if any date in range overlaps last 168h — likely zero for cases 1-5 because they are historical).

The recordings directory will balloon to ~5-50 MB total (PSV bodies are large).
That's accepted — it's settlement-grade ground truth.

## Outstanding for Plan 07 + 08

- [ ] **Plan 07:** Build `capture_recordings.ts` script + capture 5 case recordings.
- [ ] **Plan 08:** Wire recordings into `parity.test.ts` via msw's `setupServer(...handlers)` + add `recordings/README.md` listing per-case sha256 of `handlers.json`.
