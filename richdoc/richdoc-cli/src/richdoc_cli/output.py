"""JSON output helpers — every CLI response is a single-line JSON envelope.

Success: {"ok": true, ...}     (stdout, exit 0)
Error:   {"ok": false, "error": "...", "code": "...", "hint?": "...", ...}
                                 (stdout, exit 1)
"""

from __future__ import annotations

import json
import sys
from typing import Any, NoReturn

# Known error codes. INTERNAL_ERROR is emitted by the top-level trap when an
# unexpected exception escapes a command.
ERROR_CODES = frozenset(
    {
        "INVALID_PARAMS",
        "FILE_EXISTS",
        "TEMPLATE_NOT_FOUND",
        "INPUT_ERROR",
        "OUTPUT_ERROR",
        "LINT_ERRORS",
        "PREREQ_MISSING",
        "INTERNAL_ERROR",
    }
)


def _emit(payload: dict[str, Any], exit_code: int) -> NoReturn:
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(exit_code)


def json_ok(**data: Any) -> NoReturn:
    """Emit a success envelope and exit 0."""
    _emit({"ok": True, **data}, 0)


def json_error(
    error: str,
    code: str | None = None,
    hint: str | None = None,
    **extra: Any,
) -> NoReturn:
    """Emit an error envelope and exit 1."""
    payload: dict[str, Any] = {"ok": False, "error": error}
    if code:
        payload["code"] = code
    if hint:
        payload["hint"] = hint
    payload.update(extra)
    _emit(payload, 1)
