// @tradewinds/weather — weather fetchers + parsers.
//
// TS-W1 Wave 3 lands AWC live-METAR support. Subsequent waves add IEM CLI
// (Wave 4), IEM ASOS + GHCNh (TS-W2), and the disk cache (TS-W3).

export const version = "0.0.0";

export function helloWeather(): string {
  return "hello @tradewinds/weather";
}

// TS-W1 Wave 3 — AWC live METARs.
export {
  AWC_MAX_HOURS,
  AWC_METAR_URL,
  fetchAwcMetars,
  type AwcMetarRaw,
  type FetchAwcOptions,
} from "./_fetchers/awc.js";
export {
  awcToObservation,
  icaoToStationCode,
  mapCloudCover,
  parseAwcVisibility,
  type Observation,
} from "./_parsers/awc.js";
