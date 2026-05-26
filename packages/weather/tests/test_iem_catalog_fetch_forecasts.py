"""Phase 17 PLAN-08: IEMAdapter.fetch_forecasts wires fetch_iem_mos."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from mostlyright.weather.catalog.iem import IEMAdapter


def test_iem_archive_source_no_longer_raises_not_implemented() -> None:
    """The Phase-2 NotImplementedError stub is gone; iem.archive returns
    a DataFrame from the underlying fetch_iem_mos call.
    """
    with patch("mostlyright.weather._fetchers._iem_mos.fetch_iem_mos") as mock_fetch:
        mock_fetch.return_value = pd.DataFrame({"station": ["KNYC"]})
        adapter = IEMAdapter()
        df = adapter.fetch_forecasts("iem.archive", "KNYC", "2026-05-01", "2026-05-07")
        assert isinstance(df, pd.DataFrame)
        # Verify fetch_iem_mos was called with the right args (model="nbe").
        mock_fetch.assert_called_once_with("KNYC", "2026-05-01", "2026-05-07", model="nbe")


def test_iem_live_source_raises_not_implemented_with_v02_hint() -> None:
    """iem.live MOS is deferred to v0.2 — error message points callers
    at iem.archive.
    """
    adapter = IEMAdapter()
    with pytest.raises(NotImplementedError, match=r"iem\.live MOS deferred to v0\.2"):
        adapter.fetch_forecasts("iem.live", "KNYC", "2026-05-01", "2026-05-07")


def test_iem_unknown_source_raises_value_error() -> None:
    adapter = IEMAdapter()
    with pytest.raises(ValueError, match="source must be one of"):
        adapter.fetch_forecasts("ghcnh.archive", "KNYC", "2026-05-01", "2026-05-07")
