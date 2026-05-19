"""DOCX `Document` factory and style registration."""

from __future__ import annotations

from docx import Document
from docx.document import Document as DocumentT
from docx.shared import Pt


def new_document() -> DocumentT:
    doc = Document()
    _register_code_style(doc)
    return doc


def _register_code_style(doc: DocumentT) -> None:
    """Register the `RichdocCode` paragraph style used for fenced code blocks."""
    styles = doc.styles
    if "RichdocCode" in [s.name for s in styles]:
        return
    from docx.enum.style import WD_STYLE_TYPE  # noqa: PLC0415 — lazy

    style = styles.add_style("RichdocCode", WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = styles["Normal"]
    font = style.font
    font.name = "Courier New"
    font.size = Pt(9)
    pf = style.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
