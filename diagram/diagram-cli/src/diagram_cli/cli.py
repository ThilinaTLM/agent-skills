"""Top-level Click group for the `diagram` CLI."""

from __future__ import annotations

import logging
import sys

import click

from diagram_cli import __version__, output
from diagram_cli.commands.render import render_command
from diagram_cli.commands.types import types_command


# Silence httpx/httpcore INFO chatter — only JSON envelopes hit stdout, but
# library logs default to stderr and would clutter agent runs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@click.group(help="Render diagrams (PlantUML, Mermaid, GraphViz, D2, ...) via Kroki.")
@click.version_option(__version__, prog_name="diagram")
def cli() -> None:
    pass


cli.add_command(render_command)
cli.add_command(types_command)


def entrypoint() -> None:
    """Console-script entrypoint with a safety net for unexpected errors."""
    try:
        cli.main(standalone_mode=True)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover — defensive
        sys.exit(
            output.emit_error(
                "INTERNAL_ERROR",
                "Unexpected internal error.",
                f"{type(exc).__name__}: {exc}",
            )
        )


if __name__ == "__main__":
    entrypoint()
