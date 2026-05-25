// TS-W3 Plan 06 Task 2 — 5-case skip behavior replay through research().
//
// Consumes the same fixture as plan 03's skip-rules.test.ts so the cache
// primitives + the orchestrator's wiring are both exercised by the same
// canonical scenarios.
//
// Iter-1 H4: the previous version swallowed every error with a bare
// try/catch and only asserted 1 of 3 fixture properties (skipLive). The
// rewrite below:
//
//   - lets errors propagate (research() MUST complete; mocks return
//     empty bodies so the orchestrator finishes happily)
//   - asserts the `skipCurrentMonth` flag against the orchestrator's
//     year-keyed observation/climate cache. When the flag is true, NO
//     `cache.set` call may carry the case's year. When false, at least
//     one `cache.set` MUST carry it (proving the cache actually writes).
//   - keeps the `skipLive` assertion (no `.live`-suffixed key written)
//
// Iter-5 H9: the 30-day volatile-window rule is NOW wired into
// research.ts at the year-chunk level (archive-as-of = `${year}-12-31`).
// Assertion 2 below combines BOTH gates — `wroteYear` is expected iff
// neither `skipCurrentMonth` NOR `skipVolatile` fires. The fixture's
// case-2 + case-3 `now` were bumped to 2025-02-15 to push year=2024
// chunks past the volatile window, so the existing
// `skipCurrentMonth=false → wroteYear=true` semantics still hold for
// those cases. Case-4 keeps `now=2025-01-15` to exercise the new
// volatile-skip path (year=2024 is 15 days past year-end, inside the
// 30-day amendment window). A separate Assertion 3 walks every
// cache.set value and confirms no row inside the 30-day window leaked
// into the cache.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  MemoryStore,
  cacheKeyForObservations,
  isLiveSource,
} from "@mostlyrightmd/core/internal/cache";
import { research } from "../src/research.js";

import fixtureData from "../../core/tests/internal/cache/fixtures/skip-rules-behavior.json" with {
  type: "json",
};

function installMinimalFetchMock() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
    if (url.includes("aviationweather.gov"))
      return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
    if (url.includes("mesonet.agron.iastate.edu/json/cli.py"))
      return new Response(JSON.stringify({ results: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py"))
      return new Response("station,valid\n", {
        status: 200,
        headers: { "content-type": "text/plain" },
      });
    if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network"))
      return new Response("", { status: 404 });
    throw new Error(`Unexpected fetch URL: ${url}`);
  });
}

/** All cache.set keys (string-coerced) seen across the test. */
function setKeys(setSpy: { mock: { calls: ReadonlyArray<ReadonlyArray<unknown>> } }): string[] {
  return setSpy.mock.calls.map((call) => String(call[0]));
}

/**
 * All cache.set value arguments seen across the test.
 *
 * Iter-2 H7: the previous `skipLive` assertion grepped cache *keys* for
 * `.live`, but `cacheKeyForObservations` emits
 * `mostlyright:v1:observations:STATION:YYYY:MM` (and the climate key has
 * the same shape) — there is no `.live` token in any key the orchestrator
 * writes. The check passed vacuously, so a regression that wrote
 * AWC live-source rows to the cache would still pass. The fix is to
 * inspect the cache *value* (rows): when `skipLive=true`, no row in any
 * cache.set value may have a `source` matching `isLiveSource(source)`.
 */
function setValues(setSpy: {
  mock: { calls: ReadonlyArray<ReadonlyArray<unknown>> };
}): unknown[] {
  return setSpy.mock.calls.map((call) => call[1]);
}

describe("research() — 5-case skip behavior replay (TS-W3 SC#2)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // iter-6 H12: case-5-rjtt-utc-plus-9-year-wrap is no longer deferred.
  // RJTT was added to `_STATION_TZ` in snapshot.ts (entry: `Asia/Tokyo`),
  // closing the parity gap that previously caused `_resolveStationTz` to
  // throw on the international ICAO. All 5 fixture cases now run with
  // real assertions; the LST year-boundary path (UTC+9 wrapping back to
  // 2025-12-31 LST as 2026-01-01 local) is fully exercised here.
  //
  // Broader intl-station tz coverage (EGLL, YSSY, NZAA, SBGR, ...) is
  // tracked as TS-W6 — we add only what case-5 requires, matching the
  // H12 hint to close the gap cleanly without an exhaustive port.
  for (const c of fixtureData.cases) {
    it(`${c.id}: skipCurrentMonth=${c.expected.skipCurrentMonth} skipLive=${c.expected.skipLive}`, async () => {
      installMinimalFetchMock();
      const store = new MemoryStore();
      const sentinel = [
        {
          __sentinel: c.id,
          source: "iem",
          observation_date: `${c.year}-${String(c.month).padStart(2, "0")}-01`,
        },
      ];
      const key = cacheKeyForObservations(c.station, c.year, c.month);
      await store.set(key, sentinel);
      const setSpy = vi.spyOn(store, "set");

      const fromDate = `${c.year}-${String(c.month).padStart(2, "0")}-01`;
      const toDate = `${c.year}-${String(c.month).padStart(2, "0")}-15`;
      // H4: NO try/catch — research() must complete. If a fixture
      // station ever drops out of the registry or a fetcher mock
      // regresses, the test fails loudly rather than masking it.
      await research(c.station, fromDate, toDate, {
        cache: store,
        now: new Date(c.now),
      });

      const keysWritten = setKeys(setSpy);
      const valuesWritten = setValues(setSpy);

      // --- Assertion 1: skipLive — no cache.set value may contain
      // a row whose `source` is a live source (per `isLiveSource`).
      //
      // Iter-2 H7: the previous version asserted on cache *keys*
      // (`k.includes(".live")`) which was vacuous — cacheKey
      // generators never emit `.live` in any key. Now we walk every
      // cache.set value (an array of rows) and check each row's
      // `source` against the canonical `isLiveSource` predicate
      // (the same predicate research.ts uses to gate the write).
      // Any AWC-live row leaking into the cache fails the test.
      if (c.expected.skipLive) {
        for (let idx = 0; idx < valuesWritten.length; idx++) {
          const val = valuesWritten[idx];
          if (!Array.isArray(val)) continue;
          for (let rowIdx = 0; rowIdx < val.length; rowIdx++) {
            const row = val[rowIdx];
            const src =
              row !== null && typeof row === "object"
                ? (row as { source?: unknown }).source
                : undefined;
            if (typeof src !== "string") continue;
            expect(
              isLiveSource(src),
              `skipLive=true: cache.set call #${idx} (key=${JSON.stringify(keysWritten[idx])}) row #${rowIdx} has live source=${JSON.stringify(src)} — the orchestrator must never persist .live-suffixed rows`,
            ).toBe(false);
          }
        }
      }

      // --- Assertion 2: skipCurrentMonth + skipVolatile compose to
      // determine whether the year-keyed cache was written.
      // The orchestrator uses BOTH `shouldSkipCacheForCurrentLstYear`
      // AND `isWithinVolatileWindow` (iter-5 H9) — `wroteYear` is
      // expected iff neither gate fires. All caching is year-granular,
      // so we check whether any cache.set call includes `:${c.year}:`
      // (the colon-delimited year segment in both
      // cacheKeyForObservations and cacheKeyForClimate).
      const yearMarker = `:${c.year}:`;
      const yearMarkerSuffix = `:${c.year}`; // climate key has no trailing month
      const wroteYear = keysWritten.some(
        (k) =>
          k.includes(yearMarker) ||
          k.endsWith(yearMarkerSuffix) ||
          k.includes(`${yearMarkerSuffix}:`),
      );
      const expectedWroteYear = !c.expected.skipCurrentMonth && !c.expected.skipVolatile;
      expect(
        wroteYear,
        `expected wroteYear=${expectedWroteYear} (skipCurrentMonth=${c.expected.skipCurrentMonth}, skipVolatile=${c.expected.skipVolatile}) but got ${wroteYear}; keys=${JSON.stringify(keysWritten)}`,
      ).toBe(expectedWroteYear);

      // --- Assertion 3: skipVolatile — no row inside the 30-day
      // amendment window relative to `c.now` may leak into any
      // cache.set value (iter-5 H9). When the orchestrator decides
      // a year-chunk is volatile it skips the write entirely, so
      // this assertion is vacuously satisfied for the chunk-gated
      // path. The check is still kept because:
      //   1. It guards against a future "partial-chunk caching"
      //      regression that writes some rows even when the chunk
      //      end is volatile.
      //   2. It documents the row-level invariant the predicate
      //      enforces — useful when extending to per-row gating.
      // For rows lacking `observation_date` (Observation shape uses
      // `observed_at` ISO datetime) we extract the YYYY-MM-DD prefix.
      const nowIso = c.now.slice(0, 10);
      for (let idx = 0; idx < valuesWritten.length; idx++) {
        const val = valuesWritten[idx];
        if (!Array.isArray(val)) continue;
        for (let rowIdx = 0; rowIdx < val.length; rowIdx++) {
          const row = val[rowIdx];
          if (row === null || typeof row !== "object") continue;
          const rec = row as { observed_at?: unknown; observation_date?: unknown };
          const rawDate =
            typeof rec.observation_date === "string"
              ? rec.observation_date
              : typeof rec.observed_at === "string"
                ? rec.observed_at.slice(0, 10)
                : null;
          if (rawDate === null) continue;
          // Re-run the predicate with the same `days=30` the orchestrator
          // uses; nowIso plays the archiveAsOf role.
          const inWindow = (() => {
            const e = Date.parse(`${rawDate}T00:00:00Z`);
            const a = Date.parse(`${nowIso}T00:00:00Z`);
            if (!Number.isFinite(e) || !Number.isFinite(a)) return false;
            const deltaDays = (a - e) / 86_400_000;
            return deltaDays >= 0 && deltaDays <= 30;
          })();
          expect(
            inWindow,
            `cache.set call #${idx} (key=${JSON.stringify(keysWritten[idx])}) row #${rowIdx} carries date=${JSON.stringify(rawDate)} inside the 30-day volatile window relative to now=${nowIso} — orchestrator must skip writes for chunks whose data falls in [now-30d, now]`,
          ).toBe(false);
        }
      }
    });
  }
});

// Iter-10 H21: the fixture-driven `skipLive` assertion above is vacuous in
// every case because every fixture uses a stale 2024 date window relative
// to its `now`. `anyDateOverlapsAwc(toDate, hours=168, now)` short-circuits
// — AWC fetch never runs — and the minimal fetch mock above returns `[]`
// for AWC anyway. The only rows in any cache.set call come from the test's
// pre-loaded IEM-source sentinel (`source: "iem"`), so `isLiveSource(...)`
// is trivially false for everything inspected. A regression that wrote
// `.live`-sourced rows to the cache would NOT be caught.
//
// This complementary test (H21 fix) constructs a FRESH window:
//   - `now` is 2025-01-15
//   - The date range straddles 2024-06-01 → 2025-01-14, so:
//       (a) AWC's 7-day window (168h before `now`) overlaps `toDate`, so
//           `anyDateOverlapsAwc` returns true and the AWC fetch path
//           ACTUALLY executes — exercising the real live-rows-flowing-
//           through-the-orchestrator codepath.
//       (b) IEM ASOS months for June–December 2024 are neither the
//           current LST month nor volatile (>30 days past `now`), so
//           the cache.set guard at research.ts:549-556 is NOT
//           short-circuited — `cache.set` actually fires.
//   - The AWC mock returns valid METAR JSON (so AWC rows enter the
//     merge pipeline; they're parsed with `source: "awc"` per
//     `awcToObservation`).
//
// With cache.set ACTUALLY firing, the `isLiveSource` invariant is checked
// against real cache writes. The assertion is non-vacuous: a regression
// that started tagging cached rows with a `.live`-suffixed source (e.g.,
// a future catalog-layer stamping refactor) would surface here.
//
// We additionally pre-load the cache with a synthetic `.live`-sourced
// sentinel row and verify the orchestrator never re-emits it as part of a
// subsequent cache.set value. This guards against "the cache.get path
// echoes its read value back into cache.set" — a regression that would
// permit `.live` rows to persist across runs.
describe("research() — fresh-window skipLive regression (iter-10 H21)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fresh window with AWC overlap: no cache.set value contains any .live-sourced row", async () => {
    // Configure the fetch mock to return real-ish data so the orchestrator
    // exercises live + archive paths.
    //
    // - AWC mock: one METAR ~2h before `now` (well inside the 168h window).
    //   The AWC parser tags it `source: "awc"` (NOT `.live` — TS today
    //   never produces `.live`-suffixed row sources; the suffix is a
    //   catalog-layer source-id). The assertion still walks every row to
    //   guard against a future regression that introduces `.live`-tagged
    //   row emission.
    // - CLI mock: one record per queried year so cache.set fires for CLI.
    // - IEM ASOS mock: an empty CSV header (no parsed rows; cache write
    //   skipped because monthRows is empty — but the orchestrator still
    //   touches the gate, so any regression in the gate's truthiness
    //   surfaces). The point is to verify the CLI + observation gates.
    const now = new Date("2025-01-15T12:00:00Z");
    const awcObsTimeSec = Math.floor(now.getTime() / 1000) - 2 * 3600;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : ((input as Request).url ?? String(input));
      if (url.includes("aviationweather.gov")) {
        // AWC METAR with all required fields; AWC parser will emit
        // `source: "awc"` (NOT `.live`).
        const metar = [
          {
            icaoId: "KNYC",
            reportTime: "2025-01-15T10:00:00Z",
            obsTime: awcObsTimeSec,
            temp: 5.0,
            dewp: -1.0,
            wspd: 8,
            wdir: 270,
            rawOb: "KNYC 151000Z 27008KT 10SM CLR 05/M01 A3010",
          },
        ];
        return new Response(JSON.stringify(metar), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("mesonet.agron.iastate.edu/json/cli.py")) {
        return new Response(
          JSON.stringify({
            results: [
              { valid: "2024-06-15", high: 80, low: 60, product: "test-cli" },
              { valid: "2024-12-15", high: 35, low: 20, product: "test-cli" },
            ],
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (url.includes("mesonet.agron.iastate.edu/cgi-bin/request/asos.py")) {
        return new Response("station,valid\n", {
          status: 200,
          headers: { "content-type": "text/plain" },
        });
      }
      if (url.includes("ncei.noaa.gov/oa/global-historical-climatology-network")) {
        return new Response("", { status: 404 });
      }
      throw new Error(`Unexpected fetch URL: ${url}`);
    });

    const store = new MemoryStore();

    // Pre-load the cache with a synthetic `.live`-tagged sentinel under a
    // key the orchestrator won't read (a deliberate "poison" entry). If
    // any future regression caused the orchestrator to read this entry
    // and re-emit its rows on cache.set, the post-call walk catches it.
    const poisonKey = cacheKeyForObservations("KNYC", 2024, 6, "awc-poisoned");
    await store.set(poisonKey, [
      { source: "awc.live", observed_at: "2024-06-15T12:00:00Z", station_code: "NYC" },
    ]);

    const setSpy = vi.spyOn(store, "set");

    // Fresh window: AWC overlaps `now`; IEM months June-Dec 2024 are
    // non-volatile (>30 days past now=2025-01-15) and non-current-LST,
    // so cache.set fires for at least the CLI path (which writes one
    // entry per year — for 2024 and 2025 the queried range spans both).
    await research("NYC", "2024-06-01", "2025-01-14", {
      cache: store,
      now,
    });

    const valuesWritten = setValues(setSpy);
    const keysWritten = setKeys(setSpy);

    // The fresh window means cache.set MUST have fired at least once
    // (else the test would be vacuous like the fixture-loop assertion).
    // If this assertion ever flips to 0, the orchestrator's cache wiring
    // regressed and the entire H21 test is moot — fail loudly.
    expect(
      valuesWritten.length,
      `expected at least one cache.set call in the fresh window scenario; got ${valuesWritten.length}. If the orchestrator's cache writes were short-circuited, this assertion is the canary — investigate before treating H21 as covered.`,
    ).toBeGreaterThan(0);

    // The actual H21 invariant: no cache.set value may contain any row
    // whose `source` ends with `.live`. Walk every value (rows array)
    // and every row inside.
    for (let idx = 0; idx < valuesWritten.length; idx++) {
      const val = valuesWritten[idx];
      if (!Array.isArray(val)) continue;
      for (let rowIdx = 0; rowIdx < val.length; rowIdx++) {
        const row = val[rowIdx];
        const src =
          row !== null && typeof row === "object"
            ? (row as { source?: unknown }).source
            : undefined;
        if (typeof src !== "string") continue;
        expect(
          isLiveSource(src),
          `cache.set call #${idx} (key=${JSON.stringify(keysWritten[idx])}) row #${rowIdx} has live source=${JSON.stringify(src)} — the orchestrator must never persist .live-suffixed rows even in the fresh-window path`,
        ).toBe(false);
      }
    }

    // Defense-in-depth: prove the predicate semantics that the assertion
    // relies on. If isLiveSource ever regressed to return `false` for
    // a `.live` string, the loop above would pass vacuously regardless
    // of orchestrator behavior. These two expectations pin the predicate.
    expect(isLiveSource("awc.live")).toBe(true);
    expect(isLiveSource("iem.live")).toBe(true);
    expect(isLiveSource("ghcnh.live")).toBe(true);
    expect(isLiveSource("awc")).toBe(false);
    expect(isLiveSource("iem")).toBe(false);
    expect(isLiveSource("ghcnh")).toBe(false);
    expect(isLiveSource("iem.archive")).toBe(false);
  });
});
