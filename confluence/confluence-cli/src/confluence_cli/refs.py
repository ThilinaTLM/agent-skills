"""Parse Confluence page references.

Agents typically receive page references from a human in one of three
shapes:

* a bare numeric page id (``"123456"``);
* a public viewer URL of the form
  ``https://<site>/wiki/spaces/<KEY>/pages/<ID>[/<Title>]``;
* a URL carrying ``?pageId=<ID>`` in its query string (older share
  links).

The "tinylink" form (``https://<site>/wiki/x/<token>``) is *not*
resolved here \u2014 it requires a server redirect lookup. Callers should
expand it in a browser and re-run with the resulting full URL or id.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

__all__ = ["RefParseError", "parse_page_ref"]


_NUMERIC_RE = re.compile(r"^\d+$")
_PATH_PAGE_ID_RE = re.compile(r"/pages/(\d+)(?:/|$)")


class RefParseError(ValueError):
    """Raised when a page reference can't be parsed."""

    code = "INVALID_PARAMS"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


def parse_page_ref(value: str) -> str:
    """Return the numeric page id for ``value``.

    Accepts a bare id or a Confluence URL. Raises :class:`RefParseError`
    with an actionable hint when the input can't be resolved.
    """
    if not isinstance(value, str):
        raise RefParseError(
            f"Page reference must be a string, got {type(value).__name__}.",
            hint="Pass a numeric page id or a Confluence page URL.",
        )
    raw = value.strip()
    if not raw:
        raise RefParseError(
            "Page reference is empty.",
            hint="Pass a numeric page id or a Confluence page URL.",
        )

    if _NUMERIC_RE.match(raw):
        return raw

    if raw.startswith("http://") or raw.startswith("https://"):
        return _parse_url(raw)

    # Be tolerant of pasted paths without scheme.
    if raw.startswith("/wiki/"):
        return _parse_url("https://placeholder.invalid" + raw)

    raise RefParseError(
        f"Could not parse page reference {value!r}.",
        hint=(
            "Pass a numeric page id, a /wiki/spaces/<KEY>/pages/<ID>/\u2026 URL, "
            "or a URL with ?pageId=<ID>."
        ),
    )


def _parse_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""

    # Tinylinks need an HTTP redirect to resolve \u2014 reject explicitly.
    if "/wiki/x/" in path:
        raise RefParseError(
            "TinyLink URLs (/wiki/x/\u2026) cannot be resolved without a "
            "redirect lookup.",
            hint=(
                "Open the link in a browser to get the full "
                "/wiki/spaces/<KEY>/pages/<ID>/ URL, then re-run."
            ),
        )

    match = _PATH_PAGE_ID_RE.search(path)
    if match:
        return match.group(1)

    qs = parse_qs(parsed.query)
    page_id_values = qs.get("pageId") or qs.get("pageid")
    if page_id_values and _NUMERIC_RE.match(page_id_values[0]):
        return page_id_values[0]

    raise RefParseError(
        f"URL {url!r} does not contain a Confluence page id.",
        hint=(
            "Expected /wiki/spaces/<KEY>/pages/<ID>/\u2026 or a query string "
            "with ?pageId=<ID>."
        ),
    )
