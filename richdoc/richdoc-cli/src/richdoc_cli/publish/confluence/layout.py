"""Layout post-processing for the Confluence converter.

Confluence requires every ``<ac:layout-section>`` to be a direct child
of ``<ac:layout>`` at the page body's top level. The converter happily
emits layout sections inline as it walks rd-cols / rd-pros-cons; this
module's `wrap_in_layout` runs once over the final XML to group
everything into the right shape:

  body =  <leading peer content?>
          <ac:layout-section …>…</ac:layout-section>
          <peer content?>
          <ac:layout-section …>…</ac:layout-section>
          \u2026

becomes

  <ac:layout>
    <ac:layout-section type="fixed-width"><ac:layout-cell>\u2026peer\u2026</ac:layout-cell></ac:layout-section>
    <ac:layout-section …>…</ac:layout-section>
    \u2026
  </ac:layout>

If the body contains no layout sections, it's returned unchanged.
"""

from __future__ import annotations

import re

import lxml.etree as ET

__all__ = ["AC_NS", "AT_NS", "NSMAP", "RI_NS", "wrap_in_layout"]

AC_NS = "http://atlassian.com/content"
RI_NS = "http://atlassian.com/resource/identifier"
AT_NS = "http://www.w3.org/1999/xlink"

_AC = f"{{{AC_NS}}}"
NSMAP = {"ac": AC_NS, "ri": RI_NS, "at": AT_NS}

_NS_PREFIX_RE = re.compile(
    r' xmlns:(?:ac|ri|at)="(?:'
    + re.escape(AC_NS)
    + "|"
    + re.escape(RI_NS)
    + "|"
    + re.escape(AT_NS)
    + ')"'
)


def wrap_in_layout(body: str) -> str:
    """Wrap the page body in ``<ac:layout>`` when it contains any
    ``<ac:layout-section>``.

    Pages with no layout-section pass through unchanged.
    """
    if "<ac:layout-section" not in body:
        return body
    wrapped = (
        f'<root xmlns:ac="{AC_NS}" xmlns:ri="{RI_NS}" xmlns:at="{AT_NS}">'
        f"{body}</root>"
    )
    parser = ET.XMLParser(strip_cdata=False)
    try:
        root = ET.fromstring(wrapped, parser)
    except ET.XMLSyntaxError:
        # Defensive: never break the publish if a handler emitted
        # something the parser refuses. The legacy section-macro path
        # never tripped this; modern panels likewise stay well-formed.
        return body
    layout = ET.Element(f"{_AC}layout", nsmap=NSMAP)
    pending: list[ET._Element] = []

    def flush() -> None:
        if not pending:
            return
        sec = ET.SubElement(layout, f"{_AC}layout-section")
        sec.set(f"{_AC}type", "fixed-width")
        cell = ET.SubElement(sec, f"{_AC}layout-cell")
        for el in pending:
            cell.append(el)
        pending.clear()

    # Preserve any leading text inside <root> as a paragraph in the
    # first fixed-width section.
    if root.text and root.text.strip():
        p = ET.SubElement(ET.Element("_tmp"), "p")
        p.text = root.text
        pending.append(p)
    for child in list(root):
        if child.tag == f"{_AC}layout-section":
            flush()
            layout.append(child)
        else:
            pending.append(child)
    flush()
    xml = ET.tostring(layout, encoding="unicode")
    # Strip the xmlns declarations lxml adds on the outermost element;
    # the rest of the storage body uses bare ac: / ri: prefixes without
    # declarations and Confluence accepts that style.
    return _NS_PREFIX_RE.sub("", xml)
