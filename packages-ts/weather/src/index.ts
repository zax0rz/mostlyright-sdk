// @tradewinds/weather — placeholder scaffold for TS-W0 Wave 1.
// Real implementation (AWC, IEM ASOS, IEM CLI, GHCNh fetchers + parsers + cache) lands in TS-W1+.

export const version = "0.0.0";

export function helloWeather(): string {
  return "hello @tradewinds/weather";
}

// TS-W1 Wave 3: AWC METAR fetcher + parser.
export {
  fetchAwcMetars,
  AWC_METAR_URL,
  AWC_MAX_HOURS,
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

// TS-W1 Wave 4: IEM CLI fetcher + range + parser.
export {
  downloadCli,
  downloadCliRange,
  IEM_CLI_BASE_URL,
  IEM_CLI_POLITE_DELAY_MS,
  type CliRawRecord,
  type DownloadCliRangeOptions,
} from "./_fetchers/iem-cli.js";
export {
  parseCliRecord,
  parseCliResponse,
  inferReportType,
  HIGH_TEMP_MAX_F,
  HIGH_TEMP_MIN_F,
  LOW_TEMP_MAX_F,
  LOW_TEMP_MIN_F,
  type ClimateObservation,
  type ReportType,
} from "./_parsers/cli.js";
