"""Confluence storage-format export.

Public surface used by the export CLI:

- `html_to_storage`, `PendingAttachment`, `StorageResult`, `TocEntry`
  — offline HTML → Confluence storage XML converter (converter.py)
- `BundleManifest`, `BundlePage`, `BundleAttachment`, `BundleLink`,
  `write_bundle`, `read_bundle`           — bundle dataclasses + IO (bundle.py)
- `ConfluenceExportPlan`, `ConfluenceExportResult`, `export_bundle`
                                          — orchestration (pipeline.py)

This subpackage is intentionally network-free. Diagram and math rendering
do call out to Kroki, but no Confluence credentials are required. The
generated bundle is published by the separate `confluence` skill.
"""

from .bundle import (
    BUNDLE_SCHEMA,
    BundleAttachment,
    BundleLink,
    BundleManifest,
    BundlePage,
    read_bundle,
    write_bundle,
)
from .converter import (
    PendingAttachment,
    StorageResult,
    TocEntry,
    html_to_storage,
)
from .pipeline import (
    ConfluenceExportPlan,
    ConfluenceExportResult,
    export_bundle,
    page_url_token,
)

__all__ = [
    "BUNDLE_SCHEMA",
    "BundleAttachment",
    "BundleLink",
    "BundleManifest",
    "BundlePage",
    "ConfluenceExportPlan",
    "ConfluenceExportResult",
    "PendingAttachment",
    "StorageResult",
    "TocEntry",
    "export_bundle",
    "html_to_storage",
    "page_url_token",
    "read_bundle",
    "write_bundle",
]
