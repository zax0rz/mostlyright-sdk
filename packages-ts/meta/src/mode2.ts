// Mode 2 — source-explicit research() variant.
//
// Mirrors packages/core/src/tradewinds/mode2.py. Mode 1 (the existing
// `research()`) merges AWC > IEM > GHCNh; Mode 2 lets the caller pin
// observations to a single named source for source-identified
// training pairs (the workflow Vojtech wanted for backtests that
// need source-identity invariants).
//
// Lives in @tradewinds/meta (alongside `research()`), NOT in
// @tradewinds/core — `assertSourceIdentity` consumes the
// @tradewinds/weather `Observation` type, which @tradewinds/core
// must not depend on (would create a cycle).
//
// ── Vocabulary ───────────────────────────────────────────────────────
// TS narrows what Python widens: at the input boundary, TS accepts
// ONLY the four canonical dotted-form sources. Bare forms (`iem`,
// `awc`, `ghcnh`) are NEVER accepted at the API; they only ever
// appear as parser-emitted PER-ROW source tags. The alias table
// (`SOURCE_ALIASES`) bridges the boundary: filter rows whose bare
// tag is in the dotted source's alias set, but NEVER rewrite the
// per-row source — that would silently corrupt downstream Validator
// invariants. See Python mode2.py:161-166 for the canonical comment.

import {
  NotFoundError,
  STATION_BY_CODE,
  STATION_BY_ICAO,
  SourceMismatchError,
  type SourceMismatchRole,
} from "@tradewinds/core";
import {
  type Observation,
  awcToObservation,
  downloadGhcnh,
  downloadIemAsos,
  fetchAwcMetars,
  parseGhcnhPsv,
  parseIemCsv,
} from "@tradewinds/weather";

export type { SourceMismatchRole };

/** Mode 2 canonical source vocabulary. Exactly four dotted values. */
export const MODE2_SOURCES = ["iem.archive", "iem.live", "awc.live", "ghcnh.archive"] as const;

/**
 * Mode 2 source-identity type. Const-union derived from the
 * `MODE2_SOURCES` tuple-literal (NOT a TS `enum` — `enum` defeats
 * tree-shaking per TS Architect rubric §5).
 */
export type Mode2Source = (typeof MODE2_SOURCES)[number];

/**
 * Map each canonical dotted source to the bare parser-emitted tags
 * that satisfy it. Parsers emit bare `iem`/`awc`/`ghcnh` per
 * packages-ts/weather; tradewinds' canonical vocab is dotted. The
 * alias table bridges both at the boundary without rewriting the
 * per-row source — downstream consumers see the truthful
 * parser-emitted tag.
 *
 * Mirrors packages/core/src/tradewinds/mode2.py:55-63.
 */
export const SOURCE_ALIASES: ReadonlyMap<Mode2Source, ReadonlySet<string>> = new Map<
  Mode2Source,
  ReadonlySet<string>
>([
  ["iem.archive", new Set(["iem", "iem.archive"])],
  ["iem.live", new Set(["iem", "iem.live"])],
  ["awc.live", new Set(["awc", "awc.live"])],
  ["ghcnh.archive", new Set(["ghcnh", "ghcnh.archive"])],
]);

/**
 * Type-guard: narrow an unknown value to {@link Mode2Source}. Returns
 * true iff `value` is one of the four canonical dotted strings.
 * Bare-form inputs (`'iem'`, `'awc'`, `'ghcnh'`) return false — TS
 * narrows what Python widens.
 */
export function isMode2Source(value: unknown): value is Mode2Source {
  return typeof value === "string" && (MODE2_SOURCES as readonly string[]).includes(value);
}

/**
 * Throw {@link SourceMismatchError} if any row's `source` field
 * disagrees with the expected source vocabulary. Rows missing the
 * `source` field (undefined / null / non-string) are skipped
 * (matches Python mode2.py:181-182 — `if "source" not in df.columns:
 * return`). Empty `rows` passes silently.
 *
 * The `expected` parameter accepts EITHER:
 *
 *  - a single string — the most common case; downstream callers
 *    can pass `"iem.archive"` and the check is `src === "iem.archive"`.
 *  - a `ReadonlySet<string>` — used by `researchBySource` to pass
 *    the {@link SOURCE_ALIASES} entry so bare-form parser tags
 *    (`'iem'`) are accepted alongside the dotted canonical form
 *    (`'iem.archive'`). Without this, the per-row source-preserved
 *    invariant (Python mode2.py:161-166) would force the assertion
 *    to fire on every Mode 2 call.
 *
 * @param rows           rows to check (any shape with `source?: string`)
 * @param expected       the source string OR alias-set the caller asked for
 * @param role           role-name vocabulary; defaults to 'observations'
 *
 * @throws SourceMismatchError  with `schemaSource` = the expected label
 *                              (the input string, or `[...accept].sort().join("|")`
 *                              when an alias-set was passed), `dataSource` =
 *                              first sorted distinct mismatched source,
 *                              `role` = the caller-provided role,
 *                              `catalogWarning` = null.
 */
export function assertSourceIdentity<Row extends { source?: string | null | undefined }>(
  rows: ReadonlyArray<Row>,
  expected: string | ReadonlySet<string>,
  role: SourceMismatchRole = "observations",
): void {
  const accept: ReadonlySet<string> =
    typeof expected === "string" ? new Set<string>([expected]) : expected;
  const expectedLabel: string =
    typeof expected === "string" ? expected : [...accept].sort().join("|");

  const distinct = new Set<string>();
  let bad = 0;
  for (const r of rows) {
    const src = r?.source;
    if (typeof src !== "string") continue;
    if (!accept.has(src)) {
      distinct.add(src);
      bad += 1;
    }
  }
  if (bad === 0) return;
  const others = [...distinct].sort();
  const first = others[0] ?? "<unknown>";
  throw new SourceMismatchError(
    `Mode 2 dispatch requested '${expectedLabel}' but received ${bad} row(s) with other sources: [${others
      .map((s) => `'${s}'`)
      .join(", ")}]`,
    {
      schemaSource: expectedLabel,
      dataSource: first,
      role,
      catalogWarning: null,
    },
  );
}

// ---------------------------------------------------------------------------
// researchBySource — Mode 2 dispatch entry point
// ---------------------------------------------------------------------------

/** Mode 2 caller-supplied options. Subset of `ResearchOptions` — Mode 2
 *  returns observations only, so forecast + climate + cache opts are
 *  intentionally excluded. */
export interface ResearchBySourceOptions {
  /** Forward to the underlying fetcher; aborts the dispatch. */
  signal?: AbortSignal;
  /** AWC lookback window in hours (clamped by the fetcher). Default 168. */
  awcHours?: number;
  /** Polite-delay (ms) between IEM ASOS yearly chunks. Default 1000. */
  iemPolitenessMs?: number;
}

/** AWC live serves at most ~168 hours (7 days). Mirrors research.ts. */
const AWC_MAX_HOURS = 168;

interface ResolvedStation {
  readonly code: string;
  readonly icao: string;
  readonly country: string | null;
  readonly ghcnhId: string | null;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Resolve a station identifier (3-letter NWS code OR 4-letter ICAO)
 * to the full record. Inlined here instead of imported from `research.ts`
 * to keep mode2 self-contained — the ~30-line duplication is cheaper
 * than threading internal helpers through a new module boundary.
 */
function resolveStation(input: string): ResolvedStation {
  const raw = input.trim().toUpperCase();
  if (raw.length === 0) {
    throw new Error("station must be a non-empty string");
  }
  const byIcao = STATION_BY_ICAO.get(raw);
  if (byIcao !== undefined) {
    if (byIcao.code === null) {
      throw new Error(`station ${JSON.stringify(raw)} has no 3-letter NWS code`);
    }
    return {
      code: byIcao.code,
      icao: byIcao.icao,
      country: byIcao.country,
      ghcnhId: byIcao.ghcnh_id,
    };
  }
  const byCode = STATION_BY_CODE.get(raw);
  if (byCode !== undefined) {
    if (byCode.code === null) {
      throw new Error(`station ${JSON.stringify(raw)} has no 3-letter NWS code`);
    }
    return {
      code: byCode.code,
      icao: byCode.icao,
      country: byCode.country,
      ghcnhId: byCode.ghcnh_id,
    };
  }
  if (raw.startsWith("K") && raw.length === 4) {
    const stripped = raw.slice(1);
    const retry = STATION_BY_CODE.get(stripped);
    if (retry !== undefined && retry.code !== null) {
      return {
        code: retry.code,
        icao: retry.icao,
        country: retry.country,
        ghcnhId: retry.ghcnh_id,
      };
    }
  }
  throw new Error(
    `unknown station ${JSON.stringify(input)} — not found in STATION_BY_CODE or STATION_BY_ICAO`,
  );
}

function validateDateFormat(label: string, value: string): void {
  if (!DATE_RE.test(value)) {
    throw new Error(`${label} must be YYYY-MM-DD, got ${JSON.stringify(value)}`);
  }
}

/**
 * Year extracted from a YYYY-MM-DD string. Caller must validate format
 * first via `validateDateFormat`.
 */
function yearOf(isoDate: string): number {
  return Number(isoDate.slice(0, 4));
}

/**
 * Mode 2 source-explicit observation fetch.
 *
 * Dispatches to a single source's fetcher (no merge) and returns raw
 * {@link Observation}s tagged with that source. Mirrors Python
 * `tradewinds.mode2.research_by_source` (packages/core/src/tradewinds/mode2.py).
 *
 * The four supported sources:
 *
 *  - `'iem.archive'` → IEM ASOS historical CSVs (METAR + SPECI).
 *  - `'iem.live'`    → v0.1.0 parity gap; throws. Use `'iem.archive'`.
 *  - `'awc.live'`    → AWC live METAR JSON (≤168h lookback).
 *  - `'ghcnh.archive'` → NCEI GHCNh PSV (US stations only).
 *
 * The returned rows preserve the parser-emitted per-row `source` field
 * verbatim — NEVER rewritten to the dotted canonical form. Bare tags
 * (`'iem'`, `'awc'`, `'ghcnh'`) survive intact so downstream Validator
 * schemas see the truthful provenance. Mode 2 still calls
 * {@link assertSourceIdentity} internally (defense-in-depth) before
 * returning — using the {@link SOURCE_ALIASES} entry so the bare-form
 * tags pass.
 *
 * @param station    NWS 3-letter code (e.g. `"NYC"`) OR 4-letter ICAO (e.g. `"KNYC"`).
 * @param source     One of {@link MODE2_SOURCES}.
 * @param fromDate   Inclusive start, ISO `YYYY-MM-DD`.
 * @param toDate     Inclusive end, ISO `YYYY-MM-DD`.
 * @param opts       See {@link ResearchBySourceOptions}.
 *
 * @returns Frozen array of {@link Observation}s whose `source` is in
 *          `SOURCE_ALIASES.get(source)`. Empty array on no data
 *          (NOT a throw).
 *
 * @throws Error              if `source` is not one of {@link MODE2_SOURCES}.
 *                            Throws BEFORE any network call — no quota burn
 *                            on invalid input.
 * @throws Error              if `source === 'iem.live'` (v0.1.0 parity gap;
 *                            v0.2 will add per-month live IEM).
 * @throws Error              if `station` is unknown, or dates are malformed.
 * @throws NotFoundError      if `source === 'ghcnh.archive'` and `station`
 *                            is non-US (GHCNh PSV files are US-only).
 * @throws SourceMismatchError if a row's `source` disagrees with the alias
 *                             set for `source` (defense-in-depth; should
 *                             never fire under correct fetcher behavior).
 */
export async function researchBySource(
  station: string,
  source: Mode2Source,
  fromDate: string,
  toDate: string,
  opts: ResearchBySourceOptions = {},
): Promise<ReadonlyArray<Observation>> {
  // ── Synchronous-style guards (BEFORE any network call) ────────────
  // Architect rubric: unknown-source rejection MUST run before any
  // fetcher import/call (else invalid input burns API quota).
  if (!isMode2Source(source)) {
    throw new Error(
      `Mode 2 source must be one of ${JSON.stringify(
        MODE2_SOURCES,
      )}; got ${JSON.stringify(source)}`,
    );
  }
  if (source === "iem.live") {
    throw new Error(
      "Mode 2 source 'iem.live' not yet implemented in v0.1.0 " +
        "(Parity-Ticket: requires per-month live IEM endpoint not yet ported). " +
        "Use 'iem.archive' for historical IEM rows.",
    );
  }
  validateDateFormat("fromDate", fromDate);
  validateDateFormat("toDate", toDate);
  if (fromDate > toDate) {
    throw new Error(`fromDate (${fromDate}) must be <= toDate (${toDate})`);
  }
  const resolved = resolveStation(station);

  const accept = SOURCE_ALIASES.get(source);
  if (accept === undefined) {
    // Unreachable — isMode2Source guard above guarantees a hit.
    throw new Error(`internal: no SOURCE_ALIASES entry for '${source}'`);
  }

  // ── Per-source dispatch ──────────────────────────────────────────
  let rows: ReadonlyArray<Observation>;
  switch (source) {
    case "awc.live": {
      const awcOpts: { hours: number; signal?: AbortSignal } = {
        hours: opts.awcHours ?? AWC_MAX_HOURS,
      };
      if (opts.signal !== undefined) awcOpts.signal = opts.signal;
      const raw = await fetchAwcMetars([resolved.icao], awcOpts);
      const parsed: Observation[] = [];
      for (const m of raw) {
        const obs = awcToObservation(m);
        if (obs !== null) parsed.push(obs);
      }
      rows = parsed;
      break;
    }
    case "iem.archive": {
      const fromYear = yearOf(fromDate);
      const toYear = yearOf(toDate);
      const collected: Observation[] = [];
      for (let year = fromYear; year <= toYear; year++) {
        for (const reportType of [3, 4] as const) {
          const iemOpts: {
            reportType: 3 | 4;
            politenessMs: number;
            signal?: AbortSignal;
          } = {
            reportType,
            politenessMs: opts.iemPolitenessMs ?? 1000,
          };
          if (opts.signal !== undefined) iemOpts.signal = opts.signal;
          const chunks = await downloadIemAsos(
            resolved.code,
            `${year}-01-01`,
            `${year}-12-31`,
            iemOpts,
          );
          for (const chunk of chunks) {
            const parsed = parseIemCsv(chunk.csv, {
              observationTypeOverride: reportType === 3 ? "METAR" : "SPECI",
            });
            collected.push(...parsed);
          }
        }
      }
      // Filter to the queried [fromDate, toDate] window (inclusive).
      rows = collected.filter((r) => {
        const d = r.observed_at.slice(0, 10);
        return d >= fromDate && d <= toDate;
      });
      break;
    }
    case "ghcnh.archive": {
      // GHCNh PSV files are US-only. Non-US stations are advertised by
      // null `ghcnh_id` and country !== "US" in the codegen.
      if (resolved.country !== "US" || resolved.ghcnhId === null || resolved.ghcnhId.length === 0) {
        throw new NotFoundError(
          `GHCNh archive is US-only; station ${JSON.stringify(station)} ` +
            `(country=${resolved.country ?? "null"}, ghcnh_id=${
              resolved.ghcnhId === null ? "null" : JSON.stringify(resolved.ghcnhId)
            }) has no GHCNh coverage`,
        );
      }
      const fromYear = yearOf(fromDate);
      const toYear = yearOf(toDate);
      const collected: Observation[] = [];
      for (let year = fromYear; year <= toYear; year++) {
        const ghcnhOpts: { signal?: AbortSignal } = {};
        if (opts.signal !== undefined) ghcnhOpts.signal = opts.signal;
        try {
          const yr = await downloadGhcnh(resolved.ghcnhId, year, ghcnhOpts);
          const parsed = parseGhcnhPsv(yr.psv);
          for (const r of parsed) {
            if (r.station_code === resolved.code) collected.push(r);
          }
        } catch (err) {
          // 404 = no data for this station-year (typical for partial /
          // pre-1973 years). Mirrors Python research.py 404-as-skip.
          if (err instanceof NotFoundError) continue;
          throw err;
        }
      }
      rows = collected.filter((r) => {
        const d = r.observed_at.slice(0, 10);
        return d >= fromDate && d <= toDate;
      });
      break;
    }
    // iem.live is rejected above; the type narrowing here is
    // exhaustive over Mode2Source minus iem.live (which is unreachable).
  }

  // ── Filter to the alias set (Python parity: row keep iff parser-tag in alias) ──
  // biome-ignore lint/style/noNonNullAssertion: rows is assigned in every reachable case
  const filtered = rows!.filter((r) => accept.has(r.source));

  // ── Defense-in-depth: assertSourceIdentity (Python mode2.py:173-193) ────
  // Empty result still passes (no rows → no mismatch).
  assertSourceIdentity(filtered, accept, "observations");

  return filtered;
}
