// Phase 17 PLAN-11 — forecastNwp TS stub unit tests.

import { describe, expect, it } from "vitest";

import { forecastNwp } from "../../src/forecasts/index.js";

describe("forecastNwp (v1.0 stub)", () => {
  it("throws NotImplementedError-style Error pointing at v1.1", async () => {
    await expect(forecastNwp("KNYC", "hrrr")).rejects.toThrow(
      /TS NWP deferred to v1.1/,
    );
  });

  it("error message names CONTEXT decision 7", async () => {
    await expect(forecastNwp("KNYC", "gfs")).rejects.toThrow(
      /CONTEXT decision 7/,
    );
  });

  it("error message points users at the Python SDK for v1.0 NWP", async () => {
    await expect(
      forecastNwp("KNYC", "ecmwf_ifs_hres", { cycle: "2026-05-24T12:00:00Z" }),
    ).rejects.toThrow(/Python SDK/);
  });

  it("signature accepts all 24 NwpModel literals", async () => {
    // Type-level check only — runtime always throws. The list mirrors
    // the Python SUPPORTED_NWP_MODELS frozenset.
    const models = [
      "hrrr",
      "gfs",
      "nbm",
      "hrrrak",
      "gefs",
      "gdas",
      "rap",
      "rrfs",
      "rtma",
      "urma",
      "cfs",
      "ecmwf_ifs_hres",
      "ecmwf_ifs_ens",
      "ecmwf_aifs_single",
      "ecmwf_aifs_ens",
      "hrdps",
      "rdps",
      "gdps",
      "geps",
      "reps",
      "hafs",
      "nam",
      "href",
      "hiresw",
    ] as const;
    expect(models.length).toBe(24);
    // Exercise one call to lock the runtime behavior.
    await expect(forecastNwp("KNYC", models[0])).rejects.toThrow();
  });
});
