"""richdoc CLI — click group, subcommand wiring, top-level error trap.

Every code path emits a single-line JSON envelope on stdout. Click's own
usage/help text is allowed to stay (it's printed on `--help` to stdout), but
any error or uncaught exception is wrapped in our standard envelope.
"""

from __future__ import annotations

import sys
from typing import NoReturn

import click

from . import __version__
from .commands.bundle import cmd as bundle_cmd
from .commands.components import cmd as components_cmd
from .commands.export_md import cmd as export_md_cmd
from .commands.init_ import cmd as init_cmd
from .commands.lint import cmd as lint_cmd
from .commands.new_ import cmd as new_cmd
from .output import json_error


@click.group(
    name="richdoc",
    help=(
        "Scaffold, validate, and ship rich HTML documents built from the "
        "richdoc component vocabulary."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, prog_name="richdoc")
def main() -> None:  # pragma: no cover — pure dispatch
    pass


main.add_command(new_cmd)
main.add_command(init_cmd)
main.add_command(lint_cmd)
main.add_command(components_cmd)
main.add_command(export_md_cmd)
main.add_command(bundle_cmd)


def entrypoint() -> NoReturn:
    """Console-script entry point. Wraps click in a JSON-safe error trap."""
    # Let `--help` / `--version` work as usual (click handles them via
    # SystemExit(0)). Convert click errors and unexpected exceptions into
    # our JSON envelope.
    try:
        main.main(args=sys.argv[1:], prog_name="richdoc", standalone_mode=False)
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
