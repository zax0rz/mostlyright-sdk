"""Unit tests for the Schema base class, ColumnSpec, and SchemaRegistration."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta, timezone
from typing import ClassVar

import pytest
from tradewinds._v02.schema import (
    ColumnSpec,
    Schema,
    SchemaRegistration,
)

# ---------------------------------------------------------------------------
# ColumnSpec construction
# ---------------------------------------------------------------------------


class TestColumnSpecConstruction:
    def test_minimal_string_column(self) -> None:
        spec = ColumnSpec(
            name="station", dtype="string", units=None, nullable=False
        )
        assert spec.name == "station"
        assert spec.dtype == "string"
        assert spec.units is None
        assert spec.nullable is False
        assert spec.enum_values is None
        assert spec.notes == ""

    def test_float_with_units(self) -> None:
        spec = ColumnSpec(
            name="temp_c",
            dtype="float64",
            units="celsius",
            nullable=True,
            notes="bounded",
        )
        assert spec.units == "celsius"
        assert spec.notes == "bounded"

    def test_enum_column_requires_values(self) -> None:
        spec = ColumnSpec(
            name="kind",
            dtype="enum",
            units=None,
            nullable=False,
            enum_values=("A", "B"),
        )
        assert spec.enum_values == ("A", "B")

    def test_frozen_dataclass(self) -> None:
        spec = ColumnSpec(
            name="x", dtype="string", units=None, nullable=False
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.name = "y"  # type: ignore[misc]

    def test_invalid_dtype_raises(self) -> None:
        with pytest.raises(ValueError, match="not a canonical dtype"):
            ColumnSpec(name="x", dtype="binary", units=None, nullable=True)

    def test_enum_without_values_raises(self) -> None:
        with pytest.raises(ValueError, match="requires non-empty enum_values"):
            ColumnSpec(name="x", dtype="enum", units=None, nullable=False)

    def test_enum_with_empty_tuple_raises(self) -> None:
        with pytest.raises(ValueError, match="requires non-empty enum_values"):
            ColumnSpec(
                name="x",
                dtype="enum",
                units=None,
                nullable=False,
                enum_values=(),
            )

    def test_non_enum_with_enum_values_raises(self) -> None:
        with pytest.raises(ValueError, match="only valid for dtype='enum'"):
            ColumnSpec(
                name="x",
                dtype="string",
                units=None,
                nullable=False,
                enum_values=("A",),
            )

    def test_all_canonical_dtypes_accepted(self) -> None:
        # Every dtype in the canonical set should construct cleanly.
        dtypes = [
            "string",
            "float64",
            "int64",
            "timestamp_utc",
            "date",
            "bool",
        ]
        for dtype in dtypes:
            ColumnSpec(name="x", dtype=dtype, units=None, nullable=True)


# ---------------------------------------------------------------------------
# Toy schema for base-class behaviour
# ---------------------------------------------------------------------------


class _ToySchema(Schema):
    schema_id = "test.toy.v1"
    COLUMNS: ClassVar[list[ColumnSpec]] = [
        ColumnSpec(name="station", dtype="string", units=None, nullable=False),
        ColumnSpec(
            name="event_time",
            dtype="timestamp_utc",
            units=None,
            nullable=False,
        ),
        ColumnSpec(
            name="temp_c", dtype="float64", units="celsius", nullable=True
        ),
    ]
    IMPERIAL_RENAMES: ClassVar[dict[str, str]] = {
        "event_time": "utc_datetime",
        "temp_c": "temp_F",
    }


class _ToySchemaNoRenames(Schema):
    schema_id = "test.toy_no_renames.v1"
    COLUMNS: ClassVar[list[ColumnSpec]] = [
        ColumnSpec(name="a", dtype="string", units=None, nullable=False),
        ColumnSpec(name="b", dtype="int64", units=None, nullable=True),
    ]
    # No IMPERIAL_RENAMES override — falls back to the class default ({}).


# ---------------------------------------------------------------------------
# Schema.column_names + Schema.column
# ---------------------------------------------------------------------------


class TestColumnNames:
    def test_metric_mode_default(self) -> None:
        assert _ToySchema.column_names() == ["station", "event_time", "temp_c"]

    def test_metric_mode_explicit(self) -> None:
        assert _ToySchema.column_names("metric") == [
            "station",
            "event_time",
            "temp_c",
        ]

    def test_imperial_mode_applies_renames(self) -> None:
        assert _ToySchema.column_names("imperial") == [
            "station",
            "utc_datetime",
            "temp_F",
        ]

    def test_imperial_mode_with_no_renames_equals_metric(self) -> None:
        assert _ToySchemaNoRenames.column_names(
            "imperial"
        ) == _ToySchemaNoRenames.column_names("metric")

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode must be"):
            _ToySchema.column_names("kelvin")

    def test_column_lookup_hit(self) -> None:
        spec = _ToySchema.column("temp_c")
        assert spec.name == "temp_c"
        assert spec.dtype == "float64"
        assert spec.units == "celsius"

    def test_column_lookup_miss(self) -> None:
        with pytest.raises(KeyError, match="no column named"):
            _ToySchema.column("nonexistent")


# ---------------------------------------------------------------------------
# Schema.register + SchemaRegistration audit log
# ---------------------------------------------------------------------------


_TS = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)


class TestSchemaRegister:
    def test_register_returns_registration(self) -> None:
        reg = _ToySchema.register(
            source="iem.archive", retrieved_at=_TS, rows=42
        )
        assert isinstance(reg, SchemaRegistration)
        assert reg.schema is _ToySchema
        assert reg.source == "iem.archive"
        assert reg.rows == 42
        assert reg.retrieved_at_min == _TS
        assert reg.retrieved_at_max == _TS

    def test_register_appends_registered_event(self) -> None:
        reg = _ToySchema.register(
            source="iem.archive", retrieved_at=_TS, rows=42
        )
        log = reg.audit_log()
        assert len(log) == 1
        entry = log[0]
        assert entry["event"] == "registered"
        assert entry["source"] == "iem.archive"
        assert entry["rows"] == 42
        assert entry["ts"] == _TS.isoformat()

    def test_register_timestamp_is_tz_aware(self) -> None:
        reg = _ToySchema.register(
            source="awc.live", retrieved_at=_TS, rows=1
        )
        # Stored timestamps should preserve their tzinfo.
        assert reg.retrieved_at_min.tzinfo is not None
        assert reg.retrieved_at_max.tzinfo is not None

    def test_register_rejects_naive_datetime(self) -> None:
        naive = datetime(2026, 5, 21, 12, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            _ToySchema.register(
                source="iem.archive", retrieved_at=naive, rows=1
            )

    def test_register_rejects_non_datetime(self) -> None:
        with pytest.raises(TypeError, match="must be a datetime"):
            _ToySchema.register(
                source="iem.archive",
                retrieved_at="2026-05-21T12:00:00Z",  # type: ignore[arg-type]
                rows=1,
            )

    def test_register_accepts_non_utc_tz(self) -> None:
        # tzinfo other than UTC is still tz-aware; we accept it.
        eastern = timezone(timedelta(hours=-5))
        ts_et = datetime(2026, 5, 21, 7, 0, 0, tzinfo=eastern)
        reg = _ToySchema.register(
            source="iem.archive", retrieved_at=ts_et, rows=1
        )
        assert reg.retrieved_at_min == ts_et

    def test_register_normalises_retrieved_at_to_utc(self) -> None:
        # Non-UTC offsets get normalised so the stored range and audit
        # ISO strings are timezone-consistent.
        eastern = timezone(timedelta(hours=-5))
        ts_et = datetime(2026, 5, 21, 7, 0, 0, tzinfo=eastern)
        reg = _ToySchema.register(
            source="iem.archive", retrieved_at=ts_et, rows=1
        )
        assert reg.retrieved_at_min.tzinfo == UTC
        assert reg.retrieved_at_max.tzinfo == UTC
        # Same instant in UTC: 07:00-05:00 == 12:00+00:00.
        assert reg.retrieved_at_min == datetime(
            2026, 5, 21, 12, 0, 0, tzinfo=UTC
        )
        # Audit log ISO string ends with +00:00, not -05:00.
        assert reg.audit_log()[0]["ts"].endswith("+00:00")

    def test_register_rejects_empty_source(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            _ToySchema.register(source="", retrieved_at=_TS, rows=1)

    def test_register_rejects_non_str_source_bool(self) -> None:
        with pytest.raises(TypeError, match="source must be str"):
            _ToySchema.register(
                source=True,  # type: ignore[arg-type]
                retrieved_at=_TS,
                rows=1,
            )

    def test_register_rejects_non_str_source_list(self) -> None:
        with pytest.raises(TypeError, match="source must be str"):
            _ToySchema.register(
                source=["iem.archive"],  # type: ignore[arg-type]
                retrieved_at=_TS,
                rows=1,
            )

    def test_register_rejects_non_str_source_none(self) -> None:
        with pytest.raises(TypeError, match="source must be str"):
            _ToySchema.register(
                source=None,  # type: ignore[arg-type]
                retrieved_at=_TS,
                rows=1,
            )

    def test_register_rejects_negative_rows(self) -> None:
        with pytest.raises(ValueError, match="rows must be >= 0"):
            _ToySchema.register(
                source="iem.archive", retrieved_at=_TS, rows=-1
            )

    def test_register_rejects_non_int_rows(self) -> None:
        with pytest.raises(TypeError, match="rows must be int"):
            _ToySchema.register(
                source="iem.archive",
                retrieved_at=_TS,
                rows=1.5,  # type: ignore[arg-type]
            )

    def test_register_rejects_bool_rows(self) -> None:
        # bool is a subclass of int — guard against accidental passes.
        with pytest.raises(TypeError, match="rows must be int"):
            _ToySchema.register(
                source="iem.archive",
                retrieved_at=_TS,
                rows=True,  # type: ignore[arg-type]
            )

    def test_register_accepts_zero_rows(self) -> None:
        reg = _ToySchema.register(
            source="iem.archive", retrieved_at=_TS, rows=0
        )
        assert reg.rows == 0


# ---------------------------------------------------------------------------
# SchemaRegistration._append_audit / audit_log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def _fresh_registration(self) -> SchemaRegistration:
        return _ToySchema.register(
            source="iem.archive", retrieved_at=_TS, rows=10
        )

    def test_audit_log_returns_shallow_copy(self) -> None:
        reg = self._fresh_registration()
        log_a = reg.audit_log()
        log_a.append({"event": "tamper", "ts": "x"})
        log_b = reg.audit_log()
        # Mutating the returned list does not affect the underlying log.
        assert len(log_b) == 1
        assert log_b[0]["event"] == "registered"

    def test_audit_log_entries_are_defensively_copied(self) -> None:
        # Caller-side mutation of a returned entry must not flow back
        # into the registration's audit log.
        reg = self._fresh_registration()
        snapshot_1 = reg.audit_log()
        snapshot_1[0]["event"] = "tampered"
        snapshot_1[0]["injected"] = "garbage"

        snapshot_2 = reg.audit_log()
        assert snapshot_2[0]["event"] == "registered"
        assert "injected" not in snapshot_2[0]

    def test_append_source_drift_allowed(self) -> None:
        reg = self._fresh_registration()
        reg._append_audit(
            "source_drift_allowed",
            from_source="iem.archive",
            to_source="awc.live",
            reason="backup endpoint during outage 2026-05-21",
            caller="validate_dataframe",
        )
        log = reg.audit_log()
        assert len(log) == 2
        e = log[1]
        assert e["event"] == "source_drift_allowed"
        assert e["from_source"] == "iem.archive"
        assert e["to_source"] == "awc.live"
        assert e["reason"].startswith("backup endpoint")
        assert e["caller"] == "validate_dataframe"
        # Auto-stamped UTC timestamp present and ISO-8601.
        assert "ts" in e
        datetime.fromisoformat(e["ts"])

    def test_append_temporal_drift_audit(self) -> None:
        reg = self._fresh_registration()
        reg._append_audit(
            "temporal_drift_audit",
            asserted_range=["2026-05-01T00:00:00+00:00", "2026-05-21T00:00:00+00:00"],
            outcome="pass",
        )
        log = reg.audit_log()
        assert log[-1]["event"] == "temporal_drift_audit"
        assert log[-1]["outcome"] == "pass"

    def test_append_with_explicit_ts_datetime(self) -> None:
        reg = self._fresh_registration()
        ts = datetime(2026, 6, 1, 9, 30, tzinfo=UTC)
        reg._append_audit("source_drift_allowed", ts=ts, reason="r")
        # datetime ts is normalised to ISO-8601 string in the entry.
        assert reg.audit_log()[-1]["ts"] == ts.isoformat()

    def test_append_with_explicit_ts_string(self) -> None:
        reg = self._fresh_registration()
        reg._append_audit(
            "source_drift_allowed", ts="2026-06-01T09:30:00Z", reason="r"
        )
        assert reg.audit_log()[-1]["ts"] == "2026-06-01T09:30:00Z"

    def test_audit_log_chronological_order(self) -> None:
        reg = self._fresh_registration()
        reg._append_audit("source_drift_allowed", reason="first")
        reg._append_audit("temporal_drift_audit", outcome="fail")
        events = [e["event"] for e in reg.audit_log()]
        assert events == [
            "registered",
            "source_drift_allowed",
            "temporal_drift_audit",
        ]

    def test_audit_entries_are_dicts(self) -> None:
        reg = self._fresh_registration()
        for entry in reg.audit_log():
            assert isinstance(entry, dict)
            assert "event" in entry
            assert "ts" in entry


# ---------------------------------------------------------------------------
# Schema.from_dataframe — deferred to v0.1.1
# ---------------------------------------------------------------------------


class TestSchemaFromDataFrame:
    def test_from_dataframe_raises_not_implemented(self) -> None:
        # df is unused — the method short-circuits before touching it.
        with pytest.raises(NotImplementedError, match=r"v0\.1\.1"):
            _ToySchema.from_dataframe(
                df=object(),  # type: ignore[arg-type]
                source="iem.archive",
                retrieved_at=_TS,
            )
