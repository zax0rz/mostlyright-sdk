"""Shared HTTP session for SDK API clients."""

from __future__ import annotations

import importlib.metadata
import re
import warnings
from pathlib import Path
from typing import Any

import httpx

from tradewinds._internal.config import TherminalConfig
from tradewinds._internal.exceptions import (
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TherminalError,
    ValidationError,
)

# PEP 440 version strings are alnum + ``.-+~!``. Stripping to this character
# set before the User-Agent f-string below blocks CRLF injection and any
# other header-smuggling attempt from adversarial ``METADATA`` files
# shadowing a genuine ``mostlyright`` dist in the installed venv.
_VERSION_SAFE_CHARS = re.compile(r"[^A-Za-z0-9.\-+~!]")


def _resolve_version() -> str:
    """Return the installed mostlyright version, or 'dev' when running from source.

    Reading from ``importlib.metadata`` instead of hard-coding a constant
    avoids the historical drift where the ``_VERSION`` string lagged the
    actual package version on every release. The result is whitelisted to
    PEP 440 safe characters so an adversary who can drop a METADATA file
    cannot smuggle CRLF into our User-Agent header.
    """
    try:
        raw = importlib.metadata.version("mostlyright")
    except importlib.metadata.PackageNotFoundError:
        return "dev"
    cleaned = _VERSION_SAFE_CHARS.sub("", raw)
    return cleaned or "dev"


_VERSION = _resolve_version()


class HttpSession:
    """Shared HTTP session for API clients. Composition, not inheritance."""

    def __init__(self, config: TherminalConfig | None = None) -> None:
        self._config = config or TherminalConfig()
        self._client = httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            headers={
                "User-Agent": f"mostlyright-py/{_VERSION}",
            },
        )

    @property
    def config(self) -> TherminalConfig:
        return self._config

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpSession:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET request, return parsed JSON."""
        cleaned = {k: v for k, v in (params or {}).items() if v is not None}
        resp = self._client.get(path, params=cleaned)
        _raise_for_status(resp)
        return resp.json()

    def get_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_size: int = 10000,
        max_rows: int = 500000,
    ) -> list[dict[str, Any]]:
        """GET with auto-pagination. Fetches all pages until exhausted."""
        cleaned = {k: v for k, v in (params or {}).items() if v is not None}

        caller_limit = int(cleaned.get("limit", max_rows))
        effective_max = min(caller_limit, max_rows)
        cleaned["limit"] = min(page_size, effective_max)
        cleaned.setdefault("offset", 0)

        all_rows: list[dict[str, Any]] = []
        while len(all_rows) < effective_max:
            resp = self._client.get(path, params=cleaned)
            _raise_for_status(resp)
            page = resp.json()
            if not isinstance(page, list):
                break
            all_rows.extend(page)
            if len(page) < cleaned["limit"]:
                break
            cleaned["offset"] += len(page)

        if len(all_rows) >= max_rows:
            warnings.warn(
                f"Result truncated at {max_rows} rows. Use format='parquet' for bulk downloads.",
                stacklevel=2,
            )
        return all_rows

    def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        """GET request, return raw bytes."""
        cleaned = {k: v for k, v in (params or {}).items() if v is not None}
        resp = self._client.get(path, params=cleaned)
        _raise_for_status(resp)
        return resp.content

    def handle_format(
        self,
        path: str,
        params: dict[str, Any],
        fmt: str | None,
        columns: list[str] | None,
        as_dataframe: bool,
        index_col: str | None,
        default_filename: str,
        save_path: str | Path | None,
    ) -> list[dict[str, Any]] | Path | Any:
        """Route format=csv|parquet to file download."""
        if columns:
            params["columns"] = ",".join(columns)

        if fmt in ("csv", "parquet"):
            params["format"] = fmt
            content = self.get_bytes(path, params)

            if save_path is None:
                ext = "csv" if fmt == "csv" else "parquet"
                resolved_path = Path(f"{default_filename}.{ext}")
            else:
                resolved_path = Path(save_path)

            resolved_path.write_bytes(content)

            if as_dataframe and fmt == "parquet":
                try:
                    import pyarrow.parquet as pq
                except ImportError:
                    raise ImportError(
                        "pyarrow is required to load parquet files. "
                        "Install with: pip install mostlyright[parquet]"
                    ) from None
                import pandas as pd  # type: ignore[import-not-found]

                df = pq.read_table(resolved_path).to_pandas()
                return _apply_datetime_index(df, index_col)

            if as_dataframe and fmt == "csv":
                try:
                    import pandas as pd  # type: ignore[import-not-found]
                except ImportError:
                    raise ImportError(
                        "pandas is required for DataFrame output. "
                        "Install with: pip install mostlyright[parquet]"
                    ) from None
                return pd.read_csv(resolved_path)

            return resolved_path

        msg = f"handle_format called with fmt={fmt!r}, expected 'csv' or 'parquet'"
        raise ValueError(msg)


def _raise_for_status(resp: httpx.Response) -> None:
    """Map HTTP error responses to typed SDK exceptions."""
    if resp.is_success:
        return

    ct = resp.headers.get("content-type", "")
    try:
        body = resp.json() if ct.startswith("application/json") else {}
    except (ValueError, KeyError):
        body = {}
    msg = body.get("error", resp.text) if isinstance(body, dict) else resp.text

    if resp.status_code == 404:
        raise NotFoundError(msg)
    if resp.status_code == 429:
        try:
            retry = int(resp.headers.get("Retry-After", "1"))
        except (ValueError, TypeError):
            retry = 1
        raise RateLimitError(retry_after=retry)
    if resp.status_code == 400:
        raise ValidationError(msg)
    if resp.status_code == 401:
        raise AuthenticationError(msg)
    if resp.status_code == 403:
        raise ForbiddenError(msg)
    if resp.status_code >= 500:
        raise ServerError(msg, status_code=resp.status_code)
    raise TherminalError(msg, status_code=resp.status_code)


def to_dataframe(data: list[dict[str, Any]], index_col: str | None = None) -> Any:
    """Convert list of dicts to a Pandas DataFrame."""
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError:
        raise ImportError(
            "pandas is required for DataFrame output. "
            "Install with: pip install mostlyright[parquet]"
        ) from None

    df = pd.DataFrame(data)
    return _apply_datetime_index(df, index_col)


def _apply_datetime_index(df: Any, index_col: str | None) -> Any:
    """Set a datetime column as the DataFrame index."""
    if not index_col or index_col not in df.columns:
        return df
    import pandas as pd  # type: ignore[import-not-found]

    col = df[index_col]
    if pd.api.types.is_numeric_dtype(col):
        return df.set_index(index_col).sort_index()

    raw = col.astype(str)
    max_len = raw.str.len().max()
    is_date_only = pd.isna(max_len) or max_len <= 10
    if is_date_only:  # noqa: SIM108 — byte-faithful lift from mostlyright==0.14.1
        converted = pd.to_datetime(raw)
    else:
        converted = pd.to_datetime(raw, utc=True)
    return df.assign(**{index_col: converted}).set_index(index_col).sort_index()


def normalize_date(date_str: str | None) -> str | None:
    """Normalize date strings. Append T00:00:00Z if only YYYY-MM-DD."""
    if date_str is None:
        return None
    if len(date_str) == 10 and "T" not in date_str:
        return f"{date_str}T00:00:00Z"
    return date_str
