"""`richdoc export-md` — convert a richdoc HTML file to GitHub-flavored markdown."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ..markdown import html_to_markdown
from ..output import json_error, json_ok


@click.command("export-md")
@click.argument(
    "input_",
    metavar="INPUT",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
)
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output path. Use '-' for stdout (suppresses the JSON envelope). Default: <input>.md.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Overwrite the output file if it exists.",
)
def cmd(input_: Path, output: Path | None, force: bool) -> None:
    """Convert a richdoc HTML file to GitHub-flavored markdown."""
    in_path = input_.resolve()
    if in_path.suffix.lower() != ".html":
        json_error(
            f"Input must be a .html file (got '{in_path}').",
            code="INVALID_PARAMS",
        )

    try:
        source = in_path.read_text(encoding="utf-8")
    except OSError as exc:
        json_error(f"Could not read input: {exc}", code="INPUT_ERROR")

    markdown, dropped = html_to_markdown(source)

    if output is not None and str(output) == "-":
        sys.stdout.write(markdown)
        sys.stdout.flush()
        return

    out_path = output.resolve() if output is not None else in_path.with_suffix(".md")

    if out_path.exists() and not force:
        json_error(
            f"Output file already exists: {out_path}",
            code="FILE_EXISTS",
            hint="Re-run with --force to overwrite.",
            file=str(out_path),
        )

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        json_error(f"Could not write output: {exc}", code="OUTPUT_ERROR")

    json_ok(
        input=str(in_path),
        output=str(out_path),
        bytes=len(markdown.encode("utf-8")),
        dropped=sorted(set(dropped)),
    )
