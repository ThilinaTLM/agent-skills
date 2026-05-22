"""Converter state machine.

`_Converter` holds the per-walk buffer, the citation registries, the
attachment queue, and the diagram / math counters. Handlers in
`handlers_plain.py` and `handlers_rd.py` consume an instance to render
each element.

The dispatch table `HANDLERS` is module-level so the handler files can
register into it at import time. It lives here (not in `converter.py`)
to avoid a circular import: `_Converter.render` needs the dict on
hand, and `converter.html_to_storage` imports `_Converter` from this
module.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import lxml.etree as ET

from ..common.assets import AssetStore
from ..common.walker import inline_text as _inline_text
from .layout import wrap_in_layout
from .nav import build_prev_next_nav
from .refs import format_ref_li
from .xml import BLOCK_OPENER, xml_escape

if TYPE_CHECKING:
    from .converter import PendingAttachment, TocEntry

__all__ = ["HANDLERS", "_Converter"]

# Dispatch registry \u2014 populated at import time by handler_table.py.
HANDLERS: dict[str, Callable[[_Converter, ET._Element], None]] = {}


@dataclass
class _Converter:
    """Buffer + per-walk state shared by every handler."""

    asset_base: Path
    asset_store: AssetStore
    include_remote_images: bool = False
    render_diagrams: bool = True
    render_math: bool = True
    diagram_endpoint: str = "https://kroki.io"
    cross_page_links: dict[str, str] = field(default_factory=dict)
    chapter_rel: Path | None = None
    toc_entries: list[TocEntry] | None = None

    chunks: list[str] = field(default_factory=list)
    pending: list[PendingAttachment] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    math_rendered: int = 0
    math_failed: int = 0
    # True when this converter is rendering into a sub-buffer that will
    # be baked into one parent chunk (e.g. a panel's <ac:adf-content>,
    # an expand macro's <ac:rich-text-body>, a layout cell). Block-level
    # constructs that *must* sit at the page-body top level (currently
    # only <ac:layout-section>) check this flag and fall back to a
    # linearised rendering when it is True.
    in_isolated_body: bool = False
    # Citation collection (scattered rd-ref \u2192 single bibliography below)
    refs_collected: dict[str, dict[str, str]] = field(default_factory=dict)
    refs_order: list[str] = field(default_factory=list)
    refs_section_title: str = "References"

    # ---- output helpers --------------------------------------------------

    def write(self, text: str) -> None:
        if text:
            self.chunks.append(text)

    def write_text(self, text: str) -> None:
        """Write inline text, XML-escaping."""
        if text:
            self.chunks.append(xml_escape(text))

    def write_block(self, fragment: str) -> None:
        """Append a block-level XML fragment. No escaping (caller built it)."""
        if not fragment:
            return
        self.chunks.append(fragment)

    def _spawn_sub(self) -> _Converter:
        sub = _Converter(
            asset_base=self.asset_base,
            asset_store=self.asset_store,
            include_remote_images=self.include_remote_images,
            render_diagrams=self.render_diagrams,
            render_math=self.render_math,
            diagram_endpoint=self.diagram_endpoint,
            cross_page_links=self.cross_page_links,
            chapter_rel=self.chapter_rel,
            toc_entries=self.toc_entries,
            in_isolated_body=True,
        )
        sub.pending = self.pending  # shared list \u2014 handlers append directly
        sub.dropped = self.dropped
        sub.refs_collected = self.refs_collected
        sub.refs_order = self.refs_order
        return sub

    def render_inline(self, el: ET._Element) -> str:
        """Render `el` and children as an inline XML fragment. Counters
        from the sub-converter are merged back."""
        sub = self._spawn_sub()
        if el.text:
            sub.write_text(_inline_text(el.text))
        for child in el:
            sub.render(child)
            if child.tail:
                sub.write_text(_inline_text(child.tail))
        self._merge_counters(sub)
        return "".join(sub.chunks)

    def render_block_inner(self, el: ET._Element) -> str:
        """Render the children of `el` as a block-level XML fragment."""
        sub = self._spawn_sub()
        sub.render_children(el)
        self._merge_counters(sub)
        out = "".join(sub.chunks).strip()
        return out

    def render_block_inner_wrapped(self, el: ET._Element) -> str:
        """Like `render_block_inner` but wraps bare inline content in a
        single <p> so block containers (rd-card, rd-section, ...) don't end
        up with naked text outside any block element."""
        inner = self.render_block_inner(el)
        if not inner:
            return ""
        # If the rendered output already starts with a block-level tag,
        # leave it alone. Otherwise wrap in <p>.
        stripped = inner.lstrip()
        if stripped.startswith("<") and BLOCK_OPENER.match(stripped):
            return inner
        return f"<p>{inner}</p>"

    def render_children(self, el: ET._Element) -> None:
        if el.text:
            self.write_text(_inline_text(el.text))
        for child in el:
            self.render(child)
            if child.tail:
                self.write_text(_inline_text(child.tail))

    # ---- dispatch --------------------------------------------------------

    def render(self, el: ET._Element) -> None:
        tag = el.tag
        if not isinstance(tag, str):
            return  # comments / PIs
        tag = tag.lower()
        handler = HANDLERS.get(tag)
        if handler is None:
            if tag.startswith("rd-"):
                self.dropped.append(tag)
            # unwrap unknown tags
            self.render_children(el)
            return
        handler(self, el)

    # ---- pending attachment helpers --------------------------------------

    def queue_attachment(
        self,
        *,
        data: bytes,
        prefix: str,
        mime: str,
        ext: str,
        align: str = "center",
        is_inline: bool = False,
    ) -> str:
        """Stage a binary as a future attachment. Returns the placeholder
        token; emit it directly into the chunk buffer."""
        # Local import keeps the converter dataclass module-level types small.
        from .converter import PendingAttachment

        digest = hashlib.sha1(data, usedforsecurity=False).hexdigest()[:12]
        filename = f"{prefix}-{digest}{ext}"
        token = f"@@ATTACHMENT:{prefix}:{digest}@@"
        # De-dup by token so two identical math blocks share one upload.
        for existing in self.pending:
            if existing.token == token:
                return token
        self.pending.append(
            PendingAttachment(
                token=token,
                filename=filename,
                data=data,
                mime=mime,
                align=align,
                is_inline=is_inline,
            )
        )
        return token

    # ---- asset helpers --------------------------------------------------

    def resolve_local_image(self, src: str) -> PendingAttachment | None:
        """Load a local <img src> as a pending attachment.

        Remote sources are only fetched when `include_remote_images` is
        True; otherwise the caller falls back to rendering the URL as a
        plain external link.
        """
        from .converter import PendingAttachment

        ref = self.asset_store.add(
            src,
            base_dir=self.asset_base,
            fetch_remote=self.include_remote_images,
        )
        if ref is None:
            return None
        # Reuse pending entry if already queued under this filename.
        for pa in self.pending:
            if pa.filename == ref.local_name:
                return pa
        pa = PendingAttachment(
            token=f"@@ATTACHMENT:img:{ref.local_name}@@",
            filename=ref.local_name,
            data=ref.data,
            mime=ref.mime or "application/octet-stream",
            align="center",
            is_inline=False,
        )
        self.pending.append(pa)
        return pa

    # ---- finalisation ---------------------------------------------------

    def finalise(self) -> str:
        # If any rd-ref entries were collected without a matching
        # rd-references block, append an auto-generated bibliography so
        # the rd-cite markers resolve to something readable.
        if self.refs_collected and not self._refs_emitted_inline():
            self._emit_collected_bibliography()
        # Book mode only: append a single-row prev/next chapter nav at
        # the bottom of the body. The top of every chapter already has
        # the rd-toc Contents block, so no top nav is needed.
        nav = build_prev_next_nav(self)
        if nav:
            self.write_block(nav)
        # We intentionally do NOT collapse runs of whitespace here. The
        # output contains CDATA-wrapped code bodies where every space and
        # tab is significant; Confluence is happy with ambient whitespace
        # between block tags, so leaving it alone keeps the body safe.
        out = "".join(self.chunks)
        out = re.sub(r"\n{3,}", "\n\n", out)
        out = wrap_in_layout(out.strip())
        return out

    def _refs_emitted_inline(self) -> bool:
        # If an rd-references block already rendered, it'd have written a
        # "<h2>References</h2>" heading; treat that as the signal we don't
        # need to repeat ourselves.
        joined = (
            "".join(self.chunks[-200:]) if len(self.chunks) > 200 else "".join(self.chunks)
        )
        return f"<h2>{xml_escape(self.refs_section_title)}</h2>" in joined

    def _emit_collected_bibliography(self) -> None:
        items: list[str] = []
        seen: set[str] = set()
        for key in self.refs_order:
            if key in seen or key not in self.refs_collected:
                continue
            seen.add(key)
            items.append(format_ref_li(self.refs_collected[key]))
        # Uncited refs still appear, in source order, after the cited ones.
        for key, attrs in self.refs_collected.items():
            if key in seen:
                continue
            seen.add(key)
            items.append(format_ref_li(attrs))
        if not items:
            return
        self.write_block(
            f"<h2>{xml_escape(self.refs_section_title)}</h2>"
            f"<ol>{''.join(items)}</ol>"
        )

    def _merge_counters(self, sub: _Converter) -> None:
        self.diagrams_rendered += sub.diagrams_rendered
        self.diagrams_failed += sub.diagrams_failed
        self.math_rendered += sub.math_rendered
        self.math_failed += sub.math_failed
