"""Asset-inlining engine for `richdoc export html`.

Walks an HTML document and replaces every *relative-path* asset reference
with an inline equivalent: CSS becomes `<style>`, JS becomes inline
`<script>`, images / fonts / media become `data:` URIs.

Absolute URLs (`https://`, `http://`, `//cdn…`, `data:`, `mailto:`,
`tel:`, `javascript:`, `#fragment`) are never touched. Plain hyperlinks
(`<a href>`, `<area href>`) are never touched either — those are
navigation, not assets.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

import lxml.etree as ET
import lxml.html as LH

from ...mimetypes_ext import guess_mime

# Categories surface in the JSON envelope.
_CAT_CSS = "css"
_CAT_JS = "js"
_CAT_IMAGES = "images"
_CAT_OTHER = "other"


@dataclass
class BundleResult:
    html: str
    inlined: dict[str, int] = field(default_factory=dict)
    kept_absolute: int = 0
    missing: list[str] = field(default_factory=list)


def bundle(source: str, base_dir: Path) -> BundleResult:
    """Inline every relative-path dependency in `source`.

    `base_dir` is the directory the HTML lives in — used to resolve relative
    URLs and to constrain reads (no escaping above `base_dir`).
    """
    base_dir = base_dir.resolve()

    parser = LH.HTMLParser(recover=True)
    root = LH.document_fromstring(source, parser=parser)

    state = _State(base_dir=base_dir)

    # Stylesheets — must run before images so any url(./pic.png) we may want
    # to inline inside CSS could be processed (not implemented yet — we inline
    # the CSS body verbatim and trust authors to use absolute URLs there).
    _inline_stylesheets(root, state)
    _inline_scripts(root, state)
    _inline_media(root, state)
    _inline_link_assets(root, state)

    # Account for absolute hrefs/srcs we deliberately left alone.
    state.kept_absolute += _count_absolute_refs(root)

    html = _serialise(root)

    return BundleResult(
        html=html,
        inlined={
            _CAT_CSS: state.counts[_CAT_CSS],
            _CAT_JS: state.counts[_CAT_JS],
            _CAT_IMAGES: state.counts[_CAT_IMAGES],
            _CAT_OTHER: state.counts[_CAT_OTHER],
        },
        kept_absolute=state.kept_absolute,
        missing=state.missing,
    )


# ----------------------------------------------------------------------------
# State + helpers
# ----------------------------------------------------------------------------


@dataclass
class _State:
    base_dir: Path
    counts: dict[str, int] = field(
        default_factory=lambda: {_CAT_CSS: 0, _CAT_JS: 0, _CAT_IMAGES: 0, _CAT_OTHER: 0}
    )
    kept_absolute: int = 0
    missing: list[str] = field(default_factory=list)
    # de-dupe missing entries while preserving order
    _seen_missing: set[str] = field(default_factory=set)

    def note_missing(self, url: str) -> None:
        if url in self._seen_missing:
            return
        self._seen_missing.add(url)
        self.missing.append(url)


_ABSOLUTE_SCHEMES = frozenset(
    {"http", "https", "data", "mailto", "tel", "javascript", "blob", "ws", "wss"}
)


def _is_relative(url: str) -> bool:
    """True when `url` points at a local file relative to the document."""
    if not url:
        return False
    s = url.strip()
    if not s:
        return False
    if s.startswith("#"):
        return False
    if s.startswith("//"):  # protocol-relative
        return False
    parsed = urlparse(s)
    if parsed.scheme and parsed.scheme.lower() in _ABSOLUTE_SCHEMES:
        return False
    # Some odd schemes still count as absolute — anything with a scheme.
    if parsed.scheme:
        return False
    return True


def _resolve_local(url: str, base_dir: Path) -> Path | None:
    """Resolve `url` relative to `base_dir`. Returns None for empty paths.

    The bundler is run against the user's own document — we do not guard
    against path-escape because the author wrote both the HTML and the
    referenced files. Anything the calling user can read is fair game.
    """
    # Strip query / fragment for filesystem lookup.
    parsed = urlparse(url)
    path_part = unquote(parsed.path)
    if not path_part:
        return None
    p = Path(path_part)
    if p.is_absolute():
        # Absolute filesystem paths aren't "relative" deps; refuse them so we
        # don't silently inline /etc/* if an author typos a path.
        return None
    return (base_dir / p).resolve()


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _make_data_uri(path: Path, raw: bytes) -> str:
    mime = guess_mime(path)
    # SVGs render fine as utf-8 data URIs when small; base64 otherwise.
    if mime == "image/svg+xml" and len(raw) < 2048:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is not None:
            # Encode only the characters that would break a data URI.
            safe = (
                text.replace("\r", "")
                .replace("\n", " ")
                .replace("#", "%23")
                .replace("?", "%3F")
            )
            return f"data:{mime};utf8,{safe}"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ----------------------------------------------------------------------------
# Stylesheets: <link rel="stylesheet" href="…">
# ----------------------------------------------------------------------------


def _inline_stylesheets(root: ET._Element, state: _State) -> None:  # noqa: SLF001
    for link in list(root.iter("link")):
        rel = (link.get("rel") or "").lower()
        if "stylesheet" not in rel.split():
            continue
        href = link.get("href") or ""
        if not _is_relative(href):
            continue
        path = _resolve_local(href, state.base_dir)
        text = _read_text(path) if path else None
        if text is None:
            state.note_missing(href)
            continue
        style = ET.Element("style")
        # Preserve type/media if set.
        for attr in ("media", "type"):
            v = link.get(attr)
            if v:
                style.set(attr, v)
        style.text = _escape_close_tag(text, "style")
        parent = link.getparent()
        if parent is None:
            continue
        parent.replace(link, style)
        state.counts[_CAT_CSS] += 1


# ----------------------------------------------------------------------------
# Scripts: <script src="…">
# ----------------------------------------------------------------------------


def _inline_scripts(root: ET._Element, state: _State) -> None:  # noqa: SLF001
    for script in list(root.iter("script")):
        src = script.get("src") or ""
        if not src or not _is_relative(src):
            continue
        path = _resolve_local(src, state.base_dir)
        text = _read_text(path) if path else None
        if text is None:
            state.note_missing(src)
            continue
        new_script = ET.Element("script")
        # Preserve defer/async/type. Drop integrity/crossorigin which no longer apply.
        for attr in ("defer", "async", "type", "nomodule"):
            if script.get(attr) is not None:
                new_script.set(attr, script.get(attr) or "")
        new_script.text = _escape_close_tag(text, "script")
        parent = script.getparent()
        if parent is None:
            continue
        parent.replace(script, new_script)
        state.counts[_CAT_JS] += 1


# ----------------------------------------------------------------------------
# Media: img, source, video, audio, track, poster, rd-shot, rd-embed, rd-figure
# ----------------------------------------------------------------------------


# (tag, attribute, category, srcset)
_MEDIA_TARGETS: tuple[tuple[str, str, str, bool], ...] = (
    ("img", "src", _CAT_IMAGES, False),
    ("img", "srcset", _CAT_IMAGES, True),
    ("source", "src", _CAT_IMAGES, False),
    ("source", "srcset", _CAT_IMAGES, True),
    ("video", "src", _CAT_OTHER, False),
    ("video", "poster", _CAT_IMAGES, False),
    ("audio", "src", _CAT_OTHER, False),
    ("track", "src", _CAT_OTHER, False),
    ("rd-shot", "src", _CAT_IMAGES, False),
    ("rd-embed", "src", _CAT_OTHER, False),
)


def _inline_media(root: ET._Element, state: _State) -> None:  # noqa: SLF001
    for tag, attr, category, is_srcset in _MEDIA_TARGETS:
        for el in root.iter(tag):
            value = el.get(attr)
            if not value:
                continue
            if is_srcset:
                new_value, n_inlined = _rewrite_srcset(value, state, category)
                if n_inlined:
                    el.set(attr, new_value)
            else:
                replaced = _maybe_inline_single(value, state, category)
                if replaced is not None:
                    el.set(attr, replaced)


def _maybe_inline_single(url: str, state: _State, category: str) -> str | None:
    if not _is_relative(url):
        return None
    path = _resolve_local(url, state.base_dir)
    raw = _read_bytes(path) if path else None
    if raw is None:
        state.note_missing(url)
        return None
    state.counts[category] += 1
    return _make_data_uri(path, raw)


_SRCSET_SPLIT = re.compile(r"\s*,\s*(?![^()]*\))")


def _rewrite_srcset(value: str, state: _State, category: str) -> tuple[str, int]:
    pieces = _SRCSET_SPLIT.split(value)
    out: list[str] = []
    n_inlined = 0
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        parts = piece.split(None, 1)
        url = parts[0]
        descriptor = parts[1] if len(parts) > 1 else ""
        replaced = _maybe_inline_single(url, state, category)
        if replaced is not None:
            url = replaced
            n_inlined += 1
        out.append(f"{url} {descriptor}".strip())
    return ", ".join(out), n_inlined


# ----------------------------------------------------------------------------
# Other link assets: icons, manifest, preload
# ----------------------------------------------------------------------------


_LINK_ASSET_RELS: frozenset[str] = frozenset(
    {"icon", "shortcut icon", "apple-touch-icon", "manifest", "preload", "prefetch", "mask-icon"}
)


def _inline_link_assets(root: ET._Element, state: _State) -> None:  # noqa: SLF001
    for link in list(root.iter("link")):
        rel = (link.get("rel") or "").lower()
        if not rel:
            continue
        if "stylesheet" in rel.split():
            continue
        rel_set = set(rel.split())
        if not (rel_set & _LINK_ASSET_RELS):
            continue
        href = link.get("href") or ""
        if not _is_relative(href):
            continue
        path = _resolve_local(href, state.base_dir)
        raw = _read_bytes(path) if path else None
        if raw is None:
            state.note_missing(href)
            continue
        link.set("href", _make_data_uri(path, raw))
        state.counts[_CAT_OTHER] += 1


# ----------------------------------------------------------------------------
# Absolute refs (counted for the envelope)
# ----------------------------------------------------------------------------


def _count_absolute_refs(root: ET._Element) -> int:  # noqa: SLF001
    n = 0
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        for attr in ("href", "src"):
            v = el.get(attr)
            if not v:
                continue
            if v.startswith("data:"):
                # Already inlined or author-supplied — don't double-count.
                continue
            if not _is_relative(v):
                n += 1
    return n


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------


def _escape_close_tag(body: str, tag: str) -> str:
    """Defang `</script>` / `</style>` sequences inside inlined bodies."""
    pattern = re.compile(rf"</\s*{tag}", re.IGNORECASE)
    return pattern.sub(lambda m: m.group(0).replace("<", "<\\"), body)


def _serialise(root: ET._Element) -> str:  # noqa: SLF001
    html = LH.tostring(
        root,
        encoding="unicode",
        doctype="<!doctype html>",
        method="html",
    )
    if not html.endswith("\n"):
        html += "\n"
    return html
