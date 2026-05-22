"""Generic block walker + small text helpers shared across handler modules.

The walker drives top-level rendering: parse HTML, locate the body, dispatch
each direct child to the right handler. It also exposes a few text utilities
(`_inline_text`, `_dedent`, `_element_source`) and the two low-level block
emitters (`_emit_code`, `_embed_image`) that several handlers reuse.
"""

from __future__ import annotations

from io import BytesIO

import lxml.etree as ET
from docx.shared import Inches, RGBColor

from ..common.text import dedent as _dedent_canonical
from ..common.walker import (
    body_of,
    parse_html,
)
from ..common.walker import (
    element_source as _element_source,
)
from ..common.walker import (
    inline_text as _inline_text,
)
from .state import _State

# Re-exports consumed by sibling handler modules (runs.py / handlers_*.py).
__all__ = [
    "_dedent",
    "_element_source",
    "_embed_image",
    "_emit_code",
    "_has_any_heading",
    "_inline_text",
    "render_block",
    "render_children",
    "render_source",
]

# ---------------------------------------------------------------------------
# Source → tree → block dispatch
# ---------------------------------------------------------------------------


def render_source(state: _State, source: str, *, chapter_title: str | None = None) -> None:
    root = parse_html(source)
    target = body_of(root)
    # The chapter's own rd-hero / <h1> supplies its Heading 1. We only fall
    # back to the TOC-derived chapter title when the chapter has no heading
    # of its own anywhere in its top-level page tree.
    if chapter_title and not _has_any_heading(target):
        state.doc.add_heading(chapter_title, level=1)
    render_children(state, target)


def render_children(state: _State, el: ET._Element) -> None:
    if el.text and el.text.strip():
        state.add_paragraph(_inline_text(el.text))
    for child in el:
        render_block(state, child)
        if child.tail and child.tail.strip():
            state.add_paragraph(_inline_text(child.tail))


def render_block(state: _State, el: ET._Element) -> None:
    from .handler_table import BLOCK_HANDLERS
    from .runs import _flatten_inline

    tag = el.tag
    if not isinstance(tag, str):
        return
    tag = tag.lower()
    handler = BLOCK_HANDLERS.get(tag)
    if handler is None:
        if tag.startswith("rd-"):
            # Unknown rd-* — emit a paragraph from its inline text.
            text = _flatten_inline(state, el).strip()
            if text:
                state.add_paragraph(text)
            state.record_dropped(tag)
        else:
            # Unknown plain tag — emit children as paragraphs.
            render_children(state, el)
        return
    handler(state, el)


def _has_any_heading(el: ET._Element) -> bool:
    """Detect whether the chapter has its own top heading anywhere inside
    its rd-page (or top-level if no rd-page). Used to decide whether we need
    to inject a TOC-derived chapter heading."""
    for node in el.iter():
        if not isinstance(node.tag, str):
            continue
        tag = node.tag.lower()
        if tag in ("h1", "rd-hero"):
            return True
    return False


# ---------------------------------------------------------------------------
# Text utilities
#
# `_inline_text` and `_element_source` are re-exported from common.walker
# above so handler modules can keep their existing imports unchanged.
# ---------------------------------------------------------------------------


def _dedent(text: str) -> str:
    """Local alias for the canonical `export.common.text.dedent`.

    Existing handler modules import `_dedent` from this module; the
    re-export keeps their imports stable until they're moved to import
    the canonical name directly.
    """
    return _dedent_canonical(text)


# ---------------------------------------------------------------------------
# Low-level block emitters (used by several handler modules)
# ---------------------------------------------------------------------------


def _emit_code(state: _State, text: str, *, lang: str | None) -> None:
    if not text:
        return
    if lang:
        p = state.add_paragraph(style="RichdocCode")
        r = p.add_run(f"// {lang}")
        r.italic = True
        r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    for line in text.splitlines() or [text]:
        p = state.add_paragraph(style="RichdocCode")
        if line:
            r = p.add_run(line)
            # Preserve leading spaces.
            r.text = line


def _embed_image(state: _State, src: str, *, alt: str = "") -> None:
    ref = state.asset_store.add(src, base_dir=state.base_dir, fetch_remote=True)
    if ref is None:
        p = state.add_paragraph()
        r = p.add_run(f"[image not available: {alt or src}]")
        r.italic = True
        return
    try:
        state.doc.add_picture(BytesIO(ref.data), width=Inches(6.0))
        state.images_embedded += 1
    except Exception:
        p = state.add_paragraph()
        r = p.add_run(f"[image: {alt or src}]")
        r.italic = True
