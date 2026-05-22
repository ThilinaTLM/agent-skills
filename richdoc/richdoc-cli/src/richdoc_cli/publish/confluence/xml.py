"""Storage-format XML helpers.

`xml_escape` / `xml_attr` produce safely escaped strings for body text
and attribute values. `th_bold` and `cdata_safe` are component-helper
shortcuts that show up in several handlers. `_BLOCK_OPENER` is the
regex `state.render_block_inner_wrapped` uses to detect whether an
already-rendered fragment starts with a block-level tag.
"""

from __future__ import annotations

import re

__all__ = [
    "BLOCK_OPENER",
    "cdata_safe",
    "th_bold",
    "xml_attr",
    "xml_escape",
]


def xml_escape(text: str) -> str:
    """Escape ``&`` / ``<`` / ``>`` / ``"`` / ``'`` for inclusion in an XML body."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def xml_attr(text: str) -> str:
    """Escape a value going into an XML attribute. (Same as `xml_escape`
    today; kept as a separate name for the call site to read clearly.)"""
    return xml_escape(text)


def th_bold(inner_xml: str) -> str:
    """Build a ``<th>`` cell whose inline content renders bold in Confluence's
    modern editor.

    Confluence does not auto-bold ``<th>`` in its modern table renderer;
    only a light grey background distinguishes header cells. Wrapping
    the cell body in ``<p><strong>...</strong></p>`` matches the shape
    Atlassian's own templates emit and survives the storage-format
    round-trip when pages are pushed via the v2 API.

    The empty-cell fallback (``&#160;``) keeps an empty header cell at
    the usual cell height instead of collapsing to a thin sliver.
    """
    return f"<th><p><strong>{inner_xml or '&#160;'}</strong></p></th>"


def cdata_safe(text: str) -> str:
    """Escape any embedded ``]]>`` so ``text`` is safe inside a CDATA block.

    Splits each ``]]>`` into ``]]]]><![CDATA[>`` so each half lives in
    its own CDATA section.
    """
    return text.replace("]]>", "]]]]><![CDATA[>")


BLOCK_OPENER = re.compile(
    r"^<(?:h[1-6]|p|ul|ol|li|table|thead|tbody|tr|th|td|blockquote|hr|pre|"
    r"figure|figcaption|div|ac:structured-macro|ac:layout|ac:image|ac:task-list)\b",
    re.IGNORECASE,
)
