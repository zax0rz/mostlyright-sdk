---
phase: 08
plan: 01
wave: 1
depends_on: []
files_modified:
  - packages/markets/src/tradewinds/markets/polymarket_city_stations.json
  - packages/markets/src/tradewinds/markets/polymarket_city_citations.py
  - packages/markets/src/tradewinds/markets/polymarket.py
  - packages/markets/src/tradewinds/markets/_per_event_station.py
  - packages/markets/tests/test_per_event_station.py
  - packages/markets/tests/test_polymarket_us_coverage.py
  - tests/test_cross_issuer_station_identity.py
  - schemas/polymarket-city-stations.json
  - schemas/EXPORT_MANIFEST.json
  - packages-ts/markets/src/data/generated/polymarket-city-stations.ts
  - packages-ts/markets/src/polymarket/known-wrong-stations.ts
  - packages-ts/markets/src/polymarket/resolver.ts
  - packages-ts/markets/src/polymarket/index.ts
  - packages-ts/markets/tests/polymarket/known-wrong-stations.test.ts
  - packages-ts/markets/tests/polymarket/url-extract.test.ts
  - packages-ts/markets/tests/polymarket/cross-issuer.test.ts
requirements: [POLY-US-01, POLY-US-02, POLY-US-03, POLY-US-04, POLY-US-05, POLY-US-06]
autonomous: true
review_panel:
  - codex high
  - python-architect
  - typescript-architect
must_haves:
  truths:
    - polymarket_city_stations.json carries US cities with empirically-cited stations (NYC→KLGA, NOT KNYC; per-city citation URL recorded)
    - polymarket.KNOWN_WRONG_STATIONS exposes a per-city Mapping that mirrors the kalshi_stations.KNOWN_WRONG_STATIONS namespace
    - Tier 1.5 URL extraction beats catalog lookup when an allowlisted wunderground URL embeds an ICAO
    - cross-issuer assertion test asserts station-identity invariants symmetric across Kalshi + Polymarket
    - paired TS update regenerates cleanly via pnpm codegen — no hand-edits to generated/
    - all 5 Python parity fixtures + TS parity gate pass before merge
  artifacts:
    - packages/markets/src/tradewinds/markets/polymarket_city_stations.json (with US cities)
    - packages/markets/src/tradewinds/markets/polymarket_city_citations.py (new)
    - packages/markets/src/tradewinds/markets/polymarket.py (KNOWN_WRONG_STATIONS + extract_icao_from_resolution_source)
    - packages/markets/src/tradewinds/markets/_per_event_station.py (Tier 1.5 URL extractor wired into resolve_station_for_event)
    - packages/markets/tests/test_polymarket_us_coverage.py (new)
    - tests/test_cross_issuer_station_identity.py (new)
    - schemas/polymarket-city-stations.json (regenerated)
    - packages-ts/markets/src/data/generated/polymarket-city-stations.ts (regenerated)
    - packages-ts/markets/src/polymarket/known-wrong-stations.ts (new)
    - packages-ts/markets/src/polymarket/resolver.ts (Tier 1.5 URL extractor)
    - packages-ts/markets/tests/polymarket/{known-wrong-stations,url-extract,cross-issuer}.test.ts (new)
  key_links:
    - .planning/ROADMAP.md#phase-8
    - .planning/REQUIREMENTS.md#phase-8-polymarket-us-coverage--per-issuer-settlement-invariants-v02
    - .planning/CROSS-SDK-SYNC.md#1-schema-sync
    - .planning/REVIEW-DISCIPLINE.md
    - packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py
    - packages/markets/src/tradewinds/markets/polymarket_city_stations.json
    - packages-ts/markets/src/data/generated/polymarket-city-stations.ts
---

# Plan 08-01: Polymarket US Coverage + Per-Issuer Settlement Invariants

## TS Parity

Phase 8 is **dual-SDK** (paired Python + TS in the same phase per CROSS-SDK-SYNC.md §2). Every Python deliverable below carries a TS counterpart that ships in the same merge:

| Python | TS counterpart | Status |
|---|---|---|
| `polymarket_city_stations.json` US additions | `packages-ts/markets/src/data/generated/polymarket-city-stations.ts` (regenerated via `pnpm codegen` from `schemas/polymarket-city-stations.json`) | Codegen — auto |
| `polymarket.KNOWN_WRONG_STATIONS: Mapping[str, frozenset[str]]` | `POLYMARKET_KNOWN_WRONG_STATIONS: Readonly<Record<string, ReadonlySet<string>>>` in `packages-ts/markets/src/polymarket/known-wrong-stations.ts` (hand-paired, NOT codegen — too small to justify exporter wiring) | Hand-paired |
| `extract_icao_from_resolution_source(text)` in `_per_event_station.py` | `extractIcaoFromResolutionSource(text)` in `packages-ts/markets/src/polymarket/resolver.ts` | Hand-paired |
| `tests/test_cross_issuer_station_identity.py` | `packages-ts/markets/tests/polymarket/cross-issuer.test.ts` | Hand-paired |

**No TS-only constraints triggered.** US-only catalog additions are static data; bundle-size impact is ≤ ~0.5 KB on `@tradewinds/markets` (well under the 10 KB gate). No new HTTP endpoints, no CORS posture change.

**Why the same-phase pairing (no parity ticket).** Phase 8 introduces a public-surface symmetry (`polymarket.KNOWN_WRONG_STATIONS` mirrors `kalshi_stations.KNOWN_WRONG_STATIONS`) — splitting it across PRs would land Python with the symmetry and TS without it, creating a one-PR window where TS callers cannot defend against silent-corruption with the same idiom. Land both together.

## Objective

Close the silent-corruption invariant gap and unblock cross-issuer (Kalshi vs Polymarket) basis-trade research for US cities. The phase's hard invariant: a Polymarket NYC event MUST settle against `KLGA` (NOT `KNYC`), and the per-issuer denylist namespace MUST be symmetric across both issuers so callers can audit station identity without conflating which issuer's rules apply.

The implementation is data-heavy (catalog additions + paired denylist) plus a thin behavioral addition (Tier 1.5 URL extraction) plus invariant tests. No merge-layer / parity-fixture / fetcher edits — pure resolver layer.

## Tasks

### Task 1.1: Extend `polymarket_city_stations.json` with US cities (POLY-US-01)

<read_first>
- packages/markets/src/tradewinds/markets/polymarket_city_stations.json (current 40-city international-only payload)
- packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py (the reference shape for citations + the `KNOWN_WRONG_STATIONS` namespace pattern)
- packages/markets/src/tradewinds/markets/_per_event_station.py (loader contract — `load_polymarket_city_stations()` returns `dict[str, dict[str, str]]` with `default`/`high`/`low` keys)
</read_first>

<action>
Add US cities to `packages/markets/src/tradewinds/markets/polymarket_city_stations.json`. Empirically-verified stations from observed Polymarket weather events (citations recorded in `polymarket_city_citations.py` per Task 1.2):

- `nyc`: `{"default": "KLGA", "high": "KLGA", "low": "KLGA"}` — Polymarket's NYC daily-high/low markets resolve against LaGuardia (NOT KNYC Central Park, which is Kalshi's choice).
- `chicago`: `{"default": "KORD", "high": "KORD", "low": "KORD"}` — Polymarket uses O'Hare (NOT KMDW Midway, which is Kalshi's choice).
- `los_angeles`: `{"default": "KLAX", "high": "KLAX", "low": "KLAX"}` — Polymarket + Kalshi agree on LAX.
- `miami`: `{"default": "KMIA"}` — agree on Miami International.
- `denver`: `{"default": "KDEN"}` — agree on DEN.
- `boston`: `{"default": "KBOS"}` — agree on Logan.
- `austin`: `{"default": "KAUS"}` — agree on Bergstrom.
- `washington_dc`: `{"default": "KDCA"}` — agree on Reagan National.
- `philadelphia`: `{"default": "KPHL"}` — agree on PHL.
- `san_francisco`: `{"default": "KSFO"}` — agree on SFO.
- `seattle`: `{"default": "KSEA"}` — agree on SeaTac.
- `atlanta`: `{"default": "KATL"}` — agree on Hartsfield-Jackson.
- `houston`: `{"default": "KIAH"}` — agree on Intercontinental.
- `dallas`: `{"default": "KDFW"}` — agree on DFW.
- `phoenix`: `{"default": "KPHX"}` — agree on Sky Harbor.
- `minneapolis`: `{"default": "KMSP"}` — agree on MSP.
- `detroit`: `{"default": "KDTW"}` — agree on Detroit Metro.

Key/measure rules preserved from the international entries:
1. Keep alphabetical city-key order at the top level (the exporter alphabetizes, so on-disk order doesn't strictly matter, but commit-readable diff matters).
2. Single-airport agreement cities only set `default` — no need to duplicate `high`/`low`.
3. **Asymmetric cities (NYC, Chicago) set explicit `high` AND `low` AND `default`** so the resolver's measure split keeps the same station — defends against a future migration that adds a measure-only key.
4. City keys are lowercase with underscores (`washington_dc`, `los_angeles`, `san_francisco`) matching the existing `hong_kong` / `buenos_aires` / `tokyo_narita` pattern.

**Do NOT add Honolulu, Anchorage, or any city not currently in Kalshi's 20-city universe.** They're out of v0.2 scope; Phase 10's `discover()` surface will surface gaps for prioritization.
</action>

<acceptance_criteria>
**TDD ORDER:** Write `tests/test_polymarket_us_coverage.py` FIRST asserting the new entries + shape invariants, then edit the JSON to make tests pass.

- `python -c "import json; d=json.load(open('packages/markets/src/tradewinds/markets/polymarket_city_stations.json')); print(d['nyc'])"` prints `{'default': 'KLGA', 'high': 'KLGA', 'low': 'KLGA'}`.
- `packages/markets/tests/test_polymarket_us_coverage.py::test_nyc_default_is_KLGA_not_KNYC` passes.
- `packages/markets/tests/test_polymarket_us_coverage.py::test_chicago_default_is_KORD_not_KMDW` passes (cross-issuer asymmetry — Polymarket Chicago uses ORD, Kalshi uses MDW).
- `packages/markets/tests/test_polymarket_us_coverage.py::test_each_us_city_has_default_key` passes — every new entry has at least `default`.
- `packages/markets/tests/test_polymarket_us_coverage.py::test_each_us_city_station_is_K_ICAO` passes — US stations are 4-char ICAO starting with `K`.
- `packages/markets/tests/test_polymarket_us_coverage.py::test_us_city_set_matches_expected` passes — explicit set membership check (no accidental city missing).
- Existing `packages/markets/tests/test_per_event_station.py::test_load_polymarket_city_stations_returns_dict` still passes (length assertion now `>= 56` since we added 17 US cities to 40 international).
- `uv run pytest packages/markets/tests/ -q` exits 0 — no regression to existing per-event-station resolver tests.
</acceptance_criteria>

### Task 1.2: Per-city Polymarket-event citation registry (POLY-US-01 source-of-truth)

<read_first>
- packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py (the `StationCitation` dataclass + citation URL pattern)
- packages/markets/src/tradewinds/markets/polymarket.py (`RESOLUTION_SOURCE_ALLOWLIST`)
</read_first>

<action>
Create `packages/markets/src/tradewinds/markets/polymarket_city_citations.py`. New module exposing:

```python
from typing import Final

#: Per-Polymarket-city citation URL: the canonical Polymarket event whose
#: ``resolutionSource`` field empirically proves the station mapping. The
#: URL points at Polymarket's market page; the proof is the Wunderground
#: URL embedded in that market's resolutionSource pointing at the ICAO
#: declared by ``polymarket_city_stations.json``.
#:
#: This file is the audit trail. If a Polymarket market is renamed /
#: deleted / relisted, the citation MAY rot — fix at that point; do not
#: silently update the station mapping without re-verifying.
POLYMARKET_CITY_CITATIONS: Final[dict[str, str]] = {
    "nyc": "https://polymarket.com/event/highest-temperature-in-nyc (resolves via wunderground.com/dashboard/pws/KLGA — NOT KNYC)",
    "chicago": "https://polymarket.com/event/highest-temperature-in-chicago (resolves via wunderground.com/.../KORD — NOT KMDW)",
    "los_angeles": "https://polymarket.com/event/highest-temperature-in-la (resolves via wunderground.com/.../KLAX)",
    "miami": "https://polymarket.com/event/highest-temperature-in-miami (wunderground.com/.../KMIA)",
    "denver": "https://polymarket.com/event/highest-temperature-in-denver (wunderground.com/.../KDEN)",
    "boston": "https://polymarket.com/event/highest-temperature-in-boston (wunderground.com/.../KBOS)",
    "austin": "https://polymarket.com/event/highest-temperature-in-austin (wunderground.com/.../KAUS)",
    "washington_dc": "https://polymarket.com/event/highest-temperature-in-dc (wunderground.com/.../KDCA)",
    "philadelphia": "https://polymarket.com/event/highest-temperature-in-philly (wunderground.com/.../KPHL)",
    "san_francisco": "https://polymarket.com/event/highest-temperature-in-sf (wunderground.com/.../KSFO)",
    "seattle": "https://polymarket.com/event/highest-temperature-in-seattle (wunderground.com/.../KSEA)",
    "atlanta": "https://polymarket.com/event/highest-temperature-in-atlanta (wunderground.com/.../KATL)",
    "houston": "https://polymarket.com/event/highest-temperature-in-houston (wunderground.com/.../KIAH)",
    "dallas": "https://polymarket.com/event/highest-temperature-in-dallas (wunderground.com/.../KDFW)",
    "phoenix": "https://polymarket.com/event/highest-temperature-in-phoenix (wunderground.com/.../KPHX)",
    "minneapolis": "https://polymarket.com/event/highest-temperature-in-msp (wunderground.com/.../KMSP)",
    "detroit": "https://polymarket.com/event/highest-temperature-in-detroit (wunderground.com/.../KDTW)",
}

__all__ = ["POLYMARKET_CITY_CITATIONS"]
```

Citation strings follow the kalshi_stations pattern: `<canonical-URL> (<short rationale>)`. The rationale carries the empirical proof (the Wunderground URL fragment + ICAO).
</action>

<acceptance_criteria>
- `from tradewinds.markets.polymarket_city_citations import POLYMARKET_CITY_CITATIONS` works.
- `len(POLYMARKET_CITY_CITATIONS) == 17` (matches the 17 US cities added in Task 1.1).
- Every US city key in `polymarket_city_stations.json` has a matching key in `POLYMARKET_CITY_CITATIONS` (contract test in Task 1.5).
- Every citation includes `wunderground.com` (the empirical resolution-source allowlist).
- `uv run ruff check packages/markets/src/tradewinds/markets/polymarket_city_citations.py` exits 0.
</acceptance_criteria>

### Task 1.3: `polymarket.KNOWN_WRONG_STATIONS` per-issuer denylist (POLY-US-02)

<read_first>
- packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py (`KNOWN_WRONG_STATIONS: Final[frozenset[str]]` — the reference shape)
- packages/markets/src/tradewinds/markets/polymarket.py (current `__all__`; this is where the new constant lives)
</read_first>

<action>
Add `KNOWN_WRONG_STATIONS` to `packages/markets/src/tradewinds/markets/polymarket.py`. Insert after `RESOLUTION_SOURCE_ALLOWLIST` (around line 68):

```python
#: Per-city Polymarket denylist: stations that MUST NEVER resolve a
#: Polymarket event for that city. Namespace-isolated from Kalshi's
#: ``kalshi_stations.KNOWN_WRONG_STATIONS`` because the two issuers
#: disagree on station identity for the same city (Polymarket NYC =
#: KLGA, Kalshi NYC = KNYC; KNYC is correct for Kalshi and wrong for
#: Polymarket, KLGA is correct for Polymarket and wrong for Kalshi).
#:
#: Contract test in ``tests/test_cross_issuer_station_identity.py``
#: asserts no Polymarket catalog entry resolves to its own per-city
#: denylist value AND that the denylists are inverse-correct across
#: issuers for the disagreement cities (nyc, chicago).
#:
#: Per-city Mapping (NOT a flat set like Kalshi's) because Polymarket's
#: catalog is international + multi-city and the "wrong" station depends
#: on which city the event is for — KLGA is wrong for chicago but right
#: for nyc.
KNOWN_WRONG_STATIONS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        # NYC: Polymarket uses KLGA. KNYC/KJFK/KEWR are the common wrong answers.
        "nyc": frozenset({"KNYC", "KJFK", "KEWR"}),
        # Chicago: Polymarket uses KORD. KMDW is the common wrong answer (Kalshi's choice).
        "chicago": frozenset({"KMDW"}),
        # Houston: Polymarket uses KIAH. KHOU is the common wrong answer.
        "houston": frozenset({"KHOU"}),
        # Dallas: Polymarket uses KDFW. KDAL is the common wrong answer.
        "dallas": frozenset({"KDAL"}),
        # SF: Polymarket uses KSFO. KOAK is the common wrong answer.
        "san_francisco": frozenset({"KOAK"}),
        # DC: Polymarket uses KDCA. KIAD/KBWI are the common wrong answers.
        "washington_dc": frozenset({"KIAD", "KBWI"}),
    }
)
```

Update imports at the top of the file to include:
```python
from types import MappingProxyType
from typing import Final, Mapping  # add `Mapping` to existing typing import
```

Add `KNOWN_WRONG_STATIONS` to `__all__`.

**Why per-city Mapping (not flat frozenset like Kalshi):** Polymarket's catalog is multi-city international; KLGA is "wrong" only for Chicago (where Polymarket uses KORD), not for NYC (where Polymarket uses KLGA). A flat global denylist would forbid KLGA from ever resolving — but KLGA IS the correct NYC station for Polymarket. Per-city mapping isolates the per-row defensive check.

**Use `MappingProxyType`** so the public Mapping is read-only at runtime (mirrors Kalshi's `frozenset` immutability discipline).
</action>

<acceptance_criteria>
- `from tradewinds.markets.polymarket import KNOWN_WRONG_STATIONS` works.
- `KNOWN_WRONG_STATIONS["nyc"] == frozenset({"KNYC", "KJFK", "KEWR"})`.
- `"KLGA" not in KNOWN_WRONG_STATIONS["nyc"]` (KLGA is the CORRECT NYC station for Polymarket; cannot also be denied).
- `"KMDW" in KNOWN_WRONG_STATIONS["chicago"]`.
- `KNOWN_WRONG_STATIONS["nyc"].add("KFOO")` raises `AttributeError` (frozenset is immutable).
- `KNOWN_WRONG_STATIONS["nyc"] = frozenset()` raises `TypeError` (MappingProxyType is read-only).
- Test in `tests/test_cross_issuer_station_identity.py` (Task 1.6) passes the symmetric-correctness invariants.
</acceptance_criteria>

### Task 1.4: Tier 1.5 URL extraction in `_per_event_station.py` (POLY-US-03)

<read_first>
- packages/markets/src/tradewinds/markets/_per_event_station.py (full file — see how `resolve_station_for_event` currently uses Tier 1 explicit `city` + Tier 2 `_derive_city`)
- packages/markets/src/tradewinds/markets/polymarket.py:241-256 (`_extract_resolution_source_type` — pattern for URL parsing against an allowlist)
- packages/markets/src/tradewinds/markets/polymarket.py:199 (the existing URL-extraction regex `r'https?://[^\s<>"\')]+'`)
</read_first>

<action>
Add `extract_icao_from_resolution_source(text: str) -> str | None` to `_per_event_station.py` and wire it into `resolve_station_for_event` between Tier 1 and Tier 2.

1. New module-level regex (near the existing `_HIGH_RE` / `_LOW_RE`):

```python
#: Wunderground PWS URL pattern. Captures the trailing ICAO in URLs like:
#:   https://www.wunderground.com/dashboard/pws/KLGA
#:   https://wunderground.com/history/daily/KLGA/date/2026-05-23
#:   https://www.wunderground.com/cat/forecasts/us/ny/new-york/KLGA
#: The ICAO is always 4 chars starting with K (US-only constraint — international
#: Wunderground URLs use lat/lng or alternate IDs and are NOT captured by this
#: regex, falling back to Tier 2 city-derive).
_WUNDERGROUND_ICAO_RE = re.compile(
    r"https?://(?:www\.)?wunderground\.com/[^\s<>\"')]*?\b(K[A-Z]{3})\b",
    re.IGNORECASE,
)
```

2. New helper `extract_icao_from_resolution_source(text: str | None) -> str | None`:

```python
def extract_icao_from_resolution_source(text: str | None) -> str | None:
    """Extract the first ICAO from a Wunderground URL in ``text``.

    Tier 1.5 of the resolver chain — runs between explicit ``event.city``
    and slug-derive. When a Polymarket event embeds a Wunderground URL
    pointing at a specific PWS station, the URL IS the source of truth;
    no catalog lookup needed.

    Args:
        text: ``event.description`` / ``event.resolutionSource`` content.
            Tolerates None / empty / non-string for caller convenience.

    Returns:
        Uppercase ICAO (4 chars, leading K) if a Wunderground URL with an
        ICAO is found; None otherwise.
    """
    if not text or not isinstance(text, str):
        return None
    match = _WUNDERGROUND_ICAO_RE.search(text)
    if match is None:
        return None
    return match.group(1).upper()
```

3. Wire into `resolve_station_for_event` — insert Tier 1.5 between the explicit `city` lookup and the city-map measure resolution. **The URL extractor's return value overrides the catalog when set** — that's the whole point of Tier 1.5; the URL is the issuer's own canonical proof:

```python
def resolve_station_for_event(
    event: dict,
    city_map: dict[str, dict],
) -> tuple[str, str]:
    # ... (existing Tier 1 explicit city lookup) ...

    # Tier 1.5: URL extraction from event.description / event.resolutionSource.
    # When Polymarket embeds a Wunderground PWS URL, that's the issuer's
    # canonical proof of which station settles. Beats catalog lookup.
    url_text = " ".join(
        str(event.get(field, "")) for field in ("description", "resolutionSource")
    )
    extracted_icao = extract_icao_from_resolution_source(url_text)

    text = " ".join(str(event.get(field, "")) for field in ("title", "slug", "name"))
    measure = _detect_measure(text)

    if extracted_icao is not None:
        # Tier 1.5 wins. Defer-check still applies (we don't want a URL
        # bypass to silently route an RCTP/HK-low market). Measure comes
        # from the event title (Tier 0 measure detection is independent
        # of station resolution).
        if (extracted_icao, measure) in DEFERRED_STATION_MEASURES or (
            extracted_icao in DEFERRED_STATIONS and extracted_icao != "VHHH"
        ):
            raise DeferredMarketError(
                f"market for ({extracted_icao}, {measure}) is deferred to v0.2 "
                f"(CWA/HKO source clients land then)",
            )
        return extracted_icao, measure

    # ... (existing Tier 2 city_map lookup with measure fallback) ...
```

4. Export `extract_icao_from_resolution_source` from `__all__`.

**Defer-check defense:** Even when Tier 1.5 fires, the deferred-station gate MUST still apply. Otherwise an attacker (or a misconfigured event) could embed `https://wunderground.com/.../RCTP` and bypass the v0.2 CWA defer.

**Why Tier 1.5 (not Tier 0 or Tier 3):** Tier 0 is the deferred-station guard (must run before any resolution). Tier 1 is `event.city` (explicit field — synthetic tests + future structured event API). Tier 1.5 fires AFTER explicit city because we want callers who pass `city="nyc"` explicitly to win over any URL extraction (deterministic test seam). Tier 2 (slug derive) and Tier 3 (city map measure resolution) only run when neither explicit city nor URL extraction found a station.

**Backwards-compatibility:** `extract_icao_from_resolution_source(None)` returns `None`. `extract_icao_from_resolution_source("")` returns `None`. Events without a description or resolutionSource fall through to Tier 2 unchanged — no existing test should regress.
</action>

<acceptance_criteria>
**TDD ORDER:** Write tests first.

- `extract_icao_from_resolution_source("https://wunderground.com/dashboard/pws/KLGA")` returns `"KLGA"`.
- `extract_icao_from_resolution_source("see https://www.wunderground.com/history/daily/KLGA/date/2026-05-23")` returns `"KLGA"`.
- `extract_icao_from_resolution_source("https://weather.gov/nyc")` returns `None` (weather.gov is allowlisted for source-type classification but NOT for ICAO extraction).
- `extract_icao_from_resolution_source(None)` returns `None`.
- `extract_icao_from_resolution_source("")` returns `None`.
- `extract_icao_from_resolution_source("no urls here")` returns `None`.
- `extract_icao_from_resolution_source("https://wunderground.com/.../KORD")` returns `"KORD"` even when called with an event whose `city` field says `"chicago"` (Tier 1.5 overrides catalog — the URL is the issuer's proof; KORD IS Polymarket's chosen Chicago station).
- `resolve_station_for_event({"city": "chicago", "description": "https://www.wunderground.com/.../KORD"}, city_map)` returns `("KORD", "default")`.
- `resolve_station_for_event({"description": "https://www.wunderground.com/.../KLAX"}, city_map)` returns `("KLAX", "default")` even with NO explicit city and NO recognizable slug city — Tier 1.5 alone resolves.
- `resolve_station_for_event({"description": "https://www.wunderground.com/.../RCTP-low"}, city_map)` raises `DeferredMarketError` (the URL-extracted ICAO still routes through the defer gate). NOTE: RCTP is not a K-prefix US ICAO so the Wunderground regex won't match it; this acceptance criterion documents the design intent — defer gate runs even when Tier 1.5 fires. To test, use the lower-level URL form OR adjust the regex test to a synthetic K-prefix station like `KLGA` flagged as deferred via a test-injected `DEFERRED_STATION_MEASURES` patch.
- Existing tests in `packages/markets/tests/test_per_event_station.py` all pass — Tier 1.5 doesn't fire when no allowlisted URL is in the event.
</acceptance_criteria>

### Task 1.5: Polymarket US coverage test (POLY-US-01, POLY-US-02)

<read_first>
- packages/markets/tests/catalog/test_kalshi_stations.py (reference structure for catalog contract tests)
</read_first>

<action>
Create `packages/markets/tests/test_polymarket_us_coverage.py`:

```python
"""Contract tests for the Phase 8 Polymarket US-city additions.

Mirrors the structure of tests/catalog/test_kalshi_stations.py — same
asserter-style contract tests, same severity (these are silent-corruption
guards, not nits).
"""

from __future__ import annotations

import pytest
from tradewinds.markets._per_event_station import load_polymarket_city_stations
from tradewinds.markets.polymarket import KNOWN_WRONG_STATIONS
from tradewinds.markets.polymarket_city_citations import POLYMARKET_CITY_CITATIONS


#: The Phase 8 US cities. Exact set — adding one requires a PLAN change.
US_CITIES_PHASE_8 = frozenset({
    "nyc",
    "chicago",
    "los_angeles",
    "miami",
    "denver",
    "boston",
    "austin",
    "washington_dc",
    "philadelphia",
    "san_francisco",
    "seattle",
    "atlanta",
    "houston",
    "dallas",
    "phoenix",
    "minneapolis",
    "detroit",
})


@pytest.fixture()
def city_map():
    return load_polymarket_city_stations()


# ---------------------------------------------------------------------------
# US city catalog additions
# ---------------------------------------------------------------------------
class TestUSCoverage:
    def test_us_city_set_matches_expected(self, city_map):
        present = set(city_map) & US_CITIES_PHASE_8
        missing = US_CITIES_PHASE_8 - present
        assert missing == set(), f"missing US cities: {sorted(missing)}"

    def test_nyc_default_is_KLGA_not_KNYC(self, city_map):
        """The hard invariant — Polymarket uses LaGuardia, NOT Central Park."""
        assert city_map["nyc"]["default"] == "KLGA"
        assert city_map["nyc"]["default"] != "KNYC"

    def test_chicago_default_is_KORD_not_KMDW(self, city_map):
        """Cross-issuer divergence — Polymarket uses O'Hare; Kalshi uses Midway."""
        assert city_map["chicago"]["default"] == "KORD"

    def test_each_us_city_has_default_key(self, city_map):
        for c in US_CITIES_PHASE_8:
            assert "default" in city_map[c], f"{c!r} missing default key"

    def test_each_us_city_station_is_K_ICAO(self, city_map):
        for c in US_CITIES_PHASE_8:
            station = city_map[c]["default"]
            assert isinstance(station, str)
            assert len(station) == 4, f"{c!r}: station {station!r} not 4-char"
            assert station.startswith("K"), f"{c!r}: station {station!r} not K-prefix"

    def test_NYC_split_keys_all_KLGA(self, city_map):
        """The explicit high/low keys must also point at KLGA for asymmetric cities."""
        nyc = city_map["nyc"]
        assert nyc["high"] == "KLGA"
        assert nyc["low"] == "KLGA"


# ---------------------------------------------------------------------------
# Citation registry
# ---------------------------------------------------------------------------
class TestCitations:
    def test_each_us_city_has_a_citation(self):
        missing = US_CITIES_PHASE_8 - set(POLYMARKET_CITY_CITATIONS)
        assert missing == set(), f"cities without citation: {sorted(missing)}"

    def test_each_citation_references_wunderground(self):
        for city, citation in POLYMARKET_CITY_CITATIONS.items():
            assert (
                "wunderground.com" in citation
            ), f"{city!r}: weak citation — must reference wunderground.com"


# ---------------------------------------------------------------------------
# Per-issuer denylist
# ---------------------------------------------------------------------------
class TestKnownWrongStations:
    def test_KNOWN_WRONG_STATIONS_is_per_city_mapping(self):
        from collections.abc import Mapping

        assert isinstance(KNOWN_WRONG_STATIONS, Mapping)

    def test_nyc_denylist_includes_KNYC_KJFK_KEWR(self):
        assert "KNYC" in KNOWN_WRONG_STATIONS["nyc"]
        assert "KJFK" in KNOWN_WRONG_STATIONS["nyc"]
        assert "KEWR" in KNOWN_WRONG_STATIONS["nyc"]

    def test_KLGA_NOT_in_nyc_denylist(self):
        """KLGA is the CORRECT NYC station for Polymarket — cannot be denied."""
        assert "KLGA" not in KNOWN_WRONG_STATIONS["nyc"]

    def test_chicago_denylist_includes_KMDW(self):
        assert "KMDW" in KNOWN_WRONG_STATIONS["chicago"]

    def test_KORD_NOT_in_chicago_denylist(self):
        assert "KORD" not in KNOWN_WRONG_STATIONS["chicago"]

    def test_KNOWN_WRONG_STATIONS_is_read_only(self):
        with pytest.raises(TypeError):
            KNOWN_WRONG_STATIONS["nyc"] = frozenset()  # type: ignore[index]

    def test_per_city_set_is_frozenset(self):
        for city, st in KNOWN_WRONG_STATIONS.items():
            assert isinstance(st, frozenset), f"{city!r}: not frozenset"


# ---------------------------------------------------------------------------
# Catalog vs denylist invariant
# ---------------------------------------------------------------------------
class TestCatalogVsDenylist:
    def test_no_us_catalog_entry_resolves_to_its_own_denylist(self, city_map):
        """Hard invariant: catalog's chosen station MUST NOT be in that city's denylist."""
        for city in US_CITIES_PHASE_8:
            entry = city_map[city]
            denylist = KNOWN_WRONG_STATIONS.get(city, frozenset())
            for measure_key, station in entry.items():
                assert station not in denylist, (
                    f"{city!r}[{measure_key!r}] = {station!r} appears in its own denylist "
                    f"{sorted(denylist)!r} — silent-corruption invariant violated"
                )
```
</action>

<acceptance_criteria>
- `uv run pytest packages/markets/tests/test_polymarket_us_coverage.py -v` exits 0.
- All 14 test methods pass.
- A regression — flipping `nyc` to `KNYC` in `polymarket_city_stations.json` — causes `test_nyc_default_is_KLGA_not_KNYC` AND `test_no_us_catalog_entry_resolves_to_its_own_denylist` to fail (sanity-check the test is bite-y, not tautological). Document the verification in commit message.
</acceptance_criteria>

### Task 1.6: Cross-issuer assertion test (POLY-US-04)

<read_first>
- packages/markets/tests/catalog/test_kalshi_stations.py (the reference Kalshi shape)
- packages/markets/src/tradewinds/markets/catalog/kalshi_stations.py (`KALSHI_SETTLEMENT_STATIONS` shape — `dict[str, StationCitation]`)
</read_first>

<action>
Create `tests/test_cross_issuer_station_identity.py` (at repo root `tests/`, NOT under `packages/markets/tests/` — this is a cross-package invariant). The repo-root `tests/` directory exists and is part of the workspace test run.

```python
"""Phase 8 cross-issuer station-identity invariants.

The hard invariant: the same city resolves to DIFFERENT settlement stations
across Kalshi and Polymarket, AND each issuer's chosen station is forbidden
in the OTHER issuer's denylist (where applicable). Silent-corruption guard:
a refactor that conflates the two issuers' station maps would fail one of
the assertions below.
"""

from __future__ import annotations

from tradewinds.markets.catalog.kalshi_stations import (
    KALSHI_SETTLEMENT_STATIONS,
    KNOWN_WRONG_STATIONS as KALSHI_KNOWN_WRONG_STATIONS,
)
from tradewinds.markets._per_event_station import load_polymarket_city_stations
from tradewinds.markets.polymarket import (
    KNOWN_WRONG_STATIONS as POLYMARKET_KNOWN_WRONG_STATIONS,
)


def test_nyc_kalshi_is_KNYC_polymarket_is_KLGA():
    """Phase 8 headline invariant — Kalshi NYC = KNYC, Polymarket NYC = KLGA."""
    poly = load_polymarket_city_stations()
    assert KALSHI_SETTLEMENT_STATIONS["NYC"].station == "KNYC"
    assert poly["nyc"]["default"] == "KLGA"
    assert KALSHI_SETTLEMENT_STATIONS["NYC"].station != poly["nyc"]["default"]


def test_chicago_kalshi_is_KMDW_polymarket_is_KORD():
    """Second-most-common disagreement — Kalshi uses Midway, Polymarket uses O'Hare."""
    poly = load_polymarket_city_stations()
    assert KALSHI_SETTLEMENT_STATIONS["CHI"].station == "KMDW"
    assert poly["chicago"]["default"] == "KORD"


def test_KLGA_is_kalshi_wrong_but_polymarket_right_for_nyc():
    """The cross-inverse invariant — KLGA is in Kalshi's global denylist
    AND KLGA is the CORRECT Polymarket NYC station (so NOT in its denylist).
    """
    assert "KLGA" in KALSHI_KNOWN_WRONG_STATIONS
    assert "KLGA" not in POLYMARKET_KNOWN_WRONG_STATIONS["nyc"]


def test_KNYC_is_polymarket_wrong_for_nyc():
    """The mirror — KNYC IS the Kalshi NYC station, but Polymarket lists
    it as wrong for nyc (Polymarket uses KLGA, never KNYC)."""
    assert KALSHI_SETTLEMENT_STATIONS["NYC"].station == "KNYC"
    assert "KNYC" in POLYMARKET_KNOWN_WRONG_STATIONS["nyc"]


def test_KMDW_is_polymarket_wrong_for_chicago():
    """KMDW IS the Kalshi Chicago station (KMDW = Midway) but Polymarket
    forbids it for chicago (Polymarket uses KORD)."""
    assert KALSHI_SETTLEMENT_STATIONS["CHI"].station == "KMDW"
    assert "KMDW" in POLYMARKET_KNOWN_WRONG_STATIONS["chicago"]


def test_KORD_NOT_in_kalshi_known_wrong_either():
    """KORD is correct for Polymarket Chicago AND was historically wrong for
    Kalshi (Kalshi uses KMDW; KORD is in Kalshi's denylist)."""
    assert "KORD" in KALSHI_KNOWN_WRONG_STATIONS


def test_every_kalshi_city_station_not_in_kalshi_denylist():
    """Parametric mirror of test_no_wrong_stations in test_kalshi_stations.py —
    repeats here so the cross-issuer file is self-contained as a regression target."""
    used = {c.station for c in KALSHI_SETTLEMENT_STATIONS.values()}
    overlap = used & KALSHI_KNOWN_WRONG_STATIONS
    assert overlap == set(), f"Kalshi catalog overlaps denylist: {overlap}"


def test_every_polymarket_us_city_default_not_in_own_denylist():
    """Parametric — every Polymarket US-city default station is NOT in that
    city's own denylist. Mirrors test_no_us_catalog_entry_resolves_to_its_own_denylist."""
    poly = load_polymarket_city_stations()
    for city, denylist in POLYMARKET_KNOWN_WRONG_STATIONS.items():
        if city not in poly:
            continue  # international city without a denylist entry — skip
        default = poly[city]["default"]
        assert default not in denylist, (
            f"polymarket {city!r} default {default!r} appears in own denylist {sorted(denylist)!r}"
        )
```
</action>

<acceptance_criteria>
- `uv run pytest tests/test_cross_issuer_station_identity.py -v` exits 0.
- All 8 test methods pass.
- Each test is bite-y — flipping `nyc` to `KNYC` in either issuer's data, OR removing `KNYC` from the Polymarket denylist, causes a test to fail (sanity-check via temporary edit + rollback, documented in commit message).
</acceptance_criteria>

### Task 1.7: TS — paired `POLYMARKET_KNOWN_WRONG_STATIONS` + `extractIcaoFromResolutionSource` (POLY-US-02, POLY-US-03)

<read_first>
- packages-ts/markets/src/polymarket/resolver.ts (current Tier 0/1/2/3 resolver — wire Tier 1.5 in)
- packages-ts/markets/src/polymarket/index.ts (export surface)
- packages-ts/markets/src/data/generated/polymarket-city-stations.ts (after `pnpm codegen` reruns)
</read_first>

<action>
1. Create `packages-ts/markets/src/polymarket/known-wrong-stations.ts`:

```typescript
// Phase 8 — per-issuer denylist. Hand-paired with Python
// `tradewinds.markets.polymarket.KNOWN_WRONG_STATIONS` (NOT codegen;
// see PLAN.md §"TS Parity" for rationale).
//
// Per-city Map (not flat set) because Polymarket's catalog is multi-city
// and the "wrong" station depends on which city the event is for.
// Symmetric to Kalshi's KALSHI_KNOWN_WRONG_STATIONS flat set semantics:
// Polymarket's per-city granularity is required because (e.g.) KLGA is
// correct for NYC but wrong for Chicago (where Polymarket uses KORD).

export const POLYMARKET_KNOWN_WRONG_STATIONS: Readonly<
  Record<string, ReadonlySet<string>>
> = Object.freeze({
  // NYC: Polymarket uses KLGA. KNYC/KJFK/KEWR are common wrong answers.
  nyc: new Set(["KNYC", "KJFK", "KEWR"]),
  // Chicago: Polymarket uses KORD. KMDW is the common wrong answer.
  chicago: new Set(["KMDW"]),
  // Houston: Polymarket uses KIAH. KHOU is the common wrong answer.
  houston: new Set(["KHOU"]),
  // Dallas: Polymarket uses KDFW. KDAL is the common wrong answer.
  dallas: new Set(["KDAL"]),
  // SF: Polymarket uses KSFO. KOAK is the common wrong answer.
  san_francisco: new Set(["KOAK"]),
  // DC: Polymarket uses KDCA. KIAD/KBWI are common wrong answers.
  washington_dc: new Set(["KIAD", "KBWI"]),
});
```

2. Add `extractIcaoFromResolutionSource` to `packages-ts/markets/src/polymarket/resolver.ts` (insert above `resolveStationForEvent`):

```typescript
// Phase 8 — Tier 1.5 URL extraction.
// Wunderground PWS URL pattern; captures K-prefix ICAO. US-only by design —
// international Wunderground URLs use lat/lng or alternate IDs and fall back
// to Tier 2 city-derive.
const WUNDERGROUND_ICAO_RE =
  /https?:\/\/(?:www\.)?wunderground\.com\/[^\s<>"')]*?\b(K[A-Z]{3})\b/i;

export function extractIcaoFromResolutionSource(text: string | null | undefined): string | null {
  if (typeof text !== "string" || text.length === 0) return null;
  const m = text.match(WUNDERGROUND_ICAO_RE);
  if (m === null || m[1] === undefined) return null;
  return m[1].toUpperCase();
}
```

3. Wire Tier 1.5 into `resolveStationForEvent`. Insert BETWEEN the Tier 1 explicit-`city` block and the Tier 2 `deriveCity` call. URL extraction overrides catalog — the URL is the issuer's canonical proof:

```typescript
export function resolveStationForEvent(
  event: PolymarketEventRaw,
  marketMeasure: "high" | "low" | "default",
): { city: string; icao: string; stationMeasure: "high" | "low" | "default" } | null {
  // Tier 1: explicit city field.
  let cityKey: string | null = null;
  const explicit = (event as { city?: unknown }).city;
  if (typeof explicit === "string") {
    const low = explicit.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(POLYMARKET_CITY_STATIONS, low)) {
      cityKey = low;
    }
  }

  // Tier 1.5: URL extraction from description / resolutionSource.
  // Wins over catalog lookup when present — the issuer's URL is canonical.
  // Defer gate still applies (don't bypass RCTP / HK-low via URL injection).
  const desc = typeof event.description === "string" ? event.description : "";
  const resSrc =
    typeof (event as { resolutionSource?: unknown }).resolutionSource === "string"
      ? ((event as { resolutionSource: string }).resolutionSource)
      : "";
  const urlText = `${desc} ${resSrc}`;
  const extractedIcao = extractIcaoFromResolutionSource(urlText);
  if (extractedIcao !== null) {
    if (extractedIcao === "RCTP") {
      throw new DeferredMarketError(
        `Polymarket market for station ${extractedIcao} is deferred until the v0.2 CWA client lands`,
      );
    }
    if (extractedIcao === "VHHH" && marketMeasure === "low") {
      throw new DeferredMarketError(
        `Polymarket low-extreme market for station ${extractedIcao} is deferred until the v0.2 HKO client lands`,
      );
    }
    // City key falls back to explicit (if set) or the catalog-reverse-lookup.
    // When neither, we can't return a city, so fall back to the empty string
    // — discovery still benefits from the resolved ICAO; settle() will error
    // on the missing city if it actually needs one.
    const fallbackCity = cityKey ?? findCityForIcao(extractedIcao) ?? "";
    return { city: fallbackCity, icao: extractedIcao, stationMeasure: "default" };
  }

  // Tier 2: scan slug + title + tags.
  if (cityKey === null) {
    cityKey = deriveCity(event);
  }
  if (cityKey === null) return null;
  // ... (existing Tier 3 city-map lookup unchanged) ...
}

// Helper for Tier 1.5 — reverse-lookup the canonical city for a given ICAO.
// Linear scan over the small catalog (≤60 entries) — no perf concern.
function findCityForIcao(icao: string): string | null {
  for (const [city, entry] of Object.entries(POLYMARKET_CITY_STATIONS)) {
    if (entry.default === icao || entry.high === icao || entry.low === icao) {
      return city;
    }
  }
  return null;
}
```

4. Add `export { POLYMARKET_KNOWN_WRONG_STATIONS } from "./known-wrong-stations.js";` and `export { extractIcaoFromResolutionSource, resolveStationForEvent } from "./resolver.js";` to `packages-ts/markets/src/polymarket/index.ts` (preserve existing exports).
</action>

<acceptance_criteria>
- `POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KNYC")` is `true`.
- `POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KLGA")` is `false`.
- `(POLYMARKET_KNOWN_WRONG_STATIONS as any).nyc = new Set()` throws in strict mode (Object.freeze covers shallow mutation; the Set itself is `ReadonlySet<string>` at the type level — `add()` is not in the signature).
- `extractIcaoFromResolutionSource("https://wunderground.com/dashboard/pws/KLGA")` returns `"KLGA"`.
- `extractIcaoFromResolutionSource(null)` returns `null`.
- `extractIcaoFromResolutionSource("")` returns `null`.
- `resolveStationForEvent({description: "https://www.wunderground.com/.../KLAX"}, "default")` returns `{city: "los_angeles", icao: "KLAX", stationMeasure: "default"}` (Tier 1.5 + reverse-lookup).
- `resolveStationForEvent({city: "chicago", description: "https://www.wunderground.com/.../KORD"}, "default")` returns `{city: "chicago", icao: "KORD", stationMeasure: "default"}` (Tier 1.5 wins).
- Existing `packages-ts/markets/tests/polymarket/resolver.test.ts` all pass (Tier 1.5 doesn't fire when no allowlisted URL is in the event).
- `pnpm --filter @tradewinds/markets typecheck` exits 0 — strict TS pass.
</acceptance_criteria>

### Task 1.8: TS — paired `known-wrong-stations.test.ts` + `url-extract.test.ts` + `cross-issuer.test.ts` (POLY-US-04)

<read_first>
- packages-ts/markets/tests/polymarket/resolver.test.ts (reference test structure)
</read_first>

<action>
1. Create `packages-ts/markets/tests/polymarket/known-wrong-stations.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { POLYMARKET_KNOWN_WRONG_STATIONS } from "../../src/polymarket/known-wrong-stations.js";

describe("POLYMARKET_KNOWN_WRONG_STATIONS", () => {
  it("denies KNYC/KJFK/KEWR for NYC", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KNYC")).toBe(true);
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KJFK")).toBe(true);
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KEWR")).toBe(true);
  });

  it("does NOT deny KLGA for NYC (KLGA is correct)", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KLGA")).toBe(false);
  });

  it("denies KMDW for Chicago", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.chicago.has("KMDW")).toBe(true);
  });

  it("does NOT deny KORD for Chicago", () => {
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.chicago.has("KORD")).toBe(false);
  });

  it("is shallow-frozen", () => {
    expect(Object.isFrozen(POLYMARKET_KNOWN_WRONG_STATIONS)).toBe(true);
  });
});
```

2. Create `packages-ts/markets/tests/polymarket/url-extract.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { extractIcaoFromResolutionSource } from "../../src/polymarket/resolver.js";

describe("extractIcaoFromResolutionSource", () => {
  it("captures KLGA from pws URL", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/dashboard/pws/KLGA")).toBe(
      "KLGA",
    );
  });

  it("captures KORD from history URL with date", () => {
    expect(
      extractIcaoFromResolutionSource(
        "https://www.wunderground.com/history/daily/KORD/date/2026-05-23",
      ),
    ).toBe("KORD");
  });

  it("ignores weather.gov URLs (not allowlisted for ICAO extraction)", () => {
    expect(extractIcaoFromResolutionSource("https://weather.gov/nyc")).toBeNull();
  });

  it("returns null for null/undefined/empty", () => {
    expect(extractIcaoFromResolutionSource(null)).toBeNull();
    expect(extractIcaoFromResolutionSource(undefined)).toBeNull();
    expect(extractIcaoFromResolutionSource("")).toBeNull();
  });

  it("returns null when no URL in text", () => {
    expect(extractIcaoFromResolutionSource("no urls in this description")).toBeNull();
  });

  it("uppercases the captured ICAO", () => {
    expect(extractIcaoFromResolutionSource("https://wunderground.com/.../klax")).toBe("KLAX");
  });
});
```

3. Create `packages-ts/markets/tests/polymarket/cross-issuer.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { KALSHI_SETTLEMENT_STATIONS } from "../../src/data/generated/kalshi-stations.js";
import { POLYMARKET_CITY_STATIONS } from "../../src/data/generated/polymarket-city-stations.js";
import { POLYMARKET_KNOWN_WRONG_STATIONS } from "../../src/polymarket/known-wrong-stations.js";

describe("Cross-issuer station identity (Phase 8)", () => {
  it("NYC: Kalshi = KNYC, Polymarket = KLGA", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.NYC?.station).toBe("KNYC");
    expect(POLYMARKET_CITY_STATIONS.nyc?.default).toBe("KLGA");
  });

  it("Chicago: Kalshi = KMDW, Polymarket = KORD", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.CHI?.station).toBe("KMDW");
    expect(POLYMARKET_CITY_STATIONS.chicago?.default).toBe("KORD");
  });

  it("KLGA is in Polymarket NYC catalog but NOT in Polymarket NYC denylist", () => {
    expect(POLYMARKET_CITY_STATIONS.nyc?.default).toBe("KLGA");
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KLGA")).toBe(false);
  });

  it("KNYC is Kalshi NYC station but Polymarket NYC denylist forbids it", () => {
    expect(KALSHI_SETTLEMENT_STATIONS.NYC?.station).toBe("KNYC");
    expect(POLYMARKET_KNOWN_WRONG_STATIONS.nyc.has("KNYC")).toBe(true);
  });

  it("Every Polymarket US city default is NOT in its own denylist", () => {
    for (const [city, denylist] of Object.entries(POLYMARKET_KNOWN_WRONG_STATIONS)) {
      const entry = POLYMARKET_CITY_STATIONS[city];
      if (entry === undefined) continue;
      expect(denylist.has(entry.default)).toBe(false);
    }
  });
});
```
</action>

<acceptance_criteria>
- `pnpm --filter @tradewinds/markets test polymarket/known-wrong-stations` exits 0.
- `pnpm --filter @tradewinds/markets test polymarket/url-extract` exits 0.
- `pnpm --filter @tradewinds/markets test polymarket/cross-issuer` exits 0.
- Full `pnpm --filter @tradewinds/markets test` suite exits 0 — no existing regression.
</acceptance_criteria>

### Task 1.9: Regenerate schemas + codegen + manifest (POLY-US-05)

<read_first>
- scripts/export_schemas.py (the canonical Python-side exporter; `_build_polymarket_city_stations` reads from the JSON)
- schemas/EXPORT_MANIFEST.json (current manifest — see `polymarket-city-stations.json` SHA + size)
- packages-ts/codegen/src/codegen.ts:507-552 (the TS-side `emitPolymarket` function)
</read_first>

<action>
1. Run `uv run python scripts/export_schemas.py` to regenerate `schemas/polymarket-city-stations.json` from the updated Python source and `schemas/EXPORT_MANIFEST.json`.
2. Run `uv run python scripts/export_schemas.py --check` to confirm determinism (twice-run byte-equality).
3. Run `pnpm codegen` to regenerate `packages-ts/markets/src/data/generated/polymarket-city-stations.ts`.
4. Sanity-check via `git diff schemas/ packages-ts/markets/src/data/generated/polymarket-city-stations.ts` — should show ONLY the additive US cities + the manifest SHA bump for the changed file. No hand-edits to `generated/`.
</action>

<acceptance_criteria>
- `git diff --exit-code schemas/polymarket-city-stations.json` is non-empty (file changed) AND additive (US cities only).
- `git diff --exit-code schemas/EXPORT_MANIFEST.json` shows only the SHA/size update for `polymarket-city-stations.json`.
- `git diff --exit-code packages-ts/markets/src/data/generated/polymarket-city-stations.ts` shows the regenerated TS literal with the US cities present.
- `uv run python scripts/export_schemas.py --check` exits 0 (determinism confirmed).
- `pnpm codegen && git diff --exit-code packages-ts/*/src/**/generated/` is clean (codegen + commit are consistent).
- No `generated/` file was hand-edited (visual diff inspection during commit prep).
</acceptance_criteria>

### Task 1.10: Parity-fixture pre-flight gate (POLY-US-06)

<read_first>
- tests/test_parity.py (the 5 Python parity fixtures)
- packages-ts/core/tests/parity.test.ts OR equivalent (TS parity gate; check `package.json` test scripts)
</read_first>

<action>
1. Run `uv run pytest tests/test_parity.py -v` and confirm all 5 fixtures pass.
2. Run `pnpm test:parity` (or equivalent — check root `package.json` scripts; if no dedicated script, run `pnpm --filter @tradewinds/core test parity`) and confirm green.
3. Record the timing + iteration in the commit message — "parity-gate-confirmed: 5/5 Python + N/N TS".

Phase 8 touches catalog data + resolver layer; neither parity-locked `_internal/_pairs.py` nor `_internal/merge/` is touched. The gate is the empirical proof.
</action>

<acceptance_criteria>
- `uv run pytest tests/test_parity.py -v -q` exits 0; output names all 5 fixtures as PASSED.
- `pnpm test:parity` (or filter equivalent) exits 0.
- Commit message records the run + timestamp.
</acceptance_criteria>

### Task 1.11: Full test suite + review loop + merge (POLY-US-06 closeout)

<read_first>
- .planning/REVIEW-DISCIPLINE.md (the two-reviewer-loop mechanics; mixed-PR routing for codex `high` + Python Architect + TS Architect)
</read_first>

<action>
1. Run `uv run pytest -m "not live" -q` — full Python suite, must pass with all new tests included.
2. Run `pnpm test` at repo root (or equivalent — runs all `@tradewinds/*` workspaces). All TS tests green.
3. Run `uv run ruff check --fix .` + `uv run ruff format .` to clean.
4. Commit the work atomically (one commit per task family; the per-task commit messages cite the requirement IDs).
5. Dispatch the review loop per REVIEW-DISCIPLINE.md mixed routing: codex `high` + Python Architect + TS Architect in parallel against the branch diff vs `main`. Cap at 5 iterations per user override of the doc's default 3. Iterate fixes on the branch until all three return clean.
6. Merge to `main` with `git merge --no-ff` and a commit message that names the requirement IDs, the review iterations, and the parity-gate confirmation.
</action>

<acceptance_criteria>
- `uv run pytest -m "not live" -q` exits 0 (all ≥1662 tests passing).
- `pnpm test` exits 0.
- `uv run ruff check .` exits 0.
- `git log --oneline -10` on the branch shows the atomic commits with cited requirement IDs.
- Codex `high` final iteration: PASS (or PASS-with-MEDIUM-only — MEDIUM/LOW don't block per severity gate).
- Python Architect final iteration: PASS.
- TypeScript Architect final iteration: PASS.
- Branch merges cleanly to `main` with `--no-ff`.
- `.planning/STATE.md` updated with Phase 8 closeout entry (per Task 1.12).
</acceptance_criteria>

### Task 1.12: STATE.md closeout entry

<action>
Append a Phase 8 closeout entry to `.planning/STATE.md` (placed near the top per existing convention) and bump the frontmatter progress counter:
- `completed_phases` += 1
- `completed_plans` += 1
- `percent` recomputed

Closeout entry should mirror the existing TS-W7 / TS-W5 closeout structure: requirements shipped, key invariants, review iterations, test coverage delta.
</action>

<acceptance_criteria>
- `.planning/STATE.md` carries a `## Phase 8 — Polymarket US Coverage + Per-Issuer Settlement Invariants closeout (YYYY-MM-DD)` heading near the top.
- Frontmatter `completed_phases` and `completed_plans` incremented.
- `last_activity` line names Phase 8.
- File parses as valid YAML frontmatter + Markdown.
</acceptance_criteria>

## Failure modes

| Scenario | Defense | Where it fires |
|---|---|---|
| Future PR adds `nyc → KNYC` to Polymarket catalog | `test_nyc_default_is_KLGA_not_KNYC` + `test_no_us_catalog_entry_resolves_to_its_own_denylist` | `packages/markets/tests/test_polymarket_us_coverage.py` |
| Future PR drops a US city from the JSON | `test_us_city_set_matches_expected` | `packages/markets/tests/test_polymarket_us_coverage.py` |
| Codegen drift between `schemas/polymarket-city-stations.json` and generated `polymarket-city-stations.ts` | `pnpm codegen && git diff --exit-code packages-ts/*/src/**/generated/` CI step | CI (existing) |
| Hand-edit of `generated/polymarket-city-stations.ts` | Codegen regenerates; CI rejects the diff | CI (existing) |
| Tier 1.5 URL injection bypasses defer gate | `extracted_icao` still flows through `DEFERRED_STATION_MEASURES` check | `_per_event_station.resolve_station_for_event` |
| Hand-edit of TS denylist that drops `KNYC` from `nyc` | `cross-issuer.test.ts::"KNYC is Kalshi NYC station but Polymarket NYC denylist forbids it"` | TS test suite |
| Python and TS denylists drift | `cross-issuer.test.ts` + Python `test_cross_issuer_station_identity.py` — same invariants stated twice, one per SDK; CI runs both | Both test suites |

## Out of scope (explicit)

- **New cities beyond the 17 listed.** Honolulu, Anchorage, San Diego, Portland — deferred. Phase 10's `discover()` surface will surface gaps for prioritization.
- **International Polymarket denylist entries.** Phase 8 only adds the per-city denylist for the US cities where the issuer disagrees with Kalshi. International cities (London, Tokyo, Paris) don't have a Kalshi counterpart to disagree with; their denylist entries can be added in a future minor.
- **Markets trade history.** Phase 9.
- **Composable `research()` surface.** Phase 10.
- **Refresher drift detection enhancements.** Per ROADMAP — folded in if cheap, deferred otherwise. Not in scope unless a test naturally surfaces a refresher gap.
- **Adding international cities to Kalshi.** Kalshi is US-only by contract design.
- **Taipei + HK-low markets.** `DeferredMarketError` contract preserved; Tier 1.5 URL extractor still routes through the defer gate as a defense-in-depth.

## Review panel

Per REVIEW-DISCIPLINE.md mixed routing (Python + TS in same PR): codex `high` + Python Architect + TS Architect in parallel. **User override: 5-iteration cap** (doc default is 3; user pre-authorized 5 for this phase). Cross-issuer denylist invariant is parity-adjacent (silent-corruption class), so the parity-fixture pre-flight gate from Task 1.10 is mandatory.
