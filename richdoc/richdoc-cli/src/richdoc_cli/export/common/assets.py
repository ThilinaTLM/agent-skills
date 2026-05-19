"""Asset collection / materialisation for the export pipeline.

`AssetStore` is used by the markdown and docx exporters to centralise image
handling. Each call to `add()` either copies a local file or downloads a
remote URL (depending on `fetch_remote`), de-dupes by source URL, and hands
back an `AssetRef` describing the bytes and the stable local filename.

Stable filenames are `<sha1(content)[:12]>.<ext>` so two docs that reference
the same image collapse to one file on disk.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from ...mimetypes_ext import guess_mime

_ABSOLUTE_SCHEMES = frozenset({"http", "https", "data", "mailto", "tel", "javascript", "blob", "ws", "wss"})


def is_relative_url(url: str) -> bool:
    """True when `url` points at a local file relative to the document."""
    if not url:
        return False
    s = url.strip()
    if not s or s.startswith("#") or s.startswith("//"):
        return False
    parsed = urlparse(s)
    if parsed.scheme and parsed.scheme.lower() in _ABSOLUTE_SCHEMES:
        return False
    if parsed.scheme:
        return False
    return True


def is_remote_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme.lower() in ("http", "https")


@dataclass(frozen=True)
class AssetRef:
    """A single resolved asset."""

    source: str  # original URL / path as written in the HTML
    local_name: str  # stable filename, e.g. "ab12cd34ef56.png"
    mime: str
    data: bytes


@dataclass
class AssetStore:
    """Collects and de-dupes every image / media reference in a document."""

    timeout: float = 10.0
    _by_source: dict[str, AssetRef] = field(default_factory=dict)
    _missing: list[str] = field(default_factory=list)
    _seen_missing: set[str] = field(default_factory=set)

    # ---- public API ------------------------------------------------------

    def add(
        self,
        src: str,
        *,
        base_dir: Path,
        fetch_remote: bool,
    ) -> AssetRef | None:
        """Resolve `src` and store its bytes. Returns the AssetRef or None
        if the asset cannot be obtained (in which case `missing` is updated)."""
        src = (src or "").strip()
        if not src:
            return None
        if src.startswith("#") or src.startswith("data:"):
            return None
        if src in self._by_source:
            return self._by_source[src]

        if is_relative_url(src):
            ref = self._load_relative(src, base_dir)
        elif is_remote_url(src) and fetch_remote:
            ref = self._load_remote(src)
        else:
            return None

        if ref is None:
            self._note_missing(src)
            return None
        self._by_source[src] = ref
        return ref

    @property
    def missing(self) -> list[str]:
        return list(self._missing)

    def items(self) -> Iterator[AssetRef]:
        # De-dupe by local_name so two source URLs pointing at the same
        # bytes only materialise once.
        seen: set[str] = set()
        for ref in self._by_source.values():
            if ref.local_name in seen:
                continue
            seen.add(ref.local_name)
            yield ref

    def write_to(self, dest_dir: Path) -> dict[str, str]:
        """Materialise every collected asset under `dest_dir`. Returns a
        mapping of {original_url: relative_filename}."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        mapping: dict[str, str] = {}
        for ref in self.items():
            (dest_dir / ref.local_name).write_bytes(ref.data)
        for src, ref in self._by_source.items():
            mapping[src] = ref.local_name
        return mapping

    def url_for(self, src: str) -> str | None:
        """Return the local filename previously assigned to `src`, or None."""
        ref = self._by_source.get(src)
        return ref.local_name if ref else None

    # ---- loaders ---------------------------------------------------------

    def _load_relative(self, src: str, base_dir: Path) -> AssetRef | None:
        parsed = urlparse(src)
        path_part = unquote(parsed.path)
        if not path_part:
            return None
        p = Path(path_part)
        if p.is_absolute():
            return None
        full = (base_dir / p).resolve()
        try:
            data = full.read_bytes()
        except OSError:
            return None
        mime = guess_mime(full)
        local_name = _stable_name(data, hint_ext=full.suffix, mime=mime)
        return AssetRef(source=src, local_name=local_name, mime=mime, data=data)

    def _load_remote(self, src: str) -> AssetRef | None:
        try:
            req = Request(src, headers={"User-Agent": "richdoc-export/1.0"})
            with urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 — explicit user-supplied URL
                data = resp.read()
                mime = (resp.headers.get_content_type() or "").lower()
        except Exception:  # noqa: BLE001 — network errors are non-fatal
            return None
        if not mime:
            mime = guess_mime(Path(urlparse(src).path))
        hint_ext = Path(urlparse(src).path).suffix
        local_name = _stable_name(data, hint_ext=hint_ext, mime=mime)
        return AssetRef(source=src, local_name=local_name, mime=mime, data=data)

    def _note_missing(self, src: str) -> None:
        if src in self._seen_missing:
            return
        self._seen_missing.add(src)
        self._missing.append(src)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


_SAFE_EXT = re.compile(r"^\.[A-Za-z0-9]{1,8}$")


def _stable_name(data: bytes, *, hint_ext: str, mime: str) -> str:
    digest = hashlib.sha1(data, usedforsecurity=False).hexdigest()[:12]
    ext = (hint_ext or "").lower()
    if not _SAFE_EXT.match(ext):
        guessed = mimetypes.guess_extension(mime) if mime else None
        ext = (guessed or "").lower()
    if not _SAFE_EXT.match(ext):
        # Fall back to a sensible image default if mime hints at one
        if mime.startswith("image/"):
            ext = "." + mime.split("/", 1)[1].split("+")[0]
        else:
            ext = ".bin"
    return f"{digest}{ext}"
