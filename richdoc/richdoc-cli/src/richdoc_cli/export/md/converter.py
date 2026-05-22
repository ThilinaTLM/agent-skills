"""HTML → GitHub-flavored markdown converter for richdoc documents.

The converter walks the parsed HTML tree once and dispatches each element
to a tag-specific handler. Plain HTML produces CommonMark / GFM; rd-*
custom elements are mapped to the closest markdown idiom (admonitions,
tables, fenced code blocks, footnotes, definition lists, …).

This module owns the `_Converter` state machine and the small set of
generic helpers used by both plain-HTML and rd-* handler modules. The
actual element handlers live in `handlers_plain.py` / `handlers_rd.py`,
and the dispatch dict is assembled in `handler_table.py`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import lxml.etree as ET

from ..common.assets import AssetStore
from ..common.references import RefRenderer
from ..common.references import format_ref as _format_ref_canonical
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

_MD_REF_RENDERER = RefRenderer(
    escape=lambda s: s,
    link=lambda text, url: f"[{text}]({url})",
    url_only=lambda url: f"<{url}>",
)

# Re-exports for sibling handler modules. Listed here so linters and
# type checkers treat them as intentional.
__all__ = [
    "HANDLERS",
    "_Converter",
    "_ListCtx",
    "_dedent",
    "_element_source",
    "_emit_fenced",
    "_inline_text",
    "_strip_outer_blanks",
    "format_ref",
    "html_to_markdown",
]

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def html_to_markdown(
    source: str,
    *,
    asset_store: AssetStore | None = None,
    asset_base: Path | None = None,
    include_remote_images: bool = False,
    assets_subdir: str = "assets",
) -> tuple[str, list[str]]:
    """Render the document body as markdown.

    When `asset_store` is supplied, every image reference is registered with
    the store and the markdown src is rewritten to `<assets_subdir>/<local>`.
    `asset_base` must be the directory the HTML lives in so relative paths
    resolve correctly. Remote (http/https) image URLs are fetched only when
    `include_remote_images` is True; otherwise they're kept as-is.

    Returns (text, dropped_tag_names).
    """
    # Ensure handler registration has fired exactly once.
    from . import handler_table  # noqa: F401 — side-effect import

    root = parse_html(source)
    target = body_of(root)

    conv = _Converter(
        asset_store=asset_store,
        asset_base=asset_base,
        include_remote_images=include_remote_images,
        assets_subdir=assets_subdir,
    )
    conv.render_children(target)
    return conv.finalise(), conv.dropped


# ---------------------------------------------------------------------------
# Dispatch registry — populated by handler_table.py
# ---------------------------------------------------------------------------

HANDLERS: dict[str, Callable[[_Converter, ET._Element], None]] = {}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


_LEADING_NL = re.compile(r"^\n+")
_TRAILING_NL = re.compile(r"\n+$")


@dataclass
class _ListCtx:
    kind: str  # "ul" | "ol"
    index: int = 1
    depth: int = 0  # 0-based nesting


@dataclass
class _Converter:
    chunks: list[str] = field(default_factory=list)
    list_stack: list[_ListCtx] = field(default_factory=list)
    in_pre: bool = False
    # footnote / citation registries
    footnotes: list[str] = field(default_factory=list)  # markdown bodies, index = N-1
    ref_entries: dict[str, str] = field(default_factory=dict)  # key -> formatted ref body
    ref_order: list[str] = field(default_factory=list)  # cite order
    refs_section_title: str = "References"
    refs_collected: dict[str, dict[str, str]] = field(default_factory=dict)  # key -> attrs
    dropped: list[str] = field(default_factory=list)
    # asset rewriting (optional)
    asset_store: AssetStore | None = None
    asset_base: Path | None = None
    include_remote_images: bool = False
    assets_subdir: str = "assets"
    _cite_counter: int = 0

    def rewrite_image_src(self, src: str) -> str:
        """If asset collection is active, register the image and return the
        rewritten path. Otherwise return `src` unchanged."""
        if not src or self.asset_store is None or self.asset_base is None:
            return src
        if src.startswith("data:") or src.startswith("#"):
            return src
        ref = self.asset_store.add(
            src,
            base_dir=self.asset_base,
            fetch_remote=self.include_remote_images,
        )
        if ref is None:
            return src
        subdir = self.assets_subdir.strip("/")
        return f"{subdir}/{ref.local_name}" if subdir else ref.local_name

    # ---- output helpers ---------------------------------------------------

    def write(self, text: str) -> None:
        if not text:
            return
        self.chunks.append(text)

    def write_block(self, text: str) -> None:
        """Emit a block-level chunk separated from surroundings by blank lines."""
        if not text:
            return
        text = _TRAILING_NL.sub("", text)
        prev = "".join(self.chunks[-1:]) if self.chunks else ""
        if prev and not prev.endswith("\n\n"):
            if prev.endswith("\n"):
                self.chunks.append("\n")
            else:
                self.chunks.append("\n\n")
        self.chunks.append(text)
        self.chunks.append("\n\n")

    def _spawn_sub(self) -> _Converter:
        sub = _Converter(
            asset_store=self.asset_store,
            asset_base=self.asset_base,
            include_remote_images=self.include_remote_images,
            assets_subdir=self.assets_subdir,
        )
        sub.in_pre = self.in_pre
        sub.list_stack = self.list_stack[:]
        sub._cite_counter = self._cite_counter
        sub.footnotes = self.footnotes
        sub.refs_collected = self.refs_collected
        sub.ref_order = self.ref_order
        sub.ref_entries = self.ref_entries
        sub.dropped = self.dropped
        return sub

    def render_inline(self, el: ET._Element) -> str:
        """Render `el` and its children as an inline string (no block separators)."""
        sub = self._spawn_sub()
        # render only children, including the element's text
        if el.text:
            sub.write(_inline_text(el.text))
        for child in el:
            sub.render(child)
            if child.tail:
                sub.write(_inline_text(child.tail))
        self._cite_counter = sub._cite_counter
        return "".join(sub.chunks)

    def render_block_inner(self, el: ET._Element) -> str:
        """Render the children of `el` to markdown (block-level), returning the chunk."""
        sub = self._spawn_sub()
        sub.render_children(el)
        self._cite_counter = sub._cite_counter
        body = _strip_outer_blanks(sub.finalise_body())
        # The first inline text node often starts with whitespace from HTML
        # indentation — strip it so block bodies don't render with a leading
        # space.
        if body and body[0] in " \t":
            body = body.lstrip(" \t")
        return body

    def render_children(self, el: ET._Element) -> None:
        if el.text:
            self.write(_inline_text(el.text))
        for child in el:
            self.render(child)
            if child.tail:
                self.write(_inline_text(child.tail))

    # ---- dispatch ---------------------------------------------------------

    def render(self, el: ET._Element) -> None:
        tag = el.tag
        if not isinstance(tag, str):
            return  # comments / PIs
        tag = tag.lower()
        handler = HANDLERS.get(tag)
        if handler is None:
            if tag.startswith("rd-"):
                self.dropped.append(tag)
            # unwrap unknown elements
            self.render_children(el)
            return
        handler(self, el)

    # ---- finalisation ----------------------------------------------------

    def finalise_body(self) -> str:
        out = "".join(self.chunks)
        # Normalise blank-but-not-empty lines (" \n") to truly blank lines.
        out = re.sub(r"\n[ \t]+\n", "\n\n", out)
        # Strip trailing whitespace from every non-code line.
        out = _strip_trailing_ws_outside_fences(out)
        # Collapse 3+ blank lines to 2.
        out = re.sub(r"\n{3,}", "\n\n", out)
        return out

    def finalise(self) -> str:
        body = self.finalise_body()
        # Append footnotes section.
        if self.footnotes:
            lines = ["", ""]
            for i, fn_body in enumerate(self.footnotes, start=1):
                # GFM footnotes: continuation lines must be indented.
                indented = fn_body.replace("\n", "\n    ").strip()
                lines.append(f"[^{i}]: {indented}")
            body = body.rstrip() + "\n" + "\n".join(lines) + "\n"
        # Append references section if any.
        if self.ref_order or self.refs_collected:
            lines = ["", "", f"## {self.refs_section_title}", ""]
            seen: set[str] = set()
            n = 0
            for key in self.ref_order:
                if key in seen or key not in self.refs_collected:
                    continue
                seen.add(key)
                n += 1
                lines.append(f"{n}. {format_ref(self.refs_collected[key])}")
            for key, attrs in self.refs_collected.items():
                if key in seen:
                    continue
                n += 1
                lines.append(f"{n}. {format_ref(attrs)}")
            body = body.rstrip() + "\n" + "\n".join(lines) + "\n"
        body = body.lstrip("\n")
        if not body.endswith("\n"):
            body += "\n"
        return body


# ---------------------------------------------------------------------------
# Shared helpers (used by both plain-HTML and rd-* handler modules)
# ---------------------------------------------------------------------------


def _dedent(text: str) -> str:
    """Local alias for the canonical `export.common.text.dedent`.

    Existing handler modules import `_dedent` from this module; the
    re-export keeps their imports stable until they're moved to import
    the canonical name directly.
    """
    return _dedent_canonical(text)


def _strip_trailing_ws_outside_fences(text: str) -> str:
    """Strip trailing spaces on each line, but leave code fences alone."""
    out: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        stripped = line.rstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append(stripped)
            continue
        if in_fence:
            out.append(line)
        else:
            out.append(stripped)
    return "\n".join(out)


def _strip_outer_blanks(text: str) -> str:
    return _TRAILING_NL.sub("", _LEADING_NL.sub("", text))


def _emit_fenced(c: _Converter, text: str, lang: str, title: str | None = None) -> None:
    body = text.rstrip("\n")
    fence = "```"
    # use longer fence if body itself contains a fence
    while fence in body:
        fence += "`"
    header = fence + (lang or "")
    parts = [header]
    if title:
        parts.append(f"// {title}")
    parts.append(body if body else "")
    parts.append(fence)
    c.write_block("\n".join(parts))


def format_ref(attrs: dict[str, str]) -> str:
    """Format a citation entry for the markdown exporter.

    Thin wrapper around ``export.common.references.format_ref`` with
    the markdown-specific link / url-only renderers.
    """
    return _format_ref_canonical(attrs, renderer=_MD_REF_RENDERER)
