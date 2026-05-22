"""Shim \u2014 the lint implementation lives in ``richdoc_cli.lint``.

The click command and the ``lint_path`` programmatic entry point both
moved into a dedicated package so the file-walker, rule modules, and
the source rewriter could be split apart. This shim re-exports the
public names so any caller importing
``richdoc_cli.commands.lint.lint_path`` keeps working.
"""

from __future__ import annotations

from ..lint import cmd, lint_path

__all__ = ["cmd", "lint_path"]
