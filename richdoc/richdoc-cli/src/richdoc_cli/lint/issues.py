"""Issue helpers + project-wide lint constants.

Every rule writes into a single mutable ``list[dict[str, Any]]``. The
``_add`` helper keeps the shape consistent (severity / rule / message /
optional tag / attr / line / extra fields).

Constants live here so every rule module reaches into one place for
the deprecated-tag map, the always-allowed attribute set, and the
regexes that recognise the various book-mode patterns.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import lxml.etree as ET

__all__ = [
    "ALWAYS_ALLOWED_ATTRS",
    "META_NAV_SEG_RE",
    "META_SEPARATOR",
    "NAV_TEXT_RE",
    "REMOVED_TAGS",
    "SELF_CLOSE_RE",
    "add_issue",
    "iter_elements",
]

# Attributes always allowed on any element \u2014 never reported as unknown.
ALWAYS_ALLOWED_ATTRS = frozenset({"id", "class", "style"})

# Matches `<rd-foo ... />` patterns that look self-closing. HTML5 ignores
# the `/` on non-void custom elements, so the tag stays open and silently
# absorbs following siblings as children. Detect via source-text scan
# because by the time lxml has parsed the doc the damage is invisible.
SELF_CLOSE_RE = re.compile(r"<(rd-[a-z][a-z0-9-]*)\b[^>]*?/\s*>")

# Anchor text that screams "this is a nav link" \u2014 used by hero-nav-redundant.
NAV_TEXT_RE = re.compile(
    r"^\s*(?:[\u2190\u2191\u2192\u2193]|prev(?:ious)?|next|up|home|index)\b",
    re.IGNORECASE,
)

# Segments inside `<rd-hero meta="\u2026">` that duplicate the book's auto-injected
# prev/next bands. The whole segment is stripped on --fix.
META_NAV_SEG_RE = re.compile(
    r"^\s*(prev(?:ious)?|next|up)\s*:",
    re.IGNORECASE,
)

# Separator richdoc uses to join eyebrow \u00b7 lede \u00b7 meta segments.
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


def add_issue(
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
    """Append one issue to the shared list with stable key ordering."""
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


def iter_elements(root: ET._Element) -> Iterator[ET._Element]:
    """Yield every element below root (excluding comments / PIs)."""
    for el in root.iter():
        if isinstance(el.tag, str):
            yield el
