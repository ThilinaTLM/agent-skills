"""``book-toc-drift`` rule.

When this file lists other chapters in its ``<rd-toc>``, every linked
chapter on disk must carry the same TOC block. Mismatches surface as
``book-toc-drift`` errors with a structured per-entry ``diff[]``:
each item gives an index path through the chapter tree and a short
detail string explaining what changed.

The check is **never autofixed**: the agent reconciles the canonical
block manually after reviewing the diff.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lxml.etree as ET
import lxml.html as LH

from ...export.book import (
    TocSignature,
    TocSignatureEntry,
    find_book_toc,
    is_external_href,
    linked_chapter_paths,
    toc_signature,
)
from ...export.common.walker import sourceline_of
from ..issues import add_issue

__all__ = ["PeerInfo", "check_drift"]


@dataclass
class PeerInfo:
    """Cached parse of a peer chapter file."""

    source: str
    root: ET._Element
    toc_sig: TocSignature | None


def check_drift(
    *,
    file_path: Path,
    self_toc: ET._Element,
    self_sig: TocSignature,
    issues: list[dict[str, Any]],
    peer_cache: dict[Path, PeerInfo | None],
) -> None:
    """Emit ``book-toc-drift`` errors for every chapter whose own
    ``<rd-toc>`` differs from this file's signature."""
    self_toc_line = sourceline_of(self_toc)

    for target_path, raw_href in linked_chapter_paths(file_path, self_sig):
        if target_path == file_path:
            continue
        if not target_path.exists():
            # Already covered by `rd-chapter-href-missing`.
            continue

        peer = _load_peer(target_path, peer_cache)
        if peer is None:
            add_issue(
                issues,
                severity="warn",
                rule="book-peer-unreadable",
                tag="rd-toc",
                line=self_toc_line,
                attr="href",
                message=(
                    f"Could not read or parse linked chapter {raw_href!r} "
                    "to verify <rd-toc> consistency."
                ),
            )
            continue

        if peer.toc_sig is None:
            add_issue(
                issues,
                severity="error",
                rule="book-toc-drift",
                tag="rd-toc",
                line=self_toc_line,
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
            add_issue(
                issues,
                severity="error",
                rule="book-toc-drift",
                tag="rd-toc",
                line=self_toc_line,
                message=(
                    f"<rd-toc> in {raw_href!r} differs from this file's "
                    "<rd-toc>. Every chapter in a richdoc book must point "
                    "at the same chapters in the same order (relative href "
                    "strings may differ across subdirectories, but they "
                    "must resolve to the same files). Reconcile manually \u2014 "
                    "`richdoc lint --fix` does not autofix this rule."
                ),
                extra={"peer": raw_href, "diff": diff},
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_peer(
    path: Path,
    peer_cache: dict[Path, PeerInfo | None],
) -> PeerInfo | None:
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
    sig: TocSignature | None
    if toc is not None:
        sig = toc_signature(toc)
    else:
        # Fall back to *any* rd-toc (chapters without hrefs are still a toc).
        any_toc = next(iter(root.iter("rd-toc")), None)
        sig = toc_signature(any_toc) if any_toc is not None else None
    info = PeerInfo(source=text, root=root, toc_sig=sig)
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

    Hrefs compare by resolved filesystem target so ``./other.html`` and
    ``../other.html`` from different chapter directories are
    equivalent. Raw strings are surfaced in ``detail`` so the agent
    can see which side needs updating.

    Each entry is ``{"kind": "...", "path": "0/2/1", "detail": "..."}``.
    The ``path`` is the index path through the chapter tree.
    """
    out: list[dict[str, Any]] = []
    if expected.title != actual.title:
        out.append(
            {
                "kind": "changed",
                "path": "",
                "detail": f"rd-toc[title]: {expected.title!r} \u2192 {actual.title!r}",
            }
        )

    def resolve(href: str | None, base: Path) -> tuple[str, str]:
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
        # zip(strict=False) is intentional \u2014 the per-length tail of the
        # longer list is reported as added/removed below.
        for idx, (e, a) in enumerate(zip(exp, act, strict=False)):
            here = f"{prefix}{idx}"
            e_key, e_display = resolve(e.href, expected_dir)
            a_key, a_display = resolve(a.href, actual_dir)
            if e_key != a_key:
                out.append(
                    {
                        "kind": "changed",
                        "path": here,
                        "detail": f"href target: {e_display!r} \u2192 {a_display!r}",
                    }
                )
            if e.title != a.title:
                out.append(
                    {
                        "kind": "changed",
                        "path": here,
                        "detail": f"title: {e.title!r} \u2192 {a.title!r}",
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
