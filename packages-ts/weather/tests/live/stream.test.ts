// Phase 11 — `stream()` async-generator tests (14 tests).
//
// Mirrors `packages/core/tests/test_live_stream.py`. Uses
// `vi.useFakeTimers()` so the polite-floor sleep is instant, and mocks
// `globalThis.fetch` for AWC ticks. IEM tests spy on `fetchLatest` to bypass
// the dynamic-import IEM path.

import { type MockInstance, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POLITE_FLOORS_S } from "../../src/live/sources.js";
import { stream } from "../../src/live/stream.js";
import * as fetchModule from "../../src/live/_fetch.js";
import type { LiveObservation } from "../../src/live/types.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function awcMetar(obsTime: number): unknown {
  return {
    icaoId: "KNYC",
    obsTime,
    metarType: "METAR",
    temp: 20.0,
    dewp: 10.0,
    rawOb: "KNYC 251200Z 18010KT 10SM CLR 20/10 A3010",
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function iemLiveObservation(obsAt: string): LiveObservation {
  return {
    station_code: "NYC",
    observed_at: obsAt,
    observation_type: "METAR",
    source: "iem.live",
    temp_c: 20,
    dewpoint_c: 10,
    temp_f: 68,
    dewpoint_f: 50,
    wind_dir_degrees: null,
    wind_speed_kt: null,
    wind_gust_kt: null,
    altimeter_inhg: null,
    sea_level_pressure_mb: null,
    sky_cover_1: null,
    sky_base_1_ft: null,
    sky_cover_2: null,
    sky_base_2_ft: null,
    sky_cover_3: null,
    sky_base_3_ft: null,
    sky_cover_4: null,
    sky_base_4_ft: null,
    visibility_miles: null,
    weather_codes: null,
    raw_metar: null,
    precip_in: null,
    qc_field: null,
  };
}

/**
 * Collect up to N items from an async generator, advancing fake timers between
 * yields so the polite-floor sleep completes promptly.
 */
async function collectN(
  agen: AsyncGenerator<LiveObservation>,
  n: number,
): Promise<LiveObservation[]> {
  const items: LiveObservation[] = [];
  while (items.length < n) {
    // Advance timers before each `.next()` to flush any pending sleeps.
    // First iteration: no prior sleep, but advance is a no-op anyway.
    vi.runAllTimersAsync();
    const res = await agen.next();
    if (res.done) break;
    items.push(res.value);
  }
  await agen.return(undefined);
  return items;
}

let fetchSpy: MockInstance<typeof globalThis.fetch>;

beforeEach(() => {
  vi.useFakeTimers();
  fetchSpy = vi.spyOn(globalThis, "fetch");
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("stream()", () => {
  it("yields observations", async () => {
    fetchSpy.mockResolvedValue(jsonResponse([awcMetar(1748174400)]));
    const rows = await collectN(stream("KNYC"), 1);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.station_code).toBe("NYC");
  });

  it("default source is AWC", async () => {
    fetchSpy.mockResolvedValue(jsonResponse([awcMetar(1748174400)]));
    const rows = await collectN(stream("KNYC"), 1);
    expect(rows[0]?.source).toBe("awc.live");
    expect(fetchSpy).toHaveBeenCalled();
    const url = (fetchSpy.mock.calls[0]?.[0] as string) ?? "";
    expect(url).toContain("aviationweather.gov");
  });

  it("source='iem' invokes IEM dispatch", async () => {
    let i = 0;
    vi.spyOn(fetchModule, "fetchLatest").mockImplementation(async () => {
      i += 1;
      return [iemLiveObservation(`2026-05-25T12:0${i}:00Z`)];
    });
    const rows = await collectN(stream("KNYC", { source: "iem" }), 1);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(rows[0]?.source).toBe("iem.live");
  });

  it("dedups by observed_at — repeated obsTime yields once", async () => {
    fetchSpy.mockResolvedValue(jsonResponse([awcMetar(1748174400)]));
    // Use AbortController to cancel — it interrupts the polite-floor sleep
    // promptly so the test doesn't wait for fake timers to drain.
    const controller = new AbortController();
    const agen = stream("KNYC", { signal: controller.signal });
    const yielded: LiveObservation[] = [];
    const consumer = (async () => {
      for await (const row of agen) {
        yielded.push(row);
      }
    })();
    // Advance through several polite-floor cycles. Dedup must suppress every
    // poll past the first since obsTime never changes.
    for (let cycle = 0; cycle < 5; cycle++) {
      await vi.advanceTimersByTimeAsync(POLITE_FLOORS_S.awc * 1000 + 10);
      await Promise.resolve();
    }
    controller.abort();
    // Final timer-tick lets the abortable sleep resolve so the loop's next
    // iteration sees `signal.aborted === true` and the generator returns.
    await vi.advanceTimersByTimeAsync(1);
    await consumer;
    expect(yielded).toHaveLength(1);
  });

  it("yields a new observation when obsTime advances", async () => {
    let i = 0;
    fetchSpy.mockImplementation(async () => {
      i += 1;
      return jsonResponse([awcMetar(1748174400 + 60 * i)]);
    });
    const rows = await collectN(stream("KNYC"), 2);
    expect(rows).toHaveLength(2);
    expect(rows[0]?.observed_at).not.toBe(rows[1]?.observed_at);
    // ISO 8601 Z sorts lex == chrono.
    expect(rows[0]?.observed_at!.localeCompare(rows[1]?.observed_at ?? "") < 0).toBe(true);
  });

  it("unknown source throws BEFORE the first poll", async () => {
    const agen = stream("KNYC", { source: "bogus" as never });
    await expect(agen.next()).rejects.toThrow(/unknown live source/);
  });

  it("default pollSeconds for AWC = floor (30s)", async () => {
    let i = 0;
    fetchSpy.mockImplementation(async () => {
      i += 1;
      return jsonResponse([awcMetar(1748174400 + 60 * i)]);
    });
    const agen = stream("KNYC");
    const first = await agen.next();
    expect(first.done).toBe(false);
    // The sleep is in progress — advance by EXACTLY floor - 1 ms; the next
    // .next() should NOT have completed yet.
    let secondLanded = false;
    const racer = (async () => {
      const r = await agen.next();
      if (!r.done) secondLanded = true;
    })();
    await vi.advanceTimersByTimeAsync(POLITE_FLOORS_S.awc * 1000 - 1);
    await Promise.resolve();
    expect(secondLanded).toBe(false);
    await vi.advanceTimersByTimeAsync(2);
    await racer;
    expect(secondLanded).toBe(true);
    await agen.return(undefined);
  });

  it("default pollSeconds for IEM = floor (60s)", async () => {
    let i = 0;
    vi.spyOn(fetchModule, "fetchLatest").mockImplementation(async () => {
      i += 1;
      return [iemLiveObservation(`2026-05-25T12:0${i}:00Z`)];
    });
    const agen = stream("KNYC", { source: "iem" });
    const first = await agen.next();
    expect(first.done).toBe(false);
    let secondLanded = false;
    const racer = (async () => {
      const r = await agen.next();
      if (!r.done) secondLanded = true;
    })();
    await vi.advanceTimersByTimeAsync(POLITE_FLOORS_S.iem * 1000 - 1);
    await Promise.resolve();
    expect(secondLanded).toBe(false);
    await vi.advanceTimersByTimeAsync(2);
    await racer;
    expect(secondLanded).toBe(true);
    await agen.return(undefined);
  });

  it("pollSeconds below polite floor throws on first .next()", async () => {
    const agen = stream("KNYC", { pollSeconds: 10 });
    await expect(agen.next()).rejects.toThrow(/below polite floor/);
  });

  it("pollSeconds above polite floor works", async () => {
    let i = 0;
    fetchSpy.mockImplementation(async () => {
      i += 1;
      return jsonResponse([awcMetar(1748174400 + 60 * i)]);
    });
    const agen = stream("KNYC", { pollSeconds: 120 });
    const first = await agen.next();
    expect(first.done).toBe(false);
    let secondLanded = false;
    const racer = (async () => {
      const r = await agen.next();
      if (!r.done) secondLanded = true;
    })();
    // Sleep should be 120s, not the default 30s.
    await vi.advanceTimersByTimeAsync(30_000); // 30s — short of cadence
    await Promise.resolve();
    expect(secondLanded).toBe(false);
    await vi.advanceTimersByTimeAsync(90_001); // remaining 90+s
    await racer;
    expect(secondLanded).toBe(true);
    await agen.return(undefined);
  });

  it("empty tick does not abort the stream", async () => {
    let i = 0;
    fetchSpy.mockImplementation(async () => {
      i += 1;
      if (i === 1) return jsonResponse([]);
      return jsonResponse([awcMetar(1748174400 + 60 * i)]);
    });
    const rows = await collectN(stream("KNYC"), 1);
    expect(rows).toHaveLength(1);
    expect(i).toBeGreaterThanOrEqual(2);
  });

  it("cancellation via .return() exits cleanly", async () => {
    fetchSpy.mockResolvedValue(jsonResponse([awcMetar(1748174400)]));
    const agen = stream("KNYC");
    const first = await agen.next();
    expect(first.done).toBe(false);
    // Manual cancellation via .return() (mirrors `break` inside `for await`).
    const ret = await agen.return(undefined);
    expect(ret.done).toBe(true);
  });

  it("AWC stream rows carry source='awc.live'", async () => {
    fetchSpy.mockResolvedValue(jsonResponse([awcMetar(1748174400)]));
    const rows = await collectN(stream("KNYC"), 1);
    expect(rows[0]?.source).toBe("awc.live");
  });

  it("IEM stream rows carry source='iem.live'", async () => {
    let i = 0;
    vi.spyOn(fetchModule, "fetchLatest").mockImplementation(async () => {
      i += 1;
      return [iemLiveObservation(`2026-05-25T12:0${i}:00Z`)];
    });
    const rows = await collectN(stream("KNYC", { source: "iem" }), 1);
    expect(rows[0]?.source).toBe("iem.live");
  });

  it("abort listeners do NOT accumulate across polling cycles", async () => {
    // Regression for the iter-1 codex finding: every polite-floor sleep was
    // adding a fresh `abort` listener via addEventListener({once: true}). The
    // `{once: true}` flag removes the listener only when the event fires —
    // which never happens for the timeout path, so listeners accumulated one
    // per cycle until either abort (or stream close without abort, leaking
    // forever). Node's EventTarget emits MaxListenersExceededWarning at 11.
    let i = 0;
    fetchSpy.mockImplementation(async () => {
      i += 1;
      return jsonResponse([awcMetar(1748174400 + 60 * i)]);
    });
    const controller = new AbortController();
    // Spy on the signal's add/remove counts.
    const addSpy = vi.spyOn(controller.signal, "addEventListener");
    const removeSpy = vi.spyOn(controller.signal, "removeEventListener");

    const agen = stream("KNYC", { signal: controller.signal });
    const yielded: LiveObservation[] = [];
    const consumer = (async () => {
      for await (const row of agen) {
        yielded.push(row);
      }
    })();
    // Cycle through 15 polite-floor windows (well past Node's default
    // MaxListeners=10 threshold). Each cycle does:
    //   poll → yield → sleep(30s) → next iteration
    // Listener count after N cycles must NOT grow without bound; the
    // remove count must roughly track the add count (mod the active listener).
    for (let cycle = 0; cycle < 15; cycle++) {
      await vi.advanceTimersByTimeAsync(POLITE_FLOORS_S.awc * 1000 + 10);
      await Promise.resolve();
    }
    controller.abort();
    await vi.advanceTimersByTimeAsync(1);
    await consumer;

    // Each polite-floor cycle adds exactly one `abort` listener and removes
    // it on timeout. After N cycles, removeCalls === addCalls - 1 (the final
    // listener is still attached when abort fires — `{once: true}` cleans
    // that one up). This is the property the leak fix preserves.
    const addCalls = addSpy.mock.calls.filter((c) => c[0] === "abort").length;
    const removeCalls = removeSpy.mock.calls.filter((c) => c[0] === "abort").length;
    expect(addCalls).toBeGreaterThanOrEqual(10);
    // Allow off-by-one (the active listener at abort time is removed by
    // the `{once: true}` flag, not the explicit removeEventListener call).
    expect(addCalls - removeCalls).toBeLessThanOrEqual(2);
  });
});
