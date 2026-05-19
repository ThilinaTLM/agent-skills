"""Resolve available HTML templates shipped with the skill."""

from __future__ import annotations

from pathlib import Path

from .paths import TEMPLATES_DIR


def list_templates() -> list[str]:
    if not TEMPLATES_DIR.is_dir():
        return []
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.html") if p.is_file())


def template_path(name: str) -> Path:
    return TEMPLATES_DIR / f"{name}.html"


def template_exists(name: str) -> bool:
    return template_path(name).is_file()
