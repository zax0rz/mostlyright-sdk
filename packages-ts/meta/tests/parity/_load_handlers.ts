// Convert a recorded-request tape (Plan 07 output) into msw 2.x handlers.
//
// Each handler matches on exact URL + method and returns the recorded body.
// Repeat URLs are served in declared order (FIFO queue per URL+method);
// once exhausted, the last response repeats indefinitely. In TS-W2 each
// (station, year, report_type) URL is unique so this matters only as a
// defensive backstop.
//
// Replay-side discipline: the parity test installs msw with
// `onUnhandledRequest: "error"` so any URL drift between research() and
// the recordings produces an immediate, clear test failure.

import { http, type HttpHandler, HttpResponse } from "msw";

export interface RecordedRequest {
  method: string;
  url: string;
  responseStatus: number;
  responseBody: string;
  contentType: string;
}

export function loadHandlers(records: ReadonlyArray<RecordedRequest>): HttpHandler[] {
  const calls = new Map<string, number>();
  const queues = new Map<string, RecordedRequest[]>();
  for (const r of records) {
    const k = `${r.method.toUpperCase()} ${r.url}`;
    let q = queues.get(k);
    if (q === undefined) {
      q = [];
      queues.set(k, q);
    }
    q.push(r);
  }
  const handlers: HttpHandler[] = [];
  for (const [k, queue] of queues) {
    const spaceIdx = k.indexOf(" ");
    const method = k.slice(0, spaceIdx);
    const url = k.slice(spaceIdx + 1);
    const m = method.toLowerCase();
    const factory = (http as unknown as Record<string, typeof http.get | undefined>)[m];
    if (!factory) {
      throw new Error(`Unsupported HTTP method in recording: ${method}`);
    }
    handlers.push(
      factory(url, () => {
        const idx = calls.get(k) ?? 0;
        calls.set(k, idx + 1);
        const r = queue[Math.min(idx, queue.length - 1)] as RecordedRequest;
        return new HttpResponse(r.responseBody, {
          status: r.responseStatus,
          headers: { "content-type": r.contentType || "text/plain" },
        });
      }),
    );
  }
  return handlers;
}
