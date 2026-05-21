"""rd-* component handlers for the Confluence storage-format converter.

Confluence's storage format gives us native macros for code, callouts,
expand/collapse, and tables — which lets the publish path keep richdoc
documents *editable* in the Confluence UI after the push, instead of the
PNG-soup the abandoned zip exporter produced.

Mapping cheat-sheet (long form lives in references/publish.md):

- rd-code / rd-diff / rd-shell  → native `code` macro
- rd-callout / rd-banner        → native `info` / `note` / `warning` / `tip` macros
- rd-detail                     → native `expand` macro (still collapsible!)
- rd-math / rd-diagram          → Kroki PNG → page attachment → <ac:image>
- rd-toc                        → dropped (Confluence native sidebar shows the tree)
- everything else               → plain XHTML built from the relevant attributes
"""

from __future__ import annotations


import lxml.etree as ET

from ...export.common.chart_data import parse_chart
from ...export.common.diagrams import render_to_png
from .converter import (
    _Converter,
    _element_source,
    dedent,
    xml_attr,
    xml_escape,
)
from .handlers_plain import emit_code_macro
from .math import render_math_png


# Map richdoc callout/banner types onto Confluence macro names.
_CALLOUT_MACRO = {
    "info": "info",
    "note": "note",
    "tldr": "note",
    "success": "tip",
    "warn": "warning",
    "danger": "warning",
}


# ---------------------------------------------------------------------------
# Page / hero / sections / callouts
# ---------------------------------------------------------------------------


def _h_rd_page(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_rd_hero(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-hero → <h1> + meta paragraphs. Title duplicates the page title;
    Confluence editors typically prefer the page-title-only convention but
    keeping the h1 keeps standalone exports recognisable."""
    title = (el.get("title") or "").strip()
    eyebrow = (el.get("eyebrow") or "").strip()
    lede = (el.get("lede") or "").strip()
    meta = (el.get("meta") or "").strip()
    if title:
        c.write_block(f"<h1>{xml_escape(title)}</h1>")
    bits = [b for b in (eyebrow, lede, meta) if b]
    if bits:
        c.write_block(
            "<p><em>" + xml_escape(" · ".join(bits)) + "</em></p>"
        )
    inner = c.render_block_inner_wrapped(el)
    if inner:
        c.write_block(inner)


def _h_rd_section(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    if title:
        c.write_block(f"<h2>{xml_escape(title)}</h2>")
    inner = c.render_block_inner_wrapped(el)
    if inner:
        c.write_block(inner)


def _h_rd_card(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    if title:
        c.write_block(f"<h3>{xml_escape(title)}</h3>")
    inner = c.render_block_inner_wrapped(el)
    if inner:
        c.write_block(inner)


def _h_rd_cols(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Confluence has a native multi-column macro, but it's part of the
    # Adaptavist suite, not core. We linearise instead.
    c.render_children(el)


def _h_rd_banner(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    macro = _CALLOUT_MACRO.get(type_, "info")
    attr_message = (el.get("message") or "").strip()
    if attr_message:
        body = f"<p>{xml_escape(attr_message)}</p>"
    else:
        inner = c.render_inline(el).strip()
        if not inner:
            return
        body = f"<p>{inner}</p>"
    c.write_block(_emit_callout(macro=macro, title=None, body=body))


def _h_rd_callout(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    title = (el.get("title") or "").strip()
    if not title and type_ == "tldr":
        title = "TL;DR"
    macro = _CALLOUT_MACRO.get(type_, "info")
    body = c.render_block_inner_wrapped(el)
    if not body and not title:
        return
    c.write_block(_emit_callout(macro=macro, title=title or None, body=body))


def _emit_callout(*, macro: str, title: str | None, body: str) -> str:
    """Build a Confluence callout macro (`info`, `note`, `tip`, `warning`)."""
    params = ""
    if title:
        params = (
            '<ac:parameter ac:name="title">'
            f"{xml_escape(title)}"
            "</ac:parameter>"
        )
    return (
        f'<ac:structured-macro ac:name="{xml_attr(macro)}">'
        f"{params}"
        f"<ac:rich-text-body>{body or ''}</ac:rich-text-body>"
        "</ac:structured-macro>"
    )


# ---------------------------------------------------------------------------
# Information blocks
# ---------------------------------------------------------------------------


def _h_rd_kv(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip()
    layout = (el.get("layout") or "inline").lower()
    rows = [r for r in el if isinstance(r.tag, str) and r.tag.lower() == "rd-row"]
    if title:
        c.write_block(f"<p><strong>{xml_escape(title)}</strong></p>")
    if not rows:
        return
    if layout == "stacked":
        # Definition-list-ish — Confluence has no native <dl>; use a
        # bullet list with <strong> labels.
        items: list[str] = []
        for r in rows:
            key = (r.get("key") or "").strip()
            value = c.render_block_inner(r).strip()
            items.append(
                f"<li><strong>{xml_escape(key)}</strong><br/>{value}</li>"
                if value
                else f"<li><strong>{xml_escape(key)}</strong></li>"
            )
        c.write_block(f"<ul>{''.join(items)}</ul>")
    else:
        items = []
        for r in rows:
            key = (r.get("key") or "").strip()
            value = c.render_inline(r).strip()
            items.append(
                f"<li><strong>{xml_escape(key)}:</strong> {value}</li>"
                if value
                else f"<li><strong>{xml_escape(key)}</strong></li>"
            )
        c.write_block(f"<ul>{''.join(items)}</ul>")


def _h_rd_row(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Handled inside rd-kv. Loose row → render its children inline.
    c.render_children(el)


def _h_rd_badge(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    variant = (el.get("variant") or "").strip()
    inner = c.render_inline(el).strip()
    label = inner or variant or "badge"
    c.write(f"<strong>[{label}]</strong>")


def _h_rd_stat(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    value = (el.get("value") or "").strip()
    label = (el.get("label") or "").strip()
    trend = (el.get("trend") or "").strip()
    delta = (el.get("delta") or "").strip()
    extras = []
    if trend:
        glyph = {"up": "▲", "down": "▼", "flat": "→"}.get(trend, trend)
        extras.append(glyph)
    if delta:
        extras.append(delta)
    pieces = [f"<strong>{xml_escape(value)}</strong>"]
    if label:
        pieces.append(f" — {xml_escape(label)}")
    if extras:
        pieces.append(f" <em>({xml_escape(' '.join(extras))})</em>")
    c.write_block(f"<p>{''.join(pieces)}</p>")
    for child in el:
        if isinstance(child.tag, str) and child.tag.lower().startswith("rd-"):
            c.dropped.append(child.tag.lower())


def _h_rd_progress(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    from ...export.common.progress import parse_progress  # noqa: PLC0415

    p = parse_progress(el.get("value"))
    label = (el.get("label") or "").strip()
    head = (
        f"<strong>{xml_escape(label)}:</strong> {xml_escape(p.display)}"
        if label
        else f"<strong>Progress:</strong> {xml_escape(p.display)}"
    )
    c.write_block(f"<p>{head}</p>")


def _h_rd_update(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    date = (el.get("date") or "").strip()
    kind = (el.get("kind") or "").strip()
    author = (el.get("author") or "").strip()
    title = (el.get("title") or "").strip()
    head = f"<h3>{xml_escape(date)}"
    if title:
        head += f" — {xml_escape(title)}"
    head += "</h3>"
    c.write_block(head)
    meta_bits = [b for b in (kind, author) if b]
    if meta_bits:
        c.write_block(
            f"<p><em>{xml_escape(' · '.join(meta_bits))}</em></p>"
        )
    inner = c.render_block_inner_wrapped(el)
    if inner:
        c.write_block(inner)


# ---------------------------------------------------------------------------
# Comparison and code
# ---------------------------------------------------------------------------


def _h_rd_compare(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    headers = [h.strip() for h in (el.get("headers") or "").split(",") if h.strip()]
    rows: list[list[str]] = []
    for rc in el:
        if not (isinstance(rc.tag, str) and rc.tag.lower() == "rd-row-cells"):
            continue
        label = (rc.get("label") or "").strip()
        cells: list[str] = []
        for cell in rc:
            if not (isinstance(cell.tag, str) and cell.tag.lower() == "rd-cell"):
                continue
            tone = (cell.get("tone") or "").lower()
            glyph = {"positive": "✓ ", "negative": "✗ ", "neutral": "· "}.get(tone, "")
            text = c.render_inline(cell).strip()
            cells.append(xml_escape(glyph) + text)
        rows.append([xml_escape(label), *cells])
    if not headers and not rows:
        return
    width = max(len(headers), max((len(r) for r in rows), default=0))
    header_cells = [xml_escape(h) for h in headers]
    while len(header_cells) < width:
        header_cells.append("&nbsp;")
    body_rows: list[str] = []
    for r in rows:
        while len(r) < width:
            r.append("&nbsp;")
        body_rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in r) + "</tr>")
    head_xml = (
        "<thead><tr>"
        + "".join(f"<th>{cell}</th>" for cell in header_cells)
        + "</tr></thead>"
    )
    c.write_block(
        f"<table>{head_xml}<tbody>{''.join(body_rows)}</tbody></table>"
    )


def _h_rd_rubric(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    options = [o.strip() for o in (el.get("options") or "").split(",") if o.strip()]
    title = (el.get("title") or "").strip()
    if title:
        c.write_block(f"<h3>{xml_escape(title)}</h3>")
    rows: list[list[str]] = []
    totals = [0.0] * len(options)
    for crit in el:
        if not (isinstance(crit.tag, str) and crit.tag.lower() == "rd-criterion"):
            continue
        label = (crit.get("label") or "").strip()
        try:
            weight = float(crit.get("weight") or "1")
        except ValueError:
            weight = 1.0
        scores = [
            s for s in crit if isinstance(s.tag, str) and s.tag.lower() == "rd-score"
        ]
        cells: list[str] = []
        for i, _ in enumerate(options):
            if i < len(scores):
                v = scores[i].get("value") or "0"
                note = (scores[i].get("note") or "").strip()
                try:
                    totals[i] += float(v) * weight
                except ValueError:
                    pass
                cells.append(
                    xml_escape(f"{v}" + (f" — {note}" if note else ""))
                )
            else:
                cells.append("&nbsp;")
        rows.append([xml_escape(f"{label} (×{weight:g})"), *cells])
    head_cells = ["&nbsp;", *[xml_escape(o) for o in options]]
    head_xml = (
        "<thead><tr>"
        + "".join(f"<th>{cell}</th>" for cell in head_cells)
        + "</tr></thead>"
    )
    body_xml = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in r) + "</tr>"
        for r in rows
    )
    totals_xml = (
        "<tr>"
        + "<td><strong>Total</strong></td>"
        + "".join(f"<td><strong>{xml_escape(f'{t:g}')}</strong></td>" for t in totals)
        + "</tr>"
    )
    c.write_block(
        f"<table>{head_xml}<tbody>{body_xml}{totals_xml}</tbody></table>"
    )


def _h_rd_code(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    lang = (el.get("lang") or "").strip()
    title = (el.get("title") or "").strip() or None
    body = _element_source(el)
    emit_code_macro(c, body, lang=lang, title=title)


def _h_rd_diff(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip() or None
    body = _element_source(el)
    emit_code_macro(c, body, lang="diff", title=title)


def _h_rd_shell(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    title = (el.get("title") or "").strip() or None
    lines: list[str] = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        text = dedent(child.text or "")
        if t == "rd-prompt":
            for line in text.split("\n"):
                lines.append(f"$ {line}" if line else "$")
        elif t == "rd-output":
            lines.append(text)
    emit_code_macro(c, "\n".join(lines), lang="bash", title=title)


def _h_rd_math(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    display = (el.get("display") or "block").lower()
    source = dedent(_element_source(el))
    if not source.strip():
        return
    if not c.render_math:
        # Plain-text fallback: italic source.
        if display == "inline":
            c.write(f"<em>{xml_escape(source)}</em>")
        else:
            c.write_block(f"<p><em>{xml_escape(source)}</em></p>")
        return
    png = render_math_png(source, endpoint=c.diagram_endpoint)
    if png is None:
        c.math_failed += 1
        if display == "inline":
            c.write(f"<em>{xml_escape(source)}</em>")
        else:
            c.write_block(f"<p><em>{xml_escape(source)}</em></p>")
        return
    c.math_rendered += 1
    is_inline = display == "inline"
    token = c.queue_attachment(
        data=png,
        prefix="math",
        mime="image/png",
        ext=".png",
        align="center" if not is_inline else "",
        is_inline=is_inline,
    )
    if is_inline:
        c.write(token)
    else:
        c.write_block(f"<p>{token}</p>")


def _h_rd_figure(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    caption = (el.get("caption") or "").strip()
    inner = c.render_block_inner_wrapped(el)
    if inner:
        c.write_block(inner)
    if caption:
        c.write_block(f"<p><em>{xml_escape(caption)}</em></p>")


def _h_rd_chart(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-chart → native table when parseable, or a code block fallback.

    Sparkline variants would clutter the page with raw data; we drop them.
    """
    variant = (el.get("variant") or "").strip().lower()
    if variant == "sparkline":
        c.dropped.append("rd-chart[sparkline]")
        return
    title = (el.get("title") or "").strip()
    caption = (el.get("caption") or "").strip()
    if title:
        c.write_block(f"<p><strong>{xml_escape(title)}</strong></p>")
    data_attr = el.get("data") or _element_source(el)
    table = parse_chart(data_attr)
    if table is not None:
        header_xml = (
            "<thead><tr>"
            + "".join(f"<th>{xml_escape(h)}</th>" for h in table.headers)
            + "</tr></thead>"
        )
        body_rows: list[str] = []
        for row in table.rows:
            padded = row + [""] * (len(table.headers) - len(row))
            body_rows.append(
                "<tr>"
                + "".join(f"<td>{xml_escape(v)}</td>" for v in padded)
                + "</tr>"
            )
        c.write_block(
            f"<table>{header_xml}<tbody>{''.join(body_rows)}</tbody></table>"
        )
    elif data_attr.strip():
        emit_code_macro(c, data_attr, lang="text", title=None)
    if caption:
        c.write_block(f"<p><em>{xml_escape(caption)}</em></p>")


# ---------------------------------------------------------------------------
# Sequenced / interactive
# ---------------------------------------------------------------------------


def _h_rd_tabs(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    for tab in el:
        if not (isinstance(tab.tag, str) and tab.tag.lower() == "rd-tab"):
            continue
        label = (tab.get("label") or "Tab").strip()
        c.write_block(f"<h3>{xml_escape(label)}</h3>")
        inner = c.render_block_inner_wrapped(tab)
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
        head_parts = []
        if date:
            head_parts.append(f"<strong>{xml_escape(date)}</strong>")
        if title:
            head_parts.append(f"— {xml_escape(title)}")
        if body:
            head_parts.append(f"— {body}")
        if head_parts:
            items.append(f"<li>{' '.join(head_parts)}</li>")
    if items:
        c.write_block(f"<ul>{''.join(items)}</ul>")


def _h_rd_steps(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    items: list[str] = []
    for step in el:
        if not (isinstance(step.tag, str) and step.tag.lower() == "rd-step"):
            continue
        title = (step.get("title") or "").strip()
        done = step.get("done") is not None
        title_xml = (
            f"<s>{xml_escape(title)}</s>" if done and title
            else xml_escape(title)
        )
        body = c.render_block_inner(step).strip()
        bits: list[str] = []
        if title_xml:
            bits.append(f"<strong>{title_xml}</strong>")
        if body:
            bits.append(body)
        items.append("<li>" + " ".join(bits) + "</li>")
    if items:
        c.write_block(f"<ol>{''.join(items)}</ol>")


def _h_rd_detail(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-detail → native `expand` macro. Collapsibility preserved!"""
    summary = (el.get("summary") or "Details").strip()
    body = c.render_block_inner_wrapped(el)
    if not body:
        return
    c.write_block(
        '<ac:structured-macro ac:name="expand">'
        '<ac:parameter ac:name="title">'
        f"{xml_escape(summary)}"
        "</ac:parameter>"
        f"<ac:rich-text-body>{body}</ac:rich-text-body>"
        "</ac:structured-macro>"
    )


def _h_rd_checklist(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Confluence has a native `task-list` element. We use it so checkboxes
    are interactive in the published page."""
    tasks: list[str] = []
    for task in el:
        if not (isinstance(task.tag, str) and task.tag.lower() == "rd-task"):
            continue
        done = task.get("done") is not None
        assignee = (task.get("assignee") or "").strip()
        due = (task.get("due") or "").strip()
        body = c.render_inline(task).strip()
        meta_bits = []
        if assignee:
            meta_bits.append(f"@{assignee}")
        if due:
            meta_bits.append(f"due {due}")
        meta = (
            f" <em>({xml_escape(', '.join(meta_bits))})</em>"
            if meta_bits
            else ""
        )
        status = "complete" if done else "incomplete"
        tasks.append(
            "<ac:task>"
            f"<ac:task-status>{status}</ac:task-status>"
            f"<ac:task-body><span>{body}{meta}</span></ac:task-body>"
            "</ac:task>"
        )
    if tasks:
        c.write_block("<ac:task-list>" + "".join(tasks) + "</ac:task-list>")


def _h_rd_diagram(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    source = dedent(_element_source(el))
    lang = (el.get("lang") or "mermaid").strip().lower()
    if not source.strip():
        return
    if not c.render_diagrams:
        emit_code_macro(c, source, lang=lang, title=None)
        return
    png = render_to_png(source, kind=lang, endpoint=c.diagram_endpoint)
    if png is None:
        c.diagrams_failed += 1
        emit_code_macro(c, source, lang=lang, title=None)
        return
    c.diagrams_rendered += 1
    token = c.queue_attachment(
        data=png, prefix="diag", mime="image/png", ext=".png", align="center"
    )
    c.write_block(f"<p>{token}</p>")


# ---------------------------------------------------------------------------
# TOC / chapters / icons
# ---------------------------------------------------------------------------


def _h_rd_toc(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Confluence has a native page tree in the sidebar — an in-page TOC
    is redundant and visually noisy. Drop it."""
    c.dropped.append("rd-toc")


def _h_rd_icon(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    label = (el.get("label") or "").strip()
    if label:
        c.write_text(label)
    else:
        c.dropped.append("rd-icon")


# ---------------------------------------------------------------------------
# Decisions and planning
# ---------------------------------------------------------------------------


def _h_rd_decision(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    status = (el.get("status") or "proposed").strip()
    id_ = (el.get("id") or "").strip()
    date = (el.get("date") or "").strip()
    deciders = (el.get("deciders") or "").strip()
    title = (el.get("title") or "").strip()
    head_bits = [b for b in (id_, title) if b]
    head = "<h2>" + xml_escape(": ".join(head_bits) if head_bits else "Decision") + "</h2>"
    c.write_block(head)
    meta_bits = [f"[{status.upper()}]"]
    if date:
        meta_bits.append(date)
    if deciders:
        meta_bits.append(deciders)
    c.write_block(
        "<p><em>" + xml_escape(" · ".join(meta_bits)) + "</em></p>"
    )
    inner = c.render_block_inner_wrapped(el)
    if inner:
        c.write_block(inner)


def _h_rd_pros_cons(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    pros_title = (el.get("pros-title") or "Pros").strip()
    cons_title = (el.get("cons-title") or "Cons").strip()
    pros, cons = [], []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        text = c.render_inline(child).strip()
        if t == "rd-pro":
            pros.append(f"<li>{text}</li>")
        elif t == "rd-con":
            cons.append(f"<li>{text}</li>")
    if pros:
        c.write_block(
            f"<h4>{xml_escape(pros_title)}</h4>"
            f"<ul>{''.join(pros)}</ul>"
        )
    if cons:
        c.write_block(
            f"<h4>{xml_escape(cons_title)}</h4>"
            f"<ul>{''.join(cons)}</ul>"
        )


def _h_rd_api(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    method = (el.get("method") or "").strip()
    path = (el.get("path") or "").strip()
    auth = (el.get("auth") or "").strip()
    title = (el.get("title") or "").strip()
    head = (
        f"<h3><code>{xml_escape(method)}</code> "
        f"<code>{xml_escape(path)}</code>"
    )
    if title:
        head += f" — {xml_escape(title)}"
    head += "</h3>"
    c.write_block(head)
    if auth:
        c.write_block(
            f"<p><em>auth:</em> <code>{xml_escape(auth)}</code></p>"
        )
    params, responses = [], []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        t = child.tag.lower()
        if t == "rd-param":
            params.append(child)
        elif t == "rd-response":
            responses.append(child)
    if params:
        head_xml = (
            "<thead><tr>"
            "<th>Param</th><th>In</th><th>Required</th>"
            "<th>Type</th><th>Default</th><th>Description</th>"
            "</tr></thead>"
        )
        body_rows = []
        for p in params:
            name = p.get("name") or ""
            in_ = p.get("in") or "query"
            req = "✓" if p.get("required") is not None else ""
            type_ = p.get("type") or ""
            default = p.get("default") or ""
            desc = c.render_inline(p).strip()
            body_rows.append(
                "<tr>"
                f"<td><code>{xml_escape(name)}</code></td>"
                f"<td>{xml_escape(in_)}</td>"
                f"<td>{xml_escape(req)}</td>"
                f"<td>{xml_escape(type_)}</td>"
                f"<td>{xml_escape(default)}</td>"
                f"<td>{desc}</td>"
                "</tr>"
            )
        c.write_block(
            f"<table>{head_xml}<tbody>{''.join(body_rows)}</tbody></table>"
        )
    if responses:
        head_xml = (
            "<thead><tr>"
            "<th>Status</th><th>Type</th><th>Description</th>"
            "</tr></thead>"
        )
        body_rows = []
        for r in responses:
            status = r.get("status") or ""
            type_ = r.get("type") or ""
            desc = c.render_inline(r).strip()
            body_rows.append(
                "<tr>"
                f"<td><code>{xml_escape(status)}</code></td>"
                f"<td>{xml_escape(type_)}</td>"
                f"<td>{desc}</td>"
                "</tr>"
            )
        c.write_block(
            f"<table>{head_xml}<tbody>{''.join(body_rows)}</tbody></table>"
        )


# ---------------------------------------------------------------------------
# References / citations
# ---------------------------------------------------------------------------


def _h_rd_references(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """An explicit rd-references block sets the section title and renders
    its rd-ref children inline. Refs scattered elsewhere in the document
    are still picked up by `_h_rd_ref` and merged into the same
    bibliography by `_Converter.finalise()`."""
    title = (el.get("title") or "References").strip()
    c.refs_section_title = title
    # Collect rd-ref children into the shared dict; the bibliography is
    # emitted at finalise() time so order matches `rd-cite` uses.
    for r in el:
        if isinstance(r.tag, str) and r.tag.lower() == "rd-ref":
            _collect_ref(c, r)
    # If the author wrote rd-references but no refs, still emit a heading
    # to preserve their intent.
    if not c.refs_collected:
        c.write_block(f"<h2>{xml_escape(title)}</h2>")


def _h_rd_ref(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Collect a bibliography entry. The actual rendering happens in
    `finalise()` so cite order drives the numbering."""
    _collect_ref(c, el)


def _collect_ref(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    key = (el.get("key") or "").strip()
    if not key:
        return
    c.refs_collected[key] = {
        "author": el.get("author") or "",
        "title": el.get("title") or "",
        "url": el.get("url") or "",
        "date": el.get("date") or "",
        "publisher": el.get("publisher") or "",
        # render_inline already returns XML — safe to embed verbatim.
        "note": c.render_inline(el).strip(),
    }


def _h_rd_cite(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Emit a numbered citation marker. Numbering follows cite-order: the
    first key encountered is `[1]`, the second is `[2]`, etc. The
    bibliography below renumbers identically."""
    key = (el.get("key") or "").strip()
    if not key:
        return
    if key not in c.refs_order:
        c.refs_order.append(key)
    n = c.refs_order.index(key) + 1
    c.write(f"<sup>[{n}]</sup>")
