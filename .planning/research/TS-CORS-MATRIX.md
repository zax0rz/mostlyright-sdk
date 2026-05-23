# TS-CORS-MATRIX — Empirical CORS Posture per Upstream Endpoint

**Captured:** 2026-05-23
**Tool:** curl 8.x (macOS)
**Origin sent:** `https://example.com` (non-allowed; simulates a non-extension web app)
**Endpoints tested:** AWC, IEM-ASOS, IEM-CLI, GHCNh, Polymarket Gamma

This document is the binding source for TS-W2 (parity gate) decisions about which fetchers ship with a CORS-workaround note. Re-capture annually or when an upstream endpoint changes; document re-capture in the append-only Capture history at the bottom.

CORS terminology used here: a server returning `Access-Control-Allow-Origin: *` is **OPEN** (usable from any web origin). A server returning a specific origin is **ALLOW-LISTED** (only certain origins permitted). A server returning no ACAO header at all is **NONE** (browsers will block the response — server is unaware of CORS).

## Summary table

| Endpoint | Posture | ACAO header (GET) | OPTIONS preflight | Usable in web app? | Workaround |
|---|---|---|---|---|---|
| AWC | NONE | (absent) | 200 (no ACAO; only `Allow: GET, HEAD`) | No — blocked by browser | Chrome extension `host_permissions` OR Cloudflare Worker CORS proxy |
| IEM-ASOS | OPEN | `*` | 400 with `ACAO: *` (server rejects OPTIONS body but still sends ACAO) | Yes — simple GET works | none needed |
| IEM-CLI | OPEN | `*` | 200 with `ACAO: *` | Yes | none needed |
| GHCNh | OPEN | `*` | 403 with `ACAO: *` (OPTIONS not permitted but ACAO present) | Yes — simple GET works | none needed |
| Polymarket Gamma | OPEN | `*` | 200 with full preflight headers | Yes | none needed |

## Per-endpoint detail

### AWC — Aviation Weather Center METAR

**URL tested:** `https://aviationweather.gov/api/data/metar?ids=KNYC&format=json&hours=1`

**Preflight (OPTIONS):**
```
HTTP/2 200
date: Sat, 23 May 2026 20:33:49 GMT
content-type: text/plain
content-length: 9
allow: GET, HEAD
x-content-type-options: nosniff
x-frame-options: SAMEORIGIN
content-security-policy: frame-ancestors 'self' *.weather.gov
strict-transport-security: max-age=63072000; includeSubDomains
x-azure-ref: 20260523T203349Z-157794674c5tgkdkhC1FRA2thc0000000nqg00000000ec25
x-cache: CONFIG_NOCACHE
accept-ranges: bytes
```

**GET with Origin: https://example.com:**
```
HTTP/2 200
date: Sat, 23 May 2026 20:33:49 GMT
content-type: application/json; charset=utf-8
content-length: 998
cache-control: max-age=60
etag: W/"3e6-ujQg3CwznNSZNzRu8nqFHaMSgyY"
x-frame-options: SAMEORIGIN
content-security-policy: frame-ancestors 'self' *.weather.gov
strict-transport-security: max-age=63072000; includeSubDomains
x-azure-ref: 20260523T203349Z-157794674c5lcwzwhC1FRAfpqs0000000cmg000000006ad9
x-fd-int-roxy-purgeid: 66958969
x-cache: TCP_MISS
accept-ranges: bytes
```

**Posture:** NONE — no `Access-Control-Allow-Origin` header on either OPTIONS or GET response. The server returns 200 with valid JSON, but a browser fetch from a non-allowed origin will fail the CORS check and the response will be discarded by the browser before it reaches application code. Confirmed via case-insensitive grep against the GET response — zero `access-control-*` headers present.

**Browser-app usability:** **No** — blocked by browser. Server-side fetches (Node.js, Python, Chrome extension service worker with `host_permissions`) work fine; only browser-origin fetches from a web app are blocked.

**Chrome extension manifest snippet:**
```json
"host_permissions": ["https://aviationweather.gov/*"]
```

**Non-extension web-app workaround:** A tiny CORS proxy is required. Example Cloudflare Worker (~15 lines):

```js
// awc-cors-proxy.worker.js
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const upstream = `https://aviationweather.gov${url.pathname}${url.search}`;
    const resp = await fetch(upstream, { headers: { 'User-Agent': 'tradewinds-ts/0.1' } });
    const headers = new Headers(resp.headers);
    headers.set('Access-Control-Allow-Origin', '*');
    headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return new Response(resp.body, { status: resp.status, headers });
  }
};
```

Recommendation for TS-W2: fetcher `_fetchers/awc.ts` must carry a `// CORS: requires extension host_permissions OR CORS proxy (see docs/chrome-extension-integration.md)` comment. Default behavior in pure-browser web apps: surface a clear error directing user to the proxy or extension path.

### IEM-ASOS — Iowa Environmental Mesonet ASOS request

**URL tested:** `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=NYC&data=tmpf&year1=2024&month1=1&day1=1&year2=2024&month2=1&day2=2&tz=Etc/UTC&format=comma`

**Preflight (OPTIONS):**
```
HTTP/1.1 400 Bad Request
Date: Sat, 23 May 2026 20:33:54 GMT
Server: Apache/2.4.62 (AlmaLinux) OpenSSL/3.5.1 mod_fcgid/2.3.9 mod_wsgi/5.0.2 Python/3.14
X-IEM-ServerID: iemvs38-dc.agron.iastate.edu
Access-Control-Allow-Origin: *
Connection: close
Transfer-Encoding: chunked
Content-Type: text/plain; charset=UTF-8
```

Note: server returns 400 on OPTIONS (the CGI script rejects the method) BUT still emits `Access-Control-Allow-Origin: *`. For a "simple request" (GET with no custom headers beyond `Accept`), no preflight is triggered, so the 400 on OPTIONS is irrelevant in practice. If the TS fetcher adds custom headers (e.g., `X-Custom`), the preflight will fail.

**GET with Origin: https://example.com (initial; rate-limited):**
```
HTTP/1.1 429 Too Many Requests
Date: Sat, 23 May 2026 20:33:54 GMT
Server: Apache/2.4.62 (AlmaLinux) OpenSSL/3.5.1 mod_fcgid/2.3.9 mod_wsgi/5.0.2 Python/3.14
X-IEM-ServerID: iemvs44-dc.agron.iastate.edu
Access-Control-Allow-Origin: *
Transfer-Encoding: chunked
Content-Type: text/plain; charset=UTF-8
```

**GET retry after 5s backoff (successful):**
```
HTTP/1.1 200 OK
Date: Sat, 23 May 2026 20:34:29 GMT
Server: Apache/2.4.62 (AlmaLinux) OpenSSL/3.5.1 mod_fcgid/2.3.9 mod_wsgi/5.0.2 Python/3.14
X-IEM-ServerID: iemvs39-dc.agron.iastate.edu
Access-Control-Allow-Origin: *
Transfer-Encoding: chunked
Content-Type: text/plain; charset=UTF-8
```

**Posture:** OPEN — `Access-Control-Allow-Origin: *` returned on both 429 and 200 GETs (and even on the 400 OPTIONS). IEM appears to set ACAO globally at the Apache level regardless of response status.

**Browser-app usability:** **Yes** — usable directly from any web origin for simple GET requests. Keep request "simple" (no custom headers beyond `Accept`) to avoid OPTIONS preflight which the CGI rejects.

**Chrome extension manifest snippet (optional, for parity with extension consumers):**
```json
"host_permissions": ["https://mesonet.agron.iastate.edu/*"]
```

**Non-extension web-app workaround:** none needed. Caveat: rate limits (429) exist; fetcher should implement exponential backoff. Keep requests "simple" (no preflight-triggering headers).

### IEM-CLI — Iowa Environmental Mesonet CLI JSON

**URL tested:** `https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024`

**Preflight (OPTIONS):**
```
HTTP/1.1 200 OK
Date: Sat, 23 May 2026 20:33:56 GMT
Server: Apache/2.4.62 (AlmaLinux) OpenSSL/3.5.1 mod_fcgid/2.3.9 mod_wsgi/5.0.2 Python/3.14
X-IEM-ServerID: iemvs44-dc.agron.iastate.edu
Access-Control-Allow-Origin: *
Transfer-Encoding: chunked
Content-Type: application/json; charset=utf-8
```

**GET with Origin: https://example.com:**
```
HTTP/1.1 200 OK
Date: Sat, 23 May 2026 20:33:57 GMT
Server: Apache/2.4.62 (AlmaLinux) OpenSSL/3.5.1 mod_fcgid/2.3.9 mod_wsgi/5.0.2 Python/3.14
X-IEM-ServerID: iemvs39-dc.agron.iastate.edu
Access-Control-Allow-Origin: *
Transfer-Encoding: chunked
Content-Type: application/json; charset=utf-8
```

**Posture:** OPEN — `Access-Control-Allow-Origin: *` on both OPTIONS (200) and GET (200). Cleanest CORS posture of any IEM endpoint tested.

**Browser-app usability:** **Yes** — usable directly. Preflight succeeds, so the fetcher may use custom headers safely.

**Chrome extension manifest snippet (optional):**
```json
"host_permissions": ["https://mesonet.agron.iastate.edu/*"]
```

**Non-extension web-app workaround:** none needed.

### GHCNh — NCEI Global Historical Climatology Network hourly PSV

**URL tested:** `https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/2024/psv/GHCNh_USW00094728_2024.psv`

**Preflight (OPTIONS):**
```
HTTP/1.1 403 Forbidden
Date: Sat, 23 May 2026 20:34:02 GMT
Server: Apache
Strict-Transport-Security: max-age=31536000
content-length: 93
cache-control: no-cache
content-type: text/html
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: X-Requested-With, Content-Type
```

OPTIONS is rejected (403) but the server still emits `Access-Control-Allow-Origin: *` and `Access-Control-Allow-Headers: X-Requested-With, Content-Type`. For a "simple request" (GET with `Accept: */*` only), no preflight is triggered, so this is fine.

**GET with Origin: https://example.com:**
```
HTTP/1.1 200 OK
Date: Sat, 23 May 2026 20:34:02 GMT
Server: Apache
Strict-Transport-Security: max-age=31536000
content-length: 10514976
accept-ranges: bytes
last-modified: Wed, 20 May 2026 15:49:43 GMT
x-rgw-object-type: Normal
etag: "a127f1e0750b62c19848b06e2cc1e5bf"
content-disposition: hourly%2Faccess%2Fby-year%2F2024%2Fpsv%2FGHCNh_USW00094728_2024.psv
x-amz-storage-class: STANDARD
x-amz-request-id: tx000000de613f3c0b7aeca-006a120f3a-21944e4-ncei-nc-1
content-type: application/octet-stream
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: X-Requested-With, Content-Type
```

**Posture:** OPEN — `Access-Control-Allow-Origin: *` on GET 200. The Ceph/RGW (S3-style) object backend behind NCEI sets ACAO globally.

**Browser-app usability:** **Yes** — usable directly from any web origin. Note: response is 10 MB per station-year; consider streaming/range requests for large fetches. `accept-ranges: bytes` is supported.

**Chrome extension manifest snippet (optional):**
```json
"host_permissions": ["https://www.ncei.noaa.gov/*"]
```

**Non-extension web-app workaround:** none needed. Keep requests "simple" (no custom headers beyond `Accept`, `Accept-Language`, `Range`) to avoid triggering preflight which the server rejects with 403.

### Polymarket Gamma — Events API

**URL tested:** `https://gamma-api.polymarket.com/events?limit=1`

**Preflight (OPTIONS):**
```
HTTP/2 200
date: Sat, 23 May 2026 20:34:03 GMT
content-length: 0
set-cookie: __cf_bm=...; HttpOnly; SameSite=None; Secure; Path=/; Domain=polymarket.com; Expires=Sat, 23 May 2026 21:04:03 GMT
access-control-allow-headers: Accept, Authorization, Content-Type, X-CSRF-Token, Token, traceparent, tracestate, baggage
access-control-allow-methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
access-control-allow-origin: *
access-control-max-age: 2592000
vary: Origin
vary: Access-Control-Request-Method
vary: Access-Control-Request-Headers
cf-cache-status: DYNAMIC
strict-transport-security: max-age=7776000; includeSubDomains
server: cloudflare
cf-ray: a006d6d28b49f98c-PRG
alt-svc: h3=":443"; ma=86400
```

**GET with Origin: https://example.com:**
```
HTTP/2 200
date: Sat, 23 May 2026 20:34:03 GMT
content-type: application/json
vary: Accept-Encoding
vary: Origin
access-control-allow-headers: Accept, Authorization, Content-Type, X-CSRF-Token, Token, traceparent, tracestate, baggage
access-control-allow-methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
access-control-allow-origin: *
access-control-max-age: 2592000
deprecation: true
sunset: Fri, 01 May 2026 00:00:00 GMT
warning: 299 - "use /events/keyset"
set-cookie: __cf_bm=...; HttpOnly; SameSite=None; Secure; Path=/; Domain=polymarket.com; Expires=Sat, 23 May 2026 21:04:03 GMT
last-modified: Sat, 23 May 2026 20:34:03 GMT
expires: Sat, 23 May 2026 20:39:03 GMT
cache-control: public, max-age=300
cf-cache-status: EXPIRED
strict-transport-security: max-age=7776000; includeSubDomains
server: cloudflare
cf-ray: a006d6d3193634d7-PRG
alt-svc: h3=":443"; ma=86400
```

**Posture:** OPEN — full CORS: `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS`, `Access-Control-Max-Age: 2592000` (30 days). Cleanest preflight behavior of all endpoints tested.

**Browser-app usability:** **Yes** — first-class web-app usability. Preflight cached 30 days client-side.

**Sunset warning (out-of-band, but worth flagging for TS-W2):** `/events` carries `deprecation: true` and `sunset: Fri, 01 May 2026 00:00:00 GMT` plus `warning: 299 - "use /events/keyset"`. The endpoint still serves 200 today (2026-05-23) but is past its sunset date. TS-W2 fetcher should target `/events/keyset` rather than `/events`. (Re-run CORS capture against the keyset endpoint when implementing.)

**Chrome extension manifest snippet (optional):**
```json
"host_permissions": ["https://gamma-api.polymarket.com/*"]
```

**Non-extension web-app workaround:** none needed.

## Decisions for TS-W2 and beyond

- **Fetchers for endpoints with posture OPEN (IEM-ASOS, IEM-CLI, GHCNh, Polymarket Gamma):** ship directly; no CORS-workaround docs needed in fetcher tests or docs. Add `host_permissions` entries to the extension manifest for parity with extension consumers, but it's not required.
- **Fetchers for endpoints with posture NONE (AWC):** ship with a `// CORS: requires extension host_permissions OR CORS proxy` comment at the top of `_fetchers/awc.ts`. Add a section in `docs/chrome-extension-integration.md` listing AWC under "Requires host_permissions" with the manifest snippet above. Also document the Cloudflare Worker proxy template for non-extension consumers.
- **Polymarket sunset:** TS-W2 fetcher must target `/events/keyset` (or its successor); re-capture CORS posture for the new endpoint when chosen.
- **Annual re-capture cadence:** the `Captured:` date at the top drives a CI warning when stale (>365 days). Re-run the curl commands in this document and append a row to Capture history.
- **What "simple request" means in this context:** GET or POST with only the CORS-safelisted headers (`Accept`, `Accept-Language`, `Content-Language`, `Content-Type` of `application/x-www-form-urlencoded`/`multipart/form-data`/`text/plain`). Avoiding preflight matters for IEM-ASOS and GHCNh where OPTIONS is rejected. The TS fetcher SHOULD NOT add custom headers (e.g., `X-Tradewinds-Client`) for these two endpoints.

## Capture history

| Date | Capturer | What changed |
|---|---|---|
| 2026-05-23 | claude (TS-W0 Wave 5) | Initial capture. 4/5 endpoints OPEN; AWC is NONE. Polymarket `/events` flagged as past-sunset. |
