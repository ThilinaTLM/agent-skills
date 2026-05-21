"""Pipeline orchestration for `richdoc export html-confluence`.

Produces one zip archive ready for Confluence Cloud's "Import from HTML"
workflow:

```
<output.zip>
└── <space-name>/                  ← folder name = space name on import
    ├── page-one.html              ← .html extension is required
    ├── page-one/                  ← per-page asset folder (same stem)
    │   ├── <hash>.png             ← user-provided images
    │   ├── code-<hash>.png        ← rasterised code blocks
    │   ├── math-<hash>.png        ← rasterised math
    │   └── diag-<hash>.png        ← rasterised rd-diagram
    ├── page-two.html
    └── page-two/
        └── ...
```

Books → flat siblings: Confluence's importer doesn't honour subfolder
hierarchy as nesting, so chapter slugs are hyphen-joined and emitted
side-by-side. The shared `<rd-toc>` block becomes a TOC list on the
entry page only (every other chapter's copy is dropped, since the same
list would duplicate across pages once imported).

The pipeline is best-effort about images:

- Asset failures (broken `src=`) → recorded in `missing`, page emits
  the original src so the browser-rendered page still works after
  unzipping for manual review.
- Code rasterisation never fails (Pillow is deterministic).
- Math / diagram Kroki calls return None on failure; we skip the
  placeholder and leave the inline text fallback in place.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import lxml.html as LH

from ..book import ChapterFile, discover_chapters
from ..common.assets import AssetStore
from ..common.diagrams import render_to_png
from .code_image import render_code_image
from .converter import (
    PageResult,
    PendingCode,
    PendingDiagram,
    PendingMath,
    html_to_confluence_page,
)
from .math_image import render_math_image


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class ConfluenceExportResult:
    archive_path: Path
    space_name: str
    pages: list[str] = field(default_factory=list)         # zip-internal posix paths
    bytes_total: int = 0
    images_embedded: int = 0                                # user-provided + remote
    code_images: int = 0
    math_images: int = 0
    math_failed: int = 0
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    missing: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    is_book: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_confluence(
    entry: Path,
    *,
    output: Path | None,
    space_name: str | None = None,
    no_book: bool = False,
    render_diagrams: bool = True,
    render_code_images: bool = True,
    render_math_images: bool = True,
    diagram_endpoint: str = "https://kroki.io",
    include_remote_images: bool = False,
    code_style: str = "default",
    force: bool = False,
) -> ConfluenceExportResult:
    """Build the import-ready zip on disk and return the structured result."""
    discovery = discover_chapters(entry)
    is_book = discovery.is_book and not no_book
    chapters = discovery.chapters if is_book else discovery.chapters[:1]

    archive_path = _resolve_output_path(entry, output)
    if archive_path.exists() and not force:
        raise FileExistsError(f"Output file already exists: {archive_path}")

    resolved_space = _space_name(space_name, archive_path, entry)
    payload, result = _build_archive_bytes(
        chapters=chapters,
        is_book=is_book,
        space=resolved_space,
        render_diagrams=render_diagrams,
        render_code_images=render_code_images,
        render_math_images=render_math_images,
        diagram_endpoint=diagram_endpoint,
        include_remote_images=include_remote_images,
        code_style=code_style,
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(payload)
    result.archive_path = archive_path
    result.bytes_total = len(payload)
    return result


def render_to_bytes(
    entry: Path,
    *,
    space_name: str | None = None,
    no_book: bool = False,
    render_diagrams: bool = True,
    render_code_images: bool = True,
    render_math_images: bool = True,
    diagram_endpoint: str = "https://kroki.io",
    include_remote_images: bool = False,
    code_style: str = "default",
) -> bytes:
    """Return the import-ready zip as bytes (for `-o -` stdout mode)."""
    discovery = discover_chapters(entry)
    is_book = discovery.is_book and not no_book
    chapters = discovery.chapters if is_book else discovery.chapters[:1]
    resolved_space = _space_name(space_name, None, entry)
    payload, _ = _build_archive_bytes(
        chapters=chapters,
        is_book=is_book,
        space=resolved_space,
        render_diagrams=render_diagrams,
        render_code_images=render_code_images,
        render_math_images=render_math_images,
        diagram_endpoint=diagram_endpoint,
        include_remote_images=include_remote_images,
        code_style=code_style,
    )
    return payload


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def _build_archive_bytes(
    *,
    chapters: list[ChapterFile],
    is_book: bool,
    space: str,
    render_diagrams: bool,
    render_code_images: bool,
    render_math_images: bool,
    diagram_endpoint: str,
    include_remote_images: bool,
    code_style: str,
) -> tuple[bytes, ConfluenceExportResult]:
    """Walk every chapter and assemble the zip in memory."""
    result = ConfluenceExportResult(
        archive_path=Path(""),
        space_name=space,
        is_book=is_book,
    )
    # Plan slugs up front so cross-chapter links can be rewritten.
    slug_for: dict[Path, str] = {}
    seen_slugs: set[str] = set()
    for ch in chapters:
        base = _slug_for_chapter(ch)
        slug = base
        i = 2
        while slug in seen_slugs:
            slug = f"{base}-{i}"
            i += 1
        seen_slugs.add(slug)
        slug_for[ch.path] = slug
    href_map = _build_href_map(chapters, slug_for)

    rendered: list[tuple[ChapterFile, str, PageResult]] = []
    for ch in chapters:
        slug = slug_for[ch.path]
        store = AssetStore()
        page = html_to_confluence_page(
            ch.html,
            page_slug=slug,
            asset_store=store,
            asset_base=ch.path.parent,
            include_remote_images=include_remote_images,
            render_diagrams=render_diagrams,
            render_code_images=render_code_images,
            render_math_images=render_math_images,
            diagram_endpoint=diagram_endpoint,
            code_style=code_style,
        )
        # If this is a chapter in a book and not the entry, drop any
        # duplicated rd-toc body (every chapter HTML has its own copy);
        # the entry's TOC is enough.
        if is_book and ch is not chapters[0]:
            page.body_html = _strip_duplicate_toc(page.body_html)
        rendered.append((ch, slug, page))

    # Now rasterise every pending code/math/diagram, push into per-page
    # asset stores, and rewrite placeholders → <img src=…>.
    for ch, slug, page in rendered:
        _materialise_pending(
            page=page,
            slug=slug,
            diagram_endpoint=diagram_endpoint,
            counters=result,
        )

    # Compose the final page HTML and pack the zip.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for ch, slug, page in rendered:
            page_path = f"{space}/{slug}.html"
            title = page.title or ch.title or slug
            html_doc = _wrap_html(title=title, body=page.body_html, href_map=href_map)
            zf.writestr(page_path, html_doc.encode("utf-8"))
            result.pages.append(page_path)
            # Materialise asset store entries for this page.
            for ref in page.asset_store.items():
                asset_path = f"{space}/{slug}/{ref.local_name}"
                zf.writestr(asset_path, ref.data)
                result.images_embedded += 1
            for src in page.asset_store.missing:
                if src not in result.missing:
                    result.missing.append(src)
            for tag in page.dropped:
                if tag not in result.dropped:
                    result.dropped.append(tag)
    result.dropped = sorted(result.dropped)
    return buf.getvalue(), result


# ---------------------------------------------------------------------------
# Materialisation: pending → asset store + <img> in body
# ---------------------------------------------------------------------------


def _materialise_pending(
    *,
    page: PageResult,
    slug: str,
    diagram_endpoint: str,
    counters: ConfluenceExportResult,
) -> None:
    body = page.body_html
    body = _rasterise_code(body, page.code, slug, page.asset_store, counters)
    body = _rasterise_math(body, page.math, slug, page.asset_store,
                           diagram_endpoint=diagram_endpoint, counters=counters)
    body = _rasterise_diagrams(body, page.diagrams, slug, page.asset_store,
                               diagram_endpoint=diagram_endpoint, counters=counters)
    page.body_html = body


def _rasterise_code(
    body: str,
    pending: list[PendingCode],
    slug: str,
    store: AssetStore,
    counters: ConfluenceExportResult,
) -> str:
    for item in pending:
        png = render_code_image(
            item.text,
            lang=item.lang,
            title=item.title,
            line_numbers=item.line_numbers,
        )
        local = _store_synthetic(store, png, prefix="code")
        href = f"{slug}/{local}"
        body = body.replace(item.placeholder, href)
        counters.code_images += 1
    return body


def _rasterise_math(
    body: str,
    pending: list[PendingMath],
    slug: str,
    store: AssetStore,
    *,
    diagram_endpoint: str,
    counters: ConfluenceExportResult,
) -> str:
    for item in pending:
        png = render_math_image(
            item.latex,
            display=item.display,
            endpoint=diagram_endpoint,
        )
        if png is None:
            counters.math_failed += 1
            # Replace the placeholder src with a data: noop so the page
            # still renders without a broken image — keep the alt text.
            body = body.replace(
                item.placeholder,
                "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>",
            )
            continue
        local = _store_synthetic(store, png, prefix="math")
        href = f"{slug}/{local}"
        body = body.replace(item.placeholder, href)
        counters.math_images += 1
    return body


def _rasterise_diagrams(
    body: str,
    pending: list[PendingDiagram],
    slug: str,
    store: AssetStore,
    *,
    diagram_endpoint: str,
    counters: ConfluenceExportResult,
) -> str:
    for item in pending:
        png = render_to_png(item.source, kind=item.kind, endpoint=diagram_endpoint)
        if png is None:
            counters.diagrams_failed += 1
            body = body.replace(
                item.placeholder,
                "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>",
            )
            continue
        local = _store_synthetic(store, png, prefix="diag")
        href = f"{slug}/{local}"
        body = body.replace(item.placeholder, href)
        counters.diagrams_rendered += 1
    return body


def _store_synthetic(store: AssetStore, png: bytes, *, prefix: str) -> str:
    """Push synthesised PNG bytes through AssetStore by hashing the content.
    Returns the local filename. Avoids touching the public `add()` path
    which expects an on-disk source URL.
    """
    digest = hashlib.sha1(png, usedforsecurity=False).hexdigest()[:12]
    local = f"{prefix}-{digest}.png"
    synthetic_src = f"__richdoc_synthetic__:{prefix}:{digest}"
    # If we've already stored this bytes-identical asset under the same
    # synthetic key, reuse it.
    if synthetic_src in store._by_source:  # type: ignore[attr-defined]
        return store._by_source[synthetic_src].local_name  # type: ignore[attr-defined]
    from ..common.assets import AssetRef  # noqa: PLC0415

    ref = AssetRef(
        source=synthetic_src, local_name=local, mime="image/png", data=png
    )
    store._by_source[synthetic_src] = ref  # type: ignore[attr-defined]
    return local


# ---------------------------------------------------------------------------
# Slug + space-name helpers
# ---------------------------------------------------------------------------


_SLUG_CLEAN = re.compile(r"[^a-z0-9._-]+")
_SLUG_DASHES = re.compile(r"-{2,}")


def _slugify(text: str) -> str:
    s = text.strip().lower().replace(" ", "-")
    s = _SLUG_CLEAN.sub("-", s)
    s = _SLUG_DASHES.sub("-", s).strip("-")
    return s or "page"


def _slug_for_chapter(ch: ChapterFile) -> str:
    """Flat-slugify a chapter's relative path. `docs/intro.html` →
    `docs-intro`; `index.html` → `index`."""
    rel = ch.relative.with_suffix("")
    flat = "-".join(part for part in rel.parts if part)
    return _slugify(flat or ch.path.stem)


def _build_href_map(
    chapters: list[ChapterFile], slug_for: dict[Path, str]
) -> dict[str, str]:
    """Map original relative HTML paths to their final slug-based names so
    in-page links between chapters land on the right Confluence page."""
    href_map: dict[str, str] = {}
    for ch in chapters:
        slug = slug_for[ch.path]
        rel = ch.relative.as_posix()
        href_map[rel] = f"{slug}.html"
        # Also map the bare name (without folder).
        href_map[ch.relative.name] = f"{slug}.html"
        # Allow stem references in case rd-toc uses `intro` not `intro.html`.
        href_map[ch.relative.with_suffix("").as_posix()] = f"{slug}.html"
    return href_map


def _resolve_output_path(entry: Path, output: Path | None) -> Path:
    if output is not None:
        p = output.resolve()
        if p.suffix.lower() != ".zip":
            p = p.with_suffix(".zip")
        return p
    return entry.with_name(entry.stem + ".zip").resolve()


def _space_name(
    explicit: str | None, archive: Path | None, entry: Path
) -> str:
    """Pick the top-level folder name (= imported Confluence space name)."""
    for candidate in (explicit, archive.stem if archive else None, entry.stem):
        if not candidate:
            continue
        slug = _slugify(candidate)
        if slug:
            return slug
    return "richdoc"


# ---------------------------------------------------------------------------
# Final HTML assembly
# ---------------------------------------------------------------------------


def _wrap_html(*, title: str, body: str, href_map: dict[str, str]) -> str:
    """Wrap a rendered page body in the minimal HTML5 envelope Confluence
    expects, and rewrite inter-chapter `<a href>` to the slug-based names."""
    body = _rewrite_internal_links(body, href_map)
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>{safe_title}</title>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


_HREF_RE = re.compile(r'href="([^"#?]+)([?#][^"]*)?"')


def _rewrite_internal_links(body: str, href_map: dict[str, str]) -> str:
    if not href_map:
        return body

    def repl(m: re.Match[str]) -> str:
        path, tail = m.group(1), m.group(2) or ""
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", path) or path.startswith("//"):
            return m.group(0)
        # Try exact match, then stripped-extension, then bare name.
        for key in (
            path,
            path.removesuffix(".html").removesuffix(".htm"),
            Path(path).name,
        ):
            if key in href_map:
                return f'href="{href_map[key]}{tail}"'
        return m.group(0)

    return _HREF_RE.sub(repl, body)


def _strip_duplicate_toc(body: str) -> str:
    """A book has the same `<rd-toc>` baked into every chapter HTML. The
    converter emits an `<h2>Contents</h2><ul>…</ul>` block for it; that
    duplication is ugly on the imported Confluence pages, so we keep the
    TOC only on the entry page."""
    # Match the Contents heading + its immediate <ul> sibling. Tolerant of
    # the heading text differing from the default.
    pattern = re.compile(
        r"<h2>[^<]*</h2>\s*<ul>.*?</ul>\s*",
        re.DOTALL,
    )
    # We can't be 100% sure the first <h2>+<ul> is the TOC, but the
    # converter emits the TOC as the first block whenever rd-toc is the
    # first body child — which is the convention for richdoc books. To be
    # safer, scope the strip to the run-up of the document.
    head, sep, tail = body.partition("</ul>")
    if not sep:
        return body
    if "<h2>" in head and "<ul>" in head:
        # Find the most recent <h2> followed by the <ul>.
        match = re.search(r"<h2>[^<]*</h2>\s*<ul>", head)
        if match:
            cleaned = head[: match.start()] + tail.lstrip("\n")
            return cleaned
    return body


# Parse HTML for the title fallback below.
def _doc_title(html: str) -> str | None:
    try:
        root = LH.fromstring(html)
    except Exception:  # noqa: BLE001
        return None
    for h1 in root.iter("h1"):
        text = " ".join("".join(h1.itertext()).split()).strip()
        if text:
            return text
    return None
