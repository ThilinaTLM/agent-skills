"""`richdoc init` — copy richdoc.css / richdoc.js into a target directory."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import click

from ..assets import ASSET_FILES, asset_path, assets_exist
from ..output import json_error, json_ok
from ._safe import safe_command, write_or_error


@click.command("init")
@click.argument(
    "dir_",
    metavar="DIR",
    required=False,
    default=".",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("-f", "--force", is_flag=True, help="Overwrite existing assets in target.")
@safe_command
def cmd(dir_: Path, force: bool) -> None:
    """Copy richdoc.css and richdoc.js into a directory."""
    if not assets_exist():
        json_error(
            "Shipped assets are missing from the richdoc skill installation.",
            code="INPUT_ERROR",
            hint="Ensure the skill folder contains both assets/richdoc.css and assets/richdoc.js.",
        )

    target_dir = dir_.resolve()
    write_or_error(lambda: target_dir.mkdir(parents=True, exist_ok=True))

    def _copy_one(dest: Path, name: str) -> Callable[[], None]:
        def _action() -> None:
            shutil.copyfile(asset_path(name), dest)

        return _action

    written: list[str] = []
    skipped: list[str] = []
    for name in ASSET_FILES:
        dest = target_dir / name
        if dest.exists() and not force:
            skipped.append(name)
            continue
        write_or_error(_copy_one(dest, name))
        written.append(name)

    hint = (
        "Some files already existed and were left alone. Re-run with --force to overwrite."
        if skipped
        else None
    )
    json_ok(
        dir=str(target_dir),
        written=written,
        skipped=skipped,
        **({"hint": hint} if hint else {}),
    )
