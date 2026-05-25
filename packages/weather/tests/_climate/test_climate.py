"""Tests for IEM CLI climate parser.

Lifted from monorepo-v0.14.1/tests/test_climate.py — parser-level only.
Storage, sync, and CLI tests are intentionally NOT lifted: they belong with
the ingest/storage layer that has not been ported to mostlyright yet.

Namespace rewrites:
- ``from mostlyright.weather._climate`` -> ``from mostlyright.weather._climate``
- ``from mostlyright._capabilities import SPECS_DIR`` ->
  ``from mostlyright._internal._capabilities import SPECS_DIR``
- Fixture path: ``validation/fixtures/`` -> ``tests/_climate/fixtures/``

This parser is settlement-grade: Kalshi NHIGH/NLOW contracts settle on the
``high`` / ``low`` fields. Logic is byte-faithful to mostlyright==0.14.1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mostlyright._internal._capabilities import SPECS_DIR as _SPECS_DIR

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCHEMA_PATH = _SPECS_DIR / "climate.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def _load_cli_fixture() -> list[dict]:
    return json.loads((FIXTURES / "iem_cli_atl_sample.json").read_text())


CLI_FIXTURE = _load_cli_fixture()


# ---------------------------------------------------------------------------
# Report type priority constants
# ---------------------------------------------------------------------------


class TestReportTypePriority:
    def test_priority_values(self):
        from mostlyright.weather._climate import REPORT_TYPE_PRIORITY

        assert REPORT_TYPE_PRIORITY["final"] == 3.0
        assert REPORT_TYPE_PRIORITY["ncei_final"] == 2.5
        assert REPORT_TYPE_PRIORITY["correction"] == 2.0
        assert REPORT_TYPE_PRIORITY["preliminary"] == 1.0
        assert REPORT_TYPE_PRIORITY["estimated"] == 0.0

    def test_final_is_highest(self):
        from mostlyright.weather._climate import REPORT_TYPE_PRIORITY

        assert REPORT_TYPE_PRIORITY["final"] == max(REPORT_TYPE_PRIORITY.values())

    def test_all_report_types_in_schema(self):
        from mostlyright.weather._climate import REPORT_TYPE_PRIORITY

        schema = _load_schema()
        allowed = schema["properties"]["report_type"]["enum"]
        assert set(REPORT_TYPE_PRIORITY.keys()) == set(allowed)


# ---------------------------------------------------------------------------
# infer_report_type
# ---------------------------------------------------------------------------


class TestInferReportType:
    """Product format: YYYYMMDDHHmm-STATION-PRODUCT-TYPE."""

    def test_final_next_day_0620_utc(self):
        """Next day, 06:20 UTC is within 04:00-10:00 window -> final."""
        from mostlyright.weather._climate import infer_report_type

        result = infer_report_type("202501160620-KFFC-CDUS42-CLIATL", "2025-01-15")
        assert result == "final"

    def test_final_next_day_0400_utc(self):
        """Exactly 04:00 UTC is within the window -> final."""
        from mostlyright.weather._climate import infer_report_type

        result = infer_report_type("202501160400-KFFC-CDUS42-CLIATL", "2025-01-15")
        assert result == "final"

    def test_final_next_day_1000_utc(self):
        """Exactly 10:00 UTC is within the window -> final."""
        from mostlyright.weather._climate import infer_report_type

        result = infer_report_type("202501161000-KFFC-CDUS42-CLIATL", "2025-01-15")
        assert result == "final"

    def test_correction_next_day_0200_utc(self):
        """Next day, 02:00 UTC is BEFORE 04:00 window -> correction."""
        from mostlyright.weather._climate import infer_report_type

        result = infer_report_type("202501200200-KFFC-CDUS42-CLIATL", "2025-01-19")
        assert result == "correction"

    def test_correction_next_day_1100_utc(self):
        """Next day, 11:00 UTC is AFTER 10:00 window -> correction."""
        from mostlyright.weather._climate import infer_report_type

        result = infer_report_type("202501161100-KFFC-CDUS42-CLIATL", "2025-01-15")
        assert result == "correction"

    def test_preliminary_same_day(self):
        """Product issued same day as observation -> preliminary."""
        from mostlyright.weather._climate import infer_report_type

        result = infer_report_type("202501181430-KFFC-CDUS42-CLIATL", "2025-01-18")
        assert result == "preliminary"

    def test_correction_two_days_later(self):
        """>1 day later -> correction."""
        from mostlyright.weather._climate import infer_report_type

        result = infer_report_type("202501200620-KFFC-CDUS42-CLIATL", "2025-01-18")
        assert result == "correction"

    def test_unparseable_product_defaults_preliminary(self):
        """Garbled product string -> preliminary (safe default)."""
        from mostlyright.weather._climate import infer_report_type

        assert infer_report_type("GARBAGE", "2025-01-15") == "preliminary"

    def test_empty_product_defaults_preliminary(self):
        from mostlyright.weather._climate import infer_report_type

        assert infer_report_type("", "2025-01-15") == "preliminary"

    def test_none_product_defaults_preliminary(self):
        from mostlyright.weather._climate import infer_report_type

        assert infer_report_type(None, "2025-01-15") == "preliminary"

    def test_never_returns_ncei_final(self):
        """infer_report_type can only return final/correction/preliminary.

        ncei_final and estimated are only set by external code paths (NCEI/ACIS).
        """
        from mostlyright.weather._climate import infer_report_type

        # All possible product/date combos only yield these 3
        for product, obs_date, expected in [
            ("202501160620-KFFC-CDUS42-CLIATL", "2025-01-15", "final"),
            ("202501160200-KFFC-CDUS42-CLIATL", "2025-01-15", "correction"),
            ("202501151430-KFFC-CDUS42-CLIATL", "2025-01-15", "preliminary"),
            (None, "2025-01-15", "preliminary"),
        ]:
            result = infer_report_type(product, obs_date)
            assert result in ("final", "correction", "preliminary")
            assert result == expected


# ---------------------------------------------------------------------------
# parse_cli_record
# ---------------------------------------------------------------------------


class TestParseCliRecord:
    def test_valid_record(self):
        """Normal record with high, low, final report type."""
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[0]  # high=52, low=34, next-day 06:20 UTC
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["station_code"] == "ATL"
        assert result["observation_date"] == "2025-01-15"
        assert result["high_temp_f"] == 52
        assert result["low_temp_f"] == 34
        assert result["report_type"] == "final"
        assert result["report_type_priority"] == 3.0
        assert result["source"] == "iem"

    def test_missing_high_m(self):
        """high='M' -> None, record still valid if low exists."""
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[1]  # high='M', low=28
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["high_temp_f"] is None
        assert result["low_temp_f"] == 28

    def test_missing_low_null(self):
        """low=null -> None, record still valid if high exists."""
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[2]  # high=48, low=null
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["high_temp_f"] == 48
        assert result["low_temp_f"] is None

    def test_both_missing_returns_none(self):
        """If both high and low are missing, record is useless -> None."""
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[5]  # high='M', low=null
        result = parse_cli_record(rec, "ATL")
        assert result is None

    def test_preliminary_same_day(self):
        """Same-day product -> preliminary report type."""
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[3]  # product timestamp same day
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["report_type"] == "preliminary"
        assert result["report_type_priority"] == 1.0

    def test_correction_report_type(self):
        """Next day outside window -> correction."""
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[4]  # product 02:00 UTC next day
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["report_type"] == "correction"
        assert result["report_type_priority"] == 2.0

    def test_product_id_preserved(self):
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[0]
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["product_id"] == "202501160620-KFFC-CDUS42-CLIATL"

    def test_issued_at_extracted(self):
        """issued_at derived from product timestamp -> RFC3339."""
        from mostlyright.weather._climate import parse_cli_record

        rec = CLI_FIXTURE[0]  # product "202501160620-..."
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["issued_at"] == "2025-01-16T06:20:00Z"

    def test_missing_product_has_null_issued_at(self):
        from mostlyright.weather._climate import parse_cli_record

        rec = {**CLI_FIXTURE[0], "product": None}
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["issued_at"] is None
        assert result["product_id"] is None
        assert result["report_type"] == "preliminary"

    def test_missing_valid_returns_none(self):
        from mostlyright.weather._climate import parse_cli_record

        rec = {**CLI_FIXTURE[0], "valid": None}
        result = parse_cli_record(rec, "ATL")
        assert result is None

    def test_high_low_are_integers(self):
        """High/low must be int, not float."""
        from mostlyright.weather._climate import parse_cli_record

        result = parse_cli_record(CLI_FIXTURE[0], "ATL")
        assert result is not None
        assert isinstance(result["high_temp_f"], int)
        assert isinstance(result["low_temp_f"], int)

    def test_float_high_rounded_to_int(self):
        """IEM might return float 52.0 -> should become int 52."""
        from mostlyright.weather._climate import parse_cli_record

        rec = {**CLI_FIXTURE[0], "high": 52.0, "low": 34.0}
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["high_temp_f"] == 52
        assert isinstance(result["high_temp_f"], int)

    def test_output_has_exactly_9_fields(self):
        """Climate record: 8 schema fields + report_type_priority."""
        from mostlyright.weather._climate import parse_cli_record

        result = parse_cli_record(CLI_FIXTURE[0], "ATL")
        assert result is not None
        assert len(result) == 9

    def test_validates_against_schema(self):
        """Output (minus report_type_priority) validates against climate.json."""
        from jsonschema import validate
        from mostlyright.weather._climate import parse_cli_record

        schema = _load_schema()
        result = parse_cli_record(CLI_FIXTURE[0], "ATL")
        assert result is not None
        # Remove parquet-only field before schema validation
        to_validate = {k: v for k, v in result.items() if k != "report_type_priority"}
        validate(instance=to_validate, schema=schema)

    def test_extreme_high_temp_bounded(self):
        """High temp 180°F exceeds schema max 150 -> None."""
        from mostlyright.weather._climate import parse_cli_record

        rec = {**CLI_FIXTURE[0], "high": 180, "low": 34}
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["high_temp_f"] is None
        assert result["low_temp_f"] == 34

    def test_extreme_low_temp_bounded(self):
        """Low temp -100°F exceeds schema min -80 -> None."""
        from mostlyright.weather._climate import parse_cli_record

        rec = {**CLI_FIXTURE[0], "high": 52, "low": -100}
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["low_temp_f"] is None
        assert result["high_temp_f"] == 52

    def test_both_temps_out_of_bounds_returns_none(self):
        """Both out of bounds -> both None -> record dropped."""
        from mostlyright.weather._climate import parse_cli_record

        rec = {**CLI_FIXTURE[0], "high": 200, "low": -100}
        result = parse_cli_record(rec, "ATL")
        assert result is None


# ---------------------------------------------------------------------------
# parse_cli_response
# ---------------------------------------------------------------------------


class TestParseCliResponse:
    def test_parses_multiple_records(self):
        from mostlyright.weather._climate import parse_cli_response

        results = parse_cli_response(CLI_FIXTURE, "ATL")
        # 6 records, 1 has both missing -> 5 valid
        assert len(results) == 5

    def test_filters_none_records(self):
        """Records with both high and low missing are filtered out."""
        from mostlyright.weather._climate import parse_cli_response

        both_missing = [CLI_FIXTURE[5]]  # high='M', low=null
        results = parse_cli_response(both_missing, "ATL")
        assert results == []

    def test_empty_input(self):
        from mostlyright.weather._climate import parse_cli_response

        assert parse_cli_response([], "ATL") == []


# ---------------------------------------------------------------------------
# observation_date timezone verification
# ---------------------------------------------------------------------------


class TestObservationDateTimezone:
    """Verify observation_date uses station-local calendar day.

    IEM CLI `valid` field already represents the local calendar day.
    The parser passes it through directly. These tests verify that behavior
    and document the timezone contract.
    """

    def test_valid_field_passthrough(self):
        """Parser uses IEM `valid` field directly as observation_date."""
        from mostlyright.weather._climate import parse_cli_record

        rec = {**CLI_FIXTURE[0], "valid": "2025-03-09"}
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["observation_date"] == "2025-03-09"

    def test_phx_no_dst_date_preserved(self):
        """PHX has no DST (always UTC-7). IEM `valid` is local date.

        At 2025-03-10 00:30 UTC = 2025-03-09 17:30 MST.
        The CLI report is for March 9 local. IEM `valid` = "2025-03-09".
        """
        from mostlyright.weather._climate import parse_cli_record

        rec = {
            "station": "KPHX",
            "valid": "2025-03-09",
            "high": 85,
            "low": 60,
            "product": "202503100630-KPSR-CDUS45-CLIPHX",
            "name": "PHOENIX SKY HARBOR INTL ARPT",
        }
        result = parse_cli_record(rec, "PHX")
        assert result is not None
        assert result["observation_date"] == "2025-03-09"

    def test_eastern_dst_transition_date(self):
        """Eastern DST spring-forward: March 9, 2025.

        Before: UTC-5 (EST). After: UTC-4 (EDT).
        CLI report for March 8 (the day before spring-forward).
        IEM `valid` = "2025-03-08" regardless of UTC offset changes.
        """
        from mostlyright.weather._climate import parse_cli_record

        rec = {
            "station": "KATL",
            "valid": "2025-03-08",
            "high": 65,
            "low": 48,
            "product": "202503090620-KFFC-CDUS42-CLIATL",
            "name": "ATLANTA HARTSFIELD JACKSON INTL ARPT",
        }
        result = parse_cli_record(rec, "ATL")
        assert result is not None
        assert result["observation_date"] == "2025-03-08"

    def test_spring_forward_day_itself(self):
        """Spring-forward day: March 9, 2025.

        The CLI for March 9 is issued March 10 (next day) in the normal window.
        """
        from mostlyright.weather._climate import parse_cli_record

        rec = {
            "station": "KNYC",
            "valid": "2025-03-09",
            "high": 50,
            "low": 35,
            "product": "202503100600-KOKX-CDUS41-CLINYC",
            "name": "CENTRAL PARK, NEW YORK",
        }
        result = parse_cli_record(rec, "NYC")
        assert result is not None
        assert result["observation_date"] == "2025-03-09"
        assert result["report_type"] == "final"

    def test_observation_date_format(self):
        """observation_date is YYYY-MM-DD format."""
        import re

        from mostlyright.weather._climate import parse_cli_record

        result = parse_cli_record(CLI_FIXTURE[0], "ATL")
        assert result is not None
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", result["observation_date"])


# ---------------------------------------------------------------------------
# Live test — real IEM CLI endpoint
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestLiveIEMCli:
    """Live IEM CLI smoke tests for the parser.

    The IEM CLI URL is hard-coded here because the fetcher module that
    historically held ``IEM_CLI_BASE_URL`` (``ingest.sources.climate_sync``)
    is out of scope for Wave 3A. When the climate fetcher is lifted, replace
    these literals with the constant from ``mostlyright.weather._fetchers.climate``.
    """

    _IEM_CLI_BASE_URL = "https://mesonet.agron.iastate.edu/json/cli.py"

    def test_fetch_real_cli_data(self):
        """Fetch live CLI data for ATL and verify structure."""
        import httpx

        url = f"{self._IEM_CLI_BASE_URL}?station=KATL&year=2025"
        response = httpx.get(url, timeout=30.0)
        assert response.status_code == 200

        data = response.json()
        # Handle both wrapped and unwrapped formats
        records = data.get("results", data) if isinstance(data, dict) else data
        assert len(records) >= 1
        for rec in records[:5]:
            assert "station" in rec
            assert "valid" in rec
            assert "high" in rec

    def test_live_climate_validates_schema(self):
        """Live IEM CLI data parses and validates against climate.json."""
        import httpx
        from jsonschema import validate
        from mostlyright.weather._climate import parse_cli_response

        url = f"{self._IEM_CLI_BASE_URL}?station=KATL&year=2025"
        response = httpx.get(url, timeout=30.0)
        data = response.json()
        records = data.get("results", data) if isinstance(data, dict) else data

        parsed = parse_cli_response(records, "ATL")
        assert len(parsed) >= 1

        schema = _load_schema()
        for rec in parsed[:10]:
            to_validate = {k: v for k, v in rec.items() if k != "report_type_priority"}
            validate(instance=to_validate, schema=schema)
