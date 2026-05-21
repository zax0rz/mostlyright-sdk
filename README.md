# tradewinds

Local-first Python SDK for quants researching prediction-market weather settlements.

`tradewinds.research(station, from_date, to_date)` returns observations × NWS CLI climate joined on settlement window. No hosted backend; calls AWC, IEM, GHCNh, NWS CLI directly. Local parquet cache.

🚧 **Sprint 0 in progress.** v0.1.0 ships in ~3-4 calendar days (target: 2026-05-25). See [`roadmap/sprint0.md`](roadmap/sprint0.md) for status.

## Packages

| PyPI | Path | Sprint 0 status |
|---|---|---|
| `tradewinds` | [packages/core/](packages/core/) | v0.1.0 — meta + `research()` |
| `tradewinds-weather` | [packages/weather/](packages/weather/) | v0.1.0 — AWC/IEM/GHCNh/NWS CLI clients + cache |
| `tradewinds-markets` | [packages/markets/](packages/markets/) | v0.0.1 placeholder; v0.1.0 in Sprint 0.5 (Kalshi metadata) |

## Quickstart (post-v0.1.0)

```bash
pip install "tradewinds[parquet]" "tradewinds-weather[parquet]"
```

```python
import tradewinds as tw

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

## Contributing

See [`CLAUDE.md`](CLAUDE.md) for project rules + collaboration discipline. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for workflow.

## License

MIT. See [`LICENSE`](LICENSE).
