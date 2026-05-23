"""Unit tests for tradewinds.mode2 (Phase 3 Mode 2 dispatch seam)."""

from __future__ import annotations

import pandas as pd
import pytest
from tradewinds.core.exceptions import SourceMismatchError
from tradewinds.mode2 import (
    _VALID_OBSERVATION_SOURCES,
    assert_source_identity,
    research_by_source,
)


def test_valid_sources_documented():
    """Mode 2 ships the v0.14.1 4-source set."""
    assert (
        frozenset({"iem.archive", "iem.live", "awc.live", "ghcnh.archive"})
        == _VALID_OBSERVATION_SOURCES
    )


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="Mode 2 source must be one of"):
        research_by_source("KNYC", "bogus.source", "2025-01-01", "2025-01-31")


def test_research_by_source_delegates_to_adapter():
    """research_by_source raises NotImplementedError (adapter.fetch_observations
    is the Phase 3.1/3.2 entry point — v0.1.0 only ships the dispatch seam).
    """
    with pytest.raises(NotImplementedError, match="Mode-2"):
        research_by_source("KNYC", "iem.archive", "2025-01-01", "2025-01-31")


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
