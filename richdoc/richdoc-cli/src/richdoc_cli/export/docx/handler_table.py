"""Dispatch table for the DOCX exporter."""

from __future__ import annotations

from collections.abc import Callable

import lxml.etree as ET

from . import handlers_plain as p
from . import handlers_rd as r
from .state import _State
from .walker import render_children

BLOCK_HANDLERS: dict[str, Callable[[_State, ET._Element], None]] = {
    # plain HTML
    "h1": p._h_heading(1),
    "h2": p._h_heading(2),
    "h3": p._h_heading(3),
    "h4": p._h_heading(4),
    "h5": p._h_heading(5),
    "h6": p._h_heading(6),
    "p": p._h_p,
    "ul": p._h_ul,
    "ol": p._h_ol,
    "blockquote": p._h_blockquote,
    "pre": p._h_pre,
    "hr": p._h_hr,
    "table": p._h_table,
    "img": p._h_img_block,
    "div": lambda s, e: render_children(s, e),
    "section": lambda s, e: render_children(s, e),
    "article": lambda s, e: render_children(s, e),
    "header": lambda s, e: render_children(s, e),
    "footer": lambda s, e: render_children(s, e),
    "main": lambda s, e: render_children(s, e),
    "aside": lambda s, e: render_children(s, e),
    "nav": lambda s, e: render_children(s, e),
    "figure": lambda s, e: render_children(s, e),
    # rd-*
    "rd-page": r._h_rd_page,
    "rd-section": r._h_rd_section,
    "rd-hero": r._h_rd_hero,
    "rd-banner": r._h_rd_banner,
    "rd-callout": r._h_rd_callout,
    "rd-kv": r._h_rd_kv,
    "rd-stat": r._h_rd_stat,
    "rd-progress": r._h_rd_progress,
    "rd-update": r._h_rd_update,
    "rd-cols": r._h_rd_cols,
    "rd-card": r._h_rd_card,
    "rd-code": r._h_rd_code,
    "rd-diff": r._h_rd_diff,
    "rd-shell": r._h_rd_shell,
    "rd-math": r._h_rd_math,
    "rd-figure": r._h_rd_figure,
    "rd-chart": r._h_rd_chart,
    "rd-tabs": r._h_rd_tabs,
    "rd-timeline": r._h_rd_timeline,
    "rd-steps": r._h_rd_steps,
    "rd-detail": r._h_rd_detail,
    "rd-checklist": r._h_rd_checklist,
    "rd-diagram": r._h_rd_diagram,
    "rd-toc": r._h_rd_toc,
    "rd-decision": r._h_rd_decision,
    "rd-pros-cons": r._h_rd_pros_cons,
    "rd-compare": r._h_rd_compare,
    "rd-rubric": r._h_rd_rubric,
    "rd-api": r._h_rd_api,
    "rd-references": r._h_rd_references,
    "rd-ref": r._h_rd_ref,
    "rd-cite": r._h_rd_cite,
    "rd-chapter": r._h_rd_chapter,
}
