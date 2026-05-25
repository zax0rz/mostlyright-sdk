# mostlyright

Local-first **Python + TypeScript** SDK for quants researching prediction-market weather settlements.

`research(station, from_date, to_date)` returns observations × NWS CLI climate joined on settlement window. No hosted backend; calls AWC, IEM, GHCNh, NWS CLI directly. Local parquet/JSON cache.

## Packages

### Python (PyPI)

| PyPI | Path | v0.1.0 status |
|---|---|---|
| `mostlyright` | [packages/core/](packages/core/) | rc1 ready (operator-gated PyPI publish) |
| `mostlyright-weather` | [packages/weather/](packages/weather/) | rc1 ready |
| `mostlyright-markets` | [packages/markets/](packages/markets/) | rc1 ready (Polymarket stubs; live engine in TS) |

### TypeScript (npm)

| npm | Path | v0.1.0 status |
|---|---|---|
| `@mostlyrightmd/core` | [packages-ts/core/](packages-ts/core/) | TS-W6 shipped; npm publish operator-gated |
| `@mostlyrightmd/weather` | [packages-ts/weather/](packages-ts/weather/) | TS-W2 parity-gate passed |
| `@mostlyrightmd/markets` | [packages-ts/markets/](packages-ts/markets/) | TS-W5 shipped (Polymarket live + Kalshi resolver) |
| `mostlyright` (meta) | [packages-ts/meta/](packages-ts/meta/) | re-exports the three scoped pkgs |

See [`docs/ts-quickstart.md`](docs/ts-quickstart.md) for TS Node/browser quickstart and [`docs/browser-integration.md`](docs/browser-integration.md) for MV3 service-worker / content-script integration.

## Quickstart (alpha1) — <5 minutes

```bash
pip install "mostlyright[parquet]==0.1.0a1" "mostlyright-weather[parquet]==0.1.0a1"
python -c "import mostlyright as tw; print(tw.research('KNYC', '2025-01-06', '2025-01-12').head())"
```

That's it. `research(station, from_date, to_date)` returns a pandas DataFrame;
local parquet cache lives at `$HOME/.mostlyright/cache/` (override with
`TRADEWINDS_CACHE_DIR`); no API keys; no hosted backend.

### Mode 1 — v0.14.1 parity (default)

```python
import mostlyright as tw

df = tw.research(
    station="KNYC",
    from_date="2025-01-01",
    to_date="2025-03-31",
    as_dataframe=True,
)
# DataFrame: one row per settlement date.
# Columns: date, station, cli_high_f, cli_low_f, obs_high_f, obs_low_f, obs_high_at, obs_low_at
# Byte-equivalent to mostlyright==0.14.1's client.pairs(station, from_date, to_date).
```

### Temporal-safety primitives

```python
from datetime import datetime, UTC
from mostlyright.core import (
    TimePoint, KnowledgeView, LeakageDetector, assert_no_leakage,
)

# Filter a DataFrame to only rows visible at as_of (point-in-time safe).
kv = KnowledgeView(df, TimePoint("2025-02-15T00:00:00+00:00"))
visible = kv.dataframe()  # filtered copy; df unchanged

# Or assert no rows leak past the cutoff (raises LeakageError otherwise).
assert_no_leakage(df, TimePoint("2025-02-15T00:00:00+00:00"))
```

### Source-identity validator

```python
from mostlyright.weather.catalog.iem import IEMAdapter
from mostlyright.core import validate_dataframe

# Catalog adapters produce canonical-schema DataFrames with df.attrs["source"]
# already stamped. Validator compares against the schema's pinned source
# (set when mostlyright.core.schemas eager-registers at import).
obs_df = IEMAdapter.from_rows([])  # also works with parsed rows
reg = validate_dataframe(obs_df, schema_id="schema.observation.v1")
print(reg.audit_log())
# [{"event": "registered", "ts": "...", "source": "iem.archive", "rows": 0}]

# Mismatched source raises SourceMismatchError unless you opt out:
obs_df.attrs["source"] = "ghcnh.archive"  # simulating drift
reg = validate_dataframe(
    obs_df,
    schema_id="schema.observation.v1",
    allow_source_drift="manual backfill from GHCNh into the IEM schema",
)
# audit_log now carries both "registered" + "source_drift_allowed" entries.
```

### Kalshi NHIGH/NLOW resolvers

```python
from datetime import date
from mostlyright.markets.catalog import kalshi_nhigh, kalshi_nlow

# Contract IDs follow Kalshi's KHIGH<CITY> / KLOW<CITY> ticker convention.
nhigh = kalshi_nhigh.resolve("KHIGHNYC", date(2025, 1, 15))
print(nhigh.settlement_source, nhigh.settlement_station)
# cli.archive KNYC  -- NOT KLGA / NOT KJFK (Pitfall 1 canary)

# NHIGH and NLOW share the same NWS CLI product; both directions for a
# given city resolve to the same (source, station) -- the contract test
# guards against silent divergence between the two resolvers.
nlow = kalshi_nlow.resolve("KLOWNYC", date(2025, 1, 15))
assert (nhigh.settlement_source, nhigh.settlement_station) == (
    nlow.settlement_source, nlow.settlement_station
)
```

### Why local-first

- No hosted backend → no auth, no rate-limited tier, no vendor lock-in.
- Parquet cache is byte-stable across runs → deterministic backtests.
- Source-identity invariant on every DataFrame → train/infer mismatch fails
  loudly instead of silently corrupting a model.

See [docs/adapters/](docs/adapters/) for per-source notes (timezone gotchas,
DST handling, settlement-station mappings).

### Forecast catalog (Phase 17 — v1.0 headline)

`research(include_forecast=True)` populates forecast columns from IEM MOS
(parity-compatible Mode 1) or per-model NWP (Mode 2 opt-in). Mostlyright
declares a 24-model `schema.forecast_nwp.v1` catalog with the **11 NCEP
models wired end-to-end in v1.0** (HRRR, HRRRAK, GFS, GEFS, GDAS, NBM,
RAP, RRFS, RTMA, URMA, CFS). The remaining 13 ship URL patterns + QC
rules but `forecast_nwp()` raises today: MSC×5 raise
`HistoricalDepthError(archive_depth=None)` (live-only contract);
ECMWF×4 / HAFS / legacy NAM-HREF-HiResW raise
`NwpModelNotAvailableError` until their fetch+decode paths are wired.
Historical backfill via AWS Big Data Program (wired models). See
[`docs/forecasts.md`](docs/forecasts.md) for the full forecast
catalog, wiring-status table, QC rules, and historical-depth schedule.

TypeScript lane: `@mostlyrightmd/weather/forecasts` ships `iemMosForecasts()`
in v1.0; `forecastNwp()` is a v1.0 stub (deferred to v1.1 pending browser
GRIB2 decode maturity).

## Ingest strategies

`tw.weather.obs(...)` smart-routes between three ingest paths depending on
window size, cache warmth, and the `TW_HOSTED_URL` env var:

- **`exact_window`** — small queries, day-granular URL params, ≤ 2 MB cold for a 1mo KNYC query.
- **`warm_cache`** — `research()`-equivalent year-aligned caching; best for repeated overlapping queries.
- **`hosted`** — precomputed-API seam (deferred to v0.2.x).

The default `strategy="auto"` picks the right one for you. See
[`docs/ingest-strategies.md`](docs/ingest-strategies.md) for the full
decision tree and per-strategy cost table.

## Contributing

See [`CLAUDE.md`](CLAUDE.md) for project rules + collaboration discipline. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for workflow. Review discipline: see [`.planning/REVIEW-DISCIPLINE.md`](.planning/REVIEW-DISCIPLINE.md).

## License

MIT. See [`LICENSE`](LICENSE).
