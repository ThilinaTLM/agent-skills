"""``hero-nav-redundant`` rule + the autofix data it produces.

In book mode the ``<rd-toc>`` block auto-injects prev/next bands at the
top and bottom of every chapter. Hand-written prev/next links inside
``<rd-hero>`` duplicate those bands. The rule catches:

- ``<a>`` children of ``<rd-hero>`` whose href points to another book
  chapter or whose text matches the nav-keyword regex.
- ``Prev:/Previous:/Next:/Up:`` segments inside the hero's ``meta``
  attribute.

``--fix`` strips both. The rule collects ``HeroNavFix`` records during
the walk; the runner later applies them via ``apply_fix``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import lxml.etree as ET

from ...export.common.walker import sourceline_of, text_of
from ..autofix import remove_inline
from ..issues import META_NAV_SEG_RE, META_SEPARATOR, NAV_TEXT_RE, add_issue

__all__ = ["HeroNavFix", "apply_fix", "collect"]


@dataclass
class HeroNavFix:
    """Pending autofix for a single ``<rd-hero>`` element."""

    hero: ET._Element
    anchors: list[ET._Element] = field(default_factory=list)
    meta_segments: list[str] = field(default_factory=list)


def collect(
    *,
    root: ET._Element,
    book_chapter_hrefs: set[str],
    issues: list[dict[str, Any]],
) -> list[HeroNavFix]:
    """Walk every ``<rd-hero>`` and collect violations.

    ``book_chapter_hrefs`` is the set of normalised hrefs that the
    document's own ``<rd-toc>`` lists. Any ``<a>`` inside the hero
    pointing at one of these (or matching the nav-text regex) is
    flagged.
    """
    fixes: list[HeroNavFix] = []
    for hero in root.iter("rd-hero"):
        hero_line = sourceline_of(hero)
        fix = HeroNavFix(hero=hero)

        for child in hero:
            if not isinstance(child.tag, str) or child.tag.lower() != "a":
                continue
            a_href = (child.get("href") or "").strip()
            a_text = " ".join(text_of(child).split())
            href_matches = (
                bool(a_href) and _normalize_href(a_href) in book_chapter_hrefs
            )
            text_matches = bool(a_text) and NAV_TEXT_RE.search(a_text) is not None
            if href_matches or text_matches:
                fix.anchors.append(child)
                add_issue(
                    issues,
                    severity="error",
                    rule="hero-nav-redundant",
                    tag="a",
                    attr="href",
                    line=sourceline_of(child),
                    message=(
                        f"<a> child of <rd-hero> is redundant with the "
                        f"prev/next bands injected by <rd-toc> in book "
                        f"mode (href={a_href!r}, text={a_text!r}). "
                        f"Remove this link; run `richdoc lint --fix` to "
                        f"strip automatically."
                    ),
                )

        meta_value = (hero.get("meta") or "").strip()
        if meta_value:
            segments: list[str] = [
                str(s.strip()) for s in meta_value.split(META_SEPARATOR.strip())
            ]
            redundant: list[str] = [
                s for s in segments if META_NAV_SEG_RE.match(s.strip())
            ]
            if redundant:
                fix.meta_segments = redundant
                add_issue(
                    issues,
                    severity="error",
                    rule="hero-nav-redundant",
                    tag="rd-hero",
                    attr="meta",
                    line=hero_line,
                    message=(
                        "<rd-hero meta> contains 'Prev:/Next:/Up:' segments "
                        "that duplicate the prev/next bands injected by "
                        "<rd-toc>. Remove these segments; run "
                        "`richdoc lint --fix` to strip automatically."
                    ),
                )

        if fix.anchors or fix.meta_segments:
            fixes.append(fix)
    return fixes


def apply_fix(fix: HeroNavFix) -> list[dict[str, Any]]:
    """Mutate the tree to remove the queued anchors / meta segments.

    Returns one ``fixed[]`` envelope entry per fix applied so the
    runner can surface them in the CLI output.
    """
    out: list[dict[str, Any]] = []

    for a in fix.anchors:
        href = (a.get("href") or "").strip()
        out.append(
            {
                "rule": "hero-nav-redundant",
                "tag": "a",
                "line": sourceline_of(a),
                "removed_href": href,
            }
        )
        remove_inline(a)

    if fix.meta_segments:
        meta_value = (fix.hero.get("meta") or "").strip()
        segments = [s.strip() for s in meta_value.split(META_SEPARATOR.strip())]
        kept = [s for s in segments if not META_NAV_SEG_RE.match(s)]
        new_meta = META_SEPARATOR.join(kept).strip()
        if new_meta:
            fix.hero.set("meta", new_meta)
        elif "meta" in fix.hero.attrib:
            del fix.hero.attrib["meta"]
        out.append(
            {
                "rule": "hero-nav-redundant",
                "tag": "rd-hero",
                "attr": "meta",
                "line": sourceline_of(fix.hero),
                "removed_segments": fix.meta_segments,
            }
        )

    return out


def _normalize_href(href: str) -> str:
    """Strip leading ``./`` and surrounding whitespace for set membership.

    Two TOCs with ``./foo.html`` vs ``foo.html`` are intentionally
    different for drift detection (which is literal-block equality),
    but hero-nav matching is about "does this link go to a book
    chapter", which we answer by collapsing.
    """
    s = href.strip()
    if s.startswith("./"):
        s = s[2:]
    return s
