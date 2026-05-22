"""IEM CLI daily climate report parser.

Parses IEM's cli.py JSON endpoint into climate records matching
specs/climate.json. THE Kalshi settlement source.

Report type priority determines dedup: final (3.0) overwrites
preliminary (1.0), but a second final never overwrites the first
(strict >, first-seen wins at equal priority). The overnight final
IS the Kalshi settlement value.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

REPORT_TYPE_PRIORITY: dict[str, float] = {
    "final": 3.0,
    "ncei_final": 2.5,
    "correction": 2.0,
    "preliminary": 1.0,
    "estimated": 0.0,
}

# Climate temp bounds from specs/climate.json
HIGH_TEMP_MIN_F = -60
HIGH_TEMP_MAX_F = 150
LOW_TEMP_MIN_F = -80
LOW_TEMP_MAX_F = 130

_PRODUCT_TS_RE = re.compile(r"^(\d{12})")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_product_timestamp(product: str) -> datetime | None:
    """Extract issued timestamp from product field.

    Format: "202501160620-KFFC-CDUS42-CLIATL" -> first 12 chars = YYYYMMDDHHmm.
    """
    if not product:
        return None
    m = _PRODUCT_TS_RE.match(product)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)  # noqa: UP017
    except ValueError:
        return None


def infer_report_type(product: str | None, observation_date: str) -> str:
    """Infer report type from product timestamp vs observation date.

    - Same day as observation -> preliminary
    - Next day, 04:00-10:00 UTC -> final (overnight report)
    - Next day, outside window -> correction
    - >1 day later -> correction
    - Unparseable -> preliminary (safe default)
    """
    if not product:
        return "preliminary"

    issued = _parse_product_timestamp(product)
    if issued is None:
        return "preliminary"

    try:
        obs_date = date.fromisoformat(observation_date)
    except (ValueError, TypeError):
        return "preliminary"

    issued_date = issued.date()
    delta_days = (issued_date - obs_date).days

    if delta_days <= 0:
        return "preliminary"
    if delta_days == 1:
        # 04:00-10:00 UTC window: empirically derived for CONUS ASOS stations.
        # Eastern WFOs issue overnight CLI ~midnight local (04-05 UTC).
        # Western WFOs (PHX UTC-7) issue ~midnight local (07 UTC).
        # The window covers all CONUS timezones.
        if 4 <= issued.hour <= 10:
            return "final"
        return "correction"
    # >1 day later
    return "correction"


def _parse_temp(val: Any) -> int | None:
    """Parse temperature value. 'M', null, empty -> None. Otherwise int."""
    if val is None or val == "M" or val == "":
        return None
    try:
        return round(float(val))
    except (ValueError, TypeError):
        return None


def parse_cli_record(
    record: dict[str, Any], station_code: str
) -> dict[str, Any] | None:
    """Parse a single IEM CLI record into a climate schema dict.

    Returns dict with 9 fields (8 schema + report_type_priority), or None
    if both high and low are missing or observation_date is invalid.

    observation_date: Uses IEM's `valid` field directly. IEM CLI data
    reports by local calendar day (NWS convention). This is THE correct
    behavior: "March 31 high" means the station's local March 31.
    """
    observation_date = record.get("valid")
    if not observation_date or not isinstance(observation_date, str):
        return None
    if not _DATE_RE.match(observation_date):
        return None
    # Codex W3A P2: regex matches "2025-02-31" but it's not a real date.
    # Validate via date.fromisoformat() so invalid dates drop here (the
    # alternative is infer_report_type() catching the ValueError later and
    # silently classifying as "preliminary" — would corrupt settlement data).
    try:
        date.fromisoformat(observation_date)
    except ValueError:
        return None

    high = _parse_temp(record.get("high"))
    low = _parse_temp(record.get("low"))

    # Bounds check: reject physically impossible settlement values
    if high is not None and not (HIGH_TEMP_MIN_F <= high <= HIGH_TEMP_MAX_F):
        log.warning(
            "%s %s: high_temp_f=%d out of bounds [%d, %d], setting None",
            station_code,
            observation_date,
            high,
            HIGH_TEMP_MIN_F,
            HIGH_TEMP_MAX_F,
        )
        high = None
    if low is not None and not (LOW_TEMP_MIN_F <= low <= LOW_TEMP_MAX_F):
        log.warning(
            "%s %s: low_temp_f=%d out of bounds [%d, %d], setting None",
            station_code,
            observation_date,
            low,
            LOW_TEMP_MIN_F,
            LOW_TEMP_MAX_F,
        )
        low = None

    if high is None and low is None:
        return None

    product = record.get("product") or None
    report_type = infer_report_type(product, observation_date)
    priority = REPORT_TYPE_PRIORITY[report_type]

    # Extract issued_at from product timestamp
    issued_at: str | None = None
    if product:
        issued_dt = _parse_product_timestamp(product)
        if issued_dt:
            issued_at = issued_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "station_code": station_code,
        "observation_date": observation_date,
        "high_temp_f": high,
        "low_temp_f": low,
        "report_type": report_type,
        "report_type_priority": priority,
        "source": "iem",
        "product_id": product if isinstance(product, str) else None,
        "issued_at": issued_at,
    }


def parse_cli_response(
    data: list[dict[str, Any]], station_code: str
) -> list[dict[str, Any]]:
    """Parse all CLI records, filter None (both temps missing)."""
    results: list[dict[str, Any]] = []
    for record in data:
        parsed = parse_cli_record(record, station_code)
        if parsed is not None:
            results.append(parsed)
    return results
