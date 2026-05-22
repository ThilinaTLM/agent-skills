"""`richdoc components` — list every rd-* tag with its schema."""

from __future__ import annotations

import click

from ..output import json_ok
from ..schema import load_schema
from ._safe import safe_command


@click.command("components")
@click.option(
    "--tag",
    "tag",
    default=None,
    help="Show only the spec for one rd-* tag (e.g. rd-stat).",
)
@safe_command
def cmd(tag: str | None) -> None:
    """List every richdoc tag with its allowed attributes and children."""
    schema = load_schema()
    entries = list(schema.tags.items())
    if tag is not None:
        entries = [(t, spec) for (t, spec) in entries if t == tag]

    json_ok(
        schemaPath=schema.path,
        generated=schema.generated,
        count=len(entries),
        tags=[{"tagName": t, **spec} for (t, spec) in entries],
    )
