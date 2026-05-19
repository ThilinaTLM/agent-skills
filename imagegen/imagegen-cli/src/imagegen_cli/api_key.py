"""Resolve the Gemini API key.

Order:
  1. ``GEMINI_API_KEY`` environment variable (wins; supports CI / explicit override).
  2. ``.gemini-key`` file walked up from ``cwd`` to filesystem root (project-local).
  3. ``~/.gemini-key`` in the user's home directory (machine-wide default).

The file must contain just the raw key (whitespace is trimmed). Users should
add ``.gemini-key`` to ``.gitignore`` since it holds a secret.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

KEY_FILENAME = ".gemini-key"


@dataclass(frozen=True)
class ResolvedApiKey:
    key: str
    source: str  # "env" | "file"
    path: Path | None = None


def _find_project_key_file(start: Path) -> Path | None:
    cur = start.resolve()
    # Defensive cap; we stop when parent == cur (filesystem root).
    for _ in range(64):
        candidate = cur / KEY_FILENAME
        if candidate.is_file():
            return candidate
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent
    return None


def _read_key_file(path: Path) -> str | None:
    raw = path.read_text(encoding="utf-8")
    key = raw.strip()
    return key or None


def resolve_api_key(cwd: Path | None = None) -> ResolvedApiKey | None:
    env = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if env:
        return ResolvedApiKey(key=env, source="env")

    project = _find_project_key_file(cwd or Path.cwd())
    if project is not None:
        key = _read_key_file(project)
        if key:
            return ResolvedApiKey(key=key, source="file", path=project)

    home_path = Path.home() / KEY_FILENAME
    if home_path.is_file():
        key = _read_key_file(home_path)
        if key:
            return ResolvedApiKey(key=key, source="file", path=home_path)

    return None
