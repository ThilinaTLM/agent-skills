"""Source-text rewriter used by ``richdoc lint --fix``.

The rewriter only kicks in when at least one fix is queued; it
serialises the modified lxml tree back to HTML while:

- Preserving the original ``<!doctype ...>`` declaration verbatim.
- Collapsing runs of three or more blank lines (a side effect of
  consecutive sibling removals) to a single blank line.
- Restoring the trailing newline if the source had one.

Whitespace-only tail text on removed nodes is dropped (the parent's
own ``.text`` / previous sibling's ``.tail`` already carries the
indentation gap). Non-whitespace tail text is migrated onto the
surviving previous sibling so author-visible text is never silently
lost.
"""

from __future__ import annotations

import re

import lxml.etree as ET
import lxml.html as LH

__all__ = ["remove_inline", "serialize_html"]


_BLANK_LINE_RUN_RE = re.compile(r"(?:[ \t]*\n){3,}")


def remove_inline(node: ET._Element) -> None:
    """Remove ``node`` from its parent, migrating any non-whitespace tail.

    Whitespace-only tail text is dropped \u2014 the surviving parent.text /
    previous-sibling ``.tail`` already carries the indentation gap
    between the surrounding elements, so migrating the tail would leave
    a blank indented line behind for every removed node.

    Non-whitespace tail text is migrated onto the previous sibling (or
    onto ``parent.text`` if ``node`` was the first child) so
    author-visible text is not silently lost.
    """
    parent = node.getparent()
    if parent is None:
        return
    tail = node.tail or ""
    if tail.strip():
        prev = node.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail
    parent.remove(node)


def serialize_html(root: ET._Element, *, original_source: str) -> str:
    """Serialise the modified tree back to HTML, preserving doctype +
    collapsing accidental blank-line runs."""
    body = LH.tostring(root, encoding="unicode", method="html")
    doctype = ""
    head = original_source[:512].lstrip()
    if head.lower().startswith("<!doctype"):
        end = original_source.find(">", 0, 512)
        if end != -1:
            doctype = original_source[: end + 1] + "\n"
    out = doctype + body
    out = _BLANK_LINE_RUN_RE.sub("\n\n", out)
    if original_source.endswith("\n") and not out.endswith("\n"):
        out += "\n"
    return out
