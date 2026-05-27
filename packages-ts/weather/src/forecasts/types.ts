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

// ---------------------------------------------------------------------------
// Phase 20 OM-07 + OM-08: Open-Meteo forecast types
// ---------------------------------------------------------------------------

/** Open-Meteo source-identity enum (per-endpoint discrimination). */
export type OpenMeteoSource =
  | "open_meteo.previous_runs"
  | "open_meteo.single_run"
  | "open_meteo.live"
  | "open_meteo.seamless";

/** Open-Meteo dispatch mode for {@link openMeteoForecasts}. */
export type OpenMeteoMode = "training" | "live" | "seamless";

/** The 36 Open-Meteo forecast models in scope (Phase 20 D-02). */
export type OpenMeteoModel =
  // NCEP (8)
  | "gfs_seamless"
  | "gfs_global"
  | "gfs_graphcast025"
  | "aigfs025"
  | "hgefs025"
  | "ncep_hrrr_conus"
  | "ncep_nbm_conus"
  | "ncep_nam_conus"
  // ECMWF (3)
  | "ecmwf_ifs025"
  | "ecmwf_ifs_hres"
  | "ecmwf_aifs025_single"
  // DWD (5)
  | "dwd_icon_seamless"
  | "dwd_icon_global"
  | "dwd_icon_eu"
  | "dwd_icon_d2"
  | "dwd_icon_d2_15min"
  // Météo-France (6)
  | "meteofrance_seamless"
  | "meteofrance_arpege_world025"
  | "meteofrance_arpege_europe"
  | "meteofrance_arome_france0025"
  | "meteofrance_arome_france_hd"
  | "meteofrance_arome_france_hd_15min"
  // Asia + Oceania (8)
  | "jma_seamless"
  | "jma_gsm"
  | "jma_msm"
  | "kma_seamless"
  | "kma_gdps"
  | "kma_ldps"
  | "cma_grapes_global"
  | "bom_access_global"
  // Europe (3)
  | "ukmo_global_deterministic_10km"
  | "ukmo_uk_deterministic_2km"
  | "metno_nordic_pp"
  // GEM Canada (3)
  | "cmc_gem_gdps"
  | "cmc_gem_rdps"
  | "cmc_gem_hrdps";

/** Optional knobs for {@link openMeteoForecasts}. */
export interface OpenMeteoOptions {
  /** Default `"gfs_global"`. */
  readonly model?: OpenMeteoModel;
  /** Default `"training"`. */
  readonly mode?: OpenMeteoMode;
  /** Optional ISO cycle for Single Runs API dispatch. */
  readonly issuedAt?: string;
  /** Required `true` to invoke `mode: "seamless"`. */
  readonly allowLeakage?: boolean;
  /** Override the fetch function (used by tests). */
  readonly fetchFn?: typeof fetch;
}

/** One Open-Meteo forecast row (Phase 20 schema.forecast.station.v1). */
export interface OpenMeteoRow {
  readonly station: string;
  /** Open-Meteo model key (lowercase, e.g. `"gfs_global"`). */
  readonly model: string;
  /**
   * Model run datetime — UTC ISO string. May be `null` for
   * `source="open_meteo.seamless"` rows (cycle unrecoverable by design).
   */
  readonly issuedAt: string | null;
  readonly validAt: string;
  /** `(validAt - issuedAt)` in hours. `null` when `issuedAt` is null. */
  readonly forecastHour: number | null;
  readonly tempC: number | null;
  readonly dewPointC: number | null;
  readonly apparentTempC: number | null;
  readonly windSpeedMs: number | null;
  readonly windDirDeg: number | null;
  readonly windGustsMs: number | null;
  readonly precipProbability: number | null;
  readonly precipitationMm: number | null;
  readonly cloudCoverPct: number | null;
  readonly surfacePressureHpa: number | null;
  readonly pressureMslHpa: number | null;
  readonly shortwaveRadiationWm2: number | null;
  readonly directRadiationWm2: number | null;
  readonly capeJkg: number | null;
  readonly freezingLevelM: number | null;
  readonly snowDepthM: number | null;
  readonly visibilityM: number | null;
  readonly weatherCode: number | null;
  readonly source: OpenMeteoSource;
  readonly retrievedAt: string;
}
