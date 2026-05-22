# Sprint 0 Validation — N=3 Yes Signal Tracking

**Sprint 0 ships `tradewinds` + `tradewinds-weather` v0.1.0 to PyPI on Day 4. N=3 yes signals from named quants within 7 days of release gates Sprint 0.5.**

## N=3 "yes" rubric

A response counts as "yes" only if ALL three are true:

1. User installed `tradewinds*` on their own machine (verifiable: ask them to share their `pip list | grep tradewinds`).
2. They ran the quickstart against their own data within 7 days of release.
3. They responded with a concrete commitment — either:
   - "I'll switch from v0.14.1 to this for [specific work] this month," OR
   - "I'll build [specific feature] on top of this in [specific timeframe]."

NOT counted as yes:
- "Looks interesting"
- "I'll check it out later"
- "Nice work"
- Silence past 7 days
- "Would use it but not sure when"

## Contacts

### Quant 1 — Vojtech ✓ Day 0 yes

- Day 0 status: ✓ confirmed switching from v0.14.1 architecturally
- Day 4 message sent: [ ]
- Installed: [ ]
- Quickstart ran: [ ]
- Concrete commitment (per rubric): [ ]
- Quote: ___

### Quant 2 — TBD name

Source: 03-31 design doc mentions multiple users who reported data quality issues directly. Surface the name from that pool before Day 4.

- Identified: [ ] (name: ___)
- Day 4 message sent: [ ]
- Installed: [ ]
- Quickstart ran: [ ]
- Concrete commitment (per rubric): [ ]
- Quote: ___

### Quant 3 — TBD name

Source: Vojtech's network — he agreed on Day 0 to make an intro. Get the name from him before Day 4.

- Identified: [ ] (name: ___)
- Intro received from Vojtech: [ ]
- Day 4 message sent: [ ]
- Installed: [ ]
- Quickstart ran: [ ]
- Concrete commitment (per rubric): [ ]
- Quote: ___

## Yes count

Update as responses come in: **0 / 3**

Deadline: Day 4 + 7 calendar days.

## Decision matrix

| Yes count by Day 11 | Decision |
|---|---|
| 3 of 3 | Sprint 0.5 starts. Vu writes Kalshi metadata lift from `therminal/therminal-ingest/src/sources/kalshi/`. Founder does second-round outreach to grow N beyond 3. |
| 2 of 3 | Hold for 3 more days, then decide. If still 2 at Day 14, treat as "soft yes" — proceed to Sprint 0.5 but flag risk. |
| 1 of 3 (Vojtech only) | STOP, debrief. The pivot is still N=1. Consider Approach C (in-place mostlyright v0.15) per design doc Open Question #8. Re-open the diagnostic. |
| 0 of 3 | STOP, full retrospective. Either Vojtech changed his mind too, or the outreach quants weren't the right pool. Revisit demand evidence. |

## YC re-application path

If N=3 → in 30 days follow up: did anyone START PAYING for a hypothetical paid tier (live endpoints with SLA, premium curated datasets)? The YC re-application needs N=3+ paying users + paid-tier definition. Free SDK adoption is necessary but not sufficient.
