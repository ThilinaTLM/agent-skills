"""Format-agnostic text utilities used by every exporter walker.

These helpers don't depend on a target document model — they operate on
strings and lxml elements only. The md and docx converters both consume
them, which keeps the two pipelines in lock-step on whitespace, dedenting,
and element-source extraction.
"""

from __future__ import annotations

import re

import lxml.etree as ET
import lxml.html as LH


_WHITESPACE = re.compile(r"\s+")


def parse_html(source: str) -> ET._Element:  # noqa: SLF001
    """Parse an HTML string in recover mode. Returns the document root."""
    parser = LH.HTMLParser(recover=True)
    return LH.document_fromstring(source, parser=parser)


def body_of(root: ET._Element) -> ET._Element:  # noqa: SLF001
    """Return the document body, or `root` if there's no <body>."""
    body = root.find(".//body")
    return body if body is not None else root


def inline_text(text: str) -> str:
    """Normalise whitespace in inline text nodes."""
    return _WHITESPACE.sub(" ", text)


def element_source(el: ET._Element) -> str:  # noqa: SLF001
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
            script_text = "".join(child.itertext())
            if script_text.strip():
                return script_text
    return "".join(el.itertext())


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
