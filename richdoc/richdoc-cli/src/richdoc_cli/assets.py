"""Locate the shipped richdoc.css / richdoc.js assets."""

from __future__ import annotations

from pathlib import Path

from .paths import ASSETS_DIR

ASSET_FILES: tuple[str, ...] = ("richdoc.css", "richdoc.js")


def asset_path(name: str) -> Path:
    return ASSETS_DIR / name


def assets_exist() -> bool:
    return all(asset_path(f).is_file() for f in ASSET_FILES)
