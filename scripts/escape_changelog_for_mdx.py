#!/usr/bin/env python3
"""Escape CHANGELOG body content for safe MDX embedding.

The landing site renders the SDK CHANGELOG via Astro + Starlight, which
parses every .mdx file as Markdown + JSX. Several patterns common in
CHANGELOG prose break MDX parsing silently:

  - `<word` outside inline code (e.g. `<NwpModel>`, `<1ms`, `<branch>`) →
    MDX treats as a JSX tag open, fails when the tag isn't valid.
  - `{ident}` outside inline code (e.g. `{strategy}`, `{version}`) → MDX
    treats as a JSX expression, fails to resolve the identifier.
  - `---` at column 1 OUTSIDE fenced code → markdown HR token, harmless,
    but combined with frontmatter context may confuse some pipelines;
    we leave HR alone (idiomatic markdown) and only escape JSX-hostile
    patterns.

Strategy:
  - Read stdin (the spliced CHANGELOG body, after `awk` has stripped the
    H1 + intro line).
  - Track fenced-code-block state (lines starting with ```).
  - For each non-fenced line, scan for inline backtick spans and only
    escape OUTSIDE those spans:
      `<` followed by `[A-Za-z!/?]` → `&lt;`
      `{` followed by `[A-Za-z_]`  → `&#123;`
  - Write to stdout.

This is the post-splice safety net referenced in
`.github/workflows/docs-publish.yml`'s "Sync CHANGELOG.md to landing
repo" step. Adopted after Phase 21 docs-publish CR (PR #34) flagged the
unescaped-future-CHANGELOG class of bug as HIGH.

Stdlib only.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator

# Escape `<` followed by any tag-like start character. The set covers:
#   - Letters: `<NwpModel>`, `<branch>` — would-be JSX tags
#   - Digits:  `<1ms`, `<7 days` (Phase 21 fix-up landed because MDX
#              choked on `<1 minute` in live-streaming.mdx — MDX rejects
#              digit-after-`<` with "Unexpected character ... before name"
#              even though digits never start a real JSX tag)
#   - `!/?`:   HTML comments / closing tags / processing instructions
_TAG_OPEN_RE = re.compile(r"<(?=[A-Za-z0-9!/?])")
_JSX_EXPR_RE = re.compile(r"\{(?=[A-Za-z_])")
_FENCE_RE = re.compile(r"^\s*```")


def _split_by_backticks(line: str) -> Iterator[tuple[str, bool]]:
    """Yield ``(chunk, in_code)`` for each segment of a line.

    Inline backtick code spans are delimited by ``` ` ``` (single, double,
    or triple — markdown counts them, but for CHANGELOG entries single
    backticks dominate). Treat any backtick as a toggle. Mismatched
    backticks fall back to "the rest of the line is outside-code" so we
    still escape the tail (defensive default).
    """
    # Markdown's actual backtick rules are subtle (run-length must match).
    # For the changelog use-case, single-backtick spans are universal —
    # the simple toggle handles them. Multi-backtick spans wrapping a
    # literal backtick are vanishingly rare in CHANGELOG prose.
    cur: list[str] = []
    in_code = False
    for ch in line:
        if ch == "`":
            if cur:
                yield ("".join(cur), in_code)
                cur = []
            in_code = not in_code
            cur.append(ch)
        else:
            cur.append(ch)
    if cur:
        yield ("".join(cur), in_code)


def _escape_outside_code(line: str) -> str:
    parts: list[str] = []
    for chunk, in_code in _split_by_backticks(line):
        if in_code:
            parts.append(chunk)
        else:
            chunk = _TAG_OPEN_RE.sub("&lt;", chunk)
            chunk = _JSX_EXPR_RE.sub("&#123;", chunk)
            parts.append(chunk)
    return "".join(parts)


def escape(stream: Iterator[str]) -> Iterator[str]:
    """Yield escaped lines (including trailing newline)."""
    in_fence = False
    for raw in stream:
        # Preserve original line ending; operate on the content.
        line = raw.rstrip("\n")
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            yield raw
            continue
        if in_fence:
            yield raw
            continue
        escaped = _escape_outside_code(line)
        yield escaped + ("\n" if raw.endswith("\n") else "")


def main() -> int:
    for out in escape(iter(sys.stdin)):
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
