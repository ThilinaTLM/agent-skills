"""`richdoc publish <target>` — top-level Click group.

This module owns just the `publish` group; each target's subcommand
tree lives next to its implementation (e.g.
`richdoc_cli.publish.confluence.cli.confluence_group`) so changes to a
publisher don't have to round-trip through `commands/`. Adding a new
target = create `richdoc_cli/publish/<target>/cli.py` exporting a
`<target>_group` click group, then attach it here.
"""

from __future__ import annotations

import click

from ..publish.confluence.cli import confluence_group


@click.group(name="publish", help="Publish a richdoc HTML to a remote system.")
def group() -> None:
    pass


group.add_command(confluence_group)
