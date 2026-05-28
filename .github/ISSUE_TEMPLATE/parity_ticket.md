---
name: Parity Ticket
about: Track a cross-SDK port (Python <-> TypeScript) per CROSS-SDK-SYNC.md §2
title: '[Parity] '
labels: parity-ticket
---

# Parity Ticket PT-NNNN — <short title>

**Type:** [SCHEMA | FUNCTION | BEHAVIOR | EXCEPTION | ENDPOINT | DATA]
**Direction:** [PYTHON_TO_TS | TS_TO_PYTHON]
**Canonical PR:** #<number> (the PR landing the change in the source language)
**Target SDK:** [mostlyright-ts | mostlyrightmd]
**Filed by:** @<author of canonical PR>
**Assigned to:** @<author of parity PR — defaults to canonical PR author unless explicitly handed off>
**Filed:** YYYY-MM-DD
**Milestone:** [TS v0.1.0 | TS v0.1.x | Python v0.2 | ...]
**Priority:** [P0 (release-blocker) | P1 (next-release) | P2 (eventual)]

## What changed in the canonical SDK

<1-3 sentences. Link to the canonical PR.>

## Exact surface delta

```diff
- old signature / old behavior
+ new signature / new behavior
```

## Why it must port

<Trust gate. e.g.: "TS users hitting the same API would get inconsistent rows
without this fix" or "schema column added is consumed by the Chrome extension
overlay">.

## Port scope

- [ ] Function signature port
- [ ] Test parity (recorded fixture against canonical output)
- [ ] Documentation update
- [ ] Bundle-size verification (if TS) / METADATA verification (if Python)
- [ ] Drift fixture rotation (if behavioral change affects parity gate)

## Verification checklist

- [ ] Generated codegen output unchanged OR regenerated + reviewed
- [ ] Behavior tested against shared fixture under `tests/fixtures/parity/` or `tests/fixtures/parity-ts/`
- [ ] CHANGELOG / `.changeset/*.md` entry in target language
- [ ] Cross-link added to canonical PR body once parity PR opens

## Release-readiness gate

This parity ticket is one of the things that blocks the next minor release of
the target SDK. Counted by `scripts/parity_status.py` (lists open parity
tickets per milestone) in the release checklist.
