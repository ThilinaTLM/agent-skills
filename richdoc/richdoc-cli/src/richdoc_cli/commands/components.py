"""`richdoc components` — list every rd-* tag with its schema."""

from __future__ import annotations

import click

from ..output import json_error, json_ok
from ..schema import SchemaLoadError, load_schema


@click.command("components")
@click.option(
    "--tag",
    "tag",
    default=None,
    help="Show only the spec for one rd-* tag (e.g. rd-stat).",
)
def cmd(tag: str | None) -> None:
    """List every richdoc tag with its allowed attributes and children."""
    try:
        schema = load_schema()
    except SchemaLoadError as exc:
        json_error(str(exc), code="INPUT_ERROR")

    entries = list(schema.tags.items())
    if tag is not None:
        entries = [(t, spec) for (t, spec) in entries if t == tag]

    json_ok(
        schemaPath=schema.path,
        generated=schema.generated,
        count=len(entries),
        tags=[{"tagName": t, **spec} for (t, spec) in entries],
    )
