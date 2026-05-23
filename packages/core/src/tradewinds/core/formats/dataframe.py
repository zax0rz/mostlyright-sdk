"""DataFrame format — identity passthrough.

Exists so the format-dispatch layer (catalog adapters, MCP wire layer)
can call ``dumps`` / ``loads`` uniformly across every supported format.
A caller asking for ``format="dataframe"`` gets the DataFrame back
unchanged — no serialization, no copy, no validation.

Lossless by definition.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["dumps", "loads"]


def dumps(df: pd.DataFrame) -> pd.DataFrame:
    """Return the DataFrame unchanged.

    Provided for API symmetry with the other format modules. The caller
    receives the same object reference; callers that mutate must copy
    explicitly.
    """
    return df


def loads(df: pd.DataFrame) -> pd.DataFrame:
    """Return the DataFrame unchanged.

    Mirror of ``dumps`` for API symmetry. Accepts a DataFrame (not bytes
    or string) because the "dataframe" format is the in-memory form.
    """
    return df
