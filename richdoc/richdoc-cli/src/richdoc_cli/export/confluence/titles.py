"""Title resolution for the Confluence converter.

Thin wrapper around the canonical implementation in
``export.common.titles.resolve_doc_title``. The Confluence publisher
passes ``normalize_whitespace_in_hero=True`` so multi-line
``<rd-hero title>`` attributes collapse to a single line on the page
title (Confluence renders the title verbatim with no further
normalisation).
"""

from __future__ import annotations

import lxml.etree as ET

from ..common.titles import resolve_doc_title

__all__ = ["resolve_title"]


def resolve_title(root: ET._Element) -> str | None:
    """Return the resolved page title for one richdoc HTML document."""
    return resolve_doc_title(root, normalize_whitespace_in_hero=True)
