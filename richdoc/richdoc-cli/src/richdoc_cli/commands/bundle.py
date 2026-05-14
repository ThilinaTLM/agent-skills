"""`richdoc bundle` — inline relative-path deps into a self-contained HTML."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ..inline import bundle as bundle_html
from ..output import json_error, json_ok


@click.command("bundle")
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
    help="Output path. Use '-' for stdout (suppresses the JSON envelope). Default: <input>.bundle.html.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Overwrite the output file if it exists.",
)
def cmd(input_: Path, output: Path | None, force: bool) -> None:
    """Produce a self-contained HTML by inlining every relative-path dependency.

    Absolute URLs (CDN, Google Fonts) are kept as-is — the recipient is expected
    to have internet when opening the bundle.
    """
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

    result = bundle_html(source, base_dir=in_path.parent)

    if output is not None and str(output) == "-":
        sys.stdout.write(result.html)
        sys.stdout.flush()
        return

    out_path = (
        output.resolve()
        if output is not None
        else in_path.with_suffix("").with_suffix(".bundle.html")
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
        out_path.write_text(result.html, encoding="utf-8")
    except OSError as exc:
        json_error(f"Could not write output: {exc}", code="OUTPUT_ERROR")

    payload: dict = {
        "input": str(in_path),
        "output": str(out_path),
        "inlined": result.inlined,
        "kept_absolute": result.kept_absolute,
        "missing": result.missing,
    }
    if result.missing:
        payload["hint"] = (
            "Some relative assets could not be read. "
            "The bundle still works but those references stay relative."
        )
    json_ok(**payload)
