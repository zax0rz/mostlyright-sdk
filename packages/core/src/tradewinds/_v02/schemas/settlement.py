"""NWS CLI settlement schema (``schema.settlement.cli.v1``).

Per ``docs/design.md`` §BB.3 (which supersedes the §A table). CLI
settlement is canonically Fahrenheit — Kalshi contract labels are
Fahrenheit and NWS CLI products report Fahrenheit. The schema has no
metric mode; the values ARE the settlement truth.

Temporal mapping (§U + §BB.3):

- ``observation_date`` is the local climate day per NWS convention
  (no timezone applied to the date itself).
- ``station_tz`` is the IANA timezone for the station
  (``"America/Chicago"`` for KORD), looked up from a static table per
  ICAO code. Required for local-climate-day semantics.
- ``event_time`` is ``00:00 local time on observation_date`` converted to
  UTC. Used for sort / point-in-time joins only; downstream code that
  needs the local date MUST use ``observation_date`` directly.
- ``knowledge_time = product_release_time`` (parsed from the CLI product
  header).
"""

from __future__ import annotations

from ..schema import ColumnSpec, Schema


_REPORT_TYPE_VALUES: tuple[str, ...] = ("preliminary", "final", "correction")


class SettlementSchema(Schema):
    """``schema.settlement.cli.v1`` — NWS CLI daily settlement rows.

    No imperial rename map: CLI settlement IS Fahrenheit, and Fahrenheit
    is the canonical unit for both Kalshi contract labels and the NWS
    CLI product itself. Adapters must NOT convert.
    """

    schema_id = "schema.settlement.cli.v1"

    COLUMNS = [
        ColumnSpec(
            name="station",
            dtype="string",
            units=None,
            nullable=False,
            notes="ICAO/ASOS station ID",
        ),
        ColumnSpec(
            name="station_tz",
            dtype="string",
            units=None,
            nullable=False,
            notes=(
                "IANA timezone for the station (e.g. America/Chicago for "
                "KORD). Required for local-climate-day semantics; see §U."
            ),
        ),
        ColumnSpec(
            name="observation_date",
            dtype="date",
            units=None,
            nullable=False,
            notes=(
                "local climate day per NWS convention (no timezone applied "
                "to the date itself)"
            ),
        ),
        ColumnSpec(
            name="event_time",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes=(
                "00:00 local time on observation_date converted to UTC; "
                "for sort/join only"
            ),
        ),
        ColumnSpec(
            name="product_release_time",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
            notes=(
                "parsed from CLI product header "
                "(_climate.py::_parse_product_timestamp)"
            ),
        ),
        ColumnSpec(
            name="report_type",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=_REPORT_TYPE_VALUES,
            notes=(
                "preliminary | final | correction; dedup priority "
                "preliminary < final < correction"
            ),
        ),
        ColumnSpec(
            name="temp_max_F",
            dtype="float64",
            units="fahrenheit",
            nullable=True,
            notes="daily high (uppercase F for consistency with obs imperial mode)",
        ),
        ColumnSpec(
            name="temp_min_F",
            dtype="float64",
            units="fahrenheit",
            nullable=True,
            notes="daily low",
        ),
        ColumnSpec(
            name="precipitation_in",
            dtype="float64",
            units="inches",
            nullable=True,
        ),
        ColumnSpec(
            name="snowfall_in",
            dtype="float64",
            units="inches",
            nullable=True,
        ),
    ]

    #: Settlement values are already in canonical Fahrenheit / inches; no
    #: imperial-mode rename map applies. ``Schema.column_names("imperial")``
    #: returns the same names as ``column_names("metric")``.
    IMPERIAL_RENAMES: dict[str, str] = {}
