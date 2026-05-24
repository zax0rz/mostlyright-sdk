---
phase: 260524-ohu
plan: 01
subsystem: research-docs
tags: [research, ingest, planning, year-normalization, perf]
dependency-graph:
  requires: []
  provides:
    - .planning/research/INGEST-PLANNER-RESEARCH.md
  affects:
    - .planning/research/  # new artifact; no existing doc modified
tech-stack:
  added: []
  patterns: []
key-files:
  created:
    - .planning/research/INGEST-PLANNER-RESEARCH.md
  modified: []
decisions:
  - Part 1 deliverable scoped to a single research doc; Part 2 will use /gsd-add-phase + /gsd-plan-phase to design tw.weather.obs(strategy="auto").
  - Bench script (/tmp/tw_ingest_bench.py) and raw JSON (/tmp/tw_bench_results.json) NOT committed — doc inlines what matters.
  - 1mo cold-time anomaly (69.7s) is called out as one-shot process startup (Python + pandas/pyarrow import + httpx pool warmup), NOT proportional to window size.
metrics:
  duration: ~5min
  completed-date: 2026-05-24
  lines-written: 691
  tasks: 1
  files: 1
requirements:
  - QUICK-260524-ohu
---

# Quick Task 260524-ohu: Write Ingest Planner Research Doc Summary

Authored `.planning/research/INGEST-PLANNER-RESEARCH.md` (691 lines, 6 H2 sections) as Part 1 of a two-part task whose Part 2 will design `tw.weather.obs(strategy="auto")` against the empirical foundation this doc lays down — measured cold/warm timings, the year-normalization deep dive, mutable-period invariants, and five open questions for the planner phase.

## What shipped

A single research artifact: `.planning/research/INGEST-PLANNER-RESEARCH.md` with the six sections specified in the plan:

- **§1 Executive summary** — the headline finding (1mo ≈ 3mo bytes because of IEM year-normalization), 12mo doubling story, warm-is-free invariant, 1mo cold-time-anomaly call-out, forward pointer to `exact_window`.
- **§2 Current architecture (file:line refs)** — every bullet anchored to a path + line range covering the orchestrator (`research.py:876-1024`), prefetch pool (`research.py:650-873`), observation/climate range fetchers, zero-network gate (`_all_caches_warm`, `research.py:626-647`), IEM ASOS fetcher (incl. year-normalization at `iem_asos.py:204-209`), AWC/GHCNh/CLI one-liners, parquet cache layout + atomic-write semantics (`cache.py:230-253`), and mutable-period invariants (`_is_writable_month` + LST-current cache predicates).
- **§3 Empirical timing** — methodology, results (the bench JSON transcribed into a fenced block + a compact summary table), five interpretive bullets each tied to a specific number from the results. The 1mo cold-time anomaly is explicitly explained as one-time interpreter/pandas/pyarrow/httpx-pool warmup so future readers don't misread the data.
- **§4 Year-normalization deep dive** — quoted code blocks for `iem_asos.py:197-209`, the mostlyright PR #85 lift rationale, the cost on small one-off windows (~13 MB for a 1-month query), and the parity-safety note (year-normalization is cache-shape-only; the `_observed_at_month` post-parse filter keeps merge composition byte-stable).
- **§5 Auto-planner mode design constraints** — `exact_window`, `warm_cache`, `hosted` (v0.2 seam), and `source="iem"` single-source paths, plus the non-negotiable mutable-period invariants every mode must honor.
- **§6 Open questions for Part 2** — five concrete decisions: where `obs()` lives, the `strategy="auto"` decision tree, mutable-period interaction with `exact_window`, the `source=` keyword shape (string vs set), and the `research()` → `obs()` migration path (wrapper vs independent).

## Empirical findings inlined in the doc

| Case | Window | Cold (s) | Warm (s) | Cold ΔMB | Rows |
|------|--------|---------:|---------:|---------:|-----:|
| 1mo  | 2024-03-01..2024-03-31 | 69.70 | 4.72 | 13.43 | 31  |
| 3mo  | 2024-03-01..2024-05-31 | 10.17 | 0.35 | 13.54 | 92  |
| 12mo | 2024-01-01..2024-12-31 | 23.69 | 0.56 | 26.01 | 366 |

The single most-important finding: **1mo and 3mo cold downloads transfer essentially the same bytes (13.43 MB vs 13.54 MB)** because the IEM ASOS fetcher year-normalizes the request window. Small windows do NOT shrink network footprint under current behavior — this is the load-bearing motivation for a Part-2 `strategy="exact_window"` mode.

The 12mo case doubles bytes (26.01 MB) only because `extended_to=2025-01-01` (research.py:968 — `to_date + 1 day` for the LST-tail capture) spills the observation fetch into year 2, forcing a second IEM yearly chunk + a second GHCNh PSV.

Warm re-fetch is free (`delta_bytes=0`) for every window size — `_all_caches_warm` (research.py:626-647) gates the zero-network path. Warm wall-times of 0.35s/0.56s reflect pyarrow parquet reads + the `build_pairs` join, not HTTP.

## Deviations from Plan

None — plan executed exactly as written.

## Files

- **Created:** `.planning/research/INGEST-PLANNER-RESEARCH.md` (691 lines)
- **Modified:** none
- **NOT committed (intentional, per plan constraints):** `/tmp/tw_ingest_bench.py`, `/tmp/tw_bench_results.json`, `/tmp/tw_bench_progress.log`

## Verification

- File exists at `.planning/research/INGEST-PLANNER-RESEARCH.md`: PASS
- Six H2 sections (`## §1` .. `## §6`): PASS
- `iem_asos.py:204-209` cited: PASS
- `research.py:316-333` cited: PASS
- `13.43 MB` present in results block: PASS
- At least one mention of `exact_window`: PASS (multiple, including §5.1 and the Part-2 decision tree in §6)
- Length 300-800 lines: PASS (691)
- No code changes to `research.py`, fetchers, or `cache.py`: PASS
- Bench script + raw JSON not committed: PASS

## Commit

- `26c80b1` — `docs(quick-260524-ohu): write ingest planner research doc — empirical timings + year-normalization findings`

## Self-Check: PASSED

- File `.planning/research/INGEST-PLANNER-RESEARCH.md`: FOUND
- Commit `26c80b1`: FOUND in git log
