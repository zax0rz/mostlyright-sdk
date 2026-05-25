"""Tests for ``mostlyright.international.daily_extremes`` (Phase 3.1).

Exercises the new ``daily_extremes(station, from_date, to_date)`` rollup:

- Station-local IANA calendar-day bucketing across timezone shifts.
- ``low_coverage`` gate (n_obs < 12 → nulled extremes + WARNING log).
- Whole-°C international rounding vs 0.1°C US.
- Source provenance preserved per extreme (``source_tmin``, ``source_tmax``).
- Empty / partial-cache handling.

Cache reads are monkey-patched on ``mostlyright.weather.cache.read_cache``
because ``daily_extremes`` imports the cache module lazily — patching the
module attribute is enough.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import pytest
from mostlyright import international as intl


def _build_hourly_rows(
    start_utc: datetime,
    n_hours: int,
    temps: list[float],
    source: str = "iem",
    station_code: str = "RJTT",
    precip: list[float] | None = None,
) -> list[dict]:
    """Build n_hours of synthetic METAR rows starting at start_utc UTC.

    ``temps[i]`` becomes row ``i``'s ``temp_c``. If ``precip`` is provided,
    same indexing applies to ``precip_1hr_inches``.
    """
    assert len(temps) == n_hours
    rows = []
    for i in range(n_hours):
        ts = (start_utc + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = {
            "station_code": station_code,
            "observed_at": ts,
            "temp_c": temps[i],
            "source": source,
        }
        if precip is not None:
            row["precip_1hr_inches"] = precip[i]
        rows.append(row)
    return rows


def _patch_cache_with_rows(monkeypatch, rows: list[dict]) -> None:
    """Patch ``read_cache`` to behave like the real UTC-keyed parquet cache.

    Returns only the rows whose ``observed_at`` UTC year/month matches the
    requested ``(year, month)`` key. This mirrors the production behavior:
    the on-disk cache file at ``<icao>/<UTC-year>/<UTC-month>.parquet``
    only contains rows whose UTC year-month equals the file's key.

    Phase 3.1 review caught: the original lambda returned the same list for
    EVERY ``(y, m)`` call, which (a) duplicated rows when ``daily_extremes``
    legitimately reads an adjacent UTC month to cover a station-local day,
    and (b) hid the month-boundary bug it was meant to detect.
    """
    from mostlyright.weather import cache as cache_mod

    def _read_cache(station: str, year: int, month: int):
        out = [r for r in rows if r.get("observed_at", "").startswith(f"{year:04d}-{month:02d}-")]
        return out or None

    monkeypatch.setattr(cache_mod, "read_cache", _read_cache)


def _patch_cache_with_month_map(monkeypatch, by_month: dict[tuple[int, int], list[dict]]) -> None:
    """Patch ``read_cache`` to consult a (year, month) -> rows table."""
    from mostlyright.weather import cache as cache_mod

    def _read_cache(station: str, year: int, month: int):
        return by_month.get((year, month))

    monkeypatch.setattr(cache_mod, "read_cache", _read_cache)


# ---------------------------------------------------------------------------
# Tokyo (UTC+9) — basic day-bucketing + whole-°C international rounding.
# ---------------------------------------------------------------------------
def test_daily_extremes_tokyo_local_day_bucketing(monkeypatch):
    """UTC 15:00 Jan 1 = JST 00:00 Jan 2; UTC 14:59 Jan 1 = JST 23:59 Jan 1."""
    rows = []
    # 12 hourly observations on Jan 1 UTC 03:00-14:00 → JST 12:00-23:00 Jan 1.
    rows += _build_hourly_rows(
        datetime(2025, 1, 1, 3, 0, tzinfo=UTC),
        12,
        temps=[10.0 + i * 0.5 for i in range(12)],  # 10.0 ... 15.5
        station_code="RJTT",
    )
    # 12 more on Jan 1 UTC 15:00 - Jan 2 UTC 02:00 → JST 00:00-11:00 Jan 2.
    rows += _build_hourly_rows(
        datetime(2025, 1, 1, 15, 0, tzinfo=UTC),
        12,
        temps=[5.0 - i * 0.3 for i in range(12)],  # 5.0 ... 1.7
        station_code="RJTT",
    )
    _patch_cache_with_rows(monkeypatch, rows)

    out = intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 2))
    by_date = {r["local_date"]: r for r in out}
    assert "2025-01-01" in by_date
    assert "2025-01-02" in by_date
    jan1 = by_date["2025-01-01"]
    assert jan1["n_obs"] == 12
    # Intl precision = whole °C: max 15.5 rounds HALF_UP to 16; min 10.0 stays 10.
    assert jan1["tmax_c"] == 16.0
    assert jan1["tmin_c"] == 10.0
    assert jan1["country"] == "JP"
    assert jan1["station"] == "RJTT"


def test_daily_extremes_tokyo_whole_degree_rounding(monkeypatch):
    """Round-HALF-UP for international: 2.5 → 3.0, 2.4 → 2.0."""
    # 12 obs with explicit fractional temps to exercise the rounding boundary.
    rows = _build_hourly_rows(
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        12,
        temps=[2.5] * 6 + [2.4] * 6,
        station_code="RJTT",
    )
    _patch_cache_with_rows(monkeypatch, rows)
    out = intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 1))
    assert len(out) == 1
    # max=2.5 → 3.0 (HALF_UP, not banker's), min=2.4 → 2.0
    assert out[0]["tmax_c"] == 3.0
    assert out[0]["tmin_c"] == 2.0


# ---------------------------------------------------------------------------
# Buenos Aires (UTC-3) — southern-hemisphere station.
# ---------------------------------------------------------------------------
def test_daily_extremes_buenos_aires_negative_offset(monkeypatch):
    """UTC 02:00 = BA 23:00 previous day (UTC-3)."""
    # 13 obs spanning UTC 03:00 - UTC 15:00 Jan 1 → BA 00:00-12:00 Jan 1.
    rows = _build_hourly_rows(
        datetime(2025, 1, 1, 3, 0, tzinfo=UTC),
        13,
        temps=[25.0 + i for i in range(13)],  # 25..37
        station_code="SAEZ",
    )
    _patch_cache_with_rows(monkeypatch, rows)
    out = intl.daily_extremes("SAEZ", date(2025, 1, 1), date(2025, 1, 1))
    assert len(out) == 1
    assert out[0]["n_obs"] == 13
    assert out[0]["tmin_c"] == 25.0
    assert out[0]["tmax_c"] == 37.0
    assert out[0]["country"] == "AR"


# ---------------------------------------------------------------------------
# Wellington (UTC+12/13 DST) — DST-active station, southern hemisphere.
# ---------------------------------------------------------------------------
def test_daily_extremes_wellington_dst(monkeypatch):
    """Wellington is NZDT (UTC+13) in January (southern hemisphere summer)."""
    # 12 obs UTC 00:00-11:00 Jan 1 → NZDT 13:00-23:59 Jan 1 (and 00:00 Jan 2).
    # All 12 are still Jan 1 in NZDT (13..23 NZDT + 1 spill).
    rows = _build_hourly_rows(
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        12,
        temps=[18.0] * 12,
        station_code="NZWN",
    )
    _patch_cache_with_rows(monkeypatch, rows)
    # UTC 00:00 + 13h offset = NZDT 13:00 Jan 1.
    # UTC 11:00 + 13h offset = NZDT 00:00 Jan 2.
    out = intl.daily_extremes("NZWN", date(2025, 1, 1), date(2025, 1, 2))
    dates = {r["local_date"] for r in out}
    assert dates == {"2025-01-01", "2025-01-02"}


# ---------------------------------------------------------------------------
# Low-coverage gate.
# ---------------------------------------------------------------------------
def test_daily_extremes_low_coverage_nulls_temps_and_warns(monkeypatch, caplog):
    """n_obs < 12 → tmin/tmax/tmean null + WARNING with 'low_coverage'."""
    # Only 5 obs — below the 12-threshold.
    rows = _build_hourly_rows(
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        5,
        temps=[1.0, 2.0, 3.0, 4.0, 5.0],
        station_code="RJTT",
    )
    _patch_cache_with_rows(monkeypatch, rows)

    with caplog.at_level(logging.WARNING, logger=intl.__name__):
        out = intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 1))
    assert len(out) == 1
    row = out[0]
    assert row["n_obs"] == 5
    assert row["tmin_c"] is None
    assert row["tmax_c"] is None
    assert row["tmean_c"] is None
    assert row["source_tmin"] is None
    assert row["source_tmax"] is None
    # WARNING fired with 'low_coverage' keyword.
    assert any("low_coverage" in r.getMessage() for r in caplog.records)


def test_daily_extremes_at_threshold_publishes_temps(monkeypatch):
    """n_obs == 12 → temps published (threshold is strict ``<``)."""
    rows = _build_hourly_rows(
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        12,
        temps=list(range(12)),
        station_code="RJTT",
    )
    _patch_cache_with_rows(monkeypatch, rows)
    out = intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 1))
    assert out[0]["n_obs"] == 12
    assert out[0]["tmin_c"] is not None
    assert out[0]["tmax_c"] is not None


# ---------------------------------------------------------------------------
# US (NYC, 0.1°C precision).
# ---------------------------------------------------------------------------
def test_daily_extremes_us_keeps_tenth_precision(monkeypatch):
    """US stations preserve 0.1°C precision."""
    # 12 obs all on Jan 1 UTC 12:00-23:00 → NYC EST 07:00-18:00 Jan 1.
    rows = _build_hourly_rows(
        datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
        12,
        temps=[10.05] + [11.34] * 5 + [12.55] * 5 + [9.07],
        station_code="NYC",
    )
    _patch_cache_with_rows(monkeypatch, rows)
    out = intl.daily_extremes("KNYC", date(2025, 1, 1), date(2025, 1, 1))
    assert len(out) == 1
    # 0.1°C precision (HALF_UP): max 12.55 → 12.6; min 9.07 → 9.1.
    assert out[0]["tmax_c"] == 12.6
    assert out[0]["tmin_c"] == 9.1
    assert out[0]["country"] == "US"


# ---------------------------------------------------------------------------
# Source provenance per extreme.
# ---------------------------------------------------------------------------
def test_daily_extremes_source_tmin_tmax_preserved(monkeypatch):
    """source_tmin/source_tmax point to the actual contributing row."""
    rows = []
    # 11 boring iem obs + 1 awc obs that wins both extremes.
    for i in range(11):
        ts = datetime(2025, 1, 1, i, 0, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append(
            {
                "station_code": "RJTT",
                "observed_at": ts,
                "temp_c": 5.0,
                "source": "iem",
            }
        )
    # AWC row with the day's maximum.
    rows.append(
        {
            "station_code": "RJTT",
            "observed_at": "2025-01-01T11:00:00Z",
            "temp_c": 25.0,
            "source": "awc",
        }
    )
    _patch_cache_with_rows(monkeypatch, rows)
    out = intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 1))
    assert out[0]["source_tmax"] == "awc"
    # 11 iem rows all at 5.0 — first-min wins by min()'s stable semantics.
    assert out[0]["source_tmin"] == "iem"


# ---------------------------------------------------------------------------
# Precip aggregation + null handling.
# ---------------------------------------------------------------------------
def test_daily_extremes_precip_sum(monkeypatch):
    """precip_inches is the sum of non-null hourly precip across the day."""
    rows = _build_hourly_rows(
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        12,
        temps=[10.0] * 12,
        station_code="RJTT",
        precip=[0.01] * 6 + [0.0] * 6,
    )
    _patch_cache_with_rows(monkeypatch, rows)
    out = intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 1))
    # 6 * 0.01 = 0.06
    assert out[0]["precip_inches"] == pytest.approx(0.06, abs=1e-6)


# ---------------------------------------------------------------------------
# Window filtering — only return rows for [from_date, to_date].
# ---------------------------------------------------------------------------
def test_daily_extremes_window_filtering(monkeypatch):
    """Rows outside [from_date, to_date] (local-date) must be dropped."""
    # Build rows spanning Jan 1-3 in JST.
    rows = []
    for d in (1, 2, 3):
        rows += _build_hourly_rows(
            datetime(2025, 1, d, 3, 0, tzinfo=UTC),  # JST 12:00
            12,
            temps=[10.0] * 12,
            station_code="RJTT",
        )
    _patch_cache_with_rows(monkeypatch, rows)
    out = intl.daily_extremes("RJTT", date(2025, 1, 2), date(2025, 1, 2))
    dates = {r["local_date"] for r in out}
    assert dates == {"2025-01-02"}


# ---------------------------------------------------------------------------
# Cache returning None for some months.
# ---------------------------------------------------------------------------
def test_daily_extremes_partial_cache_skips_silently(monkeypatch):
    """A None return from read_cache (current LST month) is a silent skip."""
    rows_jan = _build_hourly_rows(
        datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
        12,
        temps=[10.0] * 12,
        station_code="RJTT",
    )
    _patch_cache_with_month_map(monkeypatch, {(2025, 1): rows_jan, (2025, 2): None})
    out = intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 2, 28))
    # Only Jan 1 has data (12 obs ≤ JST 12:00-23:00 Jan 1).
    dates = {r["local_date"] for r in out}
    assert "2025-01-01" in dates
    # No Feb rows shipped — month was None.
    assert not any(d.startswith("2025-02") for d in dates)


# ---------------------------------------------------------------------------
# Month-boundary correctness — the UTC cache month and the station-local
# calendar month don't line up for any non-UTC station. The codex + arch
# review caught that reading only the local-month cache files silently drops
# the leading or trailing slice of a local day at the month boundary; the
# fix is to compute the UTC-month envelope from the local window + tz, so
# the cache is consulted for every month that could possibly contain rows
# falling into the requested local-day window.
# ---------------------------------------------------------------------------
def test_daily_extremes_month_boundary_reads_adjacent_utc_month_tokyo(monkeypatch):
    """JST Feb 1 = UTC Jan 31 15:00 → UTC Feb 1 14:59. Code must read both UTC months."""
    # UTC Jan 31 15:00..23:00 → JST Feb 1 00:00..08:00 (9 rows).
    rows_jan = _build_hourly_rows(
        datetime(2025, 1, 31, 15, 0, tzinfo=UTC),
        9,
        temps=[-10.0, -8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0],
        station_code="RJTT",
    )
    # UTC Feb 1 00:00..14:00 → JST Feb 1 09:00..23:00 (15 rows).
    rows_feb = _build_hourly_rows(
        datetime(2025, 2, 1, 0, 0, tzinfo=UTC),
        15,
        temps=[
            8.0,
            9.0,
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
            14.0,
            13.0,
            12.0,
            11.0,
            10.0,
            9.0,
            8.0,
        ],
        station_code="RJTT",
    )
    _patch_cache_with_month_map(
        monkeypatch,
        {(2025, 1): rows_jan, (2025, 2): rows_feb},
    )
    out = intl.daily_extremes("RJTT", date(2025, 2, 1), date(2025, 2, 1))
    assert len(out) == 1
    row = out[0]
    assert row["local_date"] == "2025-02-01"
    # All 24 hours (9 from Jan UTC + 15 from Feb UTC) bucketed into JST Feb 1.
    assert row["n_obs"] == 24
    # tmax_c is 15.0 (mid-afternoon JST); tmin_c is -10.0 (just after midnight JST).
    # Whole-°C rounding for intl: 15.0 and -10.0 both stay whole.
    assert row["tmax_c"] == 15.0
    assert row["tmin_c"] == -10.0


def test_daily_extremes_month_boundary_negative_offset_buenos_aires(monkeypatch):
    """Buenos Aires UTC-3 — local Jan 31 ends at UTC Feb 1 03:00. Code must read Feb cache too."""
    # UTC Jan 31 03:00..23:00 → ART Jan 31 00:00..20:00 (21 rows).
    rows_jan = _build_hourly_rows(
        datetime(2025, 1, 31, 3, 0, tzinfo=UTC),
        21,
        temps=[20.0 + i * 0.5 for i in range(21)],
        station_code="SAEZ",
    )
    # UTC Feb 1 00:00..02:00 → ART Jan 31 21:00..23:00 (3 rows).
    rows_feb = _build_hourly_rows(
        datetime(2025, 2, 1, 0, 0, tzinfo=UTC),
        3,
        temps=[26.0, 25.5, 25.0],
        station_code="SAEZ",
    )
    _patch_cache_with_month_map(
        monkeypatch,
        {(2025, 1): rows_jan, (2025, 2): rows_feb},
    )
    out = intl.daily_extremes("SAEZ", date(2025, 1, 31), date(2025, 1, 31))
    assert len(out) == 1
    row = out[0]
    assert row["local_date"] == "2025-01-31"
    assert row["n_obs"] == 24  # 21 from Jan UTC + 3 from Feb UTC.


# ---------------------------------------------------------------------------
# Defensive: unknown station + invalid merge.
# ---------------------------------------------------------------------------
def test_daily_extremes_unknown_station_raises():
    with pytest.raises(KeyError, match="Unknown station"):
        intl.daily_extremes("ZZZZ", date(2025, 1, 1), date(2025, 1, 1))


def test_daily_extremes_bad_merge_raises():
    with pytest.raises(ValueError, match="unsupported"):
        intl.daily_extremes("RJTT", date(2025, 1, 1), date(2025, 1, 1), merge="experimental_v3")
