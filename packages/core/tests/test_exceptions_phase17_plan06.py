"""Phase 17 PLAN-06: StormNotFoundError + NwpModelRetiredError exceptions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mostlyright.core.exceptions import (
    NwpError,
    NwpModelRetiredError,
    StormNotFoundError,
)


def test_storm_not_found_error_is_nwp_error_subclass() -> None:
    exc = StormNotFoundError(
        "storm 'ian' not in active storms",
        query="ian",
        active_storms=["09l", "10l"],
    )
    assert isinstance(exc, NwpError)
    assert exc.query == "ian"
    assert exc.active_storms == ["09l", "10l"]


def test_storm_not_found_error_to_dict_payload() -> None:
    exc = StormNotFoundError(
        "no match",
        query="bogus",
        active_storms=["09l", "10l"],
    )
    d = exc.to_dict()
    assert d["error_code"] == "NWP_STORM_NOT_FOUND"
    assert d["query"] == "bogus"
    assert d["active_storms"] == ["09l", "10l"]
    assert d["source"] == "nwp.hafs"


def test_nwp_model_retired_error_is_nwp_error_subclass() -> None:
    retire = datetime(2026, 8, 31, tzinfo=UTC)
    exc = NwpModelRetiredError(
        "nam retired",
        model="nam",
        retired_on=retire,
        replacement_suggestions=["hrrr", "rap", "rrfs"],
    )
    assert isinstance(exc, NwpError)
    assert exc.model == "nam"
    assert exc.retired_on == retire
    assert exc.replacement_suggestions == ["hrrr", "rap", "rrfs"]


def test_nwp_model_retired_error_to_dict_payload() -> None:
    retire = datetime(2026, 8, 31, tzinfo=UTC)
    exc = NwpModelRetiredError(
        "nam retired",
        model="nam",
        retired_on=retire,
        replacement_suggestions=["hrrr"],
    )
    d = exc.to_dict()
    assert d["error_code"] == "NWP_MODEL_RETIRED"
    assert d["model"] == "nam"
    assert d["retired_on"] == "2026-08-31T00:00:00+00:00"
    assert d["replacement_suggestions"] == ["hrrr"]


def test_nwp_model_retired_error_retired_on_none_handled() -> None:
    exc = NwpModelRetiredError("future", model="future_model")
    d = exc.to_dict()
    assert d["retired_on"] is None
    assert d["replacement_suggestions"] == []


def test_storm_not_found_error_can_be_raised_and_caught() -> None:
    with pytest.raises(StormNotFoundError) as exc_info:
        raise StormNotFoundError("nope", query="x", active_storms=["09l"])
    assert exc_info.value.query == "x"
