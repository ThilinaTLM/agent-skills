"""HTML → Confluence Cloud storage-format XML converter.

The converter walks one parsed richdoc HTML chapter and produces:

- A storage-format XML body string (XHTML + `<ac:…>` macros + image
  placeholder tokens) ready for `POST /pages` or `PUT /pages/{id}`.
- A list of `PendingAttachment` entries describing every binary that has
  to be uploaded to the page *before* the body becomes valid. Each
  pending entry carries a token (e.g. `@@ATTACHMENT:abc123@@`) that
  appears verbatim in the storage XML and gets replaced with a real
  `<ac:image><ri:attachment ri:filename="…"/></ac:image>` reference once
  the upload completes.

This deferred-binding model lets us:

1. Compose the storage body without making any network call (so
   `--dry-run` works fully offline).
2. Upload attachments only once we know the page id (created/updated
   first with a placeholder body, then re-saved after upload). For an
   existing page we upload first then update once.

Like the md / docx exporters this module exposes a `_Converter` state
machine and a dispatch table populated by `handler_table.py`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import lxml.etree as ET

from ...export.common.assets import AssetStore
from ...export.common.walker import (
    body_of,
    element_source as _element_source,  # noqa: F401 — re-exported for handlers
    inline_text as _inline_text,
    parse_html,
)


# ---------------------------------------------------------------------------
# Dispatch registry — populated by handler_table.py
# ---------------------------------------------------------------------------

HANDLERS: dict[str, Callable[["_Converter", "ET._Element"], None]] = {}


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingAttachment:
    """One binary asset that has to be uploaded to the page."""

    token: str          # placeholder marker in the storage XML
    filename: str       # stable filename used on Confluence
    data: bytes
    mime: str
    align: str = "center"   # "center", "left", "right" — applied via ac:align
    is_inline: bool = False  # true → no ac:align, embedded inline


@dataclass(frozen=True)
class TocEntry:
    """One node in a book's rd-toc tree, used by `_h_rd_toc` to render an
    inline Contents block with cross-page links resolved by the pipeline.
    """

    title: str
    href: str | None          # original href as written in rd-chapter, if any
    target_rel: Path | None   # resolved relative to book root, or None for group / external
    children: tuple["TocEntry", ...] = ()


@dataclass
class StorageResult:
    """What the converter produces for one chapter."""

    body: str
    title: str
    pending: list[PendingAttachment] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    math_rendered: int = 0
    math_failed: int = 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def html_to_storage(
    source: str,
    *,
    asset_base: Path,
    include_remote_images: bool = False,
    render_diagrams: bool = True,
    render_math: bool = True,
    diagram_endpoint: str = "https://kroki.io",
    cross_page_links: dict[str, str] | None = None,
    title_override: str | None = None,
    chapter_rel: Path | None = None,
    toc_entries: list[TocEntry] | None = None,
) -> StorageResult:
    """Convert one richdoc HTML chapter into Confluence storage format.

    `cross_page_links` maps relative `.html` hrefs (as written in the
    source) → already-known Confluence page URLs, for book chapter
    cross-links. Anything not in the map is preserved as-is and rendered
    by Confluence as a regular external link.

    `title_override` is used by the pipeline to inject the resolved
    chapter title from `<rd-toc>`; when omitted the converter picks
    `<rd-hero title>` or first `<h1>` or the doc `<title>`.

    `chapter_rel` is the chapter's path relative to the book root. It
    drives href normalisation in `_h_a` so `./other.html`, `other.html`,
    and `../sub/other.html` all resolve to the same chapter. `None` in
    single-file mode.

    `toc_entries` is the rd-toc tree shared by every chapter in a book.
    `_h_rd_toc` uses it to emit an inline Contents block. `None` outside
    book mode — in which case `rd-toc` is dropped as before.
    """
    # Ensure dispatch table is populated. Side-effect import only.
    from . import handler_table  # noqa: F401, PLC0415

    root = parse_html(source)
    target = body_of(root)

    conv = _Converter(
        asset_base=asset_base,
        asset_store=AssetStore(),
        include_remote_images=include_remote_images,
        render_diagrams=render_diagrams,
        render_math=render_math,
        diagram_endpoint=diagram_endpoint,
        cross_page_links=dict(cross_page_links or {}),
        chapter_rel=chapter_rel,
        toc_entries=list(toc_entries) if toc_entries else None,
    )
    title = title_override or _resolve_title(root)
    conv.render_children(target)

    body = conv.finalise()
    return StorageResult(
        body=body,
        title=title or "Untitled",
        pending=conv.pending,
        dropped=conv.dropped,
        missing=conv.asset_store.missing,
        diagrams_rendered=conv.diagrams_rendered,
        diagrams_failed=conv.diagrams_failed,
        math_rendered=conv.math_rendered,
        math_failed=conv.math_failed,
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


_WS = re.compile(r"\s+")


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
    # Citation collection (scattered rd-ref → single bibliography below)
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

    def _spawn_sub(self) -> "_Converter":
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
        sub.pending = self.pending  # shared list — handlers append directly
        sub.dropped = self.dropped
        sub.refs_collected = self.refs_collected
        sub.refs_order = self.refs_order
        return sub

    def render_inline(self, el: ET._Element) -> str:  # noqa: SLF001
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

    def render_block_inner(self, el: ET._Element) -> str:  # noqa: SLF001
        """Render the children of `el` as a block-level XML fragment."""
        sub = self._spawn_sub()
        sub.render_children(el)
        self._merge_counters(sub)
        out = "".join(sub.chunks).strip()
        return out

    def render_block_inner_wrapped(self, el: ET._Element) -> str:  # noqa: SLF001
        """Like `render_block_inner` but wraps bare inline content in a
        single <p> so block containers (rd-card, rd-section, …) don't end
        up with naked text outside any block element."""
        inner = self.render_block_inner(el)
        if not inner:
            return ""
        # If the rendered output already starts with a block-level tag,
        # leave it alone. Otherwise wrap in <p>.
        stripped = inner.lstrip()
        if stripped.startswith("<") and _BLOCK_OPENER.match(stripped):
            return inner
        return f"<p>{inner}</p>"

    def render_children(self, el: ET._Element) -> None:  # noqa: SLF001
        if el.text:
            self.write_text(_inline_text(el.text))
        for child in el:
            self.render(child)
            if child.tail:
                self.write_text(_inline_text(child.tail))

    # ---- dispatch --------------------------------------------------------

    def render(self, el: ET._Element) -> None:  # noqa: SLF001
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
        # We intentionally do NOT collapse runs of whitespace here. The
        # output contains CDATA-wrapped code bodies where every space and
        # tab is significant; Confluence is happy with ambient whitespace
        # between block tags, so leaving it alone keeps the body safe.
        out = "".join(self.chunks)
        out = re.sub(r"\n{3,}", "\n\n", out)
        out = _wrap_in_layout(out.strip())
        return out

    def _refs_emitted_inline(self) -> bool:
        # If an rd-references block already rendered, it'd have written a
        # "<h2>References</h2>" heading; treat that as the signal we don't
        # need to repeat ourselves.
        joined = "".join(self.chunks[-200:]) if len(self.chunks) > 200 else "".join(self.chunks)
        return f"<h2>{xml_escape(self.refs_section_title)}</h2>" in joined

    def _emit_collected_bibliography(self) -> None:
        items: list[str] = []
        seen: set[str] = set()
        for key in self.refs_order:
            if key in seen or key not in self.refs_collected:
                continue
            seen.add(key)
            items.append(_format_ref_li(self.refs_collected[key]))
        # Uncited refs still appear, in source order, after the cited ones.
        for key, attrs in self.refs_collected.items():
            if key in seen:
                continue
            seen.add(key)
            items.append(_format_ref_li(attrs))
        if not items:
            return
        self.write_block(
            f"<h2>{xml_escape(self.refs_section_title)}</h2>"
            f"<ol>{''.join(items)}</ol>"
        )

    def _merge_counters(self, sub: "_Converter") -> None:
        self.diagrams_rendered += sub.diagrams_rendered
        self.diagrams_failed += sub.diagrams_failed
        self.math_rendered += sub.math_rendered
        self.math_failed += sub.math_failed


# ---------------------------------------------------------------------------
# XML escape helpers
# ---------------------------------------------------------------------------


def xml_escape(text: str) -> str:
    """Escape `&`, `<`, `>`, `"`, `'` for inclusion in an XML body."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def xml_attr(text: str) -> str:
    """Escape a value going into an XML attribute."""
    return xml_escape(text)


def th_bold(inner_xml: str) -> str:
    """Build a `<th>` cell whose inline content is wrapped to render bold
    in Confluence's modern editor.

    Confluence does not auto-bold `<th>` in its modern table renderer;
    only a light grey background distinguishes header cells. Wrapping
    the cell body in `<p><strong>...</strong></p>` matches the shape
    Atlassian's own templates emit and survives the storage-format
    round-trip when pages are pushed via the v2 API.

    The empty-cell fallback (`&#160;`) keeps an empty header cell at the
    usual cell height instead of collapsing to a thin sliver.
    """
    return f"<th><p><strong>{inner_xml or '&#160;'}</strong></p></th>"


def cdata_safe(text: str) -> str:
    """Escape any embedded `]]>` so `text` is safe inside a CDATA block."""
    # Split `]]>` into `]]]]><![CDATA[>` so each fragment lives inside its
    # own CDATA section.
    return text.replace("]]>", "]]]]><![CDATA[>")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_BLOCK_OPENER = re.compile(
    r"^<(?:h[1-6]|p|ul|ol|li|table|thead|tbody|tr|th|td|blockquote|hr|pre|"
    r"figure|figcaption|div|ac:structured-macro|ac:layout|ac:image|ac:task-list)\b",
    re.IGNORECASE,
)


def _resolve_title(root: ET._Element) -> str | None:  # noqa: SLF001
    """Mirror book.py's title resolution — used when no override is passed."""
    hero = next(iter(root.iter("rd-hero")), None)
    if hero is not None:
        t = hero.get("title")
        if t and t.strip():
            return _WS.sub(" ", t.strip())
    h1 = next(iter(root.iter("h1")), None)
    if h1 is not None:
        text = " ".join("".join(h1.itertext()).split()).strip()
        if text:
            return text
    title_el = next(iter(root.iter("title")), None)
    if title_el is not None and title_el.text and title_el.text.strip():
        return title_el.text.strip()
    return None


def _format_ref_li(attrs: dict[str, str]) -> str:
    """Render one bibliography entry as an <li>. Mirrors the md export."""
    author = (attrs.get("author") or "").strip()
    title = (attrs.get("title") or "").strip()
    url = (attrs.get("url") or "").strip()
    date = (attrs.get("date") or "").strip()
    publisher = (attrs.get("publisher") or "").strip()
    note = (attrs.get("note") or "").strip()  # already XML
    bits: list[str] = []
    if author:
        bits.append(xml_escape(author))
    if title:
        if url:
            bits.append(
                f'"<a href="{xml_attr(url)}">{xml_escape(title)}</a>"'
            )
        else:
            bits.append(f'"{xml_escape(title)}"')
    elif url:
        bits.append(f'<a href="{xml_attr(url)}">{xml_escape(url)}</a>')
    if publisher:
        bits.append(xml_escape(publisher))
    if date:
        bits.append(xml_escape(date))
    line = ". ".join(bits) + ("." if bits else "")
    if note:
        line += f" {note}"
    return f"<li>{line}</li>"


# ---------------------------------------------------------------------------
# Layout post-processing
# ---------------------------------------------------------------------------


_AC_NS = "http://atlassian.com/content"
_RI_NS = "http://atlassian.com/resource/identifier"
_AT_NS = "http://www.w3.org/1999/xlink"
_AC = f"{{{_AC_NS}}}"
_RI = f"{{{_RI_NS}}}"
_AT = f"{{{_AT_NS}}}"
_NSMAP = {"ac": _AC_NS, "ri": _RI_NS, "at": _AT_NS}
_NS_PREFIX_RE = re.compile(
    r' xmlns:(?:ac|ri|at)="(?:'
    + re.escape(_AC_NS)
    + "|"
    + re.escape(_RI_NS)
    + "|"
    + re.escape(_AT_NS)
    + ')"'
)


def _wrap_in_layout(body: str) -> str:
    """Wrap the page body in ``<ac:layout>`` when it contains any
    ``<ac:layout-section>``. Confluence requires layout-sections to be
    direct children of ``<ac:layout>`` at the body top level; this pass
    groups any peer content between layout-sections into ``fixed-width``
    sections so the entire body becomes a sequence of layout-sections.

    Pages with no layout-section pass through unchanged.
    """
    if "<ac:layout-section" not in body:
        return body
    wrapped = (
        f'<root xmlns:ac="{_AC_NS}" xmlns:ri="{_RI_NS}" xmlns:at="{_AT_NS}">'
        f"{body}</root>"
    )
    parser = ET.XMLParser(strip_cdata=False)
    try:
        root = ET.fromstring(wrapped, parser)  # noqa: S320 — trusted, self-generated
    except ET.XMLSyntaxError:
        # Defensive: never break the publish if a handler emitted
        # something the parser refuses. The legacy section macro path
        # never tripped this; modern panels likewise stay well-formed.
        return body
    layout = ET.Element(f"{_AC}layout", nsmap=_NSMAP)
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


def dedent(text: str) -> str:
    """Same dedent semantics as the md / docx converters."""
    text = text.lstrip("\n").rstrip()
    lines = text.split("\n")
    min_indent = None
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
