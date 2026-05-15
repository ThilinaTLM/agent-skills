"""`richdoc export <fmt> <input>` — unified export command.

Three subcommands:

- `md`   — produce a folder of markdown files, with a shared `assets/`.
           Books (rd-toc with rd-chapter[href]) auto-detected.
- `html` — produce a single self-contained `.html` file (relative deps
           inlined as data: URIs; CDN deps preserved).
- `docx` — produce a single `.docx` file with embedded images, intended
           for Confluence "Import Word document".
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ..export_assets import AssetStore
from ..book import discover_chapters
from ..inline import bundle as bundle_html
from ..markdown import html_to_markdown
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
    "-o",
    "--output",
    "output",
    type=click.Path(file_okay=False, path_type=Path),
    help="Output folder. Default: <input-stem>-md/ next to the input file.",
)
@click.option(
    "-f", "--force", is_flag=True, help="Overwrite existing files in the output folder."
)
@click.option(
    "--no-book",
    is_flag=True,
    help="Disable book auto-detection. Only the entry file is exported, "
    "even when its rd-toc lists other chapters.",
)
@click.option(
    "--include-remote-images",
    is_flag=True,
    help="Fetch http(s) image URLs and copy them into assets/ as well as "
    "relative ones.",
)
def cmd_md(
    input_: Path,
    output: Path | None,
    force: bool,
    no_book: bool,
    include_remote_images: bool,
) -> None:
    """Export to a folder of markdown files."""
    in_path = _require_html(input_)
    out_dir = (
        output.resolve()
        if output is not None
        else in_path.with_name(f"{in_path.stem}-md")
    )

    discovery = discover_chapters(in_path)
    chapters = discovery.chapters if not no_book else discovery.chapters[:1]
    is_book = discovery.is_book and not no_book

    store = AssetStore()
    written: list[str] = []
    dropped: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for ch in chapters:
        rel_md = ch.relative.with_suffix(".md") if is_book else Path(in_path.stem + ".md")
        # Asset paths are relative to the chapter's directory in the output tree.
        depth = len(rel_md.parts) - 1
        assets_subdir = ("../" * depth + "assets") if depth else "assets"
        md_text, ch_dropped = html_to_markdown(
            ch.html,
            asset_store=store,
            asset_base=ch.path.parent,
            include_remote_images=include_remote_images,
            assets_subdir=assets_subdir,
        )
        dropped.extend(ch_dropped)
        target = (out_dir / rel_md).resolve()
        if target.exists() and not force:
            json_error(
                f"Output file already exists: {target}",
                code="FILE_EXISTS",
                hint="Re-run with --force to overwrite.",
                file=str(target),
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md_text, encoding="utf-8")
        written.append(str(target.relative_to(out_dir)))

    asset_map: dict[str, str] = {}
    if any(True for _ in store.items()):
        asset_map = store.write_to(out_dir / "assets")

    json_ok(
        input=str(in_path),
        output=str(out_dir),
        book=is_book,
        chapters=written,
        assets=len(asset_map),
        missing=store.missing,
        dropped=sorted(set(dropped)),
    )


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
    "-o",
    "--output",
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output path. Use '-' for stdout. Default: <input-stem>.bundle.html.",
)
@click.option(
    "-f", "--force", is_flag=True, help="Overwrite the output file if it exists."
)
def cmd_html(input_: Path, output: Path | None, force: bool) -> None:
    """Export to a single self-contained .html file."""
    in_path = _require_html(input_)
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
    "-o",
    "--output",
    "output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output path. Use '-' for stdout (bytes). Default: <input-stem>.docx.",
)
@click.option(
    "-f", "--force", is_flag=True, help="Overwrite the output file if it exists."
)
@click.option(
    "--no-book",
    is_flag=True,
    help="Disable book auto-detection. Only the entry file is rendered.",
)
@click.option(
    "--no-render-diagrams",
    is_flag=True,
    help="Skip server-side rendering of rd-mermaid / rd-plantuml; embed source "
    "as a code block instead.",
)
@click.option(
    "--diagram-endpoint",
    default="https://kroki.io",
    show_default=True,
    help="Kroki-compatible server used to render diagrams.",
)
def cmd_docx(
    input_: Path,
    output: Path | None,
    force: bool,
    no_book: bool,
    no_render_diagrams: bool,
    diagram_endpoint: str,
) -> None:
    """Export to a single .docx file (Confluence-import compatible)."""
    # Import lazily — python-docx adds ~50 ms to startup we don't want for the
    # other subcommands.
    from ..docx_export import chapters_to_docx, html_to_docx

    in_path = _require_html(input_)
    discovery = discover_chapters(in_path)

    if discovery.is_book and not no_book:
        result = chapters_to_docx(
            discovery.chapters,
            book_base=in_path.parent,
            render_diagrams=not no_render_diagrams,
            diagram_endpoint=diagram_endpoint,
        )
    else:
        source = in_path.read_text(encoding="utf-8")
        result = html_to_docx(
            source,
            base_dir=in_path.parent,
            render_diagrams=not no_render_diagrams,
            diagram_endpoint=diagram_endpoint,
        )

    if output is not None and str(output) == "-":
        sys.stdout.buffer.write(result.data)
        sys.stdout.flush()
        return

    out_path = (
        output.resolve() if output is not None else in_path.with_suffix(".docx")
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
        out_path.write_bytes(result.data)
    except OSError as exc:
        json_error(f"Could not write output: {exc}", code="OUTPUT_ERROR")

    json_ok(
        input=str(in_path),
        output=str(out_path),
        bytes=len(result.data),
        book=discovery.is_book and not no_book,
        images_embedded=result.images_embedded,
        diagrams_rendered=result.diagrams_rendered,
        diagrams_failed=result.diagrams_failed,
        missing=result.missing,
        dropped=result.dropped,
    )


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
