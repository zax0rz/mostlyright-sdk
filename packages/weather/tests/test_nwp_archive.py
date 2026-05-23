"""Tests for the NOAA BDP archive URL builder + fetch helpers (Phase 3.2)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from tradewinds.weather._fetchers._nwp_archive import (
    DEFAULT_MIRROR_CHAIN,
    SUPPORTED_NWP_MIRRORS,
    SUPPORTED_NWP_MODELS,
    build_fetch_plan,
    fetch_byte_range,
    fetch_grib2_content_length,
    fetch_idx_text,
)

CYCLE = datetime(2026, 5, 23, 12, tzinfo=UTC)


def test_supported_enums_are_closed_sets() -> None:
    assert frozenset({"hrrr", "gfs", "nbm"}) == SUPPORTED_NWP_MODELS
    assert frozenset({"aws_bdp", "nomads"}) == SUPPORTED_NWP_MIRRORS


def test_default_mirror_chain_aws_first() -> None:
    """AWS is the canonical archive; NOMADS only as fallback."""
    assert DEFAULT_MIRROR_CHAIN[0] == "aws_bdp"
    assert "nomads" in DEFAULT_MIRROR_CHAIN


def test_hrrr_url_layout() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    assert plan.grib2_url == (
        "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.20260523/conus/hrrr.t12z.wrfsfcf01.grib2"
    )
    assert plan.idx_url == plan.grib2_url + ".idx"


def test_gfs_post_v16_includes_atmos_subdir() -> None:
    plan = build_fetch_plan(model="gfs", mirror="aws_bdp", cycle=CYCLE, fxx=12)
    assert "/atmos/" in plan.grib2_url
    assert plan.grib2_url.endswith("gfs.t12z.pgrb2.0p25.f012")


def test_gfs_pre_v16_no_atmos_subdir() -> None:
    """Pitfall 4 — GFS v16.0 cutover (2021-03-23) reorganised paths."""
    cycle = datetime(2020, 1, 1, 12, tzinfo=UTC)
    plan = build_fetch_plan(model="gfs", mirror="aws_bdp", cycle=cycle, fxx=12)
    assert "/atmos/" not in plan.grib2_url


def test_nbm_path_layout() -> None:
    plan = build_fetch_plan(model="nbm", mirror="aws_bdp", cycle=CYCLE, fxx=6)
    assert plan.grib2_url.endswith("blend.t12z.core.f006.co.grib2")


def test_nomads_root_distinct_from_aws() -> None:
    aws = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    nomads = build_fetch_plan(model="hrrr", mirror="nomads", cycle=CYCLE, fxx=1)
    assert aws.grib2_url != nomads.grib2_url
    assert "noaa-hrrr-bdp-pds.s3.amazonaws.com" in aws.grib2_url
    assert "nomads.ncep.noaa.gov" in nomads.grib2_url


def test_unsupported_model_raises_valueerror() -> None:
    with pytest.raises(ValueError, match="model must be one of"):
        build_fetch_plan(model="ecmwf_ifs_hres", mirror="aws_bdp", cycle=CYCLE, fxx=1)


def test_unsupported_mirror_raises_valueerror() -> None:
    with pytest.raises(ValueError, match="mirror must be one of"):
        build_fetch_plan(model="hrrr", mirror="ecmwf_data_portal", cycle=CYCLE, fxx=1)


def test_negative_fxx_rejected() -> None:
    with pytest.raises(ValueError, match="fxx must be non-negative"):
        build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=-1)


def test_naive_cycle_rejected() -> None:
    naive = datetime(2026, 5, 23, 12)
    with pytest.raises(ValueError, match="cycle must be timezone-aware"):
        build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=naive, fxx=1)


# ---------------------------------------------------------------------------
# Fetch helpers (mocked HTTP)
# ---------------------------------------------------------------------------


class _MockResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "",
        content: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=None,
                response=None,  # type: ignore[arg-type]
            )


class _MockClient:
    def __init__(
        self,
        *,
        get_response: _MockResponse | None = None,
        head_response: _MockResponse | None = None,
    ) -> None:
        self._get = get_response
        self._head = head_response
        self.get_calls: list[tuple[str, dict[str, str] | None]] = []
        self.head_calls: list[str] = []

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: float | None = None
    ) -> _MockResponse:
        self.get_calls.append((url, headers))
        return self._get or _MockResponse()

    def head(self, url: str, timeout: float | None = None) -> _MockResponse:
        self.head_calls.append(url)
        return self._head or _MockResponse(headers={"content-length": "0"})


def test_fetch_idx_text_returns_body_and_calls_correct_url() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    client = _MockClient(get_response=_MockResponse(text="1:0:d=:TMP:2 m above ground:"))
    text = fetch_idx_text(plan, client=client)
    assert text.startswith("1:0:")
    assert client.get_calls == [(plan.idx_url, None)]


def test_fetch_idx_text_raises_for_4xx() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    client = _MockClient(get_response=_MockResponse(status_code=404))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_idx_text(plan, client=client)


def test_fetch_grib2_content_length_returns_int() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    client = _MockClient(head_response=_MockResponse(headers={"content-length": "135000000"}))
    assert fetch_grib2_content_length(plan, client=client) == 135_000_000


def test_fetch_grib2_content_length_missing_header_raises() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    client = _MockClient(head_response=_MockResponse(headers={}))
    with pytest.raises(ValueError, match="no Content-Length header"):
        fetch_grib2_content_length(plan, client=client)


def test_fetch_grib2_content_length_non_int_raises() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    client = _MockClient(head_response=_MockResponse(headers={"content-length": "huge"}))
    with pytest.raises(ValueError, match="not integer"):
        fetch_grib2_content_length(plan, client=client)


def test_fetch_byte_range_sends_correct_range_header() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    client = _MockClient(get_response=_MockResponse(content=b"GRIB"))
    data = fetch_byte_range(plan, start=0, end=99, client=client)
    assert data == b"GRIB"
    assert client.get_calls == [(plan.grib2_url, {"Range": "bytes=0-99"})]


def test_fetch_byte_range_rejects_negative_start() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    with pytest.raises(ValueError, match="start must be >= 0"):
        fetch_byte_range(plan, start=-1, end=99)


def test_fetch_byte_range_rejects_end_less_than_start() -> None:
    plan = build_fetch_plan(model="hrrr", mirror="aws_bdp", cycle=CYCLE, fxx=1)
    with pytest.raises(ValueError, match="end must be >= start"):
        fetch_byte_range(plan, start=100, end=50)
