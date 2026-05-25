"""Tests for mostlyright.weather._fetchers.iem_cli.

NEW code (Sprint 0 Wave 3B, Lane F) — covers URL/params, response unwrapping,
404 + range-helper continuation, cache hits, ``skip_cache``, and multi-year
ranges. All HTTP is mocked via ``respx``; no network calls.

Settlement-grade: IEM CLI is THE Kalshi NHIGH/NLOW settlement source, so the
unwrapping + cache writes are checked byte-by-byte against the same JSON
shape the parser (``mostlyright.weather._climate``) consumes.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from mostlyright.weather._fetchers.iem_cli import (
    IEM_CLI_BASE_URL,
    IEM_CLI_POLITE_DELAY,
    download_cli,
    download_cli_range,
)


def _skip_if_no_respx() -> object:
    """Import respx lazily so the test file collects in environments where
    respx is missing — and skips cleanly."""
    try:
        import respx  # noqa: F401
    except ImportError:  # pragma: no cover - environment guard
        pytest.skip("respx not installed; skipping HTTP mock tests")
    return __import__("respx")


# Sample shape mirrors what IEM cli.py returns. The parser tests already
# exercise field semantics; here we only care about the wire format the
# fetcher must round-trip faithfully.
_SAMPLE_INNER = [
    {
        "station": "KNYC",
        "valid": "2025-01-01",
        "high": 38,
        "low": 28,
        "product": "202501020615-KOKX-CDUS41-CLINYC",
        "name": "NEW YORK CENTRAL PARK",
    },
    {
        "station": "KNYC",
        "valid": "2025-01-02",
        "high": 41,
        "low": 30,
        "product": "202501030620-KOKX-CDUS41-CLINYC",
        "name": "NEW YORK CENTRAL PARK",
    },
]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the polite delay in tests so they finish in milliseconds."""
    monkeypatch.setattr("mostlyright.weather._fetchers.iem_cli.time.sleep", lambda _: None)


class TestModuleConstants:
    def test_base_url(self) -> None:
        assert IEM_CLI_BASE_URL == "https://mesonet.agron.iastate.edu/json/cli.py"

    def test_polite_delay(self) -> None:
        # v0.14.1 parity: 1.0s between calls.
        assert IEM_CLI_POLITE_DELAY == 1.0


class TestDownloadCli:
    def test_url_params_station_and_year(self, tmp_path: Path) -> None:
        """The fetched URL is ``?station=KNYC&year=2025``."""
        respx = _skip_if_no_respx()
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025"

        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(url).respond(200, json=_SAMPLE_INNER)
            out = download_cli("KNYC", 2025, tmp_path)
            assert route.called
            # respx matched the exact URL above; verify the recorded request
            # carried both query params.
            req = route.calls.last.request
            assert req.url.params["station"] == "KNYC"
            assert req.url.params["year"] == "2025"

        assert out == tmp_path / "KNYC" / "cli_2025.json"
        assert out.exists()

    def test_response_unwraps_results_key(self, tmp_path: Path) -> None:
        """``{"results": [...]}`` is saved as a bare JSON list, not the wrapper."""
        respx = _skip_if_no_respx()
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025"

        with respx.mock() as mock:
            mock.get(url).respond(200, json={"results": _SAMPLE_INNER})
            out = download_cli("KNYC", 2025, tmp_path)

        on_disk = json.loads(out.read_text())
        assert isinstance(on_disk, list)
        assert on_disk == _SAMPLE_INNER

    def test_response_bare_list_passes_through(self, tmp_path: Path) -> None:
        """If IEM already returns a bare list, the cache contents match."""
        respx = _skip_if_no_respx()
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025"

        with respx.mock() as mock:
            mock.get(url).respond(200, json=_SAMPLE_INNER)
            out = download_cli("KNYC", 2025, tmp_path)

        on_disk = json.loads(out.read_text())
        assert on_disk == _SAMPLE_INNER

    def test_unexpected_shape_raises_value_error(self, tmp_path: Path) -> None:
        """A dict without ``results`` (or any non-list) is a hard error — the
        downstream parser expects a list."""
        respx = _skip_if_no_respx()
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025"

        with respx.mock() as mock:
            mock.get(url).respond(200, json={"unexpected": "shape"})
            with pytest.raises(ValueError, match="Unexpected IEM CLI"):
                download_cli("KNYC", 2025, tmp_path)

        # Neither the raw staging file nor the final cache file should linger.
        assert not (tmp_path / "KNYC" / "cli_2025.json").exists()
        assert not (tmp_path / "KNYC" / "cli_2025_raw.json").exists()

    def test_404_raises_http_status_error(self, tmp_path: Path) -> None:
        """IEM returns 404 for years with no data — propagate so the caller
        (typically :func:`download_cli_range`) can decide."""
        respx = _skip_if_no_respx()
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=1900"

        with respx.mock() as mock:
            mock.get(url).respond(404)
            with pytest.raises(httpx.HTTPStatusError):
                download_cli("KNYC", 1900, tmp_path)

        assert not (tmp_path / "KNYC" / "cli_1900.json").exists()

    def test_cache_hit_skips_http(self, tmp_path: Path) -> None:
        """If the cache file exists and ``skip_cache=False``, no HTTP call."""
        respx = _skip_if_no_respx()
        dest = tmp_path / "KNYC" / "cli_2025.json"
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps(_SAMPLE_INNER))
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025"

        # assert_all_called=False so a never-fired route still passes; we are
        # *asserting* that no request goes out.
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get(url).respond(200, json=_SAMPLE_INNER)
            out = download_cli("KNYC", 2025, tmp_path)
            assert not route.called

        assert out == dest

    def test_skip_cache_true_redownloads(self, tmp_path: Path) -> None:
        """``skip_cache=True`` forces a fresh fetch and overwrites the file."""
        respx = _skip_if_no_respx()
        dest = tmp_path / "KNYC" / "cli_2025.json"
        dest.parent.mkdir(parents=True)
        stale_payload = [{"station": "KNYC", "valid": "1999-01-01", "high": 0, "low": 0}]
        dest.write_text(json.dumps(stale_payload))
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025"

        with respx.mock(assert_all_called=True) as mock:
            mock.get(url).respond(200, json=_SAMPLE_INNER)
            out = download_cli("KNYC", 2025, tmp_path, skip_cache=True)

        assert out == dest
        assert json.loads(out.read_text()) == _SAMPLE_INNER

    def test_creates_station_subdir(self, tmp_path: Path) -> None:
        """Cache layout is ``<dest_dir>/<icao>/cli_<year>.json``."""
        respx = _skip_if_no_respx()
        url = f"{IEM_CLI_BASE_URL}?station=KLGA&year=2024"

        with respx.mock() as mock:
            mock.get(url).respond(200, json=_SAMPLE_INNER)
            out = download_cli("KLGA", 2024, tmp_path)

        assert out.parent == tmp_path / "KLGA"
        assert out.name == "cli_2024.json"

    def test_raw_staging_file_cleaned_up(self, tmp_path: Path) -> None:
        """After a successful unwrap+rewrite, no ``_raw.json`` lingers."""
        respx = _skip_if_no_respx()
        url = f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025"

        with respx.mock() as mock:
            mock.get(url).respond(200, json={"results": _SAMPLE_INNER})
            download_cli("KNYC", 2025, tmp_path)

        assert not (tmp_path / "KNYC" / "cli_2025_raw.json").exists()


class TestDownloadCliRange:
    def test_multi_year_range_produces_one_file_per_year(self, tmp_path: Path) -> None:
        """2020..2025 inclusive = 6 files in the per-station subdir."""
        respx = _skip_if_no_respx()

        with respx.mock(assert_all_called=True) as mock:
            for year in range(2020, 2026):
                url = f"{IEM_CLI_BASE_URL}?station=KNYC&year={year}"
                mock.get(url).respond(200, json=_SAMPLE_INNER)
            paths = download_cli_range("KNYC", 2020, 2025, tmp_path)

        assert len(paths) == 6
        assert [p.name for p in paths] == [
            "cli_2020.json",
            "cli_2021.json",
            "cli_2022.json",
            "cli_2023.json",
            "cli_2024.json",
            "cli_2025.json",
        ]
        # Each lands under the per-station subdir.
        for p in paths:
            assert p.parent == tmp_path / "KNYC"
            assert p.exists()

    def test_range_skips_404_years(self, tmp_path: Path) -> None:
        """A 404 in the middle of a range logs + continues; the missing year
        is absent from the returned manifest, but neighbours still land."""
        respx = _skip_if_no_respx()

        with respx.mock(assert_all_called=True) as mock:
            mock.get(f"{IEM_CLI_BASE_URL}?station=KNYC&year=2020").respond(200, json=_SAMPLE_INNER)
            mock.get(f"{IEM_CLI_BASE_URL}?station=KNYC&year=2021").respond(404)
            mock.get(f"{IEM_CLI_BASE_URL}?station=KNYC&year=2022").respond(200, json=_SAMPLE_INNER)
            paths = download_cli_range("KNYC", 2020, 2022, tmp_path)

        assert len(paths) == 2
        names = [p.name for p in paths]
        assert "cli_2020.json" in names
        assert "cli_2022.json" in names
        assert "cli_2021.json" not in names
        # No phantom cache for the 404 year.
        assert not (tmp_path / "KNYC" / "cli_2021.json").exists()

    def test_range_propagates_non_404_http_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A persistent 503 (after retries are exhausted) is not "no data" —
        it must propagate so the caller knows the run is degraded."""
        respx = _skip_if_no_respx()

        # download_with_retry sleeps between 5xx retries; bypass that for speed.
        monkeypatch.setattr("mostlyright._internal._http.time.sleep", lambda _: None)

        with respx.mock() as mock:
            mock.get(f"{IEM_CLI_BASE_URL}?station=KNYC&year=2020").respond(200, json=_SAMPLE_INNER)
            mock.get(f"{IEM_CLI_BASE_URL}?station=KNYC&year=2021").respond(503)
            with pytest.raises(httpx.HTTPStatusError):
                download_cli_range("KNYC", 2020, 2022, tmp_path)

    def test_range_single_year(self, tmp_path: Path) -> None:
        """Inclusive bounds: ``start_year == end_year`` produces one file."""
        respx = _skip_if_no_respx()

        with respx.mock(assert_all_called=True) as mock:
            mock.get(f"{IEM_CLI_BASE_URL}?station=KNYC&year=2025").respond(200, json=_SAMPLE_INNER)
            paths = download_cli_range("KNYC", 2025, 2025, tmp_path)

        assert len(paths) == 1
        assert paths[0].name == "cli_2025.json"

    def test_range_rejects_inverted_bounds(self, tmp_path: Path) -> None:
        """``end_year < start_year`` is a programmer error, not silent empty."""
        with pytest.raises(ValueError, match=">= start_year"):
            download_cli_range("KNYC", 2025, 2020, tmp_path)

    def test_range_honors_cache(self, tmp_path: Path) -> None:
        """Years already on disk are not re-fetched; new years are."""
        respx = _skip_if_no_respx()

        # Pre-seed 2020.
        cached = tmp_path / "KNYC" / "cli_2020.json"
        cached.parent.mkdir(parents=True)
        cached.write_text(json.dumps(_SAMPLE_INNER))

        with respx.mock(assert_all_called=True) as mock:
            mock.get(f"{IEM_CLI_BASE_URL}?station=KNYC&year=2021").respond(200, json=_SAMPLE_INNER)
            paths = download_cli_range("KNYC", 2020, 2021, tmp_path)

        assert len(paths) == 2
        assert paths[0] == cached
        assert paths[1] == tmp_path / "KNYC" / "cli_2021.json"


# ---------------------------------------------------------------------------
# Station-string boundary validation (Rob PR #2 C1/H8)
# ---------------------------------------------------------------------------
class TestStationBoundaryValidation:
    """``download_cli`` + ``download_cli_range`` reject path-traversal payloads.

    No HTTP mock - validation must fail BEFORE any request is built.
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "../evil",
            "..",
            "../../../tmp/evil",
            "KNYC/../etc",
            "KNYC/etc",
            "KNYC\\windows",
            "KNYC\x00",
            "KNYC\n",
            "K NYC",
            "knyc",
        ],
    )
    def test_download_cli_rejects_traversal(self, tmp_path: Path, payload: str) -> None:
        with pytest.raises(ValueError, match="STATION_CODE_RE"):
            download_cli(payload, 2024, tmp_path)

    @pytest.mark.parametrize("payload", ["../evil", "KNYC/etc", "knyc"])
    def test_download_cli_range_rejects_traversal(self, tmp_path: Path, payload: str) -> None:
        with pytest.raises(ValueError, match="STATION_CODE_RE"):
            download_cli_range(payload, 2023, 2024, tmp_path)
