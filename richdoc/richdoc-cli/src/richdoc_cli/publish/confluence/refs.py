"""Bibliography rendering for the Confluence converter.

Thin wrapper around the canonical
``export.common.references.format_ref``: the only differences from the
markdown exporter are the link / escape shape, which we plug in via a
``RefRenderer``.

The result is wrapped in ``<li>...</li>`` so the converter can emit a
fully-formed ``<ol>`` body.
"""

from __future__ import annotations

from ...export.common.references import RefRenderer, format_ref
from .xml import xml_attr, xml_escape

__all__ = ["format_ref_li"]


_CONFLUENCE_RENDERER = RefRenderer(
    escape=xml_escape,
    link=lambda text, url: f'<a href="{xml_attr(url)}">{xml_escape(text)}</a>',
    url_only=lambda url: f'<a href="{xml_attr(url)}">{xml_escape(url)}</a>',
)


def format_ref_li(attrs: dict[str, str]) -> str:
    """Render one bibliography entry as an ``<li>``.

    The ``note`` attribute is appended verbatim (it is already XML \u2014
    callers that collect ``rd-ref`` attributes pre-escape it).
    """
    return f"<li>{format_ref(attrs, renderer=_CONFLUENCE_RENDERER)}</li>"
