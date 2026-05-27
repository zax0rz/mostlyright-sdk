"""Weather catalog: adapter registry + WeatherAdapter Protocol.

Each adapter wraps a Phase 1 parser (``_iem`` / ``_awc`` / ``_climate`` /
``_ghcnh``) and emits a canonical-schema DataFrame with overlay columns
(``source``, ``retrieved_at``, ``knowledge_time``, ``event_time``). Adapters
declare ``SUPPORTED_SOURCES`` at class level and self-register with the
module-level ``_REGISTRY`` at import time.

``get_adapter(source_id)`` is the canonical dispatch — given a source ID
(``"iem.archive"``, ``"awc.live"``, ``"cli.archive"``, ``"ghcnh.archive"``)
it returns a fresh adapter instance.

The registry is eagerly populated when ``mostlyright.weather.catalog`` is
imported. The four canonical adapter modules import this module first to
get the ``_REGISTRY`` dict, then ``register_adapter()`` appends each.
"""

from __future__ import annotations

from typing import ClassVar, Protocol

import pandas as pd

__all__ = [
    "WeatherAdapter",
    "get_adapter",
    "list_sources",
    "register_adapter",
]


class WeatherAdapter(Protocol):
    """Protocol every weather catalog adapter satisfies."""

    SUPPORTED_SOURCES: ClassVar[list[str]]

    def fetch_observations(
        self,
        source: str,
        station: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Fetch observations from ``source`` for the given station + window.

        The returned DataFrame conforms to ``schema.observation.v1`` and
        carries ``df.attrs["source"] = source``.
        """
        ...


_REGISTRY: dict[str, type[WeatherAdapter]] = {}


def register_adapter(source_id: str, adapter_cls: type[WeatherAdapter]) -> None:
    """Register an adapter class against a source ID.

    Idempotent — re-registering the same class is a no-op. Conflicting
    re-registration raises ``ValueError`` so adapters never silently
    shadow each other.
    """
    existing = _REGISTRY.get(source_id)
    if existing is not None and existing is not adapter_cls:
        raise ValueError(
            f"source_id {source_id!r} already registered to "
            f"{existing.__name__}; cannot re-register to "
            f"{adapter_cls.__name__}"
        )
    _REGISTRY[source_id] = adapter_cls


def get_adapter(source: str) -> WeatherAdapter:
    """Return a fresh adapter instance for ``source``.

    Raises:
        DataAvailabilityError: ``source`` is not registered. The error carries
            ``reason="model_unavailable"`` so cross-SDK consumers can branch
            on ``e.reason`` rather than string-matching the message.
            DataAvailabilityError is a subclass of TradewindsError, so code
            catching the broader base class continues to work.
    """
    cls = _REGISTRY.get(source)
    if cls is None:
        # Phase 21 21-09: migrated from SourceUnavailableError to the structural
        # DataAvailabilityError. Reason="model_unavailable" matches the lockstep
        # TS enum.
        from mostlyright.core.exceptions import DataAvailabilityError

        raise DataAvailabilityError(
            reason="model_unavailable",
            hint=f"Unknown source {source!r}; known sources: {sorted(_REGISTRY)}",
            source=source,
        )
    return cls()


def list_sources() -> list[str]:
    """Return the sorted list of registered source IDs."""
    return sorted(_REGISTRY)


# Eager import of the four canonical adapters — each calls
# ``register_adapter`` at import time. Done at the bottom to avoid
# circular imports (each adapter imports symbols from this module).
from mostlyright.weather.catalog import awc, cli, ghcnh, iem  # noqa: E402, F401
