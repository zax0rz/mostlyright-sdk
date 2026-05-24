// TS-W6 Wave 4 — DataVersion reproducibility token via Web Crypto SHA-256.
//
// Ports Python `tradewinds.discovery.DataVersion.from_components` byte-for-byte:
// the canonical concatenation is `sdkVersion|sortedSchemaIds|sortedSources|codeSha|dataSha`,
// SHA-256 hex of the UTF-8 encoded string is the token.
//
// Web Crypto API is universal in modern runtimes (browser/Node 16+/Workers/Deno/Bun),
// so we use `crypto.subtle.digest` without runtime detection.

/** Immutable reproducibility token stamping a single research() call. */
export interface DataVersion {
  readonly sdkVersion: string;
  readonly schemaIds: ReadonlyArray<string>;
  readonly sources: ReadonlyArray<string>;
  readonly codeSha: string;
  readonly dataSha: string;
  readonly token: string;
}

export interface DataVersionComponents {
  sdkVersion: string;
  schemaIds: ReadonlyArray<string>;
  sources: ReadonlyArray<string>;
  codeSha: string;
  dataSha: string;
}

const HEX = "0123456789abcdef";

function bytesToHex(bytes: Uint8Array): string {
  let out = "";
  for (let i = 0; i < bytes.length; i += 1) {
    const b = bytes[i] as number;
    out += HEX[(b >> 4) & 0xf];
    out += HEX[b & 0xf];
  }
  return out;
}

/**
 * Build a frozen DataVersion from explicit components.
 *
 * Mirrors Python `DataVersion.from_components`: sorts schemaIds + sources
 * INTERNALLY before the canonical hash so input order does not affect the
 * token, but preserves the caller's order on the returned object's
 * `schemaIds` and `sources` arrays. Codex iter-5 P2: prior version sorted
 * the stored arrays alphabetically too, which masked source-priority order
 * (e.g. `awc.live, ghcnh, iem.archive, ...` instead of the canonical
 * `iem.archive, iem.live, awc.live, ghcnh, nws.cli` precedence Python
 * preserves on the tuple).
 */
export async function dataVersionFromComponents(
  components: DataVersionComponents,
): Promise<DataVersion> {
  const sortedSchemaIds = [...components.schemaIds].sort();
  const sortedSources = [...components.sources].sort();
  const canonical = [
    components.sdkVersion,
    sortedSchemaIds.join(","),
    sortedSources.join(","),
    components.codeSha,
    components.dataSha,
  ].join("|");

  const encoded = new TextEncoder().encode(canonical);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  const token = bytesToHex(new Uint8Array(digest));

  return Object.freeze({
    sdkVersion: components.sdkVersion,
    schemaIds: Object.freeze([...components.schemaIds]),
    sources: Object.freeze([...components.sources]),
    codeSha: components.codeSha,
    dataSha: components.dataSha,
    token,
  });
}

/**
 * Build a DataVersion for a research() call. Mirrors Python `DataVersion.for_research`:
 * the codeSha encodes the call signature (`research:STATION:FROM:TO`) and dataSha
 * is supplied by the caller (typically a cache fingerprint).
 *
 * The schema ids + source contract match the v0.1.0 Python SDK exactly so tokens
 * computed in TS match tokens computed in Python for the same inputs.
 */
export async function dataVersionForResearch(args: {
  sdkVersion: string;
  station: string;
  fromDate: string;
  toDate: string;
  dataSha: string;
}): Promise<DataVersion> {
  return dataVersionFromComponents({
    sdkVersion: args.sdkVersion,
    schemaIds: ["schema.observation.v1", "schema.forecast.iem_mos.v1", "schema.settlement.cli.v1"],
    sources: ["iem.archive", "iem.live", "awc.live", "ghcnh", "nws.cli"],
    codeSha: `research:${args.station}:${args.fromDate}:${args.toDate}`,
    dataSha: args.dataSha,
  });
}
