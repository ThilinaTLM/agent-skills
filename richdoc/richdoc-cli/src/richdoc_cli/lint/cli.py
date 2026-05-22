"""``richdoc lint`` Click command \u2014 flag parsing + JSON envelope wiring.

The heavy lifting lives in ``runner.lint_path``; this module exists so
the click wiring isn't entangled with the rule-application code (which
is also imported in-process by ``publish confluence push``'s
pre-publish lint pass).
"""

from __future__ import annotations

from pathlib import Path

import click

from ..commands._safe import safe_command
from ..output import json_error, json_ok
from .runner import lint_path

__all__ = ["cmd"]


@click.command("lint")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--fix",
    "fix",
    is_flag=True,
    default=False,
    help="Autofix supported rules in place. Currently only "
    "`hero-nav-redundant` (strip legacy <a> children + meta nav segments "
    "from <rd-hero> in book mode). Book-mode TOC drift is never autofixed.",
)
@safe_command
def cmd(path: Path, fix: bool) -> None:
    """Validate richdoc HTML against the rd-* schema and book-mode rules."""
    result = lint_path(path, fix=fix)
    errors = result["errors"]
    warnings = result["warnings"]
    if errors > 0:
        json_error(
            f"Lint failed: {errors} error{'' if errors == 1 else 's'}, "
            f"{warnings} warning{'' if warnings == 1 else 's'}.",
            code="LINT_ERRORS",
            **result,
        )
    json_ok(**result)
