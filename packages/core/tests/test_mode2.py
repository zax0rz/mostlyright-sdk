"""Unit tests for mostlyright.mode2 (Phase 3 Mode 2 dispatch seam)."""

from __future__ import annotations

import pandas as pd
import pytest
from mostlyright.core.exceptions import SourceMismatchError
from mostlyright.mode2 import (
    _VALID_OBSERVATION_SOURCES,
    assert_source_identity,
    research_by_source,
)


def test_valid_sources_documented():
    """Mode 2 accepts both bare parser tags and dotted canonical forms."""
    expected = frozenset(
        {
            "iem",
            "iem.archive",
            "iem.live",
            "awc",
            "awc.live",
            "ghcnh",
            "ghcnh.archive",
        }
    )
    assert expected == _VALID_OBSERVATION_SOURCES


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="Mode 2 source must be one of"):
        research_by_source("KNYC", "bogus.source", "2025-01-01", "2025-01-31")


def test_research_by_source_filters_by_parser_tag_in_production(tmp_path, monkeypatch) -> None:
    """Production parsers emit bare 'iem' / 'awc' / 'ghcnh'.

    Mode 2 must accept the dotted form at the input boundary but
    filter against the actual parser-emitted bare form (architect-
    CRITICAL fix). Verifies the alias table bridges request → parser tag.
    """
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("mostlyright.research")
    synthetic_obs = [
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T12:00:00+00:00",
            "source": "iem",  # parser emits the BARE form
            "temp_c": 5.0,
        },
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T13:00:00+00:00",
            "source": "awc",
            "temp_c": 6.0,
        },
    ]
    monkeypatch.setattr(
        research_module, "_fetch_observations_range", lambda *a, **kw: synthetic_obs
    )
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)

    df = research_by_source("KNYC", "iem.archive", "2025-01-06", "2025-01-12")
    assert len(df) == 1, "alias table failed — request 'iem.archive' should match parser 'iem'"
    # Truthful provenance: per-row source is the parser-emitted bare
    # tag, NOT silently rewritten to the requested dotted form.
    assert df.iloc[0]["source"] == "iem"
    # df.attrs records the REQUESTED source for caller reference.
    assert df.attrs.get("source") == "iem.archive"
    assert df.attrs.get("accepted_sources") == ["iem", "iem.archive"]


def test_research_by_source_bare_source_form_also_accepted(tmp_path, monkeypatch) -> None:
    """The bare 'iem' / 'awc' / 'ghcnh' tags are also valid Mode 2 inputs."""
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("mostlyright.research")
    monkeypatch.setattr(
        research_module,
        "_fetch_observations_range",
        lambda *a, **kw: [
            {
                "station_code": "KNYC",
                "observed_at": "2025-01-06T12:00:00+00:00",
                "source": "iem",
                "temp_c": 5.0,
            }
        ],
    )
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
    df = research_by_source("KNYC", "iem", "2025-01-06", "2025-01-12")
    assert len(df) == 1
    assert df.iloc[0]["source"] == "iem"


def test_research_by_source_empty_carries_attrs(tmp_path, monkeypatch) -> None:
    """Even when no rows match, the empty DataFrame carries provenance."""
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("mostlyright.research")
    monkeypatch.setattr(research_module, "_fetch_observations_range", lambda *a, **kw: [])
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
    df = research_by_source("KNYC", "iem.archive", "2025-01-06", "2025-01-12")
    assert df.empty
    assert df.attrs.get("source") == "iem.archive"


def test_research_by_source_ghcnh_alias(tmp_path, monkeypatch) -> None:
    """`ghcnh` and `ghcnh.archive` are interchangeable (parser emits bare form)."""
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("mostlyright.research")
    synthetic_obs = [
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T12:00:00+00:00",
            "source": "ghcnh",
            "temp_c": 5.0,
        },
    ]
    monkeypatch.setattr(
        research_module, "_fetch_observations_range", lambda *a, **kw: synthetic_obs
    )
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
    # Caller asks for `ghcnh.archive`; parser emitted `ghcnh`. Alias works.
    df = research_by_source("KNYC", "ghcnh.archive", "2025-01-06", "2025-01-12")
    assert len(df) == 1
    # Truthful provenance preserved — the row carries the parser's bare tag.
    assert df.iloc[0]["source"] == "ghcnh"


def test_research_by_source_as_dataframe_false(tmp_path, monkeypatch) -> None:
    import importlib

    monkeypatch.setenv("TRADEWINDS_CACHE_DIR", str(tmp_path))
    research_module = importlib.import_module("mostlyright.research")
    raw = [
        {
            "station_code": "KNYC",
            "observed_at": "2025-01-06T12:00:00+00:00",
            "source": "iem",  # parser-emitted bare form
            "temp_c": 5.0,
        }
    ]
    monkeypatch.setattr(research_module, "_fetch_observations_range", lambda *a, **kw: raw)
    monkeypatch.setattr(research_module, "_all_caches_warm", lambda *a, **kw: True)
    out = research_by_source("KNYC", "iem.archive", "2025-01-06", "2025-01-12", as_dataframe=False)
    assert isinstance(out, list)
    assert len(out) == 1
    # Truthful provenance preserved end-to-end (list path doesn't rewrite either).
    assert out[0]["source"] == "iem"


def test_assert_source_identity_happy():
    df = pd.DataFrame({"source": ["iem.archive", "iem.archive"]})
    assert_source_identity(df, "iem.archive")  # no raise


def test_assert_source_identity_mismatch_raises():
    df = pd.DataFrame({"source": ["iem.archive", "awc.live"]})
    with pytest.raises(SourceMismatchError) as exc:
        assert_source_identity(df, "iem.archive")
    assert exc.value.role == "observations"
    assert "awc.live" in str(exc.value)


def test_assert_source_identity_no_source_column_is_noop():
    """If df has no source column, assert_source_identity passes (let
    Validator handle that case)."""
    df = pd.DataFrame({"other": [1, 2]})
    assert_source_identity(df, "iem.archive")


def test_assert_source_identity_empty_df():
    df = pd.DataFrame({"source": []})
    assert_source_identity(df, "iem.archive")
