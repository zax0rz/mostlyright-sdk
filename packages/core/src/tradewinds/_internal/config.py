"""SDK configuration with layered defaults.

Resolution order (last wins):
1. Built-in defaults
2. TOML file (~/.mostlyright.toml, fallback ~/.therminal.toml)
3. Environment variables (MOSTLYRIGHT_* then THERMINAL_*)
4. Constructor kwargs
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://api.mostlyright.md"
DEFAULT_TIMEOUT = 30.0
DEFAULT_LIVE_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 3

_BUILT_IN_DEFAULTS: dict[str, Any] = {
    "units": "raw",
    "tz": "UTC",
    "station": None,
    "base_url": DEFAULT_BASE_URL,
    "timeout": DEFAULT_TIMEOUT,
    "live_timeout": DEFAULT_LIVE_TIMEOUT,
    "max_retries": DEFAULT_MAX_RETRIES,
}

# MOSTLYRIGHT_* checked first, THERMINAL_* as fallback (backward compat)
_ENV_MAP: list[tuple[str, str]] = [
    ("THERMINAL_UNITS", "units"),
    ("THERMINAL_TZ", "tz"),
    ("THERMINAL_STATION", "station"),
    ("THERMINAL_BASE_URL", "base_url"),
    ("MOSTLYRIGHT_UNITS", "units"),
    ("MOSTLYRIGHT_TZ", "tz"),
    ("MOSTLYRIGHT_STATION", "station"),
    ("MOSTLYRIGHT_BASE_URL", "base_url"),
]


class TherminalConfig:
    """SDK configuration with layered defaults.

    Resolution order (last wins):
    1. Built-in defaults
    2. TOML file (~/.mostlyright.toml or ~/.therminal.toml)
    3. Environment variables (MOSTLYRIGHT_* wins over THERMINAL_*)
    4. Constructor kwargs
    """

    __slots__ = (
        "base_url",
        "live_timeout",
        "max_retries",
        "station",
        "timeout",
        "tz",
        "units",
    )

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        units: str | None = None,
        tz: str | None = None,
        station: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        live_timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        # Layer 1: built-in defaults
        merged = dict(_BUILT_IN_DEFAULTS)

        # Layer 2: TOML file
        toml_path = _resolve_config_path(path)
        if toml_path is not None and toml_path.exists():
            merged = _merge_toml(merged, toml_path)
        elif path is None:
            # Fallback: try ~/.therminal.toml
            fallback = Path.home() / ".therminal.toml"
            if fallback.exists():
                merged = _merge_toml(merged, fallback)

        # Layer 3: environment variables (THERMINAL_ first, then MOSTLYRIGHT_ overrides)
        merged = _merge_env(merged)

        # Layer 4: constructor kwargs (only non-None values override)
        kwargs: dict[str, Any] = {
            "units": units,
            "tz": tz,
            "station": station,
            "base_url": base_url,
            "timeout": timeout,
            "live_timeout": live_timeout,
            "max_retries": max_retries,
        }
        for key, val in kwargs.items():
            if val is not None:
                merged[key] = val

        for key, val in merged.items():
            object.__setattr__(self, key, val)

    def resolve(
        self,
        *,
        units: str | None = None,
        tz: str | None = None,
        station: str | None = None,
    ) -> dict[str, str | None]:
        """Resolve per-call kwargs against config defaults."""
        return {
            "units": units if units is not None else self.units,
            "tz": tz if tz is not None else self.tz,
            "station": station if station is not None else self.station,
        }

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k}={getattr(self, k)!r}" for k in self.__slots__)
        return f"TherminalConfig({attrs})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TherminalConfig):
            return NotImplemented
        return all(getattr(self, k) == getattr(other, k) for k in self.__slots__)


def _resolve_config_path(path: str | Path | None) -> Path | None:
    """Determine the TOML config file path.

    Priority: explicit path > $MOSTLYRIGHT_CONFIG > $THERMINAL_CONFIG > ~/.mostlyright.toml
    """
    if path is not None:
        return Path(path)

    env_path = os.environ.get("MOSTLYRIGHT_CONFIG")
    if env_path:
        return Path(env_path)

    env_path = os.environ.get("THERMINAL_CONFIG")
    if env_path:
        return Path(env_path)

    return Path.home() / ".mostlyright.toml"


def _merge_toml(merged: dict[str, Any], path: Path) -> dict[str, Any]:
    """Read a TOML config file and merge into merged."""
    result = dict(merged)

    try:
        raw = path.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML config at {path}: {exc}") from exc

    defaults = data.get("defaults", {})
    for key in ("units", "tz", "station"):
        if key in defaults:
            result[key] = defaults[key]

    api = data.get("api", {})
    if "base_url" in api:
        result["base_url"] = api["base_url"]
    if "timeout" in api:
        result["timeout"] = float(api["timeout"])

    live = data.get("live", {})
    if "timeout" in live:
        result["live_timeout"] = float(live["timeout"])
    if "max_retries" in live:
        result["max_retries"] = int(live["max_retries"])

    return result


def _merge_env(merged: dict[str, Any]) -> dict[str, Any]:
    """Apply environment-variable overrides.

    THERMINAL_* applied first, MOSTLYRIGHT_* applied second (wins).
    """
    result = dict(merged)

    for env_var, config_key in _ENV_MAP:
        val = os.environ.get(env_var)
        if val is not None:
            result[config_key] = val

    return result


Config = TherminalConfig  # tradewinds-native name; TherminalConfig retained for byte-faithful lift
