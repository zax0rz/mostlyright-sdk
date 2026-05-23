"""Format roundtrip and loss-documentation tests.

Covers ``tradewinds._v02.formats``:

- Standard-fixture roundtrip for dataframe, parquet, json, csv, toon.
- TOON-specific deterministic losses per design doc §I.
- Parquet decompression-bomb policy boundary.
- Hypothesis property test: parquet roundtrip is identity for basic dtypes.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra import pandas as hpd
from pandas.testing import assert_frame_equal, assert_series_equal
from tradewinds._v02.formats import (
    csv_dumps,
    csv_loads,
    df_dumps,
    df_loads,
    json_dumps,
    json_loads,
    parquet_dumps,
    parquet_loads,
    toon_dumps,
    toon_loads,
)

# ---------------------------------------------------------------------------
# Standard fixture (schema.observation.v1 subset per design doc §A)
# ---------------------------------------------------------------------------


@pytest.fixture
def standard_df() -> pd.DataFrame:
    """Six-column DataFrame matching the schema fixture in the task spec.

    Mirrors ``schema.observation.v1`` shape: string station IDs,
    tz-aware ``Timestamp[ns, UTC]`` event time, ``float64`` measurements
    with ``NaN`` for missing, ``Int64`` for nullable wind direction,
    ``object`` for the optional raw METAR, and plain ``int64`` for the
    row counter.
    """
    return pd.DataFrame(
        {
            "station": ["KORD", "KSFO", "KJFK"],
            "event_time": pd.to_datetime(
                [
                    "2020-01-01T00:00:00",
                    "2020-01-01T01:00:00",
                    "2020-01-01T02:00:00",
                ]
            ).tz_localize("UTC"),
            "temp_c": [10.5, 22.0, np.nan],
            "wind_dir_deg": pd.array([90, 180, pd.NA], dtype="Int64"),
            "metar_raw": ["KORD 010000Z 09005KT", None, "KJFK 010200Z 18015KT"],
            "obs_count": np.array([1, 2, 3], dtype="int64"),
        }
    )


# ---------------------------------------------------------------------------
# dataframe (identity)
# ---------------------------------------------------------------------------


def test_dataframe_dumps_is_identity(standard_df: pd.DataFrame) -> None:
    """``dataframe.dumps`` returns the same object reference."""
    assert df_dumps(standard_df) is standard_df


def test_dataframe_loads_is_identity(standard_df: pd.DataFrame) -> None:
    """``dataframe.loads`` returns the same object reference."""
    assert df_loads(standard_df) is standard_df


def test_dataframe_roundtrip_preserves_dtypes(standard_df: pd.DataFrame) -> None:
    """Identity roundtrip preserves every dtype byte-for-byte."""
    rt = df_loads(df_dumps(standard_df))
    assert_frame_equal(rt, standard_df, check_dtype=True)


# ---------------------------------------------------------------------------
# parquet (lossless for canonical schemas)
# ---------------------------------------------------------------------------


def test_parquet_roundtrip_is_strict(standard_df: pd.DataFrame) -> None:
    """Parquet roundtrip preserves dtypes (Int64, tz-aware ns, NaN, NA)."""
    blob = parquet_dumps(standard_df)
    assert isinstance(blob, bytes)
    rt = parquet_loads(blob)
    assert_frame_equal(rt, standard_df, check_dtype=True)


def test_parquet_payload_is_bytes(standard_df: pd.DataFrame) -> None:
    """``dumps`` produces a non-empty bytes payload."""
    blob = parquet_dumps(standard_df)
    assert isinstance(blob, bytes)
    assert len(blob) > 0


# ---------------------------------------------------------------------------
# json (loose — dtype-lossy)
# ---------------------------------------------------------------------------


def test_json_roundtrip_loose(standard_df: pd.DataFrame) -> None:
    """JSON roundtrip preserves values but not all dtypes.

    Documented losses: Int64 -> float64, timestamps may degrade to
    object strings depending on pandas version.
    """
    s = json_dumps(standard_df)
    assert isinstance(s, str)
    rt = json_loads(s)
    # Same row count and column names.
    assert list(rt.columns) == list(standard_df.columns)
    assert len(rt) == len(standard_df)
    # Numeric values agree (with NaN tolerance).
    np.testing.assert_array_equal(rt["obs_count"].to_numpy(), standard_df["obs_count"].to_numpy())
    np.testing.assert_array_equal(
        np.isnan(rt["temp_c"].astype(float).to_numpy()),
        np.isnan(standard_df["temp_c"].astype(float).to_numpy()),
    )


def test_json_empty_dataframe_roundtrip_preserves_columns() -> None:
    """Zero-row JSON roundtrip preserves column names via the envelope form.

    Regression: ``pd.DataFrame.to_json(orient='records')`` returns ``"[]"``
    for an empty frame, which ``pd.read_json`` reads back as a zero-column
    DataFrame — columns are silently lost. The encoder now special-cases
    the empty path with a ``{"columns": [...], "data": []}`` envelope
    that the loader detects and reconstructs.
    """
    df = pd.DataFrame({"a": [], "b": [], "c": []})
    rt = json_loads(json_dumps(df))
    assert list(rt.columns) == ["a", "b", "c"]
    assert len(rt) == 0


def test_json_int64_becomes_float(standard_df: pd.DataFrame) -> None:
    """Documented loss: pandas ``Int64`` with NA roundtrips as float64."""
    rt = json_loads(json_dumps(standard_df))
    assert rt["wind_dir_deg"].dtype == np.dtype("float64")
    # The valid values still match.
    assert rt["wind_dir_deg"].iloc[0] == 90
    assert rt["wind_dir_deg"].iloc[1] == 180
    assert np.isnan(rt["wind_dir_deg"].iloc[2])


# ---------------------------------------------------------------------------
# csv (loose — dtype-lossy and null/empty ambiguity)
# ---------------------------------------------------------------------------


def test_csv_roundtrip_loose(standard_df: pd.DataFrame) -> None:
    """CSV roundtrip preserves values but not dtype detail.

    Same row count, same column names, numeric values agree.
    """
    s = csv_dumps(standard_df)
    assert isinstance(s, str)
    rt = csv_loads(s)
    assert list(rt.columns) == list(standard_df.columns)
    assert len(rt) == len(standard_df)
    # obs_count was int64 originally; CSV re-inference still gives int64
    # because no nulls.
    np.testing.assert_array_equal(rt["obs_count"].to_numpy(), standard_df["obs_count"].to_numpy())


def test_csv_null_string_collapses_to_nan(standard_df: pd.DataFrame) -> None:
    """Documented loss: ``None`` in object column reads back as ``NaN``."""
    rt = csv_loads(csv_dumps(standard_df))
    # Original metar_raw[1] was None.
    assert pd.isna(rt["metar_raw"].iloc[1])


# ---------------------------------------------------------------------------
# toon (strict on basic types, with documented losses)
# ---------------------------------------------------------------------------


def test_toon_roundtrip_basic_types(standard_df: pd.DataFrame) -> None:
    """TOON roundtrip preserves basic types and values.

    Strict on:
    - string column (station): roundtrips as a string column.
    - int64 column (obs_count): roundtrips as int64.
    - float64 column (temp_c): roundtrips as float64 with NaN preserved.

    Documented losses for this fixture:
    - event_time: Timestamp[ns, UTC] -> object/string at microsecond
      precision. Callers reconstruct via ``pd.to_datetime``.
    - wind_dir_deg: Int64 with NA -> float64 with NaN.
    - metar_raw: None in object column -> None (parsed back as None).
    """
    s = toon_dumps(standard_df)
    rt = toon_loads(s)

    # Same shape and columns.
    assert list(rt.columns) == list(standard_df.columns)
    assert len(rt) == len(standard_df)

    # Basic-type columns: values match.
    assert list(rt["station"]) == list(standard_df["station"])
    np.testing.assert_array_equal(rt["obs_count"].to_numpy(), standard_df["obs_count"].to_numpy())
    # temp_c: numeric equality with NaN tolerance.
    a = rt["temp_c"].astype(float).to_numpy()
    b = standard_df["temp_c"].astype(float).to_numpy()
    np.testing.assert_array_equal(np.isnan(a), np.isnan(b))
    np.testing.assert_array_equal(a[~np.isnan(a)], b[~np.isnan(b)])

    # Basic-type dtype assertions (strict).
    assert rt["obs_count"].dtype == np.dtype("int64")
    assert rt["temp_c"].dtype == np.dtype("float64")

    # Documented loss: Int64 with NA -> float64.
    assert rt["wind_dir_deg"].dtype == np.dtype("float64")

    # Documented loss: timestamps roundtrip as ISO-8601 strings (loader
    # does NOT auto-promote). Caller reconstructs the timestamp column.
    assert "datetime" not in str(rt["event_time"].dtype)
    reconstructed = pd.to_datetime(rt["event_time"], utc=True)
    assert standard_df["event_time"].iloc[0].floor("us") == reconstructed.iloc[0]


# --- TOON-specific loss tests (per design doc §I) ---------------------------


def test_toon_categorical_becomes_string() -> None:
    """``Categorical`` columns roundtrip as plain string columns.

    The category list is dropped; values are preserved deterministically.
    """
    df = pd.DataFrame({"cat": pd.Categorical(["a", "b", "a", "c"])})
    rt = toon_loads(toon_dumps(df))
    # Values match.
    assert list(rt["cat"]) == ["a", "b", "a", "c"]
    # No longer Categorical.
    assert not isinstance(rt["cat"].dtype, pd.CategoricalDtype)

    # Determinism: same input -> identical output bytes.
    assert toon_dumps(df) == toon_dumps(df)


def test_toon_nanosecond_precision_truncated_to_microseconds() -> None:
    """``Timestamp[ns, tz]`` cells are emitted as ISO strings at µs precision.

    The loader returns ISO-8601 strings (no auto-promotion); reconstructing
    with ``pd.to_datetime`` produces a microsecond-precision timestamp
    column. Nanosecond remainder is lost at encode time.
    """
    ns_input = pd.to_datetime(
        ["2020-01-01T00:00:00.123456789", "2020-01-01T00:00:01.987654321"]
    ).tz_localize("UTC")
    df = pd.DataFrame({"ts": ns_input})
    rt = toon_loads(toon_dumps(df))
    # Roundtrip yields object/string column — caller converts.
    # Loader returns strings (object or pandas StringDtype) — not datetime64.
    assert "datetime" not in str(rt["ts"].dtype)
    ts_col = pd.to_datetime(rt["ts"], utc=True)
    # Microsecond component is preserved.
    assert ts_col.iloc[0].microsecond == 123456
    assert ts_col.iloc[1].microsecond == 987654
    # Nanosecond remainder is lost (truncated to zero at the ns digits).
    assert ts_col.iloc[0].value % 1_000 == 0
    assert ts_col.iloc[1].value % 1_000 == 0
    # Tz preserved through caller-side conversion.
    assert str(ts_col.dt.tz) == "UTC"


def test_toon_mixed_object_column_stringified_deterministically() -> None:
    """Mixed object cells (dict/list/str) are stringified deterministically.

    - ``dict`` cells go through ``json.dumps(sort_keys=True)`` for
      insertion-order independence.
    - Other non-primitives (lists, sets) go through ``str()``.
    - Strings pass through.
    """
    df = pd.DataFrame({"mixed": [{"a": 1}, [1, 2, 3], "str"]})
    s1 = toon_dumps(df)
    s2 = toon_dumps(df)
    assert s1 == s2, "TOON dumps must be deterministic"
    rt = toon_loads(s1)
    # dict → canonical JSON.
    assert rt["mixed"].iloc[0] == '{"a": 1}'
    # list → str().
    assert rt["mixed"].iloc[1] == "[1, 2, 3]"
    # str → passthrough.
    assert rt["mixed"].iloc[2] == "str"


def test_toon_int64_above_2pow53_preserved_with_float_neighbor_column() -> None:
    """A large ``int64`` cell keeps its exact value when sharing a row with float64.

    Regression: ``df.iterrows()`` materialized each row as a ``Series``,
    which upcast every cell to the row's common dtype. An ``int64`` value
    above 2**53 (52 mantissa bits of double precision) sharing a row with
    a ``float64`` column would silently round to the nearest representable
    double. Column-wise iteration preserves each column's dtype.
    """
    big_int = 2**60  # well beyond float64's exact integer range.
    df = pd.DataFrame({"int_col": [big_int], "float_col": [1.5]})
    rt = toon_loads(toon_dumps(df))
    # The integer survives intact, not rounded to float(2**60).
    assert rt["int_col"].iloc[0] == big_int
    assert int(rt["int_col"].iloc[0]) == big_int
    # The float column is also preserved.
    assert rt["float_col"].iloc[0] == 1.5


def test_toon_dict_stringification_is_order_independent() -> None:
    """Logically-equal dicts encode identically regardless of insertion order.

    Regression: ``str({'b': 2, 'a': 1})`` produced ``"{'b': 2, 'a': 1}"``
    while ``str({'a': 1, 'b': 2})`` produced ``"{'a': 1, 'b': 2}"``, so two
    semantically-identical DataFrames roundtripped differently. The
    encoder now canonicalizes dict cells with ``json.dumps(sort_keys=True)``.
    """
    df1 = pd.DataFrame({"x": [{"b": 2, "a": 1}]})
    df2 = pd.DataFrame({"x": [{"a": 1, "b": 2}]})
    assert toon_dumps(df1) == toon_dumps(df2)


def test_toon_decimal_cells_coerce_to_float() -> None:
    """``decimal.Decimal`` cells roundtrip as ``float`` (documented loss).

    TOON's numeric model is ``int``/``float``; ``Decimal`` has no native
    representation. The encoder coerces to ``float`` so the column stays
    numeric on the wire (and is restored as a float column by the loader)
    instead of falling through to ``str(value)`` and being stringified.
    Precision above 2**53 is lost — captured in the module-level loss
    matrix.
    """
    from decimal import Decimal

    df = pd.DataFrame({"price": [Decimal("1.5"), Decimal("2.25"), Decimal("100")]})
    rt = toon_loads(toon_dumps(df))
    # Float column, not strings.
    assert rt["price"].dtype == np.dtype("float64")
    assert rt["price"].iloc[0] == 1.5
    assert rt["price"].iloc[1] == 2.25
    assert rt["price"].iloc[2] == 100.0


def test_toon_int64_with_nulls_becomes_float_with_nan() -> None:
    """``Int64`` (nullable) with NA roundtrips as ``float64`` with NaN.

    Precision below 2**53 is preserved.
    """
    df = pd.DataFrame({"v": pd.array([1, 2, pd.NA, 9999999], dtype="Int64")})
    rt = toon_loads(toon_dumps(df))
    assert rt["v"].dtype == np.dtype("float64")
    assert rt["v"].iloc[0] == 1.0
    assert rt["v"].iloc[1] == 2.0
    assert np.isnan(rt["v"].iloc[2])
    assert rt["v"].iloc[3] == 9999999.0


def test_toon_tz_aware_non_utc_preserved_through_roundtrip() -> None:
    """Tz-aware timestamps in a non-UTC zone roundtrip as ISO strings.

    The encoder emits ISO-8601 cells with the original offset. The loader
    leaves them as strings; reconstructing via ``pd.to_datetime(..., utc=True)``
    recovers the original instant (offset preserved in the string itself).
    """
    df = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01T00:00:00", "2020-01-15T12:00:00"]).tz_localize(
                "America/New_York"
            )
        }
    )
    rt = toon_loads(toon_dumps(df))
    # Loader returns strings (object or pandas StringDtype) — not datetime64.
    assert "datetime" not in str(rt["ts"].dtype)
    # The ISO strings carry the -05:00 offset.
    assert "-05:00" in rt["ts"].iloc[0]
    # Caller-side conversion preserves the instant (in UTC).
    ts_col = pd.to_datetime(rt["ts"], utc=True)
    assert ts_col.iloc[0] == df["ts"].iloc[0]
    assert ts_col.iloc[1] == df["ts"].iloc[1]


def test_toon_tz_aware_dst_crossing_collapses_to_utc() -> None:
    """Non-UTC tz cells spanning DST roundtrip as ISO strings with mixed offsets.

    The encoder emits per-cell offsets. The loader returns strings — caller
    reconstructs with ``pd.to_datetime(..., utc=True)`` which normalizes
    mixed offsets to a single UTC-tz column.
    """
    df = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2020-01-01T00:00:00", "2020-06-15T12:00:00"]).tz_localize(
                "America/New_York"
            )
        }
    )
    rt = toon_loads(toon_dumps(df))
    # Loader returns strings (object or pandas StringDtype) — not datetime64.
    assert "datetime" not in str(rt["ts"].dtype)
    # Mixed offsets visible in the strings: winter -05:00, summer -04:00.
    assert "-05:00" in rt["ts"].iloc[0]
    assert "-04:00" in rt["ts"].iloc[1]
    # Caller-side conversion to UTC preserves both instants.
    ts_col = pd.to_datetime(rt["ts"], utc=True)
    assert str(ts_col.dt.tz) == "UTC"
    assert ts_col.iloc[0] == df["ts"].iloc[0]
    assert ts_col.iloc[1] == df["ts"].iloc[1]


def test_toon_column_name_containing_brace_roundtrips() -> None:
    """Column names containing ``}`` survive the loader's header parser.

    Regression: the original ``_HEADER_RE`` used ``[^}]*`` for the columns
    region, which terminated at the first literal ``}`` inside a quoted
    column name. The loader now walks the header line with quote
    awareness so a brace inside a quoted name does not break parsing.
    """
    df = pd.DataFrame({"col}brace": [1, 2], "plain": [3, 4]})
    rt = toon_loads(toon_dumps(df))
    assert list(rt.columns) == ["col}brace", "plain"]
    assert list(rt["col}brace"]) == [1, 2]
    assert list(rt["plain"]) == [3, 4]


def test_toon_iso_looking_string_column_stays_as_strings() -> None:
    """ISO-date-looking string cells do NOT auto-promote to ``datetime64``.

    Regression: a user-supplied label column whose values happen to match
    the ISO pattern (e.g. event IDs encoded as dates) must roundtrip
    intact, not be silently mutated into a Timestamp column. This also
    makes the roundtrip idempotent — re-dumping the loaded frame is a
    no-op on the column dtype.
    """
    df = pd.DataFrame({"label": ["2020-01-01", "2020-01-02"]})
    rt = toon_loads(toon_dumps(df))
    # Not promoted to a datetime column.
    assert "datetime" not in str(rt["label"].dtype)
    # Values intact as strings.
    assert list(rt["label"]) == ["2020-01-01", "2020-01-02"]
    # Idempotent under repeat dumps/loads.
    rt2 = toon_loads(toon_dumps(rt))
    assert list(rt2["label"]) == ["2020-01-01", "2020-01-02"]
    assert "datetime" not in str(rt2["label"].dtype)


def test_toon_naive_timestamp_column_roundtrip() -> None:
    """Naive timestamp columns roundtrip as ISO-8601 strings (no tz suffix)."""
    df = pd.DataFrame({"ts": pd.to_datetime(["2020-01-01T00:00:00", "2020-01-02T12:30:00"])})
    rt = toon_loads(toon_dumps(df))
    # Loader returns strings (object or pandas StringDtype) — not datetime64.
    assert "datetime" not in str(rt["ts"].dtype)
    # No tz offset in the encoded strings.
    assert "+" not in rt["ts"].iloc[0] and "Z" not in rt["ts"].iloc[0]
    # Caller-side conversion yields the original naive timestamps.
    ts_col = pd.to_datetime(rt["ts"])
    assert ts_col.dt.tz is None
    assert list(ts_col) == list(df["ts"])


def test_toon_nan_value_roundtrip() -> None:
    """``NaN`` in a float column roundtrips as ``NaN`` (not ``None``)."""
    df = pd.DataFrame({"x": [1.0, np.nan, 3.0]})
    rt = toon_loads(toon_dumps(df))
    assert rt["x"].iloc[0] == 1.0
    assert np.isnan(rt["x"].iloc[1])
    assert rt["x"].iloc[2] == 3.0
    assert rt["x"].dtype == np.dtype("float64")


def test_toon_nat_value_roundtrip() -> None:
    """``NaT`` in a timestamp column roundtrips as ``None``; valid cells as ISO strings.

    Loader returns the string column; caller's ``pd.to_datetime`` recovers
    timestamps and treats ``None`` as ``NaT``.
    """
    df = pd.DataFrame(
        {"ts": pd.to_datetime(["2020-01-01", pd.NaT, "2020-01-03"]).tz_localize("UTC")}
    )
    rt = toon_loads(toon_dumps(df))
    # Loader returns strings (object or pandas StringDtype) — not datetime64.
    assert "datetime" not in str(rt["ts"].dtype)
    # NaT cell collapsed to a null sentinel on the wire (None or NaN
    # depending on pandas' inferred string dtype).
    assert pd.isna(rt["ts"].iloc[1])
    # Caller reconstructs the timestamp column.
    ts_col = pd.to_datetime(rt["ts"], utc=True)
    assert ts_col.iloc[0] == df["ts"].iloc[0]
    assert pd.isna(ts_col.iloc[1])
    assert ts_col.iloc[2] == df["ts"].iloc[2]


def test_toon_empty_dataframe_roundtrip() -> None:
    """Zero-row DataFrames roundtrip as zero-row DataFrames with same cols."""
    df = pd.DataFrame({"a": pd.Series([], dtype="int64"), "b": pd.Series([], dtype="object")})
    s = toon_dumps(df)
    rt = toon_loads(s)
    assert list(rt.columns) == ["a", "b"]
    assert len(rt) == 0


def test_toon_empty_dataframe_with_quote_trigger_column_names() -> None:
    """Empty frames quote-escape column names the same way non-empty ones do.

    Regression: the empty path joined ``df.columns`` directly with ``,``,
    so a column named ``"a,b"`` (containing the delimiter) broke header
    parsing — the comma inside the name was treated as a column
    separator. Applying the encoder's key-quoting helper produces a
    parseable header.
    """
    df = pd.DataFrame({"a,b": pd.Series([], dtype="int64"), "c": pd.Series([], dtype="int64")})
    rt = toon_loads(toon_dumps(df))
    assert list(rt.columns) == ["a,b", "c"]
    assert len(rt) == 0


def test_toon_dumps_deterministic_on_repeated_calls(standard_df: pd.DataFrame) -> None:
    """Two ``dumps`` calls on the same DataFrame produce identical bytes."""
    s1 = toon_dumps(standard_df)
    s2 = toon_dumps(standard_df)
    assert s1 == s2


def test_toon_loads_rejects_non_tabular_payload() -> None:
    """Non-tabular TOON (e.g. a scalar or object form) raises ``ValueError``."""
    with pytest.raises(ValueError):
        toon_loads("just a scalar")
    with pytest.raises(ValueError):
        toon_loads("")


def test_toon_loads_rejects_row_count_mismatch() -> None:
    """A declared row count that disagrees with the body raises ``ValueError``."""
    bad = "rows[5]{a,b}:\n  1,2\n  3,4\n"
    with pytest.raises(ValueError):
        toon_loads(bad)


def test_toon_loads_rejects_column_count_mismatch() -> None:
    """A row with the wrong field count raises ``ValueError``."""
    bad = "rows[2]{a,b,c}:\n  1,2,3\n  4,5\n"
    with pytest.raises(ValueError):
        toon_loads(bad)


# ---------------------------------------------------------------------------
# Parquet decompression-bomb boundary (per design doc §E)
# ---------------------------------------------------------------------------


def test_parquet_loads_handles_large_compressible_payload() -> None:
    """Loader accepts large highly-compressible payloads without enforcing a cap.

    The 50 MB / 1 GB caps from design doc §E live at the MCP server's
    trust boundary, not in the formats module. This test documents that
    decision: a payload that compresses well still roundtrips here.
    """
    # 1M rows of a single repeated string compresses to a few KB with zstd.
    df = pd.DataFrame({"x": ["the same value"] * 1_000_000})
    blob = parquet_dumps(df)
    # Confirm compression is doing its job (else this test is uninteresting).
    assert len(blob) < 1_000_000, "expected zstd to compress repetitive payload"
    rt = parquet_loads(blob)
    assert len(rt) == 1_000_000
    assert rt["x"].iloc[0] == "the same value"


def test_parquet_size_cap_is_documented_in_module() -> None:
    """Sanity: the parquet module docstring records that size caps live in MCP layer.

    Prevents the doc from drifting away from the architectural decision in §E.
    """
    from tradewinds._v02.formats import parquet as parquet_mod

    doc = parquet_mod.loads.__doc__ or ""
    assert "MCP" in doc or "trust boundary" in doc


# ---------------------------------------------------------------------------
# Hypothesis property test: parquet roundtrip is identity for basic dtypes
# ---------------------------------------------------------------------------


# Strategies for individual columns. Basic dtypes only — parquet is lossless
# for these, so the property "loads(dumps(df)) == df" must hold for any
# generated input.

_BASIC_COLUMNS = [
    hpd.column(
        name="i",
        dtype=np.int64,
        elements=st.integers(min_value=-(2**31), max_value=2**31 - 1),
    ),
    hpd.column(
        name="f",
        dtype=np.float64,
        elements=st.floats(allow_nan=True, allow_infinity=False, width=64),
    ),
    hpd.column(
        name="b",
        dtype=np.bool_,
        elements=st.booleans(),
    ),
    hpd.column(
        name="s",
        dtype=object,
        elements=st.text(min_size=0, max_size=20),
    ),
]


@given(
    df=hpd.data_frames(
        columns=_BASIC_COLUMNS,
        index=hpd.range_indexes(min_size=0, max_size=50),
    )
)
@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_parquet_roundtrip_property_basic_dtypes(df: pd.DataFrame) -> None:
    """Parquet roundtrip is identity for randomly-generated basic-dtype frames.

    Suppresses pandas/pyarrow warnings during the property run — the
    test asserts behavior, not warning silence.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        blob = parquet_dumps(df)
        rt = parquet_loads(blob)
    # Object-string columns sometimes come back with a different but
    # equivalent dtype (pyarrow `string` vs pandas `object`). Check the
    # values; the dtype-strict roundtrip is already covered by the
    # explicit standard_df test.
    assert_frame_equal(
        rt.reset_index(drop=True),
        df.reset_index(drop=True),
        check_dtype=False,
        check_like=False,
    )


# ---------------------------------------------------------------------------
# Cross-format sanity check
# ---------------------------------------------------------------------------


def test_every_format_roundtrip_preserves_row_count(
    standard_df: pd.DataFrame,
) -> None:
    """Every format preserves the row count regardless of dtype losses."""
    assert len(df_loads(df_dumps(standard_df))) == len(standard_df)
    assert len(parquet_loads(parquet_dumps(standard_df))) == len(standard_df)
    assert len(json_loads(json_dumps(standard_df))) == len(standard_df)
    assert len(csv_loads(csv_dumps(standard_df))) == len(standard_df)
    assert len(toon_loads(toon_dumps(standard_df))) == len(standard_df)


def test_every_format_roundtrip_preserves_columns(
    standard_df: pd.DataFrame,
) -> None:
    """Every format preserves column names and order."""
    cols = list(standard_df.columns)
    assert list(df_loads(df_dumps(standard_df)).columns) == cols
    assert list(parquet_loads(parquet_dumps(standard_df)).columns) == cols
    assert list(json_loads(json_dumps(standard_df)).columns) == cols
    assert list(csv_loads(csv_dumps(standard_df)).columns) == cols
    assert list(toon_loads(toon_dumps(standard_df)).columns) == cols


# ---------------------------------------------------------------------------
# Direct exercise of small helpers (branch coverage)
# ---------------------------------------------------------------------------


def test_toon_dumps_string_with_comma_is_quoted() -> None:
    """Cells containing the delimiter are quoted by the encoder."""
    df = pd.DataFrame({"x": ["a,b", "no_comma"]})
    s = toon_dumps(df)
    # Quoted cell with comma.
    assert '"a,b"' in s
    # Plain cell remains unquoted.
    assert "no_comma" in s
    rt = toon_loads(s)
    assert list(rt["x"]) == ["a,b", "no_comma"]


def test_toon_dumps_quoted_string_escapes() -> None:
    """Strings with quotes/newlines/tabs roundtrip through the escape table."""
    df = pd.DataFrame({"x": ['has "quote"', "line\nbreak", "tab\there"]})
    rt = toon_loads(toon_dumps(df))
    assert list(rt["x"]) == ['has "quote"', "line\nbreak", "tab\there"]


def test_toon_bool_column_roundtrip() -> None:
    """Bool columns roundtrip with bool values preserved."""
    df = pd.DataFrame({"b": [True, False, True]})
    rt = toon_loads(toon_dumps(df))
    assert list(rt["b"]) == [True, False, True]


def test_toon_assert_series_equal_on_obs_count(standard_df: pd.DataFrame) -> None:
    """Strict series-level comparison for the int64 column survives roundtrip."""
    rt = toon_loads(toon_dumps(standard_df))
    assert_series_equal(rt["obs_count"], standard_df["obs_count"], check_names=True)


# ---------------------------------------------------------------------------
# Lifted TOON internals — public surface smoke tests (confirms the lift works)
# ---------------------------------------------------------------------------


def test_lifted_toon_encode_tabular_smoke() -> None:
    """The lifted ``encode_tabular`` produces the canonical tabular form."""
    from tradewinds._v02.formats._toon import encode, encode_tabular

    out = encode_tabular([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}])
    assert out.startswith("rows[2]{a,b}:")
    # The generic `encode` entry point handles the same tabular case.
    assert encode([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]).startswith("rows[2]")


def test_lifted_toon_list_codec_smoke() -> None:
    """The lifted ``flatten_lists_for_toon`` joins ``qc_flags`` with ``|``."""
    from tradewinds._v02.formats._toon_list_codec import (
        QC_FLAGS_TOON_SEPARATOR,
        flatten_lists_for_toon,
    )

    assert QC_FLAGS_TOON_SEPARATOR == "|"
    flat = flatten_lists_for_toon({"qc_flags": ["one", "two"], "other": 5})
    assert flat == {"qc_flags": "one|two", "other": 5}
    # Empty list and None both collapse to "".
    assert flatten_lists_for_toon({"qc_flags": []}) == {"qc_flags": ""}
    assert flatten_lists_for_toon({"qc_flags": None}) == {"qc_flags": ""}
    # Field absent from registry: passthrough.
    assert flatten_lists_for_toon({"unknown": [1, 2]}) == {"unknown": [1, 2]}
