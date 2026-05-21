"""HTML → Confluence-importable HTML converter.

Walks the parsed HTML tree once and dispatches each element to a
tag-specific handler. Plain HTML emits the lossless subset Confluence's
HTML import preserves (headings, paragraphs, lists, tables, blockquotes,
`<code>`, `<img>`, …). Code blocks, math, and diagrams — which the
importer collapses to plain text — are queued for offline rasterisation
and embedded as `<img>` references.

The converter is intentionally pure: it walks the tree, accumulates
HTML chunks, and records pending images. The pipeline materialises
them after the walk and rewrites the queued src placeholders to the
final per-page asset paths.

This module owns the `_Converter` state machine and the handful of
generic helpers; the actual element handlers live in
`handlers_plain.py` / `handlers_rd.py`, and the dispatch dict is
assembled in `handler_table.py`.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import lxml.etree as ET

from ..common.assets import AssetRef, AssetStore
from ..common.walker import (
    body_of,
    element_source as _element_source,
    inline_text as _inline_text,
    parse_html,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def html_to_confluence_page(
    source: str,
    *,
    page_slug: str,
    asset_store: AssetStore | None = None,
    asset_base: Path | None = None,
    include_remote_images: bool = False,
    render_diagrams: bool = True,
    render_code_images: bool = True,
    render_math_images: bool = True,
    diagram_endpoint: str = "https://kroki.io",
    code_style: str = "default",
) -> "PageResult":
    """Convert one richdoc HTML document to a Confluence-importable page.

    Returns a `PageResult` carrying the HTML body, the list of pending
    code/math/diagram images, the share-able asset store, and bookkeeping.
    """
    # Side-effect import populates HANDLERS.
    from . import handler_table  # noqa: F401, PLC0415

    root = parse_html(source)
    target = body_of(root)
    conv = _Converter(
        page_slug=page_slug,
        asset_store=asset_store if asset_store is not None else AssetStore(),
        asset_base=asset_base,
        include_remote_images=include_remote_images,
        render_diagrams=render_diagrams,
        render_code_images=render_code_images,
        render_math_images=render_math_images,
        diagram_endpoint=diagram_endpoint,
        code_style=code_style,
    )
    conv.render_children(target)
    return conv.finalise()


# ---------------------------------------------------------------------------
# Dispatch registry
# ---------------------------------------------------------------------------


HANDLERS: dict[str, Callable[["_Converter", "ET._Element"], None]] = {}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PendingCode:
    """A code block awaiting rasterisation."""

    placeholder: str       # unique token spliced into the HTML body
    text: str
    lang: str | None
    title: str | None
    line_numbers: bool


@dataclass
class PendingMath:
    """A math block awaiting Kroki rendering."""

    placeholder: str
    latex: str
    display: str           # "block" | "inline"


@dataclass
class PendingDiagram:
    """A `<rd-diagram>` awaiting Kroki rendering."""

    placeholder: str
    source: str
    kind: str              # mermaid, plantuml, …


@dataclass
class PageResult:
    """Outcome of one document conversion."""

    body_html: str
    title: str
    asset_store: AssetStore
    code: list[PendingCode] = field(default_factory=list)
    math: list[PendingMath] = field(default_factory=list)
    diagrams: list[PendingDiagram] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Converter state
# ---------------------------------------------------------------------------


@dataclass
class _ListCtx:
    kind: str        # "ul" | "ol"
    depth: int = 0   # 0-based nesting


@dataclass
class _Converter:
    page_slug: str = ""
    asset_store: AssetStore = field(default_factory=AssetStore)
    asset_base: Path | None = None
    include_remote_images: bool = False
    render_diagrams: bool = True
    render_code_images: bool = True
    render_math_images: bool = True
    diagram_endpoint: str = "https://kroki.io"
    code_style: str = "default"

    # accumulators
    chunks: list[str] = field(default_factory=list)
    list_stack: list[_ListCtx] = field(default_factory=list)
    code: list[PendingCode] = field(default_factory=list)
    math: list[PendingMath] = field(default_factory=list)
    diagrams: list[PendingDiagram] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    title: str = ""

    # rd-references / rd-cite
    ref_entries: dict[str, dict[str, str]] = field(default_factory=dict)
    ref_order: list[str] = field(default_factory=list)
    refs_title: str = "References"
    refs_placeholder_emitted: bool = False
    _refs_placeholder: str = "@@@RICHDOC_REFS_SECTION@@@"

    _placeholder_n: int = 0

    # ---- output helpers --------------------------------------------------

    def write(self, html_text: str) -> None:
        if html_text:
            self.chunks.append(html_text)

    def write_block(self, html_text: str) -> None:
        if not html_text:
            return
        if self.chunks and not self.chunks[-1].endswith("\n"):
            self.chunks.append("\n")
        self.chunks.append(html_text)
        if not html_text.endswith("\n"):
            self.chunks.append("\n")

    # ---- recursion -------------------------------------------------------

    def render_children(self, el: ET._Element) -> None:
        if el.text:
            self.write(escape_text(_inline_text(el.text)))
        for child in el:
            self.render(child)
            if child.tail:
                self.write(escape_text(_inline_text(child.tail)))

    def render_inline(self, el: ET._Element) -> str:
        sub = self._spawn_sub()
        if el.text:
            sub.write(escape_text(_inline_text(el.text)))
        for child in el:
            sub.render(child)
            if child.tail:
                sub.write(escape_text(_inline_text(child.tail)))
        self._absorb(sub)
        return "".join(sub.chunks)

    def render_block_inner(self, el: ET._Element) -> str:
        sub = self._spawn_sub()
        sub.render_children(el)
        self._absorb(sub)
        return "".join(sub.chunks).strip("\n")

    def render_block_inner_wrapped(self, el: ET._Element) -> str:
        """Like `render_block_inner`, but if the result looks like bare inline
        content (text + inline tags, no block-level element), wrap it in a
        `<p>` so downstream HTML stays well-formed."""
        body = self.render_block_inner(el)
        if not body.strip():
            return ""
        if _starts_with_block(body):
            return body
        return f"<p>{body.strip()}</p>"

    def _spawn_sub(self) -> "_Converter":
        sub = _Converter(
            page_slug=self.page_slug,
            asset_store=self.asset_store,
            asset_base=self.asset_base,
            include_remote_images=self.include_remote_images,
            render_diagrams=self.render_diagrams,
            render_code_images=self.render_code_images,
            render_math_images=self.render_math_images,
            diagram_endpoint=self.diagram_endpoint,
            code_style=self.code_style,
        )
        sub.list_stack = self.list_stack[:]
        sub.code = self.code
        sub.math = self.math
        sub.diagrams = self.diagrams
        sub.dropped = self.dropped
        sub.ref_entries = self.ref_entries
        sub.ref_order = self.ref_order
        sub._placeholder_n = self._placeholder_n
        sub._refs_placeholder = self._refs_placeholder
        sub.title = self.title
        return sub

    def _absorb(self, sub: "_Converter") -> None:
        # The mutable lists/dicts are shared by reference; only counters
        # need to be propagated back.
        self._placeholder_n = sub._placeholder_n
        if sub.title and not self.title:
            self.title = sub.title

    # ---- dispatch --------------------------------------------------------

    def render(self, el: ET._Element) -> None:
        tag = el.tag
        if not isinstance(tag, str):
            return
        tag = tag.lower()
        handler = HANDLERS.get(tag)
        if handler is None:
            if tag.startswith("rd-"):
                self.dropped.append(tag)
            self.render_children(el)
            return
        handler(self, el)

    # ---- image / placeholder factories -----------------------------------

    def rewrite_image_src(self, src: str) -> tuple[str, AssetRef | None]:
        """Register `src` with the asset store and return a (relative-href,
        AssetRef) pair. The href is relative to the page's .html file —
        `"<page-slug>/<hash>.<ext>"`. Remote URLs are only fetched when
        `include_remote_images` is True; otherwise the URL is returned as-is.
        """
        if not src:
            return src, None
        if src.startswith("data:") or src.startswith("#"):
            return src, None
        if self.asset_base is None:
            return src, None
        ref = self.asset_store.add(
            src,
            base_dir=self.asset_base,
            fetch_remote=self.include_remote_images,
        )
        if ref is None:
            return src, None
        return _asset_href(self.page_slug, ref.local_name), ref

    def queue_code_image(
        self,
        text: str,
        *,
        lang: str | None,
        title: str | None,
        line_numbers: bool = False,
    ) -> str:
        """Reserve a placeholder for a code block; return the placeholder
        token. The pipeline replaces it with an `<img>` tag once the PNG
        has been rasterised and placed in the asset store."""
        ph = self._next_placeholder("code")
        self.code.append(
            PendingCode(
                placeholder=ph,
                text=text,
                lang=lang,
                title=title,
                line_numbers=line_numbers,
            )
        )
        return ph

    def queue_math_image(self, latex: str, *, display: str) -> str:
        ph = self._next_placeholder("math")
        self.math.append(
            PendingMath(placeholder=ph, latex=latex, display=display)
        )
        return ph

    def queue_diagram_image(self, source: str, *, kind: str) -> str:
        ph = self._next_placeholder("diag")
        self.diagrams.append(
            PendingDiagram(placeholder=ph, source=source, kind=kind)
        )
        return ph

    def _next_placeholder(self, prefix: str) -> str:
        self._placeholder_n += 1
        return f"@@RICHDOC_{prefix.upper()}_{self._placeholder_n}@@"

    # ---- references ------------------------------------------------------

    def refs_placeholder(self) -> str:
        """Reserve a slot in the page where the references list should be
        emitted. The pipeline substitutes the placeholder with the rendered
        list once all citations are known."""
        self.refs_placeholder_emitted = True
        return self._refs_placeholder

    # ---- finalisation ----------------------------------------------------

    def finalise(self) -> PageResult:
        body = "".join(self.chunks)
        # Append references section if any citations exist and no
        # explicit <rd-references> was emitted inline.
        if (self.ref_order or self.ref_entries) and not self.refs_placeholder_emitted:
            body += "\n" + render_references_section(
                self.refs_title, self.ref_entries, self.ref_order
            )
        elif self.refs_placeholder_emitted:
            rendered = render_references_section(
                self.refs_title, self.ref_entries, self.ref_order
            )
            body = body.replace(self._refs_placeholder, rendered, 1)
        # Tidy blank lines.
        body = re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"
        return PageResult(
            body_html=body,
            title=self.title,
            asset_store=self.asset_store,
            code=self.code,
            math=self.math,
            diagrams=self.diagrams,
            dropped=sorted(set(self.dropped)),
            missing=list(self.asset_store.missing),
        )


# ---------------------------------------------------------------------------
# Helpers shared between handler modules
# ---------------------------------------------------------------------------


def escape_text(text: str) -> str:
    """Escape text content for HTML output (handles &, <, > and quote glyphs)."""
    return html.escape(text, quote=False)


def escape_attr(text: str) -> str:
    """Escape an attribute value, including double-quote which is fine to leave
    raw inside `<tag attr='value'>` but needed for `<tag attr="value">`."""
    return html.escape(text, quote=True)


def attr(name: str, value: str | None) -> str:
    """Render `name="value"` if value is non-empty, else empty string."""
    if value is None:
        return ""
    v = value.strip()
    if not v:
        return ""
    return f' {name}="{escape_attr(v)}"'


def _asset_href(page_slug: str, local_name: str) -> str:
    """Compose the per-page asset href that Confluence expects.

    Confluence's HTML importer requires media to live in a folder with
    the same name as the page (`page-slug/<file>`). The HTML's `src`
    must be relative to the .html file.
    """
    slug = (page_slug or "").strip("/")
    if not slug:
        return local_name
    return f"{slug}/{local_name}"


def _dedent(text: str) -> str:
    """Mirror the JS `<rd-code>` dedent: strip leading/trailing newlines,
    then remove the common leading indent across non-blank lines."""
    text = text.lstrip("\n").rstrip()
    lines = text.split("\n")
    min_indent: int | None = None
    for line in lines:
        if not line.strip():
            continue
        m = re.match(r"^[ \t]*", line)
        n = len(m.group(0)) if m else 0
        if min_indent is None or n < min_indent:
            min_indent = n
    if not min_indent:
        return "\n".join(lines)
    return "\n".join(
        line[min_indent:] if len(line) >= min_indent else line for line in lines
    )


def _strip_outer_blanks(text: str) -> str:
    return text.strip("\n")


_BLOCK_PREFIXES = (
    "<p", "<h1", "<h2", "<h3", "<h4", "<h5", "<h6",
    "<ul", "<ol", "<li", "<table", "<thead", "<tbody", "<tr",
    "<pre", "<blockquote", "<hr", "<div", "<figure",
)


def _starts_with_block(html_text: str) -> bool:
    stripped = html_text.lstrip()
    lower = stripped.lower()
    return any(lower.startswith(prefix) for prefix in _BLOCK_PREFIXES)


def render_references_section(
    title: str, entries: dict[str, dict[str, str]], order: list[str]
) -> str:
    """Emit the references list as Confluence-safe HTML (h2 + ol)."""
    lines: list[str] = [f"<h2>{escape_text(title)}</h2>", "<ol>"]
    seen: set[str] = set()
    for key in order:
        if key in seen or key not in entries:
            continue
        seen.add(key)
        lines.append(f"  <li>{format_ref_html(entries[key])}</li>")
    for key, attrs in entries.items():
        if key in seen:
            continue
        lines.append(f"  <li>{format_ref_html(attrs)}</li>")
    lines.append("</ol>")
    return "\n".join(lines)


def format_ref_html(attrs: dict[str, str]) -> str:
    """Format a citation entry as inline HTML."""
    bits: list[str] = []
    author = attrs.get("author") or ""
    title = attrs.get("title") or ""
    url = attrs.get("url") or ""
    date = attrs.get("date") or ""
    publisher = attrs.get("publisher") or ""
    note = attrs.get("note") or ""
    if author:
        bits.append(escape_text(author))
    if title:
        t_html = escape_text(title)
        if url:
            bits.append(
                f'&ldquo;<a href="{escape_attr(url)}">{t_html}</a>&rdquo;'
            )
        else:
            bits.append(f"&ldquo;{t_html}&rdquo;")
    elif url:
        bits.append(f'<a href="{escape_attr(url)}">{escape_text(url)}</a>')
    if publisher:
        bits.append(escape_text(publisher))
    if date:
        bits.append(escape_text(date))
    out = ". ".join(bits) + ("." if bits else "")
    if note:
        out += " " + escape_text(note)
    return out
