"""Regression tests for ``scripts/parity_ticket_check.py``.

The parity-gate parser must NOT be fooled by the example markers shipped
inside the PR template's HTML comments / fenced code blocks. Closes TS-W0
iter-1 CRITICAL 2.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from parity_ticket_check import _classify, _load_config, parse_pr_body  # noqa: E402


def test_unchanged_template_does_not_bypass_gate() -> None:
    """The default PR template body must NOT satisfy any opt-out marker.

    If this test fails, the parity gate is bypassable: a contributor who
    files a PR without editing the template body would satisfy the gate
    even though they took no action to opt out.
    """
    template_path = _REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
    body = template_path.read_text(encoding="utf-8")
    ticket, py_only, ts_only = parse_pr_body(body)
    assert ticket is None, f"unchanged template matched a parity ticket: {ticket!r}"
    assert not py_only, "unchanged template matched python_only marker"
    assert not ts_only, "unchanged template matched typescript_only marker"


def test_real_parity_ticket_outside_comment_matches() -> None:
    """A real ticket reference (outside any comment / code block) must match."""
    body = "## Summary\n\nFoo bar.\n\nParity-Ticket: #456\n"
    ticket, py_only, ts_only = parse_pr_body(body)
    assert ticket == "456"
    assert not py_only
    assert not ts_only


def test_html_comment_with_marker_does_not_match() -> None:
    """Markers buried in an HTML comment must NOT satisfy the gate."""
    body = (
        "## Summary\n\nFoo bar.\n\n"
        "<!-- example:\nParity-Ticket: #999\npython_only: true — placeholder\n-->\n"
    )
    ticket, py_only, ts_only = parse_pr_body(body)
    assert ticket is None
    assert not py_only
    assert not ts_only


def test_fenced_code_block_with_marker_does_not_match() -> None:
    """Markers inside a fenced code block must NOT satisfy the gate."""
    body = (
        "## Summary\n\nFoo bar.\n\n"
        "```\nParity-Ticket: #999\ntypescript_only: true — example only\n```\n"
    )
    ticket, py_only, ts_only = parse_pr_body(body)
    assert ticket is None
    assert not py_only
    assert not ts_only


def test_python_only_outside_comment_matches() -> None:
    """A real `python_only: true` (outside any comment) must match."""
    body = "## Summary\n\npython_only: true — interim shim\n"
    ticket, py_only, ts_only = parse_pr_body(body)
    assert ticket is None
    assert py_only
    assert not ts_only


def test_typescript_only_outside_comment_matches() -> None:
    """A real `typescript_only: true` (outside any comment) must match."""
    body = "typescript_only: true — UI-only change\n"
    ticket, py_only, ts_only = parse_pr_body(body)
    assert ticket is None
    assert not py_only
    assert ts_only


def test_polymarket_client_ua_changes_are_paired_surface() -> None:
    """Python + TS Polymarket client UA edits must satisfy parity as paired."""
    py_globs, ts_globs = _load_config()
    files = [
        "packages/markets/src/mostlyright/markets/_polymarket_client.py",
        "packages-ts/markets/src/polymarket/client.ts",
    ]
    py_hits, ts_hits = _classify(files, py_globs, ts_globs)

    assert py_hits == ["packages/markets/src/mostlyright/markets/_polymarket_client.py"]
    assert ts_hits == ["packages-ts/markets/src/polymarket/client.ts"]
