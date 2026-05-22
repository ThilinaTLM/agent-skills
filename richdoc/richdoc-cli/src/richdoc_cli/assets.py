"""Locate the shipped richdoc.css / richdoc.js assets."""

from __future__ import annotations

import hashlib
import json
from functools import cache, lru_cache
from pathlib import Path

from .paths import ASSETS_DIR

ASSET_FILES: tuple[str, ...] = ("richdoc.css", "richdoc.js")

VERSION_FILE: str = "version.txt"

_CHUNK = 64 * 1024


def asset_path(name: str) -> Path:
    return ASSETS_DIR / name


def assets_exist() -> bool:
    return all(asset_path(f).is_file() for f in ASSET_FILES)


def file_sha256(path: Path) -> str:
    """SHA-256 of an arbitrary file, streamed."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@cache
def asset_sha256(name: str) -> str:
    """SHA-256 of a shipped asset. Cached for the process lifetime."""
    return file_sha256(asset_path(name))


@lru_cache(maxsize=1)
def shipped_version_info() -> dict | None:
    """Parse richdoc-lib/assets/version.txt. Returns {'hash','builtAt'} or None.

    The version.txt file is emitted by the richdoc-lib build. It is optional —
    if the file is missing or malformed we just return None and the update
    command falls back to per-file hashing only.
    """
    path = ASSETS_DIR / VERSION_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    info: dict = {}
    if isinstance(data.get("hash"), str):
        info["hash"] = data["hash"]
    if isinstance(data.get("builtAt"), str):
        info["builtAt"] = data["builtAt"]
    return info or None
