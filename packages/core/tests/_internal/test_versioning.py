"""Tests for versioned data snapshots — watermark/version concept.

TDD: Tests written FIRST. Implementation follows.

A DataVersion is a deterministic identifier for the state of a dataset at
a given point in time. Two queries with the same DataVersion always return
identical data. This enables reproducibility for model training and backtesting.

Lift note (Sprint 0 Wave 1, Lane V):
    The original mostlyright==0.14.1 ``tests/test_sdk_versioning.py`` also contained
    ``TestDataVersionSchema`` (depends on ``_capabilities.SPECS_DIR`` +
    ``specs/data_version.json``) and ``TestClientDataVersion`` (depends on
    ``mostlyright.client.MostlyRightClient``). Both modules are out of scope for
    this lane and intentionally not ported here — they will be re-lifted by the
    lanes that bring ``_capabilities``, ``specs/``, and ``client``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_obs(observed_at: str, station: str = "NYC") -> dict:
    return {
        "observed_at": observed_at,
        "station": station,
        "temp_f": 72.0,
        "temp_c": 22.2,
    }


# ---------------------------------------------------------------------------
# DataVersion dataclass
# ---------------------------------------------------------------------------


class TestDataVersion:
    def test_create_from_observations(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        obs_timestamps = [
            "2024-07-04T10:00:00Z",
            "2024-07-04T11:00:00Z",
            "2024-07-04T12:00:00Z",
        ]
        dv = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=obs_timestamps,
        )
        assert dv.station == "NYC"
        assert dv.as_of == "2024-07-04T13:00:00Z"
        assert dv.latest_observation == "2024-07-04T12:00:00Z"
        assert dv.observation_count == 3

    def test_empty_observations(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        dv = DataVersion.from_timestamps(
            station="ATL",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=[],
        )
        assert dv.latest_observation is None
        assert dv.observation_count == 0

    def test_version_token_is_string(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        dv = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        assert isinstance(dv.version, str)
        assert len(dv.version) > 0

    def test_version_token_is_deterministic(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        # Use explicit kwargs rather than **dict(...) so the type checker
        # can narrow each parameter's type instead of inferring ``str | list[str]``.
        dv1 = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        dv2 = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        assert dv1.version == dv2.version

    def test_different_data_different_version(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        dv1 = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        dv2 = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T11:00:00Z"],  # different
        )
        assert dv1.version != dv2.version

    def test_different_station_different_version(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        ts = ["2024-07-04T12:00:00Z"]
        dv1 = DataVersion.from_timestamps(
            station="NYC", as_of="2024-07-04T13:00:00Z", observation_timestamps=ts
        )
        dv2 = DataVersion.from_timestamps(
            station="ATL", as_of="2024-07-04T13:00:00Z", observation_timestamps=ts
        )
        assert dv1.version != dv2.version

    def test_as_of_not_in_hash(self) -> None:
        """Same observations at different query times → same version token."""
        from tradewinds._internal.versioning import DataVersion

        ts = ["2024-07-04T10:00:00Z", "2024-07-04T11:00:00Z", "2024-07-04T12:00:00Z"]
        dv_early = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=ts,
        )
        dv_late = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T23:59:00Z",  # different as_of
            observation_timestamps=ts,
        )
        # as_of is metadata only — token must be identical
        assert dv_early.version == dv_late.version
        # but as_of is preserved in the object
        assert dv_early.as_of == "2024-07-04T13:00:00Z"
        assert dv_late.as_of == "2024-07-04T23:59:00Z"

    def test_to_dict(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        dv = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        d = dv.to_dict()
        assert d["station"] == "NYC"
        assert d["as_of"] == "2024-07-04T13:00:00Z"
        assert d["version"] == dv.version
        assert d["latest_observation"] == "2024-07-04T12:00:00Z"
        assert d["observation_count"] == 1

    def test_from_dict_roundtrip(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        dv = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        d = dv.to_dict()
        dv2 = DataVersion.from_dict(d)
        assert dv2.version == dv.version
        assert dv2.station == dv.station
        assert dv2.as_of == dv.as_of


# ---------------------------------------------------------------------------
# version ordering helpers
# ---------------------------------------------------------------------------


class TestVersionOrdering:
    def test_is_newer_than(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        old = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T11:00:00Z",
            observation_timestamps=["2024-07-04T10:00:00Z"],
        )
        new = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        assert new.is_newer_than(old)
        assert not old.is_newer_than(new)

    def test_same_version_not_newer(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        dv = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T12:00:00Z"],
        )
        assert not dv.is_newer_than(dv)

    def test_is_stale_when_newer_obs_available(self) -> None:
        from tradewinds._internal.versioning import DataVersion

        dv = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T11:00:00Z",
            observation_timestamps=["2024-07-04T10:00:00Z"],
        )
        # A newer as_of with more observations → stale
        newer_dv = DataVersion.from_timestamps(
            station="NYC",
            as_of="2024-07-04T13:00:00Z",
            observation_timestamps=["2024-07-04T10:00:00Z", "2024-07-04T12:00:00Z"],
        )
        assert dv.is_stale(compared_to=newer_dv)
        assert not newer_dv.is_stale(compared_to=dv)
