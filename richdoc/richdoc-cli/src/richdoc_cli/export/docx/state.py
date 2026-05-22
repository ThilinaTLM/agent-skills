"""Walker state for the DOCX exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from docx.document import Document as DocumentT
from docx.enum.text import WD_BREAK

from ..common.assets import AssetStore


@dataclass
class DocxResult:
    """Outcome of a single docx render."""

    data: bytes
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    images_embedded: int = 0


@dataclass
class _State:
    doc: DocumentT
    asset_store: AssetStore
    base_dir: Path
    render_diagrams: bool
    diagram_endpoint: str
    # Bookkeeping that surfaces in the JSON envelope.
    dropped: list[str] = field(default_factory=list)
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    images_embedded: int = 0
    # Stack of (list_kind, depth) for nested <ul>/<ol>.
    list_stack: list[tuple[str, int]] = field(default_factory=list)
    # Citation registry.
    cite_counter: int = 0
    cite_order: list[str] = field(default_factory=list)
    refs_collected: dict[str, dict[str, str]] = field(default_factory=dict)
    refs_emitted: bool = False
    # True once an rd-toc has been rendered — subsequent ones (shared TOC in
    # every chapter of a book) are skipped.
    toc_emitted: bool = False

    # ---- writers ---------------------------------------------------------

    def add_paragraph(self, text: str = "", style: str | None = None):
        p = self.doc.add_paragraph(style=style) if style else self.doc.add_paragraph()
        if text:
            p.add_run(text)
        return p

    def add_page_break(self) -> None:
        p = self.doc.add_paragraph()
        p.add_run().add_break(WD_BREAK.PAGE)

    def record_dropped(self, tag: str) -> None:
        self.dropped.append(tag)
