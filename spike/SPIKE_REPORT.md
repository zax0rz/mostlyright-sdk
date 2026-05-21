# Day 0.7 Spike Report — Historical Multi-Day Fetch Feasibility

**Date:** 2026-05-21
**Lane:** F (Founder)
**Branch:** `sprint0/founder-day-0-7-spike`
**Spike subject:** `research_spike("KNYC", "2025-04-01", "2025-04-07")`

## Verdict

**GO.** All three public endpoints reachable with no auth; all three return data shaped close enough to `pairs()`-style rows for Day 2 to generalise cleanly.

| Endpoint | Status | Rows | Notes |
|---|---|---|---|
| IEM ASOS METAR (`asos.py`, `report_type=3`) | ✓ | 168 | 24/day × 7 days for KNYC — hourly METAR cycle, exactly what `pairs()` consumes |
| IEM ASOS SPECI (`asos.py`, `report_type=4`) | ✓ | 69 | Off-cycle special reports — v0.14.1 splits METAR / SPECI into separate fetches, doc'd in `_iem.py` |
| IEM CLI climate (`json/cli.py`) | ✓ | 363 (year), 7 (window) | Full-year payload; window-filtered down to 7 daily settlement rows |
| AWC live (`aviationweather.gov/api/data/metar`) | ✓ | 173 | Last 7 days from today only — **cannot reach 2025-04** historically |

## Endpoints lifted (URL only) from `monorepo-v0.14.1`

- IEM ASOS: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`
  - Source: `ingest/sources/iem_gap_fill.py::_build_iem_url`
  - Key params: `station=NYC` (no `K` prefix), `data=all`, `tz=Etc/UTC`, `format=comma`, `report_type={3,4}`, `year1/month1/day1 → year2/month2/day2`
  - **End date is EXCLUSIVE.** To include obs on `2025-04-07`, send `day2=8`.
- IEM CLI: `https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2025`
  - Source: `ingest/sources/climate_sync.py::download_cli`
  - Granularity is full year — caller filters to window.
  - Response may be wrapped: `{"results": [...]}`. Unwrap.
- AWC live: `https://aviationweather.gov/api/data/metar?ids=KNYC&hours=168&format=json&taf=false`
  - Source: `ingest/sources/awc_poller.py::fetch_latest`
  - Live only; no historical depth.

## Sample data shapes

**IEM ASOS METAR (CSV, header + rows):**

First data row for KNYC 2025-04-01 00:51 UTC:
```
NYC,2025-04-01 00:51,59.00,54.00,83.46,140.00,3.00,0.00,29.57,1000.40,10.00,M,BKN,OVC,M,M,8500.00,11000.00,M,M,M,M,M,M,M,M,M,59.00,KNYC 010051Z AUTO 14003KT 10SM BKN085 OVC110 15/12 A2957 RMK AO2 SLP004 T01500122
```
Columns include: `station, valid, tmpf, dwpf, relh, drct, sknt, mslp, alti, vsby, gust, skyc1..4, skyl1..4, wxcodes, peak_wind_*, metar`. Matches `mostlyright.weather._iem` parser expectations.

**IEM CLI climate (JSON dict per day):**

Sample for KNYC 2025-04-01:
```json
{
  "station": "KNYC",
  "valid": "2025-04-01",
  "high": 58,
  "low": 41,
  "precip": 0.08,
  "snow": 0.0,
  "product": "202504020619-KOKX-CDUS41-CLINYC",
  "high_normal": 56,
  "low_normal": 40,
  "high_record": 83
}
```
`product` header includes timestamp `202504020619` → `2025-04-02 06:19 UTC` — settlement `knowledge_time`. `high` / `low` are Fahrenheit, integer (the Kalshi NHIGH/NLOW settlement labels).

**AWC live (structured JSON, sanity check only):**

Sample row (today, 2026-05-21 19:00 UTC):
```json
{
  "icaoId": "KNYC",
  "reportTime": "2026-05-21T19:00:00.000Z",
  "temp": 14.4,
  "dewp": 12.8,
  "wspd": 3,
  "metarType": "METAR",
  "rawOb": "METAR KNYC 211851Z AUTO VRB03KT 10SM SCT019 BKN036 OVC110 14/13 A3025 RMK AO2 RAE50 SLP235 P0000 T01440128"
}
```

## What this proves

1. **Historical multi-day fetch works without auth.** IEM ASOS serves any arbitrary date range. The end-exclusive quirk is real but trivial. SPECI requires a separate `report_type=4` request (already known from v0.14.1).
2. **Settlement label is reachable.** IEM CLI returns a full year with per-day high/low/precip/snow + product timestamp. Filtering to window is client-side.
3. **AWC live is fine as a sanity endpoint but not as the historical source.** 173 rows for the last 7 days proves the endpoint works; the lane doc was right that historical depth must come from IEM, not AWC.
4. **No surprises in field shapes.** ASOS columns line up with `_iem.py`'s parser; CLI fields match `_climate.py`'s expected schema. No new parsing work invented during the spike.

## What this does NOT prove (and is OK to defer)

- Rate-limit behaviour under burst. Spike issued 4 requests with no concurrency.
- Pagination beyond a single 7-day chunk. For multi-month ranges, v0.14.1's `_monthly_chunks` pattern (in `iem_gap_fill.py`) applies.
- Retry / 5xx behaviour. v0.14.1 has `download_with_retry`; Day 2 wraps the spike calls through it.
- Cache behaviour. Spike is uncached by design.
- Byte-equivalence with `mostlyright==0.14.1` `client.pairs()` output. That's the Day 3 parity gate (Vu's lifted parsers + Founder's fetchers running together).

## Day 1 / Day 2 implications

- **Lane V (Vu) lift can proceed as planned.** No URL surprises, no parser deviations. `_iem.py` and `_climate.py` parse exactly what these endpoints return.
- **Lane F (Founder) fetcher modules** map cleanly:
  - `tradewinds.weather._fetchers/iem_asos.py` — wraps `fetch_iem_asos` with chunking + retries + cache.
  - `tradewinds.weather._fetchers/iem_cli.py` — wraps `fetch_iem_cli` with year-pull-then-filter + cache.
  - `tradewinds.weather._fetchers/awc.py` — live only, no historical responsibility.
- **End-exclusive date handling** must be doc'd loudly in `_fetchers/iem_asos.py` because it will trip everyone. The spike sets `end_exclusive = end + timedelta(days=1)` — Day 2 should keep this convention.

## Scope cuts honoured

Per `roadmap/lanes/founder-build-lane.md` Day 0.7:
- ✓ NO packaging / `uv` / pyproject for the spike (script is `spike/research_spike.py`, run via `uv run --with httpx python ...` against the workspace's resolver but writes no lockfile).
- ✓ NO caching.
- ✓ NO merge policy (single source per endpoint; no observation/climate join).
- ✓ NO real parser (raw bytes / JSON, picked a few fields).

## How to re-run

```bash
cd ~/Documents/GitHub/tradewinds
uv run --with httpx python spike/research_spike.py
# or with custom inputs:
uv run --with httpx python spike/research_spike.py KORD 2025-01-01 2025-01-07
```

Exits `0` on GO, `1` on NO-GO. Captured output for the Sprint 0 reference run is at `spike/spike_output.json` (run on 2026-05-21).

## Disposition

**Throwaway as designed.** Do NOT lift `spike/research_spike.py` into `packages/`. Day 2 rewrites cleanly through Vu's `_internal` shared utilities (`_http`, `_live_http`, `download_with_retry`, polite-delay timing). The spike code goes in the trash; the URL patterns + end-exclusive quirk + multi-request SPECI behaviour go into Day 2's `_fetchers/` modules.
