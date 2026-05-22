"""Book-mode prev/next navigation footer.

In book mode every chapter gets a Contents block at the top (via
``rd-toc``) and a single-row prev/next ``two_equal`` layout-section at
the bottom (this module). Empty side cells render with a ``&nbsp;``
placeholder so the layout-section stays well-formed.

`build_prev_next_nav` is called by `_Converter.finalise` and returns an
empty string in single-file mode or when the current chapter has no
neighbours.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .xml import xml_attr, xml_escape

if TYPE_CHECKING:
    from .converter import TocEntry
    from .state import _Converter

__all__ = ["build_prev_next_nav"]


def _flatten_toc(entries: list[TocEntry]) -> list[TocEntry]:
    """Depth-first flatten of the rd-toc tree, keeping only navigable
    chapters (entries with a resolved ``target_rel``). Group headers
    with no href are skipped because they don't correspond to a page.
    """
    out: list[TocEntry] = []
    for entry in entries:
        if entry.target_rel is not None:
            out.append(entry)
        if entry.children:
            out.extend(_flatten_toc(list(entry.children)))
    return out


def _nav_status_chip(label: str, colour: str) -> str:
    """Build a Confluence native Status macro (lozenge) inline fragment.

    Duplicates the shape of ``handlers_rd._status_macro`` deliberately:
    ``handlers_rd`` imports from this module's parent and importing back
    would re-introduce a cycle. The XML is small and self-contained.
    """
    return (
        '<ac:structured-macro ac:name="status" ac:schema-version="1">'
        f'<ac:parameter ac:name="title">{xml_escape(label)}</ac:parameter>'
        f'<ac:parameter ac:name="colour">{xml_attr(colour)}</ac:parameter>'
        "</ac:structured-macro>"
    )


def build_prev_next_nav(c: _Converter) -> str:
    """Build a single-row ``two_equal`` layout-section with prev / next
    chapter links for the current chapter, based on the flattened
    rd-toc order.

    Layout per cell:
      - left  : ``\u2190 <bold link> [PREVIOUS]`` (Yellow lozenge)
      - right : ``[NEXT] <bold link> \u2192`` (Green lozenge, right-aligned)

    Empty side (first / last chapter) renders an ``<ac:layout-cell>``
    with a single ``<p>\u00a0</p>`` placeholder so the layout-section
    is still well-formed.

    Returns an empty string in single-file mode (no ``toc_entries``),
    when the chapter is not in the toc (defensive fallback), or when
    the chapter has no neighbours.
    """
    if not c.toc_entries or c.chapter_rel is None:
        return ""
    flat = _flatten_toc(list(c.toc_entries))
    idx = next(
        (i for i, e in enumerate(flat) if e.target_rel == c.chapter_rel),
        None,
    )
    if idx is None:
        return ""
    prev = flat[idx - 1] if idx > 0 else None
    nxt = flat[idx + 1] if idx + 1 < len(flat) else None
    if prev is None and nxt is None:
        return ""

    def link_for(entry: TocEntry) -> str:
        url: str | None = None
        if entry.target_rel is not None:
            url = c.cross_page_links.get(
                str(entry.target_rel)
            ) or c.cross_page_links.get(entry.target_rel.as_posix())
        title = xml_escape(entry.title or "Untitled")
        if url:
            return f'<a href="{xml_attr(url)}"><strong>{title}</strong></a>'
        if entry.href:
            return f'<a href="{xml_attr(entry.href)}"><strong>{title}</strong></a>'
        return f"<strong>{title}</strong>"

    if prev is not None:
        prev_chip = _nav_status_chip("PREVIOUS", "Yellow")
        left_cell = (
            "<ac:layout-cell>"
            f"<p>\u2190 {link_for(prev)} {prev_chip}</p>"
            "</ac:layout-cell>"
        )
    else:
        left_cell = "<ac:layout-cell><p>\u00a0</p></ac:layout-cell>"

    if nxt is not None:
        next_chip = _nav_status_chip("NEXT", "Green")
        right_cell = (
            "<ac:layout-cell>"
            f'<p style="text-align: right;">{next_chip} {link_for(nxt)} \u2192</p>'
            "</ac:layout-cell>"
        )
    else:
        right_cell = "<ac:layout-cell><p>\u00a0</p></ac:layout-cell>"

    return (
        '<ac:layout-section ac:type="two_equal">'
        f"{left_cell}{right_cell}"
        "</ac:layout-section>"
    )
