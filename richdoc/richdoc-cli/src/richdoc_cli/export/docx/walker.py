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

from ..common.walker import (
    body_of,
    element_source as _element_source,
    inline_text as _inline_text,
    parse_html,
)
from .state import _State


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


def render_children(state: _State, el: ET._Element) -> None:  # noqa: SLF001
    if el.text and el.text.strip():
        state.add_paragraph(_inline_text(el.text))
    for child in el:
        render_block(state, child)
        if child.tail and child.tail.strip():
            state.add_paragraph(_inline_text(child.tail))


def render_block(state: _State, el: ET._Element) -> None:  # noqa: SLF001
    from .handler_table import BLOCK_HANDLERS  # noqa: PLC0415 — lazy to avoid cycles
    from .runs import _flatten_inline  # noqa: PLC0415

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


def _has_any_heading(el: ET._Element) -> bool:  # noqa: SLF001
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
    """Strip the common leading indent across non-blank lines.

    Treats spaces and tabs as equivalent characters for the purpose of
    measuring the common prefix, matching the runtime `k()` helper that
    `<rd-code>` / `<rd-diff>` / `<rd-shell>` use in the browser. Without
    tab awareness, source HTML that nests `<rd-code>` inside `<rd-section>`
    (the common case) leaves each code line prefixed with the surrounding
    tabs, which python-docx then renders as stacked `<w:tab/>` runs.
    """
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    indents = [len(l) - len(l.lstrip(" \t")) for l in lines if l.strip()]
    pad = min(indents) if indents else 0
    return "\n".join(l[pad:] if len(l) >= pad else l for l in lines)


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
    except Exception:  # noqa: BLE001 — unsupported format etc.
        p = state.add_paragraph()
        r = p.add_run(f"[image: {alt or src}]")
        r.italic = True
