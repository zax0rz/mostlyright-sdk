"""Phase 17 PLAN-06: HAFS + legacy (NAM/HREF/HiResW) URL builders + retirement guard."""

from __future__ import annotations

import warnings
from datetime import UTC, datetime

import pytest
from mostlyright.core.exceptions import (
    DeprecatedModelWarning,
    NwpModelRetiredError,
)
from mostlyright.weather._fetchers._nwp_archive import (
    SUPPORTED_NWP_MODELS,
    build_fetch_plan,
)
from mostlyright.weather._fetchers._nwp_grids import hafs, hiresw

PRE_RETIRE_CYCLE = datetime(2026, 5, 24, 12, tzinfo=UTC)
POST_RETIRE_CYCLE = datetime(2026, 9, 1, 12, tzinfo=UTC)


# ---------------------------------------------------------------------------
# HAFS URL builder
# ---------------------------------------------------------------------------


def test_hafs_url_contains_storm_and_flavor() -> None:
    plan = build_fetch_plan(
        model="hafs",
        mirror="nomads",
        cycle=datetime(2026, 9, 1, 12, tzinfo=UTC),
        fxx=12,
        storm="09l",
        flavor="a",
        product="storm.atm",
    )
    assert "hafs/prod/hfsa.20260901/12/09l.2026090112.hfsa.storm.atm.f012.grb2" in plan.grib2_url


# ---------------------------------------------------------------------------
# NAM / HREF / HiResW URL builders
# ---------------------------------------------------------------------------


def test_nam_url_pre_retirement() -> None:
    plan = build_fetch_plan(
        model="nam",
        mirror="nomads",
        cycle=PRE_RETIRE_CYCLE,
        fxx=6,
        product="conusnest.hiresf",
    )
    assert "nam.20260524/nam.t12z.conusnest.hiresf06.tm00.grib2" in plan.grib2_url


def test_href_url() -> None:
    plan = build_fetch_plan(
        model="href",
        mirror="nomads",
        cycle=PRE_RETIRE_CYCLE,
        fxx=6,
        domain="conus",
        product="mean",
    )
    assert "href.20260524/ensprod/href.t12z.conus.mean.f06.grib2" in plan.grib2_url


def test_hiresw_url() -> None:
    plan = build_fetch_plan(
        model="hiresw",
        mirror="nomads",
        cycle=PRE_RETIRE_CYCLE,
        fxx=6,
        product="arw_2p5km",
        domain="conus",
        member="",
    )
    assert "hiresw.20260524/hiresw.t12z.arw_2p5km.f06.conus.grib2" in plan.grib2_url


# ---------------------------------------------------------------------------
# Retirement guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["nam", "href", "hiresw"])
def test_legacy_model_post_retirement_raises_nwp_model_retired_error(model: str) -> None:
    with pytest.raises(NwpModelRetiredError) as exc_info:
        build_fetch_plan(
            model=model,
            mirror="nomads",
            cycle=POST_RETIRE_CYCLE,
            fxx=6,
        )
    err = exc_info.value
    assert err.model == model
    assert err.retired_on is not None
    assert err.retired_on.year == 2026
    assert err.retired_on.month == 8
    assert err.retired_on.day == 31
    assert "hrrr" in err.replacement_suggestions


# ---------------------------------------------------------------------------
# Member / product / domain enums
# ---------------------------------------------------------------------------


def test_hafs_flavors() -> None:
    assert frozenset({"a", "b"}) == hafs.HAFS_FLAVORS


def test_hafs_products() -> None:
    assert frozenset({"parent.atm", "storm.atm", "parent.sfc", "storm.sfc"}) == hafs.HAFS_PRODUCTS


def test_hiresw_products() -> None:
    assert frozenset({"arw_2p5km", "fv3_2p5km", "arw_5km", "fv3_5km"}) == hiresw.HIRESW_PRODUCTS


# ---------------------------------------------------------------------------
# Registry membership
# ---------------------------------------------------------------------------


def test_supported_nwp_models_includes_4_final_models() -> None:
    for m in ("hafs", "nam", "href", "hiresw"):
        assert m in SUPPORTED_NWP_MODELS


def test_supported_nwp_models_total_is_24() -> None:
    assert len(SUPPORTED_NWP_MODELS) == 24


# ---------------------------------------------------------------------------
# DeprecatedModelWarning category exists (emission tested in forecast_nwp.py
# under the live-path test set; that path needs the [nwp] extra).
# ---------------------------------------------------------------------------


def test_deprecated_model_warning_is_subclass_of_deprecation_warning() -> None:
    assert issubclass(DeprecatedModelWarning, DeprecationWarning)


def test_deprecated_model_warning_filterable_as_error() -> None:
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=DeprecatedModelWarning)
        with pytest.raises(DeprecatedModelWarning, match="retires"):
            warnings.warn(
                "nam retires 2026-08-31",
                category=DeprecatedModelWarning,
                stacklevel=2,
            )


# ---------------------------------------------------------------------------
# Phase 17 Wave-2 iter-1 review: production emission test for
# DeprecatedModelWarning. The previous filter-promotion test above stays as
# a smoke check of stdlib behavior; this new test actually exercises the
# production code path (``mostlyright.forecasts.forecast_nwp``) so a future
# regression that removes the emission gets caught in CI.
#
# Runs without ``[nwp]`` extras because the warning fires BEFORE the
# _WIRED_NWP_MODELS gate which raises ``NwpModelNotAvailableError`` — no
# network IO, no cfgrib import.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", ["nam", "href", "hiresw"])
def test_forecast_nwp_legacy_emits_deprecated_warning(model: str) -> None:
    """Calling ``forecast_nwp`` with a legacy model MUST emit
    ``DeprecatedModelWarning`` even though the wired-models gate
    immediately raises ``NwpModelNotAvailableError``.

    Uses nested context managers: ``pytest.warns`` outer (records the
    warning) + ``pytest.raises`` inner (catches the not-available error).
    """
    from mostlyright.core.exceptions import NwpModelNotAvailableError
    from mostlyright.forecasts import forecast_nwp

    with (
        pytest.warns(DeprecatedModelWarning, match="retires 2026-08-31"),
        pytest.raises(NwpModelNotAvailableError),
    ):
        forecast_nwp("KNYC", model)
