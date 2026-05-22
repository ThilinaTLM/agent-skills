"""Document-level lint rules.

These rules look at the document as a whole rather than at any
individual rd-* element. Currently:

- ``self-closing-custom-element`` (source-text scan; HTML5 doesn't
  honour `<rd-foo ... />` and silently slurps siblings).
- ``missing-css`` / ``missing-js`` \u2014 the required ``<link>`` /
  ``<script>`` are missing from ``<head>``.
- ``missing-rd-page`` / ``multiple-rd-page`` / ``rd-page-not-under-body``
  \u2014 sanity checks on the canonical top-level wrapper.
"""

from __future__ import annotations

from typing import Any

import lxml.etree as ET

from ...export.common.walker import sourceline_of
from ..issues import SELF_CLOSE_RE, add_issue

__all__ = ["check_head_and_page", "check_source_scan"]


def check_source_scan(*, source: str, issues: list[dict[str, Any]]) -> None:
    """Source-text scan for self-closing custom elements (see SELF_CLOSE_RE)."""
    for match in SELF_CLOSE_RE.finditer(source):
        tag = match.group(1).lower()
        line = source[: match.start()].count("\n") + 1
        add_issue(
            issues,
            severity="error",
            rule="self-closing-custom-element",
            tag=tag,
            line=line,
            message=(
                f"<{tag} .../> is parsed as an opening tag with no close \u2014 "
                f"following siblings become children. Write "
                f"<{tag} ...></{tag}> instead."
            ),
        )


def check_head_and_page(*, root: ET._Element, issues: list[dict[str, Any]]) -> None:
    """Verify the required asset links + the single rd-page wrapper."""
    _check_head_links(root, issues)
    _check_rd_page(root, issues)


def _check_head_links(root: ET._Element, issues: list[dict[str, Any]]) -> None:
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
        add_issue(
            issues,
            severity="error",
            rule="missing-css",
            message=(
                "richdoc.css is not linked in <head>. Add: "
                '<link rel="stylesheet" href="./richdoc.css">'
            ),
        )
    if not js_linked:
        add_issue(
            issues,
            severity="error",
            rule="missing-js",
            message=(
                "richdoc.js is not linked in <head>. Add: "
                '<script src="./richdoc.js" defer></script>'
            ),
        )


def _check_rd_page(root: ET._Element, issues: list[dict[str, Any]]) -> None:
    pages = list(root.iter("rd-page"))
    if not pages:
        add_issue(
            issues,
            severity="error",
            rule="missing-rd-page",
            message="Document has no <rd-page>. Wrap your content in <rd-page>.",
        )
        return
    if len(pages) > 1:
        add_issue(
            issues,
            severity="warn",
            rule="multiple-rd-page",
            message=(
                f"Document has {len(pages)} <rd-page> elements; usually "
                "exactly one is expected."
            ),
        )

    for p in pages:
        parent = p.getparent()
        parent_tag = (
            parent.tag if (parent is not None and isinstance(parent.tag, str)) else None
        )
        if parent_tag and parent_tag.lower() != "body":
            add_issue(
                issues,
                severity="warn",
                rule="rd-page-not-under-body",
                tag="rd-page",
                line=sourceline_of(p),
                message=(
                    f"<rd-page> should be directly under <body> (found "
                    f"under <{parent_tag.lower()}>)."
                ),
            )
