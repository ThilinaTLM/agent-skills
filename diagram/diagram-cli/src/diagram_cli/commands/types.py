"""`diagram types` — list supported diagram engines and their formats."""

from __future__ import annotations

import sys

import click

from diagram_cli import catalog, output
from diagram_cli.endpoint import resolve_endpoint


@click.command(
    "types",
    help="List supported diagram types and their output formats (no network call).",
)
@click.argument("name", required=False)
@click.option(
    "--endpoint",
    "endpoint_flag",
    type=str,
    default=None,
    help="Kroki base URL (only echoed in the response for context).",
)
def types_command(name: str | None, endpoint_flag: str | None) -> None:
    endpoint = resolve_endpoint(endpoint_flag)

    if name:
        info = catalog.lookup_type(name)
        if info is None:
            sys.exit(
                output.emit_error(
                    "TYPE_UNKNOWN",
                    f"Unknown diagram type: {name}",
                    "Run `diagram types` to list supported diagram types.",
                )
            )
        sys.exit(
            output.emit_ok(
                endpoint=endpoint,
                type=_serialize(info),
            )
        )

    sys.exit(
        output.emit_ok(
            endpoint=endpoint,
            types=[_serialize(t) for t in catalog.all_types()],
        )
    )


def _serialize(info: catalog.TypeInfo) -> dict[str, object]:
    return {
        "name": info.name,
        "slug": info.slug,
        "extensions": list(info.extensions),
        "formats": list(info.formats),
    }
