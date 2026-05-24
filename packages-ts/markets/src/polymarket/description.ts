// TS-W5 — Description-validation primitives.
//
// Ports Python `_validate_description` + `_extract_resolution_source_type`.
// All three security defenses (16 KB cap, netloc allowlist, ReDoS-safe
// URL extraction) live here so they can be unit-tested independently of
// the higher-level settle() flow.

import { PayloadTooLargeError, PolymarketEventError } from "./errors.js";
import {
  MAX_DESCRIPTION_BYTES,
  NETLOC_TO_RESOLUTION_TYPE,
  type PolymarketResolutionSourceType,
  RESOLUTION_SOURCE_ALLOWLIST,
} from "./types.js";

// Bounded URL regex (linear-time match, no nested quantifiers → ReDoS-safe).
// Stops on whitespace, `<`, `>`, `"`, `'`, `)`. Capped at 2 KB per URL.
const URL_RE = /https?:\/\/[^\s<>"')]{1,2048}/g;

/**
 * Apply the 16 KB cap + netloc allowlist to a description string.
 *
 * @throws PayloadTooLargeError when the UTF-8 byte length exceeds 16 KB.
 * @throws PolymarketEventError when any URL has a netloc outside the allowlist.
 */
export function validateDescription(description: string): void {
  if (typeof description !== "string") {
    throw new PolymarketEventError(
      `description must be a string; got ${description === null ? "null" : typeof description}`,
    );
  }
  const byteLen = new TextEncoder().encode(description).length;
  if (byteLen > MAX_DESCRIPTION_BYTES) {
    throw new PayloadTooLargeError(
      `description exceeds 16 KB cap (got ${byteLen} bytes; oversized payloads indicate hostile input)`,
    );
  }
  for (const match of description.matchAll(URL_RE)) {
    const url = match[0];
    let netloc: string;
    try {
      netloc = new URL(url).host.toLowerCase();
    } catch {
      throw new PolymarketEventError(`unparseable resolution-source URL ${JSON.stringify(url)}`);
    }
    if (netloc.length > 0 && !RESOLUTION_SOURCE_ALLOWLIST.has(netloc)) {
      throw new PolymarketEventError(
        `resolution-source URL ${JSON.stringify(url)} not in allowlist [${[
          ...RESOLUTION_SOURCE_ALLOWLIST,
        ]
          .sort()
          .join(", ")}]`,
      );
    }
  }
}

/**
 * Classify a description's resolution source by the first allowlisted netloc
 * found. Returns `"other"` when no allowlisted URL appears (the settlement
 * engine falls back to the 24-hour delay for "other").
 */
export function extractResolutionSourceType(description: string): PolymarketResolutionSourceType {
  for (const match of description.matchAll(URL_RE)) {
    const url = match[0];
    let netloc: string;
    try {
      netloc = new URL(url).host.toLowerCase();
    } catch {
      continue;
    }
    const mapped = NETLOC_TO_RESOLUTION_TYPE[netloc];
    if (mapped !== undefined) {
      return mapped as PolymarketResolutionSourceType;
    }
  }
  return "other";
}
