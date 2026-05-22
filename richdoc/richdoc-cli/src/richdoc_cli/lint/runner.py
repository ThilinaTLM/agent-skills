"""``lint_path`` \u2014 walk a file or directory, apply every rule, build the
per-file JSON envelope.

The runner is intentionally thin: it parses the HTML, decides single-
file vs directory mode, and dispatches to the rule modules in
``rules/``. Rules append to a shared ``issues`` list; the runner
computes ``errors`` / ``warnings`` totals at the end.

Public:

- ``lint_path(path, *, fix=False) -> dict``  \u2014 also re-exported by
  ``richdoc_cli.lint``.

Module-private:

- ``_lint_file``  \u2014 the per-file walk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lxml.etree as ET
import lxml.html as LH

from ..export.book import (
    TocSignature,
    find_book_toc,
    is_external_href,
    toc_signature,
)
from ..schema import SchemaFile, is_rd_tag, load_schema
from .autofix import serialize_html
from .issues import iter_elements
from .rules import attributes as attr_rules
from .rules import book as book_rules
from .rules import document as doc_rules
from .rules import hero_nav as hero_nav_rules

__all__ = ["lint_path"]


def lint_path(path: Path, *, fix: bool = False) -> dict[str, Any]:
    """Lint a single ``.html`` file or a directory of them.

    Returns an envelope payload (a dict that is structurally identical
    for success and error \u2014 the caller decides which ``json_*`` to
    emit based on ``result['errors']``).

    Single file:  ``{"file": ..., "errors": N, "warnings": M, "issues": [...], "fixed": [...]}``
    Directory:    ``{"path": ..., "files": [...], "errors": N, "warnings": M, "fixed": [...]}``
    """
    schema = load_schema()
    resolved = path.resolve()
    peer_cache: dict[Path, book_rules.PeerInfo | None] = {}

    if resolved.is_dir():
        files = sorted(resolved.glob("*.html"))
        per_file = [_lint_file(f, schema, fix=fix, peer_cache=peer_cache) for f in files]
        return {
            "path": str(resolved),
            "files": per_file,
            "errors": sum(f["errors"] for f in per_file),
            "warnings": sum(f["warnings"] for f in per_file),
            "fixed": sum(len(f.get("fixed") or []) for f in per_file),
        }

    if resolved.suffix.lower() not in (".html", ".htm"):
        raise OSError(f"Not a .html file or directory: {resolved}")

    return _lint_file(resolved, schema, fix=fix, peer_cache=peer_cache)


# ---------------------------------------------------------------------------
# Per-file walk
# ---------------------------------------------------------------------------


def _lint_file(
    file_path: Path,
    schema: SchemaFile,
    *,
    fix: bool,
    peer_cache: dict[Path, book_rules.PeerInfo | None],
) -> dict[str, Any]:
    """Lint a single file. Returns the per-file envelope payload."""
    file_path = file_path.resolve()
    allowed_tags = set(schema.tags.keys())

    # Read source.
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _unreadable_payload(file_path, exc)

    issues: list[dict[str, Any]] = []

    # Source-level checks run before parsing (so they catch
    # self-closing tags lxml would silently rewrite).
    doc_rules.check_source_scan(source=source, issues=issues)

    # Parse.
    parser = LH.HTMLParser(recover=True)
    try:
        root = LH.document_fromstring(source, parser=parser)
    except (ET.ParserError, ValueError) as exc:
        return _unparseable_payload(file_path, exc)

    # Document-level checks (head links, rd-page wrapper).
    doc_rules.check_head_and_page(root=root, issues=issues)

    # Per-element checks.
    for node in iter_elements(root):
        tag_raw = node.tag
        if not isinstance(tag_raw, str):
            continue
        tag = tag_raw.lower()
        if not is_rd_tag(tag):
            continue
        attr_rules.check_element(
            node=node,
            tag=tag,
            schema=schema,
            allowed_tags=allowed_tags,
            file_path=file_path,
            issues=issues,
        )

    # Book-mode checks (drift, hero-nav).
    self_toc = find_book_toc(root)
    is_book_mode = self_toc is not None
    self_sig: TocSignature | None = toc_signature(self_toc) if self_toc is not None else None

    if is_book_mode and self_sig is not None and self_toc is not None:
        book_rules.check_drift(
            file_path=file_path,
            self_toc=self_toc,
            self_sig=self_sig,
            issues=issues,
            peer_cache=peer_cache,
        )

    fixes: list[hero_nav_rules.HeroNavFix] = []
    if is_book_mode and self_sig is not None:
        book_chapter_hrefs = _book_chapter_hrefs(self_sig)
        fixes = hero_nav_rules.collect(
            root=root,
            book_chapter_hrefs=book_chapter_hrefs,
            issues=issues,
        )

    # Apply fixes.
    fixed: list[dict[str, Any]] = []
    if fix and fixes:
        for hf in fixes:
            fixed.extend(hero_nav_rules.apply_fix(hf))
        if fixed:
            new_source = serialize_html(root, original_source=source)
            file_path.write_text(new_source, encoding="utf-8")
            # The hero-nav-redundant issues are reported via `fixed[]`
            # instead of `issues[]` once they've been applied.
            issues = [i for i in issues if i.get("rule") != "hero-nav-redundant"]

    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warn")

    return {
        "file": str(file_path),
        "errors": errors,
        "warnings": warnings,
        "issues": issues,
        "fixed": fixed,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _book_chapter_hrefs(sig: TocSignature) -> set[str]:
    """Set of normalised, local-target hrefs the document's TOC links to."""
    out: set[str] = set()

    def walk(entries: tuple) -> None:
        for entry in entries:
            href = entry.href
            if href is not None and not is_external_href(href):
                s = href.strip()
                if s.startswith("./"):
                    s = s[2:]
                out.add(s)
            walk(entry.children)

    walk(sig.entries)
    return out


def _unreadable_payload(file_path: Path, exc: OSError) -> dict[str, Any]:
    return {
        "file": str(file_path),
        "errors": 1,
        "warnings": 0,
        "issues": [
            {
                "severity": "error",
                "rule": "unreadable-file",
                "message": f"Could not read file: {exc}",
            }
        ],
        "fixed": [],
    }


def _unparseable_payload(file_path: Path, exc: Exception) -> dict[str, Any]:
    return {
        "file": str(file_path),
        "errors": 1,
        "warnings": 0,
        "issues": [
            {
                "severity": "error",
                "rule": "unparseable-html",
                "message": f"Could not parse HTML: {exc}",
            }
        ],
        "fixed": [],
    }


