"""Shared error trap + write-error helper for click commands.

Every CLI command lifts a small number of well-known exceptions into a
JSON error envelope. Before this module each command repeated the same
``try`` / ``except`` block five times; ``safe_command`` centralises
the mapping so the command bodies stay focused on the happy path.

Mapping:

  - ``FileExistsError``     -> ``FILE_EXISTS`` (with the ``--force`` hint)
  - ``SchemaLoadError``     -> ``INPUT_ERROR``
  - ``OSError``             -> ``INPUT_ERROR`` (best guess; commands that
                              need ``OUTPUT_ERROR`` route through
                              ``write_or_error`` for the write step)

Any exception not listed escapes the decorator and is caught by
``cli.py``'s top-level trap as ``INTERNAL_ERROR``.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from ..output import json_error
from ..schema import SchemaLoadError

__all__ = ["safe_command", "write_or_error"]

P = ParamSpec("P")
R = TypeVar("R")


def safe_command(fn: Callable[P, R]) -> Callable[P, R]:
    """Wrap a click command so known exceptions become JSON errors.

    ``json_error`` calls ``sys.exit(1)`` and never returns; the wrapper
    therefore can't actually return to its caller after handling an
    exception. The ``Callable`` signature is preserved so click's type
    inference stays clean.
    """

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except FileExistsError as exc:
            json_error(
                str(exc),
                code="FILE_EXISTS",
                hint="Re-run with --force to overwrite.",
            )
        except SchemaLoadError as exc:
            json_error(str(exc), code="INPUT_ERROR")
        except OSError as exc:
            json_error(f"I/O error: {exc}", code="INPUT_ERROR")

    return wrapper


def write_or_error(action: Callable[[], None]) -> None:
    """Run ``action`` and convert any ``OSError`` into ``OUTPUT_ERROR``.

    Wrap the file-write step in this helper when an ``OSError`` should
    surface as ``OUTPUT_ERROR`` rather than the ``INPUT_ERROR`` default
    of ``safe_command``. Example::

        write_or_error(lambda: out_path.write_bytes(data))
    """
    try:
        action()
    except OSError as exc:
        json_error(f"Could not write output: {exc}", code="OUTPUT_ERROR")
