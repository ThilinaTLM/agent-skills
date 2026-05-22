"""Citation collection and the References-section emitter for DOCX."""

from __future__ import annotations

import lxml.etree as ET

from .state import _State


def _collect_ref(state: _State, el: ET._Element) -> None:
    from .runs import _flatten_inline

    key = el.get("key") or ""
    if not key:
        return
    state.refs_collected[key] = {
        "author": el.get("author") or "",
        "title": el.get("title") or "",
        "url": el.get("url") or "",
        "date": el.get("date") or "",
        "publisher": el.get("publisher") or "",
        "note": _flatten_inline(state, el).strip(),
    }


def _emit_references(state: _State, *, title: str) -> None:
    from .runs import _emit_runs, _Run

    keys: list[str] = []
    seen: set[str] = set()
    for k in state.cite_order:
        if k in state.refs_collected and k not in seen:
            seen.add(k)
            keys.append(k)
    for k in state.refs_collected:
        if k not in seen:
            seen.add(k)
            keys.append(k)
    if not keys:
        return
    state.doc.add_heading(title, level=2)
    for n, key in enumerate(keys, start=1):
        attrs = state.refs_collected[key]
        parts = [f"[{n}]"]
        if attrs.get("author"):
            parts.append(attrs["author"] + ".")
        if attrs.get("title"):
            parts.append(f'"{attrs["title"]}."')
        if attrs.get("publisher"):
            parts.append(attrs["publisher"] + ".")
        if attrs.get("date"):
            parts.append(attrs["date"] + ".")
        text = " ".join(parts)
        p = state.add_paragraph()
        p.add_run(text)
        if attrs.get("url"):
            p.add_run(" ")
            _emit_runs(p, [_Run(attrs["url"], hyperlink=attrs["url"], underline=True)])
        if attrs.get("note"):
            p2 = state.add_paragraph()
            rr = p2.add_run(attrs["note"])
            rr.italic = True


def _finalise(state: _State) -> None:
    # Auto-emit references if none of the rd-references markers placed them.
    if state.refs_collected and not state.refs_emitted:
        _emit_references(state, title="References")
