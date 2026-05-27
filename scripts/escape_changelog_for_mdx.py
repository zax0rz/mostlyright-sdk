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

# Fenced-code-block opener. Captures the leading whitespace (indent), the
# fence run (3+ backticks OR 3+ tildes), and the trailing info-string.
# Markdown spec (CommonMark §4.5): a fence closes only on a line whose
# fence run is ≥ the opener's length AND uses the same character. Inner
# fences shorter than the opener stay inside the block.
_FENCE_RE = re.compile(r"^(?P<indent>\s{0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")

# Paired inline-code span: backtick + non-backtick body + backtick.
# Treats `text` as code, leaving stray unmatched backticks alone.
# CommonMark allows multi-backtick spans (``code with ` in it``); for
# CHANGELOG prose, single-backtick spans dominate. The pattern below is
# greedy on the inner body but bounded by the next backtick — matches
# both ``code`` and `code`. Unmatched backticks are left as literals in
# the surrounding "outside" portion so the JSX-hostile escapes still
# fire on the rest of the line (PR #34 iter-2 codex HIGH fix).
_INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")


def _escape_outside_code(line: str) -> str:
    parts: list[str] = []
    last_end = 0
    for m in _INLINE_CODE_RE.finditer(line):
        # Escape the prose stretch between the previous span and this one.
        outside = line[last_end : m.start()]
        outside = _TAG_OPEN_RE.sub("&lt;", outside)
        outside = _JSX_EXPR_RE.sub("&#123;", outside)
        parts.append(outside)
        # Keep the inline-code span verbatim.
        parts.append(m.group(0))
        last_end = m.end()
    # Escape the tail (after the last span, or the whole line if no spans).
    tail = line[last_end:]
    tail = _TAG_OPEN_RE.sub("&lt;", tail)
    tail = _JSX_EXPR_RE.sub("&#123;", tail)
    parts.append(tail)
    return "".join(parts)


def escape(stream: Iterator[str]) -> Iterator[str]:
    """Yield escaped lines (including trailing newline).

    Tracks fenced-code-block state with proper close-fence semantics
    (matching character + ≥ opening length). Inner shorter fences inside
    a longer outer fence are passed through verbatim, not treated as
    closes (PR #34 iter-2 codex HIGH fix — nested fence handling).
    """
    in_fence_char: str = ""  # "" = not in fence, else "`" or "~"
    in_fence_len: int = 0
    for raw in stream:
        line = raw.rstrip("\n")
        m = _FENCE_RE.match(line)
        if m:
            run = m.group("fence")
            ch = run[0]
            run_len = len(run)
            if in_fence_char == "":
                # Opening fence.
                in_fence_char = ch
                in_fence_len = run_len
            elif ch == in_fence_char and run_len >= in_fence_len:
                # Matching-char close fence of sufficient length.
                in_fence_char = ""
                in_fence_len = 0
            # Else: inner shorter fence — stay in-fence.
            yield raw
            continue
        if in_fence_char != "":
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
