"""Phase 20 OM-09 scoping check: IEM MOS parity fixtures under new schema alias.

This regression test validates that the schema unification
(:class:`StationForecastSchema` + :class:`ForecastSchema` alias from
PLAN-01) does NOT alter the byte-equivalence of the 5 existing IEM MOS
parity fixtures captured against ``mostlyright==0.14.1``.

The 5 fixture-driven parity tests are ``@pytest.mark.live`` because they
require fetching from real public APIs (IEM ASOS, IEM CLI, GHCNh) — same
posture as ``test_parity.py``. The schema-registry-only assertions are
not live-gated; they prove the alias resolves to the same column set even
if the live cases cannot be exercised in CI.

If this test passes, OM-09 in Wave 5 PLAN-11 reduces to a trivial
alias-only verification. If it fails, OM-09 spawns a re-capture sub-task
and the diff report (`OM-09-DIFF-REPORT.md`) drives the recapture
decision.
"""

from __future__ import annotations

from pathlib import Path

import mostlyright as mr
import pandas as pd
import pytest
from mostlyright.core.schemas import SCHEMA_REGISTRY
from pandas.testing import assert_frame_equal

PARITY_DIR = Path(__file__).resolve().parent / "fixtures" / "parity"

# 5 IEM MOS parity fixtures (Phase 1 byte-equivalent against v0.14.1 client.pairs).
FIXTURES: list[tuple[int, str, str, str]] = [
    (1, "KNYC", "2025-01-06", "2025-01-12"),
    (2, "KMDW", "2025-04-01", "2025-04-30"),
    (3, "KLAX", "2025-03-01", "2025-03-31"),
    (4, "KMIA", "2024-12-01", "2025-11-30"),
    (5, "KMSY", "2024-09-08", "2024-09-22"),
]


def test_iem_mos_alias_resolves_in_registry() -> None:
    """The back-compat ``schema.forecast.iem_mos.v1`` ID still resolves."""
    assert "schema.forecast.iem_mos.v1" in SCHEMA_REGISTRY


def test_station_v1_canonical_resolves_in_registry() -> None:
    assert "schema.forecast.station.v1" in SCHEMA_REGISTRY


def test_alias_and_canonical_share_column_set() -> None:
    """Phase 20 OM-02: alias COLUMNS list is identical to canonical."""
    canonical = SCHEMA_REGISTRY["schema.forecast.station.v1"]
    alias = SCHEMA_REGISTRY["schema.forecast.iem_mos.v1"]
    assert canonical.COLUMNS == alias.COLUMNS


def test_alias_preserves_iem_archive_source() -> None:
    """``ForecastSchema._registered_source`` must remain ``iem.archive`` so
    Phase 17 source-identity checks continue to work."""
    alias = SCHEMA_REGISTRY["schema.forecast.iem_mos.v1"]
    assert alias._registered_source == "iem.archive"


def test_diff_report_file_exists() -> None:
    """OM-09 diff report (markdown) recording Wave 1 scoping signal.

    The planning artifacts live in a separate private repo
    (``mostlyrightmd/planning``) cloned alongside the SDK working copy
    per ``PLANNING-SETUP.md``. The report is searched at both the in-repo
    ``.planning/`` mount (if used) and the canonical
    ``~/Documents/GitHub/planning/`` sibling checkout. If neither is
    present (CI without planning access), skip rather than fail.
    """
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root
        / ".planning"
        / "phases"
        / "20-open-meteo-forecast-source-integration-leakage-safe-40-model"
        / "OM-09-DIFF-REPORT.md",
        Path.home()
        / "Documents"
        / "GitHub"
        / "planning"
        / "phases"
        / "20-open-meteo-forecast-source-integration-leakage-safe-40-model"
        / "OM-09-DIFF-REPORT.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            content = candidate.read_text()
            assert "OM-09 status:" in content
            return
    pytest.skip(
        "OM-09 diff report not found at any candidate path "
        f"({[str(c) for c in candidates]}); ensure planning repo is checked out."
    )


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror ``test_parity.py``'s cache-isolation fixture so any populated
    user cache cannot mask a regression."""
    monkeypatch.setenv("MOSTLYRIGHT_CACHE_DIR", str(tmp_path))


@pytest.mark.live
@pytest.mark.parametrize(
    "case_num,station,frm,to",
    FIXTURES,
    ids=[f"case-{n}-{s}-{f}-{t}" for n, s, f, t in FIXTURES],
)
def test_iem_mos_parity_fixture_passes_under_unified_schema(
    case_num: int, station: str, frm: str, to: str
) -> None:
    """Each fixture must still byte-match ``research(station, frm, to)``
    output under the new :class:`StationForecastSchema` alias for
    ``schema.forecast.iem_mos.v1``.

    Replicates ``test_parity.py::test_parity_case`` exactly so the
    schema unification's effect surfaces as a delta against the same
    fixtures with the same comparator settings.
    """
    expected = pd.read_parquet(PARITY_DIR / f"case_{case_num}_{station}_{frm}_{to}.parquet")
    actual = mr.research(station, frm, to)

    # Canonicalise (mirror test_parity.py:_canon)
    def _canon(df: pd.DataFrame) -> pd.DataFrame:
        out = df.reset_index() if df.index.name else df.reset_index(drop=True)
        if "index" in out.columns and "date" in out.columns:
            out = out.drop(columns=["index"])
        return out.sort_values(["date", "station"]).reset_index(drop=True)

    assert_frame_equal(
        _canon(actual),
        _canon(expected),
        check_dtype=True,
        check_exact=False,
        rtol=0,
        atol=1e-12,
    )
