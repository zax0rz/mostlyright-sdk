"""TradewindsResult — backend-neutral provenance wrapper.

Phase 6 (v0.2+) deliverable. Polars frames have no ``.attrs``, so the
v0.1.0 pattern of stamping ``df.attrs["source"]`` / ``df.attrs["retrieved_at"]``
cannot survive the polars backend. ``TradewindsResult`` carries the
provenance separately from the frame so both pandas and polars callers
preserve source-identity invariants without ``.attrs`` writes.

Validator, KnowledgeView, and LeakageDetector accept either a raw
DataFrame (legacy v0.1.0 path) OR a ``TradewindsResult`` (new v0.2 path);
the wrapper-aware dispatch unwraps via :meth:`frame_as_pandas` and the
existing validation logic runs unchanged.

See PLAN.md Wave 0 + CONTEXT.md "User Decisions" §2 and §7.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

    from tradewinds.discovery import DataVersion

    FrameLike = pd.DataFrame | pl.DataFrame
else:
    FrameLike = Any


__all__ = ["TradewindsResult"]


@dataclass(frozen=True)
class TradewindsResult:
    """Backend-neutral provenance wrapper for a DataFrame-returning call.

    Both pandas-backend and polars-backend adapters return the same
    wrapper shape. ``frame`` holds the native frame; the remaining fields
    carry the provenance that v0.1.0 used to stamp on ``df.attrs``.

    Attributes:
        frame: The underlying DataFrame (pandas OR polars). Optional polars
            type is type-hinted via ``TYPE_CHECKING`` so default install
            does not require polars.
        source: The canonical source identifier (e.g. ``"iem.live"``,
            ``"awc.live"``, ``"noaa_bdp"``). Mirrors the v0.1.0
            ``df.attrs["source"]`` contract.
        retrieved_at: UTC timestamp of the fetch. MUST be tz-aware.
        schema_id: Optional canonical schema ID (e.g.
            ``"schema.observation.v1"``). ``None`` if the call returns
            heterogeneous rows (e.g. ``research()`` pairs).
        qc: Optional QC summary (rules_fired counts, sidecar_paths) if the
            caller invoked ``qc=True``. Mirrors ``df.attrs["qc"]``.
        data_version: Optional ``DataVersion`` token for reproducibility.

    Examples:
        >>> import pandas as pd
        >>> from datetime import datetime, timezone
        >>> from tradewinds.core.result import TradewindsResult
        >>> df = pd.DataFrame({"date": ["2025-01-01"], "value": [42]})
        >>> result = TradewindsResult(
        ...     frame=df,
        ...     source="iem.live",
        ...     retrieved_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ... )
        >>> result.source
        'iem.live'
        >>> result.frame_as_pandas().iloc[0]["value"]
        42
    """

    frame: FrameLike
    source: str
    retrieved_at: datetime
    schema_id: str | None = None
    qc: dict[str, Any] | None = None
    data_version: DataVersion | None = field(default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source:
            raise ValueError(
                f"TradewindsResult.source must be a non-empty string; "
                f"got {type(self.source).__name__}={self.source!r}"
            )
        if not isinstance(self.retrieved_at, datetime):
            raise TypeError(
                f"TradewindsResult.retrieved_at must be a datetime; "
                f"got {type(self.retrieved_at).__name__}"
            )
        if self.retrieved_at.tzinfo is None:
            raise ValueError(
                "TradewindsResult.retrieved_at must be tz-aware; "
                "naive datetimes are rejected to match schema.py tz discipline."
            )

    def frame_as_pandas(self) -> pd.DataFrame:
        """Return the underlying frame as a pandas DataFrame.

        Pandas frames pass through unchanged. Polars frames are converted
        via ``pl.DataFrame.to_pandas()``. Parity-locked modules call this
        before running their pandas-only pipelines (Phase 6 PLAN.md W4-T1).

        Polars→pandas conversion may shift datetime resolution (``us → ns``
        on the v0.1.0 contract path) and may change nullable-int storage.
        Callers that need byte-equivalent round-trip across backends MUST
        consult the documented coercion rules in
        ``tests/fixtures/parity/coerce_pd3.py``.
        """
        import pandas as pd

        if isinstance(self.frame, pd.DataFrame):
            return self.frame

        try:
            import polars as pl
        except ImportError as exc:  # pragma: no cover - defensive
            raise ImportError(
                "TradewindsResult.frame_as_pandas() requires polars to be "
                "installed when wrapping a polars DataFrame. Install with: "
                "pip install tradewinds[polars]"
            ) from exc

        if isinstance(self.frame, pl.DataFrame):
            return self.frame.to_pandas()
        raise TypeError(
            f"TradewindsResult.frame must be a pandas or polars DataFrame; "
            f"got {type(self.frame).__name__}"
        )

    def legacy_df_with_attrs(self) -> pd.DataFrame:
        """Return the wrapped pandas DataFrame with ``df.attrs`` populated.

        Mirrors the v0.1.0 ``df.attrs``-stamped shape that catalog adapters
        produced: ``attrs["source"]``, ``attrs["retrieved_at"]`` (ISO
        string), and ``attrs["qc"]`` / ``attrs["data_version"]`` when set.
        For callers that still consume ``df.attrs["source"]`` directly
        instead of the wrapper, this method bridges the legacy expectation
        for one release cycle (strict deprecation lands in v0.3).

        Raises:
            TypeError: if the wrapped frame is polars — the legacy shape
                was pandas-only by definition.
        """
        import pandas as pd

        if not isinstance(self.frame, pd.DataFrame):
            raise TypeError(
                "legacy_df_with_attrs() requires a pandas-backed frame; "
                "polars frames have no df.attrs. Use frame_as_pandas() to "
                "convert first, or migrate the consumer to read the "
                "TradewindsResult fields directly."
            )

        df = self.frame.copy()
        df.attrs["source"] = self.source
        df.attrs["retrieved_at"] = self.retrieved_at.isoformat()
        if self.qc is not None:
            df.attrs["qc"] = self.qc
        if self.data_version is not None:
            df.attrs["data_version"] = self.data_version.token
        if self.schema_id is not None:
            df.attrs["schema_id"] = self.schema_id
        return df

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict representation for v0.2 MCP JSON-RPC serialization.

        Excludes the frame body — callers that need to ship rows over MCP
        should serialize the frame via ``tradewinds.core.formats.*`` writers
        and attach the provenance via this method's output.
        """
        out: dict[str, Any] = {
            "source": self.source,
            "retrieved_at": self.retrieved_at.isoformat(),
        }
        if self.schema_id is not None:
            out["schema_id"] = self.schema_id
        if self.qc is not None:
            out["qc"] = self.qc
        if self.data_version is not None:
            out["data_version"] = self.data_version.token
        return out
