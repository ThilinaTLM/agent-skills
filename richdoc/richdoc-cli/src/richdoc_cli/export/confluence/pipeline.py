"""Offline orchestration for ``richdoc export confluence``.

Walks a single richdoc HTML file or a whole book and produces a
self-contained on-disk bundle (see ``bundle.py``) that the separate
``confluence`` skill can publish later.

This module never opens a network socket for Confluence; the only
remote calls are the Kroki diagram/math renders performed by the
converter itself, gated on ``--no-render-*`` flags.

Cross-page link handling
------------------------

The converter's ``cross_page_links`` parameter normally takes a dict of
*resolved Confluence URLs* keyed by chapter relative path. The publisher
populates that map only after creating each page. Offline, we don't
have URLs yet — but the converter doesn't actually care what the value
is, it just substitutes the dict value into the rendered ``<a href>``.

So instead of URLs, we pass **opaque page-URL tokens**:

    @@RICHDOC_PAGE_URL:<posix-key>@@

The token survives unchanged into the bundle's storage XML and is
replaced at publish time by the consumer. The manifest records every
token along with its target chapter key so the consumer can index the
substitutions without re-parsing the XML.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import lxml.etree as ET
import lxml.html as LH

from ..book import ChapterFile, discover_chapters
from ..common.href import is_external_href
from ..common.titles import chapter_label as _chapter_label
from .bundle import (
    BUNDLE_SCHEMA,
    BundleAttachment,
    BundleLink,
    BundleManifest,
    BundlePage,
    BundleWriteResult,
    PendingBundlePage,
    safe_page_filename,
    write_bundle,
)
from .converter import (
    PendingAttachment,
    StorageResult,
    TocEntry,
    html_to_storage,
)

if TYPE_CHECKING:  # pragma: no cover
    pass


PAGE_URL_TOKEN_PREFIX = "@@RICHDOC_PAGE_URL:"
PAGE_URL_TOKEN_SUFFIX = "@@"


def page_url_token(page_key: str) -> str:
    """Build the cross-page link token for a chapter key."""
    return f"{PAGE_URL_TOKEN_PREFIX}{page_key}{PAGE_URL_TOKEN_SUFFIX}"


_PAGE_URL_TOKEN_RE = re.compile(
    re.escape(PAGE_URL_TOKEN_PREFIX) + r"(?P<key>[^@]+)" + re.escape(PAGE_URL_TOKEN_SUFFIX)
)


# ---------------------------------------------------------------------------
# Plan / result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfluenceExportPlan:
    """The user's intent. Built by the CLI command, consumed by ``export_bundle``."""

    input_path: Path
    output: Path
    no_book: bool = False
    render_diagrams: bool = True
    render_math: bool = True
    diagram_endpoint: str = "https://kroki.io"
    include_remote_images: bool = False
    force: bool = False


@dataclass
class ConfluenceExportResult:
    write: BundleWriteResult
    manifest: BundleManifest
    book: bool
    pages: list[BundlePage]
    attachments: int
    diagrams_rendered: int
    diagrams_failed: int
    math_rendered: int
    math_failed: int
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def export_bundle(plan: ConfluenceExportPlan) -> ConfluenceExportResult:
    """Render ``plan.input_path`` into a Confluence storage bundle."""
    discovery = discover_chapters(plan.input_path)
    chapters = discovery.chapters if not plan.no_book else discovery.chapters[:1]
    is_book = discovery.is_book and not plan.no_book

    if is_book:
        parent_map, toc_entries = _build_toc_structures(plan.input_path, chapters)
    else:
        parent_map, toc_entries = (
            {chapters[0].relative: None} if chapters else {},
            None,
        )

    # Map chapter rel-path -> page_key (POSIX form for stability).
    keys: dict[Path, str] = {ch.relative: ch.relative.as_posix() for ch in chapters}

    # Pre-populate cross_page_links with opaque tokens so the converter
    # emits @@RICHDOC_PAGE_URL:..@@ wherever a chapter link resolves.
    cross_page_tokens: dict[str, str] = {
        str(rel): page_url_token(keys[rel]) for rel in keys
    }
    # The converter resolves both `str(key)` and `key.as_posix()`; provide
    # both so it doesn't matter how the caller spells the rel path.
    for rel in keys:
        cross_page_tokens.setdefault(rel.as_posix(), page_url_token(keys[rel]))

    # Convert every chapter.
    walks: list[_ChapterWalk] = []
    for ch in chapters:
        walks.append(
            _walk_chapter(
                chapter=ch,
                plan=plan,
                cross_page_tokens=cross_page_tokens,
                toc_entries=toc_entries if is_book else None,
            )
        )

    # Build bundle pages.
    bundle_pages: list[BundlePage] = []
    pending_pages: list[PendingBundlePage] = []
    # Disambiguate storage filenames if two source chapters collide after
    # slugging (e.g. `a/index.html` and `a-index.html`).
    used_storage_names: dict[str, int] = defaultdict(int)
    for walk in walks:
        page_key = keys[walk.chapter.relative]
        parent_rel = parent_map.get(walk.chapter.relative)
        parent_key = keys.get(parent_rel) if parent_rel is not None else None

        base_storage_name = safe_page_filename(page_key)
        used_storage_names[base_storage_name] += 1
        if used_storage_names[base_storage_name] > 1:
            stem, _, _ = base_storage_name.rpartition(".storage.xml")
            base_storage_name = f"{stem}-{used_storage_names[base_storage_name]}.storage.xml"
        storage_path = f"pages/{base_storage_name}"

        # Attachment metadata for the manifest. The publisher uses
        # `path` to load bytes off disk and `filename` for the
        # Confluence-side attachment name.
        attachments = [
            BundleAttachment(
                token=pa.token,
                filename=pa.filename,
                path=f"attachments/{pa.filename}",
                mime=pa.mime,
                align=pa.align,
                inline=pa.is_inline,
            )
            for pa in walk.pending
        ]
        attachment_data = {pa.filename: pa.data for pa in walk.pending}

        # Record which page-URL tokens actually appear in the rendered
        # body so the publisher can fail fast on unresolved cross-links.
        links = _scan_links(walk.body_template, valid_keys=set(keys.values()))

        bundle_page = BundlePage(
            key=page_key,
            source=walk.chapter.relative.as_posix(),
            title=walk.title,
            parent_key=parent_key,
            storage_path=storage_path,
            attachments=attachments,
            links=links,
            dropped=list(walk.storage.dropped),
            missing=list(walk.storage.missing),
        )
        bundle_pages.append(bundle_page)
        pending_pages.append(
            PendingBundlePage(
                page=bundle_page,
                storage_xml=walk.body_template,
                attachment_data=attachment_data,
            )
        )

    manifest = BundleManifest(
        input_path=str(plan.input_path.resolve()),
        book=is_book,
        pages=bundle_pages,
        schema=BUNDLE_SCHEMA,
        diagrams_rendered=sum(w.storage.diagrams_rendered for w in walks),
        diagrams_failed=sum(w.storage.diagrams_failed for w in walks),
        math_rendered=sum(w.storage.math_rendered for w in walks),
        math_failed=sum(w.storage.math_failed for w in walks),
    )

    write_result = write_bundle(
        bundle_dir=plan.output,
        manifest=manifest,
        pages=pending_pages,
        force=plan.force,
    )

    return ConfluenceExportResult(
        write=write_result,
        manifest=manifest,
        book=is_book,
        pages=bundle_pages,
        attachments=write_result.attachments_written,
        diagrams_rendered=manifest.diagrams_rendered,
        diagrams_failed=manifest.diagrams_failed,
        math_rendered=manifest.math_rendered,
        math_failed=manifest.math_failed,
        dropped=_aggregate_dropped(walks),
        missing=_aggregate_missing(walks),
    )


# ---------------------------------------------------------------------------
# Chapter walking
# ---------------------------------------------------------------------------


@dataclass
class _ChapterWalk:
    chapter: ChapterFile
    title: str
    body_template: str              # storage XML with @@…@@ tokens
    pending: list[PendingAttachment]
    storage: StorageResult


def _walk_chapter(
    *,
    chapter: ChapterFile,
    plan: ConfluenceExportPlan,
    cross_page_tokens: dict[str, str] | None = None,
    toc_entries: list[TocEntry] | None = None,
) -> _ChapterWalk:
    """Run the converter against one chapter; produce a walk record."""
    result = html_to_storage(
        chapter.html,
        asset_base=chapter.path.parent,
        include_remote_images=plan.include_remote_images,
        render_diagrams=plan.render_diagrams,
        render_math=plan.render_math,
        diagram_endpoint=plan.diagram_endpoint,
        cross_page_links=cross_page_tokens,
        title_override=chapter.title,
        chapter_rel=chapter.relative,
        toc_entries=toc_entries,
    )
    return _ChapterWalk(
        chapter=chapter,
        title=result.title or chapter.title or chapter.path.stem,
        body_template=result.body,
        pending=list(result.pending),
        storage=result,
    )


# ---------------------------------------------------------------------------
# Book TOC → parent map + TocEntry tree
# ---------------------------------------------------------------------------


def _build_toc_structures(
    entry: Path, chapters: list[ChapterFile]
) -> tuple[dict[Path, Path | None], list[TocEntry] | None]:
    """Parse the entry file's ``<rd-toc>`` once and produce two things:

    1. ``parent_map`` — ``{chapter_rel: parent_rel}`` used to nest pages
       under their TOC parent. Defaults to nesting every non-entry
       chapter under the entry, overridden by explicit TOC placement.
       Group headers are transparent.
    2. ``toc_entries`` — a ``TocEntry`` tree mirroring the rd-toc, used
       by the converter to render the inline "Contents" block on every
       chapter. Returns ``None`` when the entry has no real TOC.
    """
    parser = LH.HTMLParser(recover=True)
    root = LH.document_fromstring(entry.read_text(encoding="utf-8"), parser=parser)
    toc = next(
        (
            t for t in root.iter("rd-toc")
            if any(
                isinstance(c.tag, str) and c.tag.lower() == "rd-chapter" and c.get("href")
                for c in t.iter("rd-chapter")
            )
        ),
        None,
    )
    entry_rel = chapters[0].relative
    if toc is None:
        return (
            {entry_rel: None, **{ch.relative: entry_rel for ch in chapters[1:]}},
            None,
        )

    base_dir = entry.parent
    rel_by_path: dict[Path, Path] = {ch.path: ch.relative for ch in chapters}

    parent_map: dict[Path, Path | None] = {ch.relative: entry_rel for ch in chapters}
    parent_map[entry_rel] = None

    def visit(node: ET._Element, parent_rel: Path | None) -> list[TocEntry]:
        out: list[TocEntry] = []
        for ch in node:
            if not (isinstance(ch.tag, str) and ch.tag.lower() == "rd-chapter"):
                continue
            href = (ch.get("href") or "").strip()
            title = _chapter_label(ch)
            child_parent = parent_rel
            target_rel: Path | None = None
            if href and not is_external_href(href):
                target = (base_dir / href).resolve()
                if target in rel_by_path:
                    target_rel = rel_by_path[target]
                    if target_rel != entry_rel:
                        parent_map[target_rel] = parent_rel
                    child_parent = target_rel
            children = visit(ch, child_parent)
            out.append(
                TocEntry(
                    title=title,
                    href=href or None,
                    target_rel=target_rel,
                    children=tuple(children),
                )
            )
        return out

    entries = visit(toc, entry_rel)
    return parent_map, entries


# ---------------------------------------------------------------------------
# Link scanning
# ---------------------------------------------------------------------------


def _scan_links(body_xml: str, *, valid_keys: set[str]) -> list[BundleLink]:
    """Collect every distinct page-URL token that ended up in the body.

    The publisher consults this list to verify that every token has a
    matching page in the manifest before it starts substituting.
    """
    seen: dict[str, BundleLink] = {}
    for match in _PAGE_URL_TOKEN_RE.finditer(body_xml):
        key = match.group("key")
        if key not in valid_keys:
            # Tokens for unknown keys would be a converter bug, but they
            # still get reported so the bundle is self-describing.
            pass
        token = match.group(0)
        seen.setdefault(token, BundleLink(token=token, target_key=key))
    return list(seen.values())


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_dropped(walks: list[_ChapterWalk]) -> list[str]:
    seen: set[str] = set()
    for w in walks:
        seen.update(w.storage.dropped)
    return sorted(seen)


def _aggregate_missing(walks: list[_ChapterWalk]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for w in walks:
        for m in w.storage.missing:
            if m not in seen:
                seen.add(m)
                out.append(m)
    return out
