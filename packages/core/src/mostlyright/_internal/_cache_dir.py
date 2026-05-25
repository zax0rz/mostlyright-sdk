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
_LEGACY_ENV: Final[str] = "TRADEWINDS_CACHE_DIR"
_CANONICAL_ENV: Final[str] = "MOSTLYRIGHT_CACHE_DIR"


def resolve_cache_dir() -> Path:
    canonical = os.environ.get(_CANONICAL_ENV)
    if canonical:
        return Path(canonical)
    legacy = os.environ.get(_LEGACY_ENV)
    if legacy:
        warnings.warn(
            f"{_LEGACY_ENV} is deprecated; use {_CANONICAL_ENV}. "
            f"Support will be removed in v0.3. Run: "
            f"mv ~/.tradewinds ~/.mostlyright",
            DeprecationWarning,
            stacklevel=2,
        )
        return Path(legacy)
    return _DEFAULT
