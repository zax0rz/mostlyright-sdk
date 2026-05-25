"""Versioned data snapshots — watermark/version concept.

A DataVersion is a deterministic identifier for the state of a dataset at a
given point in time.  Two queries that return the same version token always
return identical data, enabling reproducibility for ML training and backtesting.

Version token design:
    SHA-256( station + "|" + ",".join(sorted(observation_timestamps)) )
    truncated to 16 hex chars.  Opaque to callers — treat as an equality key.

    NOTE: as_of is stored as metadata but NOT included in the hash.  Same
    observations queried at different times → same version token.

Usage::

    from tradewinds._internal.versioning import DataVersion

    dv = DataVersion.from_timestamps(
        station="NYC",
        as_of="2024-07-04T13:00:00Z",
        observation_timestamps=["2024-07-04T12:00:00Z", "2024-07-04T11:00:00Z"],
    )
    print(dv.version)   # e.g. "a3f8c1d2e4b5f6a7"
    print(dv.to_dict())
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DataVersion:
    """Deterministic version record for a dataset at a point in time.

    Attributes:
        version: Opaque 16-char hex token. Same observations → same token,
            regardless of when the query was made (as_of is NOT in hash).
        station: Normalized station code (e.g. "NYC").
        as_of: Query watermark (UTC ISO 8601 string). Stored as metadata only.
        latest_observation: Latest observation timestamp included, or None.
        observation_count: Number of observations included.
    """

    version: str
    station: str
    as_of: str
    latest_observation: str | None
    observation_count: int

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_timestamps(
        cls,
        *,
        station: str,
        as_of: str,
        observation_timestamps: list[str],
    ) -> DataVersion:
        """Build a DataVersion from a list of observation timestamps.

        Args:
            station: Normalized station code.
            as_of: Query watermark (UTC ISO 8601). Stored as metadata, not hashed.
            observation_timestamps: List of observed_at strings.

        Returns:
            DataVersion with a deterministic version token.
        """
        sorted_ts = sorted(observation_timestamps)
        payload = station + "|" + ",".join(sorted_ts)
        token = hashlib.sha256(payload.encode()).hexdigest()[:16]
        latest = sorted_ts[-1] if sorted_ts else None
        return cls(
            version=token,
            station=station,
            as_of=as_of,
            latest_observation=latest,
            observation_count=len(sorted_ts),
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DataVersion:
        """Deserialize from a dict (e.g. from JSON / API response)."""
        return cls(
            version=d["version"],
            station=d["station"],
            as_of=d["as_of"],
            latest_observation=d.get("latest_observation"),
            observation_count=d["observation_count"],
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict (matches specs/data_version.json)."""
        return {
            "version": self.version,
            "station": self.station,
            "as_of": self.as_of,
            "latest_observation": self.latest_observation,
            "observation_count": self.observation_count,
        }

    # ------------------------------------------------------------------
    # Ordering helpers
    # ------------------------------------------------------------------

    def is_newer_than(self, other: DataVersion) -> bool:
        """Return True if this version's as_of is strictly after other's as_of."""
        return self.as_of > other.as_of

    def is_stale(self, *, compared_to: DataVersion) -> bool:
        """Return True if compared_to has more recent data than self.

        A version is stale when compared_to has a later latest_observation
        or more observations for the same dataset.
        """
        if compared_to.latest_observation is None:
            return False
        if self.latest_observation is None:
            return compared_to.observation_count > 0
        if compared_to.latest_observation > self.latest_observation:
            return True
        return compared_to.observation_count > self.observation_count
