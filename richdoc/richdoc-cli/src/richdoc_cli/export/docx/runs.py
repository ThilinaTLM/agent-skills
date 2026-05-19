"""Inline run flattening for the DOCX exporter.

`_Run` is the format-agnostic intermediate representation produced by
`_inline_runs()` while walking inline-level HTML. `_emit_runs()` writes the
runs onto a python-docx paragraph, and `_add_hyperlink()` is the manual
implementation Word's hyperlink XML python-docx doesn't expose directly.
"""

from __future__ import annotations

from dataclasses import dataclass

import lxml.etree as ET
from docx.oxml.ns import qn

from .state import _State
from .walker import _inline_text


@dataclass
class _Run:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    underline: bool = False
    strike: bool = False
    hyperlink: str | None = None


def _flatten_inline(state: _State, el: ET._Element) -> str:  # noqa: SLF001
    return "".join(r.text for r in _inline_runs(state, el))


def _inline_runs(
    state: _State,
    el: ET._Element,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    underline: bool = False,
    strike: bool = False,
    hyperlink: str | None = None,
) -> list[_Run]:
    """Walk inline content and yield runs with cascaded formatting."""
    from .references import _collect_ref  # noqa: PLC0415 — avoid import cycle

    runs: list[_Run] = []
    if el.text:
        runs.append(
            _Run(
                _inline_text(el.text),
                bold=bold,
                italic=italic,
                code=code,
                underline=underline,
                strike=strike,
                hyperlink=hyperlink,
            )
        )
    for child in el:
        tag = child.tag if isinstance(child.tag, str) else ""
        tag = tag.lower()
        child_bold = bold
        child_italic = italic
        child_code = code
        child_underline = underline
        child_strike = strike
        child_link = hyperlink
        skip_children = False

        if tag in ("strong", "b"):
            child_bold = True
        elif tag in ("em", "i"):
            child_italic = True
        elif tag == "code":
            child_code = True
        elif tag == "u":
            child_underline = True
        elif tag in ("s", "del", "strike"):
            child_strike = True
        elif tag == "a":
            child_link = child.get("href") or hyperlink
            child_underline = True
        elif tag == "br":
            runs.append(_Run("\n"))
            skip_children = True
        elif tag == "rd-footnote":
            mark = child.get("mark") or "*"
            runs.append(_Run(f"[{mark}]", bold=bold, italic=italic))
            # Also flatten body so context isn't lost.
            body = _flatten_inline(state, child).strip()
            if body:
                runs.append(_Run(f" ({body})", italic=True))
            skip_children = True
        elif tag == "rd-cite":
            key = child.get("key") or ""
            if key not in state.cite_order:
                state.cite_order.append(key)
            n = state.cite_order.index(key) + 1
            runs.append(_Run(f"[{n}]", bold=bold, italic=italic))
            skip_children = True
        elif tag == "rd-ref":
            _collect_ref(state, child)
            skip_children = True
        elif tag == "rd-icon":
            label = child.get("label") or ""
            if label:
                runs.append(_Run(label, bold=bold, italic=italic))
            state.record_dropped("rd-icon")
            skip_children = True
        elif tag == "rd-tooltip":
            term = child.get("term") or ""
            body = _flatten_inline(state, child).strip()
            if term and body:
                runs.append(_Run(f"{term} ({body})", bold=bold, italic=italic))
            elif term:
                runs.append(_Run(term, bold=bold, italic=italic))
            skip_children = True
        elif tag == "rd-badge":
            text = _flatten_inline(state, child).strip()
            if text:
                runs.append(_Run(f"[{text}]", bold=True))
            skip_children = True
        elif tag == "img":
            # Inline images render after the current paragraph in DOCX.
            # Flatten alt as a stand-in for inline-flow continuity.
            alt = child.get("alt") or ""
            if alt:
                runs.append(_Run(alt, italic=True))
            skip_children = True
        elif tag in ("script", "style"):
            skip_children = True

        if not skip_children:
            runs.extend(
                _inline_runs(
                    state,
                    child,
                    bold=child_bold,
                    italic=child_italic,
                    code=child_code,
                    underline=child_underline,
                    strike=child_strike,
                    hyperlink=child_link,
                )
            )
        if child.tail:
            runs.append(
                _Run(
                    _inline_text(child.tail),
                    bold=bold,
                    italic=italic,
                    code=code,
                    underline=underline,
                    strike=strike,
                    hyperlink=hyperlink,
                )
            )
    return runs


def _emit_runs(paragraph, runs: list[_Run]) -> None:
    """Append `runs` onto a python-docx paragraph."""
    for run_spec in runs:
        text = run_spec.text
        if not text:
            continue
        if run_spec.hyperlink:
            _add_hyperlink(paragraph, text, run_spec.hyperlink, run_spec)
            continue
        r = paragraph.add_run(text)
        if run_spec.bold:
            r.bold = True
        if run_spec.italic:
            r.italic = True
        if run_spec.underline:
            r.underline = True
        if run_spec.strike:
            r.font.strike = True
        if run_spec.code:
            r.font.name = "Courier New"


def _add_hyperlink(paragraph, text: str, url: str, spec: _Run) -> None:
    """Add a native Word hyperlink — python-docx doesn't expose one directly."""
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = ET.SubElement(paragraph._p, qn("w:hyperlink"))
    hyperlink.set(qn("r:id"), r_id)

    new_run = ET.SubElement(hyperlink, qn("w:r"))
    rpr = ET.SubElement(new_run, qn("w:rPr"))
    color = ET.SubElement(rpr, qn("w:color"))
    color.set(qn("w:val"), "0563C1")
    underline = ET.SubElement(rpr, qn("w:u"))
    underline.set(qn("w:val"), "single")
    if spec.bold:
        ET.SubElement(rpr, qn("w:b"))
    if spec.italic:
        ET.SubElement(rpr, qn("w:i"))
    if spec.code:
        rfonts = ET.SubElement(rpr, qn("w:rFonts"))
        rfonts.set(qn("w:ascii"), "Courier New")
        rfonts.set(qn("w:hAnsi"), "Courier New")
    t = ET.SubElement(new_run, qn("w:t"))
    t.text = text
    t.set(qn("xml:space"), "preserve")


# ---------------------------------------------------------------------------
# <li> splitting (lists nest blocks inside an inline marker)
# ---------------------------------------------------------------------------


def _split_li(li: ET._Element) -> tuple[list, list[ET._Element]]:  # noqa: SLF001
    """Return (inline_parts, nested_block_elements). `inline_parts` is a list
    of (kind, value) where kind is `text` or `element`."""
    parts: list[tuple[str, object]] = []
    if li.text:
        parts.append(("text", li.text))
    blocks: list[ET._Element] = []
    for child in li:
        if isinstance(child.tag, str) and child.tag.lower() in (
            "ul",
            "ol",
            "pre",
            "blockquote",
            "table",
        ):
            blocks.append(child)
            if child.tail:
                parts.append(("text", child.tail))
            continue
        parts.append(("element", child))
        if child.tail:
            parts.append(("text", child.tail))
    return parts, blocks


def _inline_runs_from_parts(state: _State, parts: list[tuple[str, object]]) -> list[_Run]:  # noqa: SLF001
    runs: list[_Run] = []
    for kind, val in parts:
        if kind == "text":
            text = _inline_text(val)  # type: ignore[arg-type]
            if text:
                runs.append(_Run(text))
        else:
            el = val  # type: ignore[assignment]
            tag = el.tag if isinstance(el.tag, str) else ""  # type: ignore[union-attr]
            tag = tag.lower()
            wrapper = ET.Element("span")  # synthetic parent
            wrapper.append(el)  # type: ignore[arg-type]
            wrapper.remove(el)  # type: ignore[arg-type]
            # Just call _inline_runs treating the element as a one-shot tree.
            tmp = ET.Element("span")
            tmp.append(el)  # type: ignore[arg-type]
            runs.extend(_inline_runs(state, tmp))
            # _inline_runs uses tail; clear it so caller doesn't double-emit.
            el.tail = None  # type: ignore[union-attr]
    return runs
