"""Plain-HTML handlers for the Confluence storage-format converter.

Confluence's storage format is XHTML plus a small set of `<ac:…>` macro
tags. Most plain HTML survives verbatim with minimal massaging:

- Block elements emit clean open/close pairs.
- `<a href="…">` rewrites relative `.html` hrefs that map to known
  Confluence pages.
- `<img src="…">` becomes an `<ac:image>` reference pointing at an
  attachment uploaded under the same filename.
- `<pre>` / `<pre><code>` become a native `code` macro.

Inline formatting (`<strong>`, `<em>`, `<s>`, `<code>`, `<sup>`, `<sub>`,
`<br>`, `<hr>`) passes through.
"""

from __future__ import annotations

import re
from pathlib import Path

import lxml.etree as ET
import lxml.html as LH

from .converter import (
    _Converter,
    cdata_safe,
    dedent,
    xml_attr,
    xml_escape,
)


# ---------------------------------------------------------------------------
# Inline / structural HTML
# ---------------------------------------------------------------------------


def _h_h(level: int):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
        inner = c.render_inline(el).strip()
        if not inner:
            return
        c.write_block(f"<h{level}>{inner}</h{level}>")

    return handler


def _h_p(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_inline(el).strip()
    if not inner:
        return
    c.write_block(f"<p>{inner}</p>")


def _h_br(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.write("<br/>")


def _h_hr(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.write_block("<hr/>")


def _wrap(tag: str):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
        inner = c.render_inline(el).strip()
        if not inner:
            return
        c.write(f"<{tag}>{inner}</{tag}>")

    return handler


def _h_code_inline(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Inline <code> — get the literal text, escape, wrap in <code>.
    text = el.text or ""
    for child in el:
        text += LH.tostring(child, encoding="unicode", method="text") or ""
        if child.tail:
            text += child.tail
    text = text.strip()
    if not text:
        return
    c.write(f"<code>{xml_escape(text)}</code>")


def _h_pre(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Render <pre> / <pre><code class="language-X"> as a native code macro."""
    code = el.find("code")
    lang = ""
    if code is not None and len(el) == 1:
        text = code.text or ""
        cls = code.get("class") or ""
        m = re.search(r"language-(\S+)", cls)
        if m:
            lang = m.group(1)
    else:
        text = (el.text or "") + "".join(
            (LH.tostring(child, encoding="unicode", method="text") or "")
            + (child.tail or "")
            for child in el
        )
    emit_code_macro(c, text, lang=lang, title=None)


def emit_code_macro(
    c: _Converter, text: str, *, lang: str, title: str | None,
) -> None:
    """Build a native code-block macro. Shared by <pre>, <rd-code>, etc."""
    body = dedent(text)
    params: list[str] = []
    if lang:
        params.append(_macro_param("language", lang))
    if title:
        params.append(_macro_param("title", title))
    params_xml = "".join(params)
    safe_body = cdata_safe(body)
    c.write_block(
        '<ac:structured-macro ac:name="code">'
        f"{params_xml}"
        f"<ac:plain-text-body><![CDATA[{safe_body}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def _macro_param(name: str, value: str) -> str:
    return (
        f'<ac:parameter ac:name="{xml_attr(name)}">'
        f"{xml_escape(value)}"
        "</ac:parameter>"
    )


def _h_blockquote(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_block_inner_wrapped(el)
    if not inner:
        return
    c.write_block(f"<blockquote>{inner}</blockquote>")


# ---------------------------------------------------------------------------
# Links and images
# ---------------------------------------------------------------------------


_REL_HTML = re.compile(r"^([^:/?#][^?#]*?)\.html?(#[^?]*)?(\?.*)?$")

# Virtual root used so `Path.resolve()` collapses `./` and `../` without
# touching the filesystem. The actual directory does not need to exist;
# resolve(strict=False) is the default since Python 3.6.
_VIRTUAL_BOOK_ROOT = Path("/__richdoc_book__")


def _resolve_chapter_href(c: _Converter, href: str) -> str | None:  # noqa: SLF001
    """Map a relative `.html` href on the current chapter onto a known
    Confluence URL, or return None if no rewrite applies.

    Handles `./other.html`, `other.html`, `../sub/other.html`, and any
    `#fragment` / `?query` tail consistently — the lookup key is the
    chapter's path relative to the book root, which is what the pipeline
    stores in `cross_page_links`.
    """
    if not c.cross_page_links:
        return None
    if not href or href.startswith(("#", "//")):
        return None
    first = href.split("/", 1)[0]
    if ":" in first:
        return None
    m = _REL_HTML.match(href)
    if not m:
        return None
    raw_stem = m.group(1) + ".html"
    fragment = m.group(2) or ""
    base = _VIRTUAL_BOOK_ROOT
    if c.chapter_rel is not None:
        base = (_VIRTUAL_BOOK_ROOT / c.chapter_rel).parent
    try:
        resolved = (base / raw_stem).resolve()
        key = resolved.relative_to(_VIRTUAL_BOOK_ROOT)
    except (OSError, ValueError):
        return None
    url = (
        c.cross_page_links.get(str(key))
        or c.cross_page_links.get(key.as_posix())
    )
    return (url + fragment) if url else None


def _h_a(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    href = (el.get("href") or "").strip()
    inner = c.render_inline(el).strip()
    if not inner:
        inner = xml_escape(href)
    if not href:
        c.write(inner)
        return
    rewritten = _resolve_chapter_href(c, href)
    if rewritten:
        href = rewritten
    c.write(f'<a href="{xml_attr(href)}">{inner}</a>')


def _h_img(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    src = (el.get("src") or "").strip()
    alt = el.get("alt") or ""
    if not src:
        return
    pa = c.resolve_local_image(src)
    if pa is None:
        # Couldn't load — fall back to a plain external <a> link so the
        # information isn't lost.
        c.write(
            f'<a href="{xml_attr(src)}">{xml_escape(alt or src)}</a>'
        )
        return
    c.write_block(pa.token)


# ---------------------------------------------------------------------------
# Lists and tables
# ---------------------------------------------------------------------------


def _h_list(kind: str):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
        items: list[str] = []
        for child in el:
            if not (isinstance(child.tag, str) and child.tag.lower() == "li"):
                continue
            body = c.render_block_inner(child).strip()
            items.append(f"<li>{body or ''}</li>")
        if not items:
            return
        c.write_block(f"<{kind}>{''.join(items)}</{kind}>")

    return handler


def _h_li(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Handled inside _h_list; if encountered loose, render children.
    c.render_children(el)


def _h_table(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Emit a native `<table>` preserving header / body rows.

    Confluence ignores `<thead>` / `<tbody>` containers but does render
    `<th>` vs `<td>` correctly. We keep the structure shallow.
    """
    rows_xml: list[str] = []
    for tr in el.iter("tr"):
        cells: list[str] = []
        any_th = False
        for cell in tr:
            if not isinstance(cell.tag, str):
                continue
            t = cell.tag.lower()
            if t not in ("th", "td"):
                continue
            if t == "th":
                any_th = True
            inner = c.render_block_inner(cell).strip()
            if not inner:
                # Confluence renders an empty cell as a thin sliver; pad
                # with a non-breaking space for visual stability.
                inner = "&#160;"
            cells.append(f"<{t}>{inner}</{t}>")
        if not cells:
            continue
        rows_xml.append(f"<tr>{''.join(cells)}</tr>")
        del any_th
    if not rows_xml:
        return
    c.write_block(f"<table><tbody>{''.join(rows_xml)}</tbody></table>")


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------


def _h_unwrap(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_drop(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    if isinstance(el.tag, str) and el.tag.lower().startswith("rd-"):
        c.dropped.append(el.tag.lower())


def _h_figure(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """A plain <figure>: render children, append <figcaption> as <em>.

    We don't emit `<figure>` itself — Confluence's storage format drops
    `<figure>` on save, so we keep the children flat.
    """
    caption: str | None = None
    body_parts: list[str] = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        if child.tag.lower() == "figcaption":
            caption = c.render_inline(child).strip()
            continue
        # Render this child as a standalone block. We borrow render() and
        # capture its output via the sub-buffer.
        before = len(c.chunks)
        c.render(child)
        if child.tail:
            tail = child.tail.strip()
            if tail:
                c.write_text(tail)
        body_parts.append("".join(c.chunks[before:]))
        del c.chunks[before:]
    body = "".join(body_parts).strip()
    if body:
        c.write_block(body)
    if caption:
        c.write_block(f"<p><em>{caption}</em></p>")


# inline-text wrap helpers
_h_strong = _wrap("strong")
_h_em = _wrap("em")
_h_s = _wrap("s")
_h_sup = _wrap("sup")
_h_sub = _wrap("sub")
