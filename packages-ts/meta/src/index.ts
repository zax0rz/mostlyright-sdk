// mostlyright (meta) — convenience re-export of the three scoped packages.
// Use this if you want a single `import { research } from "mostlyright"` entry point;
// otherwise import the scoped packages directly.
//
// Note: each underlying package exports its own `version` constant; to avoid
// ambiguous re-exports we expose them under namespaced module objects in
// addition to a top-level `version` for the meta package itself.

export { helloCore } from "@mostlyrightmd/core";
export { helloWeather } from "@mostlyrightmd/weather";
export { helloMarkets } from "@mostlyrightmd/markets";

import * as core from "@mostlyrightmd/core";
import * as markets from "@mostlyrightmd/markets";
import * as weather from "@mostlyrightmd/weather";

export { core, markets, weather };

// TS-W2 Wave 4: full multi-source `research()` orchestrator (AWC + IEM
// ASOS + GHCNh + CLI). Lives here (NOT in @mostlyrightmd/core) so the core
// package stays dep-free; the orchestrator pulls in both core + weather.
// `PairsRow` is the canonical row shape from @mostlyrightmd/core/internal/pairs.
export { research, type ResearchOptions, type PairsRow } from "./research.js";

// TS-W4 Wave 1: Mode 2 source-explicit dispatch (researchBySource +
// assertSourceIdentity + Mode2Source const-union). Lives in the meta
// package alongside research() — the dispatch needs the @mostlyrightmd/weather
// Observation type and assertSourceIdentity consumes it structurally;
// @mostlyrightmd/core must NOT depend on weather (cycle).
export {
  MODE2_SOURCES,
  SOURCE_ALIASES,
  assertSourceIdentity,
  isMode2Source,
  researchBySource,
  type Mode2Source,
  type ResearchBySourceOptions,
  type SourceMismatchRole,
} from "./mode2.js";

// Phase 10: composable research() dispatcher + discover() ergonomic
// surface. Lives in @mostlyrightmd/meta because compose.ts pulls in both
// @mostlyrightmd/core (cache, station registry) and @mostlyrightmd/markets
// (Kalshi catalog + Polymarket catalog + denylist) — keeping it in
// core would create a cycle (markets depends on core).
export {
  SELECTOR_NAMES,
  annotateSettlesFor,
  buildOverrideWarning,
  resolveCity,
  resolveContract,
  validateSelectors,
  type SelectorArgs,
  type SelectorName,
  type StationOverrideWarning,
} from "./compose.js";

export { discover, type DiscoverResult, type DiscoverRow } from "./discover.js";

// Phase 11 — `mostlyright.live` ticker surface re-exported through the
// meta package so all three import shapes resolve to the same surface:
//   import { stream, latest } from "mostlyright"                  // meta
//   import { stream } from "@mostlyrightmd/weather"                 // main barrel
//   import { stream } from "@mostlyrightmd/weather/live"            // subpath
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
} from "@mostlyrightmd/weather";
export { LiveStreamError, NoLiveDataError } from "@mostlyrightmd/core";

/**
 * Placeholder version string for the meta package. The authoritative
 * package version lives in `package.json#version` (currently
 * `0.1.0-rc.7`); this constant has not been bumped. Sibling packages
 * (`@mostlyrightmd/core` / `weather` / `markets`) each export their own
 * `version` constant, exposed here via the namespaced module objects.
 */
export const version = "0.0.0";
