# Browser integration guide (`@mostlyrightmd/*` in MV3 + web apps)

The TS SDK is engineered for browser runtimes alongside Node. This guide
covers the four patterns we test against:

1. **Chrome MV3 service-worker** (extension background)
2. **Chrome MV3 content-script** (page-injected)
3. **IIFE / `<script>` tag** for vanilla web apps
4. **Service worker / Cloudflare Worker / Bun edge** for serverless paths

See the in-repo worked example at [`packages-ts/examples/chrome-extension-mvp/`](../packages-ts/examples/chrome-extension-mvp/).

## Why this matters

CORS posture per [`.planning/research/TS-CORS-MATRIX.md`](../.planning/research/TS-CORS-MATRIX.md):

| Source | CORS for browser direct-fetch |
|---|---|
| AWC live (`/api/data/`) | ✅ allowed |
| IEM CLI (`/api/1/climodat_xref.json`) | ✅ allowed |
| IEM ASOS (`/cgi-bin/request/asos.py`) | ❌ blocked (no `Access-Control-Allow-Origin`) |
| GHCNh PSV (NCEI) | ❌ blocked |
| Polymarket Gamma (`gamma-api.polymarket.com`) | ❌ blocked from `*` origins |

Extensions can fetch CORS-blocked endpoints from the service worker after declaring `host_permissions` — that's the worked example below. Web apps with no extension host need a proxy.

## Pattern 1 — MV3 service worker (extension background)

Background scripts in MV3 run as ES module service workers. They have `fetch`, `crypto.subtle`, IndexedDB, and `chrome.*` APIs.

```json
// manifest.json
{
  "manifest_version": 3,
  "name": "mostlyright-extension",
  "version": "0.1.0",
  "permissions": ["storage"],
  "host_permissions": [
    "https://aviationweather.gov/*",
    "https://mesonet.agron.iastate.edu/*",
    "https://www.ncei.noaa.gov/*"
  ],
  "background": {
    "service_worker": "background.js",
    "type": "module"
  }
}
```

```ts
// background.ts → bundled to background.js as ES module
import { research } from "mostlyright";
import { kalshiSettlementFor } from "@mostlyrightmd/markets";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "research") {
    research(msg.station, msg.fromDate, msg.toDate)
      .then((rows) => sendResponse({ ok: true, rows }))
      .catch((err: Error) => sendResponse({ ok: false, error: err.message }));
    return true; // keep the response port open across the async boundary
  }
  if (msg.type === "kalshi-settlement") {
    try {
      sendResponse({ ok: true, result: kalshiSettlementFor(msg.contractId, msg.date) });
    } catch (err) {
      sendResponse({ ok: false, error: (err as Error).message });
    }
  }
});
```

**CSP-safe:** all bundles are CSP-clean (`script-src 'self'`); no `eval`, no `new Function(...)`, no remote code. ajv runs in `ajv-standalone` precompiled form, never runtime.

**Bundle size:** the `@mostlyrightmd/core` main entry stays under 25 KB min+gzip (the [`TS-BUNDLE-01`](../.planning/REVIEW-DISCIPLINE.md) gate). Subpath imports (`@mostlyrightmd/core/temporal`, `/discovery`, `/transforms`, etc.) tree-shake separately.

## Pattern 2 — MV3 content script

Content scripts run inside the page world but have a limited API surface and CANNOT make CORS-blocked requests. They forward work to the background:

```ts
// content-script.ts (injected via manifest content_scripts)
const resp = await chrome.runtime.sendMessage({
  type: "research",
  station: "KNYC",
  fromDate: "2025-01-06",
  toDate: "2025-01-12",
});
if (resp.ok) {
  console.log(`Got ${resp.rows.length} rows`);
}
```

## Pattern 3 — IIFE for vanilla web apps

The meta IIFE bundle (`mostlyright`) INLINES the three scoped packages, so a single `<script>` tag is enough. It exposes `globalThis.mostlyright` with `research()` and the rest of the meta surface. Limited to AWC + IEM CLI in-browser (the only CORS-allowed endpoints):

```html
<script src="https://unpkg.com/mostlyright/dist/index.global.js"></script>
<script>
  mostlyright.research("KNYC", "2025-01-06", "2025-01-12").then(console.log);
</script>
```

If you only need one scoped surface (e.g. just `@mostlyrightmd/core` for temporal primitives), the scoped IIFEs are available as `mostlyrightCore`, `mostlyrightWeather`, `mostlyrightMarkets` globals at `https://unpkg.com/@mostlyrightmd/<pkg>/dist/index.global.js` — but `research()` itself only ships from the meta global.

For SDK-style use, ESM via a bundler (vite/esbuild/webpack) is preferred. The IIFE is for quick scratch pages and Kalshi-page overlays that can't run a build step.

## Pattern 4 — Cloudflare Workers / Bun edge

Workers ship ES modules; the SDK works as-is. There's no IndexedDB, so the
`MemoryStore` is the default cache. Wrap in Durable Objects + KV for
cross-request persistence if needed:

```ts
import { research } from "mostlyright";
import { MemoryStore } from "@mostlyrightmd/core/internal/cache";

export default {
  async fetch(req: Request, env: Env) {
    const url = new URL(req.url);
    const station = url.searchParams.get("station") ?? "KNYC";
    const cache = new MemoryStore();
    const rows = await research(station, "2025-01-06", "2025-01-12", { cache });
    return Response.json(rows);
  },
};
```

## Verifying your integration

Quick smoke test from the browser console (after the extension is loaded
and host permissions granted). `research()` ships from the meta package
only — the worker bundle for an extension that imports `mostlyright`
exposes it as the `mostlyright` global if you used the IIFE; via the ESM
bundle it's the imported binding directly.

```ts
// ESM-bundled extensions (the recommended path) — assuming the service
// worker imports `research` from "mostlyright":
import { research } from "mostlyright";
const rows = await research("KNYC", "2025-01-06", "2025-01-12");
console.assert(rows.length > 0, "research returned no rows — check host_permissions");
console.assert(typeof rows[0].cli_high_f === "number", "CLI data missing");
```

For an end-to-end browser smoke test against published packages, see
[`packages-ts/examples/chrome-extension-mvp/`](../packages-ts/examples/chrome-extension-mvp/) — (see the chrome-extension example).

## Common pitfalls

- **`Refused to load … because it violates the Content Security Policy`** — you imported a non-mostlyright module that uses `eval`. mostlyright is CSP-clean; check your other deps.
- **`Access to fetch at … has been blocked by CORS policy`** — the page can't reach the upstream API directly. Either move the fetch to the service worker with `host_permissions`, or proxy through your own backend. AWC + IEM CLI are the only browser-direct-fetchable upstream sources.
- **`TypeError: navigator.locks is not a function`** — older browsers / jsdom test envs. The SDK transparently falls back to an in-process promise chain (FIFO) — no behavior change for single-tab use; cross-tab locking degrades to best-effort.
- **`research(...)` returns no rows after cache warming** — confirm the station code form. `research("KNYC", ...)` and `research("NYC", ...)` both work and write the cache under `NYC` (the 3-letter NWS code). See [`availability`](../packages-ts/core/src/discovery/availability.ts) which resolves both forms.
