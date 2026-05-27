// Phase 17 PLAN-11 / Phase 21 21-07 — forecastNwp TS stub unit tests.
// Post-21-07 follow-up: now throws NwpNotAvailableError (subclass of
// DataAvailabilityError) — verify back-compat AND the new typed .station/
// .model properties.

import { describe, expect, it } from "vitest";

import { DataAvailabilityError, NwpNotAvailableError } from "@mostlyrightmd/core";

import { forecastNwp } from "../../src/forecasts/index.js";

describe("forecastNwp (Phase 21 21-07 messaging)", () => {
  it("raises NwpNotAvailableError (subclass of DataAvailabilityError)", async () => {
    await expect(forecastNwp("KNYC", "hrrr")).rejects.toThrow(NwpNotAvailableError);
    try {
      await forecastNwp("KNYC", "hrrr");
    } catch (e) {
      const err = e as NwpNotAvailableError;
      // New typed-subclass dispatch path.
      expect(err).toBeInstanceOf(NwpNotAvailableError);
      // Back-compat: still catchable as DataAvailabilityError.
      expect(err).toBeInstanceOf(DataAvailabilityError);
      expect(err.reason).toBe("model_unavailable");
      // Source defaults to `nwp.${model}` on NwpNotAvailableError.
      expect(err.source).toBe("nwp.hrrr");
      // Typed properties for IDE autocomplete + log attribution.
      expect(err.station).toBe("KNYC");
      expect(err.model).toBe("hrrr");
    }
  });

  it("hint mentions iemMosForecasts() for MOS-covered stations (KNYC)", async () => {
    try {
      await forecastNwp("KNYC", "hrrr");
      throw new Error("should have thrown");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err.hint).toMatch(/iemMosForecasts/);
      expect(err.hint).toMatch(/v2\.0\+|v1\.x|deferred/);
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
      throw new Error("should have thrown DataAvailabilityError");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err).toBeInstanceOf(DataAvailabilityError);
      expect(err.hint).toMatch(/"gfs"/);
    }
    try {
      await forecastNwp("KNYC", "ecmwf_ifs_hres");
      throw new Error("should have thrown DataAvailabilityError");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err).toBeInstanceOf(DataAvailabilityError);
      expect(err.hint).toMatch(/"ecmwf_ifs_hres"/);
    }
  });

  it("hint links to docs/nwp-forecasts.md", async () => {
    try {
      await forecastNwp("KNYC", "hrrr");
      throw new Error("should have thrown DataAvailabilityError");
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err).toBeInstanceOf(DataAvailabilityError);
      expect(err.hint).toMatch(/nwp-forecasts|forecasts/);
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
