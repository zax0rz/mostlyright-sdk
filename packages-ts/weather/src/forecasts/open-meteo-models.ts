// Phase 20 OM-08 — Open-Meteo 36-model registry (TS mirror of Python
// `packages/weather/src/mostlyright/weather/_fetchers/_open_meteo_models/`).
//
// Single-file flat-table emission per D-10 bundle-size budget (TS lockstep
// pattern: Python uses per-family modules for code-org clarity; TS uses a
// flat table for byte-efficiency).

import type { OpenMeteoModel } from "./types.js";

/** The canonical 36-model set (D-02 set-equality lock). */
export const OPEN_METEO_MODELS: ReadonlySet<OpenMeteoModel> = new Set([
  // NCEP (8)
  "gfs_seamless",
  "gfs_global",
  "gfs_graphcast025",
  "aigfs025",
  "hgefs025",
  "ncep_hrrr_conus",
  "ncep_nbm_conus",
  "ncep_nam_conus",
  // ECMWF (3)
  "ecmwf_ifs025",
  "ecmwf_ifs_hres",
  "ecmwf_aifs025_single",
  // DWD (5)
  "dwd_icon_seamless",
  "dwd_icon_global",
  "dwd_icon_eu",
  "dwd_icon_d2",
  "dwd_icon_d2_15min",
  // Météo-France (6)
  "meteofrance_seamless",
  "meteofrance_arpege_world025",
  "meteofrance_arpege_europe",
  "meteofrance_arome_france0025",
  "meteofrance_arome_france_hd",
  "meteofrance_arome_france_hd_15min",
  // Asia + Oceania (8)
  "jma_seamless",
  "jma_gsm",
  "jma_msm",
  "kma_seamless",
  "kma_gdps",
  "kma_ldps",
  "cma_grapes_global",
  "bom_access_global",
  // Europe (3)
  "ukmo_global_deterministic_10km",
  "ukmo_uk_deterministic_2km",
  "metno_nordic_pp",
  // GEM Canada (3)
  "cmc_gem_gdps",
  "cmc_gem_rdps",
  "cmc_gem_hrdps",
]);

const SIX_HOURLY = [0, 6, 12, 18] as const;
const THREE_HOURLY = [0, 3, 6, 9, 12, 15, 18, 21] as const;
const HOURLY = Array.from({ length: 24 }, (_, i) => i) as readonly number[];
const TWELVE_HOURLY = [0, 12] as const;

/** Per-model UTC cycle hours. Mirrors Python `CYCLE_HOURS`. */
export const CYCLE_HOURS: ReadonlyMap<OpenMeteoModel, readonly number[]> = new Map<
  OpenMeteoModel,
  readonly number[]
>([
  // NCEP
  ["gfs_seamless", SIX_HOURLY],
  ["gfs_global", SIX_HOURLY],
  ["gfs_graphcast025", SIX_HOURLY],
  ["aigfs025", SIX_HOURLY],
  ["hgefs025", SIX_HOURLY],
  ["ncep_hrrr_conus", HOURLY],
  ["ncep_nbm_conus", HOURLY],
  ["ncep_nam_conus", SIX_HOURLY],
  // ECMWF
  ["ecmwf_ifs025", SIX_HOURLY],
  ["ecmwf_ifs_hres", SIX_HOURLY],
  ["ecmwf_aifs025_single", SIX_HOURLY],
  // DWD
  ["dwd_icon_seamless", SIX_HOURLY],
  ["dwd_icon_global", SIX_HOURLY],
  ["dwd_icon_eu", SIX_HOURLY],
  ["dwd_icon_d2", THREE_HOURLY],
  ["dwd_icon_d2_15min", THREE_HOURLY],
  // Météo-France
  ["meteofrance_seamless", SIX_HOURLY],
  ["meteofrance_arpege_world025", SIX_HOURLY],
  ["meteofrance_arpege_europe", SIX_HOURLY],
  ["meteofrance_arome_france0025", THREE_HOURLY],
  ["meteofrance_arome_france_hd", THREE_HOURLY],
  ["meteofrance_arome_france_hd_15min", THREE_HOURLY],
  // Asia + Oceania
  ["jma_seamless", SIX_HOURLY],
  ["jma_gsm", SIX_HOURLY],
  ["jma_msm", THREE_HOURLY],
  ["kma_seamless", SIX_HOURLY],
  ["kma_gdps", SIX_HOURLY],
  ["kma_ldps", THREE_HOURLY],
  ["cma_grapes_global", SIX_HOURLY],
  ["bom_access_global", SIX_HOURLY],
  // Europe
  ["ukmo_global_deterministic_10km", SIX_HOURLY],
  ["ukmo_uk_deterministic_2km", THREE_HOURLY],
  ["metno_nordic_pp", HOURLY],
  // GEM Canada
  ["cmc_gem_gdps", TWELVE_HOURLY],
  ["cmc_gem_rdps", SIX_HOURLY],
  ["cmc_gem_hrdps", SIX_HOURLY],
]);

/** Per-model publish-lag hours for Live mode cycle-math fallback (D-06). */
export const PUBLISH_LAG_HOURS: ReadonlyMap<OpenMeteoModel, number> = new Map<
  OpenMeteoModel,
  number
>([
  // NCEP — global 6h, regional/mesoscale 2h
  ["gfs_seamless", 6],
  ["gfs_global", 6],
  ["gfs_graphcast025", 6],
  ["aigfs025", 6],
  ["hgefs025", 6],
  ["ncep_hrrr_conus", 2],
  ["ncep_nbm_conus", 2],
  ["ncep_nam_conus", 2],
  // ECMWF — global 6h
  ["ecmwf_ifs025", 6],
  ["ecmwf_ifs_hres", 6],
  ["ecmwf_aifs025_single", 6],
  // DWD
  ["dwd_icon_seamless", 4],
  ["dwd_icon_global", 4],
  ["dwd_icon_eu", 4],
  ["dwd_icon_d2", 2],
  ["dwd_icon_d2_15min", 2],
  // Météo-France
  ["meteofrance_seamless", 4],
  ["meteofrance_arpege_world025", 6],
  ["meteofrance_arpege_europe", 4],
  ["meteofrance_arome_france0025", 2],
  ["meteofrance_arome_france_hd", 2],
  ["meteofrance_arome_france_hd_15min", 2],
  // Asia + Oceania
  ["jma_seamless", 6],
  ["jma_gsm", 6],
  ["jma_msm", 2],
  ["kma_seamless", 6],
  ["kma_gdps", 6],
  ["kma_ldps", 2],
  ["cma_grapes_global", 6],
  ["bom_access_global", 6],
  // Europe
  ["ukmo_global_deterministic_10km", 6],
  ["ukmo_uk_deterministic_2km", 2],
  ["metno_nordic_pp", 2],
  // GEM Canada
  ["cmc_gem_gdps", 6],
  ["cmc_gem_rdps", 4],
  ["cmc_gem_hrdps", 2],
]);

// ---------------------------------------------------------------------------
// Cycle math primitives (mirror Python `cycle_math.py`).
// ---------------------------------------------------------------------------

/**
 * Snap `valueUtcMs` (epoch ms) down to the most recent cycle hour <= value.
 * Returns the floored epoch ms.
 */
export function floorToCycleMs(valueUtcMs: number, cycleHours: readonly number[]): number {
  if (cycleHours.length === 0) {
    throw new Error("cycleHours must be non-empty");
  }
  const d = new Date(valueUtcMs);
  const hour = d.getUTCHours();
  const sorted = [...cycleHours].sort((a, b) => a - b);
  const candidates = sorted.filter((h) => h <= hour);
  if (candidates.length > 0) {
    const targetHour = candidates[candidates.length - 1];
    return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), targetHour, 0, 0, 0);
  }
  const lastCycle = sorted[sorted.length - 1];
  const prior = new Date(valueUtcMs - 86_400_000);
  return Date.UTC(
    prior.getUTCFullYear(),
    prior.getUTCMonth(),
    prior.getUTCDate(),
    lastCycle,
    0,
    0,
    0,
  );
}

/**
 * Conservative lower bound for the cycle producing `_previous_dayN` (D-05).
 */
export function issuedAtFromPreviousDayMs(
  validAtUtcMs: number,
  N: number,
  cycleHours: readonly number[],
): number {
  if (N < 1 || N > 7) {
    throw new Error(`N must be in 1..7 (Open-Meteo previous_dayN limit); got ${N}`);
  }
  return floorToCycleMs(validAtUtcMs - N * 86_400_000, cycleHours);
}

/**
 * Cycle-math fallback for Live mode `issuedAt` derivation (D-06).
 */
export function issuedAtFromLiveCycleMathMs(
  nowUtcMs: number,
  publishLagHours: number,
  cycleHours: readonly number[],
): number {
  return floorToCycleMs(nowUtcMs - publishLagHours * 3_600_000, cycleHours);
}
