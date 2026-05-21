"""Shared HTTP download helper with retry logic.

Used by both GHCNh and IEM download runners.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0
HTTP_TIMEOUT = 30.0
TRANSIENT_CODES = frozenset({500, 502, 503, 504})


def download_with_retry(url: str, dest: Path) -> None:
    """Download URL to dest with exponential backoff.

    404 raises immediately (permanent error).
    500/502/503/504 are retried up to MAX_RETRIES times.
    Writes to a .tmp file first, then atomic rename.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    delay = BASE_DELAY
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
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
            tmp.rename(dest)
            return
