"""Unit tests for the Phase 12 import rewriter (scripts/_phase12_rename.py).

Covers the 7 behaviors from 12-02-PLAN.md Task 1: rewriter accepts known imports,
preserves preserve-list literals (mostlyright==0.14.1 / mostlyright_v1 / monorepo-v0.14.1),
handles indented imports + bare imports + aliased imports.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# Load the rewriter module from scripts/ (not on sys.path by default).
_SPEC = importlib.util.spec_from_file_location(
    "_phase12_rename",
    Path(__file__).resolve().parents[1] / "scripts" / "_phase12_rename.py",
)
assert _SPEC and _SPEC.loader
_REWRITER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_REWRITER)
rewrite_line = _REWRITER.rewrite_line


def test_from_tradewinds_research():
    assert rewrite_line("from mostlyright.research import research\n") == (
        "from mostlyright.research import research\n"
    )


def test_preserve_monorepo_lift_citation():
    line = "# Lift from monorepo-v0.14.1/src/mostlyright/research.py\n"
    assert rewrite_line(line) == line


def test_preserve_mostlyright_v1_in_docstring():
    line = "DOCSTRING: 'parser_name=mostlyright_v1 stays unchanged'\n"
    assert rewrite_line(line) == line


def test_preserve_mostlyright_version_citation():
    line = "VERSION = 'mostlyright==0.14.1'\n"
    assert rewrite_line(line) == line


def test_indented_import():
    assert rewrite_line("    from mostlyright._internal import x\n") == (
        "    from mostlyright._internal import x\n"
    )


def test_bare_import_no_submodule():
    assert rewrite_line("import mostlyright\n") == "import mostlyright\n"


def test_aliased_import_preserves_alias():
    assert rewrite_line("import mostlyright.research as tw_research\n") == (
        "import mostlyright.research as tw_research\n"
    )
