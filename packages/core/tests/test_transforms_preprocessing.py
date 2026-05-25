"""Phase 3.5 — transforms + preprocessing tests."""

from __future__ import annotations

import math

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# calendar_features
# ---------------------------------------------------------------------------
class TestCalendarFeatures:
    def test_emits_all_cyclical_pairs(self) -> None:
        from mostlyright.transforms import calendar_features

        df = pd.DataFrame({"ts": pd.to_datetime(["2025-01-06T12:00:00+00:00"])})
        out = calendar_features(df, "ts")
        for prefix in ("month", "dow", "hour", "day_of_year"):
            assert f"{prefix}_sin" in out.columns
            assert f"{prefix}_cos" in out.columns

    def test_cyclical_invariant_sin2_plus_cos2_equals_one(self) -> None:
        """Phase 3.5 SC-2: sin² + cos² ≈ 1 for every row of every pair."""
        from mostlyright.transforms import calendar_features

        # 12 rows spanning various dates / hours covers most decision
        # paths without needing the full Hypothesis machinery in a
        # network-free smoke test.
        dates = pd.date_range("2024-01-01", periods=12, freq="37h", tz="UTC")
        df = pd.DataFrame({"ts": dates})
        out = calendar_features(df, "ts")
        for prefix in ("month", "dow", "hour", "day_of_year"):
            s = out[f"{prefix}_sin"]
            c = out[f"{prefix}_cos"]
            # Tolerance loose enough for the day_of_year/365 quantization
            # (real year has 365.25 days; we use 365 as the period).
            assert ((s**2 + c**2) - 1.0).abs().max() < 1e-9

    def test_calendar_features_does_not_mutate_input(self) -> None:
        from mostlyright.transforms import calendar_features

        df = pd.DataFrame({"ts": pd.to_datetime(["2025-01-06T12:00:00+00:00"])})
        original_cols = set(df.columns)
        _ = calendar_features(df, "ts")
        assert set(df.columns) == original_cols


# ---------------------------------------------------------------------------
# preprocessing.clip_outliers
# ---------------------------------------------------------------------------
class TestClipOutliers:
    def test_physics_bounds_default_for_temp_c(self) -> None:
        from mostlyright.preprocessing import PHYSICS_BOUNDS, clip_outliers

        df = pd.DataFrame({"temp_c": [-200.0, 0.0, 50.0, 200.0]})
        out = clip_outliers(df, "temp_c")
        # PHYSICS_BOUNDS for temp_c is (-89, 57).
        lo, hi = PHYSICS_BOUNDS["temp_c"]
        assert out.iloc[0] == lo  # -200 → -89
        assert out.iloc[1] == 0.0  # unchanged
        assert out.iloc[2] == 50.0  # unchanged
        assert out.iloc[3] == hi  # 200 → 57

    def test_explicit_bounds_override_physics(self) -> None:
        from mostlyright.preprocessing import clip_outliers

        df = pd.DataFrame({"temp_c": [-5.0, 5.0, 100.0]})
        out = clip_outliers(df, "temp_c", bounds=(0.0, 10.0))
        assert out.tolist() == [0.0, 5.0, 10.0]

    def test_fallback_to_std_when_no_physics_default(self) -> None:
        from mostlyright.preprocessing import clip_outliers

        # column with no PHYSICS_BOUNDS entry → sigma-based fallback.
        df = pd.DataFrame({"custom_col": [1.0, 2.0, 3.0, 4.0, 100.0]})
        out = clip_outliers(df, "custom_col", std=1.0)
        # mean=22, sigma≈43.4; bounds≈[-21.4, 65.4] → all unchanged except 100→65.4
        assert out.iloc[-1] < 100.0

    def test_unknown_column_raises(self) -> None:
        from mostlyright.preprocessing import clip_outliers

        df = pd.DataFrame({"x": [1.0]})
        with pytest.raises(KeyError):
            clip_outliers(df, "no_such_col")

    def test_input_not_mutated(self) -> None:
        from mostlyright.preprocessing import clip_outliers

        df = pd.DataFrame({"temp_c": [-200.0, 200.0]})
        snapshot = df["temp_c"].tolist()
        _ = clip_outliers(df, "temp_c")
        assert df["temp_c"].tolist() == snapshot

    def test_std_zero_or_negative_raises(self) -> None:
        """Architect iter-1 HIGH: std<=0 in sigma fallback would silently
        collapse every row to the mean. Refuse loudly instead.
        """
        from mostlyright.preprocessing import clip_outliers

        df = pd.DataFrame({"custom_col": [1.0, 2.0, 3.0, 4.0, 100.0]})
        with pytest.raises(ValueError, match="std must be > 0"):
            clip_outliers(df, "custom_col", std=0)
        with pytest.raises(ValueError, match="std must be > 0"):
            clip_outliers(df, "custom_col", std=-1.0)


# ---------------------------------------------------------------------------
# preprocessing.iem_crosscheck (standalone)
# ---------------------------------------------------------------------------
class TestIemCrosscheckStandalone:
    def test_returns_disagreement_df(self) -> None:
        from mostlyright.preprocessing import iem_crosscheck

        df = pd.DataFrame(
            {
                "station": ["KNYC", "KNYC"],
                "event_time": [
                    "2025-01-06T12:00:00+00:00",
                    "2025-01-06T12:00:00+00:00",
                ],
                "source": ["iem.archive", "ghcnh"],
                "temp_c": [4.0, 15.0],  # 11 C apart > 2 C default tolerance
            }
        )
        out = iem_crosscheck(df)
        assert len(out) == 1
        assert "delta_c" in out.columns

    def test_no_disagreement_returns_empty(self) -> None:
        from mostlyright.preprocessing import iem_crosscheck

        df = pd.DataFrame(
            {
                "station": ["KNYC", "KNYC"],
                "event_time": [
                    "2025-01-06T12:00:00+00:00",
                    "2025-01-06T12:00:00+00:00",
                ],
                "source": ["iem.archive", "ghcnh"],
                "temp_c": [4.0, 4.5],  # < 2 C
            }
        )
        out = iem_crosscheck(df)
        assert out.empty

    def test_accepts_production_station_code_observed_at(self) -> None:
        """Auto-normalizes station_code → station and observed_at → event_time."""
        from mostlyright.preprocessing import iem_crosscheck

        df = pd.DataFrame(
            {
                "station_code": ["KNYC", "KNYC"],
                "observed_at": [
                    "2025-01-06T12:00:00+00:00",
                    "2025-01-06T12:00:00+00:00",
                ],
                "source": ["iem.archive", "ghcnh"],
                "temp_c": [4.0, 15.0],
            }
        )
        out = iem_crosscheck(df)
        assert len(out) == 1

    def test_missing_source_column_raises(self) -> None:
        from mostlyright.preprocessing import iem_crosscheck

        df = pd.DataFrame({"x": [1, 2]})
        with pytest.raises(ValueError, match="source"):
            iem_crosscheck(df)

    def test_only_one_source_returns_empty(self) -> None:
        from mostlyright.preprocessing import iem_crosscheck

        df = pd.DataFrame(
            {
                "station": ["KNYC"],
                "event_time": ["2025-01-06T12:00:00+00:00"],
                "source": ["iem.archive"],
                "temp_c": [4.0],
            }
        )
        out = iem_crosscheck(df)
        assert out.empty

    def test_custom_tolerance(self) -> None:
        from mostlyright.preprocessing import iem_crosscheck

        df = pd.DataFrame(
            {
                "station": ["KNYC", "KNYC"],
                "event_time": ["2025-01-06T12:00:00+00:00", "2025-01-06T12:00:00+00:00"],
                "source": ["iem.archive", "ghcnh"],
                "temp_c": [4.0, 6.0],  # 2 C delta
            }
        )
        # Default tol = 2 C → not disagreement.
        assert iem_crosscheck(df).empty
        # Custom tol = 1 C → disagreement.
        assert len(iem_crosscheck(df, tolerance=1.0)) == 1


# ---------------------------------------------------------------------------
# wind_chill / heat_index against published references
# ---------------------------------------------------------------------------
class TestWindChillHeatIndex:
    def test_wind_chill_nws_reference_table(self) -> None:
        """NWS wind chill calculator: T=20°F V=20 mph → ~4°F.

        Formula: 35.74 + 0.6215T - 35.75V^0.16 + 0.4275T*V^0.16.
        For T=20 V=20: ≈ 4.24°F (verified against
        https://www.weather.gov/safety/cold-wind-chill-chart).
        """
        from mostlyright.transforms import wind_chill

        wc = wind_chill(20.0, 20.0)
        assert wc is not None
        assert 3.0 < wc < 6.0

    def test_wind_chill_extreme_cold(self) -> None:
        """NWS wind chill T=0°F V=30 mph → about -26°F."""
        from mostlyright.transforms import wind_chill

        wc = wind_chill(0.0, 30.0)
        assert wc is not None
        # NWS chart: T=0, V=30 → wc ≈ -26
        assert -30.0 < wc < -22.0

    def test_wind_chill_above_50f_returns_temp(self) -> None:
        from mostlyright.transforms import wind_chill

        # Outside validity: temp > 50F → returns temp unchanged.
        assert wind_chill(60.0, 20.0) == 60.0

    def test_heat_index_nws_reference(self) -> None:
        """NWS heat index T=90°F RH=70% → ~106°F."""
        from mostlyright.transforms import heat_index

        hi = heat_index(90.0, 70.0)
        assert hi is not None
        assert 100.0 < hi < 110.0

    def test_heat_index_below_80f_returns_temp(self) -> None:
        from mostlyright.transforms import heat_index

        assert heat_index(70.0, 50.0) == 70.0

    def test_nan_inputs_return_none(self) -> None:
        from mostlyright.transforms import heat_index, wind_chill

        assert wind_chill(math.nan, 10.0) is None
        assert heat_index(math.nan, 50.0) is None


# ---------------------------------------------------------------------------
# Optional Hypothesis property test for cyclical invariant
# ---------------------------------------------------------------------------
try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    _HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover
    _HAS_HYPOTHESIS = False


@pytest.mark.skipif(not _HAS_HYPOTHESIS, reason="hypothesis not installed")
class TestCalendarFeaturesProperty:
    @settings(max_examples=50, deadline=None)
    @given(
        year=st.integers(min_value=1990, max_value=2100),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        hour=st.integers(min_value=0, max_value=23),
    )
    def test_sin_squared_plus_cos_squared_is_one(
        self, year: int, month: int, day: int, hour: int
    ) -> None:
        from mostlyright.transforms import calendar_features

        ts = pd.Timestamp(year=year, month=month, day=day, hour=hour, tz="UTC")
        df = pd.DataFrame({"ts": [ts]})
        out = calendar_features(df, "ts")
        for prefix in ("month", "dow", "hour", "day_of_year"):
            s = float(out[f"{prefix}_sin"].iloc[0])
            c = float(out[f"{prefix}_cos"].iloc[0])
            assert abs(s * s + c * c - 1.0) < 1e-9, (
                f"{prefix} pair fails sin²+cos²=1 for {ts}: s={s}, c={c}, sum={s * s + c * c}"
            )
