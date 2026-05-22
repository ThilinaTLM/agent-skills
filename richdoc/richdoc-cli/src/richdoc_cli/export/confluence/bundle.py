"""Confluence storage bundle: schema, dataclasses, writer, reader.

A *bundle* is an offline, on-disk artifact produced by
``richdoc export confluence`` and consumed by the separate ``confluence``
skill's ``publish-bundle`` command. It captures everything the publisher
needs without storing Confluence credentials or making any network call.

Layout::

    <bundle_dir>/
      manifest.json
      pages/
        <safe-name>.storage.xml         # one per page; XHTML + ac:* macros
      attachments/
        diag-<sha1[:12]>.png
        math-<sha1[:12]>.png
        image-<sha1[:12]>.<ext>

The storage XML may contain two kinds of replacement tokens:

  - ``@@ATTACHMENT:<prefix>:<digest>@@``
       Replaced by the publisher with a real ``<ac:image>`` reference
       once the attachment is uploaded under the manifest-declared
       filename.
  - ``@@RICHDOC_PAGE_URL:<page_key>@@``
       Replaced by the publisher with the resolved Confluence page URL
       (plus any trailing ``#fragment`` that the converter kept attached
       to the token in the source XML).

``page_key`` is the chapter file's POSIX-form path relative to the
book root (single-file docs use the file name). The manifest's
``pages[].key`` is the canonical declaration site for that value.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

BUNDLE_SCHEMA = "richdoc.confluence.bundle.v1"
"""Stable schema identifier. Consumers should reject unknown values."""

MANIFEST_FILENAME = "manifest.json"
PAGES_DIRNAME = "pages"
ATTACHMENTS_DIRNAME = "attachments"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleAttachment:
    """One binary asset referenced by a page's storage XML."""

    token: str           # placeholder that appears verbatim in storage XML
    filename: str        # stable filename on Confluence and on disk
    path: str            # relative to bundle root (POSIX)
    mime: str
    align: str = "center"
    inline: bool = False

    def to_json(self) -> dict:
        return {
            "token": self.token,
            "filename": self.filename,
            "path": self.path,
            "mime": self.mime,
            "align": self.align,
            "inline": self.inline,
        }

    @classmethod
    def from_json(cls, data: dict) -> BundleAttachment:
        return cls(
            token=str(data["token"]),
            filename=str(data["filename"]),
            path=str(data["path"]),
            mime=str(data.get("mime") or "application/octet-stream"),
            align=str(data.get("align") or "center"),
            inline=bool(data.get("inline", False)),
        )


@dataclass(frozen=True)
class BundleLink:
    """One cross-page link the publisher must rewrite to a real URL."""

    token: str           # @@RICHDOC_PAGE_URL:<key>@@ as it appears in XML
    target_key: str      # value of a sibling page's `key`

    def to_json(self) -> dict:
        return {"token": self.token, "targetKey": self.target_key}

    @classmethod
    def from_json(cls, data: dict) -> BundleLink:
        return cls(token=str(data["token"]), target_key=str(data["targetKey"]))


@dataclass
class BundlePage:
    """One Confluence page in the bundle."""

    key: str                          # POSIX-form chapter rel path; stable
    source: str                       # original .html path relative to input
    title: str
    parent_key: str | None            # another page's `key`, or None for root
    storage_path: str                 # relative to bundle root (POSIX)
    attachments: list[BundleAttachment] = field(default_factory=list)
    links: list[BundleLink] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "source": self.source,
            "title": self.title,
            "parentKey": self.parent_key,
            "storage": self.storage_path,
            "attachments": [a.to_json() for a in self.attachments],
            "links": [link.to_json() for link in self.links],
            "dropped": list(self.dropped),
            "missing": list(self.missing),
        }

    @classmethod
    def from_json(cls, data: dict) -> BundlePage:
        return cls(
            key=str(data["key"]),
            source=str(data.get("source") or data["key"]),
            title=str(data["title"]),
            parent_key=(str(data["parentKey"]) if data.get("parentKey") else None),
            storage_path=str(data["storage"]),
            attachments=[
                BundleAttachment.from_json(a) for a in (data.get("attachments") or [])
            ],
            links=[BundleLink.from_json(link) for link in (data.get("links") or [])],
            dropped=[str(s) for s in (data.get("dropped") or [])],
            missing=[str(s) for s in (data.get("missing") or [])],
        )


@dataclass
class BundleManifest:
    """Top-level bundle manifest."""

    input_path: str                   # absolute path of the original input
    book: bool
    pages: list[BundlePage]
    created_by: str = "richdoc-cli"
    schema: str = BUNDLE_SCHEMA
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    math_rendered: int = 0
    math_failed: int = 0

    def to_json(self) -> dict:
        attachments_total = sum(len(p.attachments) for p in self.pages)
        return {
            "schema": self.schema,
            "createdBy": self.created_by,
            "input": self.input_path,
            "book": self.book,
            "pages": [p.to_json() for p in self.pages],
            "summary": {
                "attachments": attachments_total,
                "diagramsRendered": self.diagrams_rendered,
                "diagramsFailed": self.diagrams_failed,
                "mathRendered": self.math_rendered,
                "mathFailed": self.math_failed,
            },
        }

    @classmethod
    def from_json(cls, data: dict) -> BundleManifest:
        schema = str(data.get("schema") or "")
        if schema != BUNDLE_SCHEMA:
            raise BundleError(
                f"Unsupported bundle schema {schema!r}; expected {BUNDLE_SCHEMA!r}.",
            )
        summary = data.get("summary") or {}
        return cls(
            schema=schema,
            created_by=str(data.get("createdBy") or "richdoc-cli"),
            input_path=str(data.get("input") or ""),
            book=bool(data.get("book", False)),
            pages=[BundlePage.from_json(p) for p in (data.get("pages") or [])],
            diagrams_rendered=int(summary.get("diagramsRendered") or 0),
            diagrams_failed=int(summary.get("diagramsFailed") or 0),
            math_rendered=int(summary.get("mathRendered") or 0),
            math_failed=int(summary.get("mathFailed") or 0),
        )


class BundleError(RuntimeError):
    """Raised on malformed bundles or unsafe paths."""


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


@dataclass
class PendingBundlePage:
    """In-memory page data fed to ``write_bundle``.

    ``storage_xml`` is the final body the publisher will POST/PUT once
    tokens are resolved. ``attachment_data`` maps the on-disk filename
    (relative to ``attachments/``) to the binary bytes.
    """

    page: BundlePage
    storage_xml: str
    attachment_data: dict[str, bytes]   # filename -> bytes


@dataclass
class BundleWriteResult:
    bundle_dir: Path
    manifest_path: Path
    pages_written: int
    attachments_written: int


def safe_page_filename(source_rel: str) -> str:
    """Build a stable on-disk filename for a page's storage XML.

    Slashes and parent traversals collapse to ``-`` so the entire layout
    sits flat under ``pages/``; the original source is recorded in the
    manifest's ``source`` field.
    """
    slug = source_rel.replace("\\", "/").strip("/")
    slug = slug.removesuffix(".html").removesuffix(".htm")
    safe = "".join(
        ch if (ch.isalnum() or ch in "-_.") else "-" for ch in slug
    )
    safe = safe.strip("-") or "page"
    return f"{safe}.storage.xml"


def write_bundle(
    *,
    bundle_dir: Path,
    manifest: BundleManifest,
    pages: list[PendingBundlePage],
    force: bool = False,
) -> BundleWriteResult:
    """Write a bundle to disk.

    ``pages`` carries the storage XML and binary attachment data; the
    matching paths come from ``manifest.pages[].storage_path`` and
    ``manifest.pages[].attachments[].path``.
    """
    out = bundle_dir.resolve()
    if out.exists():
        if not force:
            raise FileExistsError(
                f"Bundle directory already exists: {out}. Pass --force to overwrite."
            )
        # Wipe only the well-known subdirs and manifest — preserve other
        # files the user may have dropped into the directory.
        for name in (MANIFEST_FILENAME, PAGES_DIRNAME, ATTACHMENTS_DIRNAME):
            target = out / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
    out.mkdir(parents=True, exist_ok=True)
    (out / PAGES_DIRNAME).mkdir(exist_ok=True)
    if any(p.attachment_data for p in pages):
        (out / ATTACHMENTS_DIRNAME).mkdir(exist_ok=True)

    attachments_written = 0
    seen_attachments: set[str] = set()
    for pending in pages:
        storage_target = out / pending.page.storage_path
        storage_target.parent.mkdir(parents=True, exist_ok=True)
        storage_target.write_text(pending.storage_xml, encoding="utf-8")
        for filename, data in pending.attachment_data.items():
            if filename in seen_attachments:
                continue
            att_target = out / ATTACHMENTS_DIRNAME / filename
            att_target.write_bytes(data)
            seen_attachments.add(filename)
            attachments_written += 1

    manifest_path = out / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest.to_json(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return BundleWriteResult(
        bundle_dir=out,
        manifest_path=manifest_path,
        pages_written=len(pages),
        attachments_written=attachments_written,
    )


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
    if not root.is_dir():
        raise BundleError(f"Bundle directory not found: {root}")
    manifest_file = root / MANIFEST_FILENAME
    if not manifest_file.is_file():
        raise BundleError(f"Missing {MANIFEST_FILENAME} in {root}")
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleError(f"Malformed manifest JSON: {exc}") from exc
    manifest = BundleManifest.from_json(data)

    keys: set[str] = set()
    for page in manifest.pages:
        if page.key in keys:
            raise BundleError(f"Duplicate page key in manifest: {page.key!r}")
        keys.add(page.key)
        _ensure_inside(root, page.storage_path)
        for att in page.attachments:
            _ensure_inside(root, att.path)

    for page in manifest.pages:
        if page.parent_key is not None and page.parent_key not in keys:
            raise BundleError(
                f"Page {page.key!r} has unknown parentKey {page.parent_key!r}.",
            )
    return manifest


def _ensure_inside(root: Path, rel: str) -> Path:
    """Resolve ``rel`` against ``root`` and reject path traversal."""
    if not rel:
        raise BundleError("Bundle entry has empty path.")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BundleError(
            f"Bundle path escapes bundle root: {rel!r}",
        ) from exc
    return candidate
