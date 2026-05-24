"""Local parquet cache for Phase 9 trade-history rows (TRADES-06).

Path layout::

    $HOME/.tradewinds/cache/v1/trades/<issuer>/<ticker>/<YYYY-MM>.parquet

Override the root via the ``TRADEWINDS_CACHE_DIR`` environment variable.

Safety guarantees mirror :mod:`tradewinds.weather.cache`:

- **Atomic write** via sibling ``.tmp`` + ``os.replace`` (works on POSIX
  + Windows).
- **FileLock-guarded** to serialize concurrent writers on the same
  ``(issuer, ticker, year, month)`` key.
- **Current-UTC-month-skip** — the active calendar month is still
  rewriteable (new trades may arrive), so writes are no-ops and reads
  return ``None`` to force re-fetch.
- **Future-month-skip** — write/read for a future month is rejected
  (defensive against caller bugs).

Trades are stored in UTC (not station-local time) because trade
timestamps come from the exchange's clock and have no station / weather
locality. The "current month" predicate is therefore UTC, not LST.

Issuer + ticker components are aggressively validated to prevent path
traversal (a crafted ticker like ``../../etc/passwd`` would otherwise
escape the cache root).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

logger = logging.getLogger(__name__)


CACHE_VERSION: str = "v1"
DEFAULT_ROOT: Path = Path.home() / ".tradewinds" / "cache"
LOCK_TIMEOUT_SECONDS: int = 30


#: Allowlist for the ``issuer`` segment in the cache path. Lowercase alphanum
#: plus ``.``, ``-``, ``_``. Limited to 32 chars (current issuers: ``kalshi``,
#: ``polymarket``; future possibilities like ``predictit`` / ``manifold`` all
#: fit). Must start with a letter.
_ISSUER_RE = re.compile(r"^[a-z][a-z0-9._-]{0,31}$")


#: Allowlist for the ``ticker`` segment. Permits the character classes that
#: real Kalshi (``KXHIGHNY-25MAY26-T79``) and Polymarket
#: (``0x...condition-id``) tickers use. Capped at 128 chars to bound the
#: filesystem path length on Windows (260-char default).
_TICKER_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _cache_root() -> Path:
    override = os.environ.get("TRADEWINDS_CACHE_DIR")
    return Path(override) if override else DEFAULT_ROOT


def trades_cache_path(issuer: str, ticker: str, year: int, month: int) -> Path:
    """Return the canonical cache path for a (issuer, ticker, year, month).

    Validates each segment against an allowlist; raises ``ValueError`` on
    anything that could enable path traversal or escape the cache root.

    Args:
        issuer: Lowercase issuer name (``"kalshi"`` / ``"polymarket"``).
        ticker: Market ticker / id.
        year: Calendar year (2000-2100).
        month: Calendar month (1-12).

    Returns:
        ``Path`` to the parquet file (may not exist).

    Raises:
        ValueError: invalid issuer / ticker / year / month, OR the
            computed path escapes the cache root.
    """
    if not isinstance(issuer, str) or not _ISSUER_RE.match(issuer):
        raise ValueError(
            f"invalid issuer for cache path: {issuer!r}; "
            f"must match {_ISSUER_RE.pattern}"
        )
    if not isinstance(ticker, str) or not _TICKER_RE.match(ticker):
        raise ValueError(
            f"invalid ticker for cache path: {ticker!r}; "
            f"must match {_TICKER_RE.pattern}"
        )
    if not isinstance(year, int) or not (2000 <= year <= 2100):
        raise ValueError(f"year out of range [2000, 2100]: {year!r}")
    if not isinstance(month, int) or not (1 <= month <= 12):
        raise ValueError(f"month out of range [1, 12]: {month!r}")

    root = _cache_root()
    candidate = (
        root / CACHE_VERSION / "trades" / issuer / ticker / f"{year:04d}-{month:02d}.parquet"
    )
    # Defense-in-depth: even with the regex allowlists, resolve the path and
    # confirm it stays under the cache root. Catches edge cases like symlink
    # cache roots + crafted relative segments the allowlist regex would
    # otherwise let through.
    try:
        resolved = candidate.resolve()
        root_resolved = root.resolve()
    except OSError as exc:
        raise ValueError(f"failed to resolve cache path {candidate}: {exc}") from exc
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"cache path escapes root: {resolved} not under {root_resolved}"
        ) from exc
    return candidate


def _is_current_utc_month(year: int, month: int, *, now: datetime | None = None) -> bool:
    """True when (year, month) is the active UTC calendar month."""
    n = now if now is not None else datetime.now(UTC)
    return year == n.year and month == n.month


def _is_future_utc_month(year: int, month: int, *, now: datetime | None = None) -> bool:
    """True when (year, month) is in the future relative to UTC now."""
    n = now if now is not None else datetime.now(UTC)
    return (year, month) > (n.year, n.month)


def read_trades_cache(
    issuer: str,
    ticker: str,
    year: int,
    month: int,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]] | None:
    """Read cached parquet rows for the (issuer, ticker, year, month).

    Returns ``None`` when:
    - the file does not exist,
    - the (year, month) is the current UTC month (mutable),
    - the (year, month) is in the future, OR
    - the parquet read fails (logged + swallowed; treat as cache miss).

    Args:
        now: Override wall-clock for tests. Defaults to ``datetime.now(UTC)``.
    """
    if _is_current_utc_month(year, month, now=now) or _is_future_utc_month(
        year, month, now=now
    ):
        return None
    path = trades_cache_path(issuer, ticker, year, month)
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        return table.to_pylist()
    except Exception:
        logger.warning(
            "trades cache read failed for %s; treating as miss",
            path,
            exc_info=True,
        )
        return None


def write_trades_cache(
    issuer: str,
    ticker: str,
    year: int,
    month: int,
    rows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> bool:
    """Atomically write ``rows`` to the cache for (issuer, ticker, year, month).

    No-op (returns False) when:
    - ``rows`` is empty,
    - the (year, month) is the current UTC month (still mutable),
    - the (year, month) is in the future.

    Returns True on a successful write, False on any no-op condition.

    Args:
        now: Override wall-clock for tests.
    """
    if _is_current_utc_month(year, month, now=now) or _is_future_utc_month(
        year, month, now=now
    ):
        return False
    if not rows:
        return False

    import pyarrow as pa
    import pyarrow.parquet as pq

    path = trades_cache_path(issuer, ticker, year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock", timeout=LOCK_TIMEOUT_SECONDS)
    with lock:
        table = pa.Table.from_pylist(rows)
        tmp = path.with_suffix(path.suffix + ".tmp")
        pq.write_table(table, tmp, version="2.6", coerce_timestamps="us")
        os.replace(tmp, path)
    return True


def invalidate_trades(issuer: str, ticker: str, year: int, month: int) -> bool:
    """Delete the cached parquet (if present). Returns True when a file was removed."""
    path = trades_cache_path(issuer, ticker, year, month)
    if path.exists():
        path.unlink()
        return True
    return False


__all__ = [
    "CACHE_VERSION",
    "DEFAULT_ROOT",
    "invalidate_trades",
    "read_trades_cache",
    "trades_cache_path",
    "write_trades_cache",
]
