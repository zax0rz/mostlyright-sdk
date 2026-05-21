# tradewinds

Local-first Python SDK for quants researching prediction-market weather settlements. No hosted backend — calls public APIs (AWC, IEM, GHCNh, NWS CLI, Kalshi) directly. Sprint 0 v0.1.0 ships observations + NWS CLI climate + the `research()` join, byte-equivalent to `mostlyright==0.14.1`'s `client.pairs()`.

## Project structure

- `packages/core/` → `tradewinds` PyPI distribution: `research()`, `snapshot`, shared `_internal/` utils
- `packages/weather/` → `tradewinds-weather` PyPI distribution: AWC/IEM/GHCNh/NWS CLI clients + historical fetchers + cache
- `packages/markets/` → `tradewinds-markets` PyPI distribution: Kalshi/Polymarket (v0.0.1 placeholder; v0.1.0 in Sprint 0.5)
- `roadmap/` → Sprint plans, lane checklists (`roadmap/lanes/{vu,founder}-*-lane.md`)
- `tests/` → pytest, includes `@pytest.mark.live` for network tests (excluded from CI)

## Commands

```bash
uv sync                                    # install workspace + dev deps
uv run pytest -m "not live" -q             # fast tests, no network
uv run pytest -q                           # all tests including live
uv run ruff check --fix .                  # lint + autofix
uv run ruff format .                       # format
uv build                                   # build all three packages
```

## Collaboration rules (Sprint 0 = lane-split)

**Default reviewer: @helloiamvu** (Vu).

- **Two parallel lanes:**
  - **Lane F (Founder):** new code — HTTP fetchers, cache, orchestration, README, outreach.
  - **Lane V (Vu):** lift from `monorepo-v0.14.1/` — parsers, merge policies, `pairs.py` → `research.py`, CI/CD.
  - **Cross-review:** each lane authors its own PRs; the OTHER lane reviews.
  - **Codex `model_reasoning_effort=high` mandatory** on any PR touching `_internal/merge/` or `research.py` (parity-critical paths).
- **Feature branches per work unit.** Name: `sprint0/<lane>-<task>`. Examples: `sprint0/vu-lift-core-internal`, `sprint0/founder-historical-fetcher-awc`.
- **Never commit directly to main.** Always branch + PR.
- **TDD mandatory.** Write tests first. RED → GREEN → REFACTOR. 80% coverage minimum.
- **Pre-commit hooks mandatory.** No `--no-verify`. Fix the underlying issue.
- **All API calls direct from SDK.** No `api.mostlyright.md`, no hosted-API client calls anywhere in `tradewinds.*`. Verified via grep on built wheels before publish.

## Data + parity rules

- **Source priority (LIVE_V1 observations):** AWC > IEM > GHCNh. NCEI excluded from live (latency).
- **Climate LIVE_V1:** `source_filter={iem, acis}`, NO source_priority, sort key `(-report_type_priority, source_received_at, ingestion_id)`. The file `policies_climate.py` in monorepo-v0.14.1 states: any drift here invalidates every historical Kalshi NHIGH/NLOW settlement. Treat as load-bearing.
- **Any change to merge logic MUST update parity fixtures** in `tests/fixtures/parity/`.
- **v0.14.1 contract:** `research(station, from_date, to_date)` returns byte-equivalent output to `mostlyright==0.14.1`'s `client.pairs(...)`. Columns: `date, station, cli_high_f, cli_low_f, obs_high_f, obs_low_f, obs_high_at, obs_low_at` (+ `fcst_*` if `include_forecast=True`).
- **Lift source pinned to v0.14.1 tag.** All "lift from monorepo" instructions refer to `../monorepo-v0.14.1/` (git worktree from the v0.14.1 tag), NOT monorepo head (which is at v0.17.0 with diverged behavior — Open-Meteo removal, settlement_v1 intake, etc.).
- **Cache:** `$HOME/.tradewinds/cache/observations/{station}/{year}/{month}.parquet`. `filelock`-guarded. Cache-skip when queried month equals current LST month for that station (current month is incomplete; elapsed months stable). No user-visible `fresh=` kwarg.
- **No preprocessing in v0.1.0.** Preserve `raw_metar` in observation rows so MetPy re-parse works (Vojtech's documented workflow). RH/feels_like preprocessing comes in Sprint 0.5+.
- **Raw + preprocessed split:** quants want both. Default fetch returns raw; preprocessing is opt-in via explicit transform calls (Sprint 0.5+).

## Testing

- `uv run pytest -m "not live" -q` is the default fast run. Lives in CI.
- `@pytest.mark.live` decorator for tests that hit real public APIs. Skipped in CI per testing playbook; run manually before each publish.
- **Parity test (`tests/test_parity.py`) is the HARD GATE for Sprint 0.** Sprint 0 ships only if all 5 fixtures byte-match `mostlyright==0.14.1` output. Fixtures captured at Day 0.5 (Lane V).
- 80% coverage minimum on new code (`research`, `_fetchers`, `cache`, merge wrappers). Lifted code retains its monorepo coverage.

## License

MIT. See [LICENSE](LICENSE).

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool.

Key routing rules:
- Product ideas, brainstorming → invoke `/office-hours`
- Bugs, errors, "why is this broken" → invoke `/investigate`
- Ship, deploy, push, create PR → invoke `/ship`
- QA, test the site, find bugs → invoke `/qa`
- Code review, check my diff → invoke `/review`
- Update docs after shipping → invoke `/document-release`
- Architecture review → invoke `/plan-eng-review`
