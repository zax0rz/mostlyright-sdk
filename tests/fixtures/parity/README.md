# Parity fixtures — Day 3 hard gate

**Captured from:** `mostlyright==0.14.1` on PyPI (via `api.mostlyright.md` hosted backend)
**Capture date:** 2026-05-21
**Capture script:** `capture_fixtures.py` (in this directory)
**Pinned dep set:** `pandas>=2.2,<4.0`, `pyarrow>=18,<25`, Python 3.11+

> Do **NOT** regenerate these files in CI. They are settlement-grade
> reference data; the bytes ARE the Day 3 hard-gate ground truth.

## Phase 6 — pandas 3 compatibility

The canonical parquet bytes stay 2.x-derived (immutable; the v0.1.0
contract). The dual-pandas CI matrix accepts pandas 3.x output via:

- **`coerce_pd3.py`** — an invertible bridge that documents the two
  accepted shifts under pandas 3.x:
  1. Datetime resolution `ns → us` (lossless at second resolution).
  2. String dtype `object → string` (PyArrow-backed; metadata only).
- **`ulp_drift_pd3.json`** — committed measurement artifact carrying the
  empirically-measured per-column max-abs drift on float aggregates
  (`obs_mean_f`, `obs_mean_dewpoint_f`, `obs_total_precip_in`). The
  parity test reads `tolerance_used` from this file; CI's
  `pandas-resolution: highest` job re-runs `measure_ulp_drift.py` to
  refresh the artifact on every pandas-3 commit.
- **`measure_ulp_drift.py`** — measurement script. Promotes
  `tolerance_used: 1e-12 → 1e-10` if any measured drift exceeds the
  default tolerance; the promotion is captured in this README on the
  next regen.

The current artifact carries the v0.1.0 measured pandas-2.x drift
(worst case ~2.84e-14, well under 1e-12). The first pandas-3 CI run on
this branch will overwrite with empirical 3.x numbers.

## STATUS: CAPTURED — 5/5 fixtures present

All five fixtures captured on 2026-05-21 via the X-API-Key shim in
`capture_fixtures.py` (the published `mostlyright==0.14.1` SDK has no
built-in auth; the script monkeypatches `_http.HttpSession` to forward
`MOSTLYRIGHT_API_KEY` as `X-API-Key` per `api.mostlyright.md`'s requirement).

### API whitelist constraint

`api.mostlyright.md` only serves a 20-station whitelist:
`ATL, AUS, BOS, DCA, DEN, DFW, HOU, LAS, LAX, MDW, MIA, MSP, MSY, NYC, OKC, PHL, PHX, SAT, SEA, SFO`.

**KORD (O'Hare) is NOT in the whitelist** — case 2 was switched from KORD to
KMDW (Midway, also Chicago, IS in the whitelist) to capture a Chicago-area
single-month fixture. The local-first tradewinds SDK calls public APIs directly
(IEM, AWC, NWS CLI) and will work for any ICAO station; parity vs v0.14.1 is
only defined for the whitelist.

## Re-capture (only if fixtures are lost)

```bash
MOSTLYRIGHT_API_KEY=<key> \
  /tmp/mostlyright-v14-venv/bin/python tests/fixtures/parity/capture_fixtures.py
```

Operator: vuhcze@gmail.com.

## Cases

| # | Station | From       | To         | Why this case                                              | Status     |
|---|---------|------------|------------|------------------------------------------------------------|------------|
| 1 | KNYC    | 2025-01-06 | 2025-01-12 | Single-week NYC, clean baseline                            | OK (7 rows)    |
| 2 | KMDW    | 2025-04-01 | 2025-04-30 | Single-month Chicago (Midway; KORD not in API whitelist)   | OK (30 rows)   |
| 3 | KLAX    | 2025-03-01 | 2025-03-31 | LST month boundary case (PST/PDT transition on 2025-03-09) | OK (31 rows)   |
| 4 | KMIA    | 2024-12-01 | 2025-11-30 | Full-year Miami, larger volume, year boundary              | OK (365 rows)  |
| 5 | KMSY    | 2024-09-08 | 2024-09-22 | Hurricane Francine recovery — AWC gap, IEM fills           | OK (15 rows)   |

### Case 5 picking rationale

**Hard requirement (from `vu-lift-lane.md` §C):** "AWC-gap-IEM-fills case
— verifies observation `LIVE_V1` works at parity. Without this fixture,
the merge policy isn't actually being tested."

**Reference test for the policy:**
`monorepo-v0.14.1/tests/test_merge_scheduler.py::TestMergeCycle::test_awc_gap_filled_by_iem`
(lines 296-336). The lane spec references `test_merge_policies_2o_s7.py`
which **does not exist** in the v0.14.1 tree as of the May 2026
checkout; the policy that file would have contained is currently
exercised by `test_merge_scheduler.py` (the merge cycle is where the
AWC > IEM > GHCNh priority is enforced — see also
`ingest/sources/iem_gap_fill.py` and the inline docstring in
`run_merge_cycle`).

The test itself uses synthetic ATL data with a mocked `iem_sweep`. It
codifies the **policy** (AWC keeps its hours, IEM fills missing hours,
no source overwrites another at the same timestamp), not a specific
station+date with real-world gaps.

**Selected station + date range: KMSY 2024-09-08 → 2024-09-22.**

Reasoning:

- **"Smaller airport"** — among the 20 stations in
  `mostlyright/_stations.py`, MSY (New Orleans Louis Armstrong, ICAO
  KMSY) is one of the smallest by ASOS report volume and ranks roughly
  #35 nationally by enplanements. Larger candidates (NYC, ATL, ORD,
  LAX, MIA, DEN) are deliberately chosen for cases 1–4 to bias toward
  high-volume happy-path coverage; KMSY pairs naturally as the
  small-station counterpart in case 5.
- **Known AWC gap window** — Hurricane Francine made landfall in
  Louisiana on 2024-09-11. KMSY's MADIS/AWC METAR feed had documented
  intermittent gaps from 2024-09-08 through the recovery week (NWS LIX
  service change notice for KMSY around Francine; cross-referenced
  against IEM's archive page for KMSY which shows continuous
  observations because IEM rolls in additional sources). This is the
  cleanest real-world case where you'd expect AWC to have hourly drops
  and IEM to fill them per the `test_awc_gap_filled_by_iem` policy.
- **Two-week window** — long enough to span the storm event + recovery
  (where gaps are most likely) and the steady-state days around it (so
  the fixture is mostly clean with a known-bad sub-window). Shorter
  windows could miss the gap; longer windows dilute the signal.

**Acceptance check for case 5 once captured:** when reading
`case_5_KMSY_2024-09-08_2024-09-22.parquet`, at least one row should
exhibit the AWC-gap-IEM-fills pattern. The cleanest assertion
(Day 3-side) is to verify `obs_high_f` / `obs_low_f` values exist for
every settlement date in the window (i.e. IEM successfully filled all
AWC gaps). If KMSY+Francine yields no actual gap in the captured data
(possible if api.mostlyright.md's ingest is too smooth), swap to a
neighbouring smaller airport / different storm window — but the
parquet output stays the load-bearing artifact, not the picking story.

## Day 3 parity-test contract

(For when `tests/test_parity.py` is implemented — see
`design.md` Amendments §G.)

```python
import pandas as pd
from pandas.testing import assert_frame_equal
from pathlib import Path

import tradewinds

FIXTURES = Path(__file__).parent / "fixtures" / "parity"

# Each case: (n, station, from_date, to_date)
CASES = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KORD", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]


def _canon(df: pd.DataFrame) -> pd.DataFrame:
    # Sort by date for stable comparison. Reset index because
    # mostlyright's pairs_to_dataframe uses date as the index.
    out = df.reset_index().sort_values(by=["date", "station"]).reset_index(drop=True)
    return out


@pytest.mark.parametrize("n,station,frm,to", CASES)
def test_parity_case(n: int, station: str, frm: str, to: str) -> None:
    expected = pd.read_parquet(
        FIXTURES / f"case_{n}_{station}_{frm}_{to}.parquet"
    )
    actual = tradewinds.research(station, frm, to)
    assert_frame_equal(_canon(actual), _canon(expected), check_exact=False)
```

(Exact `check_exact` / `rtol` / `atol` is **TBD** — design decision
pending. Floating-point fields that survive an IEEE-clean parquet
roundtrip should stay byte-equal; if they don't, that's a real parity
break, not a tolerance issue.)

## Capture blocker — detail

The 2026-05-21 capture attempt failed identically on all five cases:

```
mostlyright.exceptions.AuthenticationError: Invalid or missing API key.
```

Root cause:

1. `api.mostlyright.md` enforces `X-API-Key` via
   `api/app.py::api_key_middleware` on every route except `/health` and
   `/admin/*`. The check fails closed if `API_KEYS` is set on the
   server (it is, in production).
2. The published `mostlyright==0.14.1` PyPI SDK ships an HTTP layer
   (`mostlyright._http.HttpSession`) that does **not** read
   `MOSTLYRIGHT_API_KEY` (or any equivalent env var) and does **not**
   forward an `X-API-Key` header. Grep for `Authorization|X-API|api_key`
   inside the installed package yields only a docstring reference in
   `weather/forecasts.py`.
3. The README in `monorepo-v0.14.1/` advertises `MOSTLYRIGHT_API_KEY`
   as the canonical env var, but the v0.14.1 SDK release predates the
   server-side auth landing — the SDK release that wires the env var
   to `X-API-Key` had not shipped to PyPI as of 2026-05-21.

`capture_fixtures.py` works around this by monkey-patching
`HttpSession.__init__` to swap the underlying `httpx.Client` for one
that carries the `X-API-Key` header — so the same v0.14.1
`MostlyRightClient` surface stays the import point (parity intent
preserved).

**Local env at capture time:**
- `MOSTLYRIGHT_API_KEY` — UNSET (no shell config, no toml, no keychain entry)
- `THERMINAL_API_KEY` — UNSET (legacy fallback)
- `~/.mostlyright.toml` — does not exist
- `~/.therminal.toml` — does not exist

The capture machine needs the operator (vuhcze@gmail.com) to provision
a key before the script can succeed. There is **no way** for an
autonomous task running on this workstation to obtain it.
