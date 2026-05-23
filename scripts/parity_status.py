#!/usr/bin/env python3
"""Release-readiness gate: list open parity tickets per milestone.

Implements TS-SYNC-02 from `.planning/REQUIREMENTS.md`. Consumed by the
release-readiness checklist for both Python and TS SDKs. Exits non-zero when
any P0 (release-blocker) parity ticket is open against the requested
milestone — wire this into release workflows to refuse publish on a non-empty
P0 list.

Data sources, in order of preference:

1. GitHub Issues via `gh issue list --label parity-ticket --json ...`
   (preferred — issues are the canonical surface per CROSS-SDK-SYNC.md §2.2).
2. Filesystem fallback: walk `.planning/parity-tickets/*.md` and parse the
   YAML-style front-matter section (lines like `**Milestone:** ...`,
   `**Priority:** ...`, `**State:** ...`) at the top of each ticket.

The fallback is intentional: CROSS-SDK-SYNC.md §2.2 explicitly allows ticket
files under `.planning/parity-tickets/` as a git-only alternative to GitHub
issues, so the script must be useful in offline/airgapped reviews too.

CLI:
    python scripts/parity_status.py --milestone "TS v0.1.0"

Exit codes:
    0 — release-ready (no open P0 against the milestone)
    1 — open P0 ticket(s) found OR internal error
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
TICKET_DIR: Final[Path] = REPO_ROOT / ".planning" / "parity-tickets"

_OPEN_STATES: Final[frozenset[str]] = frozenset({"filed", "in_progress", "open"})
_CLOSED_STATES: Final[frozenset[str]] = frozenset(
    {"resolved", "accepted_drift", "cancelled", "closed"}
)


@dataclass(frozen=True)
class Ticket:
    """One parity ticket, normalized across the two data sources."""

    identifier: str  # GH issue number ("123") or filename stem ("PT-0042-foo")
    title: str
    priority: str  # "P0" | "P1" | "P2" | "" (unknown)
    milestone: str  # exact milestone string as filed (or "")
    state: str  # "open" | "closed"
    url: str  # gh URL or relative file path


# ---------------------------------------------------------------------------
# Source 1: GitHub Issues (preferred)
# ---------------------------------------------------------------------------


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _fetch_from_gh(milestone: str) -> list[Ticket] | None:
    """Fetch parity tickets via gh CLI; return None on any failure.

    Returns tickets across BOTH open and closed states so that the caller can
    surface accurate counts; filtering by milestone happens here.
    """
    cmd = [
        "gh",
        "issue",
        "list",
        "--label",
        "parity-ticket",
        "--state",
        "all",
        "--limit",
        "500",
        "--json",
        "number,title,state,labels,milestone,url",
    ]
    try:
        out = subprocess.check_output(cmd, cwd=REPO_ROOT, stderr=subprocess.PIPE, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return None
    tickets: list[Ticket] = []
    for entry in raw:
        ms = entry.get("milestone") or {}
        ms_title = (ms.get("title") if isinstance(ms, dict) else "") or ""
        if milestone and ms_title != milestone:
            continue
        labels = [
            (lbl.get("name") or "") for lbl in (entry.get("labels") or []) if isinstance(lbl, dict)
        ]
        priority = _priority_from_labels(labels)
        raw_state = (entry.get("state") or "").lower()
        state = "open" if raw_state == "open" else "closed"
        tickets.append(
            Ticket(
                identifier=f"#{entry.get('number', '?')}",
                title=entry.get("title", "") or "",
                priority=priority,
                milestone=ms_title,
                state=state,
                url=entry.get("url", "") or "",
            )
        )
    return tickets


def _priority_from_labels(labels: list[str]) -> str:
    for lbl in labels:
        normalized = lbl.strip().lower()
        if normalized in {"p0", "priority:p0", "priority/p0"}:
            return "P0"
        if normalized in {"p1", "priority:p1", "priority/p1"}:
            return "P1"
        if normalized in {"p2", "priority:p2", "priority/p2"}:
            return "P2"
    return ""


# ---------------------------------------------------------------------------
# Source 2: Filesystem fallback (.planning/parity-tickets/*.md)
# ---------------------------------------------------------------------------

_FIELD_RE: Final[re.Pattern[str]] = re.compile(
    r"^\*\*(?P<key>[A-Za-z][\w \-/]*?)\*\*:\s*(?P<value>.+?)\s*$",
    re.MULTILINE,
)


def _fetch_from_filesystem(milestone: str) -> list[Ticket]:
    """Walk `.planning/parity-tickets/*.md` and parse front-matter."""
    if not TICKET_DIR.exists():
        return []
    tickets: list[Ticket] = []
    for path in sorted(TICKET_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fields: dict[str, str] = {}
        for match in _FIELD_RE.finditer(text):
            key = match.group("key").strip().lower()
            value = match.group("value").strip()
            # Strip surrounding brackets like "[P0 (release-blocker) | P1 | P2]"
            # so unfilled templates don't masquerade as priorities.
            if value.startswith("[") and value.endswith("]"):
                continue
            fields.setdefault(key, value)
        ms = fields.get("milestone", "")
        if milestone and ms != milestone:
            continue
        priority_raw = fields.get("priority", "")
        priority = _priority_from_text(priority_raw)
        state_raw = fields.get("state", "filed").strip().lower()
        state = "open" if state_raw in _OPEN_STATES else "closed"
        # Title heuristic: first H1 line.
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        tickets.append(
            Ticket(
                identifier=path.stem,
                title=title,
                priority=priority,
                milestone=ms,
                state=state,
                url=str(path.relative_to(REPO_ROOT)),
            )
        )
    return tickets


def _priority_from_text(value: str) -> str:
    value_upper = value.upper()
    if value_upper.startswith("P0"):
        return "P0"
    if value_upper.startswith("P1"):
        return "P1"
    if value_upper.startswith("P2"):
        return "P2"
    return ""


# ---------------------------------------------------------------------------
# CLI driver
# ---------------------------------------------------------------------------


def _collect(milestone: str) -> tuple[list[Ticket], str]:
    """Return (tickets, source) where source identifies which backend served."""
    if _gh_available():
        tickets = _fetch_from_gh(milestone)
        if tickets is not None:
            return tickets, "gh"
    return _fetch_from_filesystem(milestone), "filesystem"


def _format_report(milestone: str, tickets: list[Ticket], source: str) -> str:
    open_tickets = [t for t in tickets if t.state == "open"]
    p0 = [t for t in open_tickets if t.priority == "P0"]
    p1 = [t for t in open_tickets if t.priority == "P1"]
    p2 = [t for t in open_tickets if t.priority == "P2"]
    unknown = [t for t in open_tickets if t.priority == ""]
    lines: list[str] = [
        f"Parity ticket status for milestone: {milestone or '(all)'}",
        f"Source: {source}",
        f"Total tracked: {len(tickets)} (open: {len(open_tickets)}, "
        f"closed: {len(tickets) - len(open_tickets)})",
        "",
        f"P0 open: {len(p0)}",
    ]
    for ticket in p0:
        lines.append(f"  - {ticket.identifier} {ticket.title} ({ticket.url})")
    lines.append(f"P1 open: {len(p1)}")
    for ticket in p1:
        lines.append(f"  - {ticket.identifier} {ticket.title} ({ticket.url})")
    lines.append(f"P2 open: {len(p2)}")
    for ticket in p2:
        lines.append(f"  - {ticket.identifier} {ticket.title} ({ticket.url})")
    if unknown:
        lines.append(f"Priority unset (open): {len(unknown)}")
        for ticket in unknown:
            lines.append(f"  - {ticket.identifier} {ticket.title} ({ticket.url})")
    release_ready = "YES" if not p0 else "NO"
    lines.append("")
    lines.append(f"release-ready: {release_ready}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--milestone",
        default="",
        help="Milestone to filter by (e.g. 'TS v0.1.0'). Empty = all.",
    )
    args = parser.parse_args(argv)
    tickets, source = _collect(args.milestone)
    report = _format_report(args.milestone, tickets, source)
    print(report)
    open_p0 = [t for t in tickets if t.state == "open" and t.priority == "P0"]
    return 0 if not open_p0 else 1


if __name__ == "__main__":
    sys.exit(main())
