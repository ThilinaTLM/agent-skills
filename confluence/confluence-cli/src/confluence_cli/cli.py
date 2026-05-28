"""confluence CLI — click group, subcommand wiring, top-level error trap.

Every code path emits a single-line JSON envelope on stdout. Click's own
usage/help text is allowed to stay (it's printed on `--help` to stdout),
but any error or uncaught exception is wrapped in our standard envelope.
"""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable
from typing import NoReturn, ParamSpec, TypeVar

import click

from . import __version__
from .auth import AuthError
from .bundle import BundleError
from .client import ConfluenceError
from .commands.auth import group as auth_group
from .commands.download import cmd_download
from .commands.pages import cmd_page_by_id, cmd_pages, page_group
from .commands.publish_bundle import cmd_publish_bundle
from .commands.spaces import cmd_spaces
from .config import ConfigError
from .markdown import MarkdownError
from .output import json_error
from .publish import PublishError
from .refs import RefParseError


@click.group(
    name="confluence",
    help=(
        "Manage Confluence Cloud spaces, pages, and attachments; "
        "publish richdoc storage bundles."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, prog_name="confluence")
def main() -> None:  # pragma: no cover — pure dispatch
    pass


main.add_command(auth_group)
main.add_command(cmd_spaces)
main.add_command(cmd_pages)
main.add_command(cmd_page_by_id)
main.add_command(page_group)
main.add_command(cmd_publish_bundle)
main.add_command(cmd_download)


# ---------------------------------------------------------------------------
# Shared error trap
# ---------------------------------------------------------------------------


P = ParamSpec("P")
R = TypeVar("R")


def safe_command(fn: Callable[P, R]) -> Callable[P, R]:
    """Translate well-known exceptions into JSON error envelopes."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except AuthError as exc:
            extras: dict = {}
            if exc.missing:
                extras["missing"] = exc.missing
            json_error(str(exc), code=exc.code, hint=exc.hint, **extras)
        except RefParseError as exc:
            json_error(str(exc), code=exc.code, hint=exc.hint)
        except MarkdownError as exc:
            json_error(str(exc), code=exc.code, hint=exc.hint)
        except ConfigError as exc:
            json_error(str(exc), code="INVALID_PARAMS")
        except BundleError as exc:
            json_error(
                str(exc),
                code=exc.code,
                hint=getattr(exc, "hint", None),
            )
        except PublishError as exc:
            json_error(str(exc), code=exc.code)
        except ConfluenceError as exc:
            json_error(str(exc), code=getattr(exc, "code", "UPSTREAM_ERROR"))
        except FileNotFoundError as exc:
            json_error(str(exc), code="NOT_FOUND")
        except FileExistsError as exc:
            json_error(
                str(exc),
                code="FILE_EXISTS",
                hint="Re-run with --force to overwrite.",
            )
        except OSError as exc:
            json_error(f"I/O error: {exc}", code="INPUT_ERROR")

    return wrapper


def entrypoint() -> NoReturn:
    """Console-script entry point. Wraps click in a JSON-safe error trap."""
    try:
        main.main(args=sys.argv[1:], prog_name="confluence", standalone_mode=False)
    except click.exceptions.UsageError as exc:
        json_error(exc.format_message(), code="INVALID_PARAMS")
    except click.exceptions.Abort:
        json_error("Aborted.", code="INTERNAL_ERROR")
    except click.exceptions.ClickException as exc:
        json_error(exc.format_message(), code="INVALID_PARAMS")
    except SystemExit:
        raise
    except Exception as exc:
        json_error(f"Internal error: {exc}", code="INTERNAL_ERROR")
    sys.exit(0)
