"""Case-5 synthetic test: AWC gap filled by IEM.

Lifted from monorepo-v0.14.1/tests/test_merge_scheduler.py::TestMergeCycle::
test_awc_gap_filled_by_iem (lines 296-336). The scheduler wrapper
(staging files, ``run_merge_cycle``, ``iem_sweep`` mock) is stripped —
reduced to a pure ``merge_observations`` call. The case-5 KMSY fixture
(2024-09-11) is the Day 3 parity gate's largest gap-fill scenario, so
this test guards the exact 24-hour invariant the parity test depends on.

Source SHA: 514fcdab227e845145ca32b989355647466231d9
Lift date: 2026-05-21
"""

from __future__ import annotations

from typing import Any

from tradewinds._internal.merge.observations import merge_observations


def _make_obs(
    station_code: str,
    observed_at: str,
    source: str,
    **overrides: object,
) -> dict[str, Any]:
    """Minimal observation dict — only the dedup-key fields + source matter here.

    Trimmed down from the 30-field ``_make_obs`` in test_observations.py since
    the merge function only reads (station_code, observed_at, observation_type,
    source). Keeping the row narrow makes the failure-mode diagnostics easy.
    """
    base: dict[str, Any] = {
        "station_code": station_code,
        "observed_at": observed_at,
        "observation_type": "METAR",
        "source": source,
        "temp_c": 25.0,
    }
    base.update(overrides)
    return base


def _hour_iso(hour: int) -> str:
    """Build an RFC3339 timestamp for hour ``hour`` on 2024-09-11."""
    return f"2024-09-11T{hour:02d}:00:00Z"


def test_awc_gap_filled_by_iem_3_hour_minimal() -> None:
    """Minimal 3-hour reproduction from v0.14.1 test_merge_scheduler.py:296-336.

    AWC has 12:00 and 14:00. IEM has 12:00, 13:00, 14:00. After merge:
    AWC wins at 12 and 14, IEM fills 13. Total: 3 rows.
    """
    awc_12 = _make_obs("ATL", "2026-04-03T12:00:00Z", "awc")
    awc_14 = _make_obs("ATL", "2026-04-03T14:00:00Z", "awc")
    iem_12 = _make_obs("ATL", "2026-04-03T12:00:00Z", "iem")
    iem_13 = _make_obs("ATL", "2026-04-03T13:00:00Z", "iem")
    iem_14 = _make_obs("ATL", "2026-04-03T14:00:00Z", "iem")

    result = merge_observations([awc_12, awc_14, iem_12, iem_13, iem_14])
    assert len(result) == 3

    by_time = {r["observed_at"]: r for r in result}
    assert by_time["2026-04-03T12:00:00Z"]["source"] == "awc"
    assert by_time["2026-04-03T14:00:00Z"]["source"] == "awc"
    assert by_time["2026-04-03T13:00:00Z"]["source"] == "iem"


def test_awc_gap_filled_by_iem_case_5_KMSY_24h() -> None:
    """Case-5 reference: KMSY 2024-09-11 — AWC has hours [0..11, 18..23],
    IEM has all 24 hours. Merge yields 24 rows; hours 12-17 source=iem;
    all other hours source=awc.

    This is the synthetic preimage of the Day 3 parity test (Wave 3).
    Per RESEARCH.md R1: the hosted-API fixture may diverge by a row here
    or there due to upstream IEM/AWC backfill timing; the parity test
    handles that with a tolerance. THIS test pins the local-merge invariant.
    """
    awc_hours = list(range(0, 12)) + list(range(18, 24))  # gap 12-17
    iem_hours = list(range(0, 24))

    awc_rows = [_make_obs("KMSY", _hour_iso(h), "awc") for h in awc_hours]
    iem_rows = [_make_obs("KMSY", _hour_iso(h), "iem") for h in iem_hours]

    result = merge_observations(awc_rows + iem_rows)

    # Exactly 24 rows: 18 AWC + 6 IEM-fills
    assert len(result) == 24

    by_time = {r["observed_at"]: r for r in result}

    # Spec line 264: hours 12-17 from IEM
    for h in [12, 13, 14, 15, 16, 17]:
        ts = _hour_iso(h)
        assert ts in by_time, f"missing hour {h}"
        assert by_time[ts]["source"] == "iem", (
            f"hour {h}: expected iem (AWC-gap fill), got {by_time[ts]['source']}"
        )

    # All other hours from AWC
    for h in awc_hours:
        ts = _hour_iso(h)
        assert ts in by_time, f"missing hour {h}"
        assert by_time[ts]["source"] == "awc", (
            f"hour {h}: expected awc (priority over IEM), got {by_time[ts]['source']}"
        )


def test_awc_empty_iem_only_returns_iem() -> None:
    """Failure-mode G guard (PLAN.md line 682):

    If AWC fetcher silently returned [] (e.g. last-168h limitation),
    ``merge_observations([] + iem_rows)`` must return ``iem_rows`` unchanged.
    This is the cache-layer's safety net during cache-miss recovery.
    """
    iem_rows = [_make_obs("KMSY", _hour_iso(h), "iem") for h in range(24)]
    # Intentional `[] + iem_rows` (not `[*iem_rows]`) — mirrors the exact call
    # shape from PLAN.md line 682's failure-mode G description.
    result = merge_observations([] + iem_rows)  # noqa: RUF005
    assert len(result) == 24
    assert {r["source"] for r in result} == {"iem"}
