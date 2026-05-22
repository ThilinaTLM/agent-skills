"""Plain-HTML block handlers for the DOCX exporter."""

from __future__ import annotations

from collections.abc import Callable

import lxml.etree as ET
from docx.oxml.ns import qn

from ..common.walker import text_of
from .runs import (
    _emit_runs,
    _inline_runs,
    _inline_runs_from_parts,
    _split_li,
)
from .state import _State
from .tables import _fill_row, _parse_html_table
from .walker import _dedent, _embed_image, _emit_code, render_block


def _h_heading(level: int) -> Callable[[_State, ET._Element], None]:
    def handler(state: _State, el: ET._Element) -> None:
        runs = _inline_runs(state, el)
        # docx's Document.add_heading honours levels 1-9 (with level 0 = Title).
        p = state.doc.add_heading("", level=min(level, 9))
        _emit_runs(p, runs)

    return handler


def _h_p(state: _State, el: ET._Element) -> None:
    runs = _inline_runs(state, el)
    if not any(r.text.strip() for r in runs):
        return
    p = state.add_paragraph()
    _emit_runs(p, runs)


def _h_ul(state: _State, el: ET._Element) -> None:
    _emit_list(state, el, kind="ul")


def _h_ol(state: _State, el: ET._Element) -> None:
    _emit_list(state, el, kind="ol")


def _emit_list(state: _State, el: ET._Element, *, kind: str) -> None:
    depth = sum(1 for k, _ in state.list_stack if k in ("ul", "ol"))
    state.list_stack.append((kind, depth))
    style_for_level = {
        "ul": ["List Bullet", "List Bullet 2", "List Bullet 3"],
        "ol": ["List Number", "List Number 2", "List Number 3"],
    }
    style = style_for_level[kind][min(depth, 2)]
    for child in el:
        if not isinstance(child.tag, str):
            continue
        if child.tag.lower() != "li":
            continue
        # Split <li> content into inline run + nested list children.
        inline_parts, nested_blocks = _split_li(child)
        p = state.doc.add_paragraph(style=style)
        runs = _inline_runs_from_parts(state, inline_parts)
        _emit_runs(p, runs)
        for nested in nested_blocks:
            render_block(state, nested)
    state.list_stack.pop()


def _h_blockquote(state: _State, el: ET._Element) -> None:
    inner_paragraphs = [c for c in el if isinstance(c.tag, str) and c.tag.lower() == "p"]
    if not inner_paragraphs:
        runs = _inline_runs(state, el)
        if any(r.text.strip() for r in runs):
            p = state.doc.add_paragraph(style="Intense Quote")
            _emit_runs(p, runs)
        return
    for para in inner_paragraphs:
        runs = _inline_runs(state, para)
        if not any(r.text.strip() for r in runs):
            continue
        p = state.doc.add_paragraph(style="Intense Quote")
        _emit_runs(p, runs)


def _h_pre(state: _State, el: ET._Element) -> None:
    # <pre><code>…</code></pre> is the common shape.
    text = text_of(el)
    _emit_code(state, _dedent(text), lang=None)


def _h_hr(state: _State, el: ET._Element) -> None:
    p = state.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = ET.SubElement(pPr, qn("w:pBdr"))
    bottom = ET.SubElement(pBdr, qn("w:bottom"))
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "999999")


def _h_table(state: _State, el: ET._Element) -> None:
    headers, rows = _parse_html_table(el)
    if not rows and not headers:
        return
    cols = max(len(headers), max((len(r) for r in rows), default=0))
    if cols == 0:
        return
    if not headers:
        headers = [""] * cols
    table = state.doc.add_table(rows=1 + len(rows), cols=cols)
    table.style = "Table Grid"
    _fill_row(state, table.rows[0], headers, bold=True)
    for i, row in enumerate(rows, start=1):
        _fill_row(state, table.rows[i], row + [""] * (cols - len(row)))


def _h_img_block(state: _State, el: ET._Element) -> None:
    src = el.get("src") or ""
    alt = el.get("alt") or ""
    if not src:
        return
    _embed_image(state, src, alt=alt)
