"""Resolve diagram source (file / inline / stdin) and the diagram type.

All failures raise `InputError`, a typed exception that the `render` command
translates into the appropriate JSON error envelope.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from diagram_cli.catalog import TypeInfo, lookup_type, type_for_extension


class InputError(Exception):
    """Raised when source/type inputs are missing, conflicting, or unreadable."""

    def __init__(self, code: str, message: str, hint: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


@dataclass(frozen=True)
class ResolvedSource:
    text: str
    extension: str | None  # e.g. '.puml', or None if unknown (inline/stdin)
    origin: str  # 'file' | 'source' | 'stdin' — informational


def resolve_source(
    input_path: str | None,
    source: str | None,
    *,
    stdin_isatty: bool,
) -> ResolvedSource:
    """Resolve the diagram source from exactly one of file/inline/stdin."""
    provided = sum(x is not None for x in (input_path, source))
    if provided > 1:
        raise InputError(
            "INPUT_CONFLICT",
            "Pass only one of --input or --source.",
            "Choose one source: --input <path>, --source <inline>, or pipe via stdin.",
        )

    if input_path is not None:
        path = Path(input_path).expanduser()
        if not path.exists():
            raise InputError(
                "INPUT_NOT_FOUND",
                f"Input file not found: {path}",
                "Check the path. Use an absolute path or one relative to the current working directory.",
            )
        if not path.is_file():
            raise InputError(
                "INPUT_NOT_FOUND",
                f"Input path is not a regular file: {path}",
                "Provide a path to a text file containing the diagram source.",
            )
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise InputError(
                "INPUT_NOT_FOUND",
                f"Input file is not valid UTF-8: {path}",
                f"Convert the file to UTF-8 and retry. ({exc.reason})",
            ) from exc
        except OSError as exc:
            raise InputError(
                "INPUT_NOT_FOUND",
                f"Could not read input file: {path}",
                str(exc),
            ) from exc
        # Strip UTF-8 BOM if present.
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")
        return ResolvedSource(text=text, extension=path.suffix.lower() or None, origin="file")

    if source is not None:
        if source == "":
            raise InputError(
                "INPUT_MISSING",
                "--source value is empty.",
                "Pass non-empty diagram source, or use --input <path> / pipe via stdin.",
            )
        return ResolvedSource(text=source, extension=None, origin="source")

    # Neither flag given — try stdin.
    if stdin_isatty:
        raise InputError(
            "INPUT_MISSING",
            "No diagram source provided.",
            "Pass --input <path>, --source <inline>, or pipe the diagram source via stdin.",
        )
    text = sys.stdin.read()
    if not text.strip():
        raise InputError(
            "INPUT_MISSING",
            "Stdin contained no diagram source.",
            "Pipe a non-empty diagram source, or use --input / --source instead.",
        )
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    return ResolvedSource(text=text, extension=None, origin="stdin")


def resolve_type(explicit_type: str | None, source_extension: str | None) -> TypeInfo:
    """Resolve the diagram type, preferring an explicit --type flag."""
    if explicit_type:
        info = lookup_type(explicit_type)
        if info is None:
            raise InputError(
                "TYPE_UNKNOWN",
                f"Unknown diagram type: {explicit_type}",
                "Run `diagram types` to list supported diagram types.",
            )
        return info

    if source_extension:
        info = type_for_extension(source_extension)
        if info is not None:
            return info

    raise InputError(
        "TYPE_MISSING",
        "Could not determine diagram type.",
        "Pass --type <name> explicitly. Run `diagram types` to list supported types.",
    )
