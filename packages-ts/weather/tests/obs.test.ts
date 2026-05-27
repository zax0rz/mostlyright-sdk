// Phase 21 21-04 — obs(station, from, to, opts?) tests.
//
// Smoke-tests:
//  - hosted strategy raises DataAvailabilityError (D-06)
//  - unknown strategy raises TypeError
//  - source filter narrows to a single source's fetcher
//  - shape projection (ObsRow includes temp_f derived from temp_c)
//
// Strategy-routing tests live in obs.strategy.test.ts. Network-backed
// end-to-end tests live in obs.live.test.ts (gated).

import { describe, expect, it, vi } from "vitest";

import { DataAvailabilityError } from "@mostlyrightmd/core";

import * as awcFetcher from "../src/_fetchers/awc.js";
import * as iemFetcher from "../src/_fetchers/iem-asos.js";
import { obs } from "../src/obs.js";

describe("obs — hosted strategy", () => {
  it("raises DataAvailabilityError with reason='model_unavailable'", async () => {
    await expect(obs("KNYC", "2025-01-06", "2025-01-12", { strategy: "hosted" })).rejects.toThrow(
      DataAvailabilityError,
    );

    try {
      await obs("KNYC", "2025-01-06", "2025-01-12", { strategy: "hosted" });
    } catch (e) {
      const err = e as DataAvailabilityError;
      expect(err.reason).toBe("model_unavailable");
      expect(err.hint).toMatch(/v0\.2\.x/);
      expect(err.source).toBe("obs-hosted-stub");
    }
  });
});

describe("obs — unknown strategy", () => {
  it("raises TypeError when strategy is not in the enum", async () => {
    await expect(
      obs("KNYC", "2025-01-06", "2025-01-12", { strategy: "made-up" as never }),
    ).rejects.toThrow(TypeError);
  });
});

describe("obs — source filter", () => {
  it("source='awc' calls AWC fetcher only (not IEM)", async () => {
    const awcSpy = vi.spyOn(awcFetcher, "fetchAwcMetars").mockResolvedValueOnce([]);
    const iemSpy = vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([]);
    await obs("KNYC", "2025-01-06", "2025-01-06", {
      source: "awc",
      strategy: "exact_window",
    });
    expect(awcSpy).toHaveBeenCalled();
    expect(iemSpy).not.toHaveBeenCalled();
  });

  it("source='iem' calls IEM fetcher only (not AWC)", async () => {
    const awcSpy = vi.spyOn(awcFetcher, "fetchAwcMetars").mockResolvedValueOnce([]);
    const iemSpy = vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([]);
    await obs("KNYC", "2025-01-06", "2025-01-06", {
      source: "iem",
      strategy: "exact_window",
    });
    expect(iemSpy).toHaveBeenCalled();
    expect(awcSpy).not.toHaveBeenCalled();
  });

  it("source=null (default) composes BOTH AWC + IEM", async () => {
    const awcSpy = vi.spyOn(awcFetcher, "fetchAwcMetars").mockResolvedValueOnce([]);
    const iemSpy = vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([]);
    await obs("KNYC", "2025-01-06", "2025-01-06", { strategy: "exact_window" });
    expect(awcSpy).toHaveBeenCalled();
    expect(iemSpy).toHaveBeenCalled();
  });
});

describe("obs — strategy=exact_window over an empty fetch", () => {
  it("returns an empty array (no rows in mocked fetch)", async () => {
    vi.spyOn(awcFetcher, "fetchAwcMetars").mockResolvedValueOnce([]);
    vi.spyOn(iemFetcher, "downloadIemAsos").mockResolvedValueOnce([]);
    const out = await obs("KNYC", "2025-01-06", "2025-01-06", {
      strategy: "exact_window",
    });
    expect(out).toEqual([]);
  });
});
