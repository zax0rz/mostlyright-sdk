"""GRIB2 ``.idx`` parser — pure Python, no network, no GRIB binary dep.

A GRIB2 file's companion ``.idx`` file is a ~10 KB ASCII index listing the
byte offset of each record. Each line has six colon-delimited fields::

    record_no:byte_offset:reference_date:variable:level:forecast_period

Example HRRR sfcf01 line::

    1:0:d=2026010100:TMP:2 m above ground:1 hour fcst:

By parsing the ``.idx`` we can issue HTTP ``Range: bytes=START-END`` requests
to fetch only the records we need from the (much larger) GRIB2 file --
typically reducing 135 MB to ~13 MB per cycle for the 13 fields mostlyright
extracts.

The last record's ``byte_end`` cannot be derived from the next record
(there is no next record); callers must pass ``content_length`` from a HEAD
request on the GRIB2 file so :func:`compute_byte_end` can fill in
``content_length - 1`` for the final record.

Pattern lifted from mostlyright ``sprint2/2r-impl-bundle`` ingest source
``nwp_idx.py``; kept independent of cfgrib/xarray so it imports cleanly
without the ``[nwp]`` extra installed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

#: Idx-file format dispatch tag (Phase 17 FORECAST-04).
#:
#: - ``"wgrib2"`` — NCEP family ``.idx`` (colon-text). Parsed by
#:   :func:`_parse_idx_wgrib2` and shipped in v0.1.0.
#: - ``"eccodes"`` — ECMWF ``.index`` (JSON-lines). Body lands in
#:   Phase 17 PLAN-04; PLAN-01 ships the dispatch shape only and raises
#:   :class:`NotImplementedError`.
IdxStyle = Literal["wgrib2", "eccodes"]


@dataclass(frozen=True)
class IdxRecord:
    """One record (one GRIB2 message) extracted from an ``.idx`` line.

    Attributes:
        record_no: 1-based record index from the source file.
        byte_offset: Inclusive start byte of this record in the GRIB2 file.
        byte_end: Inclusive end byte of this record. ``None`` until
            :func:`compute_byte_end` runs (filled in once we know the
            next record's start, or ``content_length - 1`` for the
            last record).
        reference_date: Model reference / cycle stamp from the ``.idx``
            file (e.g. ``"d=2026010100"``).
        variable: Variable identifier (e.g. ``"TMP"``, ``"DPT"``).
        level: Vertical level (e.g. ``"2 m above ground"``).
        forecast_period: Forecast horizon string (e.g. ``"1 hour fcst"``).
    """

    record_no: int
    byte_offset: int
    byte_end: int | None
    reference_date: str
    variable: str
    level: str
    forecast_period: str


_VALID_IDX_STYLES: frozenset[str] = frozenset({"wgrib2", "eccodes"})


def parse_idx(text: str, style: IdxStyle = "wgrib2") -> list[IdxRecord]:
    """Parse an ``.idx`` (wgrib2) or ``.index`` (eccodes) file.

    The ``style`` argument selects the parser implementation. ``"wgrib2"``
    is the colon-text NCEP format shipped in v0.1.0; ``"eccodes"`` is the
    ECMWF JSON-lines format whose parser body lands in Phase 17 PLAN-04.

    Args:
        text: Raw ``.idx`` / ``.index`` file content (UTF-8 decoded).
        style: ``"wgrib2"`` (default, backward-compatible) or ``"eccodes"``.

    Returns:
        Records in source order. ``byte_end`` is always ``None`` on
        return for the wgrib2 branch — call :func:`compute_byte_end` to
        resolve it.

    Raises:
        ValueError: ``style`` is not in ``{"wgrib2", "eccodes"}``, OR
            (wgrib2 path) a non-blank line cannot be parsed.
        NotImplementedError: ``style="eccodes"`` — body lands in PLAN-04.
    """
    if style == "wgrib2":
        return _parse_idx_wgrib2(text)
    if style == "eccodes":
        raise NotImplementedError(
            "eccodes .index parser lands in Phase 17 PLAN-04 (ECMWF IFS + AIFS)."
        )
    raise ValueError(f"style must be one of {{'wgrib2', 'eccodes'}}; got {style!r}")


def _parse_idx_wgrib2(text: str) -> list[IdxRecord]:
    """Parse a wgrib2-style colon-text ``.idx`` file into ordered records.

    Args:
        text: Raw ``.idx`` file content (UTF-8 decoded ASCII).

    Returns:
        Records in source order. The first five fields are mandatory;
        the sixth (forecast_period) may be empty for some products.
        ``byte_end`` is always ``None`` on return — call
        :func:`compute_byte_end` to resolve it.

    Raises:
        ValueError: A non-blank line cannot be parsed (fewer than five
            colon-delimited fields, or ``record_no`` / ``byte_offset``
            not parseable as int). Loud-fail per RESEARCH §"Anti-Patterns"
            — silently skipping malformed lines hides upstream format
            changes.
    """
    records: list[IdxRecord] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) < 5:
            raise ValueError(f"Malformed .idx line (need >=5 colon-delimited fields): {raw_line!r}")
        try:
            record_no = int(parts[0])
            byte_offset = int(parts[1])
        except ValueError as exc:
            raise ValueError(
                f"Malformed .idx line (record_no/byte_offset not int): {raw_line!r}"
            ) from exc
        reference_date = parts[2]
        variable = parts[3]
        level = parts[4]
        forecast_period = parts[5] if len(parts) >= 6 else ""
        records.append(
            IdxRecord(
                record_no=record_no,
                byte_offset=byte_offset,
                byte_end=None,
                reference_date=reference_date,
                variable=variable,
                level=level,
                forecast_period=forecast_period,
            )
        )
    return records


def compute_byte_end(
    records: list[IdxRecord],
    *,
    content_length: int | None = None,
) -> list[IdxRecord]:
    """Fill in each record's ``byte_end`` from the next record's offset.

    Non-last records: ``byte_end = next.byte_offset - 1``.

    Last record: ``byte_end = content_length - 1`` if ``content_length``
    was supplied, else ``None``. **Callers MUST pass ``content_length``
    when planning byte-range fetches** — cfgrib will reject a record with
    no concrete end byte (Pitfall 1 in 03.2-RESEARCH.md).

    Returns a new list of records; inputs are not mutated.

    Args:
        records: Ordered ``.idx`` records from :func:`parse_idx`.
        content_length: Total byte length of the GRIB2 file, typically
            obtained from a one-shot HTTP HEAD on the GRIB2 URL.

    Returns:
        New ``IdxRecord`` list with ``byte_end`` populated where possible.
    """
    if not records:
        return []
    out: list[IdxRecord] = []
    n = len(records)
    for i, rec in enumerate(records):
        if i < n - 1:
            end = records[i + 1].byte_offset - 1
        elif content_length is not None:
            end = content_length - 1
        else:
            end = None
        out.append(replace(rec, byte_end=end))
    return out


def filter_records(
    records: list[IdxRecord],
    variable_map: dict[str, tuple[str, str]],
) -> list[IdxRecord]:
    """Keep only records matching a ``(variable, level)`` map.

    Args:
        records: All ``.idx`` records (typically post-``compute_byte_end``).
        variable_map: ``{canonical_name: (variable, level)}`` — e.g.
            ``{"temp_k_2m": ("TMP", "2 m above ground")}``. Only records
            with an exact ``(variable, level)`` match to one of the
            mapped values are kept.

    Returns:
        Filtered records in source order. Records matching multiple map
        entries are kept once (de-duplicated by ``record_no``).
    """
    wanted: set[tuple[str, str]] = set(variable_map.values())
    seen: set[int] = set()
    out: list[IdxRecord] = []
    for rec in records:
        if (rec.variable, rec.level) in wanted and rec.record_no not in seen:
            out.append(rec)
            seen.add(rec.record_no)
    return out


__all__ = [
    "IdxRecord",
    "IdxStyle",
    "compute_byte_end",
    "filter_records",
    "parse_idx",
]
