import { describe, expect, it } from "vitest";

import { type ClimateKey, mergeClimate } from "../../../src/internal/merge/climate.js";

function row(
  station: string,
  date: string,
  priority: number,
  marker?: string,
): ClimateKey & { marker?: string } {
  return {
    station_code: station,
    observation_date: date,
    report_type_priority: priority,
    ...(marker !== undefined ? { marker } : {}),
  };
}

describe("mergeClimate — strict-> + first-seen tiebreak", () => {
  it("final (priority 3.0) replaces preliminary (1.0) at same (station, date)", () => {
    const prelim = row("NYC", "2025-01-08", 1.0, "prelim");
    const final = row("NYC", "2025-01-08", 3.0, "final");
    const merged = mergeClimate([prelim, final]) as Array<{ marker?: string }>;
    expect(merged).toHaveLength(1);
    expect(merged[0]?.marker).toBe("final");
  });

  it("final → preliminary does NOT replace (strict >, not >=)", () => {
    const final = row("NYC", "2025-01-08", 3.0, "final");
    const prelim = row("NYC", "2025-01-08", 1.0, "prelim");
    const merged = mergeClimate([final, prelim]) as Array<{ marker?: string }>;
    expect(merged).toHaveLength(1);
    expect(merged[0]?.marker).toBe("final");
  });

  it("two finals at same (station, date): first-seen wins on equal priority", () => {
    const f1 = row("NYC", "2025-01-08", 3.0, "first-final");
    const f2 = row("NYC", "2025-01-08", 3.0, "second-final");
    const merged = mergeClimate([f1, f2]) as Array<{ marker?: string }>;
    expect(merged).toHaveLength(1);
    expect(merged[0]?.marker).toBe("first-final");
  });

  it("missing report_type_priority on row treated as 0 (loses to anything ≥ 0+ε)", () => {
    const noPriority = {
      station_code: "NYC",
      observation_date: "2025-01-08",
      report_type_priority: 0,
    };
    const prelim = row("NYC", "2025-01-08", 1.0, "prelim");
    const merged = mergeClimate([noPriority, prelim]) as Array<{ marker?: string }>;
    expect(merged[0]?.marker).toBe("prelim");
  });
});

describe("mergeClimate — distinct-key preservation", () => {
  it("different stations: both rows kept", () => {
    const nyc = row("NYC", "2025-01-08", 3.0);
    const ord = row("ORD", "2025-01-08", 3.0);
    expect(mergeClimate([nyc, ord])).toHaveLength(2);
  });

  it("different dates: both rows kept", () => {
    const day1 = row("NYC", "2025-01-08", 3.0);
    const day2 = row("NYC", "2025-01-09", 3.0);
    expect(mergeClimate([day1, day2])).toHaveLength(2);
  });
});

describe("mergeClimate — boundary cases", () => {
  it("empty input → []", () => {
    expect(mergeClimate([])).toEqual([]);
  });

  it("single row → returned as-is", () => {
    const only = row("NYC", "2025-01-08", 3.0);
    expect(mergeClimate([only])).toEqual([only]);
  });
});
