# Lane F — Founder's Build Lane

**Owner:** Founder (Robert)
**Scope:** New code — HTTP historical fetchers, cache layer, `observations.fetch()` orchestration, README, outreach. Sync with Lane V at the gates.

**Coordination with Lane V (Vu):** Vu authors the LIFT (parsers, merge, pairs → research). You author the NEW CODE (fetchers, cache, orchestration). You review Vu's PRs; Vu reviews yours. Codex `model_reasoning_effort=high` on PRs touching `_internal/merge/` or `research.py`.

---

## Day 0 — Vojtech call ✓ DONE

Confirmed: Vojtech is switching from v0.14.1 to tradewinds.

---

## Day 0.7 — Historical-fetcher feasibility spike (~half day)

While Vu does Day 0.5 reconnaissance + fixture capture, you spike the one risky bit: **historical multi-day AWC + NWS CLI HTTP fetching**, which doesn't exist in monorepo SDK code (only in `ingest/sources/awc_poller.py`).

### Goal

Throwaway scratch directory. Build a minimal end-to-end `research_spike("KNYC", "2025-04-01", "2025-04-07")` that:
1. Calls AWC public endpoints directly (no auth) for a 7-day historical range:
   - Discovery: `https://aviationweather.gov/api/data/metar?ids=KNYC&hours=168&format=json` (returns ~last 7 days)
   - For deeper history, see how `monorepo-v0.14.1/ingest/sources/awc_poller.py` paginates / chunks
2. Calls NWS CLI public endpoints (no auth) for the same date range:
   - Pattern: see `monorepo-v0.14.1/src/mostlyright/weather/_climate.py` for the URL shape
3. Returns rows that LOOK like v0.14.1's `pairs()` rows — does not need exact byte match yet, just enough to prove the path works.

### Scope cuts

- NO packaging / `uv` / pyproject — just `python spike.py`
- NO caching
- NO merge policy (single source: AWC)
- NO actual parser (just pull the raw JSON and pick a few fields)

### Outcome

- **If it works in half a day:** Day 1 lift+build can proceed; you have a working pattern to generalize into `tradewinds.weather._fetchers/` on Day 2.
- **If it doesn't work in half a day:** STOP. Reopen timeline with Vu. The lift premise is broken; Sprint 0 needs either more days or Approach C.

Push the spike code as a draft PR (`sprint0/founder-day-0-7-spike`) so Vu can see what you proved. **The spike is throwaway** — don't promote it to production code; Day 2 will rewrite cleanly with Vu's lifted `_internal` utilities.

---

## Day 1 — Workspace bootstrap + start fetchers

### A) Morning — Bootstrap (~2 hours)

The repo is already initialized (this commit) with `pyproject.toml`, `LICENSE`, `CLAUDE.md`, etc. Your Day 1 morning task:

1. **Reserve PyPI placeholders.** Push `v0.0.1` to all three slots so the namespace is locked before public announcement:
   ```bash
   uv build
   # tradewinds v0.0.1, tradewinds-weather v0.0.1, tradewinds-markets v0.0.1
   uv publish dist/tradewinds-0.0.1*.whl dist/tradewinds-0.0.1*.tar.gz
   uv publish dist/tradewinds_weather-0.0.1*
   uv publish dist/tradewinds_markets-0.0.1*
   ```
   (Requires PYPI_TOKEN env var or `uv publish --token <token>`.)

2. **Pin deps to v0.14.1.** Cross-reference `../monorepo-v0.14.1/pyproject.toml` (which Vu has via Day 0.5 worktree) and tighten the `>=` pins in each `packages/*/pyproject.toml` if they're looser than monorepo's. The initial setup already follows v0.14.1's floors (`httpx>=0.27`, `jsonschema>=4.21`, `pyarrow>=17.0`, `pandas>=2.2`, `filelock>=3.12`).

3. **Verify `uv sync` works:** `cd /Users/robe/Downloads/mostlyright/tradewinds && uv sync`. Lockfile committed.

4. **10-min sync with Vu** on `tradewinds._internal/` public API surface — agree on which symbols you'll import on Day 2 (likely: `Config`, `Observation`, `_http.HttpSession`, `_live_http.request_live_with_retry`, `exceptions.*`, `_convert.*`).

5. **Open initial PR.** Branch: `sprint0/founder-day-1-bootstrap`. PR title: `Day 1: workspace bootstrap + PyPI placeholders`. Vu reviews. Merge to unblock Vu's Day 1 lift work.

### B) Afternoon — Start historical fetchers

Once Vu's Day 1 PR is merging (his work doesn't block you from creating fetcher files; the imports just won't resolve until his PR lands):

Create `packages/weather/src/tradewinds/weather/_fetchers/__init__.py` and `_fetchers/awc.py` based on Day 0.7's spike pattern:

```python
# packages/weather/src/tradewinds/weather/_fetchers/awc.py
from tradewinds._internal._live_http import request_live_with_retry  # depends on Vu's Day 1 lift
from tradewinds._internal._http import _VERSION

def awc_historical_fetch(station: str, from_date: str, to_date: str) -> list[dict]:
    """Return raw AWC METAR records for [from_date, to_date] inclusive.
    Returns a list of dicts matching the AWC API response shape; parsing happens
    in the caller (via tradewinds.weather._awc.awc_to_observation).
    """
    # ... HTTP loop, pagination, retry, returns rows
```

Open PR: `sprint0/founder-day-1-fetcher-awc`. Vu reviews end of day (depends on his Day 1 PR landing first).

---

## Day 2 — Finish fetchers + build cache + wire orchestration

### A) Finish remaining fetchers

Generalize the AWC pattern to:
- `_fetchers/iem.py` — pulls from IEM ASOS endpoint (see `monorepo-v0.14.1/ingest/sources/iem_gap_fill.py` for URL pattern)
- `_fetchers/ghcnh.py` — pulls from NCEI GHCNh archive
- `_fetchers/climate.py` — pulls from NWS CLI

Each returns a list of dicts in the source's native shape; parsing happens via Vu's lifted parsers (`weather/_awc.py`, etc.).

### B) Build cache layer

Create `packages/weather/src/tradewinds/weather/cache/__init__.py`:

```python
# pseudocode
from pathlib import Path
from filelock import FileLock
from datetime import date
from zoneinfo import ZoneInfo

CACHE_ROOT = Path.home() / ".tradewinds" / "cache" / "observations"

def cache_path(station: str, year: int, month: int) -> Path:
    return CACHE_ROOT / station / str(year) / f"{month:02d}.parquet"

def is_current_lst_month(station: str, year: int, month: int) -> bool:
    """LST-aware current-month check. Uses station-specific TZ offset
    (matches settlement window math in snapshot.py)."""
    # ... per-station LST detection (probably via _stations.py from Vu's lift)

def read_cache(station: str, year: int, month: int) -> pd.DataFrame | None:
    path = cache_path(station, year, month)
    if not path.exists() or is_current_lst_month(station, year, month):
        return None
    with FileLock(str(path) + ".lock"):
        return pd.read_parquet(path)

def write_cache(station: str, year: int, month: int, df: pd.DataFrame) -> None:
    if is_current_lst_month(station, year, month):
        return  # never cache the current month
    path = cache_path(station, year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path) + ".lock"):
        # write to temp then atomic rename
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp)
        tmp.rename(path)
```

Test: cache hit/miss, current-month-skip, concurrent writers don't corrupt.

### C) Wire `observations.fetch()` orchestration

Create `packages/weather/src/tradewinds/weather/observations.py`:

```python
# pseudocode
from tradewinds._internal.merge import LIVE_V1_OBSERVATIONS  # from Vu's Day 2
from tradewinds.weather._fetchers import awc, iem, ghcnh
from tradewinds.weather._awc import awc_to_observation
from tradewinds.weather._iem import iem_to_observation
from tradewinds.weather._ghcnh import ghcnh_to_observation
from tradewinds.weather.cache import read_cache, write_cache

def fetch(station: str, from_date: str, to_date: str) -> pd.DataFrame:
    # for each month in [from_date, to_date]:
    #   try cache; if miss:
    #     fan out to awc + iem + ghcnh fetchers
    #     parse each source's rows via lifted parsers
    #     apply LIVE_V1_OBSERVATIONS.select(rows) merge
    #     write to cache (if not current month)
    #   yield rows
    # return DataFrame
```

Same pattern for `tradewinds.weather.climate.fetch(...)` using `LIVE_V1_CLIMATE`.

### D) Integration smoke at end of day

Pair with Vu (~30 min):
```bash
uv run python -c "
import tradewinds as tw
df = tw.research(station='KNYC', from_date='2025-04-01', to_date='2025-04-07')
print(df.columns.tolist())
print(df.head())
"
```
Column set must match the Day 0.5 fixture for that station+range. Failures → joint debug.

PR: `sprint0/founder-day-2-fetchers-cache-orchestration`. Vu reviews.

---

## Day 3 — Live smoke tests + pair-debug parity

While Vu writes the parity test:

### A) Write `@pytest.mark.live` smoke tests

`tests/test_smoke_live.py`:

```python
import pytest

@pytest.mark.live
def test_live_awc_round_trip():
    """Hit real AWC. Verify observations.fetch() returns >= 1 row for KNYC in the last 24h."""
    # ...

@pytest.mark.live
def test_live_full_research_round_trip():
    """tradewinds.research(KNYC, last-week) returns a DataFrame with expected columns."""
    # ...

# Repeat for IEM, GHCNh, NWS CLI
```

Run manually: `uv run pytest -q` (no `-m "not live"` filter).

### B) Pair-debug parity failures with Vu

Vu's parity test is the make-or-break. Failures will likely be in your orchestration / fetcher code (since Vu's lifted code is already byte-equivalent to v0.14.1). Treat as joint debug.

PR: `sprint0/founder-day-3-smoke-live`. Vu reviews.

---

## Day 4 — README + publish v0.1.0 + outreach

### A) Morning — README

Write the workspace `README.md` with:
- `pip install "tradewinds[parquet]" "tradewinds-weather[parquet]"`
- 10-line quickstart
- "What this is / what this isn't" section
- "Performance characteristics" section (per `TODOS.md` item 2): first-fetch slow for large date ranges; subsequent calls fast via cache
- "Concurrent cache" note (per `TODOS.md` item 3)
- "Sprint 0 v0.1.0 ships only the wedge" — what's in vs. out

### B) TestPyPI dry-run

```bash
uv build
uv publish --repository testpypi
# manual clean venv:
python3 -m venv /tmp/tw-test-venv && source /tmp/tw-test-venv/bin/activate
pip install -i https://test.pypi.org/simple/ "tradewinds[parquet]" "tradewinds-weather[parquet]"
python -c "import tradewinds as tw; print(tw.research(station='KNYC', from_date='2025-04-01', to_date='2025-04-07', as_dataframe=True))"
```

### C) Publish v0.1.0

Bump `version = "0.1.0"` in `packages/core/pyproject.toml` and `packages/weather/pyproject.toml`. `tradewinds-markets` stays at `v0.0.1` placeholder.

```bash
uv build
uv publish dist/tradewinds-0.1.0*
uv publish dist/tradewinds_weather-0.1.0*
```

### D) Outreach

- **Vojtech:** "We shipped what you saw on Day 0. Install: `pip install 'tradewinds[parquet]' 'tradewinds-weather[parquet]'`. Run `tw.research(station=..., from_date=..., to_date=...)`. Try it on your real workflow this week. Tell me yes or no per the rubric in `roadmap/sprint0-validation.md` — 'I'll switch from v0.14.1 this month' OR 'I'll build my [specific work] on this.'"
- **Quant 2 (name from 03-31 design doc):** same message + your context for why this fits their workflow.
- **Quant 3 (name from Vojtech's network):** same message + Vojtech's intro.

Log each response in `roadmap/sprint0-validation.md`.

---

## Day 4 + 7 days — Decision point

Apply N=3 rubric (see [`sprint0-validation.md`](../sprint0-validation.md)).

- **N=3 yes → Sprint 0.5.** Vu starts Kalshi metadata lift; you do second-round outreach to grow beyond N=3.
- **< N=3 → STOP, debrief.** Consider Approach C (in-place mostlyright v0.15) per design doc.
