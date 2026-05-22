"""Shared href classification.

`is_external_href` is the single source of truth for the question "does
this href point at something that should be left as-is in the rendered
output instead of resolved to a chapter / asset on disk?". It returns
True for:

- Empty hrefs (defensive; an empty link is a no-op).
- Fragment-only hrefs (`#section`).
- Anything that starts with `//` (protocol-relative).
- Anything with an explicit scheme (`http:`, `https:`, `mailto:`, ...).

Previously duplicated as `book.is_external_href` and as
`publish/confluence/pipeline._is_external`. `book.py` re-exports this
function for backwards compatibility with existing import paths.
"""

from __future__ import annotations

import re

__all__ = ["is_external_href"]

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def is_external_href(href: str | None) -> bool:
    """True when ``href`` points outside the book's chapter tree."""
    if href is None:
        return True
    s = href.strip()
    if not s:
        return True
    if s.startswith("#") or s.startswith("//"):
        return True
    return bool(_SCHEME_RE.match(s))
