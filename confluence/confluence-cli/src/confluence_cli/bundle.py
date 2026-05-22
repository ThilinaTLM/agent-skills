"""Reader for the ``richdoc.confluence.bundle.v1`` on-disk format.

This module deliberately mirrors the shape produced by
``richdoc export confluence`` (see the richdoc skill) **without**
importing anything from ``richdoc_cli``: the two skills communicate
only through the manifest schema. Keeping the reader independent
means the ``confluence`` skill can publish bundles produced by other
tools too, as long as they conform to the schema.

Schema (``richdoc.confluence.bundle.v1``)::

    <bundle_dir>/
      manifest.json
      pages/
        <safe>.storage.xml
      attachments/
        <filename>

``manifest.json``::

    {
      "schema": "richdoc.confluence.bundle.v1",
      "createdBy": "richdoc-cli 0.x",
      "input": "/abs/source.html",
      "book": true,
      "pages": [
        {
          "key": "index.html",
          "source": "index.html",
          "title": "Overview",
          "parentKey": null,
          "storage": "pages/index.storage.xml",
          "attachments": [
            {"token": "@@ATTACHMENT:diag:abc123@@",
             "filename": "diag-abc123.png",
             "path": "attachments/diag-abc123.png",
             "mime": "image/png",
             "align": "center",
             "inline": false}
          ],
          "links": [
            {"token": "@@RICHDOC_PAGE_URL:chapter-1.html@@",
             "targetKey": "chapter-1.html"}
          ],
          "dropped": [],
          "missing": []
        }
      ],
      "summary": {"attachments": 1, "diagramsRendered": 0,
                  "diagramsFailed": 0, "mathRendered": 0, "mathFailed": 0}
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

BUNDLE_SCHEMA = "richdoc.confluence.bundle.v1"
MANIFEST_FILENAME = "manifest.json"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleAttachment:
    token: str
    filename: str
    path: str
    mime: str
    align: str = "center"
    inline: bool = False


@dataclass(frozen=True)
class BundleLink:
    token: str
    target_key: str


@dataclass
class BundlePage:
    key: str
    source: str
    title: str
    parent_key: str | None
    storage_path: str
    attachments: list[BundleAttachment] = field(default_factory=list)
    links: list[BundleLink] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class BundleManifest:
    bundle_dir: Path
    schema: str
    created_by: str
    input_path: str
    book: bool
    pages: list[BundlePage]


class BundleError(RuntimeError):
    """Raised on malformed bundles or unsafe paths."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "INVALID_BUNDLE",
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def read_bundle(bundle_dir: Path) -> BundleManifest:
    """Load and validate a bundle's manifest.

    Performs structural validation only; storage XML and attachment
    bytes stay on disk and are read by the consumer on demand. Path
    traversal is rejected: every ``storage`` and ``attachments[].path``
    must resolve inside ``bundle_dir``.
    """
    root = bundle_dir.resolve()
    classification = _classify_bundle_input(root)
    if classification == "missing":
        raise BundleError(f"Bundle directory not found: {root}")
    if classification == "not_a_dir":
        raise BundleError(
            f"BUNDLE must be a directory, got file: {root}",
        )
    if classification == "not_a_bundle_has_html":
        raise BundleError(
            (
                "This looks like a richdoc source tree, not a "
                f"richdoc.confluence.bundle.v1 directory: {root}."
            ),
            code="NOT_A_BUNDLE",
            hint=(
                "Build a bundle first with the richdoc skill:\n"
                f"    richdoc export confluence {root} -o <bundle-output-dir>\n"
                "Then pass the bundle path to `confluence publish-bundle`."
            ),
        )
    if classification == "not_a_bundle":
        raise BundleError(
            (
                f"Missing {MANIFEST_FILENAME} in {root}. "
                "This directory does not appear to be a "
                "richdoc.confluence.bundle.v1 bundle."
            ),
            code="NOT_A_BUNDLE",
            hint=(
                "See confluence/references/richdoc-bundles.md for the "
                "expected layout. If you have richdoc HTML source, "
                "build a bundle with `richdoc export confluence`."
            ),
        )
    manifest_file = root / MANIFEST_FILENAME
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleError(f"Malformed manifest JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BundleError("manifest.json: top-level value must be an object.")

    schema = str(data.get("schema") or "")
    if schema != BUNDLE_SCHEMA:
        raise BundleError(
            f"Unsupported bundle schema {schema!r}; expected {BUNDLE_SCHEMA!r}.",
        )

    pages: list[BundlePage] = []
    raw_pages = data.get("pages") or []
    if not isinstance(raw_pages, list) or not raw_pages:
        raise BundleError("Bundle manifest contains no pages.")
    keys: set[str] = set()
    for entry in raw_pages:
        if not isinstance(entry, dict):
            raise BundleError("Each page in manifest must be an object.")
        page = _page_from_json(entry)
        if page.key in keys:
            raise BundleError(f"Duplicate page key in manifest: {page.key!r}")
        keys.add(page.key)
        _ensure_inside(root, page.storage_path)
        for att in page.attachments:
            _ensure_inside(root, att.path)
        pages.append(page)
    for page in pages:
        if page.parent_key is not None and page.parent_key not in keys:
            raise BundleError(
                f"Page {page.key!r} has unknown parentKey {page.parent_key!r}.",
            )

    return BundleManifest(
        bundle_dir=root,
        schema=schema,
        created_by=str(data.get("createdBy") or ""),
        input_path=str(data.get("input") or ""),
        book=bool(data.get("book", False)),
        pages=pages,
    )


def read_storage(manifest: BundleManifest, page: BundlePage) -> str:
    """Load one page's storage XML, with safe path checking."""
    full = _ensure_inside(manifest.bundle_dir, page.storage_path)
    return full.read_text(encoding="utf-8")


def read_attachment(manifest: BundleManifest, att: BundleAttachment) -> bytes:
    """Load one attachment's bytes, with safe path checking."""
    full = _ensure_inside(manifest.bundle_dir, att.path)
    return full.read_bytes()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _page_from_json(data: dict) -> BundlePage:
    return BundlePage(
        key=str(data["key"]),
        source=str(data.get("source") or data["key"]),
        title=str(data["title"]),
        parent_key=(str(data["parentKey"]) if data.get("parentKey") else None),
        storage_path=str(data["storage"]),
        attachments=[
            BundleAttachment(
                token=str(a["token"]),
                filename=str(a["filename"]),
                path=str(a["path"]),
                mime=str(a.get("mime") or "application/octet-stream"),
                align=str(a.get("align") or "center"),
                inline=bool(a.get("inline", False)),
            )
            for a in (data.get("attachments") or [])
        ],
        links=[
            BundleLink(token=str(link["token"]), target_key=str(link["targetKey"]))
            for link in (data.get("links") or [])
        ],
        dropped=[str(s) for s in (data.get("dropped") or [])],
        missing=[str(s) for s in (data.get("missing") or [])],
    )


def _classify_bundle_input(root: Path) -> str:
    """Categorise the given path for ``read_bundle``'s error messages.

    Returns one of:

    - ``"missing"`` — path does not exist.
    - ``"not_a_dir"`` — path exists but is a file.
    - ``"ok"`` — directory with a ``manifest.json``.
    - ``"not_a_bundle_has_html"`` — directory without manifest but
      containing ``*.html`` files (probably a richdoc source tree).
    - ``"not_a_bundle"`` — directory without manifest and no HTML.
    """
    if not root.exists():
        return "missing"
    if not root.is_dir():
        return "not_a_dir"
    if (root / MANIFEST_FILENAME).is_file():
        return "ok"
    # Look for HTML up to two levels deep to keep this cheap.
    for pattern in ("*.html", "*/*.html"):
        for _ in root.glob(pattern):
            return "not_a_bundle_has_html"
    return "not_a_bundle"


def _ensure_inside(root: Path, rel: str) -> Path:
    """Resolve ``rel`` against ``root`` and reject path traversal."""
    if not rel:
        raise BundleError("Bundle entry has empty path.")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BundleError(f"Bundle path escapes bundle root: {rel!r}") from exc
    return candidate
