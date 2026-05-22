# `_v02/` split-out follow-up PR

**Status:** scheduled. Removed from `merged-vision` in PR #2 fix branch `fix/pr2-rob-blockers` per Rob's review (H6).

## Why split

Rob's PR #2 review flagged that `packages/core/src/tradewinds/_v02/` (~1500 LOC across 17 files + ~750 LOC test in `test_formats.py`) is high-quality forward-port code with **zero callers** from `_internal/` or `weather/`. Including it in the parity-gate PR:
- Bloated the diff (`_v02` was most of the +30k line count).
- Confused reviewers — `_v02/__init__.py` even says "NOT used by Sprint 0 ... safe to ignore until then."
- Mixed two distinct review surfaces: the Sprint 0 + Phase 1 Wave 1 lift work AND a separate v0.2 foundations forward-port.

The split keeps PR #2 focused on its title and gives `_v02` its own focused review.

## What got removed

Directories:
- `packages/core/src/tradewinds/_v02/` (entire subtree)
- `packages/core/tests/_v02/` (entire subtree)

The `_toon.py` encoder was NOT removed — it was lifted independently to `packages/core/src/tradewinds/_internal/_toon.py` (Rob's C3 fix). `snapshot.to_toon()` and `_base.to_toon()` now point at `_internal/_toon.py`. Both call sites continue to work after the split.

## Commits to cherry-pick into the follow-up branch

Per `git log --all --oneline -- 'packages/core/src/tradewinds/_v02/' 'packages/core/tests/_v02/'`:

```
650a30e feat(v02): add hypothesis to workspace dev deps for v0.2 foundations port
43a001a feat(v02): scaffold _v02 package + tests dir for wave-1-core port
7292769 feat(v02): port JSON-safe encoder from mostlyright-mcp wave-1-core
3f62c84 feat(v02): port exception hierarchy from mostlyright-mcp wave-1-core
9b06838 test(v02): port exception + encoder tests from mostlyright-mcp wave-1-core
7dac72e feat(v02): port Schema base + ColumnSpec + SchemaRegistration from mostlyright-mcp wave-1-core
d430bae feat(v02): port ObservationSchema with metric/imperial column contract
b244813 feat(v02): port ForecastSchema (subset of mostlyright FORECAST_FIELDS)
6f8bd21 feat(v02): port SettlementSchema with station_tz
61ac78a test(v02): port schema contract tests from mostlyright-mcp wave-1-core
b2f24de style(v02): apply ruff auto-fixes (UP017/UP037/I001/RUF022 etc.)
993d2a3 style(v02): add ClassVar annotations to schema subclass attributes
2957eea style(v02): sort imports in test_schema.py
72e2ffc feat(v02): port TimePoint UTC-aware wrapper from mostlyright-mcp wave-1-core
6fd0535 test(v02): port TimePoint property + DST + edge-case tests
f337e59 feat(v02): port TOON serializer (lifted via mostlyright-mcp wave-1-core)
b844676 feat(v02): port format converters (dataframe, json, parquet, csv)
5c943a1 feat(v02): port TOON DataFrame wrapper with documented losses
755cd5b test(v02): port format roundtrip + loss-documentation tests
8562e92 Merge port/v02-timepoint into feat/v0.2-foundations
c3a4be8 Merge port/v02-schema into feat/v0.2-foundations
7effe5e Merge port/v02-formats into feat/v0.2-foundations
```

## When to land the follow-up

**Hard dependency from Phase 2.** `.planning/phase-02-core-primitives-catalog-adapters/PLAN.md` Wave 1 (`phase-2/wave-1-rebrand`) plans to `git mv packages/core/src/tradewinds/_v02/` to `packages/core/src/tradewinds/core/`. Phase 2 cannot start without `_v02/` present. Sequencing:

1. PR #2 (`merged-vision -> main`) merges with the split applied.
2. `feature/v0.2-foundations-port` branch reassembles `_v02/` via cherry-picks above; opens new PR to `merged-vision`.
3. Follow-up PR review passes the two-reviewer loop.
4. Follow-up PR merges to `merged-vision`.
5. Phase 2 Wave 1 (`phase-2/wave-1-rebrand`) begins from `merged-vision` with `_v02/` in place.

No version bumps or PyPI publishes occur between PR #2 merge and the follow-up merge.

## Pointer

When the follow-up PR opens, link it from this file. Until then this note IS the bookmark.
