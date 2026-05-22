"""Format-agnostic text utilities used by every exporter walker.

These helpers don't depend on a target document model — they operate on
strings and lxml elements only. The md and docx converters both consume
them, which keeps the two pipelines in lock-step on whitespace, dedenting,
and element-source extraction.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import lxml.etree as ET
import lxml.html as LH

__all__ = [
    "body_of",
    "element_source",
    "inline_text",
    "iter_text",
    "parse_html",
    "sourceline_of",
    "text_of",
]

_WHITESPACE = re.compile(r"\s+")


def parse_html(source: str) -> ET._Element:
    """Parse an HTML string in recover mode. Returns the document root."""
    parser = LH.HTMLParser(recover=True)
    return LH.document_fromstring(source, parser=parser)


def sourceline_of(el: ET._Element) -> int | None:
    """Return ``el.sourceline`` as ``int | None``.

    Works around an lxml-stubs declaration
    (``sourceline = ...  # Optional[int]``) that mypy parses as the
    literal ``EllipsisType`` instead of the type in the comment. Routing
    every read through this helper keeps the call sites clean.
    """
    value = getattr(el, "sourceline", None)
    return value if isinstance(value, int) else None


def body_of(root: ET._Element) -> ET._Element:
    """Return the document body, or `root` if there's no <body>."""
    body = root.find(".//body")
    return body if body is not None else root


def inline_text(text: str) -> str:
    """Normalise whitespace in inline text nodes."""
    return _WHITESPACE.sub(" ", text)


def iter_text(el: ET._Element) -> Iterator[str]:
    """Iterate `el.itertext()` as ``Iterator[str]``.

    lxml-stubs declares ``el.itertext()`` as ``Iterator[str | bytes]``
    because the underlying C API can in principle yield bytes. In
    practice HTML/XML parsed by lxml always yields ``str``; this helper
    filters the union narrow so call sites stay clean.
    """
    for chunk in el.itertext():
        if isinstance(chunk, str):
            yield chunk


def text_of(el: ET._Element) -> str:
    """Concatenate every descendant text node of `el` as a single string.

    Shortcut for ``"".join(iter_text(el))``; used wherever code currently
    writes ``"".join(el.itertext())``.
    """
    return "".join(iter_text(el))


def element_source(el: ET._Element) -> str:
    """Return the literal source text of a leaf code-like element.

    Mirrors the JS runtime's `this.textContent` semantics: prefer a
    `<script type="text/...">` child if present (used to embed source
    without HTML escaping), otherwise concatenate every descendant text
    node.
    """
    for child in el:
        if not isinstance(child.tag, str):
            continue
        if child.tag.lower() == "script":
            script_text = text_of(child)
            if script_text.strip():
                return script_text
    return text_of(el)


# NOTE: `dedent()` is intentionally NOT here.
#
# The md and docx converters have two near-identical but not byte-equivalent
# dedent implementations:
#
#   md:   text.lstrip('\n').rstrip() + split('\n') + re-based [ \t]* indent
#   docx: splitlines() + pop blank head/tail + space-only indent
#
# Unifying them risks changing docx output for inputs with mixed-tab
# indentation. Each format keeps its local `_dedent` until we have an
# explicit migration backed by a parametrized test.
