// Phase 17 PLAN-11 / Phase 21 21-07 — TS `forecastNwp()` stub.
//
// Per CONTEXT decision 7: TS NWP is deferred to v2.0+. No production-ready
// browser GRIB2 decoder exists in May 2026; shipping a non-functional
// runtime-error stub now means callers can write code against the
// future-stable signature today — v2.0+ lands the execution body.
//
// Phase 21 21-07 upgrade: throws `DataAvailabilityError` (typed exception
// from Phase 21 21-09). Post-21-07 follow-up: throws the more specific
// `NwpNotAvailableError` subclass so consumers get `instanceof`-based
// dispatch + `.station` / `.model` autocomplete instead of having to parse
// the hint string. Back-compat preserved (NwpNotAvailableError extends
// DataAvailabilityError with reason="model_unavailable").

import { NwpNotAvailableError } from "@mostlyrightmd/core";

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
  return `forecastNwp(${station}, "${model}") is a v1.x stub. Browser GRIB2 decode is not production-ready in May 2026 (no eccodes / cfgrib equivalent for the browser; WASM compile time + bundle size make it impractical for v1.x). ${mosLine} See https://mostlyright.md/docs/sdk/typescript/nwp-forecasts/ for the architectural reason + v2.0+ tracking.`;
}

/**
 * Fetch a gridded NWP forecast — **v1.x stub, deferred to v2.0+**.
 *
 * @remarks
 * **⚠️ Not yet implemented in TypeScript.** This function exists so callers
 * can write code against the future-stable signature, but it throws on
 * every call. Use the Python SDK (`mostlyright>=1.0`) for gridded NWP
 * today — it wires the NCEP family (HRRR, GFS, NBM, RAP, RRFS, …) end-to-end.
 *
 * **Why deferred:** GRIB2 decode requires native libraries (eccodes C
 * library or cfgrib Python wrapper). No production-ready browser-side
 * decoder exists in May 2026; a WASM port's compile time + bundle size
 * are impractical for v1.x. v2.0+ tracks the GRIB2 ecosystem maturity.
 *
 * **Workaround paths:**
 * - **7 major US stations** (KNYC, KLAX, KORD, KMIA, KDEN, KSEA, KATL) →
 *   {@link iemMosForecasts} ships MOS-based forecasts that solve most use
 *   cases. The error hint includes this pointer automatically.
 * - **Everything else** → use the Python SDK
 *   (`pip install mostlyrightmd-weather`).
 *
 * @throws {@link NwpNotAvailableError} on every call (v1.x). The error
 *   is a subclass of `DataAvailabilityError`, so existing
 *   `catch (e instanceof DataAvailabilityError)` paths continue to catch
 *   it. The thrown instance carries typed `.station` and `.model`
 *   properties for log/error attribution.
 *
 * @see {@link https://mostlyright.md/docs/sdk/typescript/nwp-forecasts/ | docs/nwp-forecasts.md}
 *   for the full architectural rationale, the supported-model list, and
 *   the v2.0+ roadmap.
 */
export async function forecastNwp(
  station: string,
  model: NwpModel,
  _opts: ForecastNwpOptions = {},
): Promise<never> {
  throw new NwpNotAvailableError({
    station,
    model,
    hint: buildHint(station, model),
  });
}
