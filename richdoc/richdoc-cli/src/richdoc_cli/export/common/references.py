"""Shared bibliography entry formatter.

Every export target renders citation entries in the same shape:

    Author. "Title" (linked to URL if present). Publisher. Date. Note.

\u2026 the only differences are the link / escape syntax. This module
exposes a single `format_ref` that builds the string from a citation
attribute dict and delegates the format-specific bits to a small set
of caller-supplied callables (`RefRenderer`):

- `escape(text)`     normalises author / title / publisher / date.
- `link(text, url)`  renders a link with visible text.
- `url_only(url)`    renders a bare URL when there's no title.

The md exporter passes pass-through callables that emit
``[text](url)`` / ``<url>``; the Confluence converter passes
xml-escaping + ``<a href="...">...</a>``. The docx exporter builds
references directly via runs and keeps its own renderer (paragraphs +
hyperlinks), so it doesn't consume this helper.

Reference attribute order is fixed at compile time so multiple exporters
emit the same bibliography ordering for the same input.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["RefRenderer", "format_ref"]


@dataclass(frozen=True)
class RefRenderer:
    """Format-specific bits a target plugs into ``format_ref``."""

    escape: Callable[[str], str]
    link: Callable[[str, str], str]
    url_only: Callable[[str], str]


def format_ref(attrs: dict[str, str], *, renderer: RefRenderer) -> str:
    """Render one bibliography entry as a single line of plain prose.

    Wrapping (e.g. ``<li>``) and joining (e.g. markdown ordered-list
    prefixes) are the caller's responsibility; this helper produces
    the inner text only.

    ``attrs`` is a dict with optional keys ``author`` / ``title`` /
    ``url`` / ``date`` / ``publisher`` / ``note``. ``note`` is appended
    verbatim (the caller is responsible for any required escaping).
    """
    author = (attrs.get("author") or "").strip()
    title = (attrs.get("title") or "").strip()
    url = (attrs.get("url") or "").strip()
    date = (attrs.get("date") or "").strip()
    publisher = (attrs.get("publisher") or "").strip()
    note = (attrs.get("note") or "").strip()

    bits: list[str] = []
    if author:
        bits.append(renderer.escape(author))
    if title:
        if url:
            bits.append(f'"{renderer.link(title, url)}"')
        else:
            bits.append(f'"{renderer.escape(title)}"')
    elif url:
        bits.append(renderer.url_only(url))
    if publisher:
        bits.append(renderer.escape(publisher))
    if date:
        bits.append(renderer.escape(date))
    line = ". ".join(bits) + ("." if bits else "")
    if note:
        line += f" {note}"
    return line
