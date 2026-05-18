"""Concatenate every chapter of a book into one combined markdown file.

The combiner is the SINGLE-mode counterpart to the per-chapter renderer
that drives MULTI mode. It produces a single .md whose top-level shape is:

    # <Book title>           (from rd-toc title, or fallback)

    ## Contents               (markdown bullet list of chapter titles,
                              anchor-linked to each chapter's H1)

    ## <Chapter 1 title>      (heading injected only when the chapter has
                              no top-level heading of its own)
    …chapter 1 body, headings demoted by 1 level…

    ---

    ## <Chapter 2 title>
    …chapter 2 body…

The heading demotion keeps the combined doc to a single H1 at the top so
downstream tooling (Pandoc, Hugo, an LLM context) sees consistent levels.
"""

from __future__ import annotations

import re

import lxml.html as LH

from ..book import ChapterFile
from ..common.assets import AssetStore
from .converter import html_to_markdown


def combine_chapters_to_markdown(
    chapters: list[ChapterFile],
    *,
    book_title: str,
    asset_store: AssetStore,
    include_remote_images: bool = False,
) -> tuple[str, list[str]]:
    """Render every chapter and stitch the markdown chunks into one document.

    Returns (combined_markdown_text, dropped_tag_names).
    """
    dropped: list[str] = []
    sections: list[str] = []

    if book_title:
        sections.append(f"# {book_title}\n")

    # Contents block
    toc_lines = ["## Contents", ""]
    for ch in chapters:
        anchor = _anchor(ch.title)
        toc_lines.append(f"- [{ch.title}](#{anchor})")
    sections.append("\n".join(toc_lines) + "\n")

    # Per-chapter bodies. The shared `<rd-toc>` block is stripped from each
    # chapter before conversion — we already emit a `## Contents` block at
    # the top, so the per-chapter TOC is just noise in a combined doc.
    for i, ch in enumerate(chapters):
        html_without_toc = _strip_rd_toc(ch.html)
        md_text, ch_dropped = html_to_markdown(
            html_without_toc,
            asset_store=asset_store,
            asset_base=ch.path.parent,
            include_remote_images=include_remote_images,
            assets_subdir="assets",
        )
        dropped.extend(ch_dropped)
        chunk = _demote_headings(md_text, by=1)
        chunk = _ensure_chapter_heading(chunk, ch.title)
        sections.append(chunk.rstrip() + "\n")
        if i < len(chapters) - 1:
            sections.append("---\n")

    body = "\n".join(sections).rstrip() + "\n"
    # Collapse 3+ blank lines that may have crept in across the joins.
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body, sorted(set(dropped))


# ---------------------------------------------------------------------------
# Heading transforms
# ---------------------------------------------------------------------------


_FENCE = re.compile(r"^(```|~~~)")
_HEADING = re.compile(r"^(#{1,6}) ")


def _demote_headings(md: str, *, by: int) -> str:
    """Add `by` extra `#` to each ATX heading (`# ` → `## `, capped at 6).

    Lines inside fenced code blocks are left alone — a `# comment` in
    Python or Bash isn't a heading.
    """
    if by <= 0:
        return md
    out: list[str] = []
    in_fence = False
    for line in md.split("\n"):
        stripped = line.lstrip()
        if _FENCE.match(stripped):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        m = _HEADING.match(line)
        if m:
            current = len(m.group(1))
            new = min(current + by, 6)
            out.append("#" * new + line[current:])
        else:
            out.append(line)
    return "\n".join(out)


def _ensure_chapter_heading(md: str, title: str) -> str:
    """Prepend `## <title>` if the chapter body has no top-level heading."""
    body = md.lstrip()
    in_fence = False
    for line in body.split("\n"):
        stripped = line.lstrip()
        if _FENCE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line)
        if m:
            # Chapter already has its own heading — leave it.
            return body
        if line.strip():
            # First non-blank line isn't a heading. Inject one.
            break
    return f"## {title}\n\n{body}"


def _strip_rd_toc(html: str) -> str:
    """Remove every <rd-toc> element from `html` so chapter bodies don't
    duplicate the contents list we emit at the top of the combined doc.

    Returns the modified HTML as a string. We re-serialise rather than
    handing back a tree so the existing `html_to_markdown` keeps its
    string-in / string-out contract.
    """
    parser = LH.HTMLParser(recover=True)
    root = LH.document_fromstring(html, parser=parser)
    removed = False
    for toc in list(root.iter("rd-toc")):
        parent = toc.getparent()
        if parent is not None:
            parent.remove(toc)
            removed = True
    if not removed:
        return html
    return LH.tostring(root, encoding="unicode", method="html")


def _anchor(title: str) -> str:
    """GitHub-style anchor: lowercase, spaces → hyphens, strip punctuation."""
    text = title.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text or "section"
