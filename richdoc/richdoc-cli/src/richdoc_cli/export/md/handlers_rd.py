"""rd-* component handlers for the markdown converter."""

from __future__ import annotations

import re

import lxml.etree as ET

from ..common.chart_data import parse_chart
from ..common.walker import iter_text
from .converter import (
    _Converter,
    _dedent,
    _element_source,
    _emit_fenced,
    _strip_outer_blanks,
)

_CALLOUT_KEYWORDS = {
    "info": "NOTE",
    "success": "TIP",
    "warn": "WARNING",
    "danger": "CAUTION",
    "note": "NOTE",
    "tldr": "IMPORTANT",
}


# ---------------------------------------------------------------------------
# Page / hero / sections / callouts
# ---------------------------------------------------------------------------


def _h_rd_page(c: _Converter, el: ET._Element) -> None:
    c.render_children(el)


def _h_rd_banner(c: _Converter, el: ET._Element) -> None:
    type_ = (el.get("type") or "info").lower()
    message = el.get("message") or _strip_outer_blanks(c.render_inline(el)).strip() or type_
    kw = _CALLOUT_KEYWORDS.get(type_, "NOTE")
    c.write_block(f"> [!{kw}]\n> **{type_.upper()}** — {message}")


def _h_rd_hero(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_section(c: _Converter, el: ET._Element) -> None:
    title = el.get("title") or ""
    if title:
        c.write_block(f"## {title}")
    inner = c.render_block_inner(el)
    if inner.strip():
        c.write_block(inner)


def _h_rd_callout(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_cols(c: _Converter, el: ET._Element) -> None:
    c.render_children(el)


def _h_rd_card(c: _Converter, el: ET._Element) -> None:
    title = el.get("title") or ""
    if title:
        c.write_block(f"### {title}")
    inner = c.render_block_inner(el)
    if inner.strip():
        c.write_block(inner)


# ---------------------------------------------------------------------------
# Information blocks
# ---------------------------------------------------------------------------


def _h_rd_kv(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_row(c: _Converter, el: ET._Element) -> None:
    # Handled inside rd-kv. If encountered loose, render inline.
    c.render_children(el)


def _h_rd_badge(c: _Converter, el: ET._Element) -> None:
    variant = el.get("variant") or ""
    inner = c.render_inline(el).strip()
    label = inner or variant or "badge"
    c.write(f"`[{label}]`")


def _h_rd_stat(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_progress(c: _Converter, el: ET._Element) -> None:
    from ..common.progress import parse_progress

    p = parse_progress(el.get("value"))
    label = el.get("label") or ""
    line = f"**{label}:** {p.display}" if label else f"**Progress:** {p.display}"
    c.write_block(line)


def _h_rd_update(c: _Converter, el: ET._Element) -> None:
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


# ---------------------------------------------------------------------------
# Comparison and code
# ---------------------------------------------------------------------------


def _h_rd_compare(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_rubric(c: _Converter, el: ET._Element) -> None:
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
        for i, _opt in enumerate(options):
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


def _h_rd_code(c: _Converter, el: ET._Element) -> None:
    lang = el.get("lang") or ""
    title = el.get("title") or ""
    body = _dedent(_element_source(el))
    _emit_fenced(c, body, lang, title)


def _h_rd_diff(c: _Converter, el: ET._Element) -> None:
    title = el.get("title") or ""
    body = _dedent(_element_source(el))
    _emit_fenced(c, body, "diff", title)


def _h_rd_shell(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_math(c: _Converter, el: ET._Element) -> None:
    display = (el.get("display") or "block").lower()
    text = _dedent(_element_source(el))
    if display == "inline":
        c.write(f"${text}$")
    else:
        c.write_block(f"$$\n{text}\n$$")


def _h_rd_figure(c: _Converter, el: ET._Element) -> None:
    caption = el.get("caption") or ""
    inner = c.render_block_inner(el).strip()
    if inner:
        c.write_block(inner)
    if caption:
        c.write_block(f"*{caption}*")


def _h_rd_chart(c: _Converter, el: ET._Element) -> None:
    title = el.get("title") or ""
    caption = el.get("caption") or ""
    data_attr = el.get("data") or _element_source(el)
    if title:
        c.write_block(f"**{title}**")
    table = parse_chart(data_attr)
    if table is not None:
        c.write_block(_chart_table_to_markdown(table))
    elif data_attr.strip():
        c.write_block(f"```\n{data_attr.strip()}\n```")
    if caption:
        c.write_block(f"*{caption}*")


def _chart_table_to_markdown(table) -> str:
    width = len(table.headers)
    lines = [
        "| " + " | ".join(table.headers) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in table.rows:
        # Pad short CSV rows with a single space, matching the legacy markdown
        # rendering. The parser doesn't pad, so renderers stay independent.
        padded = row + [" "] * (width - len(row)) if len(row) < width else row
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sequenced / interactive
# ---------------------------------------------------------------------------


def _h_rd_tabs(c: _Converter, el: ET._Element) -> None:
    for tab in el:
        if not (isinstance(tab.tag, str) and tab.tag.lower() == "rd-tab"):
            continue
        label = tab.get("label") or "Tab"
        c.write_block(f"### {label}")
        inner = c.render_block_inner(tab)
        if inner.strip():
            c.write_block(inner)


def _h_rd_timeline(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_steps(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_detail(c: _Converter, el: ET._Element) -> None:
    summary = el.get("summary") or "Details"
    open_attr = " open" if el.get("open") is not None else ""
    inner = c.render_block_inner(el).strip()
    c.write_block(f"<details{open_attr}>\n<summary>{summary}</summary>\n\n{inner}\n\n</details>")


def _h_rd_checklist(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_diagram(c: _Converter, el: ET._Element) -> None:
    text = _dedent(_element_source(el))
    lang = (el.get("lang") or "").strip().lower() or "text"
    # GFM only natively renders ```mermaid; for every other lang the
    # source still travels with a meaningful info string so downstream
    # processors (or the human reader) can recognise the language.
    _emit_fenced(c, text, lang)


# ---------------------------------------------------------------------------
# TOC / chapters
# ---------------------------------------------------------------------------


def _h_rd_toc(c: _Converter, el: ET._Element) -> None:
    chapters = [
        child
        for child in el
        if isinstance(child.tag, str) and child.tag.lower() == "rd-chapter"
    ]
    if not chapters:
        # Single-file mode: in-page TOC is dropped (the markdown reader can
        # rely on heading order).
        c.dropped.append("rd-toc")
        return
    # Book mode: emit a markdown list reflecting the chapter tree. Relative
    # .html / .htm links are rewritten to .md so the sibling chapters that
    # `richdoc export md` emits are reachable from this index.
    title = el.get("title") or "Contents"
    lines: list[str] = [f"**{title}**", ""]
    _emit_chapter_list(lines, chapters, depth=0)
    c.write_block("\n".join(lines).rstrip())


def _emit_chapter_list(
    lines: list[str], chapters: list[ET._Element], depth: int
) -> None:
    indent = "  " * depth
    for ch in chapters:
        title = _chapter_title_md(ch)
        href = ch.get("href")
        if href and not re.match(r"^(?:https?:|mailto:|tel:|#)", href):
            href = re.sub(r"\.html?(#|$)", r".md\1", href)
        if href and title:
            lines.append(f"{indent}- [{title}]({href})")
        elif href:
            lines.append(f"{indent}- [{href}]({href})")
        else:
            lines.append(f"{indent}- **{title}**")
        nested = [
            c
            for c in ch
            if isinstance(c.tag, str) and c.tag.lower() == "rd-chapter"
        ]
        if nested:
            _emit_chapter_list(lines, nested, depth + 1)


def _chapter_title_md(node: ET._Element) -> str:
    """Mirrors the runtime/lint chapter-title extraction: text content of the
    element with nested <rd-chapter> sub-trees removed."""
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if isinstance(child.tag, str) and child.tag.lower() == "rd-chapter":
            if child.tail:
                parts.append(child.tail)
            continue
        parts.extend(iter_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split()).strip()


# ---------------------------------------------------------------------------
# Inline glyphs / tooltips
# ---------------------------------------------------------------------------


def _h_rd_icon(c: _Converter, el: ET._Element) -> None:
    label = el.get("label") or ""
    if label:
        c.write(label)
    else:
        c.dropped.append("rd-icon")


# ---------------------------------------------------------------------------
# Decision and planning
# ---------------------------------------------------------------------------


def _h_rd_decision(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_pros_cons(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_api(c: _Converter, el: ET._Element) -> None:
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


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------


def _h_rd_references(c: _Converter, el: ET._Element) -> None:
    title = el.get("title") or "References"
    c.refs_section_title = title
    # Children rd-ref are collected globally; the references section is
    # appended in finalise(). Mark presence by ensuring at least one key.


def _h_rd_ref(c: _Converter, el: ET._Element) -> None:
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


def _h_rd_cite(c: _Converter, el: ET._Element) -> None:
    key = el.get("key") or ""
    if not key:
        return
    if key not in c.ref_order:
        c.ref_order.append(key)
    n = c.ref_order.index(key) + 1
    c.write(f"[{n}]")
