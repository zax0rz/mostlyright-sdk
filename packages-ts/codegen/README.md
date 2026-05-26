# @mostlyrightmd/codegen

Build-only codegen for the [mostlyright](https://github.com/mostlyrightmd/mostlyright-sdk) TypeScript SDK. Reads the canonical schema artifacts under `schemas/` (emitted by the Python-side `scripts/export_schemas.py`) and produces typed TS modules into the `src/**/generated/` directories of each consumer package. **Private — never published to npm.**

## What it emits

Inputs (read from `<repoRoot>/schemas/`):

- `schemas/json/schema.*.v1.json` — canonical JSON Schemas (observation, forecast.iem_mos, settlement.cli, observation_ledger, observation_qc)
- `schemas/stations.json` — 61-row station registry (20 US + 41 international)
- `schemas/kalshi-settlement-stations.json` — Kalshi 20-city settlement-station map + known-wrong list
- `schemas/source-priority.json` — observation + climate + LIVE_V1 source-priority policy
- `schemas/polymarket-city-stations.json` — Polymarket 40-city map
- `schemas/qc-alpha-rules.json` — alpha QC rules at bit positions 0..4

Outputs:

- `packages-ts/core/src/schemas/generated/*.v1.ts` — TS interfaces compiled via `json-schema-to-typescript`, plus an `index.ts` barrel
- `packages-ts/core/src/data/generated/stations.ts` — `STATIONS`, `STATION_BY_CODE`, `STATION_BY_ICAO`
- `packages-ts/core/src/data/generated/source-priority.ts` — `OBSERVATION_SOURCE_PRIORITY`, `CLIMATE_REPORT_TYPE_PRIORITY`, `LIVE_V1_POLICY`
- `packages-ts/core/src/data/generated/qc-alpha-rules.ts` — `QC_ALPHA_RULES`, `QC_ALPHA_RULES_BY_ID`
- `packages-ts/markets/src/data/generated/kalshi-stations.ts` — `KALSHI_SETTLEMENT_STATIONS`, `KNOWN_WRONG_STATIONS`
- `packages-ts/markets/src/data/generated/polymarket-city-stations.ts` — `POLYMARKET_CITY_STATIONS`
- One `index.ts` barrel per `*/generated/` directory

Every emitted file carries an `// AUTO-GENERATED` header and ends with a single trailing newline (LF). Outputs are deterministic across runs (verified by `pnpm --filter @mostlyrightmd/codegen run codegen:check`).

## How to run

```bash
# Emit all generated files into the consumer packages:
pnpm --filter @mostlyrightmd/codegen run codegen

# Determinism check (runs codegen twice in memory, asserts byte-equality):
pnpm --filter @mostlyrightmd/codegen run codegen:check
```

Also wired as `prebuild` in each consumer package so `pnpm -r run build` regenerates first.

## Why a separate codegen package?

- Keeps consumer packages free of `json-schema-to-typescript` and `ajv-cli` deps — those are dev-only.
- One place to enforce the `AUTO-GENERATED` banner + determinism contract.
- Lets CI run `pnpm --filter @mostlyrightmd/codegen run codegen:check` as a drift gate without booting the whole workspace.
