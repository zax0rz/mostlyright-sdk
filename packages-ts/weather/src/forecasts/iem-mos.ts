// Phase 17 PLAN-11 — IEM MOS TS fetcher.
//
// Mirrors Python `packages/weather/src/mostlyright/weather/_fetchers/_iem_mos.py`.
// Endpoint: https://mesonet.agron.iastate.edu/api/1/mos.json
// CORS: OPEN per IEM ASOS posture (see `.planning/research/FORECAST-CORS-MATRIX.md`).

import type { IemMosModel, IemMosOptions, IemMosRow, IemMosSource } from "./types.js";

const IEM_MOS_URL = "https://mesonet.agron.iastate.edu/api/1/mos.json";

const SUPPORTED_MODELS: ReadonlySet<IemMosModel> = new Set(["nbe", "gfs", "lav", "met", "ecm"]);

const KT_TO_MS = 0.5144444;

const NBE_CYCLE_CUTOVER = Date.UTC(2026, 5 - 1, 5, 0, 0, 0); // 2026-05-05T00:00:00Z

/**
 * Max number of MOS runtime-cycle requests in flight at once (GH #58).
 *
 * The fan-out is bounded rather than unbounded: a `Promise.all` over the full
 * day × runtime-hour grid would launch ~1,460 simultaneous requests for a
 * year-scale window, risking client connection limits, memory pressure, and
 * IEM-side rate limiting. A cap of 8 keeps essentially all of the small-window
 * speedup (typical ±1–3 day windows have ≤ 12 cycles) while staying polite for
 * large historical ranges.
 */
export const MOS_FETCH_CONCURRENCY = 8;

/**
 * Map `items` through `fn` with at most `limit` invocations in flight at once,
 * returning results in input order (NOT resolution order). Bounded-concurrency
 * replacement for `Promise.all(items.map(fn))` — preserves the byte-identical
 * ordering the serial path produced while capping peak fan-out.
 */
async function mapWithConcurrency<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let cursor = 0;
  async function worker(): Promise<void> {
    while (cursor < items.length) {
      const index = cursor++;
      results[index] = await fn(items[index] as T, index);
    }
  }
  const poolSize = Math.min(limit, items.length);
  await Promise.all(Array.from({ length: poolSize }, () => worker()));
  return results;
}

/** Pick the right NBE runtime-hour set based on the requested range. */
function runtimeHoursFor(model: IemMosModel, fromDt: Date, toDt: Date): readonly number[] {
  if (model !== "nbe") return [0, 6, 12, 18];
  const fromMs = fromDt.getTime();
  const toMs = toDt.getTime();
  const pre = fromMs < NBE_CYCLE_CUTOVER;
  const post = toMs >= NBE_CYCLE_CUTOVER;
  if (pre && post) return [0, 1, 6, 7, 12, 13, 18, 19];
  if (pre) return [1, 7, 13, 19];
  return [0, 6, 12, 18];
}

function fahrenheitToCelsius(f: number | null): number | null {
  if (f === null || Number.isNaN(f)) return null;
  return ((f - 32) * 5) / 9;
}

function knotsToMs(kt: number | null): number | null {
  if (kt === null || Number.isNaN(kt)) return null;
  return kt * KT_TO_MS;
}

function percentToUnit(pct: number | null): number | null {
  if (pct === null || Number.isNaN(pct)) return null;
  return pct / 100;
}

function maybeNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "M" || value === "") {
    return null;
  }
  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return null;
  return num;
}

function parseDate(value: unknown): Date | null {
  if (typeof value !== "string" || !value) return null;
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return null;
  return dt;
}

interface RawMosRow {
  readonly runtime?: string;
  readonly model_runtime?: string;
  readonly ftime?: string;
  readonly valid_time?: string;
  readonly tmp?: number | string | null;
  readonly dpt?: number | string | null;
  readonly wsp?: number | string | null;
  readonly wdr?: number | string | null;
  readonly pop12?: number | string | null;
}

function parseRow(
  raw: RawMosRow,
  station: string,
  model: IemMosModel,
  retrievedAt: string,
): IemMosRow | null {
  const issuedDt = parseDate(raw.runtime ?? raw.model_runtime);
  const validDt = parseDate(raw.ftime ?? raw.valid_time);
  if (issuedDt === null || validDt === null) return null;
  const forecastHour = Math.round((validDt.getTime() - issuedDt.getTime()) / 3_600_000);
  return {
    station,
    model: model.toUpperCase(),
    issuedAt: issuedDt.toISOString(),
    validAt: validDt.toISOString(),
    forecastHour,
    tempC: fahrenheitToCelsius(maybeNumber(raw.tmp)),
    dewPointC: fahrenheitToCelsius(maybeNumber(raw.dpt)),
    windSpeedMs: knotsToMs(maybeNumber(raw.wsp)),
    windDirDeg: (() => {
      const d = maybeNumber(raw.wdr);
      return d === null ? null : Math.round(d);
    })(),
    precipProbability: percentToUnit(maybeNumber(raw.pop12)),
    skyCoverPct: null,
    source: "iem.archive" as IemMosSource,
    retrievedAt,
  };
}

/** Parse ISO `YYYY-MM-DD` to a UTC `Date` at 00:00:00. */
function parseIsoDate(iso: string, endOfDay: boolean): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (match === null) {
    throw new Error(`iemMosForecasts: from/to dates must be ISO YYYY-MM-DD; got ${iso}`);
  }
  const [, y, m, d] = match;
  if (endOfDay) {
    return new Date(Date.UTC(Number(y), Number(m) - 1, Number(d), 23, 59, 59));
  }
  return new Date(Date.UTC(Number(y), Number(m) - 1, Number(d)));
}

/**
 * Fetch IEM MOS forecasts for `station` in `[fromDate, toDate]`.
 *
 * Mirrors Python `fetch_iem_mos(...)`. Iterates the model's runtime-hour
 * grid (NBE moved from {01,07,13,19}Z to {00,06,12,18}Z on 2026-05-05;
 * other models use {00,06,12,18}Z), GETs the JSON endpoint, and projects
 * rows to {@link IemMosRow}.
 *
 * 404 responses are silently skipped (many runtimes have no MOS data).
 * Empty input range returns `[]`.
 *
 * @throws `Error` if `model` is not in `SUPPORTED_MODELS`.
 */
export async function iemMosForecasts(
  station: string,
  fromDate: string,
  toDate: string,
  opts: IemMosOptions = {},
): Promise<IemMosRow[]> {
  const model = opts.model ?? "nbe";
  if (!SUPPORTED_MODELS.has(model)) {
    throw new Error(
      `iemMosForecasts: model must be one of ${[...SUPPORTED_MODELS].sort().join(",")}; got ${model}`,
    );
  }
  const fetchFn = opts.fetchFn ?? fetch;
  const fromDt = parseIsoDate(fromDate, false);
  const toDt = parseIsoDate(toDate, true);
  const hours = runtimeHoursFor(model, fromDt, toDt);
  const retrievedAt = new Date().toISOString();

  // GH #58: collect every (day × runtime-hour) URL first, then fan out
  // concurrently with a bounded pool. The cycles are independent (nothing in
  // one depends on another's response), so the previous serial-await loop
  // was paying N round-trips of ~620–760 ms each (~3.2 s for 12 cycles).
  // Bounded fan-out (MOS_FETCH_CONCURRENCY) collapses the wall-clock to
  // ~ceil(N/limit) round-trips on typical short windows while staying polite
  // on large historical ranges (an unbounded Promise.all over a year-scale
  // window would launch ~1,460 simultaneous requests — codex review P2).
  // Row ordering is preserved by keeping the URL list in day-then-hour order
  // and indexing results by position — byte-identical output to the serial path.
  const dayMs = 86_400_000;
  const urls: string[] = [];
  for (let day = fromDt.getTime(); day <= toDt.getTime(); day += dayMs) {
    for (const h of hours) {
      const rt = new Date(day);
      rt.setUTCHours(h, 0, 0, 0);
      if (rt < fromDt || rt > toDt) continue;
      // IEM /api/1/mos.json regex ^(AVN|GFS|...|NBE|...)$ is uppercase-only;
      // sending lowercase returns HTTP 422 (issue #17). Mirrors the upper()
      // applied to `model` on returned rows above and the Python fix at
      // _iem_mos.py:239.
      urls.push(
        `${IEM_MOS_URL}?station=${encodeURIComponent(
          station,
        )}&model=${encodeURIComponent(model.toUpperCase())}&runtime=${encodeURIComponent(
          rt.toISOString(),
        )}`,
      );
    }
  }

  // Run the FULL per-cycle lifecycle (fetch → status check → body read → row
  // projection) inside the bounded pool, NOT just the header fetch. `fetch()`
  // resolves once headers arrive, so bounding only the fetch promise would
  // still leave unbounded response bodies open and defer error handling until
  // every URL had been requested (codex review iter-2 P2). Returning per-cycle
  // row arrays and flattening in input order keeps byte-identical output.
  const perCycle = await mapWithConcurrency(urls, MOS_FETCH_CONCURRENCY, async (url) => {
    const resp = (await fetchFn(url)) as Response;
    if (resp.status === 404) return [] as IemMosRow[];
    if (!resp.ok) {
      throw new Error(`iemMosForecasts: HTTP ${resp.status} on ${url}`);
    }
    const payload = (await resp.json()) as { data?: RawMosRow[] };
    const out: IemMosRow[] = [];
    for (const raw of payload.data ?? []) {
      const projected = parseRow(raw, station, model, retrievedAt);
      if (projected !== null) out.push(projected);
    }
    return out;
  });
  return perCycle.flat();
}

export const __internal__ = {
  runtimeHoursFor,
  parseRow,
  NBE_CYCLE_CUTOVER,
};
