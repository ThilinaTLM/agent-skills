"""Per-element rule application.

For every rd-* element in the document, ``check_element`` validates:

- known tag (or one of the migrated-out ``REMOVED_TAGS``)
- required attributes are present and non-empty
- unknown attributes (warned only; ``data-*`` is always allowed)
- enum-constrained attribute values
- ``allowedParents`` declared on the tag spec
- ``customChildren`` declared on the tag spec
- two component-specific micro-rules that didn't fit the generic shape:
  ``rd-callout type=tldr`` body-wrapping and ``rd-chapter`` href / title.

Everything reads from the schema dict produced by ``schema.load_schema``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import lxml.etree as ET

from ...export.book import chapter_title
from ...export.common.walker import sourceline_of
from ...schema import SchemaFile, is_rd_tag
from ..issues import ALWAYS_ALLOWED_ATTRS, REMOVED_TAGS, add_issue

__all__ = ["check_element"]


def check_element(
    *,
    node: ET._Element,
    tag: str,
    schema: SchemaFile,
    allowed_tags: set[str],
    file_path: Path,
    issues: list[dict[str, Any]],
) -> None:
    """Apply every per-element rule to one rd-* node.

    ``tag`` is the lower-cased tag name (pre-validated by the caller as
    starting with ``rd-``).
    """
    line: int | None = sourceline_of(node)
    tags_spec = schema.tags

    if tag not in allowed_tags:
        removed_hint = REMOVED_TAGS.get(tag)
        if removed_hint is not None:
            add_issue(
                issues,
                severity="error",
                rule="removed-tag",
                tag=tag,
                line=line,
                message=(
                    f"<{tag}> was removed from the richdoc vocabulary \u2014 "
                    f"{removed_hint}."
                ),
            )
            return
        add_issue(
            issues,
            severity="error",
            rule="unknown-tag",
            tag=tag,
            line=line,
            message=(
                f"Unknown richdoc tag <{tag}>. Allowed: "
                f"{', '.join(sorted(allowed_tags))}."
            ),
        )
        return

    spec = tags_spec.get(tag, {}) or {}
    required: list[str] = spec.get("required") or []
    optional: list[str] = spec.get("optional") or []
    enums: dict[str, list[str]] = spec.get("enums") or {}
    allowed_parents: list[str] | None = spec.get("allowedParents")
    custom_children = spec.get("customChildren")

    _check_required_attrs(node, tag, required, line, issues)
    _check_unknown_attrs(node, tag, required, optional, line, issues)
    _check_enum_values(node, tag, enums, line, issues)
    if allowed_parents:
        _check_parent(node, tag, allowed_parents, line, issues)

    if tag == "rd-chapter":
        _check_rd_chapter(node, file_path, line, issues)
    if tag == "rd-callout" and (node.get("type") or "") == "tldr":
        _check_rd_callout_tldr(node, line, issues)

    if isinstance(custom_children, list):
        _check_children(node, tag, custom_children, issues)


# ---------------------------------------------------------------------------
# Generic per-attribute / per-child checks
# ---------------------------------------------------------------------------


def _check_required_attrs(
    node: ET._Element,
    tag: str,
    required: list[str],
    line: int | None,
    issues: list[dict[str, Any]],
) -> None:
    for attr in required:
        v = node.get(attr)
        if v is None or v == "":
            add_issue(
                issues,
                severity="error",
                rule="missing-required-attr",
                tag=tag,
                attr=attr,
                line=line,
                message=f"<{tag}> is missing required attribute '{attr}'.",
            )


def _check_unknown_attrs(
    node: ET._Element,
    tag: str,
    required: list[str],
    optional: list[str],
    line: int | None,
    issues: list[dict[str, Any]],
) -> None:
    known = set(required) | set(optional)
    for raw_attr in node.attrib.keys():
        # lxml types attrib keys as `str | bytes`; in practice HTML
        # attributes are always str.
        if not isinstance(raw_attr, str):
            continue
        attr = raw_attr
        if attr.startswith("data-") or attr in ALWAYS_ALLOWED_ATTRS:
            continue
        if attr not in known:
            known_list = ", ".join(sorted(known)) if known else "(none)"
            add_issue(
                issues,
                severity="warn",
                rule="unknown-attr",
                tag=tag,
                attr=attr,
                line=line,
                message=(
                    f"<{tag}> has unknown attribute '{attr}'. Known: {known_list}."
                ),
            )


def _check_enum_values(
    node: ET._Element,
    tag: str,
    enums: dict[str, list[str]],
    line: int | None,
    issues: list[dict[str, Any]],
) -> None:
    for attr, allowed_values in enums.items():
        v = node.get(attr)
        if v is not None and v != "" and v not in allowed_values:
            add_issue(
                issues,
                severity="error",
                rule="invalid-attr-value",
                tag=tag,
                attr=attr,
                line=line,
                message=(
                    f"<{tag} {attr}=\"{v}\"> is invalid. "
                    f"Allowed values: {', '.join(allowed_values)}."
                ),
            )


def _check_parent(
    node: ET._Element,
    tag: str,
    allowed_parents: list[str],
    line: int | None,
    issues: list[dict[str, Any]],
) -> None:
    parent = node.getparent()
    parent_tag_str = ""
    if parent is not None and isinstance(parent.tag, str):
        parent_tag_str = parent.tag.lower()
    if parent_tag_str not in allowed_parents:
        allowed_str = " or ".join(f"<{p}>" for p in allowed_parents)
        add_issue(
            issues,
            severity="error",
            rule="wrong-parent",
            tag=tag,
            line=line,
            message=(
                f"<{tag}> must be a direct child of {allowed_str} "
                f"(found inside <{parent_tag_str or '?'}>)."
            ),
        )


def _check_children(
    node: ET._Element,
    tag: str,
    allowed_children: list[str],
    issues: list[dict[str, Any]],
) -> None:
    for child in node:
        if not isinstance(child.tag, str):
            continue
        ct = child.tag.lower()
        if is_rd_tag(ct) and ct not in allowed_children:
            allowed_str = ", ".join(f"<{c}>" for c in allowed_children)
            add_issue(
                issues,
                severity="error",
                rule="wrong-child",
                tag=tag,
                line=sourceline_of(child),
                message=(
                    f"<{ct}> is not allowed inside <{tag}>. Allowed rd-* "
                    f"children: {allowed_str}."
                ),
            )


# ---------------------------------------------------------------------------
# Component-specific checks
# ---------------------------------------------------------------------------


def _check_rd_chapter(
    node: ET._Element,
    file_path: Path,
    line: int | None,
    issues: list[dict[str, Any]],
) -> None:
    href = node.get("href")
    title = chapter_title(node)
    has_nested = any(
        isinstance(c.tag, str) and c.tag.lower() == "rd-chapter" for c in node
    )
    if not title and not href:
        add_issue(
            issues,
            severity="error",
            rule="rd-chapter-empty",
            tag="rd-chapter",
            line=line,
            message="<rd-chapter> needs at least a title (text content) or an href.",
        )
    elif not title and not has_nested:
        add_issue(
            issues,
            severity="warn",
            rule="rd-chapter-empty",
            tag="rd-chapter",
            line=line,
            message="<rd-chapter> has an href but no visible title text.",
        )
    if href:
        parts = urlsplit(href)
        if not parts.scheme and not parts.netloc and parts.path:
            target = (file_path.parent / parts.path).resolve()
            if not target.exists():
                add_issue(
                    issues,
                    severity="warn",
                    rule="rd-chapter-href-missing",
                    tag="rd-chapter",
                    attr="href",
                    line=line,
                    message=(
                        f"<rd-chapter href=\"{href}\"> points to a file that "
                        f"does not exist relative to this document: {target}."
                    ),
                )


def _check_rd_callout_tldr(
    node: ET._Element,
    line: int | None,
    issues: list[dict[str, Any]],
) -> None:
    """`rd-callout type=tldr` lays children out as a grid; the body
    should be a single block."""
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
        add_issue(
            issues,
            severity="warn",
            rule="block-body-required",
            tag="rd-callout",
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
