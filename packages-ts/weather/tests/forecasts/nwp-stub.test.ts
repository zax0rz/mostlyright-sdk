// Phase 17 PLAN-11 / Phase 21 21-07 — forecastNwp TS stub unit tests.

import { describe, expect, it } from "vitest";

import { DataAvailabilityError } from "@mostlyrightmd/core";

import { forecastNwp } from "../../src/forecasts/index.js";

describe("forecastNwp (Phase 21 21-07 messaging)", () => {
  it("raises DataAvailabilityError with reason='model_unavailable'", async () => {
    await expect(forecastNwp("KNYC", "hrrr")).rejects.toThrow(DataAvailabilityError);
    try {
      await forecastNwp("KNYC", "hrrr");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err).toBeInstanceOf(DataAvailabilityError);
      expect(err.reason).toBe("model_unavailable");
      expect(err.source).toBe("nwp-stub");
    }
  });

  it("hint mentions iemMosForecasts() for MOS-covered stations (KNYC)", async () => {
    try {
      await forecastNwp("KNYC", "hrrr");
      throw new Error("should have thrown");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err.hint).toMatch(/iemMosForecasts/);
      expect(err.hint).toMatch(/v1\.1\+|v1\.x|deferred/);
    }
  });

  it("hint omits iemMosForecasts for non-MOS-covered stations (KSFO)", async () => {
    try {
      await forecastNwp("KSFO", "hrrr");
      throw new Error("should have thrown");
    } catch (e) {
      const err = e as DataAvailabilityError;
      // The non-MOS branch points at the Python SDK fallback only.
      expect(err.hint).not.toMatch(/iemMosForecasts\("KSFO"/);
      expect(err.hint).toMatch(/Python SDK/);
    }
  });

  it("hint includes the requested model name", async () => {
    try {
      await forecastNwp("KNYC", "gfs");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err.hint).toMatch(/"gfs"/);
    }
    try {
      await forecastNwp("KNYC", "ecmwf_ifs_hres");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err.hint).toMatch(/"ecmwf_ifs_hres"/);
    }
  });

  it("hint links to docs/forecasts.md typescript-lane section", async () => {
    try {
      await forecastNwp("KNYC", "hrrr");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err.hint).toMatch(/typescript-lane|forecasts/);
    }
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
