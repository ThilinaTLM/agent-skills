"""rd-* component handlers for the Confluence exporter.

Each handler emits the HTML that survives Confluence's import whitelist
(headings, paragraphs, lists, tables, blockquotes, `<code>`, `<img>`)
and queues PNG renders for the constructs Confluence collapses
(code blocks, math, diagrams).
"""

from __future__ import annotations

import re

import lxml.etree as ET

from ..common.chart_data import parse_chart
from .converter import (
    _Converter,
    _dedent,
    _element_source,
    _strip_outer_blanks,
    attr,
    escape_attr,
    escape_text,
)
from .handlers_plain import _emit_code


_CALLOUT_DEFAULT_TITLE = {
    "info": "Info",
    "success": "Success",
    "warn": "Warning",
    "danger": "Danger",
    "note": "Note",
    "tldr": "TL;DR",
}


# ---------------------------------------------------------------------------
# Page / hero / sections / callouts
# ---------------------------------------------------------------------------


def _h_rd_page(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_rd_hero(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    eyebrow = (el.get("eyebrow") or "").strip()
    lede = (el.get("lede") or "").strip()
    meta = (el.get("meta") or "").strip()
    if title and not c.title:
        c.title = title
    if eyebrow:
        c.write_block(f"<p><strong>{escape_text(eyebrow.upper())}</strong></p>")
    if title:
        c.write_block(f"<h1>{escape_text(title)}</h1>")
    if lede:
        c.write_block(f"<p><em>{escape_text(lede)}</em></p>")
    if meta:
        c.write_block(f"<p><small>{escape_text(meta)}</small></p>")
    inner = c.render_block_inner_wrapped(el).strip()
    if inner:
        c.write_block(inner)


def _h_rd_section(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    if title:
        c.write_block(f"<h2>{escape_text(title)}</h2>")
    inner = c.render_block_inner_wrapped(el).strip()
    if inner:
        c.write_block(inner)


def _h_rd_banner(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    msg = (el.get("message") or "").strip() or c.render_inline(el).strip()
    label = type_.upper()
    if msg:
        c.write_block(
            f"<blockquote><p><strong>[{escape_text(label)}]</strong> "
            f"{msg}</p></blockquote>"
        )


def _h_rd_callout(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    title = (el.get("title") or _CALLOUT_DEFAULT_TITLE.get(type_, type_.title())).strip()
    inner = c.render_block_inner_wrapped(el).strip()
    head = (
        f"<p><strong>{escape_text(title)}</strong> "
        f"<small>[{escape_text(type_)}]</small></p>"
        if title
        else ""
    )
    if not inner and not head:
        return
    body = "\n".join(part for part in (head, inner) if part)
    c.write_block(f"<blockquote>{body}</blockquote>")


def _h_rd_cols(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Linearise — Confluence doesn't preserve multi-column layouts.
    c.render_children(el)


def _h_rd_card(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    accent = (el.get("accent") or "").strip()
    if accent:
        c.write_block(
            f"<p><small><strong>{escape_text(accent.upper())}</strong></small></p>"
        )
    if title:
        c.write_block(f"<h3>{escape_text(title)}</h3>")
    inner = c.render_block_inner_wrapped(el).strip()
    if inner:
        c.write_block(inner)


# ---------------------------------------------------------------------------
# Information blocks
# ---------------------------------------------------------------------------


def _h_rd_kv(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    if title:
        c.write_block(f"<h3>{escape_text(title)}</h3>")
    rows = [r for r in el if isinstance(r.tag, str) and r.tag.lower() == "rd-row"]
    if not rows:
        return
    parts = ["<table>", "  <tbody>"]
    for r in rows:
        key = (r.get("key") or "").strip()
        value = c.render_inline(r).strip()
        parts.append(
            f"    <tr><th>{escape_text(key)}</th><td>{value}</td></tr>"
        )
    parts.append("  </tbody>")
    parts.append("</table>")
    c.write_block("\n".join(parts))


def _h_rd_row(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Only meaningful inside <rd-kv>; if encountered loose, render inline.
    c.render_children(el)


def _h_rd_badge(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    variant = (el.get("variant") or "").strip()
    inner = c.render_inline(el).strip()
    label = inner or variant or "badge"
    c.write(f"<strong>[{label}]</strong>")


def _h_rd_stat(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    value = (el.get("value") or "").strip()
    label = (el.get("label") or "").strip()
    delta = (el.get("delta") or "").strip()
    trend = (el.get("trend") or "").strip()
    glyph = {"up": "▲", "down": "▼", "flat": "→"}.get(trend, "")
    bits = []
    if value:
        bits.append(f"<strong>{escape_text(value)}</strong>")
    if label:
        bits.append(escape_text(label))
    if delta:
        if glyph:
            bits.append(f"({glyph} {escape_text(delta)})")
        else:
            bits.append(f"({escape_text(delta)})")
    c.write_block("<p>" + " — ".join(bits) + "</p>")
    # Drop sparkline children — too noisy as a table in Confluence.
    for child in el:
        if isinstance(child.tag, str) and child.tag.lower().startswith("rd-"):
            c.dropped.append(child.tag.lower())


def _h_rd_progress(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    from ..common.progress import parse_progress  # noqa: PLC0415

    p = parse_progress(el.get("value"))
    label = (el.get("label") or "").strip()
    head = (
        f"<strong>{escape_text(label)}:</strong> {escape_text(p.display)}"
        if label
        else f"<strong>Progress:</strong> {escape_text(p.display)}"
    )
    c.write_block(f"<p>{head}</p>")


def _h_rd_update(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    date = (el.get("date") or "").strip()
    kind = (el.get("kind") or "").strip()
    author = (el.get("author") or "").strip()
    title = (el.get("title") or "").strip()
    head = " — ".join(bit for bit in (date, title) if bit)
    if head:
        c.write_block(f"<h4>{escape_text(head)}</h4>")
    meta = " · ".join(bit for bit in (kind, author) if bit)
    if meta:
        c.write_block(f"<p><em>{escape_text(meta)}</em></p>")
    inner = c.render_block_inner_wrapped(el).strip()
    if inner:
        c.write_block(inner)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _h_rd_compare(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    headers = [h.strip() for h in (el.get("headers") or "").split(",") if h.strip()]
    body_rows: list[tuple[str, list[tuple[str, str]]]] = []
    for rc in el:
        if not (isinstance(rc.tag, str) and rc.tag.lower() == "rd-row-cells"):
            continue
        label = rc.get("label") or ""
        cells = []
        for cell in rc:
            if not (isinstance(cell.tag, str) and cell.tag.lower() == "rd-cell"):
                continue
            tone = (cell.get("tone") or "").lower()
            text = c.render_inline(cell).strip()
            cells.append((tone, text))
        body_rows.append((label, cells))
    if not headers and not body_rows:
        return
    parts = ["<table>"]
    if headers:
        parts.append("  <thead>")
        head = "<th></th>" + "".join(f"<th>{escape_text(h)}</th>" for h in headers)
        parts.append(f"    <tr>{head}</tr>")
        parts.append("  </thead>")
    parts.append("  <tbody>")
    for label, cells in body_rows:
        td = []
        for tone, text in cells:
            glyph = {"positive": "✓ ", "negative": "✗ ", "neutral": "· "}.get(tone, "")
            td.append(f"<td>{glyph}{text}</td>")
        parts.append(
            f"    <tr><th>{escape_text(label)}</th>" + "".join(td) + "</tr>"
        )
    parts.append("  </tbody>")
    parts.append("</table>")
    c.write_block("\n".join(parts))


def _h_rd_rubric(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    options = [o.strip() for o in (el.get("options") or "").split(",") if o.strip()]
    title = (el.get("title") or "").strip()
    if title:
        c.write_block(f"<h3>{escape_text(title)}</h3>")
    criteria: list[ET._Element] = [
        crit for crit in el
        if isinstance(crit.tag, str) and crit.tag.lower() == "rd-criterion"
    ]
    if not criteria or not options:
        return
    parts = ["<table>", "  <thead>"]
    head = "<th></th>" + "".join(f"<th>{escape_text(o)}</th>" for o in options)
    parts.append(f"    <tr>{head}</tr>")
    parts.append("  </thead>")
    parts.append("  <tbody>")
    totals = [0.0] * len(options)
    for crit in criteria:
        label = crit.get("label") or ""
        try:
            weight = float(crit.get("weight") or "1")
        except ValueError:
            weight = 1.0
        scores = [
            s for s in crit if isinstance(s.tag, str) and s.tag.lower() == "rd-score"
        ]
        cells: list[str] = []
        for i, _opt in enumerate(options):
            if i < len(scores):
                v_raw = scores[i].get("value") or "0"
                note = scores[i].get("note") or ""
                try:
                    totals[i] += float(v_raw) * weight
                except ValueError:
                    pass
                cell = escape_text(v_raw) + (
                    f" <small>— {escape_text(note)}</small>" if note else ""
                )
                cells.append(f"<td>{cell}</td>")
            else:
                cells.append("<td></td>")
        parts.append(
            f"    <tr><th>{escape_text(label)} (×{weight:g})</th>"
            + "".join(cells)
            + "</tr>"
        )
    parts.append("  </tbody>")
    parts.append("  <tfoot>")
    total_cells = "".join(
        f"<th>{t:g}</th>" for t in totals
    )
    parts.append(f"    <tr><th>Total</th>{total_cells}</tr>")
    parts.append("  </tfoot>")
    parts.append("</table>")
    c.write_block("\n".join(parts))


# ---------------------------------------------------------------------------
# Code / shell / diff
# ---------------------------------------------------------------------------


def _h_rd_code(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    lang = (el.get("lang") or "").strip() or None
    title = (el.get("title") or "").strip() or None
    line_numbers = el.get("line-numbers") is not None
    body = _dedent(_element_source(el))
    if not body.strip():
        return
    _emit_code(c, text=body, lang=lang, title=title, line_numbers=line_numbers)


def _h_rd_diff(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip() or None
    body = _dedent(_element_source(el))
    if not body.strip():
        return
    _emit_code(c, text=body, lang="diff", title=title)


def _h_rd_shell(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip() or None
    lines: list[str] = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        text = _dedent(child.text or "")
        if t == "rd-prompt":
            cwd = child.get("cwd") or ""
            prefix = f"{cwd} $ " if cwd else "$ "
            for line in text.split("\n"):
                lines.append(f"{prefix}{line}" if line else "$")
        elif t == "rd-output":
            lines.append(text)
    body = "\n".join(lines)
    if not body.strip():
        return
    _emit_code(c, text=body, lang="bash", title=title)


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def _h_rd_math(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    body = _dedent(_element_source(el))
    if not body.strip():
        return
    display = (el.get("display") or "block").lower()
    if c.render_math_images:
        ph = c.queue_math_image(body, display=display)
        alt = body[:80].replace("\n", " ")
        if display == "inline":
            c.write(
                f'<img src="{ph}" alt="{escape_attr(alt)}" '
                f'style="vertical-align:middle">'
            )
        else:
            c.write_block(
                f'<p style="text-align:center"><img src="{ph}" '
                f'alt="{escape_attr(alt)}"></p>'
            )
        return
    # Fallback: keep the source readable as italic plain text.
    if display == "inline":
        c.write(f"<em>{escape_text(body)}</em>")
    else:
        c.write_block(
            f'<p style="text-align:center"><em>{escape_text(body)}</em></p>'
        )


# ---------------------------------------------------------------------------
# Figure / chart / diagram
# ---------------------------------------------------------------------------


def _h_rd_figure(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    caption = (el.get("caption") or "").strip()
    inner = c.render_block_inner_wrapped(el).strip()
    if inner:
        c.write_block(inner)
    if caption:
        c.write_block(f"<p><em>{escape_text(caption)}</em></p>")


def _h_rd_chart(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    caption = (el.get("caption") or "").strip()
    data_attr = el.get("data") or _element_source(el)
    if title:
        c.write_block(f"<h3>{escape_text(title)}</h3>")
    chart = parse_chart(data_attr)
    if chart is not None:
        width = len(chart.headers)
        parts = ["<table>", "  <thead>"]
        head = "".join(f"<th>{escape_text(h)}</th>" for h in chart.headers)
        parts.append(f"    <tr>{head}</tr>")
        parts.append("  </thead>")
        parts.append("  <tbody>")
        for row in chart.rows:
            padded = row + [""] * (width - len(row)) if len(row) < width else row
            tds = "".join(f"<td>{escape_text(cell)}</td>" for cell in padded)
            parts.append(f"    <tr>{tds}</tr>")
        parts.append("  </tbody>")
        parts.append("</table>")
        c.write_block("\n".join(parts))
    elif data_attr.strip():
        # Fall back to a code image so the data still travels visually.
        _emit_code(c, text=data_attr.strip(), lang=None, title=title or None)
    if caption:
        c.write_block(f"<p><em>{escape_text(caption)}</em></p>")


def _h_rd_diagram(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    text = _dedent(_element_source(el))
    lang = (el.get("lang") or "").strip().lower()
    if not text.strip():
        return
    if not lang or not c.render_diagrams:
        # Without a lang or with diagrams disabled, emit the source as a
        # code image so the content still travels visibly.
        _emit_code(c, text=text, lang=lang or None, title=None)
        return
    ph = c.queue_diagram_image(text, kind=lang)
    c.write_block(
        f'<p style="text-align:center"><img src="{ph}" '
        f'alt="{escape_attr(lang + " diagram")}"></p>'
    )


# ---------------------------------------------------------------------------
# Sequenced / interactive
# ---------------------------------------------------------------------------


def _h_rd_tabs(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    for tab in el:
        if not (isinstance(tab.tag, str) and tab.tag.lower() == "rd-tab"):
            continue
        label = (tab.get("label") or "Tab").strip()
        c.write_block(f"<h3>{escape_text(label)}</h3>")
        inner = c.render_block_inner_wrapped(tab).strip()
        if inner:
            c.write_block(inner)


def _h_rd_timeline(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    items: list[str] = []
    for ev in el:
        if not (isinstance(ev.tag, str) and ev.tag.lower() == "rd-event"):
            continue
        date = (ev.get("date") or "").strip()
        title = (ev.get("title") or "").strip()
        body = c.render_inline(ev).strip()
        head_bits = []
        if date:
            head_bits.append(f"<strong>{escape_text(date)}</strong>")
        if title:
            head_bits.append(escape_text(title))
        head = " — ".join(head_bits) if head_bits else ""
        line = head + ((" — " + body) if body else "")
        items.append(f"  <li>{line}</li>")
    if items:
        c.write_block("<ul>\n" + "\n".join(items) + "\n</ul>")


def _h_rd_steps(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    items: list[str] = []
    for step in el:
        if not (isinstance(step.tag, str) and step.tag.lower() == "rd-step"):
            continue
        title = (step.get("title") or "").strip()
        done = step.get("done") is not None
        marker = "✓ " if done else ""
        title_html = (
            f"<s>{escape_text(title)}</s>" if done and title else escape_text(title)
        )
        body = c.render_block_inner_wrapped(step).strip()
        head = f"{marker}<strong>{title_html}</strong>" if title else marker.strip()
        if head and body:
            li_body = f"<p>{head}</p>\n{body}" if body.lstrip().startswith("<") else f"<p>{head} — {body}</p>"
        elif head:
            li_body = f"<p>{head}</p>"
        else:
            li_body = body
        items.append(f"  <li>{li_body}</li>")
    if items:
        c.write_block("<ol>\n" + "\n".join(items) + "\n</ol>")


def _h_rd_detail(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    summary = (el.get("summary") or "Details").strip()
    inner = c.render_block_inner_wrapped(el).strip()
    c.write_block(f"<h3>{escape_text(summary)}</h3>")
    if inner:
        c.write_block(inner)


def _h_rd_checklist(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    items: list[str] = []
    for task in el:
        if not (isinstance(task.tag, str) and task.tag.lower() == "rd-task"):
            continue
        done = task.get("done") is not None
        box = "☑" if done else "☐"
        body = c.render_inline(task).strip()
        assignee = task.get("assignee") or ""
        due = task.get("due") or ""
        meta = []
        if assignee:
            meta.append(f"@{escape_text(assignee)}")
        if due:
            meta.append(f"due {escape_text(due)}")
        meta_str = f" <small>({', '.join(meta)})</small>" if meta else ""
        items.append(f"  <li>{box} {body}{meta_str}</li>")
    if items:
        c.write_block("<ul>\n" + "\n".join(items) + "\n</ul>")


# ---------------------------------------------------------------------------
# TOC
# ---------------------------------------------------------------------------


def _h_rd_toc(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    chapters = [
        child for child in el
        if isinstance(child.tag, str) and child.tag.lower() == "rd-chapter"
    ]
    if not chapters:
        c.dropped.append("rd-toc")
        return
    # Book mode: emit as a simple bulleted list. The pipeline rewrites the
    # hrefs to point at the matching exported page slugs.
    title = (el.get("title") or "Contents").strip()
    c.write_block(f"<h2>{escape_text(title)}</h2>")
    lines: list[str] = ["<ul>"]
    _emit_chapter_list(lines, chapters, depth=1)
    lines.append("</ul>")
    c.write_block("\n".join(lines))


def _emit_chapter_list(
    lines: list[str], chapters: list[ET._Element], depth: int  # noqa: SLF001
) -> None:
    indent = "  " * depth
    for ch in chapters:
        title = _chapter_title(ch)
        href = ch.get("href")
        if href and not _is_external(href):
            # Rewrite .html → .html (passthrough), but normalise to forward-slash
            # path so it works regardless of input style.
            href = re.sub(r"\\", "/", href)
        if href and title:
            lines.append(
                f"{indent}<li><a href=\"{escape_attr(href)}\">{escape_text(title)}</a></li>"
            )
        elif href:
            lines.append(
                f"{indent}<li><a href=\"{escape_attr(href)}\">{escape_text(href)}</a></li>"
            )
        else:
            lines.append(f"{indent}<li><strong>{escape_text(title)}</strong></li>")
        nested = [
            sub for sub in ch
            if isinstance(sub.tag, str) and sub.tag.lower() == "rd-chapter"
        ]
        if nested:
            lines.append(f"{indent}<ul>")
            _emit_chapter_list(lines, nested, depth + 1)
            lines.append(f"{indent}</ul>")


def _chapter_title(node: ET._Element) -> str:  # noqa: SLF001
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if isinstance(child.tag, str) and child.tag.lower() == "rd-chapter":
            if child.tail:
                parts.append(child.tail)
            continue
        parts.extend(child.itertext())
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split()).strip()


def _is_external(href: str) -> bool:
    s = (href or "").strip()
    if not s or s.startswith("#"):
        return True
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", s)) or s.startswith("//")


# ---------------------------------------------------------------------------
# Icons / decision / pros-cons / api
# ---------------------------------------------------------------------------


def _h_rd_icon(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    label = (el.get("label") or "").strip()
    if label:
        c.write(escape_text(label))
    else:
        c.dropped.append("rd-icon")


def _h_rd_decision(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    status = (el.get("status") or "proposed").strip()
    id_ = (el.get("id") or "").strip()
    title = (el.get("title") or "").strip()
    date = (el.get("date") or "").strip()
    deciders = (el.get("deciders") or "").strip()
    head_bits = [b for b in (id_, title) if b]
    head = ": ".join(head_bits) if head_bits else "Decision"
    c.write_block(f"<h2>{escape_text(head)}</h2>")
    c.write_block(
        f"<p><strong>Status:</strong> <code>{escape_text(status.upper())}</code></p>"
    )
    meta = " · ".join(b for b in (date, deciders) if b)
    if meta:
        c.write_block(f"<p><em>{escape_text(meta)}</em></p>")
    inner = c.render_block_inner_wrapped(el).strip()
    if inner:
        c.write_block(inner)


def _h_rd_pros_cons(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    pros_title = (el.get("pros-title") or "Pros").strip()
    cons_title = (el.get("cons-title") or "Cons").strip()
    pros: list[str] = []
    cons: list[str] = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        text = c.render_inline(child).strip()
        if not text:
            continue
        if t == "rd-pro":
            pros.append(f"  <li>{text}</li>")
        elif t == "rd-con":
            cons.append(f"  <li>{text}</li>")
    if pros:
        c.write_block(
            f"<h3>✓ {escape_text(pros_title)}</h3>\n<ul>\n"
            + "\n".join(pros)
            + "\n</ul>"
        )
    if cons:
        c.write_block(
            f"<h3>✗ {escape_text(cons_title)}</h3>\n<ul>\n"
            + "\n".join(cons)
            + "\n</ul>"
        )


def _h_rd_api(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    method = (el.get("method") or "").strip()
    path = (el.get("path") or "").strip()
    auth = (el.get("auth") or "").strip()
    title = (el.get("title") or "").strip()
    head = f"<code>{escape_text(method)}</code> <code>{escape_text(path)}</code>"
    if title:
        head = f"{head} — {escape_text(title)}"
    c.write_block(f"<h3>{head}</h3>")
    if auth:
        c.write_block(
            f"<p><em>auth:</em> <code>{escape_text(auth)}</code></p>"
        )
    params = [
        p for p in el
        if isinstance(p.tag, str) and p.tag.lower() == "rd-param"
    ]
    responses = [
        r for r in el
        if isinstance(r.tag, str) and r.tag.lower() == "rd-response"
    ]
    if params:
        parts = ["<table>", "  <thead>"]
        parts.append(
            "    <tr><th>Param</th><th>In</th><th>Required</th>"
            "<th>Type</th><th>Default</th><th>Description</th></tr>"
        )
        parts.append("  </thead>")
        parts.append("  <tbody>")
        for p in params:
            name = p.get("name") or ""
            in_ = p.get("in") or "query"
            req = "✓" if p.get("required") is not None else ""
            type_ = p.get("type") or ""
            default = p.get("default") or ""
            desc = c.render_inline(p).strip()
            parts.append(
                f"    <tr><td><code>{escape_text(name)}</code></td>"
                f"<td>{escape_text(in_)}</td>"
                f"<td>{escape_text(req)}</td>"
                f"<td>{escape_text(type_)}</td>"
                f"<td>{escape_text(default)}</td>"
                f"<td>{desc}</td></tr>"
            )
        parts.append("  </tbody>")
        parts.append("</table>")
        c.write_block("\n".join(parts))
    if responses:
        parts = ["<table>", "  <thead>"]
        parts.append(
            "    <tr><th>Status</th><th>Type</th><th>Description</th></tr>"
        )
        parts.append("  </thead>")
        parts.append("  <tbody>")
        for r in responses:
            status = r.get("status") or ""
            type_ = r.get("type") or ""
            desc = c.render_inline(r).strip()
            parts.append(
                f"    <tr><td><code>{escape_text(status)}</code></td>"
                f"<td>{escape_text(type_)}</td>"
                f"<td>{desc}</td></tr>"
            )
        parts.append("  </tbody>")
        parts.append("</table>")
        c.write_block("\n".join(parts))


# ---------------------------------------------------------------------------
# References / citations
# ---------------------------------------------------------------------------


def _h_rd_references(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.refs_title = (el.get("title") or "References").strip() or "References"
    # Collect any inline rd-ref children first.
    for child in el:
        if isinstance(child.tag, str) and child.tag.lower() == "rd-ref":
            _collect_ref(c, child)
    # Emit a placeholder; pipeline replaces it with the rendered list once
    # every citation in the document has been processed.
    c.write_block(c.refs_placeholder())


def _h_rd_ref(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    _collect_ref(c, el)


def _h_rd_cite(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    key = (el.get("key") or "").strip()
    if not key:
        return
    if key not in c.ref_order:
        c.ref_order.append(key)
    n = c.ref_order.index(key) + 1
    c.write(f"[{n}]")


def _collect_ref(c: _Converter, el: ET._Element) -> None:
    key = (el.get("key") or "").strip()
    if not key:
        return
    c.ref_entries[key] = {
        "author": el.get("author") or "",
        "title": el.get("title") or "",
        "url": el.get("url") or "",
        "date": el.get("date") or "",
        "publisher": el.get("publisher") or "",
        "note": c.render_inline(el).strip(),
    }


def _h_rd_chapter(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Only meaningful inside <rd-toc>.
    pass
