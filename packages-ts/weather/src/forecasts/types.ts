// Phase 17 PLAN-11 — IEM MOS forecast types (mirrors Python schema.forecast.iem_mos.v1).
//
// Python emits snake_case columns; TS uses camelCase per Dual-SDK Rule. The
// per-row shape is conceptually identical; the wire-format boundary handles
// the case conversion.

/** Canonical source enum (matches Python `source` column values). */
export type IemMosSource = "iem.archive" | "iem.live";

/** IEM MOS model enum (matches Python `SUPPORTED_MOS_MODELS`). */
export type IemMosModel = "nbe" | "gfs" | "lav" | "met" | "ecm";

/** One IEM MOS forecast row (Phase 17 PLAN-11). camelCase TS / snake_case Python. */
export interface IemMosRow {
  /** ICAO station code (uppercased). */
  readonly station: string;
  /** UPPERCASE model id (e.g. `"NBE"`). */
  readonly model: string;
  /** Model run datetime — UTC ISO string. */
  readonly issuedAt: string;
  /** Forecast valid datetime — UTC ISO string. */
  readonly validAt: string;
  /** ``(validAt - issuedAt)`` in hours. */
  readonly forecastHour: number;
  /** 2-m temperature in Celsius (null when MOS field is M / missing). */
  readonly tempC: number | null;
  /** 2-m dew point in Celsius. */
  readonly dewPointC: number | null;
  /** 10-m wind speed in m/s. */
  readonly windSpeedMs: number | null;
  /** Wind direction in degrees [0, 360). */
  readonly windDirDeg: number | null;
  /** 12-hour probability of precipitation [0, 1]. */
  readonly precipProbability: number | null;
  /** Sky cover %; IEM MOS does not expose this — always null. */
  readonly skyCoverPct: number | null;
  /** Per-row source identity. Always `"iem.archive"` for now. */
  readonly source: IemMosSource;
  /** When the row was fetched — UTC ISO string. */
  readonly retrievedAt: string;
}

/** Optional knobs for {@link iemMosForecasts}. */
export interface IemMosOptions {
  /** Default `"nbe"`. */
  readonly model?: IemMosModel;
  /** Override the fetch function (used by tests). */
  readonly fetchFn?: typeof fetch;
}
