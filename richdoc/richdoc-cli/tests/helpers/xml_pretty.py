"""Pretty-print Confluence storage XML for snapshot testing.

The publish converter emits XML as a single line of densely-packed
markup. Pretty-printing it makes snapshot diffs readable. We wrap the
fragment in a ``<root xmlns:ac="…">`` so lxml understands the
``ac:`` / ``ri:`` / ``at:`` prefixes; the wrapper is stripped before
returning.

Whitespace inside ``<![CDATA[...]]>`` blocks is preserved verbatim
because Confluence treats CDATA bodies as significant (rd-code).
"""

from __future__ import annotations

import re

import lxml.etree as ET

_AC_NS = "http://atlassian.com/content"
_RI_NS = "http://atlassian.com/resource/identifier"
_AT_NS = "http://www.w3.org/1999/xlink"

_NS_DECL_RE = re.compile(
    r' xmlns:(?:ac|ri|at)="(?:'
    + re.escape(_AC_NS)
    + "|"
    + re.escape(_RI_NS)
    + "|"
    + re.escape(_AT_NS)
    + ')"'
)


def pretty_storage_xml(fragment: str) -> str:
    """Return `fragment` pretty-printed, or the original string if it
    can't be parsed (we never want a test to fail on the prettifier;
    raw output is still snapshot-worthy)."""
    if not fragment.strip():
        return ""
    wrapped = (
        f'<root xmlns:ac="{_AC_NS}" xmlns:ri="{_RI_NS}" xmlns:at="{_AT_NS}">'
        f"{fragment}</root>"
    )
    parser = ET.XMLParser(strip_cdata=False, remove_blank_text=True)
    try:
        root = ET.fromstring(wrapped, parser)
    except ET.XMLSyntaxError:
        return fragment

    out = ET.tostring(root, pretty_print=True, encoding="unicode")
    # Strip the synthetic <root …> open + </root> close.
    out = out.strip()
    if out.startswith("<root"):
        first_close = out.index(">")
        out = out[first_close + 1 :]
    if out.endswith("</root>"):
        out = out[: -len("</root>")]
    out = _NS_DECL_RE.sub("", out)
    return out.strip()
