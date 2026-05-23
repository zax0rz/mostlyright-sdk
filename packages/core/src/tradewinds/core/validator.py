"""DataFrame validator with source-identity enforcement.

The Validator is the source-identity invariant gate: every canonical-schema
DataFrame flowing through tradewinds must carry ``df.attrs["source"]``, and
that ``source`` must match the schema's registered canonical source unless
the caller explicitly opts out via ``allow_source_drift``.

This is *the* invariant that prevents the silent train/infer mismatch
research() Mode 2 is designed against. When a parquet cache file is loaded
the next session and the saved ``source`` differs from what the schema
expects, the user learns immediately (loud :class:`SourceMismatchError`)
instead of finding out their model trained on AWC data and inferred on IEM.

Engine choice (D-02 — decided in Phase 2 Wave 1 Task 1.0 spike): jsonschema
4.x. Per-column dtype validation is done in pandas-native (faster, no
serialization roundtrip); enum-value checks use jsonschema directly so the
error format is consistent with future MCP wire serialization.

See ``docs/design.md`` §H (test bar) + §J (allow_source_drift semantics).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from tradewinds.core.exceptions import (
    SchemaValidationError,
    SourceMismatchError,
)
from tradewinds.core.schema import Schema, SchemaRegistration

if TYPE_CHECKING:
    pass


__all__ = ["validate_dataframe"]


_SAMPLE_CAP = 10


# ---------------------------------------------------------------------------
# Schema registry — populated by ``register_schema`` at module load.
# ---------------------------------------------------------------------------
_SCHEMA_REGISTRY: dict[str, type[Schema]] = {}


def register_schema(schema_cls: type[Schema]) -> None:
    """Register a Schema subclass by its ``schema_id``.

    Called eagerly at ``tradewinds.core.schemas`` import for the three
    canonical schemas. Idempotent — re-registering with the same class is
    a no-op; re-registering the same ID with a different class raises.
    """
    sid = schema_cls.schema_id
    if not sid:
        raise ValueError(f"Cannot register {schema_cls.__name__}: schema_id is empty")
    existing = _SCHEMA_REGISTRY.get(sid)
    if existing is not None and existing is not schema_cls:
        raise ValueError(
            f"schema_id {sid!r} already registered to "
            f"{existing.__name__}; cannot re-register {schema_cls.__name__}"
        )
    _SCHEMA_REGISTRY[sid] = schema_cls


def _lookup_schema(schema_id: str) -> type[Schema]:
    cls = _SCHEMA_REGISTRY.get(schema_id)
    if cls is None:
        raise SchemaValidationError(
            f"Unknown schema_id {schema_id!r}; " f"known: {sorted(_SCHEMA_REGISTRY)}",
            schema_id=schema_id,
            violations=[{"rule": "unknown_schema_id"}],
        )
    return cls


# ---------------------------------------------------------------------------
# Dtype dispatch
# ---------------------------------------------------------------------------
def _check_string(s: pd.Series) -> bool:
    return pd.api.types.is_string_dtype(s) or s.dtype == "object"


def _check_float64(s: pd.Series) -> bool:
    return pd.api.types.is_float_dtype(s)


def _check_int(s: pd.Series) -> bool:
    return pd.api.types.is_integer_dtype(s)


def _check_date(s: pd.Series) -> bool:
    # ``date`` columns may be stored as Python ``date`` objects (object dtype)
    # or as a naive datetime64; either is acceptable at this layer.
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    if s.dtype == "object":
        # Sample a non-null value to confirm it is a date-like.
        non_null = s.dropna()
        if non_null.empty:
            return True
        from datetime import date

        return all(isinstance(v, date) for v in non_null.head(5))
    return False


def _check_timestamp_utc(s: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(s) and getattr(s.dt, "tz", None) is not None


def _check_enum(s: pd.Series) -> bool:
    # Enum dtype is exercised by _check_enum_values; here we accept string
    # / object / categorical as the storage layer.
    return (
        pd.api.types.is_string_dtype(s)
        or s.dtype == "object"
        or isinstance(s.dtype, pd.CategoricalDtype)
    )


_DTYPE_CHECKERS: dict[str, Any] = {
    "string": _check_string,
    "float64": _check_float64,
    "int": _check_int,
    "int64": _check_int,
    "date": _check_date,
    "timestamp_utc": _check_timestamp_utc,
    "enum": _check_enum,
}


# ---------------------------------------------------------------------------
# Null-sentinel mix detection (Pitfall 15)
# ---------------------------------------------------------------------------
def _has_mixed_null_sentinels(s: pd.Series) -> bool:
    """Return True if a column contains both ``pd.NA`` and ``np.nan``.

    Adapters that internally use ``fillna`` or ``.where`` can accidentally
    coerce ``pd.NA`` to ``np.nan`` (or vice versa) in subsets of rows,
    producing a column with both sentinels. Downstream dtype-aware code
    (e.g. IEM ``M``-vs-zero discrimination per Pitfall 8) is then unsafe.
    """
    if s.dtype == "object":
        sample = s.head(1000)
        has_na = any(v is pd.NA for v in sample)
        has_nan = any(isinstance(v, float) and v != v for v in sample)  # NaN
        return has_na and has_nan
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def validate_dataframe(
    df: pd.DataFrame,
    schema_id: str,
    *,
    allow_source_drift: str | None = None,
) -> SchemaRegistration:
    """Validate a DataFrame against the named canonical schema.

    The Validator runs four checks, in order:

    1. **Source-identity invariant.** Reads ``df.attrs["source"]`` and
       compares against ``schema_cls._registered_source``. If they differ
       and ``allow_source_drift`` is None, raises
       :class:`SourceMismatchError`. If ``allow_source_drift`` is supplied,
       the drift is permitted and the audit log records the reason.
    2. **Required-column presence.** Non-nullable columns must be present
       in ``df.columns``.
    3. **Per-column dtype.** Dispatched on :class:`ColumnSpec.dtype`.
    4. **Enum value membership.** ``dtype="enum"`` columns must have values
       in ``ColumnSpec.enum_values``. Sample of violating values capped at 10.

    Args:
        df: The DataFrame to validate. Must carry ``df.attrs["source"]``.
        schema_id: Canonical schema ID (e.g. ``"schema.observation.v1"``).
        allow_source_drift: Reason string. If supplied, source mismatch is
            allowed; audit log records the reason.

    Returns:
        A :class:`SchemaRegistration` recording the validation. Carries the
        full audit log (``registered`` event always; ``source_drift_allowed``
        event when ``allow_source_drift`` is supplied).

    Raises:
        SchemaValidationError: column / dtype / enum / null-sentinel violations.
        SourceMismatchError: source identity violated without opt-out.
    """
    schema_cls = _lookup_schema(schema_id)

    # --- 1. Source-identity invariant ---
    data_source = df.attrs.get("source")
    if data_source is None:
        raise SchemaValidationError(
            "DataFrame missing df.attrs['source']; " "cannot validate source-identity",
            schema_id=schema_id,
            violations=[{"rule": "source_attr_required"}],
            quarantine_count=len(df),
            sample_violations=[],
        )

    registered_source = getattr(schema_cls, "_registered_source", None)
    if (
        registered_source is not None
        and data_source != registered_source
        and allow_source_drift is None
    ):
        raise SourceMismatchError(
            f"Source drift: data is {data_source!r}, " f"schema expects {registered_source!r}",
            schema_source=registered_source,
            data_source=data_source,
            role=None,
            catalog_warning=None,
        )

    # --- 1b. Per-row source-column check (codex iter-2 HIGH fix) ---
    # If the DataFrame carries an overlay ``source`` column (catalog adapters
    # always do), every non-null value must equal ``df.attrs["source"]``.
    # Without this check, an attacker / buggy adapter could mix rows from
    # multiple sources while leaving df.attrs labelled as one of them.
    if "source" in df.columns:
        non_null_sources = df["source"].dropna()
        if len(non_null_sources) > 0:
            mismatched = non_null_sources[non_null_sources != data_source]
            if len(mismatched) > 0:
                distinct_bad = sorted(set(mismatched.astype(str).tolist()))[:_SAMPLE_CAP]
                raise SourceMismatchError(
                    f"Per-row 'source' column has {len(mismatched)} row(s) "
                    f"not matching df.attrs['source']={data_source!r}; "
                    f"distinct mismatched values: {distinct_bad}",
                    schema_source=data_source,
                    data_source=str(distinct_bad[0]) if distinct_bad else "<unknown>",
                    role=None,
                    catalog_warning=(
                        "row-level source column drift; the validator requires "
                        "all per-row sources to match df.attrs['source']"
                    ),
                )

    # --- 2-4. Column / dtype / enum / null checks ---
    violations: list[dict[str, Any]] = []

    for spec in schema_cls.COLUMNS:
        col_name = spec.name
        if col_name not in df.columns:
            if not spec.nullable:
                violations.append({"column": col_name, "rule": "required_column_missing"})
            # Nullable columns may be absent.
            continue

        col = df[col_name]

        # 2a. Null check.
        if not spec.nullable and col.isna().any():
            n = int(col.isna().sum())
            violations.append({"column": col_name, "rule": "non_nullable_has_nulls", "count": n})

        # 2b. Mixed-null-sentinel check (Pitfall 15).
        if _has_mixed_null_sentinels(col):
            violations.append({"column": col_name, "rule": "mixed_null_sentinels"})

        # 3. Dtype check.
        checker = _DTYPE_CHECKERS.get(spec.dtype)
        if checker is None:
            violations.append({"column": col_name, "rule": "unknown_dtype", "dtype": spec.dtype})
        else:
            try:
                ok = checker(col)
            except Exception as e:  # — surface as violation
                ok = False
                violations.append(
                    {"column": col_name, "rule": "dtype_check_error", "error": str(e)}
                )
            else:
                if not ok:
                    violations.append(
                        {
                            "column": col_name,
                            "rule": "dtype_mismatch",
                            "expected": spec.dtype,
                            "actual": str(col.dtype),
                        }
                    )

        # 4. Enum-value check.
        if spec.dtype == "enum" and spec.enum_values is not None:
            non_null = col.dropna()
            mask_bad = ~non_null.isin(list(spec.enum_values))
            if mask_bad.any():
                bad_idx = non_null.index[mask_bad][:_SAMPLE_CAP]
                sample = [{"row_idx": int(idx), "value": non_null.loc[idx]} for idx in bad_idx]
                violations.append(
                    {
                        "column": col_name,
                        "rule": "enum_value_violation",
                        "count": int(mask_bad.sum()),
                        "sample": sample,
                    }
                )

    if violations:
        # First _SAMPLE_CAP violations as the inline sample.
        sample = violations[:_SAMPLE_CAP]
        raise SchemaValidationError(
            f"Schema {schema_id!r} validation failed with " f"{len(violations)} violation(s)",
            schema_id=schema_id,
            violations=violations,
            quarantine_count=0,
            sample_violations=sample,
        )

    # --- Build SchemaRegistration ---
    # codex iter-2 HIGH fix: never fabricate retrieved_at. Validator must
    # use the provenance the producer captured — silent "now()" fallback
    # would let a cache/load path that dropped attrs validate with a false
    # retrieval timestamp, breaking amendment-window audits.
    retrieved_at = df.attrs.get("retrieved_at")
    if retrieved_at is None and "retrieved_at" in df.columns:
        # Fall back to row-level retrieved_at column (catalog adapters
        # always populate this). Use the maximum non-null value as the
        # registration's retrieved_at; row-level range is preserved on
        # the column itself.
        col = df["retrieved_at"].dropna()
        if len(col) > 0:
            retrieved_at = pd.Timestamp(col.max()).to_pydatetime()
    if retrieved_at is None:
        raise SchemaValidationError(
            "DataFrame missing provenance: neither df.attrs['retrieved_at'] "
            "nor a 'retrieved_at' column is present. Validator will not "
            "fabricate a timestamp — catalog adapters must supply it.",
            schema_id=schema_id,
            violations=[{"rule": "retrieved_at_required"}],
            quarantine_count=len(df),
            sample_violations=[],
        )
    if isinstance(retrieved_at, pd.Timestamp):
        retrieved_at = retrieved_at.to_pydatetime()

    reg = schema_cls.register(
        source=data_source,
        retrieved_at=retrieved_at,
        rows=len(df),
    )
    if registered_source is not None and data_source != registered_source:
        # Drift was permitted — audit it.
        reg._append_audit(
            "source_drift_allowed",
            schema_source=registered_source,
            data_source=data_source,
            reason=allow_source_drift,
        )
    return reg
