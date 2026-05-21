"""Resolve the Kroki endpoint URL.

Order of precedence:
1. `--endpoint <url>` flag (function argument)
2. `KROKI_URL` environment variable
3. `.kroki-url` file walked up from `start_dir` (first non-empty match wins)
4. Default `https://kroki.io`
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ENDPOINT = "https://kroki.io"
_CONFIG_FILENAME = ".kroki-url"


def _walk_up_for_config(start_dir: Path) -> str | None:
    """Look for `.kroki-url` from start_dir upward to the filesystem root."""
    current = start_dir.resolve()
    while True:
        candidate = current / _CONFIG_FILENAME
        if candidate.is_file():
            try:
                value = candidate.read_text(encoding="utf-8").strip()
            except OSError:
                value = ""
            if value:
                return value
        if current.parent == current:
            return None
        current = current.parent


def resolve_endpoint(flag: str | None, start_dir: Path | None = None) -> str:
    """Resolve the Kroki endpoint, stripped of any trailing slash."""
    raw: str | None = None
    if flag and flag.strip():
        raw = flag.strip()
    elif os.environ.get("KROKI_URL", "").strip():
        raw = os.environ["KROKI_URL"].strip()
    else:
        from_file = _walk_up_for_config(start_dir or Path.cwd())
        if from_file:
            raw = from_file
    if not raw:
        raw = DEFAULT_ENDPOINT
    return raw.rstrip("/")
