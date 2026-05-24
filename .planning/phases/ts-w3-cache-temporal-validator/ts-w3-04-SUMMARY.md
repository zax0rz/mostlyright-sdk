---
phase: ts-w3-cache-temporal-validator
plan: 04
subsystem: temporal
tags: [temporal, timepoint, knowledge-view, leakage-detector, fast-check]
status: complete
completed: 2026-05-24
commits:
  - c98d1ef feat(ts-w3/04): TimePoint — UTC-aware timestamp wrapper
  - 188b6f5 feat(ts-w3/04): KnowledgeView + fast-check property test
  - 0861c4c fix(ts-w3/04): cast invalid-shape KnowledgeView test rows through unknown
  - 71b1875 feat(ts-w3/04): assertNoLeakage + LeakageDetector + barrel + subpath export
test_delta: +46 (TimePoint 23 + KnowledgeView 11 unit + 1 property + Leakage 11)
---

# TS-W3 Plan 04: Temporal Primitives Summary

Ported three temporal-safety primitives from Python at
`@tradewinds/core/temporal`: TimePoint, KnowledgeView, LeakageDetector
+ assertNoLeakage.

## What shipped

- **`TimePoint`** (`src/temporal/timepoint.ts`) — UTC-aware timestamp
  wrapper. Rejects naive ISO strings (no Z/offset), date-only ISO
  strings (YYYY-MM-DD), NaN/Infinity Dates, empty/whitespace strings,
  and non-Date/non-string runtime inputs. Accessors: toUTCDate()
  (defensive copy), toISOString() (always Z), asZone(tz), equals,
  before, after, TimePoint.now().
- **`KnowledgeView<Row>`** (`src/temporal/knowledge-view.ts`) — generic
  over `Row extends { knowledge_time: string }`. Eager
  construction-time validation throws SchemaValidationError on any
  invalid knowledge_time. `.rows()` returns a fresh array each call.
- **`assertNoLeakage` + `LeakageDetector`** (`src/temporal/leakage.ts`)
  — throws LeakageError on knowledge_time > asOf. SAMPLE_CAP=10.
  Skips rows with non-string / unparseable knowledge_time (matches
  Python: validation is KnowledgeView's job).
- **Barrel** (`src/temporal/index.ts`) + **subpath export**
  (`./temporal` in package.json + tsup.config.ts).
- **Root re-export** from `src/index.ts` so both
  `@tradewinds/core` and `@tradewinds/core/temporal` paths resolve.

## Key decisions

- **Date vs. ISO string asymmetry.** A JS Date is just epoch ms — no
  timezone metadata. "Naive" only applies to STRING inputs. For Date
  inputs we only reject NaN/Infinity. Documented in the class JSDoc.
- **TZ_SUFFIX regex** (`/(?:Z|[+-]\d{2}:?\d{2})$/`) accepts both
  `+0000` and `+00:00` formats — matches Python's
  `datetime.fromisoformat` tolerance.
- **toDict() snake_case parity.** LeakageError's `toDict()` already
  emitted snake_case (`as_of`, `violating_count`, `sample_violations`)
  from TS-W1; this plan just consumes it without changes.
- **Property test range** capped at `[2018-01-01, 2027-12-31]` UTC per
  TS-W3 SC#3 — 200 random runs, both directions of the filter
  invariant asserted.

## Test count delta

Core: 181 → 227 (+46).

## Follow-ups

None — the plan executed exactly as written. The temporal layer is
ready for consumption by validators (Plan 05) and the orchestrator
(Plan 06).
