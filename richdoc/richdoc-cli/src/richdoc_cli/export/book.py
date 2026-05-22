"""Multi-file book discovery.

A richdoc book is a set of HTML files linked via a shared `<rd-toc>` block
whose `<rd-chapter>` children carry `href` attributes. Each chapter file
contains the same TOC verbatim (see references/multi-file-books.md).

`discover_chapters(entry)` parses the entry file, walks its TOC tree, and
returns a list of `ChapterFile` objects in TOC document order — entry first
(if present in the TOC), then every other chapter resolved relative to the
entry directory. Absolute hrefs are skipped. Missing files are reported via
the `missing` field; the caller decides how to surface them.

The helpers `find_book_toc`, `chapter_title`, `toc_signature`, and
`linked_chapter_paths` are exposed for use by `richdoc lint` (and any
future tooling) so the same definition of "a book" applies to the
publisher, the linter, and the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import lxml.etree as ET
import lxml.html as LH

from .common.href import is_external_href
from .common.titles import chapter_label as _chapter_label_canonical
from .common.titles import resolve_doc_title as _resolve_doc_title_canonical

# Re-export so existing `from .book import is_external_href` callers
# keep working without touching their import path.
__all__ = [
    "BookDiscovery",
    "ChapterFile",
    "TocSignature",
    "TocSignatureEntry",
    "chapter_title",
    "discover_chapters",
    "find_book_toc",
    "is_external_href",
    "linked_chapter_paths",
    "toc_signature",
]


@dataclass(frozen=True)
class TocSignatureEntry:
    """One node in a normalised <rd-toc> signature, used to compare TOC
    blocks across chapter files for equality.

    `href` is the raw attribute value (or None for group headers), not a
    resolved path — two TOCs with `./foo.html` vs `foo.html` are
    intentionally different, mirroring the runtime contract ("the same
    block lives in every file, verbatim").
    """

    href: str | None
    title: str
    children: tuple[TocSignatureEntry, ...]


@dataclass(frozen=True)
class TocSignature:
    """Normalised representation of a chapter file's <rd-toc> block."""

    title: str  # the rd-toc[title] attribute, whitespace-collapsed
    entries: tuple[TocSignatureEntry, ...]

    def is_empty(self) -> bool:
        return not self.entries


@dataclass(frozen=True)
class ChapterFile:
    """One chapter resolved on disk."""

    path: Path
    html: str
    # Path relative to the book root (the entry file's parent dir).
    relative: Path
    # Title pulled from the chapter's TOC entry — used as the output stem
    # fallback and the docx Heading 1 when chapters are concatenated.
    title: str


@dataclass
class BookDiscovery:
    chapters: list[ChapterFile] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    # True iff the entry has an rd-toc with at least one href-carrying chapter.
    is_book: bool = False


def discover_chapters(entry: Path) -> BookDiscovery:
    """Find every chapter linked from `entry`'s rd-toc. Always includes the
    entry file as the first chapter (with a synthesised title if absent)."""
    entry = entry.resolve()
    source = entry.read_text(encoding="utf-8")
    parser = LH.HTMLParser(recover=True)
    root = LH.document_fromstring(source, parser=parser)

    toc = find_book_toc(root)
    base_dir = entry.parent

    if toc is None:
        return BookDiscovery(
            chapters=[
                ChapterFile(
                    path=entry,
                    html=source,
                    relative=Path(entry.name),
                    title=_doc_title(root) or entry.stem,
                )
            ],
            is_book=False,
        )

    entries = list(_walk_chapters(toc, base_dir=base_dir))

    seen: dict[Path, ChapterFile] = {}
    missing: list[str] = []
    for href, title in entries:
        if href is None:
            continue  # group header
        if is_external_href(href):
            continue
        target = (base_dir / href).resolve()
        if target in seen:
            continue
        try:
            text = target.read_text(encoding="utf-8")
        except OSError:
            missing.append(href)
            continue
        rel = _safe_relative(target, base_dir)
        seen[target] = ChapterFile(
            path=target, html=text, relative=rel, title=title or target.stem
        )

    # Ensure entry is included first, even if its href doesn't appear in the
    # TOC (lint accepts that). Title comes from <rd-toc> if listed, else
    # falls back to the document's first <h1>/<rd-hero title> or stem.
    if entry not in seen:
        ordered = [
            ChapterFile(
                path=entry,
                html=source,
                relative=Path(entry.name),
                title=_doc_title(root) or entry.stem,
            ),
            *seen.values(),
        ]
    else:
        # Move the entry to the front, preserve the rest in TOC order.
        entry_ch = seen.pop(entry)
        ordered = [entry_ch, *seen.values()]

    return BookDiscovery(chapters=ordered, missing=missing, is_book=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def find_book_toc(root: ET._Element) -> ET._Element | None:
    """Find an rd-toc element whose direct children contain at least one
    rd-chapter with an href. Returns None for single-file docs."""
    for toc in root.iter("rd-toc"):
        for ch in toc.iter("rd-chapter"):
            if ch.get("href"):
                return toc
    return None


def _walk_chapters(
    toc: ET._Element, *, base_dir: Path
) -> list[tuple[str | None, str]]:
    """Flatten the rd-chapter tree into a list of (href, title) tuples in
    document order. href is None for group headers."""
    out: list[tuple[str | None, str]] = []

    def walk(node: ET._Element) -> None:
        for child in node:
            if not isinstance(child.tag, str):
                continue
            if child.tag.lower() != "rd-chapter":
                continue
            href = child.get("href")
            title = chapter_title(child)
            out.append((href, title))
            walk(child)

    walk(toc)
    return out


def chapter_title(node: ET._Element) -> str:
    """Visible text of one ``<rd-chapter>``, nested sub-trees stripped.

    Thin wrapper around the canonical implementation in
    ``export.common.titles.chapter_label``; kept here so existing
    callers (lint, publisher) don't have to change import paths.
    """
    return _chapter_label_canonical(node)


def toc_signature(toc: ET._Element) -> TocSignature:
    """Reduce an <rd-toc> element to its comparable signature.

    Two `<rd-toc>` blocks are considered identical iff their signatures
    compare equal. Compare against the entry file's signature to detect
    drift across chapter files (the `book-toc-drift` lint rule).
    """

    def walk(node: ET._Element) -> tuple[TocSignatureEntry, ...]:
        out: list[TocSignatureEntry] = []
        for child in node:
            if not isinstance(child.tag, str):
                continue
            if child.tag.lower() != "rd-chapter":
                continue
            href = child.get("href")
            href_norm = href.strip() if href is not None else None
            out.append(
                TocSignatureEntry(
                    href=href_norm,
                    title=chapter_title(child),
                    children=walk(child),
                )
            )
        return tuple(out)

    title_attr = (toc.get("title") or "").strip()
    title_norm = " ".join(title_attr.split())
    return TocSignature(title=title_norm, entries=walk(toc))


def linked_chapter_paths(
    file_path: Path, sig: TocSignature
) -> list[tuple[Path, str]]:
    """Resolve every relative file-targeting `<rd-chapter href>` in `sig`
    against `file_path.parent`. Returns `(resolved_path, raw_href)` tuples
    in TOC document order. Skips external URLs, fragment-only hrefs, and
    group headers (href is None).
    """
    base_dir = file_path.parent
    out: list[tuple[Path, str]] = []

    def walk(entries: tuple[TocSignatureEntry, ...]) -> None:
        for entry in entries:
            if entry.href is not None and not is_external_href(entry.href):
                target = (base_dir / entry.href).resolve()
                out.append((target, entry.href))
            walk(entry.children)

    walk(sig.entries)
    return out


def _doc_title(root: ET._Element) -> str | None:
    """Legacy alias for ``export.common.titles.resolve_doc_title``."""
    return _resolve_doc_title_canonical(root)


def _safe_relative(target: Path, base_dir: Path) -> Path:
    try:
        return target.relative_to(base_dir)
    except ValueError:
        # Chapter lives above the entry's directory — flatten it under its
        # filename so we never escape the output folder.
        return Path(target.name)
