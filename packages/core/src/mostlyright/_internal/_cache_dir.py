"""Resolve the on-disk cache directory.

Resolution order (highest precedence first):
1. ``MOSTLYRIGHT_CACHE_DIR`` env var (canonical, post-Phase-12).
2. ``TRADEWINDS_CACHE_DIR`` env var (legacy; emits DeprecationWarning;
   scheduled for removal in v0.3).
3. Default: ``~/.mostlyright/cache/v1/``.

In v0.3 the ``TRADEWINDS_CACHE_DIR`` branch will be removed; users on v0.2.x get
one full release to migrate. Migration is byte-equivalent: ``mv ~/.tradewinds
~/.mostlyright`` works without schema change.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Final

_DEFAULT: Final[Path] = Path.home() / ".mostlyright" / "cache" / "v1"
_DEFAULT_ROOT: Final[Path] = Path.home() / ".mostlyright" / "cache"  # without /v1
_LEGACY_ENV: Final[str] = "TRADEWINDS_CACHE_DIR"
_CANONICAL_ENV: Final[str] = "MOSTLYRIGHT_CACHE_DIR"
_DEPRECATION_MESSAGE: Final[str] = (
    f"{_LEGACY_ENV} is deprecated; use {_CANONICAL_ENV}. "
    f"Support will be removed in v0.3. Run: mv ~/.tradewinds ~/.mostlyright"
)


def _resolve_env_value(stacklevel: int = 2) -> str | None:
    """Read the env-var override (canonical → legacy + warn), or return None.

    Shared by :func:`resolve_cache_dir` (which appends ``/v1`` for the canonical
    "full cache dir" callers) and by the 3 legacy ``_cache_root()`` helpers
    in :mod:`mostlyright.discovery`, :mod:`mostlyright.weather.cache`, and
    :mod:`mostlyright.markets._trades_cache` (which preserve the legacy
    "env var = cache ROOT without /v1, callers append CACHE_VERSION" contract).

    Single source of truth for the resolution order + deprecation warning, so a
    future change to either (e.g. adding XDG fallback, changing the v0.3
    removal text) propagates to all consumers atomically.
    """
    canonical = os.environ.get(_CANONICAL_ENV)
    if canonical:
        return canonical
    legacy = os.environ.get(_LEGACY_ENV)
    if legacy:
        warnings.warn(
            _DEPRECATION_MESSAGE,
            DeprecationWarning,
            stacklevel=stacklevel + 1,
        )
        return legacy
    return None


def resolve_cache_dir() -> Path:
    """Return the full cache directory (with ``/v1`` default).

    Resolution order: ``MOSTLYRIGHT_CACHE_DIR`` env > ``TRADEWINDS_CACHE_DIR`` env
    (DeprecationWarning, removed v0.3) > ``~/.mostlyright/cache/v1``.

    New callers that want the canonical full cache directory should use this
    function. Existing callers that build paths via ``_cache_root() / CACHE_VERSION``
    use :func:`resolve_cache_root_without_v1` to preserve the legacy contract.
    """
    value = _resolve_env_value(stacklevel=2)
    if value is not None:
        return Path(value)
    return _DEFAULT


def resolve_cache_root_without_v1() -> Path:
    """Return the cache ROOT (without ``/v1``) — the legacy contract.

    Used by the 3 ``_cache_root()`` helpers in ``discovery.py``,
    ``weather/cache.py``, and ``markets/_trades_cache.py`` which still append
    ``CACHE_VERSION='v1'`` themselves. Same resolution order as
    :func:`resolve_cache_dir` (canonical → legacy + warn → default), but the
    default is ``~/.mostlyright/cache`` (no ``/v1``), and env-var overrides are
    returned verbatim (legacy semantic: env var IS the cache root).

    v0.3 work: collapse the two helpers into one when the legacy contract is
    retired alongside ``TRADEWINDS_CACHE_DIR``.
    """
    value = _resolve_env_value(stacklevel=2)
    if value is not None:
        return Path(value).expanduser()
    return _DEFAULT_ROOT
