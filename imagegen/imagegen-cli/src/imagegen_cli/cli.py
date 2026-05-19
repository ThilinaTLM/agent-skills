"""imagegen CLI — click group, subcommand wiring, top-level error trap.

Every code path emits a single-line JSON envelope on stdout. Click's own
usage/help text is allowed to stay (it's printed on ``--help`` to stdout);
any other error or uncaught exception is wrapped in the standard envelope.
"""

from __future__ import annotations

import sys
from typing import NoReturn

import click

from . import __version__
from .commands.generate import cmd as generate_cmd
from .output import json_error


class AliasedGroup(click.Group):
    """click.Group that resolves a fixed alias map at lookup time."""

    aliases: dict[str, str] = {"gen": "generate"}

    def get_command(self, ctx, cmd_name):
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        return super().get_command(ctx, self.aliases.get(cmd_name, cmd_name))


@click.group(
    name="imagegen",
    cls=AliasedGroup,
    help="AI image generation via Google Gemini.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, prog_name="imagegen")
def main() -> None:  # pragma: no cover — pure dispatch
    pass


main.add_command(generate_cmd)  # `generate`; `gen` resolves via AliasedGroup


def entrypoint() -> NoReturn:
    """Console-script entry point. Wraps click in a JSON-safe error trap."""
    try:
        main.main(args=sys.argv[1:], prog_name="imagegen", standalone_mode=False)
    except click.exceptions.UsageError as exc:
        json_error(exc.format_message(), code="INVALID_PARAMS")
    except click.exceptions.Abort:
        json_error("Aborted.", code="INTERNAL_ERROR")
    except click.exceptions.ClickException as exc:
        json_error(exc.format_message(), code="INVALID_PARAMS")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — final safety net
        json_error(f"Internal error: {exc}", code="INTERNAL_ERROR")
    sys.exit(0)
