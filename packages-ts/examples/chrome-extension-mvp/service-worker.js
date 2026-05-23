// MV3 service worker for the TS-W1 Chrome smoke extension.
//
// Loads the BUNDLED `tradewinds` ESM (single-file build with workspace
// deps inlined) copied to ./lib/index.bundle.mjs by the setup step in
// README.md, and exposes `research()` via chrome.runtime messaging.
// The popup sends `{ type: "research", station, fromDate, toDate }`
// and receives `{ ok: true, rows }` or `{ ok: false, error }`.
//
// IMPORTANT: do NOT import the non-bundled `index.mjs` here — that file
// has bare specifiers (`@tradewinds/core`, etc.) that Chrome MV3 service
// workers cannot resolve (no node_modules, no import map). The bundled
// variant inlines all workspace deps; only standard browser globals
// (`fetch`, `URL`, `AbortController`, etc.) remain external.
//
// MV3 service workers run in their own JS context (no DOM, no
// localStorage) but DO have `fetch` and bypass CORS for hosts listed in
// `manifest.json -> host_permissions` — exactly what AWC needs.

import { research } from "./lib/index.bundle.mjs";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== "research") return false;
  // We must return `true` synchronously so the channel stays open for the
  // async response.
  research(msg.station, msg.fromDate, msg.toDate)
    .then((rows) => {
      sendResponse({ ok: true, rows });
    })
    .catch((err) => {
      sendResponse({ ok: false, error: String(err?.message ?? err) });
    });
  return true;
});
