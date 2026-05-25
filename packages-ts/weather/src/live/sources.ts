// Phase 11 — per-source registry + polite floors.
//
// Mirrors Python `tradewinds/live/_sources.py`. Source set + floor values are
// kept byte-faithful with Python so cross-SDK consumers see the same
// invariant. Any divergence triggers the dual-SDK parity gate.

/** Canonical ordered tuple of supported sources. Order matters — keep AWC first. */
export const SUPPORTED_SOURCES = ["awc", "iem"] as const;

/** Validated source enum derived from `SUPPORTED_SOURCES`. */
export type LiveSource = (typeof SUPPORTED_SOURCES)[number];

/**
 * Minimum allowed poll cadence per source, in seconds.
 *
 * - AWC: 30s — aviationweather.gov has no documented rate limit but 30s is
 *   the empirically-validated floor that won't trip anti-abuse heuristics.
 * - IEM: 60s — mesonet.agron.iastate.edu is a university server; IEM docs
 *   explicitly ask for reasonable headroom above 1 req/s.
 */
export const POLITE_FLOORS_S: Readonly<Record<LiveSource, number>> = {
  awc: 30,
  iem: 60,
};

/**
 * Canonical per-source `source` field tag emitted on every observation row.
 *
 * `"awc.live"` / `"iem.live"` are the live-channel identity tags — distinct
 * from the archive-channel `"awc"` / `"iem"` written by the historical
 * fetchers. Cross-SDK parity: these match Python `SOURCE_IDENTITY_TAGS`.
 */
export const SOURCE_IDENTITY_TAGS = {
  awc: "awc.live",
  iem: "iem.live",
} as const satisfies Readonly<Record<LiveSource, string>>;

export type LiveSourceTag = (typeof SOURCE_IDENTITY_TAGS)[LiveSource];

/**
 * Normalize and validate a `source` option.
 *
 * @param source - Caller-supplied source string. `undefined`/`null` defaults
 *   to the first entry in `SUPPORTED_SOURCES` (AWC). Case-insensitive.
 * @returns The normalized lowercase source name (one of `SUPPORTED_SOURCES`).
 * @throws `Error` when the source is not in `SUPPORTED_SOURCES`.
 */
export function validateSource(source: string | null | undefined): LiveSource {
  if (source === undefined || source === null) {
    return SUPPORTED_SOURCES[0];
  }
  const normalized = source.trim().toLowerCase();
  if (!isLiveSource(normalized)) {
    throw new Error(
      `unknown live source ${JSON.stringify(source)}; supported: ${JSON.stringify(
        SUPPORTED_SOURCES,
      )}`,
    );
  }
  return normalized;
}

/** Type guard: narrow a string to `LiveSource`. */
export function isLiveSource(s: string): s is LiveSource {
  return (SUPPORTED_SOURCES as ReadonlyArray<string>).includes(s);
}

/**
 * Apply the polite-floor invariant to a caller-supplied cadence.
 *
 * @param pollSeconds - Caller-supplied cadence. `undefined`/`null` → use the floor.
 * @param source - A *validated* source name (call `validateSource` first).
 * @returns The cadence to use, in seconds.
 * @throws `Error` when `pollSeconds` is below the polite floor.
 */
export function validatePollSeconds(
  pollSeconds: number | null | undefined,
  source: LiveSource,
): number {
  const floor = POLITE_FLOORS_S[source];
  if (pollSeconds === undefined || pollSeconds === null) {
    return floor;
  }
  if (pollSeconds < floor) {
    throw new Error(
      `pollSeconds=${pollSeconds} below polite floor ${floor}s for source=${JSON.stringify(
        source,
      )}`,
    );
  }
  return pollSeconds;
}

/** Map a validated source name to its canonical row-level identity tag. */
export function sourceTag(source: LiveSource): LiveSourceTag {
  return SOURCE_IDENTITY_TAGS[source];
}
