"""Phase 2.1 — read-time merge policy for silver-tier observation ledgers.

Silver-tier ledger schema (``schema.observation_ledger.v1``) carries one
row per ``(station, observed_at, source)`` — multiple rows per
``(station, observed_at)`` are valid (one per contributing source).
This module provides ``query_time_merge(silver_df, policy=LIVE_V1)``
that materializes the v0.14.1-equivalent single-row-per-key gold shape
for Mode-1 parity callers.

Policy ``LIVE_V1`` uses strict ``>`` priority on ``source_priority`` (AWC=3,
IEM=2, GHCNh=1; ``ncei`` reserved per D-2.1-09 but never written in v0.1.0).
Ties resolved by deterministic secondary key
``(source_received_at, ingestion_id)``.

See ``.planning/phases/02.1-sprint-2o-lineage-refactor-per-source-provenance/02.1-PLAN-02-merge-policy-port.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    import pandas as pd


__all__ = [
    "LIVE_V1",
    "ObservationMergePolicy",
    "query_time_merge",
]


@dataclass(frozen=True)
class ObservationMergePolicy:
    """Read-time merge policy for silver-tier observation ledger.

    Frozen at the dataclass level AND at the source_priority value level
    (codex Phase 2.1 review HIGH: a frozen dataclass with a mutable dict
    attribute is not actually immutable — callers could mutate
    LIVE_V1.source_priority at runtime and globally change merge results).
    Construction wraps any input dict in MappingProxyType for read-only
    enforcement.
    """

    name: str
    source_priority: Mapping[str, int]
    secondary_key: tuple[str, ...] = field(default=("source_received_at", "ingestion_id"))

    #: Strict ">" priority comparison — first-row-seen wins at equal priority,
    #: secondary key breaks ties deterministically.
    STRICT_PRIORITY: ClassVar[bool] = True

    def __post_init__(self) -> None:
        # Wrap source_priority in MappingProxyType so the policy is truly
        # immutable. Use object.__setattr__ because the dataclass is frozen.
        if not isinstance(self.source_priority, MappingProxyType):
            object.__setattr__(
                self, "source_priority", MappingProxyType(dict(self.source_priority))
            )

    def apply(self, silver_df: pd.DataFrame) -> pd.DataFrame:
        """Materialize gold (single-row-per-(station, observed_at)) from silver."""
        return query_time_merge(silver_df, policy=self)


#: Canonical Mode-1 parity policy — AWC > IEM > GHCNh; ncei reserved.
LIVE_V1 = ObservationMergePolicy(
    name="LIVE_V1",
    source_priority={"awc": 3, "iem": 2, "ghcnh": 1, "ncei": 0},
)


def query_time_merge(
    silver_df: pd.DataFrame,
    *,
    policy: ObservationMergePolicy = LIVE_V1,
) -> pd.DataFrame:
    """Materialize gold shape from silver-tier ledger.

    The silver-tier ``schema.observation_ledger.v1`` carries one row per
    ``(station, observed_at, source)``. This function applies
    ``policy.source_priority`` with strict ``>`` to keep only the
    highest-priority source per ``(station_code, observed_at)`` key,
    using the policy's ``secondary_key`` for deterministic tiebreaks.

    Args:
        silver_df: DataFrame conforming to ``schema.observation_ledger.v1``.
            MUST carry ``station_code``, ``observed_at``, ``source`` columns.
        policy: Merge policy (default ``LIVE_V1``).

    Returns:
        DataFrame with one row per ``(station_code, observed_at)`` — the
        v0.14.1-equivalent gold shape Mode-1 parity callers expect.
    """

    if silver_df.empty:
        return silver_df.copy()

    required = {"station_code", "observed_at", "source"}
    missing = required - set(silver_df.columns)
    if missing:
        raise ValueError(
            f"silver_df missing required columns {missing}; got columns {list(silver_df.columns)}"
        )

    # Assign per-row priority from policy.
    df = silver_df.copy()
    df["__priority"] = df["source"].map(policy.source_priority).fillna(-1).astype(int)

    # Sort by (key, priority DESC, secondary_key ASC) — first row per key wins.
    secondary_cols = [c for c in policy.secondary_key if c in df.columns]
    sort_cols = ["station_code", "observed_at", "__priority", *secondary_cols]
    sort_asc = [True, True, False] + [True] * len(secondary_cols)
    df = df.sort_values(sort_cols, ascending=sort_asc, kind="mergesort")

    # Strict > priority: drop_duplicates keeps the first occurrence per key
    # (which is now the highest-priority + deterministic-tiebreak row).
    gold = df.drop_duplicates(subset=["station_code", "observed_at"], keep="first")

    # Surface provenance columns even on the gold shape (so Mode 2 callers
    # can inspect which source won each key).
    gold = gold.drop(columns=["__priority"], errors="ignore").reset_index(drop=True)

    # Preserve df.attrs from input.
    gold.attrs.update(silver_df.attrs)
    return gold
