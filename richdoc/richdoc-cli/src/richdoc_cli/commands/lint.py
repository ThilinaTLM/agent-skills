"""`richdoc lint` — validate an HTML file against the rd-* component schema."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import click
import lxml.etree as ET
import lxml.html as LH

from ..output import json_error, json_ok
from ..schema import SchemaLoadError, is_rd_tag, load_schema

# Attributes always allowed on any element — never reported as unknown.
ALWAYS_ALLOWED_ATTRS = frozenset({"id", "class", "style"})

# Matches `<rd-foo ... />` patterns that look self-closing. HTML5 ignores
# the `/` on non-void custom elements, so the tag stays open and silently
# absorbs following siblings as children — the bug that made my paper
# prototype render badly. Detect via source-text scan because by the time
# lxml has parsed the doc the damage is invisible.
SELF_CLOSE_RE = re.compile(r"<(rd-[a-z][a-z0-9-]*)\b[^>]*?/\s*>")

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


def _chapter_title(node: ET._Element) -> str:  # noqa: SLF001
    """Text content of an <rd-chapter>, excluding any nested <rd-chapter>.

    Mirrors the runtime extraction in toc.ts so author-visible text and the
    rendered chapter title stay in sync.
    """
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if isinstance(child.tag, str) and child.tag.lower() == "rd-chapter":
            # Skip nested chapter subtree, but keep its tail text.
            if child.tail:
                parts.append(child.tail)
            continue
        # Walk other child elements: their full text contribution is allowed.
        # `itertext()` is fine here because we only descend through non-
        # chapter elements; nested chapters are still excluded by virtue of
        # the loop above never recursing into them.
        parts.extend(child.itertext())
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split()).strip()


def _add(
    issues: list[dict[str, Any]],
    *,
    severity: str,
    rule: str,
    message: str,
    tag: str | None = None,
    attr: str | None = None,
    line: int | None = None,
) -> None:
    issue: dict[str, Any] = {"severity": severity, "rule": rule, "message": message}
    if tag is not None:
        issue["tag"] = tag
    if attr is not None:
        issue["attr"] = attr
    if line is not None:
        issue["line"] = line
    issues.append(issue)


def _iter_elements(root: ET._Element):  # noqa: SLF001
    """Yield every element below root (excluding comments / PIs)."""
    for el in root.iter():
        # Skip non-Element nodes (lxml uses functions for comments/PIs).
        if isinstance(el.tag, str):
            yield el


@click.command("lint")
@click.argument(
    "file",
    type=click.Path(dir_okay=False, path_type=Path),
)
def cmd(file: Path) -> None:
    """Validate a richdoc .html file against the rd-* component schema."""
    try:
        schema = load_schema()
    except SchemaLoadError as exc:
        json_error(str(exc), code="INPUT_ERROR")

    allowed_tags = set(schema.tags.keys())
    tags_spec = schema.tags

    file_path = file.resolve()
    try:
        source = file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        json_error(f"Could not read file: {exc}", code="INPUT_ERROR")
    except OSError as exc:
        json_error(f"Could not read file: {exc}", code="INPUT_ERROR")

    issues: list[dict[str, Any]] = []

    # Source-level scan for self-closing custom elements. Must happen on
    # the raw text — lxml silently discards the `/` and reparents the
    # following siblings into the would-be-void element, so the bug is
    # invisible once the doc has been parsed.
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
        json_error(f"Could not parse HTML: {exc}", code="INPUT_ERROR")

    # --- Document-level checks ------------------------------------------------

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

    # --- Walk every rd-* element ---------------------------------------------

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

        # Required attributes (missing or empty string treated as missing).
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

        # Unknown attributes (warning) — ignore data-*, id, class, style.
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

        # Enum validation.
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

        # Parent constraint.
        if allowed_parents:
            parent = node.getparent()
            parent_tag = ""
            if parent is not None and isinstance(parent.tag, str):
                parent_tag = parent.tag.lower()
            if parent_tag not in allowed_parents:
                allowed_str = " or ".join(f"<{p}>" for p in allowed_parents)
                _add(
                    issues,
                    severity="error",
                    rule="wrong-parent",
                    tag=tag,
                    line=line,
                    message=f"<{tag}> must be a direct child of {allowed_str} (found inside <{parent_tag or '?'}>).",
                )

        # rd-chapter-specific checks: book mode integrity.
        if tag == "rd-chapter":
            href = node.get("href")
            title = _chapter_title(node)
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
                # Only check relative, file-targeting hrefs. Skip absolute
                # URLs, mailto/tel schemes, and bare fragments.
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

        # rd-callout[type="tldr"] specifically: the host CSS is a 2-col grid.
        # If the author leaves multiple top-level fragments inside the body
        # (text + inline element, multiple elements, ...), each fragment
        # becomes its own grid item and the body cascades across rows instead
        # of flowing as one block in column 2.
        #
        # Newer richdoc.js wraps the body automatically (single _rd-callout-body
        # div = single grid item), so this is a no-op visually for docs shipped
        # with up-to-date assets. The rule still warns to protect docs vendored
        # against an older richdoc.js copy and to nudge authors toward the
        # documented `<p>`-wrap convention.
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

        # Custom-children constraint: only constrains rd-* children; plain HTML
        # children are always allowed.
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

    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warn")

    if errors > 0:
        json_error(
            f"Lint failed: {errors} error{'' if errors == 1 else 's'}, "
            f"{warnings} warning{'' if warnings == 1 else 's'}.",
            code="LINT_ERRORS",
            file=str(file_path),
            errors=errors,
            warnings=warnings,
            issues=issues,
        )

    json_ok(
        file=str(file_path),
        errors=errors,
        warnings=warnings,
        issues=issues,
    )
