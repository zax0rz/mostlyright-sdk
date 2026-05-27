// Phase 17 PLAN-11 — `@mostlyrightmd/weather/forecasts` subpath barrel.

export type {
  IemMosModel,
  IemMosOptions,
  IemMosRow,
  IemMosSource,
  OpenMeteoMode,
  OpenMeteoModel,
  OpenMeteoOptions,
  OpenMeteoRow,
  OpenMeteoSource,
} from "./types.js";

export { iemMosForecasts } from "./iem-mos.js";

export {
  forecastNwp,
  type ForecastNwpOptions,
  type NwpModel,
} from "./nwp-stub.js";

// Phase 20 OM-07 + OM-08
export {
  openMeteoForecasts,
  OPEN_METEO_PREVIOUS_RUNS_URL,
  OPEN_METEO_SINGLE_RUNS_URL,
  OPEN_METEO_LIVE_URL,
  OPEN_METEO_SEAMLESS_URL,
} from "./open-meteo.js";

export {
  CYCLE_HOURS as OPEN_METEO_CYCLE_HOURS,
  OPEN_METEO_MODELS,
  PUBLISH_LAG_HOURS as OPEN_METEO_PUBLISH_LAG_HOURS,
  floorToCycleMs,
  issuedAtFromLiveCycleMathMs,
  issuedAtFromPreviousDayMs,
} from "./open-meteo-models.js";
