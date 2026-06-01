"""Shared HTTP download helper with retry logic.

Used by both GHCNh and IEM download runners.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)


# GH #51: env-var overrides so batch callers can tune IEM 429 behavior
# without monkey-patching site-packages. Defaults are unchanged from prior
# releases; both vars apply process-wide at module load. Set on shell
# launch or in CI:
#   MOSTLYRIGHT_HTTP_MAX_RETRIES=1
#   MOSTLYRIGHT_HTTP_TIMEOUT=5.0
# Invalid values (non-numeric, negative) silently fall back to defaults
# so a typo in an env var never blocks legitimate fetches.
def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        log.warning("Ignoring non-integer %s=%r; using default %d", name, raw, default)
        return default
    if value < 0:
        log.warning("Ignoring negative %s=%r; using default %d", name, raw, default)
        return default
    return value


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        log.warning("Ignoring non-numeric %s=%r; using default %.1f", name, raw, default)
        return default
    if value <= 0:
        log.warning("Ignoring non-positive %s=%r; using default %.1f", name, raw, default)
        return default
    return value


MAX_RETRIES = _int_env("MOSTLYRIGHT_HTTP_MAX_RETRIES", 3)
BASE_DELAY = 1.0
# Phase 1.5 PERF-03 — PR #85 (commit cf9eb85) HIGH-2 round-2 finding:
# 12x larger payload-per-request after the IEM chunk bump (monthly -> 365-day).
# Pre-bump ASOS was ~150 KB/month (30s plenty); post-bump it's ~1.8 MB/year on
# the empirical KNYC sample. mostlyright note: AWC + GHCNh + CLI did NOT change
# payload size — the bump is conservative overhead for those endpoints, not
# load-bearing.
HTTP_TIMEOUT = _float_env("MOSTLYRIGHT_HTTP_TIMEOUT", 60.0)
# Retryable HTTP responses. 429 (Too Many Requests) is included because IEM
# ASOS rate-limits bursts of monthly downloads (12+ months x 2 report_types
# in quick succession is enough to trip it on a fresh cache). Without retry,
# research() silently swallows partial fetch failures and emits a degraded
# parity output - which is exactly what the Wave 3 HARD GATE caught when
# cache isolation was added. Codex iter-2 wave-3 follow-up.
TRANSIENT_CODES = frozenset({429, 500, 502, 503, 504})


def download_with_retry(url: str, dest: Path, *, client: httpx.Client | None = None) -> None:
    """Download URL to dest with exponential backoff.

    404 raises immediately (permanent error).
    429/500/502/503/504 are retried up to MAX_RETRIES times.
    Writes to a .tmp file first, then atomic rename.

    Phase 24-04: pass ``client`` to reuse a pooled :class:`httpx.Client`
    across many files (one TCP+TLS handshake instead of one per call). When
    ``client`` is provided the caller owns its lifecycle — the helper does
    NOT close it. When ``client`` is ``None`` a fresh client is created and
    closed per call (backward-compatible default).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if client is None:
        with httpx.Client(timeout=HTTP_TIMEOUT) as owned:
            _download_with_client(owned, url, dest)
    else:
        _download_with_client(client, url, dest)


def _download_with_client(client: httpx.Client, url: str, dest: Path) -> None:
    """Run the retry loop against ``client`` (does not close it)."""
    delay = BASE_DELAY
    for attempt in range(MAX_RETRIES):
        response = client.get(url)
        if response.status_code == 404:
            response.raise_for_status()
        if response.status_code in TRANSIENT_CODES:
            if attempt < MAX_RETRIES - 1:
                log.warning(
                    "HTTP %d for %s, retry %d/%d in %.1fs",
                    response.status_code,
                    url,
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
        response.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(response.content)
        # Rob H1: `os.replace` is atomic on both POSIX and Windows
        # (unlike `Path.rename`, which raises FileExistsError on
        # Windows when dest exists -- so `skip_cache=True` re-downloads
        # broke on Windows). Matches `cache.py::_atomic_write` style.
        os.replace(tmp, dest)
        return
