"""Multi-file book discovery.

A richdoc book is a set of HTML files linked via a shared `<rd-toc>` block
whose `<rd-chapter>` children carry `href` attributes. Each chapter file
contains the same TOC verbatim (see SKILL.md "Multi-file documentation").

`discover_chapters(entry)` parses the entry file, walks its TOC tree, and
returns a list of `ChapterFile` objects in TOC document order — entry first
(if present in the TOC), then every other chapter resolved relative to the
entry directory. Absolute hrefs are skipped. Missing files are reported via
the `missing` field; the caller decides how to surface them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import lxml.etree as ET
import lxml.html as LH


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

    toc = _find_book_toc(root)
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
        if _is_external_href(href):
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


def _find_book_toc(root: ET._Element) -> ET._Element | None:  # noqa: SLF001
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
            title = _chapter_title(child)
            out.append((href, title))
            walk(child)

    walk(toc)
    return out


def _chapter_title(node: ET._Element) -> str:  # noqa: SLF001
    """Mirror the renderer/lint chapter-title extraction: text content of
    the element with nested <rd-chapter> sub-trees removed."""
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


def _doc_title(root: ET._Element) -> str | None:  # noqa: SLF001
    hero = next(iter(root.iter("rd-hero")), None)
    if hero is not None:
        t = hero.get("title")
        if t and t.strip():
            return t.strip()
    h1 = next(iter(root.iter("h1")), None)
    if h1 is not None:
        text = " ".join("".join(h1.itertext()).split()).strip()
        if text:
            return text
    title_el = next(iter(root.iter("title")), None)
    if title_el is not None and title_el.text and title_el.text.strip():
        return title_el.text.strip()
    return None


def _is_external_href(href: str) -> bool:
    s = (href or "").strip()
    if not s:
        return True
    if s.startswith("#"):
        return True
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", s)) or s.startswith("//")


def _safe_relative(target: Path, base_dir: Path) -> Path:
    try:
        return target.relative_to(base_dir)
    except ValueError:
        # Chapter lives above the entry's directory — flatten it under its
        # filename so we never escape the output folder.
        return Path(target.name)
