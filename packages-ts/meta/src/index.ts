// tradewinds (meta) — convenience re-export of the three scoped packages.
// Use this if you want a single `import { research } from "tradewinds"` entry point;
// otherwise import the scoped packages directly.
//
// Note: each underlying package exports its own `version` constant; to avoid
// ambiguous re-exports we expose them under namespaced module objects in
// addition to a top-level `version` for the meta package itself.

export { helloCore } from "@tradewinds/core";
export { helloWeather } from "@tradewinds/weather";
export { helloMarkets } from "@tradewinds/markets";

import * as core from "@tradewinds/core";
import * as markets from "@tradewinds/markets";
import * as weather from "@tradewinds/weather";

export { core, markets, weather };

// TS-W1 Wave 6: minimal `research()` orchestrator (AWC + CLI only).
// Lives here (NOT in @tradewinds/core) so the core package stays
// dep-free; the orchestrator pulls in both core + weather.
export { research, type ResearchOptions, type ResearchRow } from "./research.js";

export const version = "0.0.0";
