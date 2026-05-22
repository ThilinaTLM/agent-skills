"""DOCX export package.

Public entry points:
- `html_to_docx(source, *, base_dir, …) -> DocxResult` — single HTML file.
- `chapters_to_docx(chapters, *, book_base, …) -> DocxResult` — book mode
  (every chapter concatenated into one DOCX with page breaks).

Importing this package registers the handler dispatch table as a side
effect of importing `handler_table`.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from ..book import ChapterFile
from ..common.assets import AssetStore
from . import handler_table  # noqa: F401 — side-effect: build BLOCK_HANDLERS
from .document import new_document
from .references import _finalise
from .state import DocxResult, _State
from .walker import render_source


def html_to_docx(
    source: str,
    *,
    base_dir: Path,
    render_diagrams: bool = True,
    diagram_endpoint: str = "https://kroki.io",
    asset_store: AssetStore | None = None,
) -> DocxResult:
    """Render a single richdoc HTML file to a DOCX byte string."""
    doc = new_document()
    store = asset_store if asset_store is not None else AssetStore()
    state = _State(
        doc=doc,
        asset_store=store,
        base_dir=base_dir,
        render_diagrams=render_diagrams,
        diagram_endpoint=diagram_endpoint,
    )
    render_source(state, source)
    _finalise(state)
    return _serialise(state)


def chapters_to_docx(
    chapters: list[ChapterFile],
    *,
    book_base: Path,
    render_diagrams: bool = True,
    diagram_endpoint: str = "https://kroki.io",
) -> DocxResult:
    """Render a multi-file book into one DOCX. Each chapter starts on a new
    page; the chapter title is emitted as Heading 1."""
    doc = new_document()
    store = AssetStore()
    state = _State(
        doc=doc,
        asset_store=store,
        base_dir=book_base,
        render_diagrams=render_diagrams,
        diagram_endpoint=diagram_endpoint,
    )
    for i, ch in enumerate(chapters):
        if i > 0:
            state.add_page_break()
        # Override base_dir for asset resolution per chapter.
        state.base_dir = ch.path.parent
        render_source(state, ch.html, chapter_title=ch.title)
    state.base_dir = book_base
    _finalise(state)
    return _serialise(state)


def _serialise(state: _State) -> DocxResult:
    buf = BytesIO()
    state.doc.save(buf)
    return DocxResult(
        data=buf.getvalue(),
        dropped=sorted(set(state.dropped)),
        missing=list(state.asset_store.missing),
        diagrams_rendered=state.diagrams_rendered,
        diagrams_failed=state.diagrams_failed,
        images_embedded=state.images_embedded,
    )


__all__ = ["DocxResult", "chapters_to_docx", "html_to_docx"]
