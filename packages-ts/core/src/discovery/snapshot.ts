// TS-W6 Wave 3 — DataSnapshot + buildSnapshot.
//
// Frozen, JSON-safe immutable record of a research() result with provenance.
// `toDict()` returns the JSON-safe payload (cycles + non-finite numbers
// handled by `toJsonSafe`); `toToon()` serializes as a TOON tabular block
// via the existing `toonDumps` encoder.

import { toJsonSafe } from "../exceptions/index.js";
import { toonDumps } from "../formats/toon.js";

import type { DataVersion } from "./data-version.js";

/** Frozen snapshot wrapper around row data + provenance. */
export interface DataSnapshot {
  /** ISO 8601 UTC instant when the snapshot was built (always ends with Z). */
  readonly knowledgeTime: string;
  /** Schema id the rows conform to. */
  readonly schemaId: string;
  /** Source identifier (e.g. `iem.archive`, `awc.live`). Snapshot-scoped. */
  readonly source: string;
  /** Row payload — opaque to this layer. Frozen. */
  readonly rows: ReadonlyArray<Readonly<Record<string, unknown>>>;
  /** Optional reproducibility token. */
  readonly dataVersion: DataVersion | null;
  /** Optional arbitrary metadata. JSON-safe-coerced on `toDict`. */
  readonly metadata: Readonly<Record<string, unknown>>;
  /** JSON-safe dict form. */
  toDict(): Record<string, unknown>;
  /** TOON-v3 tabular form (rows only — provenance lives in the dict form). */
  toToon(): string;
}

export interface BuildSnapshotOptions {
  schemaId: string;
  source: string;
  rows: ReadonlyArray<Record<string, unknown>>;
  knowledgeTime?: Date | string;
  dataVersion?: DataVersion | null;
  metadata?: Record<string, unknown>;
}

function normalizeKnowledgeTime(value: Date | string | undefined): string {
  if (value === undefined) {
    return new Date().toISOString();
  }
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      throw new RangeError("buildSnapshot: knowledgeTime is an invalid Date");
    }
    return value.toISOString();
  }
  // String: parse + re-emit so the result is always canonical ISO with Z.
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) {
    throw new RangeError(
      `buildSnapshot: knowledgeTime ${JSON.stringify(value)} is not a parseable ISO 8601 timestamp`,
    );
  }
  return new Date(ms).toISOString();
}

function freezeRows(
  rows: ReadonlyArray<Record<string, unknown>>,
): ReadonlyArray<Readonly<Record<string, unknown>>> {
  const out: Readonly<Record<string, unknown>>[] = [];
  for (const r of rows) {
    out.push(Object.freeze({ ...r }));
  }
  return Object.freeze(out);
}

/**
 * Build a frozen DataSnapshot.
 *
 * Throws RangeError on invalid `knowledgeTime`. Row payloads are shallow-
 * cloned and frozen so callers can't mutate snapshot state post-build.
 */
export function buildSnapshot(opts: BuildSnapshotOptions): DataSnapshot {
  if (typeof opts.schemaId !== "string" || opts.schemaId.length === 0) {
    throw new RangeError("buildSnapshot: schemaId must be a non-empty string");
  }
  if (typeof opts.source !== "string" || opts.source.length === 0) {
    throw new RangeError("buildSnapshot: source must be a non-empty string");
  }
  if (!Array.isArray(opts.rows)) {
    throw new RangeError("buildSnapshot: rows must be an array");
  }

  const knowledgeTime = normalizeKnowledgeTime(opts.knowledgeTime);
  const rows = freezeRows(opts.rows);
  const dataVersion = opts.dataVersion ?? null;
  const metadata = Object.freeze({ ...(opts.metadata ?? {}) });

  const snapshot: DataSnapshot = {
    knowledgeTime,
    schemaId: opts.schemaId,
    source: opts.source,
    rows,
    dataVersion,
    metadata,
    toDict(): Record<string, unknown> {
      // `toJsonSafe` handles cycles + non-finite numbers + Dates. DataVersion
      // is a plain dict-shaped object already, so it round-trips cleanly.
      return toJsonSafe({
        knowledge_time: knowledgeTime,
        schema_id: opts.schemaId,
        source: opts.source,
        rows,
        data_version: dataVersion,
        metadata,
      }) as Record<string, unknown>;
    },
    toToon(): string {
      // TOON encodes a tabular block (rows-only). The header (schema id,
      // source, knowledge time, data version) lives in `toDict()`. Callers
      // that want the full snapshot in TOON wrap toDict output themselves.
      return toonDumps(rows as unknown as Array<Record<string, unknown>>);
    },
  };

  return Object.freeze(snapshot);
}
