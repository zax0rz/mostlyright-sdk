// Phase 8 — per-issuer denylist. Hand-paired with Python
// `mostlyright.markets.polymarket.KNOWN_WRONG_STATIONS` (NOT codegen;
// see .planning/phases/08-.../PLAN.md §"TS Parity" for rationale —
// the constant is small enough that exporter wiring would cost more
// than it saves, and the alphabetized JSON exporter side-effect would
// conflate it with the cities map).
//
// Per-city Map (not flat set) because Polymarket's catalog is multi-city
// and the "wrong" station depends on which city the event is for.
// Symmetric in spirit to Kalshi's KALSHI_KNOWN_WRONG_STATIONS flat set:
// Polymarket's per-city granularity is required because (e.g.) KLGA is
// correct for NYC but wrong for Chicago (where Polymarket uses KORD).

export const POLYMARKET_KNOWN_WRONG_STATIONS: Readonly<Record<string, ReadonlySet<string>>> =
  Object.freeze({
    // NYC: Polymarket uses KLGA. KNYC/KJFK/KEWR are common wrong answers.
    nyc: new Set(["KNYC", "KJFK", "KEWR"]),
    // Chicago: Polymarket uses KORD. KMDW is the common wrong answer.
    chicago: new Set(["KMDW"]),
    // Houston: Polymarket uses KIAH. KHOU is the common wrong answer.
    houston: new Set(["KHOU"]),
    // Dallas: Polymarket uses KDFW. KDAL is the common wrong answer.
    dallas: new Set(["KDAL"]),
    // SF: Polymarket uses KSFO. KOAK is the common wrong answer.
    san_francisco: new Set(["KOAK"]),
    // DC: Polymarket uses KDCA. KIAD/KBWI are common wrong answers.
    washington_dc: new Set(["KIAD", "KBWI"]),
  });
