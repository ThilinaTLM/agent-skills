"""HTML \u2192 Confluence Cloud storage-format XML converter.

The converter walks one parsed richdoc HTML chapter and produces:

- A storage-format XML body string (XHTML + ``<ac:\u2026>`` macros + image
  placeholder tokens) ready for ``POST /pages`` or ``PUT /pages/{id}``.
- A list of ``PendingAttachment`` entries describing every binary that
  has to be uploaded to the page *before* the body becomes valid. Each
  pending entry carries a token (e.g. ``@@ATTACHMENT:abc123@@``) that
  appears verbatim in the storage XML and gets replaced with a real
  ``<ac:image><ri:attachment ri:filename="..."/></ac:image>`` reference
  once the upload completes.

This deferred-binding model lets us:

1. Compose the storage body without making any network call (so
   ``--dry-run`` works fully offline).
2. Upload attachments only once we know the page id (created/updated
   first with a placeholder body, then re-saved after upload). For an
   existing page we upload first then update once.

This module is intentionally thin \u2014 the heavy lifting lives in
sibling modules and the handler-files import what they need from them
directly:

- ``state.py``   : ``_Converter`` state machine + ``HANDLERS`` dispatch table.
- ``xml.py``     : ``xml_escape`` / ``xml_attr`` / ``th_bold`` / ``cdata_safe``.
- ``layout.py``  : ``wrap_in_layout`` and namespace constants.
- ``nav.py``     : ``build_prev_next_nav``.
- ``refs.py``    : ``format_ref_li``.
- ``titles.py``  : ``resolve_title``.

The handler files import directly from those modules; this module
re-exports the most common names (``_Converter``, ``HANDLERS``,
``xml_escape``, ...) so existing ``from .converter import ...`` lines
continue to resolve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...export.common.assets import AssetStore
from ...export.common.text import dedent as _dedent_canonical
from ...export.common.walker import body_of, parse_html
from ...export.common.walker import element_source as _element_source
from ...export.common.walker import inline_text as _inline_text
from .state import HANDLERS, _Converter
from .titles import resolve_title

# Re-exports so existing handler modules can keep importing from
# `.converter` rather than reaching for the split modules.
from .xml import BLOCK_OPENER as _BLOCK_OPENER  # noqa: F401
from .xml import cdata_safe, th_bold, xml_attr, xml_escape

__all__ = [
    "HANDLERS",
    "PendingAttachment",
    "StorageResult",
    "TocEntry",
    "_Converter",
    "_element_source",
    "_inline_text",
    "cdata_safe",
    "dedent",
    "html_to_storage",
    "th_bold",
    "xml_attr",
    "xml_escape",
]


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingAttachment:
    """One binary asset that has to be uploaded to the page."""

    token: str          # placeholder marker in the storage XML
    filename: str       # stable filename used on Confluence
    data: bytes
    mime: str
    align: str = "center"   # "center", "left", "right" \u2014 applied via ac:align
    is_inline: bool = False  # true \u2192 no ac:align, embedded inline


@dataclass(frozen=True)
class TocEntry:
    """One node in a book's rd-toc tree, used by `_h_rd_toc` to render an
    inline Contents block with cross-page links resolved by the pipeline.
    """

    title: str
    href: str | None          # original href as written in rd-chapter, if any
    target_rel: Path | None   # resolved relative to book root, or None for group / external
    children: tuple[TocEntry, ...] = ()


@dataclass
class StorageResult:
    """What the converter produces for one chapter."""

    body: str
    title: str
    pending: list[PendingAttachment] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    math_rendered: int = 0
    math_failed: int = 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def html_to_storage(
    source: str,
    *,
    asset_base: Path,
    include_remote_images: bool = False,
    render_diagrams: bool = True,
    render_math: bool = True,
    diagram_endpoint: str = "https://kroki.io",
    cross_page_links: dict[str, str] | None = None,
    title_override: str | None = None,
    chapter_rel: Path | None = None,
    toc_entries: list[TocEntry] | None = None,
) -> StorageResult:
    """Convert one richdoc HTML chapter into Confluence storage format.

    ``cross_page_links`` maps relative ``.html`` hrefs (as written in
    the source) \u2192 already-known Confluence page URLs, for book chapter
    cross-links. Anything not in the map is preserved as-is and
    rendered by Confluence as a regular external link.

    ``title_override`` is used by the pipeline to inject the resolved
    chapter title from ``<rd-toc>``; when omitted the converter picks
    ``<rd-hero title>`` or the first ``<h1>`` or the doc ``<title>``.

    ``chapter_rel`` is the chapter's path relative to the book root.
    It drives href normalisation in ``_h_a`` so ``./other.html``,
    ``other.html``, and ``../sub/other.html`` all resolve to the same
    chapter. ``None`` in single-file mode.

    ``toc_entries`` is the rd-toc tree shared by every chapter in a
    book. ``_h_rd_toc`` uses it to emit an inline Contents block.
    ``None`` outside book mode \u2014 in which case ``rd-toc`` is dropped
    as before.
    """
    # Ensure dispatch table is populated. Side-effect import only.
    from . import handler_table  # noqa: F401

    root = parse_html(source)
    target = body_of(root)

    conv = _Converter(
        asset_base=asset_base,
        asset_store=AssetStore(),
        include_remote_images=include_remote_images,
        render_diagrams=render_diagrams,
        render_math=render_math,
        diagram_endpoint=diagram_endpoint,
        cross_page_links=dict(cross_page_links or {}),
        chapter_rel=chapter_rel,
        toc_entries=list(toc_entries) if toc_entries else None,
    )
    title = title_override or resolve_title(root)
    conv.render_children(target)

    body = conv.finalise()
    return StorageResult(
        body=body,
        title=title or "Untitled",
        pending=conv.pending,
        dropped=conv.dropped,
        missing=conv.asset_store.missing,
        diagrams_rendered=conv.diagrams_rendered,
        diagrams_failed=conv.diagrams_failed,
        math_rendered=conv.math_rendered,
        math_failed=conv.math_failed,
    )


def dedent(text: str) -> str:
    """Local alias for `export.common.text.dedent`. Kept so handler
    modules can ``from .converter import dedent`` without ricochet.
    """
    return _dedent_canonical(text)
