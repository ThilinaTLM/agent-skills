"""Read local image files for the Gemini API inline-data parts.

Raw bytes are returned; the google-genai SDK serializes inline data itself,
so we don't base64-encode eagerly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MIME_BY_EXT: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@dataclass(frozen=True)
class InputImage:
    absolute_path: Path
    mime_type: str
    data_bytes: bytes


class InputError(Exception):
    """Raised for unreadable or unsupported input image files."""

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(message)
        self.message = message
        self.path = path


def read_input_image(raw_path: str) -> InputImage:
    """Resolve, MIME-detect, and read a single image file.

    Raises :class:`InputError` on unsupported extension or read failure.
    """
    abs_path = Path(raw_path).resolve()
    ext = abs_path.suffix.lower()
    mime = MIME_BY_EXT.get(ext)
    if not mime:
        supported = ", ".join(MIME_BY_EXT.keys())
        raise InputError(
            f"Unsupported image extension '{ext or '(none)'}'. Supported: {supported}",
            abs_path,
        )
    try:
        data = abs_path.read_bytes()
    except OSError as exc:
        raise InputError(f"Could not read input image: {exc}", abs_path) from exc
    return InputImage(absolute_path=abs_path, mime_type=mime, data_bytes=data)
