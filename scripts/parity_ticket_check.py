#!/usr/bin/env python3
"""Parity-ticket gate for cross-SDK PRs.

Implements the rule from `.planning/CROSS-SDK-SYNC.md` §2.1:

If a PR diff touches any path matching `.github/parity-trigger-paths.json`
`python_paths` AND no corresponding TypeScript change is included in the same
diff AND the PR body does not carry a `Parity-Ticket: #<num>` line AND the PR
body does not carry a `python_only: true` / `typescript_only: true`
justification line, the gate FAILS (exit 1). The reverse rule applies for
TypeScript-only diffs that touch `typescript_paths`.

Invoked by `.github/workflows/parity-ticket-check.yml`. Standard library only.

CLI:
    python scripts/parity_ticket_check.py \
        --pr-body "<full PR body as a string>" \
        --base origin/main \
        --head HEAD \
        --label-list "label1,label2,label3"

Exit codes:
    0 — clean (rule satisfied or rule does not apply)
    1 — gate violation (touches trigger surface without parity opt-out)
    2 — internal error (config missing, git failure, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
CONFIG_PATH: Final[Path] = REPO_ROOT / ".github" / "parity-trigger-paths.json"

# Recognized opt-out markers in the PR body. Both `Parity-Ticket: #N` and the
# bare-flag forms are accepted (the latter satisfies CROSS-SDK-SYNC.md §6.4).
_PARITY_TICKET_RE: Final[re.Pattern[str]] = re.compile(r"^\s*Parity-Ticket:\s*#(\d+)", re.MULTILINE)
_PYTHON_ONLY_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*python_only:\s*true\b", re.IGNORECASE | re.MULTILINE
)
_TYPESCRIPT_ONLY_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*typescript_only:\s*true\b", re.IGNORECASE | re.MULTILINE
)

# HTML comment (`<!-- ... -->`) — non-greedy, multi-line. Stripped from the PR
# body before opt-out regexes run so the unchanged PR template (which carries
# example markers inside an HTML comment) cannot bypass the parity gate.
# See TS-W0 iter-1 CRITICAL 2.
_HTML_COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"<!--.*?-->", re.DOTALL)
# Fenced code block (``` ... ```) — also stripped before regex parsing. Lets
# us document example markers in the template inside a fenced block without
# the parser mistaking them for real markers.
_FENCED_CODE_BLOCK_RE: Final[re.Pattern[str]] = re.compile(r"```.*?```", re.DOTALL)


def _strip_inert_regions(body: str) -> str:
    """Strip HTML comments + fenced code blocks before parsing opt-out markers.

    The PR template carries example markers inside an HTML comment AND/OR
    inside a fenced code block — both are inert to readers, and neither
    should satisfy the parity gate.
    """
    body = _HTML_COMMENT_RE.sub("", body)
    body = _FENCED_CODE_BLOCK_RE.sub("", body)
    return body

# Labels that satisfy the gate.
_LABEL_PYTHON_ONLY: Final[str] = "python_only"
_LABEL_TYPESCRIPT_ONLY: Final[str] = "typescript_only"
_LABEL_PARITY_TICKETED: Final[str] = "parity-ticketed"


def _load_config() -> tuple[list[str], list[str]]:
    """Load python + typescript trigger-path globs from the JSON config."""
    if not CONFIG_PATH.exists():
        print(
            f"::error::parity-trigger-paths config missing at {CONFIG_PATH}",
            file=sys.stderr,
        )
        sys.exit(2)
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    py = list(raw.get("python_paths", []))
    ts = list(raw.get("typescript_paths", []))
    if not isinstance(py, list) or not isinstance(ts, list):
        print(
            "::error::parity-trigger-paths.json malformed: expected arrays "
            "for python_paths and typescript_paths",
            file=sys.stderr,
        )
        sys.exit(2)
    return py, ts


def _git_diff_files(base: str, head: str) -> list[str]:
    """Return the list of files changed between `base` and `head`.

    Falls back to `git diff --name-only HEAD~1 HEAD` if the explicit refs
    aren't resolvable in the CI checkout (shallow clone edge case).
    """
    candidates: list[list[str]] = [
        ["git", "diff", "--name-only", f"{base}...{head}"],
        ["git", "diff", "--name-only", base, head],
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
    ]
    last_err: str = ""
    for cmd in candidates:
        try:
            out = subprocess.check_output(cmd, cwd=REPO_ROOT, stderr=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as exc:
            last_err = exc.stderr or str(exc)
            continue
        files = [line.strip() for line in out.splitlines() if line.strip()]
        return files
    print(
        f"::error::Could not compute PR diff (tried base={base!r} head={head!r}): "
        f"{last_err.strip()}",
        file=sys.stderr,
    )
    sys.exit(2)


def _glob_to_regex(pattern: str) -> str:
    """Translate a gitignore-style glob into a fullmatch regex.

    Rules implemented (matches the subset we need for parity-trigger-paths):
    - `**/` matches zero-or-more directory segments (so `a/**/b.py` matches
      `a/b.py`, `a/x/b.py`, and `a/x/y/b.py`).
    - `**` alone matches any path.
    - `*` matches any chars except `/`.
    - `?` matches any single char except `/`.
    - Regex metacharacters in the rest of the pattern are escaped.
    """
    result: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        # `**/` -> zero-or-more directories.
        if pattern.startswith("**/", i):
            result.append("(?:.*/)?")
            i += 3
            continue
        # `/**` at end -> zero-or-more trailing segments.
        if pattern.startswith("/**", i) and i + 3 == n:
            result.append("(?:/.*)?")
            i += 3
            continue
        # Bare `**` (no path delimiter) -> any chars including `/`.
        if pattern.startswith("**", i):
            result.append(".*")
            i += 2
            continue
        if ch == "*":
            result.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            result.append("[^/]")
            i += 1
            continue
        if ch in r".^$+{}[]|()\\":
            result.append(re.escape(ch))
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _matches_any(path: str, globs: list[str]) -> bool:
    """Return True if `path` matches any glob in `globs`.

    Uses a gitignore-style translator (`_glob_to_regex`) rather than the
    stdlib `fnmatch` module because fnmatch does NOT special-case `**` (it
    treats `*` as matching any chars including `/`, which is wrong for our
    purposes — we want `*` confined to a single path segment and `**` to
    cross segments).
    """
    for pattern in globs:
        regex = _glob_to_regex(pattern)
        if re.fullmatch(regex, path):
            return True
    return False


def _classify(
    files: list[str], py_globs: list[str], ts_globs: list[str]
) -> tuple[list[str], list[str]]:
    """Split changed files into (python-trigger, typescript-trigger) hits."""
    py_hits = [f for f in files if _matches_any(f, py_globs)]
    ts_hits = [f for f in files if _matches_any(f, ts_globs)]
    return py_hits, ts_hits


def _parse_labels(label_csv: str) -> set[str]:
    return {label.strip() for label in label_csv.split(",") if label.strip()}


def parse_pr_body(body: str) -> tuple[str | None, bool, bool]:
    """Parse opt-out markers from a PR body.

    Returns ``(parity_ticket, python_only, typescript_only)`` where
    ``parity_ticket`` is the matched ticket id string (e.g. ``"123"``) or
    ``None`` if no marker is found.

    HTML comments + fenced code blocks are stripped before regex parsing so
    the PR template's example markers cannot bypass the parity gate (TS-W0
    iter-1 CRITICAL 2).
    """
    cleaned = _strip_inert_regions(body)
    ticket_match = _PARITY_TICKET_RE.search(cleaned)
    ticket = ticket_match.group(1) if ticket_match else None
    python_only = bool(_PYTHON_ONLY_RE.search(cleaned))
    typescript_only = bool(_TYPESCRIPT_ONLY_RE.search(cleaned))
    return ticket, python_only, typescript_only


def _render_failure_comment(py_hits: list[str], ts_hits: list[str], direction: str) -> str:
    """Format the structured failure message printed to stdout + CI logs."""
    if direction == "python":
        canonical_label = "`python_only: true`"
        paired_label = "TypeScript"
        sample = (
            "Parity-Ticket: #123\n"
            "or\n"
            "python_only: true — interim shim for mostly-light migration"
        )
        hits = py_hits
    else:
        canonical_label = "`typescript_only: true`"
        paired_label = "Python"
        sample = (
            "Parity-Ticket: #123\n"
            "or\n"
            "typescript_only: true — UI helper specific to Chrome extension overlay"
        )
        hits = ts_hits
    lines = [
        "Parity-ticket gate FAILED.",
        "",
        f"This PR touches the parity-trigger surface ({direction} side) and",
        f"does NOT include a paired {paired_label} change, a "
        "`Parity-Ticket: #<num>` reference, or a",
        f"{canonical_label} justification.",
        "",
        "Add ONE of the following to the PR body:",
        "",
        sample,
        "",
        "Trigger-matching files in this diff:",
        *[f"  - {p}" for p in sorted(hits)[:25]],
    ]
    if len(hits) > 25:
        lines.append(f"  ... and {len(hits) - 25} more")
    lines.extend(
        [
            "",
            "See `.planning/CROSS-SDK-SYNC.md` §2 for the full workflow and",
            "`.github/parity-trigger-paths.json` for the surface definition.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-body", default="", help="Full PR body text")
    parser.add_argument("--base", default="origin/main", help="Base git ref for diff")
    parser.add_argument("--head", default="HEAD", help="Head git ref for diff")
    parser.add_argument(
        "--label-list",
        default="",
        help="Comma-separated PR label names (from github.event.pull_request.labels)",
    )
    args = parser.parse_args(argv)

    py_globs, ts_globs = _load_config()
    files = _git_diff_files(args.base, args.head)
    py_hits, ts_hits = _classify(files, py_globs, ts_globs)
    labels = _parse_labels(args.label_list)

    parsed_ticket, parsed_py_only, parsed_ts_only = parse_pr_body(args.pr_body)
    has_parity_ticket = parsed_ticket is not None
    has_python_only = parsed_py_only or (_LABEL_PYTHON_ONLY in labels)
    has_typescript_only = parsed_ts_only or (_LABEL_TYPESCRIPT_ONLY in labels)
    has_parity_label = _LABEL_PARITY_TICKETED in labels

    # No trigger-surface touched → gate does not apply.
    if not py_hits and not ts_hits:
        print("parity-ticket-check: PR does not touch parity-trigger surface; " "gate skipped.")
        return 0

    # Paired-language diff present → gate satisfied irrespective of body.
    if py_hits and ts_hits:
        print(
            "parity-ticket-check: PR touches BOTH Python and TypeScript "
            "trigger surfaces — paired-language change satisfies the gate."
        )
        return 0

    # Python-only diff that touches trigger surface.
    if py_hits and not ts_hits:
        if has_parity_ticket or has_python_only or has_parity_label:
            print(
                "parity-ticket-check: Python-side trigger surface touched; "
                "opt-out satisfied (parity ticket, python_only flag, or label)."
            )
            return 0
        msg = _render_failure_comment(py_hits, ts_hits, "python")
        print(msg)
        print(f"::error::{msg.splitlines()[0]}")
        return 1

    # TypeScript-only diff that touches trigger surface.
    if ts_hits and not py_hits:
        if has_parity_ticket or has_typescript_only or has_parity_label:
            print(
                "parity-ticket-check: TS-side trigger surface touched; "
                "opt-out satisfied (parity ticket, typescript_only flag, or label)."
            )
            return 0
        msg = _render_failure_comment(py_hits, ts_hits, "typescript")
        print(msg)
        print(f"::error::{msg.splitlines()[0]}")
        return 1

    # Defensive: unreachable.
    return 0


if __name__ == "__main__":
    sys.exit(main())
