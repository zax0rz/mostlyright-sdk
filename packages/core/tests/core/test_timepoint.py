"""Tests for ``mostlyright.core.timepoint.TimePoint``.

Covers:
- Property-based round-trips (Hypothesis) for UTC datetimes and ISO strings
- DST spring-forward and fall-back in US timezones (2026 dates)
- Naive datetime / pd.Timestamp / ISO rejection
- Date-only ISO string rejection
- Microsecond preservation through ISO round-trip and to_utc()
- Comparison and hashing semantics
- ``TimePoint.now()`` proximity to current UTC time
- ``TimePoint.from_pandas`` explicit constructor + type check
- ``as_zone`` for IANA conversions
- Operator dispatch with non-TimePoint operands (NotImplemented path)
"""

from __future__ import annotations

import warnings
from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from mostlyright.core.temporal.timepoint import TimePoint

# ---------------------------------------------------------------------------
# Property tests (Hypothesis)
# ---------------------------------------------------------------------------


# Bound the strategy to a reasonable range so we exercise the same arithmetic
# as production data (1970-2100) without spending time on edge-of-epoch cases
# that exercise the same code path.
_DT_STRATEGY = st.datetimes(
    min_value=datetime(1970, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(UTC),
)


@given(_DT_STRATEGY)
@settings(max_examples=200)
def test_utc_datetime_round_trips(dt: datetime) -> None:
    """For any UTC-aware datetime, TimePoint(dt).to_utc() == dt."""
    assert TimePoint(dt).to_utc() == dt


@given(_DT_STRATEGY)
@settings(max_examples=200)
def test_iso_round_trip(dt: datetime) -> None:
    """Round-trip through ISO string returns an equal TimePoint."""
    tp = TimePoint(dt)
    assert TimePoint(tp.iso()) == tp


@given(_DT_STRATEGY)
@settings(max_examples=100)
def test_equal_construction_paths_hash_equal(dt: datetime) -> None:
    """Two TimePoints from the same instant via different constructors are
    equal AND have the same hash (so they're usable as dict keys / set
    members interchangeably)."""
    via_datetime = TimePoint(dt)
    via_iso = TimePoint(dt.isoformat())
    via_pandas = TimePoint(pd.Timestamp(dt))

    assert via_datetime == via_iso == via_pandas
    assert hash(via_datetime) == hash(via_iso) == hash(via_pandas)


# ---------------------------------------------------------------------------
# DST boundaries (explicit unit tests for spring-forward + fall-back)
# ---------------------------------------------------------------------------


# 2026 US DST transitions (US-wide):
#   spring-forward: 2026-03-08 at 02:00 local → 03:00 local (skip)
#   fall-back:      2026-11-01 at 02:00 local → 01:00 local (repeat)
#
# America/New_York   UTC-5 EST / UTC-4 EDT
# America/Chicago    UTC-6 CST / UTC-5 CDT
# America/Los_Angeles UTC-8 PST / UTC-7 PDT


@pytest.mark.parametrize(
    "tz_name, before_local, after_local, before_utc_iso, after_utc_iso",
    [
        # Spring-forward: pre-transition (01:30 local EST) and post (03:30 EDT).
        # EST (UTC-5): 01:30 → 06:30 UTC
        # EDT (UTC-4): 03:30 → 07:30 UTC (one wall-clock hour after pre-transition)
        (
            "America/New_York",
            datetime(2026, 3, 8, 1, 30),
            datetime(2026, 3, 8, 3, 30),
            "2026-03-08T06:30:00+00:00",
            "2026-03-08T07:30:00+00:00",
        ),
        # CST (UTC-6): 01:30 → 07:30 UTC
        # CDT (UTC-5): 03:30 → 08:30 UTC
        (
            "America/Chicago",
            datetime(2026, 3, 8, 1, 30),
            datetime(2026, 3, 8, 3, 30),
            "2026-03-08T07:30:00+00:00",
            "2026-03-08T08:30:00+00:00",
        ),
        # PST (UTC-8): 01:30 → 09:30 UTC
        # PDT (UTC-7): 03:30 → 10:30 UTC
        (
            "America/Los_Angeles",
            datetime(2026, 3, 8, 1, 30),
            datetime(2026, 3, 8, 3, 30),
            "2026-03-08T09:30:00+00:00",
            "2026-03-08T10:30:00+00:00",
        ),
    ],
)
def test_dst_spring_forward(
    tz_name: str,
    before_local: datetime,
    after_local: datetime,
    before_utc_iso: str,
    after_utc_iso: str,
) -> None:
    """Spring-forward: TimePoint built from local times either side of the
    skip produces the correct UTC instant, and ``as_zone`` round-trips back
    to the same local clock time."""
    zone = ZoneInfo(tz_name)

    before = TimePoint(before_local.replace(tzinfo=zone))
    after = TimePoint(after_local.replace(tzinfo=zone))

    assert before.iso() == before_utc_iso
    assert after.iso() == after_utc_iso

    # The gap across the transition is exactly one wall-clock hour even
    # though local-clock difference looks like two hours: spring-forward
    # collapses one hour.
    assert (after.to_utc() - before.to_utc()) == timedelta(hours=1)

    # Round-trip back to the source zone returns the same local clock
    # readings.
    assert before.as_zone(tz_name).replace(tzinfo=None) == before_local
    assert after.as_zone(tz_name).replace(tzinfo=None) == after_local


@pytest.mark.parametrize(
    "tz_name, fold_zero_utc_iso, fold_one_utc_iso",
    [
        # Fall-back 2026-11-01 02:00 local: 01:30 local occurs twice.
        # fold=0 → first occurrence (still DST). fold=1 → second (standard).
        # NY EDT→EST: fold=0 01:30 EDT = 05:30 UTC; fold=1 01:30 EST = 06:30 UTC.
        ("America/New_York", "2026-11-01T05:30:00+00:00", "2026-11-01T06:30:00+00:00"),
        # Chicago CDT→CST: fold=0 01:30 CDT = 06:30 UTC; fold=1 01:30 CST = 07:30 UTC.
        ("America/Chicago", "2026-11-01T06:30:00+00:00", "2026-11-01T07:30:00+00:00"),
        # LA PDT→PST: fold=0 01:30 PDT = 08:30 UTC; fold=1 01:30 PST = 09:30 UTC.
        (
            "America/Los_Angeles",
            "2026-11-01T08:30:00+00:00",
            "2026-11-01T09:30:00+00:00",
        ),
    ],
)
def test_dst_fall_back(tz_name: str, fold_zero_utc_iso: str, fold_one_utc_iso: str) -> None:
    """Fall-back: 01:30 local is ambiguous and ``fold`` disambiguates.
    TimePoint must preserve the ``fold`` choice through UTC normalization.
    """
    zone = ZoneInfo(tz_name)
    ambiguous_local = datetime(2026, 11, 1, 1, 30)

    fold_zero = TimePoint(ambiguous_local.replace(tzinfo=zone, fold=0))
    fold_one = TimePoint(ambiguous_local.replace(tzinfo=zone, fold=1))

    assert fold_zero.iso() == fold_zero_utc_iso
    assert fold_one.iso() == fold_one_utc_iso

    # The two folds are exactly one hour apart in UTC even though they
    # represent the same local clock reading.
    assert (fold_one.to_utc() - fold_zero.to_utc()) == timedelta(hours=1)

    # Display round-trip preserves the original local clock value (the
    # fold info may not survive, but the wall-clock string does).
    assert fold_zero.as_zone(tz_name).replace(tzinfo=None) == ambiguous_local
    assert fold_one.as_zone(tz_name).replace(tzinfo=None) == ambiguous_local


def test_chicago_full_dst_round_trip() -> None:
    """Explicit Chicago round-trip across both 2026 transitions, since the
    spec calls out Chicago specifically for the as_zone round-trip check."""
    tz = "America/Chicago"
    zone = ZoneInfo(tz)

    # Spring-forward boundary (01:59 CST is the last second before the skip).
    pre_spring = TimePoint(datetime(2026, 3, 8, 1, 59, tzinfo=zone))
    assert pre_spring.iso() == "2026-03-08T07:59:00+00:00"
    assert pre_spring.as_zone(tz).utcoffset() == timedelta(hours=-6)  # CST

    # Just after spring-forward.
    post_spring = TimePoint(datetime(2026, 3, 8, 3, 0, tzinfo=zone))
    assert post_spring.iso() == "2026-03-08T08:00:00+00:00"
    assert post_spring.as_zone(tz).utcoffset() == timedelta(hours=-5)  # CDT

    # Fall-back boundary.
    pre_fall = TimePoint(datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0))  # CDT
    post_fall = TimePoint(datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1))  # CST
    assert post_fall.to_utc() - pre_fall.to_utc() == timedelta(hours=1)
    assert pre_fall.as_zone(tz).utcoffset() == timedelta(hours=-5)
    assert post_fall.as_zone(tz).utcoffset() == timedelta(hours=-6)


# ---------------------------------------------------------------------------
# Naive rejection (datetime, pd.Timestamp, ISO string)
# ---------------------------------------------------------------------------


def test_naive_datetime_rejected() -> None:
    """A naive datetime (tzinfo=None) is rejected with 'naive' in the message."""
    with pytest.raises(ValueError, match="naive"):
        TimePoint(datetime(2026, 5, 21, 14, 30))


def test_tzinfo_with_null_utcoffset_rejected() -> None:
    """A datetime carrying a tzinfo whose utcoffset() returns None is
    technically tz-aware (tzinfo is not None) but functionally naive --
    astimezone() would silently reinterpret it using the host's local
    timezone, producing environment-dependent UTC values. TimePoint must
    reject this case loudly."""

    class FakeNaiveTz(tzinfo):
        def utcoffset(self, dt):  # type: ignore[override]
            return None

        def dst(self, dt):  # type: ignore[override]
            return None

        def tzname(self, dt):  # type: ignore[override]
            return None

    dt = datetime(2026, 5, 21, 14, tzinfo=FakeNaiveTz())
    with pytest.raises(ValueError, match="utcoffset"):
        TimePoint(dt)


def test_naive_pandas_timestamp_rejected() -> None:
    """A naive pd.Timestamp (tz=None) is rejected with 'naive' in the message."""
    with pytest.raises(ValueError, match="naive"):
        TimePoint(pd.Timestamp("2026-05-21 14:30:00"))


def test_naive_iso_string_rejected() -> None:
    """An ISO string with no timezone offset is rejected with 'naive'."""
    with pytest.raises(ValueError, match="naive"):
        TimePoint("2026-05-21T14:30:00")


def test_from_pandas_naive_rejected() -> None:
    """``TimePoint.from_pandas`` rejects naive Timestamps the same way."""
    with pytest.raises(ValueError, match="naive"):
        TimePoint.from_pandas(pd.Timestamp("2026-05-21 14:30:00"))


def test_from_pandas_non_timestamp_rejected() -> None:
    """``TimePoint.from_pandas`` rejects non-Timestamp inputs with TypeError."""
    with pytest.raises(TypeError, match=r"pd.Timestamp"):
        TimePoint.from_pandas("2026-05-21T14:30:00+00:00")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# NaT / NaN rejection
# ---------------------------------------------------------------------------


def test_nat_rejected_with_helpful_message() -> None:
    """``pd.NaT`` is rejected up front (does NOT misroute through the datetime
    path as a 'naive datetime' error). The message must name NaT."""
    with pytest.raises(ValueError, match="NaT"):
        TimePoint(pd.NaT)


def test_float_nan_rejected_with_helpful_message() -> None:
    """``float('nan')`` is rejected up front. The message must name NaN."""
    with pytest.raises(ValueError, match="NaN"):
        TimePoint(float("nan"))


def test_from_pandas_nat_rejected_with_helpful_message() -> None:
    """``TimePoint.from_pandas(pd.NaT)`` raises ValueError with 'NaT' in the
    message — caught BEFORE the isinstance(pd.Timestamp) check (NaT passes that
    check but is a missing-data sentinel, not a real timestamp)."""
    with pytest.raises(ValueError, match="NaT"):
        TimePoint.from_pandas(pd.NaT)


# ---------------------------------------------------------------------------
# Date-only ISO rejection
# ---------------------------------------------------------------------------


def test_date_only_iso_rejected() -> None:
    """A date-only ISO string is rejected."""
    with pytest.raises(ValueError, match="datetime, not date"):
        TimePoint("2026-05-21")


def test_date_only_iso_with_leading_whitespace_rejected_as_date() -> None:
    """A date-only ISO string with leading whitespace must still hit the
    date-only branch, not the generic fromisoformat-parse-failure branch
    (the leading space would otherwise satisfy the 'T or space' heuristic
    and produce a confusing 'could not parse' error)."""
    with pytest.raises(ValueError, match="date"):
        TimePoint(" 2026-05-21")
    with pytest.raises(ValueError, match="date"):
        TimePoint("2026-05-21 ")
    with pytest.raises(ValueError, match="date"):
        TimePoint("\t2026-05-21\n")


def test_empty_string_rejected() -> None:
    """An empty string is rejected loudly (would otherwise become a less
    helpful fromisoformat error)."""
    with pytest.raises(ValueError, match="non-empty"):
        TimePoint("")


def test_whitespace_only_string_rejected() -> None:
    """A whitespace-only string is rejected — same path as empty."""
    with pytest.raises(ValueError, match="non-empty"):
        TimePoint("   ")


def test_garbage_iso_string_rejected() -> None:
    """A garbage string that's neither date-only nor parseable raises ValueError
    with a message naming the input."""
    with pytest.raises(ValueError, match="parse"):
        TimePoint("not a timestamp T xyz")


# ---------------------------------------------------------------------------
# Microsecond preservation
# ---------------------------------------------------------------------------


def test_microsecond_preservation_through_iso_and_to_utc() -> None:
    """Microseconds survive both ISO serialization and to_utc()."""
    dt = datetime(2026, 5, 21, 14, 30, 0, microsecond=123456, tzinfo=UTC)
    tp = TimePoint(dt)

    assert tp.to_utc() == dt
    assert tp.to_utc().microsecond == 123456
    assert tp.iso() == "2026-05-21T14:30:00.123456+00:00"

    # And round-tripping the ISO string preserves microseconds too.
    assert TimePoint(tp.iso()).to_utc().microsecond == 123456


def test_zero_microseconds_omitted_from_iso() -> None:
    """Per the design ambiguity note, the ISO string omits microseconds when
    they are zero (matches stdlib ``datetime.isoformat()`` default)."""
    dt = datetime(2026, 5, 21, 14, 30, 0, tzinfo=UTC)
    assert TimePoint(dt).iso() == "2026-05-21T14:30:00+00:00"


def test_pandas_nanoseconds_truncated_silently() -> None:
    """Nanosecond precision in a pd.Timestamp is silently truncated to
    microseconds (the limit of stdlib datetime). This is the documented
    design behavior, so:

    - the .123456789 ns input must yield .123456 us in the ISO
    - no UserWarning may be emitted (pandas raises one by default; the
      coercion path passes warn=False)
    """
    ts = pd.Timestamp("2026-05-21 14:30:00.123456789", tz="UTC")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes a test failure
        tp = TimePoint(ts)

    assert tp.iso().endswith(".123456+00:00")
    assert tp.iso() == "2026-05-21T14:30:00.123456+00:00"
    assert tp.to_utc().microsecond == 123456


# ---------------------------------------------------------------------------
# Comparison + hashing + repr
# ---------------------------------------------------------------------------


def test_comparison_lt_le_eq() -> None:
    """Comparison operators behave by UTC value."""
    early = TimePoint("2026-05-21T14:00:00+00:00")
    late = TimePoint("2026-05-21T15:00:00+00:00")
    same_as_early = TimePoint("2026-05-21T14:00:00+00:00")

    assert early < late
    assert early <= late
    assert early <= same_as_early
    assert early == same_as_early
    assert early != late
    assert not (late < early)
    assert not (late <= early)


def test_comparison_across_zones_same_instant() -> None:
    """TimePoints constructed from different zones representing the same UTC
    instant compare equal."""
    east = TimePoint(
        datetime(2026, 5, 21, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    )  # EDT (UTC-4): 14:00 UTC
    west = TimePoint(
        datetime(2026, 5, 21, 7, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    )  # PDT (UTC-7): 14:00 UTC
    utc = TimePoint("2026-05-21T14:00:00+00:00")

    assert east == west == utc


def test_operator_with_non_timepoint_returns_notimplemented() -> None:
    """Operator overloads against unrelated types return ``NotImplemented``
    (which Python turns into ``TypeError`` for ordering, or ``False`` for
    equality)."""
    tp = TimePoint("2026-05-21T14:00:00+00:00")

    # Equality with arbitrary type is False (not an error).
    assert (tp == "not a timepoint") is False
    assert (tp == 42) is False
    assert (tp != "not a timepoint") is True

    # Ordering against arbitrary type raises TypeError.
    with pytest.raises(TypeError):
        _ = tp < "not a timepoint"  # type: ignore[operator]
    with pytest.raises(TypeError):
        _ = tp <= 42  # type: ignore[operator]


def test_hash_collision_for_equal_timepoints() -> None:
    """Equal TimePoints have identical hashes (so they collapse in dict/set)."""
    a = TimePoint("2026-05-21T14:30:00+00:00")
    b = TimePoint(datetime(2026, 5, 21, 14, 30, tzinfo=UTC))

    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_repr_round_trips_through_iso() -> None:
    """``repr`` includes the ISO string so it's reconstructable by eye."""
    tp = TimePoint("2026-05-21T14:30:00+00:00")
    r = repr(tp)
    assert r.startswith("TimePoint(")
    assert "2026-05-21T14:30:00+00:00" in r


# ---------------------------------------------------------------------------
# TimePoint.now()
# ---------------------------------------------------------------------------


def test_now_within_5_seconds_of_datetime_now() -> None:
    """``TimePoint.now()`` returns a TimePoint whose UTC value is within
    5 seconds of ``datetime.now(timezone.utc)``."""
    before = datetime.now(UTC)
    tp = TimePoint.now()
    after = datetime.now(UTC)

    # tp's UTC must lie between two wall-clock samples (modulo clock jitter)
    # and be within 5s of both — comfortably loose for any CI machine.
    assert abs((tp.to_utc() - before).total_seconds()) < 5
    assert abs((tp.to_utc() - after).total_seconds()) < 5


def test_now_returns_tz_aware_utc() -> None:
    """``now()`` is tz-aware and pinned to UTC."""
    tp = TimePoint.now()
    assert tp.to_utc().tzinfo is not None
    assert tp.to_utc().utcoffset() == timedelta(0)


# ---------------------------------------------------------------------------
# Non-UTC tz-aware inputs (covered briefly above; explicit cases per §H)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tz_name, local_time, expected_utc_iso",
    [
        # Tokyo: UTC+9, no DST.
        (
            "Asia/Tokyo",
            datetime(2026, 5, 21, 23, 30),
            "2026-05-21T14:30:00+00:00",
        ),
        # Europe/London: BST in May (UTC+1).
        (
            "Europe/London",
            datetime(2026, 5, 21, 15, 30),
            "2026-05-21T14:30:00+00:00",
        ),
        # Auckland: NZST in May (UTC+12).
        (
            "Pacific/Auckland",
            datetime(2026, 5, 22, 2, 30),
            "2026-05-21T14:30:00+00:00",
        ),
        # India: UTC+5:30 (offset includes minutes — exercises non-hour offset).
        (
            "Asia/Kolkata",
            datetime(2026, 5, 21, 20, 0),
            "2026-05-21T14:30:00+00:00",
        ),
    ],
)
def test_non_utc_zones_normalize_to_utc(
    tz_name: str, local_time: datetime, expected_utc_iso: str
) -> None:
    """Tz-aware inputs in non-UTC zones (including half-hour offsets) are
    correctly normalized to UTC for storage."""
    local = local_time.replace(tzinfo=ZoneInfo(tz_name))
    tp = TimePoint(local)
    assert tp.iso() == expected_utc_iso


# ---------------------------------------------------------------------------
# as_zone() — display conversions
# ---------------------------------------------------------------------------


def test_as_zone_unknown_iana_zone_raises() -> None:
    """``as_zone`` with an invalid IANA zone raises ZoneInfoNotFoundError."""
    tp = TimePoint("2026-05-21T14:00:00+00:00")
    with pytest.raises(ZoneInfoNotFoundError):
        tp.as_zone("Not/A/Zone")


def test_as_zone_returns_tz_aware_datetime_in_requested_zone() -> None:
    """``as_zone`` returns a tz-aware ``datetime`` whose tzinfo matches the
    requested zone."""
    tp = TimePoint("2026-05-21T14:30:00+00:00")
    converted = tp.as_zone("Asia/Tokyo")
    assert converted.tzinfo == ZoneInfo("Asia/Tokyo")
    # 14:30 UTC = 23:30 Tokyo (UTC+9).
    assert converted.replace(tzinfo=None) == datetime(2026, 5, 21, 23, 30)


# ---------------------------------------------------------------------------
# Unsupported input types
# ---------------------------------------------------------------------------


def test_unsupported_input_type_raises_typeerror() -> None:
    """Constructing from an unsupported type (int, list, date, etc.) raises
    TypeError naming the supported set."""
    for bad in (42, 3.14, [2026, 5, 21], date(2026, 5, 21), None):
        with pytest.raises(TypeError, match=r"datetime, pd.Timestamp, or ISO string"):
            TimePoint(bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ISO string with space separator (RFC 3339 alt form) accepted
# ---------------------------------------------------------------------------


def test_iso_string_with_space_separator_accepted() -> None:
    """Python's fromisoformat accepts space as the date/time separator;
    the gate in our parser allows it explicitly."""
    tp = TimePoint("2026-05-21 14:30:00+00:00")
    assert tp.iso() == "2026-05-21T14:30:00+00:00"


# ---------------------------------------------------------------------------
# Slots invariant (catches accidental ``self.foo = ...`` regressions)
# ---------------------------------------------------------------------------


def test_timepoint_uses_slots() -> None:
    """TimePoint is __slots__'d, so adding stray attributes fails. This guards
    against future code accidentally creating per-instance __dict__ that would
    break hash equality."""
    tp = TimePoint("2026-05-21T14:00:00+00:00")
    with pytest.raises(AttributeError):
        tp.foo = "bar"  # type: ignore[attr-defined]
