"""Plain-HTML element handlers for the markdown converter.

Each handler takes the active `_Converter` plus the element to render and
mutates the converter's chunk buffer. Handlers never return values.
"""

from __future__ import annotations

import re

import lxml.etree as ET
import lxml.html as LH

from .converter import (
    _Converter,
    _emit_fenced,
    _ListCtx,
    _strip_outer_blanks,
)

# ---------------------------------------------------------------------------
# Inline / structural HTML
# ---------------------------------------------------------------------------


def _h_h(level: int):
    def handler(c: _Converter, el: ET._Element) -> None:
        text = _strip_outer_blanks(c.render_inline(el)).strip()
        if not text:
            return
        c.write_block(f"{'#' * level} {text}")

    return handler


def _h_p(c: _Converter, el: ET._Element) -> None:
    text = _strip_outer_blanks(c.render_inline(el)).strip()
    if not text:
        return
    c.write_block(text)


def _h_br(c: _Converter, el: ET._Element) -> None:
    c.write("  \n")


def _h_hr(c: _Converter, el: ET._Element) -> None:
    c.write_block("---")


def _h_strong(c: _Converter, el: ET._Element) -> None:
    inner = c.render_inline(el).strip()
    if inner:
        c.write(f"**{inner}**")


def _h_em(c: _Converter, el: ET._Element) -> None:
    inner = c.render_inline(el).strip()
    if inner:
        c.write(f"*{inner}*")


def _h_s(c: _Converter, el: ET._Element) -> None:
    inner = c.render_inline(el).strip()
    if inner:
        c.write(f"~~{inner}~~")


def _h_code_inline(c: _Converter, el: ET._Element) -> None:
    text = (el.text or "")
    for child in el:
        # rare; flatten
        text += LH.tostring(child, encoding="unicode", method="text") or ""
        if child.tail:
            text += child.tail
    text = text.strip()
    if not text:
        return
    # If text contains backticks, use longer fence.
    backticks = "`"
    while backticks in text:
        backticks += "`"
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    c.write(f"{backticks}{pad}{text}{pad}{backticks}")


def _h_pre(c: _Converter, el: ET._Element) -> None:
    # If pre wraps a single <code>, treat as fenced code block; otherwise as preformatted.
    code = el.find("code")
    if code is not None and len(el) == 1:
        text = (code.text or "")
        lang = ""
        cls = code.get("class") or ""
        m = re.search(r"language-(\S+)", cls)
        if m:
            lang = m.group(1)
        _emit_fenced(c, text, lang)
    else:
        text = (el.text or "") + "".join(
            (LH.tostring(child, encoding="unicode", method="text") or "")
            + (child.tail or "")
            for child in el
        )
        _emit_fenced(c, text, "")


def _h_blockquote(c: _Converter, el: ET._Element) -> None:
    inner = c.render_block_inner(el)
    if not inner.strip():
        return
    quoted = "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))
    c.write_block(quoted)


# ---------------------------------------------------------------------------
# Links and images
# ---------------------------------------------------------------------------


_REL_HTML = re.compile(r"^([^:/?#][^?#]*?)\.html?(#[^?]*)?(\?.*)?$")


def _rewrite_doc_link(href: str) -> str:
    """Relative `.html` / `.htm` hrefs are rewritten to `.md` so a folder of
    exported markdown files is internally navigable. Absolute URLs and any
    href without an .html / .htm suffix pass through untouched."""
    if not href or href.startswith(("#", "//")) or ":" in href.split("/", 1)[0]:
        return href
    m = _REL_HTML.match(href)
    if not m:
        return href
    stem, fragment, query = m.group(1), m.group(2) or "", m.group(3) or ""
    return f"{stem}.md{query}{fragment}"


def _h_a(c: _Converter, el: ET._Element) -> None:
    href = el.get("href") or ""
    inner = c.render_inline(el).strip()
    if not inner:
        inner = href
    if not href:
        c.write(inner)
        return
    c.write(f"[{inner}]({_rewrite_doc_link(href)})")


def _h_img(c: _Converter, el: ET._Element) -> None:
    src = el.get("src") or ""
    alt = el.get("alt") or ""
    title = el.get("title")
    if not src:
        return
    src = c.rewrite_image_src(src)
    if title:
        c.write(f'![{alt}]({src} "{title}")')
    else:
        c.write(f"![{alt}]({src})")


# ---------------------------------------------------------------------------
# Lists and tables
# ---------------------------------------------------------------------------


def _h_list(kind: str):
    def handler(c: _Converter, el: ET._Element) -> None:
        depth = sum(1 for ctx in c.list_stack)
        ctx = _ListCtx(kind=kind, depth=depth)
        c.list_stack.append(ctx)
        # collect list items into a buffer so spacing is tight
        items: list[str] = []
        for child in el:
            if isinstance(child.tag, str) and child.tag.lower() == "li":
                marker = "- " if kind == "ul" else f"{ctx.index}. "
                ctx.index += 1
                body = c.render_block_inner(child).strip("\n")
                if not body:
                    items.append(marker.rstrip())
                    continue
                indent = " " * len(marker)
                lines = body.split("\n")
                rendered_first = lines[0]
                rest = [(indent + ln) if ln else "" for ln in lines[1:]]
                items.append(marker + rendered_first + ("\n" + "\n".join(rest) if rest else ""))
        c.list_stack.pop()
        prefix = "  " * depth
        if prefix:
            items = [
                "\n".join((prefix + ln) if ln else "" for ln in item.split("\n"))
                for item in items
            ]
        block = "\n".join(items)
        if depth == 0:
            c.write_block(block)
        else:
            # nested — caller is collecting via render_block_inner; emit inline
            c.write("\n" + block + "\n")

    return handler


def _h_li(c: _Converter, el: ET._Element) -> None:
    # Handled inside the list handler — fall back to inline if encountered loose.
    c.render_children(el)


def _h_table(c: _Converter, el: ET._Element) -> None:
    rows: list[list[str]] = []
    has_header = False
    for tr in el.iter("tr"):
        cells: list[str] = []
        is_header_row = False
        for cell in tr:
            if not isinstance(cell.tag, str):
                continue
            t = cell.tag.lower()
            if t not in ("th", "td"):
                continue
            if t == "th":
                is_header_row = True
            inner = c.render_inline(cell).strip().replace("\n", " ").replace("|", "\\|")
            cells.append(inner or " ")
        if not cells:
            continue
        if is_header_row and not rows:
            has_header = True
        rows.append(cells)
    if not rows:
        return
    width = max(len(r) for r in rows)
    for r in rows:
        while len(r) < width:
            r.append(" ")
    if not has_header:
        rows.insert(0, [" "] * width)
    header = rows[0]
    sep = ["---"] * width
    body_rows = rows[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for r in body_rows:
        lines.append("| " + " | ".join(r) + " |")
    c.write_block("\n".join(lines))


# ---------------------------------------------------------------------------
# Generic fallbacks
# ---------------------------------------------------------------------------


def _h_unwrap(c: _Converter, el: ET._Element) -> None:
    c.render_children(el)


def _h_drop(c: _Converter, el: ET._Element) -> None:
    if isinstance(el.tag, str) and el.tag.lower().startswith("rd-"):
        c.dropped.append(el.tag.lower())
