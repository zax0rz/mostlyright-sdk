// @mostlyright/weather — weather fetchers + parsers.
//
// TS-W1 ships AWC (Wave 3) + IEM CLI (Wave 4). TS-W2 Plan 01 adds IEM ASOS
// (yearly-chunk historical METARs) + the IEM CSV parser. Subsequent TS-W2
// plans add GHCNh + mergeObservations; TS-W3 adds the disk cache.

export const version = "0.0.0";

export function helloWeather(): string {
  return "hello @mostlyright/weather";
}

// TS-W1 Wave 3 — AWC live METARs.
export {
  AWC_MAX_HOURS,
  AWC_METAR_URL,
  fetchAwcMetars,
  type AwcMetarRaw,
  type FetchAwcOptions,
} from "./_fetchers/awc.js";
// Shared row contract: `Observation.source` widened in TS-W2 Plan 01 to
// `"awc" | "iem" | "ghcnh"`. Each parser still emits its own literal.
export {
  awcToObservation,
  icaoToStationCode,
  mapCloudCover,
  parseAwcVisibility,
  type Observation,
} from "./_parsers/awc.js";

// TS-W1 Wave 4 — IEM CLI fetcher + range + parser.
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
  mergeClimate,
  inferReportType,
  HIGH_TEMP_MAX_F,
  HIGH_TEMP_MIN_F,
  LOW_TEMP_MAX_F,
  LOW_TEMP_MIN_F,
  type ClimateObservation,
  type ReportType,
} from "./_parsers/cli.js";

// TS-W2 Plan 01 — IEM ASOS yearly-chunk fetcher + chunker + CSV parser.
export {
  yearlyChunksExclusiveEnd,
  type IsoDate,
} from "./_fetchers/_iem_chunks.js";
export {
  buildIemUrl,
  downloadIemAsos,
  IEM_BASE_URL,
  IEM_POLITE_DELAY_MS,
  type DownloadIemAsosOptions,
  type IemChunkResult,
} from "./_fetchers/iem-asos.js";
export {
  iemToObservation,
  parseIemCsv,
  type IemCsvRow,
  type IemObservationTypeOverride,
  type IemToObservationOptions,
} from "./_parsers/iem.js";

// TS-W2 Plan 02 — GHCNh PSV fetcher + parser + station-id translator.
export {
  downloadGhcnh,
  downloadGhcnhRange,
  GHCNH_BASE_URL,
  NCEI_POLITE_DELAY_MS,
  type DownloadGhcnhRangeOptions,
  type GhcnhYearResult,
} from "./_fetchers/ghcnh.js";
export {
  parseGhcnhPsv,
  parseGhcnhRow,
  ghcnhStationToCode,
  extractStationCode,
  SSID_COLUMNS,
} from "./_parsers/ghcnh.js";

// Phase 11 — `mostlyright.live` ticker surface (stream + latest).
export {
  POLITE_FLOORS_S,
  SOURCE_IDENTITY_TAGS,
  SUPPORTED_SOURCES,
  isLiveSource,
  latest,
  sourceTag,
  stream,
  validatePollSeconds,
  validateSource,
  type LatestOptions,
  type LiveObservation,
  type LiveSource,
  type LiveSourceTag,
  type StreamOptions,
} from "./live/index.js";
export { LiveStreamError, NoLiveDataError } from "@mostlyright/core";
