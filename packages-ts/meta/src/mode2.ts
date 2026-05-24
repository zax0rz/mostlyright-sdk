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

import { SourceMismatchError, type SourceMismatchRole } from "@tradewinds/core";

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
