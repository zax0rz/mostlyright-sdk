"""Shared calendar-year chunkers for IEM fetchers.

Lift target: mostlyright PR #85 commit ``cf9eb85`` (2026-05-12), Pattern 1.

Two helpers, both leap-year-safe (use ``date(year+1, 1, 1)`` to advance, NOT
``timedelta(days=365)`` which silently drops Feb 29 in leap years and walks
off the calendar boundary by one day every year):

- :func:`yearly_chunks_inclusive` — ``[start, end]`` split into per-calendar-year
  inclusive-end chunks. Each chunk's end is ``min(date(year, 12, 31), end)``.
- :func:`yearly_chunks_exclusive_end` — same range split into per-calendar-year
  EXCLUSIVE-end chunks. Each chunk's end is ``date(next_year, 1, 1)``. Used by
  ``iem_asos.download_iem_asos`` (IEM ``asos.py``'s ``day2`` is exclusive — the
  next-year-Jan-1 boundary cleanly conveys "include all of this year").

Both functions return ``[]`` on reversed ranges (``start > end``) — a caller-side
guard preferred over raising because higher layers iterate the list directly.
"""

from __future__ import annotations

from datetime import date

__all__ = ["yearly_chunks_exclusive_end", "yearly_chunks_inclusive"]


def yearly_chunks_inclusive(start: date, end: date) -> list[tuple[date, date]]:
    """``[start, end]`` split into per-calendar-year inclusive-end chunks.

    The first chunk's start is ``start`` (caller's actual start, not Jan 1) so
    no over-fetch on the leading edge. The final chunk's end is ``end`` (caller's
    actual end, not Dec 31) so no over-fetch on the trailing edge. Intermediate
    chunks cover full calendar years (Jan 1 — Dec 31).

    Returns ``[]`` when ``start > end``.
    """
    if start > end:
        return []
    chunks: list[tuple[date, date]] = []
    current = start
    while current <= end:
        year_end = date(current.year, 12, 31)
        chunk_end = min(year_end, end)
        chunks.append((current, chunk_end))
        current = date(current.year + 1, 1, 1)  # leap-year safe (NOT timedelta(days=365))
    return chunks


def yearly_chunks_exclusive_end(start: date, end: date) -> list[tuple[date, date]]:
    """Range split into per-calendar-year EXCLUSIVE-end chunks (Jan 1 of next year).

    Differs from :func:`yearly_chunks_inclusive`:

    - The first chunk's start is clamped: ``max(date(start.year, 1, 1), start)``
      so subsequent calls in the same year share a cache key (the ``current =
      date(start.year, 1, 1)`` initialization ensures the loop visits every
      calendar-year boundary).
    - Every chunk's end is ``date(year+1, 1, 1)`` — the IEM ``day2``-exclusive
      convention for "include all of ``year``".

    This is the chunker the IEM ASOS download loop uses; the inclusive-end variant
    is provided for future MOS / climate paths that natively take inclusive bounds.

    Returns ``[]`` when ``start > end``.
    """
    if start > end:
        return []
    chunks: list[tuple[date, date]] = []
    current = date(start.year, 1, 1)
    while current <= end:
        chunk_start = max(current, start)
        next_year_1st = date(current.year + 1, 1, 1)  # leap-year safe
        chunks.append((chunk_start, next_year_1st))
        current = next_year_1st
    return chunks
