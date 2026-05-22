"""Tests for tradewinds.weather._fetchers._iem_chunks (Phase 1.5 PERF-01).

Lifted from mostlyright PR #85 (commit ``cf9eb85``). The critical leap-year
test (:meth:`TestYearlyChunksExclusiveEnd.test_leap_year_2024_boundary`) is
specifically designed to fail any naive ``timedelta(days=365)`` implementation —
walking 365 days from Jan 1 2024 lands on Dec 31 2024 (not Jan 1 2025) because
2024 has 366 days, so the boundary check drifts year-over-year.
"""

from __future__ import annotations

from datetime import date

from tradewinds.weather._fetchers._iem_chunks import (
    yearly_chunks_exclusive_end,
    yearly_chunks_inclusive,
)


class TestYearlyChunksExclusiveEnd:
    def test_reversed_range_returns_empty(self) -> None:
        assert yearly_chunks_exclusive_end(date(2025, 12, 31), date(2025, 1, 1)) == []

    def test_single_chunk_within_one_year(self) -> None:
        # mid-year start → first-and-only chunk starts at the caller's actual start
        # and ends at the next Jan 1 (exclusive).
        assert yearly_chunks_exclusive_end(date(2025, 3, 1), date(2025, 9, 30)) == [
            (date(2025, 3, 1), date(2026, 1, 1)),
        ]

    def test_two_year_range_produces_two_chunks(self) -> None:
        assert yearly_chunks_exclusive_end(date(2024, 6, 1), date(2025, 6, 1)) == [
            (date(2024, 6, 1), date(2025, 1, 1)),
            (date(2025, 1, 1), date(2026, 1, 1)),
        ]

    def test_leap_year_2024_boundary(self) -> None:
        """CRITICAL — Pitfall 1. Verifies leap-year safety.

        If the impl used ``timedelta(days=365)`` the second chunk's end would be
        ``date(2024, 12, 31)`` (Jan 1 2024 + 365 days = Dec 31 2024 because 2024
        is a leap year). The correct impl yields ``date(2025, 1, 1)`` exactly.
        """
        chunks = yearly_chunks_exclusive_end(date(2023, 1, 1), date(2025, 1, 1))
        # 3 chunks: 2023, 2024, 2025 (the final one because Jan 1 2025 falls
        # within the 2025 iteration).
        assert len(chunks) == 3
        # The SECOND chunk's exclusive end MUST be Jan 1 2025 exactly.
        assert chunks[1] == (date(2024, 1, 1), date(2025, 1, 1))
        # Sanity: the first chunk ends at Jan 1 2024 (next-year boundary of 2023).
        assert chunks[0] == (date(2023, 1, 1), date(2024, 1, 1))

    def test_jan_1_start_boundary(self) -> None:
        """Caller starts exactly on Jan 1; no clamping needed."""
        assert yearly_chunks_exclusive_end(date(2025, 1, 1), date(2025, 1, 1)) == [
            (date(2025, 1, 1), date(2026, 1, 1)),
        ]

    def test_same_start_and_end_midyear(self) -> None:
        """Single-day range still emits one chunk."""
        assert yearly_chunks_exclusive_end(date(2025, 6, 15), date(2025, 6, 15)) == [
            (date(2025, 6, 15), date(2026, 1, 1)),
        ]


class TestYearlyChunksInclusive:
    def test_yearly_chunks_inclusive_basic(self) -> None:
        assert yearly_chunks_inclusive(date(2024, 5, 1), date(2025, 3, 15)) == [
            (date(2024, 5, 1), date(2024, 12, 31)),
            (date(2025, 1, 1), date(2025, 3, 15)),
        ]

    def test_yearly_chunks_inclusive_reversed_returns_empty(self) -> None:
        assert yearly_chunks_inclusive(date(2025, 1, 1), date(2024, 12, 31)) == []

    def test_yearly_chunks_inclusive_single_year_range(self) -> None:
        assert yearly_chunks_inclusive(date(2025, 3, 1), date(2025, 9, 30)) == [
            (date(2025, 3, 1), date(2025, 9, 30)),
        ]

    def test_yearly_chunks_inclusive_leap_year_safe(self) -> None:
        """Mirror of the exclusive-end leap-year test for the inclusive variant."""
        chunks = yearly_chunks_inclusive(date(2023, 6, 1), date(2025, 6, 1))
        assert chunks == [
            (date(2023, 6, 1), date(2023, 12, 31)),
            (date(2024, 1, 1), date(2024, 12, 31)),
            (date(2025, 1, 1), date(2025, 6, 1)),
        ]
