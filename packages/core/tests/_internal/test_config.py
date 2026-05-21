"""Tests for src/tradewinds/_internal/config.py — SDK configuration.

Lifted byte-faithful from monorepo-v0.14.1/tests/test_sdk_config.py with the
single namespace rewrite ``mostlyright.config`` -> ``tradewinds._internal.config``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestBuiltInDefaults:
    """Layer 1: built-in defaults."""

    def test_default_base_url(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert cfg.base_url == "https://api.mostlyright.md"

    def test_default_timeout(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert cfg.timeout == 30.0

    def test_default_live_timeout(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert cfg.live_timeout == 10.0

    def test_default_max_retries(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert cfg.max_retries == 3

    def test_default_units(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert cfg.units == "raw"

    def test_default_tz(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert cfg.tz == "UTC"

    def test_default_station_none(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert cfg.station is None


class TestKwargsOverride:
    """Layer 4: constructor kwargs override everything."""

    def test_base_url_override(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(base_url="http://localhost:8000")
        assert cfg.base_url == "http://localhost:8000"

    def test_timeout_override(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(timeout=5.0)
        assert cfg.timeout == 5.0

    def test_station_override(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(station="ATL")
        assert cfg.station == "ATL"

    def test_units_override(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(units="metric")
        assert cfg.units == "metric"


class TestTomlConfig:
    """Layer 2: TOML file."""

    def test_mostlyright_toml_loaded(self, tmp_path: Path) -> None:
        from tradewinds._internal.config import TherminalConfig

        toml_file = tmp_path / ".mostlyright.toml"
        toml_file.write_text(
            '[defaults]\nstation = "NYC"\n[api]\nbase_url = "http://custom"\n'
        )
        cfg = TherminalConfig(path=toml_file)
        assert cfg.station == "NYC"
        assert cfg.base_url == "http://custom"

    def test_therminal_toml_fallback(self, tmp_path: Path, monkeypatch: object) -> None:
        """Falls back to ~/.therminal.toml when ~/.mostlyright.toml doesn't exist."""
        from tradewinds._internal.config import TherminalConfig

        toml_file = tmp_path / ".therminal.toml"
        toml_file.write_text('[defaults]\nstation = "MDW"\n')
        cfg = TherminalConfig(path=toml_file)
        assert cfg.station == "MDW"

    def test_toml_timeout_as_float(self, tmp_path: Path) -> None:
        from tradewinds._internal.config import TherminalConfig

        toml_file = tmp_path / ".mostlyright.toml"
        toml_file.write_text("[api]\ntimeout = 15\n")
        cfg = TherminalConfig(path=toml_file)
        assert cfg.timeout == 15.0

    def test_toml_live_section(self, tmp_path: Path) -> None:
        from tradewinds._internal.config import TherminalConfig

        toml_file = tmp_path / ".mostlyright.toml"
        toml_file.write_text("[live]\ntimeout = 5\nmax_retries = 5\n")
        cfg = TherminalConfig(path=toml_file)
        assert cfg.live_timeout == 5.0
        assert cfg.max_retries == 5

    def test_invalid_toml_raises(self, tmp_path: Path) -> None:
        import pytest
        from tradewinds._internal.config import TherminalConfig

        bad_file = tmp_path / "bad.toml"
        bad_file.write_text("not valid toml [[[")
        with pytest.raises(ValueError, match="Invalid TOML"):
            TherminalConfig(path=bad_file)


class TestEnvOverride:
    """Layer 3: environment variables."""

    def test_env_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tradewinds._internal.config import TherminalConfig

        monkeypatch.setenv("MOSTLYRIGHT_BASE_URL", "http://env-url")
        cfg = TherminalConfig()
        assert cfg.base_url == "http://env-url"

    def test_env_station(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tradewinds._internal.config import TherminalConfig

        monkeypatch.setenv("MOSTLYRIGHT_STATION", "LAX")
        cfg = TherminalConfig()
        assert cfg.station == "LAX"

    def test_therminal_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """THERMINAL_* env vars still work (backward compat)."""
        from tradewinds._internal.config import TherminalConfig

        monkeypatch.setenv("THERMINAL_STATION", "ORD")
        cfg = TherminalConfig()
        assert cfg.station == "ORD"

    def test_mostlyright_env_beats_therminal_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tradewinds._internal.config import TherminalConfig

        monkeypatch.setenv("MOSTLYRIGHT_STATION", "ATL")
        monkeypatch.setenv("THERMINAL_STATION", "NYC")
        cfg = TherminalConfig()
        assert cfg.station == "ATL"


class TestLayerPrecedence:
    """Verify resolution order: defaults < toml < env < kwargs."""

    def test_kwargs_beat_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tradewinds._internal.config import TherminalConfig

        monkeypatch.setenv("MOSTLYRIGHT_STATION", "ENV")
        cfg = TherminalConfig(station="KWARG")
        assert cfg.station == "KWARG"

    def test_env_beats_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tradewinds._internal.config import TherminalConfig

        toml_file = tmp_path / "cfg.toml"
        toml_file.write_text('[defaults]\nstation = "TOML"\n')
        monkeypatch.setenv("MOSTLYRIGHT_STATION", "ENV")
        cfg = TherminalConfig(path=toml_file)
        assert cfg.station == "ENV"


class TestConfigResolve:
    """Per-call resolution (units, tz, station)."""

    def test_resolve_uses_defaults(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(station="ATL", units="raw")
        resolved = cfg.resolve()
        assert resolved["station"] == "ATL"
        assert resolved["units"] == "raw"

    def test_resolve_overrides(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(station="ATL")
        resolved = cfg.resolve(station="NYC")
        assert resolved["station"] == "NYC"

    def test_resolve_none_falls_back(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig(units="metric")
        resolved = cfg.resolve(units=None)
        assert resolved["units"] == "metric"


class TestConfigRepr:
    def test_repr_contains_base_url(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        cfg = TherminalConfig()
        assert "base_url" in repr(cfg)

    def test_equality(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        a = TherminalConfig(station="ATL")
        b = TherminalConfig(station="ATL")
        assert a == b

    def test_inequality(self) -> None:
        from tradewinds._internal.config import TherminalConfig

        a = TherminalConfig(station="ATL")
        b = TherminalConfig(station="NYC")
        assert a != b


class TestConfigPathResolution:
    """Config file path resolution."""

    def test_explicit_path_wins(self, tmp_path: Path) -> None:
        from tradewinds._internal.config import _resolve_config_path

        p = tmp_path / "my.toml"
        assert _resolve_config_path(p) == p

    def test_env_config_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tradewinds._internal.config import _resolve_config_path

        monkeypatch.setenv("MOSTLYRIGHT_CONFIG", str(tmp_path / "env.toml"))
        result = _resolve_config_path(None)
        assert result == tmp_path / "env.toml"

    def test_therminal_config_env_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tradewinds._internal.config import _resolve_config_path

        monkeypatch.delenv("MOSTLYRIGHT_CONFIG", raising=False)
        monkeypatch.setenv("THERMINAL_CONFIG", str(tmp_path / "old.toml"))
        result = _resolve_config_path(None)
        assert result == tmp_path / "old.toml"

    def test_default_home_mostlyright(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tradewinds._internal.config import _resolve_config_path

        monkeypatch.delenv("MOSTLYRIGHT_CONFIG", raising=False)
        monkeypatch.delenv("THERMINAL_CONFIG", raising=False)
        result = _resolve_config_path(None)
        assert result == Path.home() / ".mostlyright.toml"

    def test_home_fallback_to_therminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ~/.mostlyright.toml doesn't exist, falls back to ~/.therminal.toml."""
        from tradewinds._internal.config import _resolve_config_path

        monkeypatch.delenv("MOSTLYRIGHT_CONFIG", raising=False)
        monkeypatch.delenv("THERMINAL_CONFIG", raising=False)
        primary = _resolve_config_path(None)
        assert primary is not None


class TestConfigAlias:
    """The Config alias points to TherminalConfig (tradewinds-native name)."""

    def test_config_is_therminal_config(self) -> None:
        from tradewinds._internal.config import Config, TherminalConfig

        assert Config is TherminalConfig

    def test_config_alias_instantiable(self) -> None:
        from tradewinds._internal.config import Config

        cfg = Config(station="ATL")
        assert cfg.station == "ATL"
