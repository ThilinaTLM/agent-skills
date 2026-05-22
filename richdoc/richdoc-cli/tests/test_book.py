"""Unit tests for `export/book.py`.

The book discovery + TOC signature helpers are foundational to every
multi-file flow (export, publish, lint drift). These tests pin their
behaviour independently of the higher-level command surface.
"""

from __future__ import annotations

from pathlib import Path

from richdoc_cli.export.book import (
    chapter_title,
    discover_chapters,
    find_book_toc,
    is_external_href,
    linked_chapter_paths,
    toc_signature,
)
from richdoc_cli.export.common.walker import parse_html

# ---------------------------------------------------------------------------
# is_external_href
# ---------------------------------------------------------------------------


def test_is_external_href_recognises_schemes():
    assert is_external_href("https://example.com")
    assert is_external_href("http://example.com")
    assert is_external_href("mailto:a@b")
    assert is_external_href("//example.com")
    assert is_external_href("#fragment-only")
    assert is_external_href("")


def test_is_external_href_keeps_relative_local():
    assert not is_external_href("./chapter.html")
    assert not is_external_href("chapter.html")
    assert not is_external_href("../sibling/chapter.html")


# ---------------------------------------------------------------------------
# discover_chapters
# ---------------------------------------------------------------------------


def test_discover_single_file_is_not_a_book(examples_dir):
    result = discover_chapters(examples_dir / "showcase.html")
    assert result.is_book is False
    assert len(result.chapters) == 1
    assert result.chapters[0].path == (examples_dir / "showcase.html").resolve()
    assert result.missing == []


def test_discover_book_finds_every_chapter(examples_dir):
    entry = examples_dir / "book" / "index.html"
    result = discover_chapters(entry)
    assert result.is_book is True
    # Entry chapter is always first.
    assert result.chapters[0].path == entry.resolve()
    paths = [c.path.name for c in result.chapters]
    # Order follows TOC document order.
    assert "01-species.html" in paths
    assert "02-habitat.html" in paths
    assert result.missing == []


def test_discover_book_reports_missing_chapters(tmp_path):
    entry = tmp_path / "index.html"
    entry.write_text(
        """<!doctype html><html><body>
        <rd-page>
          <rd-toc title="t">
            <rd-chapter href="./missing.html">Missing</rd-chapter>
          </rd-toc>
        </rd-page>
        </body></html>""",
        encoding="utf-8",
    )
    result = discover_chapters(entry)
    assert result.is_book is True
    assert result.missing == ["./missing.html"]
    # Entry is still the only chapter file we could read.
    assert [c.path for c in result.chapters] == [entry.resolve()]


# ---------------------------------------------------------------------------
# find_book_toc
# ---------------------------------------------------------------------------


def test_find_book_toc_requires_href_carrying_chapter(tmp_path):
    # rd-toc without href children is treated as headings-mode \u2014 not a book.
    src = """<!doctype html><html><body>
    <rd-page>
      <rd-toc title="t">
        <rd-chapter>No href here</rd-chapter>
      </rd-toc>
    </rd-page>
    </body></html>"""
    root = parse_html(src)
    assert find_book_toc(root) is None


def test_find_book_toc_picks_first_book_toc(tmp_path):
    src = """<!doctype html><html><body>
    <rd-page>
      <rd-toc title="A">
        <rd-chapter>No href</rd-chapter>
      </rd-toc>
      <rd-toc title="B">
        <rd-chapter href="./other.html">Other</rd-chapter>
      </rd-toc>
    </rd-page>
    </body></html>"""
    root = parse_html(src)
    toc = find_book_toc(root)
    assert toc is not None
    assert toc.get("title") == "B"


# ---------------------------------------------------------------------------
# chapter_title
# ---------------------------------------------------------------------------


def test_chapter_title_strips_nested_chapter_subtrees():
    src = """<rd-chapter href="./a.html">
        Parent title
        <rd-chapter href="./a-1.html">Nested 1</rd-chapter>
        <rd-chapter href="./a-2.html">Nested 2</rd-chapter>
    </rd-chapter>"""
    root = parse_html(f"<!doctype html><html><body>{src}</body></html>")
    ch = next(root.iter("rd-chapter"))
    assert chapter_title(ch) == "Parent title"


def test_chapter_title_concatenates_inline_decorations():
    src = """<rd-chapter href="./a.html">
        <em>Italic</em> chapter <strong>title</strong>
    </rd-chapter>"""
    root = parse_html(f"<!doctype html><html><body>{src}</body></html>")
    ch = next(root.iter("rd-chapter"))
    assert chapter_title(ch) == "Italic chapter title"


# ---------------------------------------------------------------------------
# toc_signature
# ---------------------------------------------------------------------------


def test_toc_signature_is_stable_across_equal_blocks(examples_dir):
    book = examples_dir / "book"
    sig_index = toc_signature(
        find_book_toc(parse_html((book / "index.html").read_text(encoding="utf-8")))
    )
    sig_species = toc_signature(
        find_book_toc(parse_html((book / "01-species.html").read_text(encoding="utf-8")))
    )
    assert sig_index == sig_species


def test_toc_signature_differs_when_titles_drift(fixtures_dir):
    drift = fixtures_dir / "book-drift"
    sig_index = toc_signature(
        find_book_toc(parse_html((drift / "index.html").read_text(encoding="utf-8")))
    )
    sig_two = toc_signature(
        find_book_toc(parse_html((drift / "two.html").read_text(encoding="utf-8")))
    )
    assert sig_index != sig_two


# ---------------------------------------------------------------------------
# linked_chapter_paths
# ---------------------------------------------------------------------------


def test_linked_chapter_paths_resolves_against_file_dir(examples_dir):
    entry = examples_dir / "book" / "index.html"
    sig = toc_signature(find_book_toc(parse_html(entry.read_text(encoding="utf-8"))))
    paths = linked_chapter_paths(entry, sig)
    assert paths, "expected at least one linked chapter"
    book_root = entry.parent.resolve()
    for resolved, _href in paths:
        assert isinstance(resolved, Path)
        assert resolved.is_absolute()
        # Every chapter resolves under the book root (possibly in subdirs).
        assert book_root in resolved.parents or resolved.parent == book_root
