"""Parquet format — Arrow-backed lossless serialization.

Uses pyarrow as the engine and zstd compression. Lossless for the
schemas in this project (string, int, Int64 nullable, float, bool,
tz-aware Timestamp[ns, tz], object-of-strings).

Documented exceptions:

- pandas ``Categorical`` dtypes roundtrip as ``Categorical`` with
  ``pyarrow``'s dictionary encoding, but the category ``ordered`` flag
  is preserved while the underlying ``dtype`` may rebuild on read.
- pandas extension dtypes that pyarrow does not natively map (rare in
  the canonical schemas — see design doc §A) may degrade to their
  ``object`` representation.
- Object columns holding mixed Python types are written using
  pyarrow's best-effort type inference; columns mixing dicts/lists and
  primitives will raise at write time rather than silently coerce.

Decompression-bomb protection is NOT enforced in this layer — see the
docstring on ``loads`` and design doc §E. The MCP server layer applies
the per-payload uncompressed-size cap before invoking ``loads``.
"""

from __future__ import annotations

import io

import pandas as pd

__all__ = ["dumps", "loads"]


def dumps(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to a parquet byte payload.

    Engine: pyarrow. Compression: zstd. The full DataFrame schema —
    column names, dtypes (including nullable ``Int64``, ``boolean``,
    and tz-aware ``Timestamp``), and the index unless the caller drops
    it — is preserved on the wire.
    """
    buf = io.BytesIO()
    df.to_parquet(buf, engine="pyarrow", compression="zstd")
    return buf.getvalue()


def loads(data: bytes) -> pd.DataFrame:
    """Parse a parquet byte payload back into a DataFrame.

    Engine: pyarrow. No decompression-bomb protection at this layer —
    the MCP server enforces a per-payload uncompressed-size cap (1 GB
    default per design doc §E) before invoking this function, and the
    SDK caller is trusted to pass parquet they themselves produced.
    Adding a size cap here would push policy into the format layer; it
    lives at the trust boundary instead.
    """
    return pd.read_parquet(io.BytesIO(data), engine="pyarrow")
