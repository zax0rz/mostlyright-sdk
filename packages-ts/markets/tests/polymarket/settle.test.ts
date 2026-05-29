import { describe, expect, it } from "vitest";

import {
  PayloadTooLargeError,
  PolymarketEventError,
  PolymarketSettlementError,
  TooEarlyToSettleError,
  polymarketSettle,
} from "../../src/polymarket/index.js";

function denseRows(
  isoDate: string,
  tempsC: number[],
): Array<{ observed_at: string; temp_c: number; source: string }> {
  // Spread observations every hour from isoDate 00:00 UTC.
  const start = new Date(`${isoDate}T00:00:00Z`).getTime();
  return tempsC.map((t, i) => ({
    observed_at: new Date(start + i * 3600 * 1000).toISOString(),
    temp_c: t,
    source: "iem",
  }));
}

describe("polymarketSettle — security defenses", () => {
  it("rejects empty / missing event id", async () => {
    await expect(
      polymarketSettle({
        event: { slug: "will-london-be-above-25c-on-2026-05-23" },
      }),
    ).rejects.toThrow(PolymarketEventError);
  });

  it("rejects event id outside the EVENT_ID_RE shape", async () => {
    await expect(
      polymarketSettle({
        event: { id: "not valid!", slug: "will-london-on-2026-05-23" },
      }),
    ).rejects.toThrow(PolymarketEventError);
  });

  it("rejects oversized description", async () => {
    await expect(
      polymarketSettle({
        event: {
          id: "evt-abc",
          slug: "will-london-on-2026-05-23",
          description: "x".repeat(16 * 1024 + 1),
        },
      }),
    ).rejects.toThrow(PayloadTooLargeError);
  });

  it("rejects URL outside the netloc allowlist", async () => {
    await expect(
      polymarketSettle({
        event: {
          id: "evt-abc",
          slug: "will-london-on-2026-05-23",
          description: "Source: https://evil.example.com/",
        },
      }),
    ).rejects.toThrow(PolymarketEventError);
  });
});

describe("polymarketSettle — settlement", () => {
  it("raises PolymarketSettlementError when loader returns no rows", async () => {
    await expect(
      polymarketSettle({
        event: {
          id: "evt-abc",
          slug: "will-london-hottest-on-2026-05-23",
          description: "https://www.weather.gov/",
        },
        now: new Date("2026-05-24T20:00:00Z"),
        loader: async () => [],
      }),
    ).rejects.toThrow(PolymarketSettlementError);
  });

  it("raises TooEarlyToSettleError before the publication delay elapses", async () => {
    const rows = denseRows("2026-05-23", new Array(12).fill(20));
    await expect(
      polymarketSettle({
        event: {
          id: "evt-abc",
          slug: "will-london-hottest-on-2026-05-23",
          description: "https://www.wunderground.com/",
        },
        // 1 hour after London midnight: well within the 6h Wunderground delay.
        now: new Date("2026-05-24T00:00:00Z"),
        loader: async () => rows,
      }),
    ).rejects.toThrow(TooEarlyToSettleError);
  });

  it("resolves a London HIGH market once the delay has elapsed (international → °C native)", async () => {
    const rows = denseRows(
      "2026-05-23",
      [
        // 12 obs, with the day's max at 30°C → 86°F.
        20, 22, 24, 26, 28, 30, 29, 27, 25, 23, 21, 19,
      ],
    );
    const result = await polymarketSettle({
      event: {
        id: "evt-abc",
        slug: "will-london-hottest-on-2026-05-23",
        description: "https://www.weather.gov/",
      },
      now: new Date("2026-05-25T12:00:00Z"), // > 24h after settlement date
      loader: async () => rows,
    });
    expect(result.eventId).toBe("evt-abc");
    expect(result.icao).toBe("EGLC");
    expect(result.settlementDate).toBe("2026-05-23");
    expect(result.measure).toBe("high");
    expect(result.unit).toBe("celsius");
    // 30°C → 86°F. Allow ±1 in the native unit.
    expect(result.resolvedValueC).toBeGreaterThanOrEqual(29);
    expect(result.resolvedValueC).toBeLessThanOrEqual(31);
    expect(result.resolvedValueF).toBeGreaterThanOrEqual(85);
    expect(result.resolvedValueF).toBeLessThanOrEqual(87);
    expect(result.resolvedValue).toBe(result.resolvedValueC);
    expect(result.resolutionSourceType).toBe("noaa_wrh");
  });

  it("uses the explicit unit option to override native default", async () => {
    const rows = denseRows("2026-05-23", new Array(12).fill(30));
    const result = await polymarketSettle({
      event: {
        id: "evt-abc",
        slug: "will-london-hottest-on-2026-05-23",
        description: "https://www.weather.gov/",
      },
      now: new Date("2026-05-25T12:00:00Z"),
      loader: async () => rows,
      unit: "fahrenheit",
    });
    expect(result.unit).toBe("fahrenheit");
    expect(result.resolvedValue).toBe(result.resolvedValueF);
  });

  it("emits a dataQualityAlert when the C-native resolved value diverges from Polymarket's published °C", async () => {
    const rows = denseRows("2026-05-23", new Array(12).fill(30));
    const result = await polymarketSettle({
      event: {
        id: "evt-abc",
        slug: "will-london-hottest-on-2026-05-23",
        description: "https://www.weather.gov/",
      },
      now: new Date("2026-05-25T12:00:00Z"),
      loader: async () => rows,
      polymarketPublishedValue: 20, // claim 20°C but mostlyright resolves ~30°C
    });
    expect(result.dataQualityAlert).not.toBeNull();
    expect(result.dataQualityAlert).toMatch(/Δ/);
    expect(result.dataQualityAlert).toContain("°C");
  });

  it("refuses to settle ambiguous markets (codex iter-1 P2)", async () => {
    const rows = denseRows("2026-05-23", new Array(12).fill(20));
    await expect(
      polymarketSettle({
        event: {
          id: "evt-abc",
          slug: "will-london-on-2026-05-23",
          title: "London weather event (no high/low keyword)",
          description: "https://www.weather.gov/",
        },
        now: new Date("2026-05-25T12:00:00Z"),
        loader: async () => rows,
      }),
    ).rejects.toThrow(PolymarketSettlementError);
  });

  it("returns dataQualityAlert null when the values agree within the unit threshold (°C native)", async () => {
    const rows = denseRows("2026-05-23", new Array(12).fill(30));
    const result = await polymarketSettle({
      event: {
        id: "evt-abc",
        slug: "will-london-hottest-on-2026-05-23",
        description: "https://www.weather.gov/",
      },
      now: new Date("2026-05-25T12:00:00Z"),
      loader: async () => rows,
      polymarketPublishedValue: 30, // matches the C-native resolved value
    });
    expect(result.dataQualityAlert).toBeNull();
  });
});
