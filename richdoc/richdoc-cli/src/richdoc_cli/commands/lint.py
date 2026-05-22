"""`richdoc lint` — validate an HTML file (or directory of files) against
the rd-* component schema and book-mode authoring rules.

Single file → returns a `file` / `errors` / `warnings` / `issues` envelope.
Directory  → walks every `*.html` child and aggregates into a `files[]`
array with the same per-file shape. The lint helpers are also exported
as `lint_path(path, *, fix=False)` so `richdoc publish confluence push`
can run the same checks before any network call.

The `--fix` flag autofixes the `hero-nav-redundant` rule (strips legacy
`<a>` children and `Prev:/Next:/Up:` segments from the hero's `meta`
attribute when book mode is active). Book-mode TOC drift is reported
but never autofixed — the agent reconciles the canonical block manually.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import click
import lxml.etree as ET
import lxml.html as LH

from ..export.book import (
    TocSignature,
    TocSignatureEntry,
    chapter_title,
    find_book_toc,
    is_external_href,
    linked_chapter_paths,
    toc_signature,
)
from ..output import json_error, json_ok
from ..schema import SchemaLoadError, is_rd_tag, load_schema

# Attributes always allowed on any element — never reported as unknown.
ALWAYS_ALLOWED_ATTRS = frozenset({"id", "class", "style"})

# Matches `<rd-foo ... />` patterns that look self-closing. HTML5 ignores
# the `/` on non-void custom elements, so the tag stays open and silently
# absorbs following siblings as children. Detect via source-text scan
# because by the time lxml has parsed the doc the damage is invisible.
SELF_CLOSE_RE = re.compile(r"<(rd-[a-z][a-z0-9-]*)\b[^>]*?/\s*>")

# Anchor text that screams "this is a nav link" — used by hero-nav-redundant.
NAV_TEXT_RE = re.compile(
    r"^\s*(?:[\u2190\u2191\u2192\u2193]|prev(?:ious)?|next|up|home|index)\b",
    re.IGNORECASE,
)

# Segments inside `<rd-hero meta="…">` that duplicate the book's auto-injected
# prev/next bands. The whole segment is stripped on --fix.
META_NAV_SEG_RE = re.compile(
    r"^\s*(prev(?:ious)?|next|up)\s*:",
    re.IGNORECASE,
)

# Separator richdoc uses to join eyebrow · lede · meta segments.
META_SEPARATOR = " \u00b7 "

# Tags removed from the vocabulary. When seen in a doc, the linter
# emits a `removed-tag` error pointing at the replacement so authors
# get a clear migration path.
REMOVED_TAGS: dict[str, str] = {
    "rd-mermaid": 'use <rd-diagram lang="mermaid">',
    "rd-plantuml": 'use <rd-diagram lang="plantuml">',
    "rd-swatch": "removed; render the chip inline or with <rd-card>",
    "rd-gallery": "removed; use <rd-cols> of <rd-figure>",
    "rd-shot": "removed; child of <rd-gallery> (also removed) \u2014 use <rd-figure>",
    "rd-embed": "removed; use <iframe> inside <rd-figure>",
    "rd-tooltip": 'removed; use inline prose or <rd-detail variant="question">',
    "rd-tree": "removed; nest <rd-detail> elements or use a <ul>",
    "rd-node": "removed; child of <rd-tree> (also removed)",
    "rd-roadmap": "removed; use <rd-compare> or an embedded image",
    "rd-lane": "removed; child of <rd-roadmap> (also removed)",
    "rd-item": "removed; child of <rd-lane> (also removed)",
    "rd-quote": "removed; use <blockquote> (styled automatically)",
    "rd-footnote": 'removed; use <rd-cite key="\u2026"> with <rd-ref>',
}


# ---------------------------------------------------------------------------
# Issue helpers
# ---------------------------------------------------------------------------


def _add(
    issues: list[dict[str, Any]],
    *,
    severity: str,
    rule: str,
    message: str,
    tag: str | None = None,
    attr: str | None = None,
    line: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    issue: dict[str, Any] = {"severity": severity, "rule": rule, "message": message}
    if tag is not None:
        issue["tag"] = tag
    if attr is not None:
        issue["attr"] = attr
    if line is not None:
        issue["line"] = line
    if extra:
        issue.update(extra)
    issues.append(issue)


def _iter_elements(root: ET._Element):  # noqa: SLF001
    """Yield every element below root (excluding comments / PIs)."""
    for el in root.iter():
        if isinstance(el.tag, str):
            yield el


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------


@click.command("lint")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--fix",
    "fix",
    is_flag=True,
    default=False,
    help="Autofix supported rules in place. Currently only "
    "`hero-nav-redundant` (strip legacy <a> children + meta nav segments "
    "from <rd-hero> in book mode). Book-mode TOC drift is never autofixed.",
)
def cmd(path: Path, fix: bool) -> None:
    """Validate richdoc HTML against the rd-* schema and book-mode rules."""
    try:
        result = lint_path(path, fix=fix)
    except SchemaLoadError as exc:
        json_error(str(exc), code="INPUT_ERROR")
    except OSError as exc:
        json_error(f"Could not read input: {exc}", code="INPUT_ERROR")

    errors = result["errors"]
    warnings = result["warnings"]
    if errors > 0:
        json_error(
            f"Lint failed: {errors} error{'' if errors == 1 else 's'}, "
            f"{warnings} warning{'' if warnings == 1 else 's'}.",
            code="LINT_ERRORS",
            **result,
        )
    json_ok(**result)


# ---------------------------------------------------------------------------
# Public entry — used by `cmd` above and by `publish confluence push`
# ---------------------------------------------------------------------------


def lint_path(path: Path, *, fix: bool = False) -> dict[str, Any]:
    """Lint a single .html file or a directory of them.

    Returns an envelope payload (a dict that is structurally identical for
    success and error — the caller decides which `json_*` to emit based on
    `result['errors']`).

    Single file:  {"file": ..., "errors": N, "warnings": M, "issues": [...], "fixed": [...]}
    Directory:    {"path": ..., "files": [...], "errors": N, "warnings": M, "fixed": [...]}
    """
    schema = load_schema()
    resolved = path.resolve()
    peer_cache: dict[Path, _PeerInfo | None] = {}

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
# Per-file lint
# ---------------------------------------------------------------------------


class _PeerInfo:
    """Cached parse of a peer chapter file. `None` means unreadable."""

    __slots__ = ("source", "root", "toc_sig")

    def __init__(self, source: str, root: ET._Element, toc_sig: TocSignature | None) -> None:  # noqa: SLF001
        self.source = source
        self.root = root
        self.toc_sig = toc_sig


def _lint_file(
    file_path: Path,
    schema,  # noqa: ANN001
    *,
    fix: bool,
    peer_cache: dict[Path, _PeerInfo | None],
) -> dict[str, Any]:
    """Lint a single file. Returns the per-file envelope payload."""
    file_path = file_path.resolve()
    allowed_tags = set(schema.tags.keys())
    tags_spec = schema.tags

    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as exc:
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

    issues: list[dict[str, Any]] = []

    # Source-level scan for self-closing custom elements (see top of file).
    for match in SELF_CLOSE_RE.finditer(source):
        tag = match.group(1).lower()
        line = source[: match.start()].count("\n") + 1
        _add(
            issues,
            severity="error",
            rule="self-closing-custom-element",
            tag=tag,
            line=line,
            message=(
                f"<{tag} .../> is parsed as an opening tag with no close — "
                f"following siblings become children. Write "
                f"<{tag} ...></{tag}> instead."
            ),
        )

    parser = LH.HTMLParser(recover=True)
    try:
        root = LH.document_fromstring(source, parser=parser)
    except (ET.ParserError, ValueError) as exc:
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

    # --- Document-level checks ----------------------------------------------

    head = root.find(".//head")
    css_linked = False
    js_linked = False
    if head is not None:
        for link in head.iter("link"):
            rel = (link.get("rel") or "").lower()
            href = (link.get("href") or "").lower()
            if rel == "stylesheet" and "richdoc.css" in href:
                css_linked = True
                break
        for script in head.iter("script"):
            src = (script.get("src") or "").lower()
            if "richdoc.js" in src:
                js_linked = True
                break

    if not css_linked:
        _add(
            issues,
            severity="error",
            rule="missing-css",
            message='richdoc.css is not linked in <head>. Add: <link rel="stylesheet" href="./richdoc.css">',
        )
    if not js_linked:
        _add(
            issues,
            severity="error",
            rule="missing-js",
            message='richdoc.js is not linked in <head>. Add: <script src="./richdoc.js" defer></script>',
        )

    pages = list(root.iter("rd-page"))
    if not pages:
        _add(
            issues,
            severity="error",
            rule="missing-rd-page",
            message="Document has no <rd-page>. Wrap your content in <rd-page>.",
        )
    elif len(pages) > 1:
        _add(
            issues,
            severity="warn",
            rule="multiple-rd-page",
            message=f"Document has {len(pages)} <rd-page> elements; usually exactly one is expected.",
        )

    for p in pages:
        parent = p.getparent()
        parent_tag = parent.tag if (parent is not None and isinstance(parent.tag, str)) else None
        if parent_tag and parent_tag.lower() != "body":
            _add(
                issues,
                severity="warn",
                rule="rd-page-not-under-body",
                tag="rd-page",
                line=p.sourceline,
                message=f"<rd-page> should be directly under <body> (found under <{parent_tag.lower()}>).",
            )

    # --- Walk every rd-* element --------------------------------------------

    for node in _iter_elements(root):
        tag_raw = node.tag
        if not isinstance(tag_raw, str):
            continue
        tag = tag_raw.lower()
        if not is_rd_tag(tag):
            continue

        line = node.sourceline

        if tag not in allowed_tags:
            removed_hint = REMOVED_TAGS.get(tag)
            if removed_hint is not None:
                _add(
                    issues,
                    severity="error",
                    rule="removed-tag",
                    tag=tag,
                    line=line,
                    message=f"<{tag}> was removed from the richdoc vocabulary — {removed_hint}.",
                )
                continue
            _add(
                issues,
                severity="error",
                rule="unknown-tag",
                tag=tag,
                line=line,
                message=f"Unknown richdoc tag <{tag}>. Allowed: {', '.join(sorted(allowed_tags))}.",
            )
            continue

        spec = tags_spec.get(tag, {}) or {}
        required = spec.get("required") or []
        optional = spec.get("optional") or []
        enums = spec.get("enums") or {}
        allowed_parents = spec.get("allowedParents")
        custom_children = spec.get("customChildren")

        for attr in required:
            v = node.get(attr)
            if v is None or v == "":
                _add(
                    issues,
                    severity="error",
                    rule="missing-required-attr",
                    tag=tag,
                    attr=attr,
                    line=line,
                    message=f"<{tag}> is missing required attribute '{attr}'.",
                )

        known = set(required) | set(optional)
        for attr in node.attrib.keys():
            if attr.startswith("data-") or attr in ALWAYS_ALLOWED_ATTRS:
                continue
            if attr not in known:
                known_list = ", ".join(sorted(known)) if known else "(none)"
                _add(
                    issues,
                    severity="warn",
                    rule="unknown-attr",
                    tag=tag,
                    attr=attr,
                    line=line,
                    message=f"<{tag}> has unknown attribute '{attr}'. Known: {known_list}.",
                )

        for attr, allowed_values in enums.items():
            v = node.get(attr)
            if v is not None and v != "" and v not in allowed_values:
                _add(
                    issues,
                    severity="error",
                    rule="invalid-attr-value",
                    tag=tag,
                    attr=attr,
                    line=line,
                    message=f"<{tag} {attr}=\"{v}\"> is invalid. Allowed values: {', '.join(allowed_values)}.",
                )

        if allowed_parents:
            parent = node.getparent()
            parent_tag_str = ""
            if parent is not None and isinstance(parent.tag, str):
                parent_tag_str = parent.tag.lower()
            if parent_tag_str not in allowed_parents:
                allowed_str = " or ".join(f"<{p}>" for p in allowed_parents)
                _add(
                    issues,
                    severity="error",
                    rule="wrong-parent",
                    tag=tag,
                    line=line,
                    message=f"<{tag}> must be a direct child of {allowed_str} (found inside <{parent_tag_str or '?'}>).",
                )

        if tag == "rd-chapter":
            href = node.get("href")
            title = chapter_title(node)
            has_nested = any(
                isinstance(c.tag, str) and c.tag.lower() == "rd-chapter" for c in node
            )
            if not title and not href:
                _add(
                    issues,
                    severity="error",
                    rule="rd-chapter-empty",
                    tag=tag,
                    line=line,
                    message="<rd-chapter> needs at least a title (text content) or an href.",
                )
            elif not title and not has_nested:
                _add(
                    issues,
                    severity="warn",
                    rule="rd-chapter-empty",
                    tag=tag,
                    line=line,
                    message="<rd-chapter> has an href but no visible title text.",
                )
            if href:
                parts = urlsplit(href)
                if not parts.scheme and not parts.netloc and parts.path:
                    target = (file_path.parent / parts.path).resolve()
                    if not target.exists():
                        _add(
                            issues,
                            severity="warn",
                            rule="rd-chapter-href-missing",
                            tag=tag,
                            attr="href",
                            line=line,
                            message=(
                                f"<rd-chapter href=\"{href}\"> points to a file that does "
                                f"not exist relative to this document: {target}."
                            ),
                        )

        if tag == "rd-callout" and (node.get("type") or "") == "tldr":
            grid_items = 0
            if (node.text or "").strip():
                grid_items += 1
            for child in node:
                if not isinstance(child.tag, str):
                    continue
                grid_items += 1
                if (child.tail or "").strip():
                    grid_items += 1
            if grid_items > 1:
                _add(
                    issues,
                    severity="warn",
                    rule="block-body-required",
                    tag=tag,
                    line=line,
                    message=(
                        '<rd-callout type="tldr"> has multiple top-level body '
                        "fragments. Wrap the body in a single <p>\u2026</p> so each "
                        "fragment isn't laid out as its own grid cell. (Newer "
                        "richdoc.js wraps the body automatically; this warning "
                        "protects docs shipped with an older copy of the asset \u2014 "
                        "refresh with `richdoc update`.)"
                    ),
                )

        if isinstance(custom_children, list):
            allowed_children = list(custom_children)
            for child in node:
                if not isinstance(child.tag, str):
                    continue
                ct = child.tag.lower()
                if is_rd_tag(ct) and ct not in allowed_children:
                    allowed_str = ", ".join(f"<{c}>" for c in allowed_children)
                    _add(
                        issues,
                        severity="error",
                        rule="wrong-child",
                        tag=tag,
                        line=child.sourceline,
                        message=f"<{ct}> is not allowed inside <{tag}>. Allowed rd-* children: {allowed_str}.",
                    )

    # --- Book-mode checks ---------------------------------------------------

    self_toc = find_book_toc(root)
    is_book_mode = self_toc is not None
    self_sig = toc_signature(self_toc) if self_toc is not None else None
    book_chapter_hrefs: set[str] = set()
    if self_sig is not None:
        for href in _flat_hrefs(self_sig.entries):
            if href is not None and not is_external_href(href):
                book_chapter_hrefs.add(_normalize_href(href))

    if is_book_mode and self_sig is not None and self_toc is not None:
        _check_book_toc_drift(
            file_path=file_path,
            self_toc=self_toc,
            self_sig=self_sig,
            issues=issues,
            peer_cache=peer_cache,
        )

    # Hero-nav-redundant + autofix tracking.
    fixes_to_apply: list[_HeroNavFix] = []
    if is_book_mode:
        for hero in root.iter("rd-hero"):
            hero_line = hero.sourceline
            redundant_anchors: list[ET._Element] = []  # noqa: SLF001
            for child in hero:
                if not isinstance(child.tag, str):
                    continue
                if child.tag.lower() != "a":
                    continue
                a_href = (child.get("href") or "").strip()
                a_text = " ".join("".join(child.itertext()).split())
                href_matches = (
                    bool(a_href)
                    and _normalize_href(a_href) in book_chapter_hrefs
                )
                text_matches = bool(a_text) and NAV_TEXT_RE.search(a_text) is not None
                if href_matches or text_matches:
                    redundant_anchors.append(child)
                    _add(
                        issues,
                        severity="error",
                        rule="hero-nav-redundant",
                        tag="a",
                        attr="href",
                        line=child.sourceline,
                        message=(
                            f"<a> child of <rd-hero> is redundant with the prev/next "
                            f"bands injected by <rd-toc> in book mode (href={a_href!r}, "
                            f"text={a_text!r}). Remove this link; run "
                            f"`richdoc lint --fix` to strip automatically."
                        ),
                    )

            meta_value = (hero.get("meta") or "").strip()
            redundant_meta_segments: list[str] = []
            if meta_value:
                segments = [s.strip() for s in meta_value.split(META_SEPARATOR.strip())]
                for seg in segments:
                    if META_NAV_SEG_RE.match(seg.strip()):
                        redundant_meta_segments.append(seg)
                if redundant_meta_segments:
                    _add(
                        issues,
                        severity="error",
                        rule="hero-nav-redundant",
                        tag="rd-hero",
                        attr="meta",
                        line=hero_line,
                        message=(
                            "<rd-hero meta> contains 'Prev:/Next:/Up:' segments "
                            "that duplicate the prev/next bands injected by <rd-toc>. "
                            "Remove these segments; run `richdoc lint --fix` to "
                            "strip automatically."
                        ),
                    )

            if redundant_anchors or redundant_meta_segments:
                fixes_to_apply.append(
                    _HeroNavFix(
                        hero=hero,
                        anchors=redundant_anchors,
                        meta_segments=redundant_meta_segments,
                    )
                )

    # --- Apply fixes --------------------------------------------------------

    fixed: list[dict[str, Any]] = []
    if fix and fixes_to_apply:
        changed = False
        for hf in fixes_to_apply:
            for a in hf.anchors:
                _remove_inline(a)
                fixed.append(
                    {
                        "rule": "hero-nav-redundant",
                        "tag": "a",
                        "line": a.sourceline,
                        "removed_href": (a.get("href") or "").strip(),
                    }
                )
                changed = True
            if hf.meta_segments:
                meta_value = (hf.hero.get("meta") or "").strip()
                segments = [s.strip() for s in meta_value.split(META_SEPARATOR.strip())]
                kept = [s for s in segments if not META_NAV_SEG_RE.match(s)]
                new_meta = META_SEPARATOR.join(kept).strip()
                if new_meta:
                    hf.hero.set("meta", new_meta)
                else:
                    if "meta" in hf.hero.attrib:
                        del hf.hero.attrib["meta"]
                fixed.append(
                    {
                        "rule": "hero-nav-redundant",
                        "tag": "rd-hero",
                        "attr": "meta",
                        "line": hf.hero.sourceline,
                        "removed_segments": hf.meta_segments,
                    }
                )
                changed = True

        if changed:
            new_source = _serialize_html(root, original_source=source)
            file_path.write_text(new_source, encoding="utf-8")
            # Re-drop any hero-nav-redundant issues that were fixed; they're
            # surfaced in `fixed[]` instead.
            issues = [
                i for i in issues if i.get("rule") != "hero-nav-redundant"
            ]

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
# Book-mode helpers (drift + hero-nav)
# ---------------------------------------------------------------------------


class _HeroNavFix:
    __slots__ = ("hero", "anchors", "meta_segments")

    def __init__(
        self,
        hero: ET._Element,  # noqa: SLF001
        anchors: list[ET._Element],  # noqa: SLF001
        meta_segments: list[str],
    ) -> None:
        self.hero = hero
        self.anchors = anchors
        self.meta_segments = meta_segments


def _flat_hrefs(entries: tuple[TocSignatureEntry, ...]):
    for entry in entries:
        yield entry.href
        yield from _flat_hrefs(entry.children)


def _normalize_href(href: str) -> str:
    """Normalise a relative href for set membership.

    Two TOCs with `./foo.html` vs `foo.html` are intentionally different
    for drift detection (that's literal-block equality), but hero-nav
    matching is about "does this link go to a book chapter," which we
    answer by stripping leading `./` and collapsing whitespace.
    """
    s = href.strip()
    if s.startswith("./"):
        s = s[2:]
    return s


def _check_book_toc_drift(
    *,
    file_path: Path,
    self_toc: ET._Element,  # noqa: SLF001
    self_sig: TocSignature,
    issues: list[dict[str, Any]],
    peer_cache: dict[Path, _PeerInfo | None],
) -> None:
    """Emit `book-toc-drift` errors for any linked chapter whose own
    `<rd-toc>` block does not match this file's signature.
    """
    for target_path, raw_href in linked_chapter_paths(file_path, self_sig):
        if target_path == file_path:
            continue
        if not target_path.exists():
            # Already covered by `rd-chapter-href-missing` warning.
            continue

        peer = _load_peer(target_path, peer_cache)
        if peer is None:
            _add(
                issues,
                severity="warn",
                rule="book-peer-unreadable",
                tag="rd-toc",
                line=self_toc.sourceline,
                attr="href",
                message=(
                    f"Could not read or parse linked chapter {raw_href!r} "
                    "to verify <rd-toc> consistency."
                ),
            )
            continue

        if peer.toc_sig is None:
            _add(
                issues,
                severity="error",
                rule="book-toc-drift",
                tag="rd-toc",
                line=self_toc.sourceline,
                message=(
                    f"Chapter {raw_href!r} has no <rd-toc> block of its own, "
                    "but this file's <rd-toc> lists it as part of a book. "
                    "Copy this file's <rd-toc> block verbatim into every "
                    "chapter (book-mode contract)."
                ),
                extra={"peer": raw_href},
            )
            continue

        diff = _signature_diff(
            self_sig,
            peer.toc_sig,
            expected_dir=file_path.parent,
            actual_dir=target_path.parent,
        )
        if diff:
            _add(
                issues,
                severity="error",
                rule="book-toc-drift",
                tag="rd-toc",
                line=self_toc.sourceline,
                message=(
                    f"<rd-toc> in {raw_href!r} differs from this file's "
                    "<rd-toc>. Every chapter in a richdoc book must point "
                    "at the same chapters in the same order (relative href "
                    "strings may differ across subdirectories, but they "
                    "must resolve to the same files). Reconcile manually — "
                    "`richdoc lint --fix` does not autofix this rule."
                ),
                extra={"peer": raw_href, "diff": diff},
            )


def _load_peer(
    path: Path, peer_cache: dict[Path, _PeerInfo | None]
) -> _PeerInfo | None:
    if path in peer_cache:
        return peer_cache[path]
    try:
        text = path.read_text(encoding="utf-8")
        parser = LH.HTMLParser(recover=True)
        root = LH.document_fromstring(text, parser=parser)
    except (OSError, ET.ParserError, ValueError):
        peer_cache[path] = None
        return None
    toc = find_book_toc(root)
    if toc is not None:
        sig = toc_signature(toc)
    else:
        # Fall back to *any* rd-toc (chapters without hrefs are still a toc).
        any_toc = next(iter(root.iter("rd-toc")), None)
        sig = toc_signature(any_toc) if any_toc is not None else None
    info = _PeerInfo(source=text, root=root, toc_sig=sig)
    peer_cache[path] = info
    return info


def _signature_diff(
    expected: TocSignature,
    actual: TocSignature,
    *,
    expected_dir: Path,
    actual_dir: Path,
) -> list[dict[str, Any]]:
    """Produce a small structured diff between two TOC signatures.

    Hrefs are compared by resolved filesystem path, not raw string — a
    chapter at the book root may use `./other.html` while a chapter in a
    subdirectory uses `../other.html` for the same target. The raw
    strings are surfaced in `detail` so the agent can see which side
    needs updating.

    Each entry is `{"kind": "...", "path": "0/2/1", "detail": "..."}`.
    The path is the index path through the chapter tree.
    """
    out: list[dict[str, Any]] = []
    if expected.title != actual.title:
        out.append(
            {
                "kind": "changed",
                "path": "",
                "detail": f"rd-toc[title]: {expected.title!r} → {actual.title!r}",
            }
        )

    def resolve(href: str | None, base: Path) -> tuple[str, str]:
        """Return (resolved_key, display_string) for comparison."""
        if href is None:
            return ("", "")
        if is_external_href(href):
            return (href.strip(), href)
        return (str((base / href).resolve()), href)

    def walk(
        exp: tuple[TocSignatureEntry, ...],
        act: tuple[TocSignatureEntry, ...],
        prefix: str,
    ) -> None:
        for idx, (e, a) in enumerate(zip(exp, act)):
            here = f"{prefix}{idx}"
            e_key, e_display = resolve(e.href, expected_dir)
            a_key, a_display = resolve(a.href, actual_dir)
            if e_key != a_key:
                out.append(
                    {
                        "kind": "changed",
                        "path": here,
                        "detail": f"href target: {e_display!r} → {a_display!r}",
                    }
                )
            if e.title != a.title:
                out.append(
                    {
                        "kind": "changed",
                        "path": here,
                        "detail": f"title: {e.title!r} → {a.title!r}",
                    }
                )
            walk(e.children, a.children, here + "/")
        if len(exp) > len(act):
            for idx in range(len(act), len(exp)):
                e = exp[idx]
                out.append(
                    {
                        "kind": "removed",
                        "path": f"{prefix}{idx}",
                        "detail": f"missing: href={e.href!r} title={e.title!r}",
                    }
                )
        elif len(act) > len(exp):
            for idx in range(len(exp), len(act)):
                a = act[idx]
                out.append(
                    {
                        "kind": "added",
                        "path": f"{prefix}{idx}",
                        "detail": f"extra: href={a.href!r} title={a.title!r}",
                    }
                )

    walk(expected.entries, actual.entries, "")
    return out


# ---------------------------------------------------------------------------
# Source rewrite (for --fix)
# ---------------------------------------------------------------------------


def _remove_inline(node: ET._Element) -> None:  # noqa: SLF001
    """Remove `node` from its parent.

    Whitespace-only tail text is dropped — the surviving parent.text /
    previous-sibling .tail already carries the indentation gap between
    the surrounding elements, so migrating the tail would leave a blank
    indented line behind for every removed node.

    Non-whitespace tail text is migrated onto the previous sibling (or
    onto parent.text if `node` was the first child) so author-visible
    text is not silently lost.
    """
    parent = node.getparent()
    if parent is None:
        return
    tail = node.tail or ""
    if tail.strip():
        prev = node.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail
    parent.remove(node)


_BLANK_LINE_RUN_RE = re.compile(r"(?:[ \t]*\n){3,}")


def _serialize_html(root: ET._Element, *, original_source: str) -> str:  # noqa: SLF001
    """Serialise the modified tree back to HTML.

    Preserves the original doctype declaration, collapses runs of 3+
    blank lines (a side effect of consecutive sibling removals) to a
    single blank line, and restores the trailing newline if the source
    had one.
    """
    body = LH.tostring(root, encoding="unicode", method="html")
    doctype = ""
    head = original_source[:512].lstrip()
    if head.lower().startswith("<!doctype"):
        end = original_source.find(">", 0, 512)
        if end != -1:
            doctype = original_source[: end + 1] + "\n"
    out = doctype + body
    out = _BLANK_LINE_RUN_RE.sub("\n\n", out)
    if original_source.endswith("\n") and not out.endswith("\n"):
        out += "\n"
    return out
