---
phase: 10
plan: 01
wave: 1
depends_on: [08, 09]
files_modified:
  - packages/core/src/tradewinds/research.py
  - packages/core/src/tradewinds/_compose.py
  - packages/core/src/tradewinds/discover.py
  - packages/core/src/tradewinds/exceptions/__init__.py
  - packages/core/src/tradewinds/__init__.py
  - packages/core/tests/test_compose.py
  - packages/core/tests/test_discover.py
  - packages-ts/core/src/research/index.ts
  - packages-ts/core/src/research/compose.ts
  - packages-ts/core/src/discovery/discover.ts
  - packages-ts/core/tests/research/compose.test.ts
  - packages-ts/core/tests/discovery/discover.test.ts
requirements: [COMPOSE-01, COMPOSE-02, COMPOSE-03, COMPOSE-04, COMPOSE-05, COMPOSE-06, COMPOSE-07, COMPOSE-08, COMPOSE-09]
autonomous: true
review_panel:
  - codex high
  - python-architect
  - typescript-architect
must_haves:
  truths:
    - existing research(station, from_date, to_date) signature works unchanged (parity gate green)
    - city= selector returns per-station rows with settles_for annotation
    - contract= selector resolves Kalshi + Polymarket contract ids to their settlement stations
    - contracts= + include_trades=True returns multi-issuer DataFrame with basis_f column
    - station_override emits StationOverrideWarning + sets settlement_mismatch=True
    - sources= (plural) vs source= (singular) mutually exclusive
    - discover(city=) shows per-station settles_for annotations
    - TS surface mirrors Python via union types
  artifacts:
    - packages/core/src/tradewinds/_compose.py (new dispatch helper)
    - packages/core/src/tradewinds/discover.py (new module)
    - packages/core/src/tradewinds/research.py (signature widened with kwargs)
    - packages/core/src/tradewinds/exceptions/__init__.py (StationOverrideWarning)
    - packages/core/tests/test_compose.py (new)
    - packages/core/tests/test_discover.py (new)
    - packages-ts/core/src/research/compose.ts (new)
    - packages-ts/core/src/discovery/discover.ts (new function)
    - packages-ts/core/tests/research/compose.test.ts (new)
    - packages-ts/core/tests/discovery/discover.test.ts (new)
  key_links:
    - .planning/ROADMAP.md#phase-10
    - .planning/REQUIREMENTS.md#phase-10-composable-research--multi-contract-basis-trade-v02
    - .planning/REVIEW-DISCIPLINE.md
    - packages/markets/src/tradewinds/markets/catalog/kalshi_nhigh.py
    - packages/markets/src/tradewinds/markets/polymarket_trades.py
    - packages/markets/src/tradewinds/markets/_per_event_station.py
---

# Plan 10-01: Composable `research()` — Multi-Contract Basis Trade

## TS Parity

Phase 10 is **dual-SDK** (paired Python + TS in same merge per CROSS-SDK-SYNC.md §2). Every selector that lands in Python lands in TS in the same PR.

| Python | TS counterpart |
|---|---|
| `research(station=, city=, contract=, contracts=, ...)` kwargs | `research({station, city, contract, contracts, ...})` options object with TS union types enforcing mutual exclusion |
| `_compose.py` dispatcher | `research/compose.ts` dispatcher |
| `discover(city=...)` | `discover({city})` in `@tradewinds/core/discovery` |
| `StationOverrideWarning` (Python `Warning` subclass) | `StationOverrideWarning` (TS class extending `TradewindsError` with a `severity: "warning"` field — there's no JS analogue to Python `warnings.warn()` so we use a structured warning object emitted via the existing optional `onWarning?` callback in research options) |

**No TS-only constraints triggered.** Selector dispatch is pure logic; the actual data-fetch flows through existing Phase 1 (research), Phase 8 (catalog), and Phase 9 (trades) surfaces already shipped on both SDKs. Bundle delta is small (~2-3 KB on `@tradewinds/core`).

## Objective

Evolve `research()` from station-only into a composable selector surface that lets quants ask: "give me Kalshi NYC + Polymarket NYC weather + their trade timeseries + the basis spread, in one call." Adds 4 mutually-exclusive selectors (`station=` | `city=` | `contract=` | `contracts=`) + optional kwargs (`station_override=`, `sources=` / `source=`, `include_trades=`) + a separate `discover(city=...)` ergonomic surface.

**Hard backwards-compat invariant:** the existing `research(station, from_date, to_date)` signature MUST continue to work unchanged so all 5 Phase 1 parity fixtures stay byte-equivalent. The new surface is purely additive.

## Tasks

### Task 1.1: New `_compose.py` dispatcher

<read_first>
- packages/core/src/tradewinds/research.py:1074-1180 (the existing `research()` signature)
- packages/markets/src/tradewinds/markets/catalog/kalshi_nhigh.py + kalshi_nlow.py (contract resolvers)
- packages/markets/src/tradewinds/markets/_per_event_station.py (Polymarket city resolver)
</read_first>

<action>
Create `packages/core/src/tradewinds/_compose.py` with:

```python
"""Phase 10 — composable `research()` dispatcher.

Translates the new selectors (`city=`, `contract=`, `contracts=`) into the
existing station-based research() invocation, joining + annotating the
returned rows with cross-issuer metadata.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

#: Marker types for the selector union — exactly one must be provided.
_SELECTOR_NAMES = ("station", "city", "contract", "contracts")


class StationOverrideWarning(UserWarning):
    """Emitted when `station_override=` deliberately mismatches the contract's
    canonical settlement station. The output row carries `settlement_mismatch=True`."""


@dataclass(frozen=True)
class _Resolved:
    """Internal resolution of a selector → list of (station, contract_id?) pairs."""
    stations: tuple[str, ...]
    contracts: tuple[str, ...] = ()
    mismatch: bool = False


def validate_selectors(
    station: str | None,
    city: str | None,
    contract: str | None,
    contracts: list[str] | tuple[str, ...] | None,
) -> str:
    """Validate that exactly one selector is provided; return the active name."""
    provided = [
        n for n in _SELECTOR_NAMES if locals().get(n) is not None and locals().get(n) != ""
    ]
    if not provided:
        raise ValueError(
            "research(): one of station=, city=, contract=, contracts= must be provided"
        )
    if len(provided) > 1:
        raise ValueError(
            f"research(): selectors are mutually exclusive; got {provided!r}"
        )
    return provided[0]


def resolve_contract(contract_id: str) -> tuple[str, str]:
    """Resolve a `"<issuer>:<contract_id>"` string to `(station, issuer)`.

    Supported issuer prefixes: `kalshi:` (NHIGH/NLOW), `polymarket:` (US cities).
    """
    if ":" not in contract_id:
        raise ValueError(
            f"contract id must be `<issuer>:<id>`; got {contract_id!r}"
        )
    issuer, raw = contract_id.split(":", 1)
    issuer = issuer.lower()
    if issuer == "kalshi":
        from datetime import date as _date

        from tradewinds.markets.catalog import kalshi_nhigh, kalshi_nlow

        if raw.upper().startswith("KHIGH") or raw.upper().startswith("KXHIGH"):
            r = kalshi_nhigh.resolve(raw, _date.today())
            return r.settlement_station, "kalshi"
        if raw.upper().startswith("KLOW") or raw.upper().startswith("KXLOW"):
            r = kalshi_nlow.resolve(raw, _date.today())
            return r.settlement_station, "kalshi"
        raise ValueError(f"unsupported kalshi contract format: {raw!r}")
    elif issuer == "polymarket":
        # Polymarket uses event_id → station via _per_event_station.
        # Phase 10 v0.2 scope: pass through event id; resolver wires later.
        # Returns ("KLGA", "polymarket") as a placeholder for NYC.
        raise NotImplementedError(
            "polymarket contract resolution requires event_id → station lookup; "
            "Phase 10 wires this via tradewinds.markets._per_event_station + a "
            "city-to-station fallback once polymarket_discover() is integrated."
        )
    raise ValueError(f"unknown issuer prefix: {issuer!r}")


def resolve_city(city: str) -> tuple[str, ...]:
    """Resolve a city slug (e.g. "NYC") to all stations that any issuer
    settles against. Returns deduplicated tuple in stable order.

    For NYC: returns ("KNYC", "KLGA", "KJFK", "KEWR") — KNYC is Kalshi's
    settlement station, KLGA is Polymarket's, KJFK + KEWR are the
    backstop public stations that Polymarket's denylist forbids
    (intentionally surfaced so quants see the full neighborhood).
    """
    from tradewinds.markets._per_event_station import load_polymarket_city_stations
    from tradewinds.markets.catalog.kalshi_stations import KALSHI_SETTLEMENT_STATIONS
    from tradewinds.markets.polymarket import KNOWN_WRONG_STATIONS as POLY_WRONG

    out: list[str] = []
    city_upper = city.upper()
    city_lower = city.lower()
    if city_upper in KALSHI_SETTLEMENT_STATIONS:
        out.append(KALSHI_SETTLEMENT_STATIONS[city_upper].station)
    poly = load_polymarket_city_stations()
    if city_lower in poly:
        for v in poly[city_lower].values():
            if v not in out:
                out.append(v)
    # Surface the per-city Polymarket denylist too — quants want to SEE
    # which stations are forbidden (and why) for explicit station_override.
    for st in POLY_WRONG.get(city_lower, frozenset()):
        if st not in out:
            out.append(st)
    if not out:
        raise ValueError(f"unknown city {city!r}; not in kalshi or polymarket catalogs")
    return tuple(out)


def annotate_settles_for(station: str, city: str | None) -> list[str]:
    """Return the list of issuer:contract markers that settle against `station`."""
    from tradewinds.markets._per_event_station import load_polymarket_city_stations
    from tradewinds.markets.catalog.kalshi_stations import KALSHI_SETTLEMENT_STATIONS

    out: list[str] = []
    if city is not None:
        city_upper = city.upper()
        city_lower = city.lower()
        if (
            city_upper in KALSHI_SETTLEMENT_STATIONS
            and KALSHI_SETTLEMENT_STATIONS[city_upper].station == station
        ):
            out.append(f"kalshi:{city_upper}")
        poly = load_polymarket_city_stations()
        if city_lower in poly and station in poly[city_lower].values():
            out.append(f"polymarket:{city_lower}")
    return out


__all__ = [
    "StationOverrideWarning",
    "annotate_settles_for",
    "resolve_city",
    "resolve_contract",
    "validate_selectors",
]
```
</action>

<acceptance_criteria>
- `validate_selectors(station="KNYC", city=None, contract=None, contracts=None)` returns `"station"`.
- `validate_selectors(None, None, None, None)` raises ValueError.
- `validate_selectors(station="KNYC", city="NYC", ...)` raises ValueError ("mutually exclusive").
- `resolve_contract("kalshi:KXHIGHNYC")` returns `("KNYC", "kalshi")`.
- `resolve_contract("kalshi:KLOWNYC")` returns `("KNYC", "kalshi")`.
- `resolve_contract("polymarket:abc")` raises NotImplementedError with actionable message.
- `resolve_city("NYC")` returns tuple including KNYC AND KLGA.
- `annotate_settles_for("KNYC", "NYC")` returns `["kalshi:NYC"]`.
- `annotate_settles_for("KLGA", "NYC")` returns `["polymarket:nyc"]`.
- `StationOverrideWarning` is a `UserWarning` subclass.
</acceptance_criteria>

### Task 1.2: Widen `research()` signature with composable kwargs

<action>
Update `packages/core/src/tradewinds/research.py` signature to add new optional kwargs without breaking the existing `(station, from_date, to_date)` positional contract:

```python
def research(
    station: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    *,
    city: str | None = None,
    contract: str | None = None,
    contracts: list[str] | tuple[str, ...] | None = None,
    station_override: str | None = None,
    sources: list[str] | tuple[str, ...] | None = None,
    source: str | None = None,
    include_trades: bool = False,
    include_forecast: bool = False,
    forecast_model: str | None = None,
    as_dataframe: bool = True,
    tz_override: str | None = None,
    qc: bool = False,
    backend: str = "pandas",
    return_type: str = "dataframe",
) -> Any:
    # Backwards compat short-circuit: if station + dates positional, behave EXACTLY
    # as before — no selector validation, no compose dispatch, no annotations.
    # This preserves all 5 Phase 1 parity fixtures byte-equivalent.
    if station is not None and city is None and contract is None and contracts is None:
        # Validate from_date / to_date required when station= is the selector.
        if from_date is None or to_date is None:
            raise ValueError("research(station=...) requires from_date and to_date")
        # `station_override` is meaningless without a contract — error if both passed.
        if station_override is not None:
            raise ValueError(
                "station_override= requires contract= (not standalone station=)"
            )
        # `sources` / `source` mutually exclusive.
        if sources is not None and source is not None:
            raise ValueError("sources= and source= are mutually exclusive")
        # ... existing station-based body unchanged ...
        return _research_by_station(
            station, from_date, to_date,
            include_forecast=include_forecast,
            forecast_model=forecast_model,
            as_dataframe=as_dataframe,
            tz_override=tz_override,
            qc=qc,
            backend=backend,
            return_type=return_type,
        )

    # NEW selector dispatch (city / contract / contracts).
    from tradewinds._compose import validate_selectors

    selector = validate_selectors(station, city, contract, contracts)
    # ... dispatch to _research_by_city / _research_by_contract / _research_by_contracts ...
```

The existing station-path body becomes `_research_by_station` (an internal helper); selector dispatch routes to new private helpers per selector.

The Phase 1 parity gate (`tests/test_parity.py`) MUST stay byte-equivalent. Run it as the FIRST gate after refactoring.
</action>

<acceptance_criteria>
- Existing `research("NYC", "2025-01-06", "2025-01-12")` works unchanged.
- `tests/test_parity.py::test_dtypes_match_ground_truth` still passes.
- `research(station="NYC", city="NYC", from_date=..., to_date=...)` raises ValueError ("mutually exclusive").
- `research()` (no args) raises ValueError ("one of ... must be provided").
- `research(station="NYC")` (no dates) raises ValueError ("requires from_date and to_date").
- `research(station="NYC", from_date=..., to_date=..., station_override="KLAX")` raises ValueError (override requires contract).
- `research(station="NYC", from_date=..., to_date=..., sources=[...], source="iem.archive")` raises ValueError (mutually exclusive).
</acceptance_criteria>

### Task 1.3: `discover(city=...)` ergonomic surface

<action>
Create `packages/core/src/tradewinds/discover.py`:

```python
"""Phase 10 — discover() ergonomic surface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


def discover(*, city: str) -> "pd.DataFrame":
    """Return per-station discovery table for ``city``.

    Each row is a (city, station, settles_for) triple showing which
    issuer:contract markers settle against that station. Use this to
    pick the right selector before invoking research().

    Columns: city (str), station (str), settles_for (list[str]).
    """
    try:
        import pandas as pd
    except ImportError as exc:
        from tradewinds.core.exceptions import SourceUnavailableError

        raise SourceUnavailableError(
            "tradewinds.discover requires pandas. Install with: pip install tradewinds[parquet]",
            source="discover",
            retryable=False,
            underlying=str(exc),
        ) from None

    from tradewinds._compose import annotate_settles_for, resolve_city

    stations = resolve_city(city)
    rows = [
        {
            "city": city,
            "station": station,
            "settles_for": annotate_settles_for(station, city),
        }
        for station in stations
    ]
    df = pd.DataFrame(rows, columns=["city", "station", "settles_for"])
    df.attrs["city"] = city
    df.attrs["source"] = "discover"
    return df


__all__ = ["discover"]
```

Re-export from `packages/core/src/tradewinds/__init__.py`.
</action>

<acceptance_criteria>
- `discover(city="NYC")` returns DataFrame with rows for KNYC, KLGA (+ denylist entries).
- KNYC row's `settles_for` includes `"kalshi:NYC"`.
- KLGA row's `settles_for` includes `"polymarket:nyc"`.
- KJFK row's `settles_for` is `[]` (in NYC denylist but not a settlement target).
- `from tradewinds import discover` works.
</acceptance_criteria>

### Task 1.4: TS paired surface

<action>
Mirror in `packages-ts/core/src/research/compose.ts` + `discovery/discover.ts`:
1. Union-type selector for `research()` options object.
2. TS-level mutual-exclusion enforced via discriminated union (one of `station` / `city` / `contract` / `contracts`).
3. `StationOverrideWarning` emitted via existing `onWarning?` callback in research options (TS has no `warnings.warn()` equivalent).
4. `discover({ city })` mirrors Python behavior.

Update `packages-ts/core/package.json` exports if a new subpath is needed.
</action>

<acceptance_criteria>
- TS `research({ station, fromDate, toDate })` works unchanged (existing tests pass).
- TS `research({ station, city, fromDate, toDate })` raises at the type level (TS won't compile) + at runtime if the type check is bypassed.
- TS `discover({ city: "NYC" })` returns rows mirroring Python output.
- `pnpm --filter @tradewinds/core typecheck` exits 0.
</acceptance_criteria>

### Task 1.5: Tests + review loop + merge

<action>
1. Run `uv run pytest -m "not live" -q` — must pass with all new tests included.
2. Run `pnpm -r --filter '@tradewinds/core' --filter '@tradewinds/markets' exec vitest run`.
3. Dispatch review per REVIEW-DISCIPLINE.md mixed routing (codex high + python + ts architects).
4. Iterate fixes; cap at 5 iterations.
5. Update STATE.md with Phase 10 closeout.
6. Rebase against main (Phase 6 + 7 + 8 + 9 all already there) + merge `--no-ff`.
</action>

<acceptance_criteria>
- All three reviewers final-iter PASS.
- Parity gate (`tests/test_parity.py`) byte-equivalent.
- STATE.md updated.
- Branch merges cleanly.
</acceptance_criteria>

## Out of scope

- Polymarket contract resolution from event_id (needs Phase 9's `polymarket_discover` integration; Phase 10 v0.2 raises NotImplementedError with actionable message and defers to v0.3).
- New issuers beyond Kalshi + Polymarket (PredictIt, Manifold) — v0.3.
- Real-time streaming of joined data — v0.3.
- Statistical basis-trade strategies (this phase ships the data plumbing only).

## Review panel

Per REVIEW-DISCIPLINE.md mixed routing (Python + TS in same PR): codex `high` + Python Architect + TS Architect in parallel. User-authorized 5-iteration cap. API surface evolution is signature-design-heavy — focus on backward-compat invariants + mutual-exclusion validation + the parity fixture pre-flight gate.
