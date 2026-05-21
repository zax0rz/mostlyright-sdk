"""Observation model — frozen dataclass matching specs/observation.json.

30 storage fields + 2 computed fields (relative_humidity, feels_like_f)
derived at load time from stored values. SDK backward compatible with
all 29 legacy SDK fields plus 3 new additive fields (temp_c, dewpoint_c, qc_field).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from tradewinds._internal._convert import (
    compute_feels_like,
    compute_relative_humidity,
)
from tradewinds._internal.models._base import DictLikeMixin

_REQUIRED_FIELDS = ("station_code", "observed_at", "observation_type", "source")


@dataclass(frozen=True)
class Observation(DictLikeMixin):
    _COMPUTED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"relative_humidity", "feels_like_f"}
    )

    # === Required identity fields ===
    station_code: str
    observed_at: str
    observation_type: str
    source: str

    # === Temperature (stored) ===
    temp_c: float | None
    dewpoint_c: float | None
    temp_f: float | None
    dewpoint_f: float | None

    # === Wind ===
    wind_dir_degrees: int | None
    wind_speed_kt: int | None
    wind_gust_kt: int | None

    # === Pressure ===
    altimeter_inhg: float | None
    sea_level_pressure_mb: float | None

    # === Sky ===
    sky_cover_1: str | None
    sky_base_1_ft: int | None
    sky_cover_2: str | None
    sky_base_2_ft: int | None
    sky_cover_3: str | None
    sky_base_3_ft: int | None
    sky_cover_4: str | None
    sky_base_4_ft: int | None

    # === Visibility / weather ===
    visibility_miles: float | None
    weather_codes: str | None

    # === Precipitation ===
    precip_1hr_inches: float | None

    # === Peak wind (from METAR remarks) ===
    peak_wind_gust_kt: int | None
    peak_wind_dir: int | None
    peak_wind_time: str | None

    # === Other ===
    snow_depth_inches: float | None
    qc_field: int | None
    raw_metar: str | None

    # === Computed at load time (not stored in parquet) ===
    relative_humidity: float | None = field(init=False, default=None)
    feels_like_f: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        # TODO(post-sprint-0): inherited bug from mostlyright==0.14.1 — after
        # convert_observation() does dataclasses.replace() to swap kt→ms or
        # kt→mph, this __post_init__ reruns and recomputes feels_like_f using
        # the converted wind value as if it were still in knots. The result is
        # wrong on cold/windy observations post-conversion. Byte-faithful lift
        # preserves the bug; fix when refactoring units handling (codex W2-B P2,
        # 2026-05-21).
        rh = compute_relative_humidity(self.temp_c, self.dewpoint_c)
        fl = compute_feels_like(self.temp_f, self.wind_speed_kt, rh)
        # Use object.__setattr__ because frozen=True
        object.__setattr__(self, "relative_humidity", rh)
        object.__setattr__(self, "feels_like_f", fl)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Observation:
        """Create from a dict (e.g. parsed from parquet or API response)."""
        missing = [f for f in _REQUIRED_FIELDS if not d.get(f)]
        if missing:
            raise ValueError(
                f"Observation.from_dict: missing required fields: {missing}"
            )
        return cls(
            station_code=d["station_code"],
            observed_at=d["observed_at"],
            observation_type=d["observation_type"],
            source=d["source"],
            temp_c=d.get("temp_c"),
            dewpoint_c=d.get("dewpoint_c"),
            temp_f=d.get("temp_f"),
            dewpoint_f=d.get("dewpoint_f"),
            wind_dir_degrees=d.get("wind_dir_degrees"),
            wind_speed_kt=d.get("wind_speed_kt"),
            wind_gust_kt=d.get("wind_gust_kt"),
            altimeter_inhg=d.get("altimeter_inhg"),
            sea_level_pressure_mb=d.get("sea_level_pressure_mb"),
            sky_cover_1=d.get("sky_cover_1"),
            sky_base_1_ft=d.get("sky_base_1_ft"),
            sky_cover_2=d.get("sky_cover_2"),
            sky_base_2_ft=d.get("sky_base_2_ft"),
            sky_cover_3=d.get("sky_cover_3"),
            sky_base_3_ft=d.get("sky_base_3_ft"),
            sky_cover_4=d.get("sky_cover_4"),
            sky_base_4_ft=d.get("sky_base_4_ft"),
            visibility_miles=d.get("visibility_miles"),
            weather_codes=d.get("weather_codes"),
            precip_1hr_inches=d.get("precip_1hr_inches"),
            peak_wind_gust_kt=d.get("peak_wind_gust_kt"),
            peak_wind_dir=d.get("peak_wind_dir"),
            peak_wind_time=d.get("peak_wind_time"),
            snow_depth_inches=d.get("snow_depth_inches"),
            qc_field=d.get("qc_field"),
            raw_metar=d.get("raw_metar"),
        )
