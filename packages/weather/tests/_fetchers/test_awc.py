"""Tests for mostlyright.weather._fetchers.awc — AWC live METAR HTTP fetcher.

Sprint 0 Wave 3B (Lane F, net-new code). Covers:

- happy path returns parsed JSON list
- URL + params constructed correctly (host, ids, format, taf, hours)
- multi-station ICAO list comma-joined
- ``hours`` parameter forwarded as string
- 4xx response returns empty list (no exception)
- 5xx response retries then succeeds
- 5xx response exhausts retries and returns empty list
- network/timeout error returns empty list
- non-list JSON body returns empty list (defensive)
- empty station list short-circuits with empty list, no request issued

All tests mock ``httpx`` via ``respx``; none hit the live AWC endpoint. The
live endpoint is exercised by Wave 4 parity tests and by the existing
``spike/research_spike.py`` (out of scope for this fetcher's unit tests).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from mostlyright.weather._fetchers.awc import AWC_METAR_URL, fetch_awc_metars


def _sample_metar(icao: str = "KNYC") -> dict[str, Any]:
    """Minimal AWC METAR JSON shape — matches the spike sample row.

    See ``spike/SPIKE_REPORT.md`` for the full real-world response.
    """
    return {
        "icaoId": icao,
        "reportTime": "2026-05-21T19:00:00.000Z",
        "obsTime": 1747853400,
        "temp": 14.4,
        "dewp": 12.8,
        "wspd": 3,
        "metarType": "METAR",
        "rawOb": (
            f"METAR {icao} 211851Z AUTO VRB03KT 10SM SCT019 BKN036 OVC110 14/13 A3025 RMK AO2"
        ),
    }


class TestAwcFetcherHappyPath:
    def test_returns_list_of_dicts(self) -> None:
        with respx.mock(assert_all_called=True) as mock:
            mock.get(AWC_METAR_URL).respond(200, json=[_sample_metar()])
            result = fetch_awc_metars(["KNYC"], hours=24)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["icaoId"] == "KNYC"
        assert result[0]["rawOb"].startswith("METAR KNYC")

    def test_returns_multiple_rows(self) -> None:
        with respx.mock(assert_all_called=True) as mock:
            mock.get(AWC_METAR_URL).respond(
                200,
                json=[_sample_metar("KNYC"), _sample_metar("KLAX")],
            )
            result = fetch_awc_metars(["KNYC", "KLAX"])

        assert len(result) == 2
        assert {r["icaoId"] for r in result} == {"KNYC", "KLAX"}

    def test_empty_list_response_returned_as_empty_list(self) -> None:
        """AWC returns ``[]`` for stations with no recent reports — not an error."""
        with respx.mock(assert_all_called=True) as mock:
            mock.get(AWC_METAR_URL).respond(200, json=[])
            result = fetch_awc_metars(["KNYC"])

        assert result == []


class TestAwcFetcherUrlAndParams:
    def test_url_is_aviationweather_metar_endpoint(self) -> None:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(AWC_METAR_URL).respond(200, json=[])
            fetch_awc_metars(["KNYC"])

        # respx asserts the route was called — URL host/path matched
        assert route.called
        # Sanity-check the canonical URL string (catches accidental host changes)
        assert AWC_METAR_URL == "https://aviationweather.gov/api/data/metar"

    def test_required_query_params_present(self) -> None:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(AWC_METAR_URL).respond(200, json=[])
            fetch_awc_metars(["KNYC"], hours=24)

        request = route.calls.last.request
        params = request.url.params
        assert params["ids"] == "KNYC"
        assert params["format"] == "json"
        assert params["taf"] == "false"
        assert params["hours"] == "24"

    def test_multi_station_ids_comma_joined(self) -> None:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(AWC_METAR_URL).respond(200, json=[])
            fetch_awc_metars(["KNYC", "KLAX", "KORD"])

        request = route.calls.last.request
        assert request.url.params["ids"] == "KNYC,KLAX,KORD"

    def test_hours_param_passed_correctly(self) -> None:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(AWC_METAR_URL).respond(200, json=[])
            fetch_awc_metars(["KNYC"], hours=72)

        assert route.calls.last.request.url.params["hours"] == "72"

    def test_default_hours_is_168(self) -> None:
        """Default lookback = AWC's max (~7 days)."""
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(AWC_METAR_URL).respond(200, json=[])
            fetch_awc_metars(["KNYC"])

        assert route.calls.last.request.url.params["hours"] == "168"

    def test_empty_station_list_short_circuits(self) -> None:
        """No request is issued when station list is empty."""
        with respx.mock(assert_all_called=False) as mock:
            route = mock.get(AWC_METAR_URL).respond(200, json=[_sample_metar()])
            result = fetch_awc_metars([])

        assert result == []
        assert not route.called


class TestAwcFetcher4xx:
    def test_404_returns_empty_list(self) -> None:
        """4xx is permanent — match v0.14.1 awc_poller.fetch_latest: log + [] not raise."""
        with respx.mock(assert_all_called=True) as mock:
            mock.get(AWC_METAR_URL).respond(404)
            result = fetch_awc_metars(["KNYC"])

        assert result == []

    def test_400_returns_empty_list(self) -> None:
        with respx.mock(assert_all_called=True) as mock:
            mock.get(AWC_METAR_URL).respond(400)
            result = fetch_awc_metars(["KNYC"])

        assert result == []


class TestAwcFetcher5xx:
    def test_500_retried_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """5xx is transient — exponential backoff up to MAX_RETRIES."""
        monkeypatch.setattr("mostlyright.weather._fetchers.awc.time.sleep", lambda _: None)

        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(AWC_METAR_URL)
            route.side_effect = [
                httpx.Response(500),
                httpx.Response(503),
                httpx.Response(200, json=[_sample_metar()]),
            ]
            result = fetch_awc_metars(["KNYC"])

        assert len(result) == 1
        assert result[0]["icaoId"] == "KNYC"

    def test_503_exhausts_retries_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """After MAX_RETRIES attempts of 5xx, return [] (do not raise)."""
        monkeypatch.setattr("mostlyright.weather._fetchers.awc.time.sleep", lambda _: None)

        with respx.mock() as mock:
            mock.get(AWC_METAR_URL).respond(503)
            result = fetch_awc_metars(["KNYC"])

        assert result == []

    def test_502_exhausts_retries_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("mostlyright.weather._fetchers.awc.time.sleep", lambda _: None)

        with respx.mock() as mock:
            mock.get(AWC_METAR_URL).respond(502)
            result = fetch_awc_metars(["KNYC"])

        assert result == []


class TestAwcFetcherNetworkErrors:
    def test_connect_timeout_returns_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """httpx.RequestError (timeout, DNS failure, etc.) — retry then [] ."""
        monkeypatch.setattr("mostlyright.weather._fetchers.awc.time.sleep", lambda _: None)

        with respx.mock() as mock:
            mock.get(AWC_METAR_URL).mock(side_effect=httpx.ConnectTimeout("boom"))
            result = fetch_awc_metars(["KNYC"])

        assert result == []

    def test_network_error_then_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One transient network error, then success — should return data."""
        monkeypatch.setattr("mostlyright.weather._fetchers.awc.time.sleep", lambda _: None)

        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(AWC_METAR_URL)
            route.side_effect = [
                httpx.ConnectTimeout("flaky"),
                httpx.Response(200, json=[_sample_metar()]),
            ]
            result = fetch_awc_metars(["KNYC"])

        assert len(result) == 1


class TestAwcFetcherMalformedResponse:
    def test_non_list_json_returns_empty_list(self) -> None:
        """Defensive: AWC should always return a list; dict body is treated as error."""
        with respx.mock(assert_all_called=True) as mock:
            mock.get(AWC_METAR_URL).respond(200, json={"error": "unexpected"})
            result = fetch_awc_metars(["KNYC"])

        assert result == []

    def test_invalid_json_returns_empty_list(self) -> None:
        """200 OK with non-JSON body — log and return []."""
        with respx.mock(assert_all_called=True) as mock:
            mock.get(AWC_METAR_URL).respond(
                200,
                content=b"not json at all",
                headers={"content-type": "text/plain"},
            )
            result = fetch_awc_metars(["KNYC"])

        assert result == []
