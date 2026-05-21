"""Confluence HTML-import exporter.

Public surface:

- `html_to_confluence_page(source, ...) -> PageResult` — convert one
  HTML document to Confluence-importable HTML plus the queues of
  pending PNG renders.
- `export_confluence(entry, ...) -> ConfluenceExportResult` —
  end-to-end orchestration: discover chapters, walk each, rasterise
  code/math/diagrams, and package everything into a single
  Confluence-importable zip.

Importing this package triggers handler registration as a side effect.
"""

from . import handler_table  # noqa: F401 — side effect: populate HANDLERS
from .converter import (
    PageResult,
    PendingCode,
    PendingDiagram,
    PendingMath,
    html_to_confluence_page,
)
from .pipeline import (
    ConfluenceExportResult,
    export_confluence,
    render_to_bytes,
)

__all__ = [
    "ConfluenceExportResult",
    "PageResult",
    "PendingCode",
    "PendingDiagram",
    "PendingMath",
    "export_confluence",
    "html_to_confluence_page",
    "render_to_bytes",
]
