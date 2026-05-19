"""Load the rd-* component schema from <framework>/assets/schema.json.

The schema is produced by `pnpm build` from the per-component sources. The
CLI never hand-maintains the vocabulary — single source of truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .paths import SCHEMA_PATH


@dataclass(frozen=True)
class SchemaFile:
    tags: dict[str, dict[str, Any]]
    generated: str | None
    path: str


_CACHED: SchemaFile | None = None


def load_schema() -> SchemaFile:
    """Read and cache schema.json. Raises FileNotFoundError-ish errors with a hint."""
    global _CACHED
    if _CACHED is not None:
        return _CACHED

    try:
        text = SCHEMA_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SchemaLoadError(
            f"Could not load richdoc schema from {SCHEMA_PATH}: {exc}. "
            "Run `pnpm build` from richdoc/richdoc-lib/ to generate it."
        ) from exc
    except OSError as exc:
        raise SchemaLoadError(
            f"Could not read richdoc schema at {SCHEMA_PATH}: {exc}."
        ) from exc

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaLoadError(
            f"richdoc schema at {SCHEMA_PATH} is not valid JSON: {exc}."
        ) from exc

    tags = parsed.get("tags") if isinstance(parsed, dict) else None
    if not isinstance(tags, dict):
        raise SchemaLoadError(
            f"richdoc schema at {SCHEMA_PATH} is missing a 'tags' object."
        )

    _CACHED = SchemaFile(
        tags=tags,
        generated=parsed.get("generated"),
        path=str(SCHEMA_PATH),
    )
    return _CACHED


class SchemaLoadError(RuntimeError):
    """Raised when the schema can't be loaded — caught by the command layer."""


def is_rd_tag(tag: str) -> bool:
    """True if `tag` starts with `rd-` (case-insensitive)."""
    return tag.lower().startswith("rd-")
