"""rd-* component handlers for the Confluence storage-format converter.

Confluence's storage format gives us native cloud-editor elements for
layouts, panels, decisions, status lozenges, code, expand/collapse, and
tables — which lets the publish path keep richdoc documents *editable*
in the Confluence UI after the push, with no "legacy content" warnings.

Mapping cheat-sheet (long form lives in references/publish.md):

- rd-cols / rd-pros-cons        → native `<ac:layout-section>` (page layout)
- rd-card / rd-stat             → modern Panel (`<ac:adf-node type="panel">`)
- rd-callout / rd-banner        → modern Panel (same form as cards)
- rd-decision                   → modern Decision (`<ac:adf-node type="decision-list">`)
- rd-badge                      → native Status macro (coloured lozenge)
- rd-kv                         → modern table with `data-layout` + col widths
- rd-code / rd-diff / rd-shell  → native `code` macro
- rd-detail                     → native `expand` macro (still collapsible)
- rd-math / rd-diagram          → Kroki PNG → page attachment → <ac:image>
- rd-toc                        → inline Contents block in book mode, dropped otherwise
- everything else               → plain XHTML built from the relevant attributes
"""

from __future__ import annotations

import re
import uuid

import lxml.etree as ET

from ...export.common.chart_data import parse_chart
from ...export.common.diagrams import render_to_png
from .converter import (
    TocEntry,
    _Converter,
    _element_source,
    dedent,
    xml_attr,
    xml_escape,
)
from .handlers_plain import emit_code_macro
from .math import render_math_png


# Map richdoc callout/banner types onto modern Panel `panel-type` values.
_PANEL_TYPE_CALLOUT = {
    "info":    "info",
    "note":    "note",
    "tldr":    "note",
    "success": "success",
    "warn":    "warning",
    "danger":  "error",
}

# Map richdoc rd-card / rd-stat accent onto modern Panel `panel-type`.
_PANEL_TYPE_CARD = {
    "":        "note",   # no accent
    "default": "note",
    "info":    "info",
    "success": "success",
    "warn":    "warning",
    "danger":  "error",
    "note":    "note",
}

# Map rd-decision `status` onto the modern Decision element's state and
# the inline status-lozenge label / colour.
_DECISION_STATE = {
    "accepted":   ("DECIDED",   "Green",  "Accepted"),
    "rejected":   ("UNDECIDED", "Red",    "Rejected"),
    "proposed":   ("UNDECIDED", "Blue",   "Proposed"),
    "superseded": ("UNDECIDED", "Purple", "Superseded"),
}

# Map rd-badge variants onto the native Status macro `colour` value.
# `None` falls through to the default (Grey).
_BADGE_COLOUR = {
    "":        None,
    "default": None,
    "muted":   None,
    "info":    "Blue",
    "success": "Green",
    "warn":    "Yellow",
    "danger":  "Red",
}


# ---------------------------------------------------------------------------
# Page / hero / sections / callouts
# ---------------------------------------------------------------------------


def _h_rd_page(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    c.render_children(el)


def _h_rd_hero(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-hero → <h1> + meta paragraphs. Body children are rendered as
    peer-level chunks so any rd-cols inside the hero can bubble up to
    the page-body top level (where Confluence requires layout-sections
    to live).
    """
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
    c.render_children(el)


def _h_rd_section(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-section → <h2> + peer-level body children.

    Renders children as peers (not inside a wrapped sub-buffer) so any
    rd-cols nested in the section emits its layout-section at the
    page-body top level.
    """
    title = (el.get("title") or "").strip()
    if title:
        c.write_block(f"<h2>{xml_escape(title)}</h2>")
    c.render_children(el)


def _h_rd_card(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-card → modern Panel with the card's accent mapped to a
    `panel-type`. Title becomes a bold first paragraph inside the panel
    body so it visually stands out without resorting to a heading.
    """
    title = (el.get("title") or "").strip()
    accent = (el.get("accent") or "").strip().lower()
    panel_type = _PANEL_TYPE_CARD.get(accent, "note")
    body = c.render_block_inner_wrapped(el)
    if not title and not body:
        return
    _emit_panel(c, panel_type=panel_type, title=title or None, body=body)


def _h_rd_cols(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-cols → native `<ac:layout-section>` at page-body top level.

    Confluence's modern editor renders layout-sections as full-width
    multi-column slots. They are only legal as direct children of
    `<ac:layout>` at the body root, so nested rd-cols (inside a panel /
    expand / card / detail) falls back to a linearised rendering: each
    column is emitted as a peer block-level chunk.
    """
    columns: list[str] = []
    for child in el:
        if not isinstance(child.tag, str):
            continue
        sub = c._spawn_sub()  # noqa: SLF001
        sub.render(child)
        rendered = "".join(sub.chunks).strip()
        c._merge_counters(sub)  # noqa: SLF001
        if rendered:
            columns.append(rendered)
    if not columns:
        return
    if c.in_isolated_body or len(columns) == 1:
        # Inside a sub-buffer or single column — just write the columns
        # back-to-back. Single-column rd-cols also takes this path; a
        # one-cell layout-section is needless editor chrome.
        for col in columns:
            c.write_block(col)
        return
    for chunk in _chunk_columns(columns):
        _emit_layout_section(c, chunk, ac_type=_layout_type(len(chunk)))


def _emit_layout_section(
    c: _Converter,
    columns: list[str],
    *,
    ac_type: str,
) -> None:
    cells = "".join(
        f"<ac:layout-cell>{col}</ac:layout-cell>" for col in columns
    )
    c.write_block(
        f'<ac:layout-section ac:type="{xml_attr(ac_type)}" ac:breakout-mode="default">'
        f"{cells}"
        "</ac:layout-section>"
    )


def _layout_type(n: int) -> str:
    """Map column count to the `<ac:layout-section ac:type>` name.

    Confluence Cloud layout-sections accept a fixed cell count per
    type: `single` (1), `two_equal` (2), `three_equal` (3). Any larger
    count is split into multiple sections by `_chunk_columns` before
    this function is called.
    """
    if n <= 1:
        return "single"
    if n == 2:
        return "two_equal"
    return "three_equal"


def _chunk_columns(columns: list[str]) -> list[list[str]]:
    """Split N columns into chunks of ≤3, preferring symmetric splits.

    Confluence Cloud caps the layout-section cell count at 3 per
    section, but richdoc lets authors write rd-cols n="4" / n="5" /
    n="6". The cleanest visual is to break those into multiple
    consecutive sections instead of overflowing the cell limit:

    - n=4  → 2 + 2  (two `two_equal` sections)
    - n=5  → 3 + 2
    - n=6  → 3 + 3
    - n=7  → 3 + 2 + 2  (avoid a stranded 1-cell row at the end)
    - n=8  → 3 + 3 + 2
    - n≥9 → chunk by 3 from the front, rebalance the tail when the
      final chunk would be size 1
    """
    n = len(columns)
    if n == 0:
        return []
    if n == 4:
        return [columns[:2], columns[2:]]
    if n == 5:
        return [columns[:3], columns[3:]]
    chunks: list[list[str]] = []
    i = 0
    while i < n:
        chunks.append(columns[i : i + 3])
        i += 3
    # If the last chunk has just 1 cell, rebalance the last two chunks
    # so we don't leave a stranded full-width tile at the end.
    if len(chunks) >= 2 and len(chunks[-1]) == 1:
        tail = chunks.pop()[0]
        prev = chunks.pop()
        chunks.append(prev[:-1])
        chunks.append([prev[-1], tail])
    return chunks


def _emit_panel(
    c: _Converter,
    *,
    panel_type: str,
    title: str | None,
    body: str,
) -> None:
    """Emit a modern Panel element (the cloud-editor `/panel` form)."""
    parts: list[str] = []
    if title:
        parts.append(f"<p><strong>{xml_escape(title)}</strong></p>")
    if body:
        parts.append(body)
    content = "".join(parts) or "<p>&#160;</p>"
    c.write_block(
        "<ac:adf-extension>"
        '<ac:adf-node type="panel">'
        f'<ac:adf-attribute key="panel-type">{xml_attr(panel_type)}</ac:adf-attribute>'
        f"<ac:adf-content>{content}</ac:adf-content>"
        "</ac:adf-node>"
        "</ac:adf-extension>"
    )


def _h_rd_banner(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    panel_type = _PANEL_TYPE_CALLOUT.get(type_, "info")
    attr_message = (el.get("message") or "").strip()
    if attr_message:
        body = f"<p>{xml_escape(attr_message)}</p>"
    else:
        inner = c.render_inline(el).strip()
        if not inner:
            return
        body = f"<p>{inner}</p>"
    _emit_panel(c, panel_type=panel_type, title=None, body=body)


def _h_rd_callout(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    type_ = (el.get("type") or "info").lower()
    title = (el.get("title") or "").strip()
    if not title and type_ == "tldr":
        title = "TL;DR"
    panel_type = _PANEL_TYPE_CALLOUT.get(type_, "info")
    body = c.render_block_inner_wrapped(el)
    if not body and not title:
        return
    _emit_panel(c, panel_type=panel_type, title=title or None, body=body)


# ---------------------------------------------------------------------------
# Information blocks
# ---------------------------------------------------------------------------


def _h_rd_kv(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Render rd-kv as a modern Confluence table with a narrow, bold key
    column.

    Three details matter for the cloud editor's render quality:

    1. `data-layout="default"` keeps the modern table chrome (resize
       handles, "highlight first column" toggle), so the table doesn't
       drop back to the legacy renderer.
    2. An explicit `<colgroup>` with a 200px first column stops Confluence
       from giving the key column half the table width.
    3. The `<th>` body is `<p><strong>...</strong></p>` — matches
       Atlassian's own Decision template normalisation, so the editor
       doesn't warn that the cell isn't a paragraph.

    Inline layouts render the row's children as one inline XML fragment
    (wrapped in a single `<p>` inside the cell); stacked layouts render
    a full block body so paragraphs, lists, and code survive.
    """
    title = (el.get("title") or "").strip()
    layout = (el.get("layout") or "inline").lower()
    rows = [r for r in el if isinstance(r.tag, str) and r.tag.lower() == "rd-row"]
    if title:
        c.write_block(f"<p><strong>{xml_escape(title)}</strong></p>")
    if not rows:
        return
    body_rows: list[str] = []
    for r in rows:
        key = (r.get("key") or "").strip()
        if layout == "stacked":
            value = c.render_block_inner(r).strip()
            value_xml = value or "<p>&#160;</p>"
        else:
            inline = c.render_inline(r).strip()
            value_xml = f"<p>{inline or '&#160;'}</p>"
        body_rows.append(
            "<tr>"
            f"<th><p><strong>{xml_escape(key)}</strong></p></th>"
            f"<td>{value_xml}</td>"
            "</tr>"
        )
    c.write_block(
        '<table data-layout="default">'
        "<colgroup>"
        '<col style="width: 200.0px;" />'
        '<col style="width: 760.0px;" />'
        "</colgroup>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _h_rd_row(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    # Handled inside rd-kv. Loose row → render its children inline.
    c.render_children(el)


def _h_rd_badge(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-badge → native Status macro (coloured lozenge).

    Renders inline so badges nest naturally inside rd-kv `<td>` cells,
    prose paragraphs, and decision-item titles. The label falls back to
    the variant name (or the literal string "badge") when the rd-badge
    has no inline text — mirrors the prior `[label]` behaviour.
    """
    variant = (el.get("variant") or "").strip().lower()
    label = c.render_inline(el).strip() or variant or "badge"
    c.write(_status_macro(label, _BADGE_COLOUR.get(variant)))


def _status_macro(label: str, colour: str | None) -> str:
    """Build a Confluence native Status macro storage fragment.

    `colour` accepts Atlassian's case-sensitive palette names
    (Grey / Blue / Red / Yellow / Green / Purple). `None` omits the
    parameter, which the editor renders as the default grey "Not
    started" lozenge.
    """
    colour_xml = (
        f'<ac:parameter ac:name="colour">{xml_attr(colour)}</ac:parameter>'
        if colour
        else ""
    )
    # The label inside `title` is plain text (the macro renders it as
    # the lozenge label) — strip any HTML the inline renderer produced
    # so we don't end up with markup leaking into the lozenge title.
    plain = _strip_inline_html(label)
    return (
        '<ac:structured-macro ac:name="status" ac:schema-version="1">'
        f'<ac:parameter ac:name="title">{xml_escape(plain)}</ac:parameter>'
        f"{colour_xml}"
        "</ac:structured-macro>"
    )


_INLINE_HTML_RE = re.compile(r"<[^>]+>")


def _strip_inline_html(text: str) -> str:
    """Drop simple inline tags from `text`. The status macro `title`
    parameter is plain text — unwrapping `<strong>` / `<em>` here keeps
    a status lozenge readable when the source rd-badge wrapped its body
    in formatting tags.
    """
    return _INLINE_HTML_RE.sub("", text).strip()


def _h_rd_stat(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """rd-stat → modern Panel (neutral `note` type) styled as a stat tile.

    Inside the panel we emit the value as a bold paragraph and the label
    + trend / delta as a subdued line below — same content as before, but
    wrapped in a panel so a row of rd-stats inside an rd-cols renders as
    a row of dashboard tiles.
    """
    value = (el.get("value") or "").strip()
    label = (el.get("label") or "").strip()
    trend = (el.get("trend") or "").strip()
    delta = (el.get("delta") or "").strip()
    extras: list[str] = []
    if trend:
        glyph = {"up": "▲", "down": "▼", "flat": "→"}.get(trend, trend)
        extras.append(glyph)
    if delta:
        extras.append(delta)
    body_parts: list[str] = []
    if value:
        body_parts.append(f"<p><strong>{xml_escape(value)}</strong></p>")
    meta_bits: list[str] = []
    if label:
        meta_bits.append(xml_escape(label))
    if extras:
        meta_bits.append(f"<em>({xml_escape(' '.join(extras))})</em>")
    if meta_bits:
        body_parts.append("<p>" + " ".join(meta_bits) + "</p>")
    body = "".join(body_parts)
    if not body:
        return
    _emit_panel(c, panel_type="note", title=None, body=body)
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
        header_cells.append("&#160;")
    body_rows: list[str] = []
    for r in rows:
        while len(r) < width:
            r.append("&#160;")
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
                cells.append("&#160;")
        rows.append([xml_escape(f"{label} (×{weight:g})"), *cells])
    head_cells = ["&#160;", *[xml_escape(o) for o in options]]
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
    is_inline = display == "inline"
    source = dedent(_element_source(el))
    if not source.strip():
        return
    if not c.render_math:
        # Plain-text fallback: italic source.
        if is_inline:
            c.write(f"<em>{xml_escape(source)}</em>")
        else:
            c.write_block(f"<p><em>{xml_escape(source)}</em></p>")
        return
    png = render_math_png(source, endpoint=c.diagram_endpoint)
    if png is None:
        c.math_failed += 1
        if is_inline:
            c.write(f"<em>{xml_escape(source)}</em>")
        else:
            c.write_block(f"<p><em>{xml_escape(source)}</em></p>")
        return
    c.math_rendered += 1
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
        return
    c.write_block(f"<p>{token}</p>")
    _emit_source_expand(c, source, lang="latex", summary="Show LaTeX source")


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
    _emit_source_expand(c, source, lang=lang, summary=f"Show {lang} source")


def _emit_source_expand(
    c: _Converter,
    source: str,
    *,
    lang: str,
    summary: str,
) -> None:
    """Emit the rendered-block source inside a collapsible `expand` macro.

    Used by `rd-math` (block) and `rd-diagram` so the published page leads
    with the rendered image but still keeps the original source
    accessible — a click on the expand reveals the LaTeX / Mermaid /
    PlantUML / D2 text, ready for editing without going back to the
    richdoc HTML.
    """
    if not source.strip():
        return
    sub = c._spawn_sub()  # noqa: SLF001
    emit_code_macro(sub, source, lang=lang, title=None)
    c._merge_counters(sub)  # noqa: SLF001
    body = "".join(sub.chunks)
    c.write_block(
        '<ac:structured-macro ac:name="expand">'
        '<ac:parameter ac:name="title">'
        f"{xml_escape(summary)}"
        "</ac:parameter>"
        f"<ac:rich-text-body>{body}</ac:rich-text-body>"
        "</ac:structured-macro>"
    )


# ---------------------------------------------------------------------------
# TOC / chapters / icons
# ---------------------------------------------------------------------------


def _h_rd_toc(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Render rd-toc as an inline "Contents" block of cross-page links.

    The pipeline builds the TocEntry tree from the entry chapter's
    `<rd-toc>` once per publish and passes it to every chapter walk, so
    each chapter shows the same Contents tree (mirroring the rd-toc
    sidebar in the HTML book). For single-file documents there is no
    `toc_entries` payload and we drop the element as before.
    """
    entries = c.toc_entries
    if not entries:
        c.dropped.append("rd-toc")
        return
    title = (el.get("title") or "Contents").strip()
    body = _render_toc_tree(c, entries)
    if not body:
        c.dropped.append("rd-toc")
        return
    c.write_block(f"<p><strong>{xml_escape(title)}</strong></p>")
    c.write_block(body)


def _render_toc_tree(c: _Converter, entries: list[TocEntry]) -> str:  # noqa: SLF001
    items: list[str] = []
    for e in entries:
        label = xml_escape(e.title or "Untitled")
        url = (
            c.cross_page_links.get(str(e.target_rel))
            or c.cross_page_links.get(e.target_rel.as_posix())
            if e.target_rel is not None
            else None
        )
        if e.target_rel is not None and e.target_rel == c.chapter_rel:
            head = f"<strong>{label}</strong>"  # active chapter — don't self-link
        elif url:
            head = f'<a href="{xml_attr(url)}">{label}</a>'
        elif e.href:
            # External href or unresolved — preserve as a plain link.
            head = f'<a href="{xml_attr(e.href)}">{label}</a>'
        else:
            head = f"<strong>{label}</strong>"  # group header
        nested = _render_toc_tree(c, list(e.children)) if e.children else ""
        items.append(f"<li>{head}{nested}</li>")
    return f"<ul>{''.join(items)}</ul>" if items else ""


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
    """Render rd-decision as a modern Decision element (`/decision`).

    The decision-list contains a single decision-item whose inline
    content is the bold ID + title, followed by the status lozenge and
    date / deciders meta. The body paragraphs are emitted as peer-level
    siblings of the decision-list — not nested inside it — so multiple
    consecutive rd-decisions each get their own decision marker without
    the body content disappearing into the inline title slot.
    """
    status_raw = (el.get("status") or "proposed").strip().lower()
    state, colour, status_label = _DECISION_STATE.get(
        status_raw, ("UNDECIDED", "Grey", status_raw.title() or "Pending"),
    )
    id_ = (el.get("id") or "").strip()
    title = (el.get("title") or "").strip()
    date = (el.get("date") or "").strip()
    deciders = (el.get("deciders") or "").strip()
    head_bits = [b for b in (id_, title) if b]
    label = ": ".join(head_bits) if head_bits else "Decision"
    status_xml = _status_macro(status_label, colour)
    meta_extras = " · ".join([b for b in (date, deciders) if b])
    inline_parts = [f"<strong>{xml_escape(label)}</strong>", status_xml]
    if meta_extras:
        inline_parts.append(xml_escape(meta_extras))
    inline = " · ".join(inline_parts)
    list_id = uuid.uuid4().hex
    item_id = uuid.uuid4().hex
    c.write_block(
        "<ac:adf-extension>"
        '<ac:adf-node type="decision-list">'
        f'<ac:adf-attribute key="local-id">{list_id}</ac:adf-attribute>'
        "<ac:adf-content>"
        '<ac:adf-node type="decision-item">'
        f'<ac:adf-attribute key="local-id">{item_id}</ac:adf-attribute>'
        f'<ac:adf-attribute key="state">{state}</ac:adf-attribute>'
        f"<ac:adf-content>{inline}</ac:adf-content>"
        "</ac:adf-node>"
        "</ac:adf-content>"
        "</ac:adf-node>"
        "</ac:adf-extension>"
    )
    inner = c.render_block_inner_wrapped(el)
    if inner:
        c.write_block(inner)


def _h_rd_pros_cons(c: _Converter, el: ET._Element) -> None:  # noqa: SLF001
    """Render rd-pros-cons as a two-column `<ac:layout-section>` (or
    linearised when nested in an isolated body).
    """
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
    columns: list[str] = []
    if pros:
        columns.append(
            f"<p><strong>{xml_escape(pros_title)}</strong></p>"
            f"<ul>{''.join(pros)}</ul>"
        )
    if cons:
        columns.append(
            f"<p><strong>{xml_escape(cons_title)}</strong></p>"
            f"<ul>{''.join(cons)}</ul>"
        )
    if not columns:
        return
    if c.in_isolated_body or len(columns) == 1:
        for col in columns:
            c.write_block(col)
        return
    _emit_layout_section(c, columns, ac_type=_layout_type(len(columns)))


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
