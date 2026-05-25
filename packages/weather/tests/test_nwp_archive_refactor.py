"""Phase 17 FORECAST-02/03/04/05/09: ``_nwp_archive`` Herbie-pattern refactor.

Pre/post GFS-v16 path regression tests guard against silent URL drift
during the SOURCES_BY_MODEL dict introduction; the range-not-honored
guard catches mirror misconfigurations that would otherwise download the
full file instead of a byte range.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from mostlyright.weather._fetchers._nwp_archive import (
    IDX_STYLE_BY_MODEL,
    IDX_SUFFIX_BY_MODEL,
    NOMADS_CONCURRENCY_CAP,
    SOURCES_BY_MODEL,
    SUPPORTED_NWP_MIRRORS,
    SUPPORTED_NWP_MODELS,
    assert_range_honored,
    build_fetch_plan,
)

# ---------------------------------------------------------------------------
# Per-model dispatch tables
# ---------------------------------------------------------------------------


def test_sources_by_model_per_model_dict() -> None:
    assert SOURCES_BY_MODEL["hrrr"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["gfs"] == ("aws_bdp", "nomads")
    assert SOURCES_BY_MODEL["nbm"] == ("aws_bdp", "nomads")


def test_sources_by_model_keys_match_supported_models() -> None:
    # Every supported model must have a sources entry; no orphan keys.
    assert set(SOURCES_BY_MODEL.keys()) == set(SUPPORTED_NWP_MODELS)
    for model, mirrors in SOURCES_BY_MODEL.items():
        for mirror in mirrors:
            assert mirror in SUPPORTED_NWP_MIRRORS, (
                f"{model}: mirror {mirror!r} not in SUPPORTED_NWP_MIRRORS"
            )


def test_idx_suffix_by_model_wgrib2() -> None:
    assert IDX_SUFFIX_BY_MODEL["hrrr"] == (".idx",)
    assert IDX_SUFFIX_BY_MODEL["gfs"] == (".idx",)
    assert IDX_SUFFIX_BY_MODEL["nbm"] == (".idx",)


def test_idx_style_by_model_wgrib2_for_ncep() -> None:
    assert IDX_STYLE_BY_MODEL["hrrr"] == "wgrib2"
    assert IDX_STYLE_BY_MODEL["gfs"] == "wgrib2"
    assert IDX_STYLE_BY_MODEL["nbm"] == "wgrib2"


def test_nomads_concurrency_cap_is_four() -> None:
    # Per Herbie issue #371 IP-ban evidence.
    assert NOMADS_CONCURRENCY_CAP == 4


# ---------------------------------------------------------------------------
# Range-not-honored guard
# ---------------------------------------------------------------------------


def test_assert_range_honored_passes_on_206() -> None:
    resp = MagicMock()
    resp.status_code = 206
    resp.url = "https://example.com/file.grib2"
    # Should not raise.
    assert_range_honored(resp, url="https://example.com/file.grib2")


def test_assert_range_honored_raises_on_200() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.url = "https://example.com/file.grib2"
    with pytest.raises(RuntimeError, match="Range request not honored"):
        assert_range_honored(resp, url="https://example.com/file.grib2")


def test_assert_range_honored_raises_on_416() -> None:
    resp = MagicMock()
    resp.status_code = 416
    resp.url = "https://example.com/file.grib2"
    with pytest.raises(RuntimeError, match="Range request not honored"):
        assert_range_honored(resp)


# ---------------------------------------------------------------------------
# fetch_byte_range integration with assert_range_honored (Codex iter-1 HIGH)
# ---------------------------------------------------------------------------


def test_fetch_byte_range_aborts_on_200_full_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mirror that returns 200 OK with the full body MUST raise RuntimeError.

    Phase 17 FORECAST-05 / Herbie ``core.py:1108-1115``. Without this
    guard, a misconfigured mirror could silently return ~135 MB for what
    the caller expected to be a 10 KB byte-range.
    """
    from mostlyright.weather._fetchers import _nwp_archive as nwp_archive

    plan = build_fetch_plan(
        model="hrrr",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=1,
    )

    class _FakeStreamCtx:
        def __init__(self) -> None:
            self.status_code = 200  # the failure mode we guard against
            self.url = plan.grib2_url

        def __enter__(self) -> _FakeStreamCtx:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None  # 200 doesn't raise

        def read(self) -> bytes:  # pragma: no cover — must NOT be called
            raise AssertionError("read() must not be called after 200 OK guard")

    class _FakeClient:
        def __init__(self, *_a: object, **_kw: object) -> None: ...

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def stream(self, *_a: object, **_kw: object) -> _FakeStreamCtx:
            return _FakeStreamCtx()

    monkeypatch.setattr(nwp_archive.httpx, "Client", _FakeClient)

    with pytest.raises(RuntimeError, match="Range request not honored"):
        nwp_archive.fetch_byte_range(plan, start=0, end=1023)


# ---------------------------------------------------------------------------
# Per-model dispatch wiring (Codex iter-1 HIGH)
# ---------------------------------------------------------------------------


def test_build_fetch_plan_uses_idx_suffix_by_model() -> None:
    """idx_url suffix comes from IDX_SUFFIX_BY_MODEL, not a hardcoded ``.idx``.

    NCEP family stays ``.idx`` (byte-identical to pre-refactor). Wave 2
    ECMWF entry would set this to ``.index``; the test verifies the
    plumbing is in place.
    """
    plan = build_fetch_plan(
        model="hrrr",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=1,
    )
    assert plan.idx_url == plan.grib2_url + ".idx"
    assert plan.idx_url.endswith(IDX_SUFFIX_BY_MODEL["hrrr"][0])


# ---------------------------------------------------------------------------
# GFS URL regression — pre/post v16 cutover via shared transitions catalog
# ---------------------------------------------------------------------------


def test_build_fetch_plan_gfs_post_v16_path_unchanged() -> None:
    plan = build_fetch_plan(
        model="gfs",
        mirror="aws_bdp",
        cycle=datetime(2026, 5, 24, 12, tzinfo=UTC),
        fxx=6,
    )
    assert plan.grib2_url == (
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20260524/12/atmos/gfs.t12z.pgrb2.0p25.f006"
    )
    assert plan.idx_url == plan.grib2_url + ".idx"


def test_build_fetch_plan_gfs_pre_v16_path_no_atmos() -> None:
    plan = build_fetch_plan(
        model="gfs",
        mirror="aws_bdp",
        cycle=datetime(2020, 1, 1, 12, tzinfo=UTC),
        fxx=6,
    )
    assert plan.grib2_url == (
        "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20200101/12/gfs.t12z.pgrb2.0p25.f006"
    )
