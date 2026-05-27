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

  const rows: IemMosRow[] = [];
  const dayMs = 86_400_000;
  for (let day = fromDt.getTime(); day <= toDt.getTime(); day += dayMs) {
    for (const h of hours) {
      const rt = new Date(day);
      rt.setUTCHours(h, 0, 0, 0);
      if (rt < fromDt || rt > toDt) continue;
      // IEM /api/1/mos.json regex ^(AVN|GFS|...|NBE|...)$ is uppercase-only;
      // sending lowercase returns HTTP 422 (issue #17). Mirrors the upper()
      // applied to `model` on returned rows above and the Python fix at
      // _iem_mos.py:239.
      const url = `${IEM_MOS_URL}?station=${encodeURIComponent(
        station,
      )}&model=${encodeURIComponent(model.toUpperCase())}&runtime=${encodeURIComponent(
        rt.toISOString(),
      )}`;
      const resp = await fetchFn(url);
      if (resp.status === 404) continue;
      if (!resp.ok) {
        throw new Error(`iemMosForecasts: HTTP ${resp.status} on ${url}`);
      }
      const payload = (await resp.json()) as { data?: RawMosRow[] };
      for (const raw of payload.data ?? []) {
        const projected = parseRow(raw, station, model, retrievedAt);
        if (projected !== null) rows.push(projected);
      }
    }
  }
  return rows;
}

export const __internal__ = {
  runtimeHoursFor,
  parseRow,
  NBE_CYCLE_CUTOVER,
};
