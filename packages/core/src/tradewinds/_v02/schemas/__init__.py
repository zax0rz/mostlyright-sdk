"""Canonical schemas shipped with mostlyright-mcp v0.1.

The three schemas — observation, forecast, settlement — are the shape
contracts every weather-vertical adapter (IEM, AWC, NWS CLI) normalises
to. See ``docs/design.md`` §A, §X, and §BB.3 for the column-by-column
specification.
"""

from .observation import ObservationSchema


__all__ = ["ObservationSchema"]
