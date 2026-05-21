"""rd-* component handlers for the DOCX exporter."""

from __future__ import annotations

from io import BytesIO

import lxml.etree as ET
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from ..common.chart_data import parse_chart
from ..common.diagrams import render_to_png
from .references import _collect_ref, _emit_references
from .runs import (
    _Run,
    _emit_runs,
    _flatten_inline,
    _inline_runs,
)
from .state import _State
from .tables import _fill_row, _set_cell_border, _set_cell_shading
from .walker import (
    _dedent,
    _element_source,
    _embed_image,
    _emit_code,
    render_block,
    render_children,
)


# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------


def _h_rd_page(state: _State, el: ET._Element) -> None:
    render_children(state, el)


def _h_rd_section(state: _State, el: ET._Element) -> None:
    title = el.get("title") or ""
    if title:
        state.doc.add_heading(title, level=2)
    render_children(state, el)


def _h_rd_hero(state: _State, el: ET._Element) -> None:
    title = el.get("title") or ""
    eyebrow = el.get("eyebrow") or ""
    lede = el.get("lede") or ""
    meta = el.get("meta") or ""
    if eyebrow:
        p = state.add_paragraph()
        r = p.add_run(eyebrow.upper())
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    if title:
        state.doc.add_heading(title, level=1)
    if lede:
        p = state.add_paragraph()
        r = p.add_run(lede)
        r.italic = True
    if meta:
        p = state.add_paragraph()
        r = p.add_run(meta)
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    # Extras
    render_children(state, el)


def _h_rd_banner(state: _State, el: ET._Element) -> None:
    type_ = (el.get("type") or "info").lower()
    msg = (el.get("message") or _flatten_inline(state, el)).strip()
    label = type_.upper()
    p = state.add_paragraph()
    r = p.add_run(f"[{label}] ")
    r.bold = True
    if msg:
        p.add_run(msg)


_CALLOUT_DEFAULT_TITLE = {
    "info": "Info",
    "success": "Success",
    "warn": "Warning",
    "danger": "Danger",
    "note": "Note",
    "tldr": "TL;DR",
}

_CALLOUT_COLORS = {
    "info": "3B82F6",
    "success": "10B981",
    "warn": "F59E0B",
    "danger": "EF4444",
    "note": "6B7280",
    "tldr": "111111",
}


_CALLOUT_BLOCK_TAGS = {
    "p", "ul", "ol", "pre", "blockquote", "table", "hr",
    "rd-code", "rd-diff", "rd-shell",
}


def _h_rd_callout(state: _State, el: ET._Element) -> None:
    type_ = (el.get("type") or "info").lower()
    title = el.get("title") or _CALLOUT_DEFAULT_TITLE.get(type_, "")
    color = _CALLOUT_COLORS.get(type_, "DDDDDD")

    table = state.doc.add_table(rows=1, cols=1)
    table.autofit = True
    cell = table.rows[0].cells[0]
    _set_cell_border(cell, side="left", color=color, sz=24)
    _set_cell_shading(cell, "FAFAFA")
    cell.text = ""

    # Detect whether the callout's body is inline-only (a bare text run or
    # inline tags) versus structured (any block child like <p>, <ul>, <rd-code>).
    has_block_children = any(
        isinstance(c.tag, str) and c.tag.lower() in _CALLOUT_BLOCK_TAGS
        for c in el
    )

    if title:
        p = cell.paragraphs[0]
        r = p.add_run(title)
        r.bold = True
        body_p_first = cell.add_paragraph()
    else:
        body_p_first = cell.paragraphs[0]

    if not has_block_children:
        # Inline-only callout: <rd-callout>just some text</rd-callout>.
        runs = _inline_runs(state, el)
        if any(r.text.strip() for r in runs):
            _emit_runs(body_p_first, runs)
        return

    # Structured callout: emit each block child as its own paragraph.
    # Any leading inline text (el.text) lands on the first body paragraph.
    first_used = False
    if el.text and el.text.strip():
        body_p_first.add_run(el.text.strip())
        first_used = True
    for child in el:
        if not isinstance(child.tag, str):
            continue
        tag = child.tag.lower()
        if tag not in _CALLOUT_BLOCK_TAGS:
            # Skip stray inline elements (they'd be confusing siblings to <p>);
            # the JS component wraps everything in body text, so authors who
            # mix inline + block at the top level are rare.
            continue
        text = _flatten_inline(state, child).strip()
        if not text:
            continue
        target = body_p_first if not first_used else cell.add_paragraph()
        if target is body_p_first:
            target.add_run(text)
            first_used = True
        else:
            target.add_run(text)


def _h_rd_kv(state: _State, el: ET._Element) -> None:
    title = el.get("title") or ""
    if title:
        state.doc.add_heading(title, level=3)
    rows = [r for r in el if isinstance(r.tag, str) and r.tag.lower() == "rd-row"]
    if not rows:
        return
    table = state.doc.add_table(rows=len(rows), cols=2)
    table.autofit = True
    for i, row in enumerate(rows):
        key = row.get("key") or ""
        value_runs = _inline_runs(state, row)
        cells = table.rows[i].cells
        cells[0].text = ""
        kp = cells[0].paragraphs[0]
        kr = kp.add_run(key)
        kr.bold = True
        cells[1].text = ""
        vp = cells[1].paragraphs[0]
        _emit_runs(vp, value_runs)


def _h_rd_stat(state: _State, el: ET._Element) -> None:
    value = el.get("value") or ""
    label = el.get("label") or ""
    delta = el.get("delta") or ""
    p = state.add_paragraph()
    r = p.add_run(value)
    r.bold = True
    r.font.size = Pt(24)
    if label:
        p2 = state.add_paragraph()
        rr = p2.add_run(label)
        rr.font.size = Pt(9)
        rr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    if delta:
        p3 = state.add_paragraph()
        p3.add_run(delta)


def _h_rd_progress(state: _State, el: ET._Element) -> None:
    from ..common.progress import parse_progress  # noqa: PLC0415

    parsed = parse_progress(el.get("value"))
    label = el.get("label") or ""
    p = state.add_paragraph()
    if label:
        r = p.add_run(f"{label}: ")
        r.bold = True
    p.add_run(parsed.display)


def _h_rd_update(state: _State, el: ET._Element) -> None:
    date = el.get("date") or ""
    kind = el.get("kind") or ""
    author = el.get("author") or ""
    title = el.get("title") or ""
    heading_bits = [b for b in (date, kind, title) if b]
    if heading_bits:
        state.doc.add_heading(" — ".join(heading_bits), level=4)
    if author:
        p = state.add_paragraph()
        r = p.add_run(f"by {author}")
        r.italic = True
    render_children(state, el)


def _h_rd_cols(state: _State, el: ET._Element) -> None:
    # Flatten to sequential rendering — Confluence Word import doesn't
    # preserve Word columns reliably, and rd-cols is structural parallelism.
    render_children(state, el)


def _h_rd_card(state: _State, el: ET._Element) -> None:
    title = el.get("title") or ""
    accent = el.get("accent") or ""
    if accent:
        p = state.add_paragraph()
        r = p.add_run(accent.upper())
        r.bold = True
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    if title:
        state.doc.add_heading(title, level=3)
    render_children(state, el)


def _h_rd_code(state: _State, el: ET._Element) -> None:
    lang = el.get("lang") or None
    title = el.get("title") or ""
    if title:
        p = state.add_paragraph()
        r = p.add_run(title)
        r.bold = True
    text = _dedent(_element_source(el))
    _emit_code(state, text, lang=lang)


def _h_rd_diff(state: _State, el: ET._Element) -> None:
    title = el.get("title") or ""
    if title:
        p = state.add_paragraph()
        r = p.add_run(title)
        r.bold = True
    text = _dedent(_element_source(el))
    _emit_code(state, text, lang="diff")


def _h_rd_shell(state: _State, el: ET._Element) -> None:
    title = el.get("title") or ""
    if title:
        p = state.add_paragraph()
        r = p.add_run(title)
        r.bold = True
    lines: list[str] = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        tag = child.tag.lower()
        text = " ".join("".join(child.itertext()).split())
        if tag == "rd-prompt":
            cwd = child.get("cwd")
            if cwd:
                lines.append(f"{cwd} $ {text}")
            else:
                lines.append(f"$ {text}")
        elif tag == "rd-output":
            lines.append(text)
    _emit_code(state, "\n".join(lines), lang=None)


def _h_rd_math(state: _State, el: ET._Element) -> None:
    from .math import latex_to_omath, wrap_block  # noqa: PLC0415 — keep import local

    text = _dedent(_element_source(el))
    if not text.strip():
        return
    display = (el.get("display") or "block").lower()
    omath = latex_to_omath(text)
    if omath is None:
        # LaTeX we couldn't convert — fall back to italic Cambria Math so
        # the source still travels and reads as math, not code.
        p = state.add_paragraph()
        if display != "inline":
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.italic = True
        r.font.name = "Cambria Math"
        return
    if display == "inline":
        # Block-position inline math: rare but possible. Drop it on its own
        # paragraph without the oMathPara wrapper so it sits on the
        # baseline like a normal run.
        p = state.add_paragraph()
        p._p.append(omath)
    else:
        p = state.add_paragraph()
        p._p.append(wrap_block(omath))


def _h_rd_figure(state: _State, el: ET._Element) -> None:
    caption = el.get("caption") or ""
    # rd-figure wraps an arbitrary block (img, rd-diagram, rd-chart,
    # etc.) plus an optional caption.
    render_children(state, el)
    if caption:
        p = state.add_paragraph()
        r = p.add_run(caption)
        r.italic = True
        r.font.size = Pt(9)


def _h_rd_chart(state: _State, el: ET._Element) -> None:
    title = el.get("title") or ""
    caption = el.get("caption") or ""
    data_attr = el.get("data") or _element_source(el)
    if title:
        p = state.add_paragraph()
        r = p.add_run(title)
        r.bold = True
    rendered = _chart_to_table(state, data_attr)
    if not rendered and data_attr.strip():
        _emit_code(state, data_attr.strip(), lang=None)
    if caption:
        p = state.add_paragraph()
        r = p.add_run(caption)
        r.italic = True
        r.font.size = Pt(9)


def _chart_to_table(state: _State, raw: str) -> bool:  # noqa: SLF001
    chart = parse_chart(raw)
    if chart is None:
        return False
    width = len(chart.headers)
    table = state.doc.add_table(rows=1 + len(chart.rows), cols=width)
    table.style = "Table Grid"
    _fill_row(state, table.rows[0], chart.headers, bold=True)
    for i, row in enumerate(chart.rows, start=1):
        # Pad short rows with empty strings to match docx's prior behavior.
        padded = row + [""] * (width - len(row)) if len(row) < width else row
        _fill_row(state, table.rows[i], padded)
    return True


def _h_rd_tabs(state: _State, el: ET._Element) -> None:
    for tab in el:
        if not (isinstance(tab.tag, str) and tab.tag.lower() == "rd-tab"):
            continue
        label = tab.get("label") or ""
        if label:
            state.doc.add_heading(label, level=3)
        render_children(state, tab)


def _h_rd_timeline(state: _State, el: ET._Element) -> None:
    for ev in el:
        if not (isinstance(ev.tag, str) and ev.tag.lower() == "rd-event"):
            continue
        date = ev.get("date") or ""
        title = ev.get("title") or ""
        head = " — ".join(b for b in (date, title) if b)
        if head:
            p = state.add_paragraph()
            r = p.add_run(head)
            r.bold = True
        render_children(state, ev)


_STEP_BLOCK_TAGS = {
    "p", "ul", "ol", "pre", "blockquote", "table", "hr",
    "rd-code", "rd-diff", "rd-shell", "rd-callout", "rd-diagram",
    "rd-figure", "rd-math", "rd-chart",
}


def _h_rd_steps(state: _State, el: ET._Element) -> None:
    state.list_stack.append(("ol", 0))
    for step in el:
        if not (isinstance(step.tag, str) and step.tag.lower() == "rd-step"):
            continue
        title = step.get("title") or ""
        done = step.get("done") is not None
        marker = "☑ " if done else ""
        p = state.doc.add_paragraph(style="List Number")
        if marker:
            p.add_run(marker)
        if title:
            tr = p.add_run(title)
            tr.bold = True
        # Body: walk children, emitting inline content (text / <code> /
        # <strong> / etc.) onto the list-item paragraph and dispatching any
        # block-level child (ul, pre, rd-code, …) as its own paragraph.
        # `_inline_runs` already handles text + tail correctly; we only
        # need to split the step into inline-vs-block segments first.
        inline_runs, block_children = _split_step_body(state, step)
        if inline_runs:
            if title or marker:
                p.add_run(" \u2014 ")  # em-dash separator between title and body
            _emit_runs(p, inline_runs)
        for block in block_children:
            render_block(state, block)
    state.list_stack.pop()


def _split_step_body(state: _State, step: ET._Element) -> tuple[list, list[ET._Element]]:
    """Return (inline_runs, block_children) for an rd-step body.

    Inline content (leading text, inline tags, their tails) collapses into
    one run list. Block children (`<p>`, `<ul>`, `<rd-code>`, …) are
    rendered separately as follow-on paragraphs.
    """
    from .runs import _Run, _inline_runs  # noqa: PLC0415

    from .walker import _inline_text  # noqa: PLC0415

    runs: list[_Run] = []
    blocks: list[ET._Element] = []
    if step.text:
        runs.append(_Run(_inline_text(step.text)))
    # Snapshot children before any reparenting (we splice inline ones into a
    # synthetic wrapper, which would otherwise corrupt iteration).
    children = list(step)
    for child in children:
        tag = child.tag.lower() if isinstance(child.tag, str) else ""
        tail = child.tail
        if tag in _STEP_BLOCK_TAGS:
            blocks.append(child)
            if tail and tail.strip():
                runs.append(_Run(_inline_text(tail)))
            continue
        # Inline element — flatten via _inline_runs through a synthetic
        # wrapper so its text + tail are walked correctly.
        child.tail = None
        wrapper = ET.Element("span")
        wrapper.append(child)
        runs.extend(_inline_runs(state, wrapper))
        if tail:
            runs.append(_Run(_inline_text(tail)))
    # Drop pure-whitespace runs at the ends.
    while runs and not runs[0].text.strip():
        runs.pop(0)
    while runs and not runs[-1].text.strip():
        runs.pop()
    return runs, blocks


def _h_rd_detail(state: _State, el: ET._Element) -> None:
    summary = el.get("summary") or ""
    if summary:
        state.doc.add_heading(summary, level=3)
    render_children(state, el)


def _h_rd_checklist(state: _State, el: ET._Element) -> None:
    for task in el:
        if not (isinstance(task.tag, str) and task.tag.lower() == "rd-task"):
            continue
        done = task.get("done") is not None
        marker = "☑ " if done else "☐ "
        runs = _inline_runs(state, task)
        p = state.doc.add_paragraph(style="List Bullet")
        p.add_run(marker)
        _emit_runs(p, runs)
        meta = []
        if task.get("assignee"):
            meta.append(f"@{task.get('assignee')}")
        if task.get("due"):
            meta.append(f"due {task.get('due')}")
        if meta:
            r = p.add_run("  " + " ".join(meta))
            r.italic = True
            r.font.size = Pt(8)


def _h_rd_diagram(state: _State, el: ET._Element) -> None:
    text = _dedent(_element_source(el))
    lang = (el.get("lang") or "").strip().lower()
    if not lang:
        # Without a lang we can't talk to Kroki; emit the source as a
        # plain code block so the content still travels.
        _emit_code(state, text, lang="text")
        return
    _render_diagram(state, text, kind=lang)


def _render_diagram(state: _State, text: str, *, kind: str) -> None:
    if not text.strip():
        return
    if state.render_diagrams:
        png = render_to_png(text, kind=kind, endpoint=state.diagram_endpoint)  # type: ignore[arg-type]
        if png is not None:
            state.doc.add_picture(BytesIO(png), width=Inches(6.0))
            state.diagrams_rendered += 1
            return
        state.diagrams_failed += 1
    _emit_code(state, text, lang=kind)


def _h_rd_toc(state: _State, el: ET._Element) -> None:
    chapters = [c for c in el if isinstance(c.tag, str) and c.tag.lower() == "rd-chapter"]
    if not chapters:
        state.record_dropped("rd-toc")
        return
    if state.toc_emitted:
        # The same rd-toc block is duplicated across every chapter of a book
        # (required for in-browser nav). One copy in the docx is plenty.
        return
    title = el.get("title") or "Contents"
    state.doc.add_heading(title, level=2)
    _emit_chapter_list(state, chapters, depth=0)
    state.toc_emitted = True


def _emit_chapter_list(state: _State, chapters, depth: int) -> None:
    for ch in chapters:
        title = _chapter_text(ch)
        href = ch.get("href")
        if title or href:
            style_level = min(depth, 2)
            style = ["List Bullet", "List Bullet 2", "List Bullet 3"][style_level]
            p = state.doc.add_paragraph(style=style)
            if href and title:
                _emit_runs(p, [_Run(title, hyperlink=href, underline=True)])
            elif href:
                _emit_runs(p, [_Run(href, hyperlink=href, underline=True)])
            else:
                r = p.add_run(title)
                r.bold = True
        nested = [c for c in ch if isinstance(c.tag, str) and c.tag.lower() == "rd-chapter"]
        if nested:
            _emit_chapter_list(state, nested, depth + 1)


def _chapter_text(node: ET._Element) -> str:  # noqa: SLF001
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


def _h_rd_decision(state: _State, el: ET._Element) -> None:
    status = el.get("status") or "proposed"
    id_ = el.get("id") or ""
    title = el.get("title") or ""
    date = el.get("date") or ""
    deciders = el.get("deciders") or ""
    head = " — ".join(b for b in (id_, title) if b) or "Decision"
    state.doc.add_heading(head, level=2)
    p = state.add_paragraph()
    r = p.add_run(f"Status: {status}")
    r.bold = True
    if date or deciders:
        p2 = state.add_paragraph()
        bits = []
        if date:
            bits.append(f"Date: {date}")
        if deciders:
            bits.append(f"Deciders: {deciders}")
        r2 = p2.add_run("  ·  ".join(bits))
        r2.italic = True
    render_children(state, el)


def _h_rd_pros_cons(state: _State, el: ET._Element) -> None:
    # `rd-cols` linearises in DOCX (Confluence import doesn't preserve
    # multi-column Word layouts); pros-cons follows the same convention.
    # We emit two stacked sections — "✓ Pros" with a bulleted list, then
    # "✗ Cons" with a bulleted list. Items aren't paired by position, so
    # asymmetric lists no longer produce empty cells.
    pros_title = el.get("pros-title") or "Pros"
    cons_title = el.get("cons-title") or "Cons"
    pros = [c for c in el if isinstance(c.tag, str) and c.tag.lower() == "rd-pro"]
    cons = [c for c in el if isinstance(c.tag, str) and c.tag.lower() == "rd-con"]
    for items, glyph, heading in (
        (pros, "✓", pros_title),
        (cons, "✗", cons_title),
    ):
        if not items:
            continue
        state.doc.add_heading(f"{glyph} {heading}", level=3)
        for item in items:
            text = _flatten_inline(state, item).strip()
            if not text:
                continue
            p = state.doc.add_paragraph(style="List Bullet")
            p.add_run(text)


def _h_rd_compare(state: _State, el: ET._Element) -> None:
    headers = [h.strip() for h in (el.get("headers") or "").split(",")]
    rows = [r for r in el if isinstance(r.tag, str) and r.tag.lower() == "rd-row-cells"]
    if not headers and not rows:
        return
    cols = len(headers) + 1 if headers else max((len([c for c in r if isinstance(c.tag, str) and c.tag.lower() == "rd-cell"]) for r in rows), default=0) + 1
    if cols < 2:
        return
    table = state.doc.add_table(rows=1 + len(rows), cols=cols)
    table.style = "Table Grid"
    _fill_row(state, table.rows[0], [""] + headers, bold=True)
    for i, r in enumerate(rows, start=1):
        label = r.get("label") or ""
        cells = [c for c in r if isinstance(c.tag, str) and c.tag.lower() == "rd-cell"]
        values = [_flatten_inline(state, c).strip() for c in cells]
        _fill_row(state, table.rows[i], [label] + values + [""] * (cols - 1 - len(values)))


def _h_rd_rubric(state: _State, el: ET._Element) -> None:
    options = [o.strip() for o in (el.get("options") or "").split(",")]
    title = el.get("title") or ""
    scale = float(el.get("scale") or 5)  # noqa: F841 — preserved for clarity
    criteria = [c for c in el if isinstance(c.tag, str) and c.tag.lower() == "rd-criterion"]
    if not options or not criteria:
        return
    if title:
        state.doc.add_heading(title, level=3)
    cols = 2 + len(options)  # criterion + weight + per-option scores
    table = state.doc.add_table(rows=1 + len(criteria) + 1, cols=cols)
    table.style = "Table Grid"
    _fill_row(state, table.rows[0], ["Criterion", "Weight"] + options, bold=True)
    totals = [0.0] * len(options)
    weights_sum = 0.0
    for i, crit in enumerate(criteria, start=1):
        label = crit.get("label") or ""
        weight = float(crit.get("weight") or 1)
        scores = [s for s in crit if isinstance(s.tag, str) and s.tag.lower() == "rd-score"]
        score_vals: list[str] = []
        for j, sc in enumerate(scores[: len(options)]):
            try:
                val = float(sc.get("value") or 0)
            except ValueError:
                val = 0.0
            totals[j] += val * weight
            score_vals.append(sc.get("value") or "")
        score_vals += [""] * (len(options) - len(score_vals))
        weights_sum += weight
        _fill_row(state, table.rows[i], [label, str(weight)] + score_vals)
    total_row = ["Total", f"{weights_sum:g}"]
    for v in totals:
        total_row.append(f"{v:g}")
    _fill_row(state, table.rows[-1], total_row, bold=True)


def _h_rd_api(state: _State, el: ET._Element) -> None:
    method = el.get("method") or ""
    path = el.get("path") or ""
    title = el.get("title") or ""
    auth = el.get("auth") or ""
    head = f"{method} {path}".strip()
    if title:
        head = f"{title} — {head}" if head else title
    if head:
        state.doc.add_heading(head, level=3)
    if auth:
        p = state.add_paragraph()
        r = p.add_run(f"Auth: {auth}")
        r.italic = True
    params = [c for c in el if isinstance(c.tag, str) and c.tag.lower() == "rd-param"]
    responses = [c for c in el if isinstance(c.tag, str) and c.tag.lower() == "rd-response"]
    if params:
        state.doc.add_heading("Parameters", level=4)
        table = state.doc.add_table(rows=1 + len(params), cols=5)
        table.style = "Table Grid"
        _fill_row(state, table.rows[0], ["Name", "In", "Type", "Required", "Description"], bold=True)
        for i, p in enumerate(params, start=1):
            desc = _flatten_inline(state, p).strip()
            _fill_row(
                state,
                table.rows[i],
                [
                    p.get("name") or "",
                    p.get("in") or "query",
                    p.get("type") or "",
                    "yes" if p.get("required") is not None else "",
                    desc,
                ],
            )
    if responses:
        state.doc.add_heading("Responses", level=4)
        table = state.doc.add_table(rows=1 + len(responses), cols=3)
        table.style = "Table Grid"
        _fill_row(state, table.rows[0], ["Status", "Type", "Description"], bold=True)
        for i, resp in enumerate(responses, start=1):
            desc = _flatten_inline(state, resp).strip()
            _fill_row(
                state,
                table.rows[i],
                [resp.get("status") or "", resp.get("type") or "", desc],
            )


def _h_rd_references(state: _State, el: ET._Element) -> None:
    # rd-references placement marker — emit collected refs here if any.
    _emit_references(state, title=el.get("title") or "References")
    state._refs_emitted = True  # type: ignore[attr-defined]


def _h_rd_ref(state: _State, el: ET._Element) -> None:
    _collect_ref(state, el)


def _h_rd_cite(state: _State, el: ET._Element) -> None:
    # Top-level rd-cite is unusual but handle it gracefully.
    key = el.get("key") or ""
    if key and key not in state.cite_order:
        state.cite_order.append(key)


def _h_rd_chapter(state: _State, el: ET._Element) -> None:
    # Inside rd-toc only — caller handles it.
    pass
