// TS-W3 Plan 04 Task 2 — fast-check property test for KnowledgeView.
//
// This is the TS-W3 SC#3 acceptance criterion: the filter invariant
// `view.rows() ⊆ rows ∧ ∀r∈rows: r.knowledge_time ≤ asOf ⇔ r∈view.rows()`
// must hold over the constrained `[2018-01-01, 2027-12-31]` UTC range with
// at least 200 random runs.

import fc from "fast-check";
import { describe, it } from "vitest";

import { KnowledgeView } from "../../src/temporal/knowledge-view.js";
import { TimePoint } from "../../src/temporal/timepoint.js";

const DATE_RANGE_START = Date.parse("2018-01-01T00:00:00Z");
const DATE_RANGE_END = Date.parse("2027-12-31T23:59:59Z");

const arbDateMs = fc.integer({ min: DATE_RANGE_START, max: DATE_RANGE_END });
const arbRow = arbDateMs.map((ms) => ({
  knowledge_time: new Date(ms).toISOString(),
}));

describe("KnowledgeView property: filter retains only knowledge_time <= asOf", () => {
  it("invariant holds over the [2018-01-01, 2027-12-31] UTC range (200 runs)", () => {
    fc.assert(
      fc.property(fc.array(arbRow, { minLength: 0, maxLength: 100 }), arbDateMs, (rows, asOfMs) => {
        const asOf = new TimePoint(new Date(asOfMs));
        const view = new KnowledgeView(rows, asOf);
        const filtered = view.rows();

        // 1. Every row in `filtered` has knowledge_time <= asOf.
        for (const r of filtered) {
          if (Date.parse(r.knowledge_time) > asOfMs) return false;
        }
        // 2. Every row in `rows` with knowledge_time <= asOf appears in `filtered`.
        //    (Filter completeness — no spurious drops.)
        for (const r of rows) {
          if (Date.parse(r.knowledge_time) <= asOfMs && !filtered.includes(r)) {
            return false;
          }
        }
        return true;
      }),
      { numRuns: 200 },
    );
  });
});
