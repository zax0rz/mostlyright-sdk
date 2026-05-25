// mostlyright (meta) — convenience re-export of the three scoped packages.
// Use this if you want a single `import { research } from "mostlyright"` entry point;
// otherwise import the scoped packages directly.
//
// Note: each underlying package exports its own `version` constant; to avoid
// ambiguous re-exports we expose them under namespaced module objects in
// addition to a top-level `version` for the meta package itself.

export { helloCore } from "@mostlyright/core";
export { helloWeather } from "@mostlyright/weather";
export { helloMarkets } from "@mostlyright/markets";

import * as core from "@mostlyright/core";
import * as markets from "@mostlyright/markets";
import * as weather from "@mostlyright/weather";

export { core, markets, weather };

// TS-W2 Wave 4: full multi-source `research()` orchestrator (AWC + IEM
// ASOS + GHCNh + CLI). Lives here (NOT in @mostlyright/core) so the core
// package stays dep-free; the orchestrator pulls in both core + weather.
// `PairsRow` is the canonical row shape from @mostlyright/core/internal/pairs.
export { research, type ResearchOptions, type PairsRow } from "./research.js";

// TS-W4 Wave 1: Mode 2 source-explicit dispatch (researchBySource +
// assertSourceIdentity + Mode2Source const-union). Lives in the meta
// package alongside research() — the dispatch needs the @mostlyright/weather
// Observation type and assertSourceIdentity consumes it structurally;
// @mostlyright/core must NOT depend on weather (cycle).
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
// surface. Lives in @mostlyright/meta because compose.ts pulls in both
// @mostlyright/core (cache, station registry) and @mostlyright/markets
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
//   import { stream } from "@mostlyright/weather"                 // main barrel
//   import { stream } from "@mostlyright/weather/live"            // subpath
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
} from "@mostlyright/weather";
export { LiveStreamError, NoLiveDataError } from "@mostlyright/core";

export const version = "0.0.0";
