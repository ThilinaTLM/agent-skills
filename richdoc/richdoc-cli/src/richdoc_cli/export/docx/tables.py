"""Table-cell helpers for the DOCX exporter."""

from __future__ import annotations

import lxml.etree as ET
from docx.oxml.ns import qn
from docx.table import _Cell

from ..common.walker import text_of
from .state import _State


def _parse_html_table(el: ET._Element) -> tuple[list[str], list[list[str]]]:
    headers: list[str] = []
    rows: list[list[str]] = []
    for tr in el.iter("tr"):
        cells = [c for c in tr if isinstance(c.tag, str) and c.tag.lower() in ("th", "td")]
        texts = [" ".join(text_of(c).split()).strip() for c in cells]
        if cells and all(isinstance(c.tag, str) and c.tag.lower() == "th" for c in cells) and not headers:
            headers = texts
        else:
            rows.append(texts)
    return headers, rows


def _fill_row(state: _State, row, cells: list[str], *, bold: bool = False) -> None:
    for idx, text in enumerate(cells):
        cell = row.cells[idx]
        cell.text = ""
        p = cell.paragraphs[0]
        r = p.add_run(text)
        if bold:
            r.bold = True


def _set_cell_border(cell: _Cell, *, side: str, color: str, sz: int) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = ET.SubElement(tcPr, qn("w:tcBorders"))
    border = tcBorders.find(qn(f"w:{side}"))
    if border is None:
        border = ET.SubElement(tcBorders, qn(f"w:{side}"))
    border.set(qn("w:val"), "single")
    border.set(qn("w:sz"), str(sz))
    border.set(qn("w:space"), "0")
    border.set(qn("w:color"), color)


def _set_cell_shading(cell: _Cell, color: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = ET.SubElement(tcPr, qn("w:shd"))
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
