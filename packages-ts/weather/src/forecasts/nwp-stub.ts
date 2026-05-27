// Phase 17 PLAN-11 / Phase 21 21-07 — TS `forecastNwp()` stub.
//
// Per CONTEXT decision 7: TS NWP is deferred to v1.1+. No production-ready
// browser GRIB2 decoder exists in May 2026; shipping a non-functional
// runtime-error stub now means callers can write code against the
// future-stable signature today — v1.1+ lands the execution body.
//
// Phase 21 21-07 upgrade: throws `DataAvailabilityError` (typed exception
// from Phase 21 21-09) instead of generic `Error`. The hint string routes
// callers to the `iemMosForecasts()` workaround for stations with MOS
// coverage, and points at docs/forecasts.md for the architectural reason.

import { DataAvailabilityError } from "@mostlyrightmd/core";

/** NWP model enum — mirror of Python `SUPPORTED_NWP_MODELS` (24 entries). */
export type NwpModel =
  | "hrrr"
  | "gfs"
  | "nbm"
  // PLAN-03 NCEP family
  | "hrrrak"
  | "gefs"
  | "gdas"
  | "rap"
  | "rrfs"
  | "rtma"
  | "urma"
  | "cfs"
  // PLAN-04 ECMWF family
  | "ecmwf_ifs_hres"
  | "ecmwf_ifs_ens"
  | "ecmwf_aifs_single"
  | "ecmwf_aifs_ens"
  // PLAN-05 MSC Canadian family
  | "hrdps"
  | "rdps"
  | "gdps"
  | "geps"
  | "reps"
  // PLAN-06 NOMADS-only family
  | "hafs"
  | "nam"
  | "href"
  | "hiresw";

/** Optional knobs for {@link forecastNwp}. */
export interface ForecastNwpOptions {
  /** Model run datetime — UTC ISO string. */
  readonly cycle?: string;
  /** Forecast hour ahead of `cycle`. */
  readonly fxx?: number;
  /** Force a mirror (e.g. `"aws_bdp"`). */
  readonly mirror?: string;
}

/**
 * Major US stations with IEM MOS coverage. Phase 21 21-07 hint surface
 * — if the caller's station is in this set, the error hint includes an
 * `iemMosForecasts()` workaround pointer. Otherwise the hint mentions
 * the Python SDK fallback only.
 *
 * Source: Phase 17 IEM MOS catalog. The exact set may grow over time;
 * we keep the hint list narrow (7 stations) so the message stays terse.
 */
const IEM_MOS_COVERED_STATIONS: ReadonlySet<string> = new Set([
  "KNYC",
  "KLAX",
  "KORD",
  "KMIA",
  "KDEN",
  "KSEA",
  "KATL",
]);

function buildHint(station: string, model: NwpModel): string {
  const hasMosCoverage = IEM_MOS_COVERED_STATIONS.has(station.toUpperCase());
  const mosLine = hasMosCoverage
    ? `Workaround for ${station}: iemMosForecasts("${station}", ...) is available (IEM MOS catalog covers this station).`
    : `Workaround: this station has no IEM MOS coverage; use the Python SDK's mostlyright.forecast_nwp() in v1.x.`;
  return `forecastNwp(${station}, "${model}") is a v1.x stub. Browser GRIB2 decode is not production-ready in May 2026 (no eccodes / cfgrib equivalent for the browser; WASM compile time + bundle size make it impractical for v1.x). ${mosLine} See https://mostlyright.md/docs/sdk/typescript/forecasts#typescript-lane for the architectural reason + v1.1+ tracking.`;
}

/**
 * Fetch a gridded NWP forecast — **v1.x stub, deferred to v1.1+**.
 *
 * Per Phase 17 CONTEXT decision 7, the TS NWP execution body is deferred
 * to v1.1+ because no production-ready browser GRIB2 decoder exists in
 * May 2026. This function signature is stable so callers can ship code
 * today; v1.1+ lands the fetch + decode wiring as a runtime upgrade with
 * no signature break.
 *
 * @throws DataAvailabilityError with reason="model_unavailable" and a
 *   hint that conditionally routes to `iemMosForecasts()` for the 7
 *   major US stations with IEM MOS coverage (Phase 21 21-07).
 */
export async function forecastNwp(
  station: string,
  model: NwpModel,
  _opts: ForecastNwpOptions = {},
): Promise<never> {
  throw new DataAvailabilityError({
    reason: "model_unavailable",
    source: "nwp-stub",
    hint: buildHint(station, model),
  });
}
