"""`diagram render` — render a diagram source via Kroki and write to disk."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from diagram_cli import catalog, output
from diagram_cli.endpoint import resolve_endpoint
from diagram_cli.inputs import InputError, resolve_source, resolve_type
from diagram_cli.render import KrokiUnavailable, RenderFailed, render


@click.command(
    "render",
    help=(
        "Render a diagram source (PlantUML, Mermaid, GraphViz, D2, ...) "
        "to a file via the Kroki HTTP API."
    ),
)
@click.option(
    "--input",
    "input_path",
    type=click.Path(dir_okay=False, path_type=str),
    default=None,
    help="Path to a file containing the diagram source.",
)
@click.option(
    "--source",
    type=str,
    default=None,
    help="Inline diagram source (alternative to --input).",
)
@click.option(
    "--type",
    "diagram_type",
    type=str,
    default=None,
    help="Diagram type (e.g. plantuml, mermaid, graphviz). Auto-detected from --input extension when omitted.",
)
@click.option(
    "--format",
    "fmt",
    type=str,
    default="svg",
    show_default=True,
    help="Output format (svg, png, pdf, jpeg, txt, base64). Support varies per diagram type.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=str),
    default=None,
    help="Destination file path (required). Parent directories will be created.",
)
@click.option(
    "--endpoint",
    "endpoint_flag",
    type=str,
    default=None,
    help="Kroki base URL. Overrides KROKI_URL env and .kroki-url file.",
)
@click.option(
    "--timeout",
    type=float,
    default=30.0,
    show_default=True,
    help="HTTP timeout in seconds.",
)
def render_command(
    input_path: str | None,
    source: str | None,
    diagram_type: str | None,
    fmt: str,
    output_path: str | None,
    endpoint_flag: str | None,
    timeout: float,
) -> None:
    exit_code = _run(
        input_path=input_path,
        source=source,
        diagram_type=diagram_type,
        fmt=fmt.lower(),
        output_path=output_path,
        endpoint_flag=endpoint_flag,
        timeout=timeout,
    )
    sys.exit(exit_code)


def _run(
    *,
    input_path: str | None,
    source: str | None,
    diagram_type: str | None,
    fmt: str,
    output_path: str | None,
    endpoint_flag: str | None,
    timeout: float,
) -> int:
    if not output_path:
        return output.emit_error(
            "OUTPUT_MISSING",
            "--output is required.",
            "Pass --output <path> so the rendered diagram can be written to disk.",
        )

    # 1. Source + type resolution
    try:
        resolved = resolve_source(input_path, source, stdin_isatty=sys.stdin.isatty())
        type_info = resolve_type(diagram_type, resolved.extension)
    except InputError as exc:
        return output.emit_error(exc.code, exc.message, exc.hint)

    # 2. Format compatibility (pre-flight)
    if not catalog.supports_format(type_info, fmt):
        supported = ", ".join(type_info.formats)
        return output.emit_error(
            "FORMAT_UNSUPPORTED",
            f"Output format '{fmt}' is not supported for diagram type '{type_info.name}'.",
            f"Supported formats for {type_info.name}: {supported}.",
            type=type_info.name,
            format=fmt,
            supportedFormats=list(type_info.formats),
        )

    # 3. Endpoint
    endpoint = resolve_endpoint(endpoint_flag)

    # 4. Render
    try:
        rendered = render(
            endpoint=endpoint,
            type_slug=type_info.slug,
            fmt=fmt,
            source=resolved.text,
            timeout=timeout,
        )
    except RenderFailed as exc:
        return output.emit_error(
            "RENDER_FAILED",
            f"Kroki rejected the diagram (HTTP {exc.status}).",
            exc.detail or "Check the diagram source for syntax errors.",
            type=type_info.name,
            format=fmt,
            endpoint=endpoint,
            status=exc.status,
        )
    except KrokiUnavailable as exc:
        return output.emit_error(
            "KROKI_UNAVAILABLE",
            "Could not reach the Kroki service.",
            (
                f"{exc.detail}. Verify the endpoint is reachable "
                "(set KROKI_URL or --endpoint for a self-hosted instance) and retry."
            ),
            endpoint=endpoint,
        )

    # 5. Write output
    out_path = Path(output_path).expanduser().resolve()
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(rendered)
    except OSError as exc:
        return output.emit_error(
            "IO_ERROR",
            f"Failed to write output file: {out_path}",
            str(exc),
        )

    return output.emit_ok(
        file=str(out_path),
        type=type_info.name,
        format=fmt,
        bytes=len(rendered),
        endpoint=endpoint,
        sourceOrigin=resolved.origin,
    )
