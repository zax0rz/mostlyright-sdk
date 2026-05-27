// Phase 21 21-01 — composable-kwargs surface + runtime validation.
//
// Asserts the TS `research()` accepts the Python-parity options shape, and
// that runtime validation rejects mutually-exclusive misuse, unknown keys,
// and the `backend="polars"` case (D-03: no Polars in browser/Node TS).

import { DataAvailabilityError } from "@mostlyrightmd/core";
import { describe, expect, it } from "vitest";

import { research } from "../src/research.js";
import { KNOWN_RESEARCH_OPTION_KEYS, validateResearchKwargs } from "../src/research.types.js";

describe("Phase 21 21-01: research() composable kwargs surface", () => {
  // We don't exercise the network path here (the parity suite covers that);
  // we just assert validation fires BEFORE any I/O. Each test calls research()
  // with a config that fails validation, and asserts the expected throw shape.

  it("KNOWN_RESEARCH_OPTION_KEYS contains all Phase 21 21-01 snake_case kwargs", () => {
    for (const k of [
      "include_forecast",
      "forecast_model",
      "forecast_models",
      "qc",
      "tz_override",
      "backend",
      "return_type",
    ]) {
      expect(KNOWN_RESEARCH_OPTION_KEYS.has(k), `missing ${k} in known options`).toBe(true);
    }
  });

  it("validateResearchKwargs accepts an empty options object (no extra kwargs)", () => {
    // Regression check: research(station, from, to) with no options must
    // continue to work — the parity fixtures all use this path.
    expect(() => validateResearchKwargs({})).not.toThrow();
  });

  it("validateResearchKwargs rejects unknown option keys (typo defense)", () => {
    expect(() =>
      validateResearchKwargs({ inclide_forecast: true } as Readonly<Record<string, unknown>>),
    ).toThrow(TypeError);
    expect(() =>
      validateResearchKwargs({ unknown_key: 1 } as Readonly<Record<string, unknown>>),
    ).toThrow(/unknown option key/i);
  });

  it("validateResearchKwargs rejects sources + source together (mutually exclusive)", () => {
    expect(() =>
      validateResearchKwargs({
        sources: ["awc"],
        source: "iem",
      } as Readonly<Record<string, unknown>>),
    ).toThrow(/mutually exclusive/);
  });

  it("validateResearchKwargs rejects forecast_model + forecast_models together", () => {
    expect(() =>
      validateResearchKwargs({
        include_forecast: true,
        forecast_model: "gfs",
        forecast_models: ["gfs", "nbm"],
      } as Readonly<Record<string, unknown>>),
    ).toThrow(/mutually exclusive/);
  });

  it("validateResearchKwargs rejects forecast_model without include_forecast=true", () => {
    expect(() =>
      validateResearchKwargs({
        forecast_model: "gfs",
      } as Readonly<Record<string, unknown>>),
    ).toThrow(/include_forecast=true/);
  });

  it("research() throws DataAvailabilityError on backend='polars' (D-03)", async () => {
    // backend="polars" is the TS surface-parity kwarg that must raise per
    // D-03 — symmetric with Python (which routes to a Polars frame).
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", { backend: "polars" }),
    ).rejects.toBeInstanceOf(DataAvailabilityError);
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", { backend: "polars" }),
    ).rejects.toMatchObject({ reason: "model_unavailable" });
  });

  it("research() raises TypeError on sources + source together (BEFORE network)", async () => {
    // Mutually-exclusive misuse must surface as TypeError — the new validator
    // runs ahead of the old Phase 10 selector check (which throws plain
    // Error). Since validation fires first, this is the expected shape.
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", {
        sources: ["awc"],
        source: "iem",
      } as never),
    ).rejects.toBeInstanceOf(TypeError);
  });

  it("research() raises TypeError on unknown option key (typo defense)", async () => {
    await expect(
      research("KNYC", "2025-01-06", "2025-01-12", {
        inclide_forecast: true,
      } as never),
    ).rejects.toBeInstanceOf(TypeError);
  });

  // Phase 21 21-09 fix-iter-1 (codex+ts-architect HIGH): JSON `null` round-
  // tripped from Python `None` MUST be treated as "absent" — not as
  // "provided". Otherwise a cross-SDK options dict that's valid in Python
  // would falsely trigger the mutually-exclusive TypeError in TS.
  it("treats JSON null as absent (Python `None` cross-wire parity)", () => {
    // Both sources and source set to `null` — Python treats both as absent
    // (`is not None` is false), so the guard does NOT fire. Pre-fix TS used
    // `!== undefined`, which treated `null` as provided and falsely raised.
    expect(() =>
      validateResearchKwargs({
        sources: null,
        source: null,
      } as Readonly<Record<string, unknown>>),
    ).not.toThrow();

    // forecast_model: null (== absent) + forecast_models: null (== absent)
    // also passes.
    expect(() =>
      validateResearchKwargs({
        forecast_model: null,
        forecast_models: null,
      } as Readonly<Record<string, unknown>>),
    ).not.toThrow();
  });
});
