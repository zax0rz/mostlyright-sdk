"""Shared base utilities for MostlyRight model dataclasses."""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar


class DictLikeMixin:
    """Mixin providing dict-style access on frozen dataclasses.

    Supports obs["field"], "field" in obs, obs.get("field", default).
    """

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    # Fields computed at load time, not stored in parquet.
    _COMPUTED_FIELDS: ClassVar[frozenset[str]] = frozenset()

    def to_dict(self) -> dict[str, Any]:
        """All fields including computed."""
        return dataclasses.asdict(self)  # type: ignore[arg-type]

    def to_storage_dict(self) -> dict[str, Any]:
        """Storage fields only (matches JSON Schema, no computed fields)."""
        return {
            k: v
            for k, v in dataclasses.asdict(self).items()  # type: ignore[arg-type]
            if k not in self._COMPUTED_FIELDS
        }

    def to_toon(self) -> str:
        """Encode as TOON v3.0 string. Storage fields only (30 fields).

        Matches the served API contract - no computed fields leak.
        Use ``encode(self.to_dict())`` directly if you need computed fields.
        """
        from tradewinds._internal._toon import encode

        return encode(self.to_storage_dict())
