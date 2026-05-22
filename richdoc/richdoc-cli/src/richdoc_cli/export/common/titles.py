"""Shared title / chapter-label resolution.

The exporters and publisher all need to answer two near-identical
questions:

- "What's the canonical title of *this document*?" \u2014 used as the
  default chapter title in books, the page title on Confluence, the
  H1 in DOCX exports, etc.
- "What's the visible label of *this `<rd-chapter>` element*?" \u2014 the
  text content of the element with nested `<rd-chapter>` sub-trees
  stripped out, used everywhere a chapter is referenced by name.

Before this module the two questions had four near-identical
implementations spread across `book.py`, `pipeline.py`, and the
Confluence converter; the differences (whitespace normalisation, h1
text extraction) were accidental drift rather than intentional. The
canonical resolvers here accept an explicit
``normalize_whitespace_in_hero`` flag for the rare case where a caller
wants the raw author-typed title.
"""

from __future__ import annotations

import re

import lxml.etree as ET

from .walker import iter_text, text_of

__all__ = ["chapter_label", "resolve_doc_title"]

_WS = re.compile(r"\s+")


def resolve_doc_title(
    root: ET._Element,
    *,
    normalize_whitespace_in_hero: bool = False,
) -> str | None:
    """Find the canonical title of a richdoc document.

    Looks for, in order:

    1. ``<rd-hero title>``       (the visible doc title in nearly every
       template).
    2. The first ``<h1>``        (fallback when there's no hero).
    3. The ``<title>``           (last-resort, only used by the
       implicit single-file path).

    Returns ``None`` if none of the above produce a non-empty string.

    ``normalize_whitespace_in_hero=True`` collapses any run of inner
    whitespace in the hero title's attribute value down to a single
    space. The Confluence publisher uses this to keep page titles tidy
    when the author broke the attribute over multiple lines; book
    discovery keeps the raw value because it round-trips literally
    into the chapter file's TOC entry.
    """
    hero = next(iter(root.iter("rd-hero")), None)
    if hero is not None:
        t = hero.get("title")
        if t and t.strip():
            cleaned = t.strip()
            return _WS.sub(" ", cleaned) if normalize_whitespace_in_hero else cleaned
    h1 = next(iter(root.iter("h1")), None)
    if h1 is not None:
        text = " ".join(text_of(h1).split()).strip()
        if text:
            return text
    title_el = next(iter(root.iter("title")), None)
    if title_el is not None and title_el.text and title_el.text.strip():
        return title_el.text.strip()
    return None


def chapter_label(node: ET._Element) -> str:
    """Return the visible text of one ``<rd-chapter>`` element.

    Nested ``<rd-chapter>`` sub-trees are stripped out so a parent
    chapter doesn't accidentally pick up its children's titles.
    Whitespace is collapsed to a single space. Identical to the
    runtime's chapter-title extraction.
    """
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if isinstance(child.tag, str) and child.tag.lower() == "rd-chapter":
            if child.tail:
                parts.append(child.tail)
            continue
        parts.extend(iter_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split()).strip()
