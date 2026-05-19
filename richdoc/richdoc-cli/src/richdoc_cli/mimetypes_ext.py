"""Mime sniffing for the bundler.

Stdlib `mimetypes` is patchy on a handful of formats (svg, webp, woff2, …).
We layer a small override table on top of `mimetypes.guess_type` so the
bundler emits accurate `data:` URIs.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

# Extensions that stdlib doesn't reliably map, especially on older runtimes.
_OVERRIDES: dict[str, str] = {
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
    ".json": "application/json",
    ".mjs": "text/javascript",
    ".js": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".xml": "application/xml",
    ".pdf": "application/pdf",
    ".wasm": "application/wasm",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}


def guess_mime(path: Path) -> str:
    """Return a best-effort mime type for the given path."""
    ext = path.suffix.lower()
    if ext in _OVERRIDES:
        return _OVERRIDES[ext]
    guess, _ = mimetypes.guess_type(path.name)
    return guess or "application/octet-stream"
