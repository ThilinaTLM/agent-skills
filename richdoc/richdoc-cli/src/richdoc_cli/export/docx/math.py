"""LaTeX → Office Math (OMML) conversion for the DOCX exporter.

`<rd-math>` carries KaTeX-flavoured LaTeX. In the browser KaTeX renders
it into HTML/MathML; for DOCX we need Word's native equation format
(OMML) so that imports into Word / Confluence land as editable equations
instead of raw `\\frac{…}` source text.

Pipeline:

    LaTeX  ──latex2mathml──▶  MathML  ──MML2OMML.xsl──▶  OMML <m:oMath>

The XSLT (`mml2omml.xsl`) is the XSLT 1.0 stylesheet that ships with
Microsoft Word and is redistributed under TEI's BSD-2-Clause licence;
see ``MML2OMML.NOTICE.md`` next to it. Both halves are pure Python /
pure XSLT, so no external binaries are involved.

If anything goes wrong (parser failure, unsupported LaTeX command, …) we
return ``None`` so the caller can fall back to the literal source.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import latex2mathml.converter as _latex
import lxml.etree as ET

_M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_XSLT_PATH = Path(__file__).with_name("mml2omml.xsl")


@cache
def _transformer() -> ET.XSLT:
    return ET.XSLT(ET.parse(str(_XSLT_PATH)))


def latex_to_omath(source: str) -> ET._Element | None:
    """Convert a LaTeX math expression into an ``<m:oMath>`` element.

    Returns ``None`` if the LaTeX cannot be parsed or the XSLT produces
    no math content. The returned element belongs to a throwaway tree;
    callers should append it (or a copy) into the target document.
    """
    source = source.strip()
    if not source:
        return None
    try:
        mathml = _latex.convert(source)
    except Exception:
        return None
    try:
        mml_doc = ET.fromstring(mathml.encode("utf-8"))
    except ET.XMLSyntaxError:
        return None
    try:
        result = _transformer()(mml_doc)
    except ET.XSLTError:
        return None
    root = result.getroot()
    if root is None or root.tag != f"{{{_M_NS}}}oMath":
        return None
    # Drop a `<m:oMath>` that contains no runs — XSLT emits the wrapper
    # even when MathML it didn't recognise produced no children.
    if not list(root):
        return None
    return root


def wrap_block(omath: ET._Element) -> ET._Element:
    """Wrap an ``<m:oMath>`` in an ``<m:oMathPara>`` for display-mode use.

    A bare ``<m:oMath>`` renders inline; ``<m:oMathPara>`` is Word's
    display container — centred on its own line with the equation
    typeset on the math baseline.
    """
    para = ET.Element(f"{{{_M_NS}}}oMathPara")
    # Right-align indicator: the default justification is centred, which
    # matches KaTeX's display behaviour.
    para.append(omath)
    return para
