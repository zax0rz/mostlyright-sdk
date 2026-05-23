"""Format converters for DataFrame interchange.

One ``dumps`` / ``loads`` pair per supported format. The dispatch layer
(catalog adapters, MCP wire layer) selects a format module and calls
its functions uniformly.

Supported formats:

- ``dataframe`` — identity passthrough (lossless by definition).
- ``parquet`` — Arrow-backed binary, lossless for canonical schemas.
- ``json`` — records-oriented string; lossy on dtype.
- ``csv`` — pandas-native string; lossy on dtype and null vs empty.
- ``toon`` — TOON v3.0 string; lossy per design doc §I.

See each submodule's docstring for the full loss matrix.
"""

from __future__ import annotations

from .csv import dumps as csv_dumps
from .csv import loads as csv_loads
from .dataframe import dumps as df_dumps
from .dataframe import loads as df_loads
from .json import dumps as json_dumps
from .json import loads as json_loads
from .parquet import dumps as parquet_dumps
from .parquet import loads as parquet_loads
from .toon import dumps as toon_dumps
from .toon import loads as toon_loads

__all__ = [
    "csv_dumps",
    "csv_loads",
    "df_dumps",
    "df_loads",
    "json_dumps",
    "json_loads",
    "parquet_dumps",
    "parquet_loads",
    "toon_dumps",
    "toon_loads",
]
