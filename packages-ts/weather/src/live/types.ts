// Phase 11 — LiveObservation row type.
//
// Mirrors Python: `live.stream()` / `live.latest()` rows are the existing
// observation shape with the `source` field widened to the live-channel
// identity tag (`"awc.live"` / `"iem.live"`). The archive-channel source
// values (`"awc"` / `"iem"` / `"ghcnh"`) on the canonical `Observation`
// type are NOT valid on live rows — keeping the union narrow lets
// downstream consumers branch on `source.endsWith(".live")` without
// re-parsing.

import type { Observation } from "../_parsers/awc.js";

import type { LiveSourceTag } from "./sources.js";

/**
 * Observation row emitted by `tradewinds.live.stream` and `live.latest`.
 *
 * Same shape as the canonical `Observation` row, but with `source` narrowed
 * to the live-channel identity tags. The widened-archive `"awc"` / `"iem"`
 * / `"ghcnh"` source values are NOT valid here — that's the point of the
 * separate type.
 */
export type LiveObservation = Omit<Observation, "source"> & {
  readonly source: LiveSourceTag;
};
