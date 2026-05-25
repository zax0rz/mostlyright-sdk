"""Phase 10 — tests for the discover(city=) ergonomic surface."""

from __future__ import annotations

import pytest
from mostlyright import discover


class TestDiscoverCity:
    def test_nyc_returns_dataframe_with_expected_columns(self):
        df = discover(city="NYC")
        assert list(df.columns) == ["city", "station", "settles_for"]
        assert df.attrs["city"] == "NYC"
        assert df.attrs["source"] == "discover"

    def test_nyc_includes_KNYC_and_KLGA(self):
        df = discover(city="NYC")
        stations = df["station"].tolist()
        assert "KNYC" in stations
        assert "KLGA" in stations

    def test_nyc_KNYC_settles_for_kalshi(self):
        df = discover(city="NYC")
        knyc_row = df[df["station"] == "KNYC"].iloc[0]
        assert "kalshi:NYC" in knyc_row["settles_for"]

    def test_nyc_KLGA_settles_for_polymarket(self):
        """The KLGA row should annotate `polymarket:nyc` even when the
        input city is 'NYC' (upper) — annotate_settles_for normalizes."""
        df = discover(city="NYC")
        klga_row = df[df["station"] == "KLGA"].iloc[0]
        assert "polymarket:nyc" in klga_row["settles_for"]

    def test_nyc_KJFK_has_empty_settles_for(self):
        """KJFK is in Polymarket's NYC denylist — no issuer settles
        against it, but it's surfaced so quants see the full neighborhood."""
        df = discover(city="NYC")
        kjfk_row = df[df["station"] == "KJFK"].iloc[0]
        assert kjfk_row["settles_for"] == []

    def test_chicago_polymarket_KORD_settles_for_polymarket(self):
        df = discover(city="chicago")
        kord_row = df[df["station"] == "KORD"].iloc[0]
        assert "polymarket:chicago" in kord_row["settles_for"]

    def test_chicago_KMDW_cross_issuer_kalshi_polymarket_denylist(self):
        """Iter-1 python-architect HIGH: KMDW is Kalshi's Chicago station
        AND in Polymarket's chicago denylist. Cross-issuer alias surfaces
        it correctly — kalshi:CHI annotation present (NOT empty)."""
        df = discover(city="chicago")
        kmdw_row = df[df["station"] == "KMDW"].iloc[0]
        # The cross-issuer alias resolves "chicago" → kalshi "CHI" → KMDW.
        # The denylist surfacing now correctly shows KMDW belongs to Kalshi.
        assert "kalshi:CHI" in kmdw_row["settles_for"]

    def test_chicago_and_CHI_return_same_cross_issuer_table(self):
        """Both slug forms produce the same full cross-issuer neighborhood
        (the iter-1 architect bite-y test)."""
        long_form = discover(city="chicago")
        short_form = discover(city="CHI")
        assert sorted(long_form["station"].tolist()) == sorted(short_form["station"].tolist())

    def test_empty_city_raises(self):
        with pytest.raises(ValueError, match="non-empty str"):
            discover(city="")

    def test_unknown_city_raises(self):
        with pytest.raises(ValueError, match="unknown city"):
            discover(city="atlantis")

    def test_keyword_only_arg(self):
        with pytest.raises(TypeError):
            discover("NYC")  # type: ignore[misc]

    def test_missing_markets_pkg_raises_source_unavailable(self, monkeypatch):
        """Iter-2 codex HIGH: when `mostlyright.markets` is missing
        (because the user installed `mostlyright` without
        `mostlyright-markets`), discover() must raise a friendly
        SourceUnavailableError with the install hint — NOT a raw
        ModuleNotFoundError.

        Simulate the missing-markets condition by intercepting the
        resolve_city call with a function that raises the canonical
        error shape Python emits when the markets package isn't
        installed.
        """
        from mostlyright import _compose
        from mostlyright.core.exceptions import SourceUnavailableError

        def fake_resolve_city(_city: str):
            raise ModuleNotFoundError(
                "No module named 'mostlyright.markets'", name="mostlyright.markets"
            )

        monkeypatch.setattr(_compose, "resolve_city", fake_resolve_city)
        with pytest.raises(SourceUnavailableError, match="mostlyright-markets"):
            discover(city="NYC")
