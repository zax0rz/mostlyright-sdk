# tradewinds TS-W1 Chrome MVP smoke

A minimal MV3 extension that calls `research(station, fromDate, toDate)` from
the built `tradewinds` meta bundle inside a service worker. MV3 service workers
bypass CORS for hosts declared in `host_permissions`, so AWC + IEM CLI both
work without a proxy.

1. From repo root: `pnpm --filter tradewinds build`
2. Copy the built ESM bundle to `lib/`:
   `mkdir -p packages-ts/examples/chrome-extension-mvp/lib && cp packages-ts/meta/dist/index.mjs packages-ts/examples/chrome-extension-mvp/lib/`
3. Open `chrome://extensions/` → enable Developer Mode → "Load unpacked" →
   select `packages-ts/examples/chrome-extension-mvp/`.
4. Click the extension icon → confirm station "NYC" + date range → "Lookup".
5. Expected: JSON output with one row per day. The 7 most recent days will
   carry `obs_count > 0` (AWC live window); CLI fields populate for any day
   that has a published NWS climate report.

Not currently part of the workspace `pnpm -r` graph — this directory is shipped
as-is for manual smoke testing.
