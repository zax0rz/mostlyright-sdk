"""Phase 3.4 — QC wiring tests.

Validates the opt-in ``qc=True`` kwarg on :func:`tradewinds.research`:
- Mode 1 parity preserved when qc=False (default).
- QC runs against raw observations without mutating row contents.
- Sidecar written to the canonical
  ``$HOME/.tradewinds/cache/v1/observations_qc/{station}/{YYYY}/{MM}.parquet``
  location.
- Failures degrade silently (errors land in df.attrs["qc"]["error"]).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helper: _run_qc_and_write_sidecar directly (no network)
# ---------------------------------------------------------------------------
def _make_info(icao: str = "KNYC") -> Any:
    """Return a real StationInfo for KNYC out of the registry."""
    from tradewinds._internal._stations import STATIONS

    return STATIONS["NYC"]


class TestRunQcDirectly:
    def test_empty_raw_obs_returns_summary_skeleton(self) -> None:
        from tradewinds.research import _run_qc_and_write_sidecar

        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=[],
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        assert summary["rows_total"] == 0
        assert summary["rows_flagged"] == 0
        assert summary["sidecar_paths"] == []

    def test_temp_out_of_range_fires_rule(self, tmp_path: Path, monkeypatch) -> None:
        from tradewinds.research import _run_qc_and_write_sidecar

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        # Construct two rows: one in-range, one with absurd temperature.
        raw = [
            {
                "station": "KNYC",
                "event_time": "2025-01-06T12:00:00+00:00",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 40.0,  # ~ 4.4C
                "dwpf": 30.0,
            },
            {
                "station": "KNYC",
                "event_time": "2025-01-06T13:00:00+00:00",
                "observed_at": "2025-01-06T13:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 500.0,  # ~ 260C — fires temp_out_of_range
                "dwpf": 30.0,
            },
        ]
        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=raw,
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        assert summary["rows_total"] == 2
        assert summary["rows_flagged"] == 1
        assert "temp_c.out_of_range" in summary["rules_fired"]
        assert summary["rules_fired"]["temp_c.out_of_range"] == 1

    def test_dewpoint_gt_temp_fires_rule(self, tmp_path: Path, monkeypatch) -> None:
        from tradewinds.research import _run_qc_and_write_sidecar

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        raw = [
            {
                "station": "KNYC",
                "event_time": "2025-01-06T12:00:00+00:00",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 40.0,
                "dwpf": 60.0,  # dewpoint > temp impossible
            },
        ]
        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=raw,
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        assert summary["rules_fired"].get("dew_point_c.exceeds_temp") == 1

    def test_crosscheck_runs_when_both_sources_present(self, tmp_path: Path, monkeypatch) -> None:
        from tradewinds.research import _run_qc_and_write_sidecar

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        raw = [
            {
                "station": "KNYC",
                "event_time": "2025-01-06T12:00:00+00:00",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 40.0,  # 4.4C
                "dwpf": 30.0,
            },
            {
                "station": "KNYC",
                "event_time": "2025-01-06T12:00:00+00:00",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "ghcnh",
                "tmpf": 60.0,  # 15.5C — 11C off from IEM
                "dwpf": 30.0,
            },
        ]
        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=raw,
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        # IEM (4.4C) vs GHCNh (15.5C) → 11C delta > 2C tol → 1 disagreement.
        assert summary["crosscheck_disagreements"] >= 1

    def test_sidecar_written_to_canonical_path(self, tmp_path: Path, monkeypatch) -> None:
        from tradewinds.research import _run_qc_and_write_sidecar
        from tradewinds.weather.qc_sidecar import qc_sidecar_path

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        raw = [
            {
                "station": "KNYC",
                "event_time": "2025-01-06T12:00:00+00:00",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 500.0,  # fires temp_out_of_range
                "dwpf": 30.0,
            },
        ]
        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=raw,
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        assert len(summary["sidecar_paths"]) == 1
        path = Path(summary["sidecar_paths"][0])
        expected = qc_sidecar_path("KNYC", 2025, 1)
        assert path == expected
        assert path.exists()


class TestProductionShapeIntegration:
    """Architect iter-1 HIGH-2: real adapter rows use station_code + observed_at.

    Production parsers (_iem.py, _ghcnh.py, _awc.py) emit `station_code`
    + `observed_at` (NOT `station` + `event_time`). The QC engine and
    crosscheck both read `station` + `event_time`. _run_qc_and_write_sidecar
    normalizes these so the wiring works for real research(qc=True) calls.
    """

    def test_production_row_shape_fires_temp_rule_and_writes_sidecar(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from tradewinds.research import _run_qc_and_write_sidecar
        from tradewinds.weather.qc_sidecar import qc_sidecar_path

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        raw = [
            {
                "station_code": "KNYC",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 500.0,  # fires temp_c.out_of_range
                "dwpf": 30.0,
            },
        ]
        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=raw,
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        assert summary["rows_total"] == 1
        assert summary["rows_flagged"] == 1
        # Sidecar must actually land on disk — the field-name normalization
        # is what makes this possible (previously the sidecar rows got an
        # empty `observed_at`, which the per-month split dropped silently).
        assert len(summary["sidecar_paths"]) == 1
        path = Path(summary["sidecar_paths"][0])
        assert path == qc_sidecar_path("KNYC", 2025, 1)
        assert path.exists()

    def test_production_dewpoint_kt_mb_columns_normalized(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Codex iter-1 P2: dewpoint_c, wind_speed_kt, wind_dir_degrees,
        sea_level_pressure_mb (the actual parser-emitted names) must
        normalize to the QC engine's expected names so dewpoint, wind,
        and pressure rules fire on real data.
        """
        from tradewinds.research import _run_qc_and_write_sidecar

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        raw = [
            {
                "station_code": "KNYC",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "temp_c": 5.0,
                "dewpoint_c": 10.0,  # dewpoint > temp → fires
                "wind_speed_kt": -1,  # negative → fires
                "wind_dir_degrees": 500,  # out of [0, 360] → fires
                "sea_level_pressure_mb": 700,  # < 870 → fires
            },
        ]
        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=raw,
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        assert summary["rows_total"] == 1
        # All four rules should fire on this synthesized-but-realistic row.
        assert "dew_point_c.exceeds_temp" in summary["rules_fired"]
        assert "wind_speed_ms.negative" in summary["rules_fired"]
        assert "wind_dir_deg.out_of_range" in summary["rules_fired"]
        assert "slp_hpa.out_of_range" in summary["rules_fired"]

    def test_production_row_shape_crosscheck_fires(self, tmp_path: Path, monkeypatch) -> None:
        from tradewinds.research import _run_qc_and_write_sidecar

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        raw = [
            {
                "station_code": "KNYC",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 40.0,  # 4.4 C
                "dwpf": 30.0,
            },
            {
                "station_code": "KNYC",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "ghcnh",
                "tmpf": 60.0,  # 15.5 C
                "dwpf": 30.0,
            },
        ]
        summary = _run_qc_and_write_sidecar(
            info=_make_info(),
            raw_obs=raw,
            from_date="2025-01-06",
            to_date="2025-01-12",
        )
        assert summary.get("crosscheck_error") is None
        assert summary["crosscheck_disagreements"] >= 1


# ---------------------------------------------------------------------------
# Sidecar writer
# ---------------------------------------------------------------------------
class TestQcSidecarWriter:
    def test_empty_rows_no_io(self, tmp_path: Path, monkeypatch) -> None:
        from tradewinds.weather.qc_sidecar import write_qc_sidecar

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        out = write_qc_sidecar([], station="KNYC", year=2025, month=1)
        assert out is None
        # No file written.
        assert not (tmp_path / "v1" / "observations_qc").exists()

    def test_writes_parquet_round_trip(self, tmp_path: Path, monkeypatch) -> None:
        import pyarrow.parquet as pq
        from tradewinds.weather.qc_sidecar import write_qc_sidecar

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        rows = [
            {
                "station_code": "KNYC",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "qc_system": "tradewinds.qc.alpha",
                "qc_version": "v0.1.0a1",
                "rule_id": "temp_c.out_of_range",
                "field": "temp_c",
                "flag": "flagged",
                "detector_metadata": "{}",
            }
        ]
        out = write_qc_sidecar(rows, station="KNYC", year=2025, month=1)
        assert out is not None
        assert out.exists()
        # Round-trip via parquet.
        df = pq.read_table(out).to_pandas()
        assert len(df) == 1
        assert df.iloc[0]["rule_id"] == "temp_c.out_of_range"

    def test_path_invalid_station_rejected(self, tmp_path: Path, monkeypatch) -> None:
        from tradewinds.weather.qc_sidecar import qc_sidecar_path

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        with pytest.raises(ValueError):
            qc_sidecar_path("../escape", 2025, 1)


# ---------------------------------------------------------------------------
# research(qc=True) integration: parity preserved + attrs populated
# ---------------------------------------------------------------------------
class TestResearchQcKwarg:
    def test_research_qc_kwarg_default_false(self) -> None:
        """qc=False is the default — Mode 1 parity preserved."""
        import inspect

        from tradewinds.research import research

        sig = inspect.signature(research)
        param = sig.parameters.get("qc")
        assert param is not None
        assert param.default is False

    def test_research_with_qc_true_runs_engine_against_synthetic_obs(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """When qc=True, _run_qc_and_write_sidecar is invoked.

        Patch the upstream fetchers so the test doesn't hit the network,
        then assert df.attrs["qc"] is populated.
        """
        import importlib

        research_module = importlib.import_module("tradewinds.research")

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))

        # Patch the fetchers to return synthetic data.
        synthetic_obs = [
            {
                "station": "KNYC",
                "event_time": "2025-01-06T12:00:00+00:00",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 500.0,  # fires temp_out_of_range
                "dwpf": 30.0,
            },
        ]
        monkeypatch.setattr(
            research_module,
            "_fetch_observations_range",
            lambda *a, **kw: synthetic_obs,
        )
        monkeypatch.setattr(
            research_module,
            "_fetch_climate_range",
            lambda *a, **kw: [],
        )
        monkeypatch.setattr(
            research_module,
            "_all_caches_warm",
            lambda *a, **kw: True,
        )

        df = research_module.research(
            "KNYC",
            "2025-01-06",
            "2025-01-12",
            qc=True,
        )
        assert "qc" in df.attrs
        qc = df.attrs["qc"]
        assert qc["rows_total"] == 1
        assert qc["rows_flagged"] == 1
        assert "temp_c.out_of_range" in qc["rules_fired"]
        # Sidecar got written.
        assert len(qc["sidecar_paths"]) == 1

    def test_research_with_qc_false_omits_attrs(self, tmp_path: Path, monkeypatch) -> None:
        """qc=False → no df.attrs['qc'] key at all (parity / clean)."""
        import importlib

        research_module = importlib.import_module("tradewinds.research")

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(research_module, "_fetch_observations_range", lambda *a, **kw: [])
        monkeypatch.setattr(research_module, "_fetch_climate_range", lambda *a, **kw: [])
        monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
        df = research_module.research(
            "KNYC",
            "2025-01-06",
            "2025-01-12",
        )
        assert "qc" not in df.attrs

    def test_qc_does_not_mutate_observation_rows(self, tmp_path: Path, monkeypatch) -> None:
        """Parity invariant: even with qc=True, the returned DataFrame's
        observation/pair columns are unchanged from the qc=False call.
        """
        import importlib

        research_module = importlib.import_module("tradewinds.research")

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        synthetic_obs = [
            {
                "station": "KNYC",
                "event_time": "2025-01-06T12:00:00+00:00",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem.archive",
                "tmpf": 40.0,
                "dwpf": 30.0,
                "metar": "KNYC 061200Z 18012KT 10SM CLR 04/M01",
            },
        ]
        monkeypatch.setattr(
            research_module,
            "_fetch_observations_range",
            lambda *a, **kw: list(synthetic_obs),
        )
        monkeypatch.setattr(research_module, "_fetch_climate_range", lambda *a, **kw: [])
        monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)

        df_no_qc = research_module.research("KNYC", "2025-01-06", "2025-01-12")
        df_qc = research_module.research("KNYC", "2025-01-06", "2025-01-12", qc=True)
        # The pairs DataFrame contents must match exactly — qc adds
        # only df.attrs["qc"], never a column or row mutation.
        pd.testing.assert_frame_equal(df_no_qc, df_qc, check_like=False)
