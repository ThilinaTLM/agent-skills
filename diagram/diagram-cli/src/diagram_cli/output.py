"""JSON envelope writer.

All stdout output from the CLI goes through these helpers. Nothing else may
write to stdout — agents parse it as a single JSON line.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _emit(payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False, sort_keys=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def emit_ok(**fields: Any) -> int:
    """Write a success envelope and return exit code 0."""
    payload: dict[str, Any] = {"ok": True}
    payload.update(fields)
    _emit(payload)
    return 0


def emit_error(code: str, error: str, hint: str, **extra: Any) -> int:
    """Write an error envelope and return exit code 1."""
    payload: dict[str, Any] = {
        "ok": False,
        "error": error,
        "code": code,
        "hint": hint,
    }
    payload.update(extra)
    _emit(payload)
    return 1
