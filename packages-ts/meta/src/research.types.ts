// Phase 21 21-01 — research() composable kwargs surface.
//
// Mirrors the Python `research(*, include_forecast, forecast_model,
// forecast_models, qc, tz_override, sources, source, backend, return_type)`
// signature so cross-SDK consumers see the same options shape on either
// side. Per D-03, the `backend` and `return_type` kwargs are accepted in TS
// but `backend="polars"` raises DataAvailabilityError (no Polars in
// browser/Node TS — Python only), and `return_type="wrapper"` is a no-op
// (TS returns plain object arrays; wrappers don't carry semantic value
// without a separate frame backend to wrap).
//
// Snake_case keys match the Python wire format — a cross-language wrapper
// can pass the same options dict to either SDK without case-folding.

/**
 * Phase 21 21-01 composable-kwargs extension to `ResearchOptions`.
 *
 * All fields are optional; defaults match Python. Each field's runtime
 * validation lives in `validateResearchKwargs()` so the failure surface is
 * lockstep with Python's `_validate_research_kwargs`.
 */
export interface ResearchKwargsExtension {
  /**
   * When `true`, attach `fcst_*` columns. Phase 17 wired this end-to-end
   * for IEM MOS; other forecast models require Phase 21 follow-up plans.
   *
   * Default: `false`.
   */
  include_forecast?: boolean;

  /**
   * Single forecast model name (e.g. `"gfs"`, `"nbm"`). Requires
   * `include_forecast=true`. Mutually exclusive with `forecast_models`.
   */
  forecast_model?: string;

  /**
   * Multi-model forecast fan-out. Requires `include_forecast=true`.
   * Mutually exclusive with `forecast_model`.
   */
  forecast_models?: ReadonlyArray<string>;

  /**
   * When `true`, run QC passes and surface QC columns. Default `false`.
   */
  qc?: boolean;

  /**
   * IANA timezone override for stations not in the canonical registry.
   * Rarely needed for the 20-station Phase 1 set (all covered).
   */
  tz_override?: string;

  /**
   * D-03: accepted but no-op in TS. `backend="polars"` raises
   * `DataAvailabilityError` (no Polars in browser/Node TS). Default
   * `"pandas"` mirrors Python; in TS this is informational only.
   */
  backend?: "pandas" | "polars";

  /**
   * D-03: accepted but no-op in TS. Python returns a `TradewindsResult`
   * wrapper class when `return_type="wrapper"`; TS returns plain object
   * arrays (no `.attrs` divergence to bridge), so the wrapper would carry
   * no extra signal.
   */
  return_type?: "frame" | "wrapper";
}

/**
 * Full set of keys accepted on `ResearchOptions` (any value not in this
 * set raises `TypeError` at validation time — defends against silent
 * typo acceptance).
 *
 * Pre-Phase-21 keys (camelCase + lowercase): the existing TS surface;
 * shipped via Phase 7 / 10 / 17 / 18.
 *
 * Phase 21 21-01 keys (snake_case): the new composable kwargs ported from
 * Python.
 */
export const KNOWN_RESEARCH_OPTION_KEYS: ReadonlySet<string> = new Set([
  // Pre-Phase-21 fetcher controls.
  "signal",
  "awcHours",
  "iemPolitenessMs",
  "ghcnhPolitenessMs",
  "cliPolitenessMs",
  "now",
  "cache",
  // Pre-Phase-21 selectors.
  "city",
  "contract",
  "contracts",
  "stationOverride",
  "sources",
  "source",
  "includeTrades",
  "onWarning",
  // Phase 21 21-01: Python-parity composable kwargs.
  "include_forecast",
  "forecast_model",
  "forecast_models",
  "qc",
  "tz_override",
  "backend",
  "return_type",
]);

/**
 * Phase 21 21-01: runtime kwarg validation for `research()`. Lockstep with
 * Python `_validate_research_kwargs`. Throws `TypeError` (NOT
 * `DataAvailabilityError`) for the same reasons Python raises `TypeError`:
 *
 *   1. Unknown option key (silent typo defense).
 *   2. `sources` and `source` are mutually exclusive.
 *   3. `forecast_model` and `forecast_models` are mutually exclusive.
 *   4. `forecast_model`/`forecast_models` require `include_forecast=true`.
 *
 * The `backend="polars"` rejection lives in the calling code, NOT here —
 * it raises `DataAvailabilityError(reason: "model_unavailable")` per D-03
 * to match Python's `SourceUnavailableError` shape lockstep.
 */
export function validateResearchKwargs(opts: Readonly<Record<string, unknown>>): void {
  // (1) Unknown-key defense. Catches typos like `inclide_forecast` that
  // would otherwise silently no-op.
  for (const key of Object.keys(opts)) {
    if (!KNOWN_RESEARCH_OPTION_KEYS.has(key)) {
      throw new TypeError(
        `research(): unknown option key ${JSON.stringify(key)}. ` +
          `Valid keys: ${[...KNOWN_RESEARCH_OPTION_KEYS].sort().join(", ")}`,
      );
    }
  }

  // (2) sources / source mutually exclusive.
  if (opts.sources !== undefined && opts.source !== undefined) {
    throw new TypeError(
      "research(): sources= and source= are mutually exclusive — " +
        "use `sources=` for the LIVE_V1 multi-source selector or " +
        "`source=` for a single-source query, not both",
    );
  }

  // (3) forecast_model / forecast_models mutually exclusive.
  if (opts.forecast_model !== undefined && opts.forecast_models !== undefined) {
    throw new TypeError(
      "research(): forecast_model= and forecast_models= are mutually exclusive — " +
        "use `forecast_models=` for multi-model fan-out or `forecast_model=` for " +
        "a single model, not both",
    );
  }

  // (4) forecast_model / forecast_models require include_forecast=true.
  const wantsForecast = opts.forecast_model !== undefined || opts.forecast_models !== undefined;
  if (wantsForecast && opts.include_forecast !== true) {
    throw new TypeError(
      "research(): forecast_model=/forecast_models= require include_forecast=true; " +
        "the model filter is otherwise silently ignored",
    );
  }
}
