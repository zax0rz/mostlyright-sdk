// Phase 17 PLAN-11 — TS `forecastNwp()` stub.
//
// Per CONTEXT decision 7: TS NWP is deferred to v1.1. No production-ready
// browser GRIB2 decoder exists in May 2026; shipping a non-functional
// runtime-error stub now means callers can write code against the
// future-stable signature today — v1.1 lands the execution body.

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
 * Fetch a gridded NWP forecast — **v1.0 stub, deferred to v1.1**.
 *
 * Per Phase 17 CONTEXT decision 7, the TS NWP execution body is deferred
 * to v1.1 because no production-ready browser GRIB2 decoder exists in
 * May 2026. This function signature is stable so callers can ship code
 * today; v1.1 lands the fetch + decode wiring as a runtime upgrade with
 * no signature break.
 *
 * @throws `Error('forecastNwp: TS NWP deferred to v1.1 ...')`.
 */
export async function forecastNwp(
  _station: string,
  _model: NwpModel,
  _opts: ForecastNwpOptions = {},
): Promise<never> {
  throw new Error(
    "forecastNwp: TS NWP deferred to v1.1 per CONTEXT decision 7. " +
      "Browser GRIB2 decode is not production-ready in May 2026; the v1.0 " +
      "TS forecast surface ships iemMosForecasts() only. Use the Python " +
      "SDK's mostlyright.forecast_nwp() for NWP in v1.0.",
  );
}
