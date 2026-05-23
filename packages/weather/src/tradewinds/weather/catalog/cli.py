"""NWS CLI settlement adapter (CATALOG-03).

Wraps :func:`tradewinds.weather._climate.parse_cli_record` (and
``parse_cli_response``) into a class that satisfies the ``WeatherAdapter``
Protocol and emits a canonical ``schema.settlement.cli.v1`` DataFrame.

R3 mitigation (PLAN.md Task 4.3): the adapter carries the
``(station, observation_date)`` dedup logic lifted from
``monorepo-v0.14.1/src/mostlyright/pairs.py`` — strict-``>`` priority
between ``preliminary < final < correction`` with first-row-seen wins
at equal priority. Without this, multiple report-type rows for the same
local date would slip downstream and corrupt Kalshi NHIGH/NLOW settlement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar
from zoneinfo import ZoneInfo

import pandas as pd
from tradewinds.weather._climate import (
    REPORT_TYPE_PRIORITY,
    parse_cli_record,
    parse_cli_response,
)

#: Default station_tz for adapter callers that do not know the per-station
#: IANA zone. Production code should look up the real zone from a static
#: table; this is a sentinel that fails Validator if used unexpectedly.
_UTC_FALLBACK_TZ = "UTC"

#: Parser output (parse_cli_record / parse_cli_response) -> canonical
#: settlement schema field name. Parser keys differ from the canonical
#: column names; this mapping is the single source of truth.
_PROJECTION: dict[str, str] = {
    "station_code": "station",
    "observation_date": "observation_date",
    "report_type": "report_type",
    "high_temp_f": "temp_max_F",
    "low_temp_f": "temp_min_F",
    "precipitation_in": "precipitation_in",
    "snowfall_in": "snowfall_in",
    # parse_cli_record emits issued_at (ISO string). Canonical column is
    # product_release_time per docs/design.md §BB.3.
    "issued_at": "product_release_time",
}


class CLIAdapter:
    """NWS CLI settlement adapter."""

    SUPPORTED_SOURCES: ClassVar[list[str]] = ["cli.archive", "cli.live"]

    def fetch_observations(
        self,
        source: str,
        station: str,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        """Phase 3 Mode-2 entry point. v0.1: NotImplementedError."""
        raise NotImplementedError(
            "CLIAdapter.fetch_observations is the Phase 3 Mode-2 entry point. "
            "v0.1 callers should use tradewinds.research() (Mode 1 parity)."
        )

    @staticmethod
    def from_records(
        records: list[dict[str, object]],
        *,
        source: str = "cli.archive",
        station_tz: str = _UTC_FALLBACK_TZ,
        retrieved_at: datetime | None = None,
    ) -> pd.DataFrame:
        """Project parsed CLI records to a canonical settlement DataFrame.

        Applies the v0.14.1 ``(station, observation_date)`` dedup:
        strict-``>`` priority by ``REPORT_TYPE_PRIORITY`` with first-row-seen
        wins at equal priority. The adapter never silently merges across
        stations.

        Args:
            records: List of dicts as returned by :func:`parse_cli_record`.
            source: Source ID for ``df.attrs["source"]``.
            station_tz: IANA timezone name. Required for ``event_time``
                (00:00 local on observation_date → UTC). Default ``"UTC"``
                is a sentinel — production code MUST pass the real zone.
            retrieved_at: Wall-clock UTC of the pull. Defaults to ``now()``.

        Returns:
            DataFrame conforming to ``schema.settlement.cli.v1`` (12 columns)
            plus overlay columns (``source``, ``retrieved_at``, ``knowledge_time``,
            ``event_time``).
        """
        if retrieved_at is None:
            retrieved_at = datetime.now(UTC)
        # Defensive: reject naive retrieved_at (cryptic pandas error otherwise).
        if retrieved_at.tzinfo is None:
            raise ValueError(
                "retrieved_at must be a tz-aware datetime; "
                f"got naive {retrieved_at!r}. Attach a tzinfo before calling."
            )
        if source not in CLIAdapter.SUPPORTED_SOURCES:
            raise ValueError(
                f"CLIAdapter does not support source={source!r}; "
                f"supported: {CLIAdapter.SUPPORTED_SOURCES}"
            )

        # Dedup: by (station, observation_date), keep the strictly highest
        # report_type priority; ties resolved first-row-seen.
        deduped: dict[tuple[str, object], dict[str, object]] = {}
        for row in records:
            station = row.get("station_code")
            obs_date = row.get("observation_date")
            if station is None or obs_date is None:
                continue
            key = (station, obs_date)
            rtype = row.get("report_type", "preliminary")
            new_prio = REPORT_TYPE_PRIORITY.get(str(rtype), 0)
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = row
            else:
                old_prio = REPORT_TYPE_PRIORITY.get(
                    str(existing.get("report_type", "preliminary")), 0
                )
                if new_prio > old_prio:
                    deduped[key] = row
                # equal priority → keep existing (first-row-seen)

        if not deduped:
            df = _empty_settlement_df()
        else:
            projected = []
            for row in deduped.values():
                p: dict[str, object] = {}
                for src_k, dst_k in _PROJECTION.items():
                    p[dst_k] = row.get(src_k)
                projected.append(p)
            df = pd.DataFrame(projected)

        # Datatypes + overlay columns.
        # codex iter-6 HIGH fix: also coerce on the empty-DataFrame path so
        # zero-row pulls satisfy the Validator. Previously the
        # "if not df.empty" gate skipped these casts and the empty df
        # carried object/float64 dtypes that mismatched the schema.
        if not df.empty:
            df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce").dt.date
            df["product_release_time"] = pd.to_datetime(
                df["product_release_time"], utc=True, errors="coerce"
            )
        else:
            # Empty: ensure observation_date is a date-typed object series and
            # product_release_time is tz-aware datetime64 so Validator's date /
            # timestamp_utc checks succeed.
            df["observation_date"] = pd.Series([], dtype="object")
            df["product_release_time"] = pd.Series([], dtype="datetime64[ns, UTC]")

        # codex iter-5 HIGH fix: parse_cli_record emits int temps; the
        # canonical settlement schema declares float64. Coerce here so
        # adapter -> Validator integration succeeds.
        for col in ("temp_max_F", "temp_min_F", "precipitation_in", "snowfall_in"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        # string columns
        for col in ("station", "report_type", "cli_data_quality", "settlement_finality"):
            if col in df.columns:
                df[col] = df[col].astype("string")

        df["station_tz"] = station_tz
        # event_time = 00:00 station-local on observation_date → UTC.
        df["event_time"] = _event_time_from_date(df["observation_date"], station_tz)

        # cli_data_quality + settlement_finality: default to clean/final for
        # Phase 2 (Phase 3.4 QC engine populates the richer values).
        df["cli_data_quality"] = "clean"
        df["settlement_finality"] = (
            df.get("report_type", "preliminary")
            .map(
                {
                    "preliminary": "provisional",
                    "final": "final",
                    "correction": "final",
                }
            )
            .fillna("provisional")
        )

        df["source"] = source
        df["retrieved_at"] = pd.Timestamp(retrieved_at).tz_convert("UTC")
        # knowledge_time = product_release_time (canonical CLI semantics).
        df["knowledge_time"] = df["product_release_time"]
        df.attrs["source"] = source
        df.attrs["retrieved_at"] = retrieved_at
        return df


def _empty_settlement_df() -> pd.DataFrame:
    cols = [
        *list(_PROJECTION.values()),
        "station_tz",
        "event_time",
        "cli_data_quality",
        "settlement_finality",
        "source",
        "retrieved_at",
        "knowledge_time",
    ]
    return pd.DataFrame({c: [] for c in cols})


def _event_time_from_date(date_series: pd.Series, tz: str) -> pd.Series:
    """Convert observation_date (local date) to UTC midnight timestamp."""
    if date_series.empty:
        return pd.Series([], dtype="datetime64[ns, UTC]")
    zone = ZoneInfo(tz)
    out = []
    for d in date_series:
        if d is None or (isinstance(d, float) and d != d):
            out.append(pd.NaT)
            continue
        local = datetime(d.year, d.month, d.day, tzinfo=zone)
        out.append(local.astimezone(UTC))
    return pd.Series(pd.to_datetime(out, utc=True))


__all__ = ["CLIAdapter", "parse_cli_record", "parse_cli_response"]


from tradewinds.weather.catalog import register_adapter  # noqa: E402

for _sid in CLIAdapter.SUPPORTED_SOURCES:
    register_adapter(_sid, CLIAdapter)
