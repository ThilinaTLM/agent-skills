"""Shared text utilities for every export pipeline.

`dedent` was previously duplicated as three near-identical
implementations (md / docx / confluence). The differences (space-only
vs tab-aware, splitlines vs split, ...) were accidental drift; this
canonical implementation matches the runtime ``k()`` helper that
`<rd-code>` / `<rd-diff>` / `<rd-shell>` use in the browser \u2014 the same
shape the agent sees when authoring the doc.

Tabs and spaces are treated as one indent character each, mirroring
the JS `String.prototype.replace` semantics. Without tab awareness,
source HTML that nests ``<rd-code>`` inside ``<rd-section>`` (the
common case) would leave each code line prefixed with the surrounding
indent tabs.
"""

from __future__ import annotations

import re

__all__ = ["dedent"]

_INDENT_RE = re.compile(r"^[ \t]*")


def dedent(text: str) -> str:
    """Strip leading newlines, trailing whitespace, then remove the
    common leading indent (tabs and spaces) from every non-blank line.

    Equivalent to the JS runtime's ``k()`` helper used by code blocks.
    """
    text = text.lstrip("\n").rstrip()
    lines = text.split("\n")
    min_indent: int | None = None
    for line in lines:
        if not line.strip():
            continue
        m = _INDENT_RE.match(line)
        n = len(m.group(0)) if m else 0
        if min_indent is None or n < min_indent:
            min_indent = n
    if not min_indent:
        return "\n".join(lines)
    return "\n".join(
        line[min_indent:] if len(line) >= min_indent else line for line in lines
    )
