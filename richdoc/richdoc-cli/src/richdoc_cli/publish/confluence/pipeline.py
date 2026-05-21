"""Orchestrate the HTML → Confluence publish flow.

For a single-file input the pipeline:

  1. Walks the chapter via `html_to_storage` (no network).
  2. Decides create-vs-update by looking up `(space, parent, title)`.
  3. For a create: makes the page with a placeholder body, uploads
     attachments, then updates the page body with the real attachment
     references.
  4. For an update: uploads attachments (versioning by filename), then
     updates the page body in one call.

For a book input the same flow runs per chapter; chapters nest under
their parent in TOC order. The entry chapter goes under the user-supplied
`parent_id` (or space root); each child chapter goes under whatever page
the previous chapter resolved to in the TOC tree.

The pipeline is intentionally synchronous and serial — Confluence
rate-limits concurrent writes, and serial output keeps the JSON
envelope's `pages` list ordered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import lxml.etree as ET
import lxml.html as LH

from ...export.book import ChapterFile, discover_chapters
from .client import (
    ConfluenceClient,
    ConfluenceConflictError,
    Page,
)
from .converter import PendingAttachment, TocEntry, html_to_storage, xml_attr


# ---------------------------------------------------------------------------
# Plan / result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublishPlan:
    """The user's intent. Built by the CLI command, consumed by `publish()`."""

    input_path: Path
    space_key: str
    parent_id: str | None       # explicit parent override (book entry parent)
    title_override: str | None  # single-file mode title
    title_prefix: str           # prepended to every page title
    page_id_override: str | None  # forces update on this page id
    no_book: bool
    dry_run: bool
    render_diagrams: bool
    render_math: bool
    diagram_endpoint: str
    include_remote_images: bool
    update_comment: str


@dataclass
class PageOutcome:
    """One published page, captured for the JSON envelope."""

    id: str
    title: str
    parent_id: str | None
    url: str
    action: str  # "created" | "updated" | "unchanged" | "planned"
    version: int


@dataclass
class PublishResult:
    site: str
    space_id: str
    space_key: str
    book: bool
    pages: list[PageOutcome] = field(default_factory=list)
    attachments_uploaded: int = 0
    attachments_skipped: int = 0
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    math_rendered: int = 0
    math_failed: int = 0
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    dry_run: bool = False
    dry_run_bodies: list[dict] = field(default_factory=list)
    # Per-page parent override (book chapter tree) lives here for the
    # envelope's caller — not needed inside the pipeline once we're done.


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def publish(plan: PublishPlan, client: ConfluenceClient) -> PublishResult:
    """Run the publish pipeline against the given Confluence client."""
    space = client.get_space_by_key(plan.space_key)
    discovery = discover_chapters(plan.input_path)
    chapters = discovery.chapters if not plan.no_book else discovery.chapters[:1]
    is_book = discovery.is_book and not plan.no_book

    # Build a TOC-driven parent map: each chapter knows the relative path of
    # its parent chapter (or None for the book entry / single page). The
    # same walk also yields the rd-toc tree as `TocEntry`s so every chapter
    # can render an inline Contents block with resolved Confluence links.
    if is_book:
        parent_map, toc_entries = _build_toc_structures(
            plan.input_path, chapters
        )
    else:
        parent_map, toc_entries = {}, None

    # Walk every chapter into storage XML up-front so we know titles and
    # cross-page link targets before any network call.
    walks: list[_ChapterWalk] = []
    for ch in chapters:
        walk = _walk_chapter(
            chapter=ch,
            plan=plan,
            toc_entries=toc_entries,
        )
        walks.append(walk)

    # Cross-page link map: resolved Confluence page URLs by chapter relative
    # path. Populated as pages are created/looked up; injected into a second
    # pass converter run.
    cross_page_links: dict[str, str] = {}

    # Page id by chapter relative path — used to walk the chapter tree.
    chapter_pages: dict[Path, Page] = {}
    page_outcomes: list[PageOutcome] = []
    pending_for_first_pass: list[tuple[_ChapterWalk, str | None]] = []

    # First pass — resolve or create every page (placeholder body if there
    # are pending attachments) so we have ids for cross-chapter links.
    for walk in walks:
        parent_rel = parent_map.get(walk.chapter.relative)
        if parent_rel is not None and parent_rel in chapter_pages:
            parent_id_for_chapter: str | None = chapter_pages[parent_rel].id
        else:
            parent_id_for_chapter = plan.parent_id

        full_title = (plan.title_prefix or "") + (
            plan.title_override if (plan.title_override and walk is walks[0] and not is_book)
            else walk.title
        )

        existing = _find_existing(
            client,
            space_id=space.id,
            page_id_override=plan.page_id_override if walk is walks[0] else None,
            title=full_title,
            parent_id=parent_id_for_chapter,
        )

        if plan.dry_run:
            outcome = PageOutcome(
                id=existing.id if existing else "(planned)",
                title=full_title,
                parent_id=parent_id_for_chapter,
                url=client.page_url(existing, space.key) if existing else "(planned)",
                action="planned",
                version=existing.version if existing else 0,
            )
            page_outcomes.append(outcome)
            chapter_pages[walk.chapter.relative] = existing or Page(
                id="(planned)", title=full_title, space_id=space.id,
                parent_id=parent_id_for_chapter, version=0, webui="",
            )
            cross_page_links[str(walk.chapter.relative)] = "(planned)"
            continue

        if existing is None:
            # Create with a placeholder body — the real body comes after
            # attachments upload (so token replacement has real filenames).
            placeholder = "<p><em>Publishing — body coming in a follow-up update.</em></p>"
            created = client.create_page(
                space_id=space.id,
                parent_id=parent_id_for_chapter,
                title=full_title,
                body_storage=placeholder if walk.pending else walk.body_template,
            )
            chapter_pages[walk.chapter.relative] = created
            cross_page_links[str(walk.chapter.relative)] = client.page_url(created, space.key)
            pending_for_first_pass.append((walk, "created"))
            outcome = PageOutcome(
                id=created.id,
                title=created.title,
                parent_id=created.parent_id,
                url=client.page_url(created, space.key),
                action="created",
                version=created.version,
            )
            page_outcomes.append(outcome)
        else:
            chapter_pages[walk.chapter.relative] = existing
            cross_page_links[str(walk.chapter.relative)] = client.page_url(existing, space.key)
            pending_for_first_pass.append((walk, "updated"))
            outcome = PageOutcome(
                id=existing.id,
                title=existing.title,
                parent_id=existing.parent_id,
                url=client.page_url(existing, space.key),
                action="updated",
                version=existing.version,
            )
            page_outcomes.append(outcome)

    # Second pass — upload attachments (idempotent) and update bodies with
    # cross-page links resolved.
    attachments_uploaded = 0
    attachments_skipped = 0
    if plan.dry_run:
        # For dry-run we just record the storage XML and the attachment plan.
        # Re-walk in book mode so the preview reflects the cross-page link
        # map exactly as a real publish would — placeholder URLs and all.
        bodies = []
        for walk, outcome in zip(walks, page_outcomes):
            preview_walk = walk
            if is_book:
                preview_walk = _walk_chapter(
                    chapter=walk.chapter,
                    plan=plan,
                    cross_page_links=cross_page_links,
                    toc_entries=toc_entries,
                )
            bodies.append({
                "chapter": str(walk.chapter.relative),
                "title": outcome.title,
                "parent_id": outcome.parent_id,
                "body_preview": preview_walk.body_template,
                "pending_attachments": [
                    {"filename": pa.filename, "mime": pa.mime, "bytes": len(pa.data)}
                    for pa in preview_walk.pending
                ],
            })
        return PublishResult(
            site=client.site,
            space_id=space.id,
            space_key=space.key,
            book=is_book,
            pages=page_outcomes,
            dropped=_aggregate_dropped(walks),
            missing=_aggregate_missing(walks),
            diagrams_rendered=sum(w.storage.diagrams_rendered for w in walks),
            diagrams_failed=sum(w.storage.diagrams_failed for w in walks),
            math_rendered=sum(w.storage.math_rendered for w in walks),
            math_failed=sum(w.storage.math_failed for w in walks),
            dry_run=True,
            dry_run_bodies=bodies,
        )

    for walk, outcome in zip(walks, page_outcomes):
        page = chapter_pages[walk.chapter.relative]
        # Re-render the storage body with resolved cross-page links
        # whenever we're in book mode — every chapter needs cross_page_links
        # to resolve its rd-toc Contents block and any in-body chapter links.
        # In single-file mode the first pass already produced the final body.
        if is_book:
            walk = _walk_chapter(
                chapter=walk.chapter,
                plan=plan,
                cross_page_links=cross_page_links,
                toc_entries=toc_entries,
            )
        # Upload attachments.
        existing_atts = (
            {a.title for a in client.list_attachments(page.id)} if walk.pending else set()
        )
        body = walk.body_template
        for pa in walk.pending:
            if pa.filename in existing_atts:
                attachments_skipped += 1
            else:
                client.upload_attachment(
                    page_id=page.id,
                    filename=pa.filename,
                    data=pa.data,
                    mime=pa.mime,
                    comment=plan.update_comment,
                )
                attachments_uploaded += 1
                existing_atts.add(pa.filename)
            body = body.replace(pa.token, _image_xml(pa))

        # Push the final body. We always re-save: even when no body change
        # happened, this is the only place a placeholder-on-create gets
        # replaced.
        try:
            updated = client.update_page(
                page_id=page.id,
                title=outcome.title,
                body_storage=body,
                current_version=page.version,
                parent_id=outcome.parent_id,
                comment=plan.update_comment,
            )
        except ConfluenceConflictError:
            # Someone else updated meanwhile — refetch and retry once.
            fresh = client.get_page(page.id)
            updated = client.update_page(
                page_id=fresh.id,
                title=outcome.title,
                body_storage=body,
                current_version=fresh.version,
                parent_id=outcome.parent_id,
                comment=plan.update_comment,
            )
        outcome.version = updated.version

    return PublishResult(
        site=client.site,
        space_id=space.id,
        space_key=space.key,
        book=is_book,
        pages=page_outcomes,
        attachments_uploaded=attachments_uploaded,
        attachments_skipped=attachments_skipped,
        diagrams_rendered=sum(w.storage.diagrams_rendered for w in walks),
        diagrams_failed=sum(w.storage.diagrams_failed for w in walks),
        math_rendered=sum(w.storage.math_rendered for w in walks),
        math_failed=sum(w.storage.math_failed for w in walks),
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
    body_template: str   # body with @@ATTACHMENT:..@@ tokens
    pending: list[PendingAttachment]
    storage: object  # StorageResult


def _walk_chapter(
    *,
    chapter: ChapterFile,
    plan: PublishPlan,
    cross_page_links: dict[str, str] | None = None,
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
        cross_page_links=cross_page_links,
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
# Existing-page lookup
# ---------------------------------------------------------------------------


def _find_existing(
    client: ConfluenceClient,
    *,
    space_id: str,
    page_id_override: str | None,
    title: str,
    parent_id: str | None,
) -> Page | None:
    if page_id_override:
        return client.get_page(page_id_override)
    return client.find_page_by_title(
        space_id=space_id, title=title, parent_id=parent_id
    )


# ---------------------------------------------------------------------------
# Book TOC → parent map + TocEntry tree
# ---------------------------------------------------------------------------


def _build_toc_structures(
    entry: Path, chapters: list[ChapterFile]
) -> tuple[dict[Path, Path | None], list[TocEntry] | None]:
    """Parse the entry file's `<rd-toc>` once and produce two things:

    1. `parent_map` — `{chapter_rel: parent_rel}` used by the pipeline
       to nest pages under their TOC parent. Defaults to nesting every
       non-entry chapter under the entry, overridden by explicit TOC
       placement. Group headers are transparent.
     2. `toc_entries` — a `TocEntry` tree mirroring the rd-toc, used by
        the converter to render the inline "Contents" block on every
        chapter. Returns `None` when the entry has no real TOC — in
        that case the converter falls back to dropping `rd-toc`.
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

    # Default: every non-entry chapter nests under the entry. Specific TOC
    # placements below override this default.
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
            if href and not _is_external(href):
                target = (base_dir / href).resolve()
                if target in rel_by_path:
                    target_rel = rel_by_path[target]
                    # The entry chapter always lives directly under the
                    # user-supplied parent_id, regardless of how it appears
                    # in its own TOC.
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

    # Top-level TOC entries default to nesting under the entry chapter.
    entries = visit(toc, entry_rel)
    return parent_map, entries


def _chapter_label(node: ET._Element) -> str:
    """Mirror book.py's chapter-title extraction: text content of `node`
    with nested `<rd-chapter>` sub-trees removed."""
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if isinstance(child.tag, str) and child.tag.lower() == "rd-chapter":
            if child.tail:
                parts.append(child.tail)
            continue
        parts.extend(child.itertext())
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split()).strip()


def _is_external(href: str) -> bool:
    s = href.strip()
    if not s or s.startswith("#") or s.startswith("//"):
        return True
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", s))


# ---------------------------------------------------------------------------
# Attachment XML
# ---------------------------------------------------------------------------


def _image_xml(pa: PendingAttachment) -> str:
    """Build the `<ac:image>` reference for a resolved attachment."""
    if pa.is_inline:
        return (
            f'<ac:image><ri:attachment ri:filename="{xml_attr(pa.filename)}"/></ac:image>'
        )
    align = pa.align or "center"
    return (
        f'<ac:image ac:align="{xml_attr(align)}">'
        f'<ri:attachment ri:filename="{xml_attr(pa.filename)}"/>'
        "</ac:image>"
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _aggregate_dropped(walks: list[_ChapterWalk]) -> list[str]:
    seen: dict[str, int] = {}
    for w in walks:
        for tag in w.storage.dropped:
            seen[tag] = seen.get(tag, 0) + 1
    # Sort for stable output.
    return sorted(seen.keys())


def _aggregate_missing(walks: list[_ChapterWalk]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for w in walks:
        for m in w.storage.missing:
            if m not in seen:
                seen.add(m)
                out.append(m)
    return out
