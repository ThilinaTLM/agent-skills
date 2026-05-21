"""Plain-HTML element handlers for the Confluence exporter.

Each handler mirrors a small piece of HTML that survives the Confluence
importer's whitelist. Anything Confluence drops on import (code blocks,
equations, figure semantics) is rasterised by the rd-* handlers and
embedded as `<img>`.
"""

from __future__ import annotations

import re

import lxml.etree as ET
import lxml.html as LH

from .converter import (
    _Converter,
    _ListCtx,
    attr,
    escape_attr,
    escape_text,
)


# ---------------------------------------------------------------------------
# Headings, paragraphs, inline emphasis
# ---------------------------------------------------------------------------


def _h_h(level: int):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
        inner = c.render_inline(el).strip()
        if not inner:
            return
        if level == 1 and not c.title:
            # Remember the first H1 as the page title.
            text_only = re.sub(r"<[^>]+>", "", inner).strip()
            if text_only:
                c.title = text_only
        c.write_block(f"<h{level}>{inner}</h{level}>")

    return handler


def _h_p(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_inline(el).strip()
    if not inner:
        return
    c.write_block(f"<p>{inner}</p>")


def _h_br(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.write("<br>")


def _h_hr(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.write_block("<hr>")


def _h_inline_tag(tag: str):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
        inner = c.render_inline(el)
        if not inner.strip():
            return
        c.write(f"<{tag}>{inner}</{tag}>")

    return handler


def _h_code_inline(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Inline <code> survives Confluence's importer — emit it verbatim.
    text = (el.text or "") + "".join(
        (LH.tostring(child, encoding="unicode", method="text") or "") + (child.tail or "")
        for child in el
    )
    if not text:
        return
    c.write(f"<code>{escape_text(text)}</code>")


def _h_pre(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Vanilla `<pre>` block — rasterise as a code image so it stays a
    code block in Confluence rather than collapsing to plain prose."""
    code = el.find("code")
    if code is not None and len(el) == 1:
        text = code.text or ""
        cls = code.get("class") or ""
        m = re.search(r"language-(\S+)", cls)
        lang = m.group(1) if m else None
    else:
        text = (el.text or "") + "".join(
            (LH.tostring(child, encoding="unicode", method="text") or "") + (child.tail or "")
            for child in el
        )
        lang = None
    text = text.rstrip("\n")
    if not text.strip():
        return
    _emit_code(c, text=text, lang=lang, title=None, line_numbers=False)


def _emit_code(
    c: _Converter,
    *,
    text: str,
    lang: str | None,
    title: str | None,
    line_numbers: bool = False,
) -> None:
    """Either queue a PNG render (default) or emit a `<pre><code>` fallback
    (when --no-code-images is in effect)."""
    if c.render_code_images:
        ph = c.queue_code_image(
            text, lang=lang, title=title, line_numbers=line_numbers
        )
        alt_bits = []
        if title:
            alt_bits.append(title)
        if lang:
            alt_bits.append(lang)
        alt = " · ".join(alt_bits) or "code"
        c.write_block(
            f'<p><img src="{ph}" alt="{escape_attr(alt)}"></p>'
        )
        return
    # Non-image fallback: `<pre><code>` survives Confluence as plain text
    # but at least keeps the source intact for round-trip editing.
    cls = f' class="language-{escape_attr(lang)}"' if lang else ""
    label = f"<p><strong>{escape_text(title)}</strong></p>\n" if title else ""
    c.write_block(
        f"{label}<pre><code{cls}>{escape_text(text)}</code></pre>"
    )


def _h_blockquote(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_block_inner(el).strip()
    if not inner:
        return
    c.write_block(f"<blockquote>{inner}</blockquote>")


# ---------------------------------------------------------------------------
# Links and images
# ---------------------------------------------------------------------------


_REL_HTML = re.compile(r"^([^:/?#][^?#]*?)\.html?(#[^?]*)?(\?.*)?$")


def _rewrite_doc_link(href: str, *, slug_map: dict[str, str] | None = None) -> str:
    """Relative `.html` / `.htm` hrefs inside a book bundle get rewritten to
    the matching page slug + `.html` so chapters cross-link inside the
    imported space. Absolute URLs pass through untouched."""
    if not href or href.startswith(("#", "//")) or ":" in href.split("/", 1)[0]:
        return href
    m = _REL_HTML.match(href)
    if not m:
        return href
    stem = m.group(1)
    fragment = m.group(2) or ""
    query = m.group(3) or ""
    # If we have a slug map (pipeline-side), use it; otherwise just keep the
    # stem unchanged with `.html`.
    if slug_map and stem in slug_map:
        stem = slug_map[stem]
    return f"{stem}.html{query}{fragment}"


def _h_a(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    href = el.get("href") or ""
    inner = c.render_inline(el)
    if not inner.strip():
        inner = escape_text(href)
    if not href:
        c.write(inner)
        return
    c.write(f'<a href="{escape_attr(_rewrite_doc_link(href))}">{inner}</a>')


def _h_img(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    src = el.get("src") or ""
    alt = el.get("alt") or ""
    title = el.get("title") or ""
    if not src:
        return
    new_src, _ref = c.rewrite_image_src(src)
    parts = [f'<img src="{escape_attr(new_src)}"']
    parts.append(attr("alt", alt))
    if title:
        parts.append(attr("title", title))
    parts.append(">")
    c.write("".join(parts))


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def _h_list(kind: str):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
        depth = len(c.list_stack)
        c.list_stack.append(_ListCtx(kind=kind, depth=depth))
        parts: list[str] = [f"<{kind}>"]
        for child in el:
            if not isinstance(child.tag, str):
                continue
            if child.tag.lower() != "li":
                continue
            body = c.render_block_inner(child).strip()
            parts.append(f"  <li>{body}</li>")
        parts.append(f"</{kind}>")
        c.list_stack.pop()
        block = "\n".join(parts)
        if depth == 0:
            c.write_block(block)
        else:
            c.write("\n" + block + "\n")

    return handler


def _h_li(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Only reached when a stray <li> appears outside a list — render its
    # contents inline so we don't lose the text.
    c.render_children(el)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _h_table(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    rows = [tr for tr in el.iter("tr")]
    if not rows:
        return
    parts: list[str] = ["<table>"]
    head_rows: list[ET._Element] = []
    body_rows: list[ET._Element] = []
    for tr in rows:
        is_header = any(
            isinstance(cell.tag, str) and cell.tag.lower() == "th" for cell in tr
        )
        (head_rows if is_header else body_rows).append(tr)
    if head_rows:
        parts.append("  <thead>")
        for tr in head_rows:
            parts.append("    " + _render_row(c, tr, force_th=True))
        parts.append("  </thead>")
    if body_rows:
        parts.append("  <tbody>")
        for tr in body_rows:
            parts.append("    " + _render_row(c, tr))
        parts.append("  </tbody>")
    parts.append("</table>")
    c.write_block("\n".join(parts))


def _render_row(c: _Converter, tr: ET._Element, *, force_th: bool = False) -> str:
    cells: list[str] = []
    for cell in tr:
        if not isinstance(cell.tag, str):
            continue
        t = cell.tag.lower()
        if t not in ("th", "td"):
            continue
        tag = "th" if (force_th or t == "th") else "td"
        inner = c.render_inline(cell).strip()
        cells.append(f"<{tag}>{inner}</{tag}>")
    return "<tr>" + "".join(cells) + "</tr>"


# ---------------------------------------------------------------------------
# Generic fallbacks
# ---------------------------------------------------------------------------


def _h_unwrap(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_drop(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    if isinstance(el.tag, str) and el.tag.lower().startswith("rd-"):
        c.dropped.append(el.tag.lower())
