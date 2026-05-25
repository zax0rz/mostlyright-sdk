"""Phase 3.6 — discovery + DataVersion + settlement primitives.

NOTE: This test file intentionally uses the legacy ``TRADEWINDS_CACHE_DIR``
env var (not the canonical ``MOSTLYRIGHT_CACHE_DIR``) to exercise the Phase 12
W4 back-compat shim. The other test files were migrated to the canonical
env var. Scheduled for removal in v0.3 when the deprecation window closes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

# Silence DeprecationWarning for this whole module (legacy env-var usage is
# intentional back-compat coverage; the back-compat shim's 3-test suite at
# packages/core/tests/test_cache_env_back_compat.py is the canonical proof
# the warning fires). Use pytestmark + filterwarnings — module-level
# warnings.filterwarnings() does NOT survive pytest's per-test warning-filter
# reset; pytestmark IS picked up by pytest's collection layer.
pytestmark = pytest.mark.filterwarnings(
    "ignore:TRADEWINDS_CACHE_DIR is deprecated:DeprecationWarning"
)


class TestAvailability:
    def test_no_cache_returns_zero_counts(self, tmp_path: Path, monkeypatch) -> None:
        from mostlyright.discovery import availability

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        out = availability("KNYC")
        assert out["station"] == "KNYC"
        assert out["months_cached"] == 0
        assert out["first_month"] is None
        assert out["last_month"] is None
        assert out["climate_years"] == 0
        assert out["qc_sidecars"] == 0

    def test_counts_obs_climate_qc_files(self, tmp_path: Path, monkeypatch) -> None:
        from mostlyright.discovery import availability

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        # Build a synthetic cache layout.
        obs = tmp_path / "v1" / "observations" / "KNYC" / "2025"
        obs.mkdir(parents=True)
        (obs / "01.parquet").touch()
        (obs / "02.parquet").touch()
        cli = tmp_path / "v1" / "climate" / "KNYC"
        cli.mkdir(parents=True)
        (cli / "2024.parquet").touch()
        (cli / "2025.parquet").touch()
        qc = tmp_path / "v1" / "observations_qc" / "KNYC" / "2025"
        qc.mkdir(parents=True)
        (qc / "01.parquet").touch()

        out = availability("KNYC")
        assert out["months_cached"] == 2
        assert out["first_month"] == "01.parquet"
        assert out["last_month"] == "02.parquet"
        assert out["climate_years"] == 2
        assert out["first_climate_year"] == "2024"
        assert out["last_climate_year"] == "2025"
        assert out["qc_sidecars"] == 1


class TestClimateGaps:
    def test_no_cache_all_days_are_gaps(self, tmp_path: Path, monkeypatch) -> None:
        from mostlyright.discovery import climate_gaps

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        gaps = climate_gaps("KNYC", "2025-01-01", "2025-01-03")
        assert gaps == ["2025-01-01", "2025-01-02", "2025-01-03"]

    def test_year_cached_no_gaps_within_year(self, tmp_path: Path, monkeypatch) -> None:
        from mostlyright.discovery import climate_gaps

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        cli = tmp_path / "v1" / "climate" / "KNYC"
        cli.mkdir(parents=True)
        (cli / "2025.parquet").touch()
        assert climate_gaps("KNYC", "2025-01-01", "2025-01-31") == []

    def test_year_boundary_only_uncached_year_in_gaps(self, tmp_path: Path, monkeypatch) -> None:
        from mostlyright.discovery import climate_gaps

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        cli = tmp_path / "v1" / "climate" / "KNYC"
        cli.mkdir(parents=True)
        (cli / "2025.parquet").touch()
        gaps = climate_gaps("KNYC", "2024-12-30", "2025-01-02")
        assert "2024-12-30" in gaps
        assert "2024-12-31" in gaps
        assert "2025-01-01" not in gaps
        assert "2025-01-02" not in gaps

    def test_reversed_range_returns_empty(self, tmp_path: Path, monkeypatch) -> None:
        from mostlyright.discovery import climate_gaps

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        assert climate_gaps("KNYC", "2025-12-31", "2025-01-01") == []


class TestDescribe:
    def test_known_schema_returns_text(self) -> None:
        from mostlyright.discovery import describe

        text = describe("schema.observation.v1")
        assert "Schema: schema.observation.v1" in text
        assert "Columns:" in text

    def test_unknown_schema_raises(self) -> None:
        from mostlyright.discovery import describe

        with pytest.raises(ValueError, match="Unknown schema_id"):
            describe("schema.bogus.v1")


class TestFeatureCatalog:
    def test_lists_transforms_public_surface(self) -> None:
        from mostlyright.discovery import feature_catalog

        catalog = feature_catalog()
        for name in (
            "lag",
            "diff",
            "rolling",
            "calendar_features",
            "spread",
            "wind_chill",
            "heat_index",
        ):
            assert name in catalog


class TestSettlementWrappers:
    def test_settlement_date_for_returns_iso_date(self) -> None:
        from mostlyright.discovery import settlement_date_for

        ts = datetime(2025, 1, 6, 18, 0, tzinfo=UTC)
        out = settlement_date_for("NYC", ts)
        # NYC LST is UTC-5 → 18:00 UTC == 13:00 LST → same LST date 2025-01-06.
        assert out == "2025-01-06"

    def test_settlement_window_utc_returns_aware_tuple(self) -> None:
        from mostlyright.discovery import settlement_window_utc

        start, end = settlement_window_utc("NYC", "2025-01-06")
        assert start.tzinfo is not None
        assert end.tzinfo is not None
        # End is exactly 24h after start (midnight to midnight LST).
        assert (end - start).total_seconds() == 24 * 3600

    def test_settlement_wrappers_match_snapshot_impl(self) -> None:
        from mostlyright.discovery import settlement_date_for as discovery_sdf
        from mostlyright.discovery import settlement_window_utc as discovery_swu
        from mostlyright.snapshot import settlement_date_for as snapshot_sdf
        from mostlyright.snapshot import settlement_window_utc as snapshot_swu

        ts = datetime(2025, 6, 15, 22, 0, tzinfo=UTC)
        # The discovery wrapper for settlement_date_for accepts datetime;
        # the underlying snapshot impl takes an ISO string.
        assert discovery_sdf("LAX", ts) == snapshot_sdf(ts.isoformat(), "LAX")
        assert discovery_swu("LAX", "2025-06-15") == snapshot_swu("2025-06-15", "LAX")


class TestDataVersion:
    def test_token_is_deterministic_for_same_inputs(self) -> None:
        from mostlyright.discovery import DataVersion

        a = DataVersion.from_components(
            sdk_version="0.1.0",
            schema_ids=("schema.observation.v1",),
            sources=("iem.archive",),
            code_sha="abc",
            data_sha="def",
        )
        b = DataVersion.from_components(
            sdk_version="0.1.0",
            schema_ids=("schema.observation.v1",),
            sources=("iem.archive",),
            code_sha="abc",
            data_sha="def",
        )
        assert a.token == b.token
        assert len(a.token) == 64  # SHA-256 hex

    def test_token_changes_when_any_component_changes(self) -> None:
        from mostlyright.discovery import DataVersion

        base = DataVersion.from_components(
            sdk_version="0.1.0",
            schema_ids=("a",),
            sources=("b",),
            code_sha="c",
            data_sha="d",
        )
        # Mutate each input separately and confirm the token differs.
        for kwarg, new_value in (
            ("sdk_version", "0.2.0"),
            ("schema_ids", ("z",)),
            ("sources", ("z",)),
            ("code_sha", "z"),
            ("data_sha", "z"),
        ):
            kwargs = {
                "sdk_version": "0.1.0",
                "schema_ids": ("a",),
                "sources": ("b",),
                "code_sha": "c",
                "data_sha": "d",
                kwarg: new_value,
            }
            mutated = DataVersion.from_components(**kwargs)
            assert mutated.token != base.token, f"token did not change for {kwarg}"

    def test_token_invariant_under_schema_id_ordering(self) -> None:
        """Reordering schema_ids shouldn't change the token (canonical sort)."""
        from mostlyright.discovery import DataVersion

        a = DataVersion.from_components(
            sdk_version="0.1.0",
            schema_ids=("a", "b"),
            sources=("c",),
            code_sha="d",
            data_sha="e",
        )
        b = DataVersion.from_components(
            sdk_version="0.1.0",
            schema_ids=("b", "a"),
            sources=("c",),
            code_sha="d",
            data_sha="e",
        )
        assert a.token == b.token

    def test_for_research_token_invariant_for_same_cache(self, tmp_path: Path, monkeypatch) -> None:
        from mostlyright.discovery import DataVersion

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        a = DataVersion.for_research(station="KNYC", from_date="2025-01-06", to_date="2025-01-12")
        b = DataVersion.for_research(station="KNYC", from_date="2025-01-06", to_date="2025-01-12")
        assert a.token == b.token

    def test_for_research_token_changes_when_cache_changes(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from mostlyright.discovery import DataVersion

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        before = DataVersion.for_research(
            station="KNYC", from_date="2025-01-06", to_date="2025-01-12"
        )
        # Touch a new cache file → mtime fingerprint changes → token changes.
        obs = tmp_path / "v1" / "observations" / "KNYC" / "2025"
        obs.mkdir(parents=True)
        (obs / "01.parquet").write_bytes(b"x")
        after = DataVersion.for_research(
            station="KNYC", from_date="2025-01-06", to_date="2025-01-12"
        )
        assert before.token != after.token


class TestDataVersionWiredIntoResearch:
    """Ensure DataVersion stamps a research() result when requested."""

    def test_research_can_attach_data_version_via_attrs(self, tmp_path: Path, monkeypatch) -> None:
        """research() doesn't auto-attach DataVersion in v0.1, but the
        token is callable so quants can stamp it manually.
        """
        import importlib

        from mostlyright.discovery import DataVersion

        research_module = importlib.import_module("mostlyright.research")

        monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(research_module, "_fetch_observations_range", lambda *a, **kw: [])
        monkeypatch.setattr(research_module, "_fetch_climate_range", lambda *a, **kw: [])
        monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
        df = importlib.import_module("mostlyright.research").research(
            "KNYC", "2025-01-06", "2025-01-12"
        )
        token = DataVersion.for_research(
            station="KNYC", from_date="2025-01-06", to_date="2025-01-12"
        )
        df.attrs["data_version"] = token.token
        assert df.attrs["data_version"] == token.token
        assert len(token.token) == 64
