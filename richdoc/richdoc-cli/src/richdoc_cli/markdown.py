"""HTML → GitHub-flavored markdown converter for richdoc documents.

Public surface:

    html_to_markdown(source) -> (markdown_text, dropped_tag_names)

The converter walks the parsed HTML tree once and dispatches each element
to a tag-specific handler. Plain HTML produces CommonMark / GFM; rd-*
custom elements are mapped to the closest markdown idiom (admonitions,
tables, fenced code blocks, footnotes, definition lists, …).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

import lxml.etree as ET
import lxml.html as LH

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def html_to_markdown(source: str) -> tuple[str, list[str]]:
    """Render the document body as markdown. Returns (text, dropped_tag_names)."""
    parser = LH.HTMLParser(recover=True)
    root = LH.document_fromstring(source, parser=parser)
    body = root.find(".//body")
    target = body if body is not None else root

    conv = _Converter()
    conv.render_children(target)
    return conv.finalise(), conv.dropped


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


_WHITESPACE = re.compile(r"\s+")
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
    _cite_counter: int = 0

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

    def render_inline(self, el: ET._Element) -> str:  # noqa: SLF001
        """Render `el` and its children as an inline string (no block separators)."""
        sub = _Converter()
        sub.in_pre = self.in_pre
        sub.list_stack = self.list_stack[:]
        sub._cite_counter = self._cite_counter
        sub.footnotes = self.footnotes  # share state
        sub.refs_collected = self.refs_collected
        sub.ref_order = self.ref_order
        sub.ref_entries = self.ref_entries
        sub.dropped = self.dropped
        # render only children, including the element's text
        if el.text:
            sub.write(_inline_text(el.text))
        for child in el:
            sub.render(child)
            if child.tail:
                sub.write(_inline_text(child.tail))
        self._cite_counter = sub._cite_counter
        return "".join(sub.chunks)

    def render_block_inner(self, el: ET._Element) -> str:  # noqa: SLF001
        """Render the children of `el` to markdown (block-level), returning the chunk."""
        sub = _Converter()
        sub.in_pre = self.in_pre
        sub.list_stack = self.list_stack[:]
        sub._cite_counter = self._cite_counter
        sub.footnotes = self.footnotes
        sub.refs_collected = self.refs_collected
        sub.ref_order = self.ref_order
        sub.ref_entries = self.ref_entries
        sub.dropped = self.dropped
        sub.render_children(el)
        self._cite_counter = sub._cite_counter
        body = _strip_outer_blanks(sub.finalise_body())
        # The first inline text node often starts with whitespace from HTML
        # indentation — strip it so block bodies don't render with a leading
        # space.
        if body and body[0] in " \t":
            body = body.lstrip(" \t")
        return body

    def render_children(self, el: ET._Element) -> None:  # noqa: SLF001
        if el.text:
            self.write(_inline_text(el.text))
        for child in el:
            self.render(child)
            if child.tail:
                self.write(_inline_text(child.tail))

    # ---- dispatch ---------------------------------------------------------

    def render(self, el: ET._Element) -> None:  # noqa: SLF001
        tag = el.tag
        if not isinstance(tag, str):
            return  # comments / PIs
        tag = tag.lower()
        handler = _HANDLERS.get(tag)
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
                lines.append(f"{n}. {_format_ref(self.refs_collected[key])}")
            for key, attrs in self.refs_collected.items():
                if key in seen:
                    continue
                n += 1
                lines.append(f"{n}. {_format_ref(attrs)}")
            body = body.rstrip() + "\n" + "\n".join(lines) + "\n"
        body = body.lstrip("\n")
        if not body.endswith("\n"):
            body += "\n"
        return body


def _inline_text(text: str) -> str:
    """Normalise whitespace in inline text nodes."""
    return _WHITESPACE.sub(" ", text)


def _dedent(text: str) -> str:
    """Mirror the JS k() helper used by `<rd-code>` / `<rd-diff>` / `<rd-shell>`.

    Strip leading newlines, trailing whitespace, then remove the common
    leading indent across non-blank lines.
    """
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
    return "\n".join(line[min_indent:] if len(line) >= min_indent else line for line in lines)


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


def _escape_md(text: str) -> str:
    """Escape characters that would otherwise be interpreted as markdown.

    Intentionally narrow: we only escape leading list-bullet / heading sigils
    inside inline contexts. Aggressive escaping butchers prose.
    """
    return text


# ---------------------------------------------------------------------------
# Plain-HTML handlers
# ---------------------------------------------------------------------------


def _h_h(level: int):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
        text = _strip_outer_blanks(c.render_inline(el)).strip()
        if not text:
            return
        c.write_block(f"{'#' * level} {text}")

    return handler


def _h_p(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    text = _strip_outer_blanks(c.render_inline(el)).strip()
    if not text:
        return
    c.write_block(text)


def _h_br(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.write("  \n")


def _h_hr(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.write_block("---")


def _h_strong(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_inline(el).strip()
    if inner:
        c.write(f"**{inner}**")


def _h_em(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_inline(el).strip()
    if inner:
        c.write(f"*{inner}*")


def _h_s(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_inline(el).strip()
    if inner:
        c.write(f"~~{inner}~~")


def _h_code_inline(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
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


def _h_pre(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
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


def _h_blockquote(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    inner = c.render_block_inner(el)
    if not inner.strip():
        return
    quoted = "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))
    c.write_block(quoted)


def _h_a(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    href = el.get("href") or ""
    inner = c.render_inline(el).strip()
    if not inner:
        inner = href
    if not href:
        c.write(inner)
        return
    c.write(f"[{inner}]({href})")


def _h_img(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    src = el.get("src") or ""
    alt = el.get("alt") or ""
    title = el.get("title")
    if not src:
        return
    if title:
        c.write(f'![{alt}]({src} "{title}")')
    else:
        c.write(f"![{alt}]({src})")


def _h_list(kind: str):
    def handler(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
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


def _h_li(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Handled inside the list handler — fall back to inline if encountered loose.
    c.render_children(el)


def _h_table(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
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


def _h_unwrap(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_drop(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    if isinstance(el.tag, str) and el.tag.lower().startswith("rd-"):
        c.dropped.append(el.tag.lower())


# ---------------------------------------------------------------------------
# rd-* handlers
# ---------------------------------------------------------------------------


_CALLOUT_KEYWORDS = {
    "info": "NOTE",
    "success": "TIP",
    "warn": "WARNING",
    "danger": "CAUTION",
    "note": "NOTE",
    "tldr": "IMPORTANT",
}


def _h_rd_page(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_rd_banner(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    message = el.get("message") or _strip_outer_blanks(c.render_inline(el)).strip() or type_
    kw = _CALLOUT_KEYWORDS.get(type_, "NOTE")
    c.write_block(f"> [!{kw}]\n> **{type_.upper()}** — {message}")


def _h_rd_hero(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    eyebrow = el.get("eyebrow") or ""
    lede = el.get("lede") or ""
    meta = el.get("meta") or ""
    extras_inner = c.render_block_inner(el).strip()
    if title:
        c.write_block(f"# {title}")
    meta_bits = [b for b in (eyebrow, lede, meta) if b]
    if meta_bits:
        c.write_block(f"*{' · '.join(meta_bits)}*")
    if extras_inner:
        c.write_block(extras_inner)


def _h_rd_section(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    if title:
        c.write_block(f"## {title}")
    inner = c.render_block_inner(el)
    if inner.strip():
        c.write_block(inner)


def _h_rd_callout(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    title = el.get("title") or ""
    kw = _CALLOUT_KEYWORDS.get(type_, "NOTE")
    inner = c.render_block_inner(el).strip()
    header = f"> [!{kw}]"
    if title:
        header += f" {title}"
    elif type_ == "tldr":
        header += " TL;DR"
    if inner:
        quoted = "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))
        c.write_block(f"{header}\n{quoted}")
    else:
        c.write_block(header)


def _h_rd_cols(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_rd_card(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    if title:
        c.write_block(f"### {title}")
    inner = c.render_block_inner(el)
    if inner.strip():
        c.write_block(inner)


def _h_rd_kv(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    layout = (el.get("layout") or "inline").lower()
    if title:
        c.write_block(f"**{title}**")
    rows = [r for r in el if isinstance(r.tag, str) and r.tag.lower() == "rd-row"]
    if layout == "stacked":
        parts: list[str] = []
        for r in rows:
            key = r.get("key") or ""
            value = _strip_outer_blanks(c.render_block_inner(r)).strip()
            parts.append(f"*{key}*\n: {value}" if value else f"*{key}*")
        c.write_block("\n\n".join(parts))
    else:
        lines = []
        for r in rows:
            key = r.get("key") or ""
            value = c.render_inline(r).strip()
            lines.append(f"- **{key}:** {value}" if value else f"- **{key}**")
        if lines:
            c.write_block("\n".join(lines))


def _h_rd_row(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Handled inside rd-kv. If encountered loose, render inline.
    c.render_children(el)


def _h_rd_badge(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    variant = el.get("variant") or ""
    inner = c.render_inline(el).strip()
    label = inner or variant or "badge"
    c.write(f"`[{label}]`")


def _h_rd_stat(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    value = el.get("value") or ""
    label = el.get("label") or ""
    trend = el.get("trend") or ""
    delta = el.get("delta") or ""
    extras = []
    if trend:
        glyph = {"up": "▲", "down": "▼", "flat": "→"}.get(trend, trend)
        extras.append(glyph)
    if delta:
        extras.append(delta)
    line = f"**{value}**"
    if label:
        line += f" — {label}"
    if extras:
        line += f" ({' '.join(extras)})"
    c.write_block(line)
    # Children (sparkline data) are noisy in markdown; drop them.
    for child in el:
        if isinstance(child.tag, str) and child.tag.lower().startswith("rd-"):
            c.dropped.append(child.tag.lower())


def _h_rd_progress(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    raw = el.get("value") or ""
    label = el.get("label") or ""
    pct = _progress_to_pct(raw)
    line = f"**{label}:** {pct}" if label else f"**Progress:** {pct}"
    c.write_block(line)


def _progress_to_pct(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "0%"
    if raw.endswith("%"):
        return raw
    if "/" in raw:
        try:
            num, denom = raw.split("/", 1)
            n = float(num.strip())
            d = float(denom.strip())
            if d > 0:
                return f"{round(n / d * 100)}% ({raw})"
        except ValueError:
            pass
    try:
        v = float(raw)
        return f"{round(v * 100)}%"
    except ValueError:
        return raw


def _h_rd_update(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    date = el.get("date") or ""
    kind = el.get("kind") or ""
    author = el.get("author") or ""
    title = el.get("title") or ""
    head = f"### {date}" + (f" — {title}" if title else "")
    c.write_block(head)
    meta_bits = [b for b in (kind, author) if b]
    if meta_bits:
        c.write_block(f"*{' · '.join(meta_bits)}*")
    inner = c.render_block_inner(el)
    if inner.strip():
        c.write_block(inner)


def _h_rd_quote(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    author = el.get("author") or ""
    cite = el.get("cite") or ""
    inner = c.render_block_inner(el).strip()
    quoted_lines = [f"> {line}" if line else ">" for line in inner.split("\n")]
    if author or cite:
        attrib = f"— {author}" if author else ""
        if cite:
            attrib = (attrib + f", *{cite}*") if attrib else f"— *{cite}*"
        quoted_lines.append(f"> {attrib}")
    c.write_block("\n".join(quoted_lines))


def _h_rd_footnote(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    body = _strip_outer_blanks(c.render_block_inner(el)).strip()
    c.footnotes.append(body)
    n = len(c.footnotes)
    c.write(f"[^{n}]")


def _h_rd_swatch(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    name = el.get("name") or ""
    value = el.get("value") or ""
    kind = el.get("kind") or ""
    note = el.get("note") or ""
    bits = [f"**{name}**", f"`{value}`"]
    if kind:
        bits.append(f"_{kind}_")
    if note:
        bits.append(note)
    c.write_block(" — ".join(bits))


def _h_rd_compare(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    headers = [h.strip() for h in (el.get("headers") or "").split(",") if h.strip()]
    rows: list[list[str]] = []
    for rc in el:
        if not (isinstance(rc.tag, str) and rc.tag.lower() == "rd-row-cells"):
            continue
        label = rc.get("label") or ""
        cells = []
        for cell in rc:
            if not (isinstance(cell.tag, str) and cell.tag.lower() == "rd-cell"):
                continue
            tone = (cell.get("tone") or "").lower()
            glyph = {"positive": "✓ ", "negative": "✗ ", "neutral": "· "}.get(tone, "")
            text = c.render_inline(cell).strip().replace("|", "\\|").replace("\n", " ")
            cells.append(glyph + text)
        rows.append([label, *cells])
    if not headers and not rows:
        return
    width = max(len(headers), max((len(r) for r in rows), default=0))
    headers_full = list(headers)
    while len(headers_full) < width:
        headers_full.append(" ")
    for r in rows:
        while len(r) < width:
            r.append(" ")
    lines = [
        "| " + " | ".join(headers_full) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    c.write_block("\n".join(lines))


def _h_rd_rubric(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    options = [o.strip() for o in (el.get("options") or "").split(",") if o.strip()]
    title = el.get("title") or ""
    if title:
        c.write_block(f"### {title}")
    rows: list[list[str]] = []
    totals = [0.0] * len(options)
    for crit in el:
        if not (isinstance(crit.tag, str) and crit.tag.lower() == "rd-criterion"):
            continue
        label = crit.get("label") or ""
        try:
            weight = float(crit.get("weight") or "1")
        except ValueError:
            weight = 1.0
        scores = [s for s in crit if isinstance(s.tag, str) and s.tag.lower() == "rd-score"]
        cells: list[str] = []
        for i, opt in enumerate(options):
            if i < len(scores):
                v = scores[i].get("value") or "0"
                note = scores[i].get("note") or ""
                try:
                    totals[i] += float(v) * weight
                except ValueError:
                    pass
                cells.append(f"{v}" + (f" — {note}" if note else ""))
            else:
                cells.append(" ")
        rows.append([f"{label} (×{weight:g})", *cells])
    headers = [" ", *options]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    totals_row = ["**Total**", *[f"**{t:g}**" for t in totals]]
    lines.append("| " + " | ".join(totals_row) + " |")
    c.write_block("\n".join(lines))


def _h_rd_code(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    lang = el.get("lang") or ""
    title = el.get("title") or ""
    body = _dedent(el.text or "")
    _emit_fenced(c, body, lang, title)


def _h_rd_diff(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    body = _dedent(el.text or "")
    _emit_fenced(c, body, "diff", title)


def _h_rd_shell(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    lines: list[str] = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        text = _dedent(child.text or "")
        if t == "rd-prompt":
            for line in text.split("\n"):
                lines.append(f"$ {line}" if line else "$")
        elif t == "rd-output":
            lines.append(text)
    _emit_fenced(c, "\n".join(lines), "bash", title)


def _h_rd_math(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    display = (el.get("display") or "block").lower()
    text = _dedent(el.text or "")
    if display == "inline":
        c.write(f"${text}$")
    else:
        c.write_block(f"$$\n{text}\n$$")


def _h_rd_figure(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    caption = el.get("caption") or ""
    inner = c.render_block_inner(el).strip()
    if inner:
        c.write_block(inner)
    if caption:
        c.write_block(f"*{caption}*")


def _h_rd_chart(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    caption = el.get("caption") or ""
    data_attr = el.get("data") or (el.text or "")
    if title:
        c.write_block(f"**{title}**")
    rendered = _chart_to_table(data_attr)
    if rendered:
        c.write_block(rendered)
    elif data_attr.strip():
        c.write_block(f"```\n{data_attr.strip()}\n```")
    if caption:
        c.write_block(f"*{caption}*")


def _chart_to_table(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    import json as _json

    # JSON array?
    if raw.startswith("[") or raw.startswith("{"):
        try:
            data = _json.loads(raw)
        except ValueError:
            data = None
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                keys = list(data[0].keys())
            else:
                keys = ["value"]
                data = [{"value": v} for v in data]
            lines = [
                "| " + " | ".join(keys) + " |",
                "| " + " | ".join(["---"] * len(keys)) + " |",
            ]
            for row in data:
                lines.append("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")
            return "\n".join(lines)
    # CSV?
    if "\n" in raw and "," in raw:
        rows = [r.split(",") for r in raw.splitlines() if r.strip()]
        if rows:
            head = rows[0]
            body = rows[1:]
            lines = [
                "| " + " | ".join(c.strip() for c in head) + " |",
                "| " + " | ".join(["---"] * len(head)) + " |",
            ]
            for r in body:
                lines.append("| " + " | ".join((c.strip() if i < len(r) else " ") for i, c in enumerate(r)) + " |")
            return "\n".join(lines)
    # Comma list of numbers?
    if re.fullmatch(r"[\d\s,.\-eE]+", raw):
        values = [v.strip() for v in raw.split(",") if v.strip()]
        lines = [
            "| # | value |",
            "| --- | --- |",
        ]
        for i, v in enumerate(values, start=1):
            lines.append(f"| {i} | {v} |")
        return "\n".join(lines)
    return ""


def _h_rd_gallery(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    if title:
        c.write_block(f"### {title}")
    items = []
    for shot in el:
        if not (isinstance(shot.tag, str) and shot.tag.lower() == "rd-shot"):
            continue
        src = shot.get("src") or ""
        alt = shot.get("alt") or ""
        caption = shot.get("caption") or ""
        item = f"- ![{alt}]({src})"
        if caption:
            item += f" — {caption}"
        items.append(item)
    if items:
        c.write_block("\n".join(items))


def _h_rd_embed(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    src = el.get("src") or ""
    title = el.get("title") or "Embed"
    caption = el.get("caption") or ""
    if src:
        c.write_block(f"[▶ {title}]({src})")
    if caption:
        c.write_block(f"*{caption}*")


def _h_rd_tabs(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    for tab in el:
        if not (isinstance(tab.tag, str) and tab.tag.lower() == "rd-tab"):
            continue
        label = tab.get("label") or "Tab"
        c.write_block(f"### {label}")
        inner = c.render_block_inner(tab)
        if inner.strip():
            c.write_block(inner)


def _h_rd_timeline(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    lines = []
    for ev in el:
        if not (isinstance(ev.tag, str) and ev.tag.lower() == "rd-event"):
            continue
        date = ev.get("date") or ""
        title = ev.get("title") or ""
        body = c.render_inline(ev).strip()
        head = f"- **{date}**"
        if title:
            head += f" — {title}"
        if body:
            head += f" — {body}"
        lines.append(head)
    if lines:
        c.write_block("\n".join(lines))


def _h_rd_steps(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    items = []
    n = 1
    for step in el:
        if not (isinstance(step.tag, str) and step.tag.lower() == "rd-step"):
            continue
        title = step.get("title") or ""
        done = step.get("done") is not None
        title_str = f"~~{title}~~" if done else title
        body = c.render_block_inner(step).strip("\n")
        marker = f"{n}. "
        n += 1
        first = f"**{title_str}**" if title_str else ""
        if body:
            indent = " " * len(marker)
            body_lines = body.split("\n")
            if first:
                items.append(marker + first + "\n" + "\n".join((indent + ln) if ln else "" for ln in body_lines))
            else:
                items.append(marker + body_lines[0] + ("\n" + "\n".join((indent + ln) if ln else "" for ln in body_lines[1:]) if len(body_lines) > 1 else ""))
        else:
            items.append(marker + first)
    if items:
        c.write_block("\n".join(items))


def _h_rd_detail(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    summary = el.get("summary") or "Details"
    open_attr = " open" if el.get("open") is not None else ""
    inner = c.render_block_inner(el).strip()
    c.write_block(f"<details{open_attr}>\n<summary>{summary}</summary>\n\n{inner}\n\n</details>")


def _h_rd_tree(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    if title:
        c.write_block(f"**{title}**")
    lines: list[str] = []

    def walk(node: ET._Element, depth: int) -> None:  # noqa: SLF001
        if not (isinstance(node.tag, str) and node.tag.lower() == "rd-node"):
            return
        label = node.get("label") or ""
        lines.append("  " * depth + f"- {label}")
        for child in node:
            walk(child, depth + 1)

    for child in el:
        walk(child, 0)
    if lines:
        c.write_block("\n".join(lines))


def _h_rd_checklist(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    lines = []
    for task in el:
        if not (isinstance(task.tag, str) and task.tag.lower() == "rd-task"):
            continue
        done = task.get("done") is not None
        assignee = task.get("assignee") or ""
        due = task.get("due") or ""
        body = c.render_inline(task).strip()
        meta_bits = []
        if assignee:
            meta_bits.append(f"@{assignee}")
        if due:
            meta_bits.append(f"due {due}")
        meta = f" ({', '.join(meta_bits)})" if meta_bits else ""
        box = "[x]" if done else "[ ]"
        lines.append(f"- {box} {body}{meta}")
    if lines:
        c.write_block("\n".join(lines))


def _h_rd_mermaid(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    text = _dedent(el.text or "")
    _emit_fenced(c, text, "mermaid")


def _h_rd_plantuml(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    text = _dedent(el.text or "")
    _emit_fenced(c, text, "plantuml")


def _h_rd_toc(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.dropped.append("rd-toc")


def _h_rd_icon(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    label = el.get("label") or ""
    if label:
        c.write(label)
    else:
        c.dropped.append("rd-icon")


def _h_rd_tooltip(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    term = el.get("term") or ""
    body = c.render_inline(el).strip()
    if term and body:
        c.write(f"{term} ({body})")
    elif term:
        c.write(term)
    else:
        c.write(body)


def _h_rd_decision(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    status = el.get("status") or "proposed"
    id_ = el.get("id") or ""
    date = el.get("date") or ""
    deciders = el.get("deciders") or ""
    title = el.get("title") or ""
    head_bits: list[str] = []
    if id_:
        head_bits.append(id_)
    if title:
        head_bits.append(title)
    head = "### " + (": ".join(head_bits) if head_bits else "Decision")
    c.write_block(head)
    meta_bits = [f"`[{status.upper()}]`"]
    if date:
        meta_bits.append(date)
    if deciders:
        meta_bits.append(deciders)
    c.write_block(f"*{' · '.join(meta_bits)}*")
    inner = c.render_block_inner(el)
    if inner.strip():
        c.write_block(inner)


def _h_rd_pros_cons(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    pros_title = el.get("pros-title") or "Pros"
    cons_title = el.get("cons-title") or "Cons"
    pros, cons = [], []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        text = c.render_inline(child).strip()
        if t == "rd-pro":
            pros.append(f"- {text}")
        elif t == "rd-con":
            cons.append(f"- {text}")
    if pros:
        c.write_block(f"#### {pros_title}\n" + "\n".join(pros))
    if cons:
        c.write_block(f"#### {cons_title}\n" + "\n".join(cons))


def _h_rd_roadmap(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or ""
    if title:
        c.write_block(f"### {title}")
    for lane in el:
        if not (isinstance(lane.tag, str) and lane.tag.lower() == "rd-lane"):
            continue
        name = lane.get("name") or ""
        if name:
            c.write_block(f"#### {name}")
        rows = []
        for item in lane:
            if not (isinstance(item.tag, str) and item.tag.lower() == "rd-item"):
                continue
            start = item.get("start") or ""
            end = item.get("end") or ""
            label = item.get("label") or ""
            progress = item.get("progress") or ""
            pct = _progress_to_pct(progress) if progress else ""
            rows.append([label, start, end, pct])
        if rows:
            lines = [
                "| Item | Start | End | Progress |",
                "| --- | --- | --- | --- |",
            ]
            for r in rows:
                lines.append("| " + " | ".join(r) + " |")
            c.write_block("\n".join(lines))


def _h_rd_api(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    method = el.get("method") or ""
    path = el.get("path") or ""
    auth = el.get("auth") or ""
    title = el.get("title") or ""
    head = f"### `{method}` `{path}`"
    if title:
        head += f" — {title}"
    c.write_block(head)
    if auth:
        c.write_block(f"*auth:* `{auth}`")
    params = []
    responses = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        if t == "rd-param":
            params.append(child)
        elif t == "rd-response":
            responses.append(child)
    if params:
        lines = [
            "| Param | In | Required | Type | Default | Description |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for p in params:
            name = p.get("name") or ""
            in_ = p.get("in") or "query"
            req = "✓" if p.get("required") is not None else ""
            type_ = p.get("type") or ""
            default = p.get("default") or ""
            desc = c.render_inline(p).strip().replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{name}` | {in_} | {req} | {type_} | {default} | {desc} |")
        c.write_block("\n".join(lines))
    if responses:
        lines = [
            "| Status | Type | Description |",
            "| --- | --- | --- |",
        ]
        for r in responses:
            status = r.get("status") or ""
            type_ = r.get("type") or ""
            desc = c.render_inline(r).strip().replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{status}` | {type_} | {desc} |")
        c.write_block("\n".join(lines))


def _h_rd_references(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = el.get("title") or "References"
    c.refs_section_title = title
    # Children rd-ref are collected globally; the references section is
    # appended in finalise(). Mark presence by ensuring at least one key.


def _h_rd_ref(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    key = el.get("key") or ""
    if not key:
        return
    attrs = {
        "author": el.get("author") or "",
        "title": el.get("title") or "",
        "url": el.get("url") or "",
        "date": el.get("date") or "",
        "publisher": el.get("publisher") or "",
        "note": c.render_inline(el).strip(),
    }
    c.refs_collected[key] = attrs


def _format_ref(attrs: dict[str, str]) -> str:
    bits: list[str] = []
    author = attrs.get("author")
    title = attrs.get("title")
    url = attrs.get("url")
    date = attrs.get("date")
    publisher = attrs.get("publisher")
    note = attrs.get("note")
    if author:
        bits.append(author)
    if title:
        if url:
            bits.append(f'"[{title}]({url})"')
        else:
            bits.append(f'"{title}"')
    elif url:
        bits.append(f"<{url}>")
    if publisher:
        bits.append(publisher)
    if date:
        bits.append(date)
    line = ". ".join(bits) + ("." if bits else "")
    if note:
        line += f" {note}"
    return line


def _h_rd_cite(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    key = el.get("key") or ""
    if not key:
        return
    if key not in c.ref_order:
        c.ref_order.append(key)
    n = c.ref_order.index(key) + 1
    c.write(f"[{n}]")


# ---------------------------------------------------------------------------
# Handler table
# ---------------------------------------------------------------------------


_HANDLERS: dict[str, Callable[["_Converter", "ET._Element"], None]] = {
    # plain HTML
    "h1": _h_h(1),
    "h2": _h_h(2),
    "h3": _h_h(3),
    "h4": _h_h(4),
    "h5": _h_h(5),
    "h6": _h_h(6),
    "p": _h_p,
    "br": _h_br,
    "hr": _h_hr,
    "strong": _h_strong,
    "b": _h_strong,
    "em": _h_em,
    "i": _h_em,
    "s": _h_s,
    "del": _h_s,
    "strike": _h_s,
    "code": _h_code_inline,
    "pre": _h_pre,
    "blockquote": _h_blockquote,
    "a": _h_a,
    "img": _h_img,
    "ul": _h_list("ul"),
    "ol": _h_list("ol"),
    "li": _h_li,
    "table": _h_table,
    "thead": _h_unwrap,
    "tbody": _h_unwrap,
    "tfoot": _h_unwrap,
    "tr": _h_unwrap,
    "th": _h_unwrap,
    "td": _h_unwrap,
    "div": _h_unwrap,
    "span": _h_unwrap,
    "section": _h_unwrap,
    "article": _h_unwrap,
    "header": _h_unwrap,
    "footer": _h_unwrap,
    "main": _h_unwrap,
    "nav": _h_unwrap,
    "aside": _h_unwrap,
    "figure": _h_unwrap,
    "figcaption": _h_em,
    "time": _h_unwrap,
    "small": _h_unwrap,
    "u": _h_unwrap,
    "mark": _h_unwrap,
    "sup": _h_unwrap,
    "sub": _h_unwrap,
    # head / metadata
    "script": _h_drop,
    "style": _h_drop,
    "head": _h_drop,
    "meta": _h_drop,
    "title": _h_drop,
    "link": _h_drop,
    # rd-*
    "rd-page": _h_rd_page,
    "rd-banner": _h_rd_banner,
    "rd-hero": _h_rd_hero,
    "rd-section": _h_rd_section,
    "rd-callout": _h_rd_callout,
    "rd-cols": _h_rd_cols,
    "rd-card": _h_rd_card,
    "rd-kv": _h_rd_kv,
    "rd-row": _h_rd_row,
    "rd-badge": _h_rd_badge,
    "rd-stat": _h_rd_stat,
    "rd-progress": _h_rd_progress,
    "rd-update": _h_rd_update,
    "rd-quote": _h_rd_quote,
    "rd-footnote": _h_rd_footnote,
    "rd-footnotes": _h_drop,  # auto-generated by JS; we manage our own.
    "rd-swatch": _h_rd_swatch,
    "rd-compare": _h_rd_compare,
    "rd-rubric": _h_rd_rubric,
    "rd-code": _h_rd_code,
    "rd-diff": _h_rd_diff,
    "rd-shell": _h_rd_shell,
    "rd-math": _h_rd_math,
    "rd-figure": _h_rd_figure,
    "rd-chart": _h_rd_chart,
    "rd-gallery": _h_rd_gallery,
    "rd-embed": _h_rd_embed,
    "rd-tabs": _h_rd_tabs,
    "rd-timeline": _h_rd_timeline,
    "rd-steps": _h_rd_steps,
    "rd-detail": _h_rd_detail,
    "rd-tree": _h_rd_tree,
    "rd-checklist": _h_rd_checklist,
    "rd-mermaid": _h_rd_mermaid,
    "rd-plantuml": _h_rd_plantuml,
    "rd-toc": _h_rd_toc,
    "rd-icon": _h_rd_icon,
    "rd-tooltip": _h_rd_tooltip,
    "rd-decision": _h_rd_decision,
    "rd-pros-cons": _h_rd_pros_cons,
    "rd-roadmap": _h_rd_roadmap,
    "rd-api": _h_rd_api,
    "rd-references": _h_rd_references,
    "rd-ref": _h_rd_ref,
    "rd-cite": _h_rd_cite,
}
