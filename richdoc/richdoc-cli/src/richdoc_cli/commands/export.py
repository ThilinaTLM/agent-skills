"""`richdoc export <fmt> <input>` — unified export command.

Three subcommands, one consistent flag layout:

    richdoc export md   INPUT [-o OUT] [-f] [--no-book] [--single|--multi] …
    richdoc export html INPUT [-o OUT] [-f] [--no-book] [--single|--multi]
    richdoc export docx INPUT [-o OUT] [-f] [--no-book] [--single|--multi] …

- `--single`: produce one output file containing the whole book.
- `--multi`:  produce one output file per chapter, in a mirrored folder.
- For a non-book input both flags collapse to the same behavior (one
  file); the envelope reports `mode_collapsed: true` so the caller knows.

This module is intentionally thin: it parses flags, delegates to the
appropriate pipeline in `export.<fmt>.pipeline`, and turns the structured
result into a JSON envelope.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ..export.common.modes import ExportMode
from ..output import json_error, json_ok


@click.group("export", help="Export a richdoc HTML file to markdown / html / docx.")
def group() -> None:
    pass


# ---------------------------------------------------------------------------
# md
# ---------------------------------------------------------------------------


@group.command("md")
@click.argument(
    "input_",
    metavar="INPUT",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
)
@click.option(
    "-o", "--output", "output",
    type=click.Path(path_type=Path),
    help="Output path. Single mode → file; multi mode → folder. "
    "Default: <stem>.md (single) or <stem>-md/ (multi).",
)
@click.option(
    "-f", "--force", is_flag=True, help="Overwrite existing output."
)
@click.option(
    "--no-book", is_flag=True,
    help="Disable book auto-detection. Only the entry file is exported.",
)
@click.option(
    "--single", "single_flag", is_flag=True,
    help="Combine the whole book into one .md.",
)
@click.option(
    "--multi", "multi_flag", is_flag=True,
    help="Render one .md per chapter (default for books).",
)
@click.option(
    "--include-remote-images", is_flag=True,
    help="Fetch http(s) image URLs and copy them into assets/.",
)
def cmd_md(
    input_: Path,
    output: Path | None,
    force: bool,
    no_book: bool,
    single_flag: bool,
    multi_flag: bool,
    include_remote_images: bool,
) -> None:
    """Export to markdown (single .md or a folder of .md per chapter)."""
    in_path = _require_html(input_)
    mode = _resolve_mode(single_flag, multi_flag, default=ExportMode.MULTI)

    from ..export.md.pipeline import export_md  # noqa: PLC0415

    try:
        result = export_md(
            in_path,
            output=output,
            mode=mode,
            no_book=no_book,
            include_remote_images=include_remote_images,
            force=force,
        )
    except FileExistsError as exc:
        json_error(str(exc), code="FILE_EXISTS", hint="Re-run with --force to overwrite.")
    except OSError as exc:
        json_error(f"Could not write output: {exc}", code="OUTPUT_ERROR")

    plan = result.plan
    payload: dict = {
        "input": str(in_path),
        "output": str(plan.root),
        "mode": plan.mode.value,
        "book": result.is_book,
        "chapters": _relative_paths(result.chapters_written, plan.root, plan.mode),
        "assets": result.assets_written,
        "missing": result.missing,
        "dropped": result.dropped,
    }
    json_ok(**payload)


# ---------------------------------------------------------------------------
# html
# ---------------------------------------------------------------------------


@group.command("html")
@click.argument(
    "input_",
    metavar="INPUT",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
)
@click.option(
    "-o", "--output", "output",
    type=click.Path(path_type=Path),
    help="Output path. Single mode → file (use '-' for stdout); "
    "multi mode → folder. Default: <stem>.bundle.html (single) or "
    "<stem>-html/ (multi).",
)
@click.option(
    "-f", "--force", is_flag=True, help="Overwrite existing output."
)
@click.option(
    "--no-book", is_flag=True,
    help="Disable book auto-detection. Only the entry file is exported.",
)
@click.option(
    "--single", "single_flag", is_flag=True,
    help="Inline only the entry file (default).",
)
@click.option(
    "--multi", "multi_flag", is_flag=True,
    help="Bundle each chapter into its own .bundle.html under a folder.",
)
def cmd_html(
    input_: Path,
    output: Path | None,
    force: bool,
    no_book: bool,
    single_flag: bool,
    multi_flag: bool,
) -> None:
    """Export to a self-contained .html (single) or a folder of bundles (multi)."""
    in_path = _require_html(input_)
    mode = _resolve_mode(single_flag, multi_flag, default=ExportMode.SINGLE)

    # `-o -` → stdout (single mode only).
    if output is not None and str(output) == "-":
        if mode is ExportMode.MULTI:
            json_error(
                "Cannot write to stdout in --multi mode (multiple files).",
                code="INVALID_PARAMS",
            )
        from ..export.html.pipeline import bundle_to_string  # noqa: PLC0415

        try:
            text = bundle_to_string(in_path)
        except OSError as exc:
            json_error(f"Could not read input: {exc}", code="INPUT_ERROR")
        sys.stdout.write(text)
        sys.stdout.flush()
        return

    from ..export.html.pipeline import export_html  # noqa: PLC0415

    try:
        result = export_html(
            in_path,
            output=output,
            mode=mode,
            no_book=no_book,
            force=force,
        )
    except FileExistsError as exc:
        json_error(str(exc), code="FILE_EXISTS", hint="Re-run with --force to overwrite.")
    except OSError as exc:
        json_error(f"Could not write output: {exc}", code="OUTPUT_ERROR")

    plan = result.plan
    payload: dict = {
        "input": str(in_path),
        "output": str(plan.root),
        "mode": plan.mode.value,
        "book": result.is_book,
        "files": _relative_paths(result.files_written, plan.root, plan.mode),
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


# ---------------------------------------------------------------------------
# docx
# ---------------------------------------------------------------------------


@group.command("docx")
@click.argument(
    "input_",
    metavar="INPUT",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
)
@click.option(
    "-o", "--output", "output",
    type=click.Path(path_type=Path),
    help="Output path. Single mode → file (use '-' for stdout, bytes); "
    "multi mode → folder. Default: <stem>.docx (single) or <stem>-docx/ (multi).",
)
@click.option(
    "-f", "--force", is_flag=True, help="Overwrite existing output."
)
@click.option(
    "--no-book", is_flag=True,
    help="Disable book auto-detection. Only the entry file is rendered.",
)
@click.option(
    "--single", "single_flag", is_flag=True,
    help="Combine the whole book into one .docx with page breaks (default).",
)
@click.option(
    "--multi", "multi_flag", is_flag=True,
    help="Render one .docx per chapter, mirroring the source tree.",
)
@click.option(
    "--no-render-diagrams", is_flag=True,
    help="Skip server-side rendering of rd-diagram; embed "
    "source as a code block instead.",
)
@click.option(
    "--diagram-endpoint", default="https://kroki.io", show_default=True,
    help="Kroki-compatible server used to render diagrams.",
)
def cmd_docx(
    input_: Path,
    output: Path | None,
    force: bool,
    no_book: bool,
    single_flag: bool,
    multi_flag: bool,
    no_render_diagrams: bool,
    diagram_endpoint: str,
) -> None:
    """Export to .docx (single concatenated or per-chapter folder)."""
    in_path = _require_html(input_)
    mode = _resolve_mode(single_flag, multi_flag, default=ExportMode.SINGLE)
    render_diagrams = not no_render_diagrams

    # `-o -` → stdout bytes (single mode only).
    if output is not None and str(output) == "-":
        if mode is ExportMode.MULTI:
            json_error(
                "Cannot write to stdout in --multi mode (multiple files).",
                code="INVALID_PARAMS",
            )
        from ..export.docx.pipeline import render_to_bytes  # noqa: PLC0415

        try:
            docx = render_to_bytes(
                in_path,
                no_book=no_book,
                render_diagrams=render_diagrams,
                diagram_endpoint=diagram_endpoint,
            )
        except OSError as exc:
            json_error(f"Could not read input: {exc}", code="INPUT_ERROR")
        sys.stdout.buffer.write(docx.data)
        sys.stdout.flush()
        return

    from ..export.docx.pipeline import export_docx  # noqa: PLC0415

    try:
        result = export_docx(
            in_path,
            output=output,
            mode=mode,
            no_book=no_book,
            render_diagrams=render_diagrams,
            diagram_endpoint=diagram_endpoint,
            force=force,
        )
    except FileExistsError as exc:
        json_error(str(exc), code="FILE_EXISTS", hint="Re-run with --force to overwrite.")
    except OSError as exc:
        json_error(f"Could not write output: {exc}", code="OUTPUT_ERROR")

    plan = result.plan
    payload: dict = {
        "input": str(in_path),
        "output": str(plan.root),
        "mode": plan.mode.value,
        "book": result.is_book,
        "files": _relative_paths(result.files_written, plan.root, plan.mode),
        "bytes": result.bytes_total,
        "images_embedded": result.images_embedded,
        "diagrams_rendered": result.diagrams_rendered,
        "diagrams_failed": result.diagrams_failed,
        "missing": result.missing,
        "dropped": result.dropped,
    }
    json_ok(**payload)


# ---------------------------------------------------------------------------
# shared
# ---------------------------------------------------------------------------


def _require_html(path: Path) -> Path:
    p = path.resolve()
    if p.suffix.lower() not in (".html", ".htm"):
        json_error(
            f"Input must be a .html file (got '{p}').", code="INVALID_PARAMS"
        )
    return p


def _relative_paths(paths: list[Path], root: Path, mode: ExportMode) -> list[str]:
    """Render written paths as strings relative to the natural display root.

    For MULTI: relative to the output folder (the chapter tree shows through).
    For SINGLE: just the file name (the root *is* the file).
    """
    if mode is ExportMode.MULTI:
        return [str(p.relative_to(root)) for p in paths]
    return [p.name for p in paths]


def _resolve_mode(single: bool, multi: bool, *, default: ExportMode) -> ExportMode:
    if single and multi:
        json_error(
            "--single and --multi are mutually exclusive.",
            code="INVALID_PARAMS",
        )
    if single:
        return ExportMode.SINGLE
    if multi:
        return ExportMode.MULTI
    return default
