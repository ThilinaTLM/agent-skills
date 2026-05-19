"""`richdoc new` — scaffold a new .html document from a template."""

from __future__ import annotations

import shutil
from pathlib import Path

import click

from ..assets import ASSET_FILES
from ..output import json_error, json_ok
from ..templates import list_templates, template_exists, template_path

DEFAULT_TEMPLATE = "plan"


@click.command("new")
@click.argument(
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option(
    "-t",
    "--template",
    "template",
    default=DEFAULT_TEMPLATE,
    show_default=True,
    help="Template to use.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Overwrite the output file if it exists.",
)
def cmd(output: Path, template: str, force: bool) -> None:
    """Scaffold a new richdoc .html file from a template."""
    available = list_templates()
    if not template_exists(template):
        json_error(
            f"Unknown template '{template}'.",
            code="TEMPLATE_NOT_FOUND",
            hint=f"Available templates: {', '.join(available) if available else '(none)'}",
            available=available,
        )

    out_path = output.resolve()
    if out_path.suffix.lower() != ".html":
        json_error(
            f"Output path must end with .html (got '{out_path}').",
            code="INVALID_PARAMS",
        )

    if out_path.exists() and not force:
        json_error(
            f"Output file already exists: {out_path}",
            code="FILE_EXISTS",
            hint="Re-run with --force to overwrite.",
            file=str(out_path),
        )

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_path(template), out_path)
    except OSError as exc:
        json_error(
            f"Could not write output: {exc}",
            code="OUTPUT_ERROR",
        )

    # Whether the linked assets are present next to the output file.
    parent = out_path.parent
    missing = [f for f in ASSET_FILES if not (parent / f).is_file()]
    hint = (
        f"Run `richdoc init {parent}` to drop the CSS/JS assets next to this file."
        if missing
        else None
    )
    json_ok(
        file=str(out_path),
        template=template,
        assets_needed=missing,
        **({"hint": hint} if hint else {}),
    )
