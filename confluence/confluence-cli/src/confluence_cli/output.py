"""Single-line JSON output envelopes.

Every command emits exactly one JSON object on stdout. ``json_ok``
returns; ``json_error`` exits with status 1 so the agent can branch
on the exit code without parsing the body.
"""

from __future__ import annotations

import json
import sys
from typing import Any, NoReturn


def json_ok(**payload: Any) -> None:
    """Write a success envelope to stdout."""
    body = {"ok": True, **payload}
    sys.stdout.write(json.dumps(body, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


def json_error(
    message: str,
    *,
    code: str = "INTERNAL_ERROR",
    hint: str | None = None,
    **extra: Any,
) -> NoReturn:
    """Write an error envelope and exit with status 1."""
    body: dict[str, Any] = {
        "ok": False,
        "error": message,
        "code": code,
    }
    if hint:
        body["hint"] = hint
    body.update(extra)
    sys.stdout.write(json.dumps(body, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(1)
