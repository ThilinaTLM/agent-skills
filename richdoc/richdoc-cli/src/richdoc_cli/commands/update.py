"""`richdoc update` \u2014 refresh shipped assets in existing doc folders.

Walks a directory tree, identifies every folder that contains the shipped
asset filenames (richdoc.css + richdoc.js), and compares each local file's
SHA-256 against the shipped asset's SHA-256. Read-only by default; pass
``--apply`` to overwrite stale / missing files.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import click

from ..assets import (
    ASSET_FILES,
    asset_path,
    asset_sha256,
    assets_exist,
    file_sha256,
    shipped_version_info,
)
from ..output import json_error, json_ok
from ._safe import safe_command

# Directories pruned from recursive walks unless --include-hidden is set.
# .git is always pruned (even with --include-hidden) to avoid pathological
# scans of pack files.
JUNK_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
        ".next",
        ".svelte-kit",
        "__pycache__",
    }
)
ALWAYS_PRUNED: frozenset[str] = frozenset({".git"})


def _is_richdoc_folder(d: Path) -> bool:
    return all((d / name).is_file() for name in ASSET_FILES)


def _evaluate_folder(d: Path, shipped: dict[str, str]) -> list[dict[str, str]]:
    """Per-file status for one folder: 'up-to-date' | 'stale' | 'missing'."""
    files: list[dict[str, str]] = []
    for name in ASSET_FILES:
        local = d / name
        if not local.is_file():
            files.append({"name": name, "status": "missing"})
            continue
        try:
            local_hash = file_sha256(local)
        except OSError:
            files.append({"name": name, "status": "stale"})
            continue
        status = "up-to-date" if local_hash == shipped[name] else "stale"
        files.append({"name": name, "status": status})
    return files


def _discover(root: Path, recursive: bool, include_hidden: bool) -> list[Path]:
    """Yield doc folders rooted at *root*."""
    if not recursive:
        return [root] if _is_richdoc_folder(root) else []

    out: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root):
        # Prune in place so os.walk skips junk subtrees.
        if include_hidden:
            dirnames[:] = [d for d in dirnames if d not in ALWAYS_PRUNED]
        else:
            dirnames[:] = [d for d in dirnames if d not in JUNK_DIRS]
        here = Path(dirpath)
        if _is_richdoc_folder(here):
            out.append(here)
    return out


@click.command("update")
@click.argument(
    "root",
    metavar="[ROOT]",
    required=False,
    default=".",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--apply",
    "apply_",
    is_flag=True,
    help="Overwrite stale assets. Default is report-only.",
)
@click.option(
    "--no-recursive",
    "recursive",
    flag_value=False,
    default=True,
    help="Only inspect ROOT, do not descend into subdirectories.",
)
@click.option(
    "--include-hidden",
    is_flag=True,
    help="Do not skip junk directories (node_modules, .venv, dist, ...).",
)
@safe_command
def cmd(root: Path, apply_: bool, recursive: bool, include_hidden: bool) -> None:
    """Check / refresh shipped assets in existing richdoc folders."""
    if not assets_exist():
        json_error(
            "Shipped assets are missing from the richdoc skill installation.",
            code="INPUT_ERROR",
            hint="Ensure the skill folder contains both assets/richdoc.css and assets/richdoc.js.",
        )

    root_abs = root.resolve()
    if not root_abs.is_dir():
        json_error(
            f"ROOT is not a directory: {root_abs}",
            code="INVALID_PARAMS",
        )

    shipped_hashes: dict[str, str] = {name: asset_sha256(name) for name in ASSET_FILES}
    folders = _discover(root_abs, recursive=recursive, include_hidden=include_hidden)

    up_to_date: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    for d in folders:
        files = _evaluate_folder(d, shipped_hashes)
        if all(f["status"] == "up-to-date" for f in files):
            up_to_date.append({"dir": str(d)})
        else:
            stale.append({"dir": str(d), "files": files})

    shipped_meta: dict[str, Any] = {"files": list(ASSET_FILES)}
    info = shipped_version_info()
    if info:
        shipped_meta.update(info)

    if not apply_:
        payload: dict[str, Any] = {
            "root": str(root_abs),
            "recursive": recursive,
            "shipped": shipped_meta,
            "scanned": len(folders),
            "up_to_date": up_to_date,
            "stale": stale,
            "applied": False,
        }
        if stale:
            n = len(stale)
            payload["hint"] = (
                f"{n} folder{'s' if n != 1 else ''} out of date. "
                "Re-run with --apply to refresh."
            )
        elif not folders:
            payload["hint"] = (
                "No richdoc folders found. A folder must contain both "
                f"{' and '.join(ASSET_FILES)} to be picked up."
            )
        json_ok(**payload)

    # --apply: overwrite stale/missing files. Best-effort \u2014 per-file errors are
    # collected but do not abort the run unless every write failed.
    applied: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    attempted_writes = 0
    successful_writes = 0

    for entry in stale:
        d = Path(entry["dir"])
        written: list[str] = []
        for f in entry["files"]:
            if f["status"] == "up-to-date":
                continue
            attempted_writes += 1
            name = f["name"]
            try:
                shutil.copyfile(asset_path(name), d / name)
                written.append(name)
                successful_writes += 1
            except OSError as exc:
                errors.append({"dir": str(d), "file": name, "error": str(exc)})
        applied.append({"dir": str(d), "written": written})

    if attempted_writes > 0 and successful_writes == 0:
        json_error(
            "Every asset write failed. Check directory permissions.",
            code="OUTPUT_ERROR",
            errors=errors,
        )

    payload = {
        "root": str(root_abs),
        "recursive": recursive,
        "shipped": shipped_meta,
        "scanned": len(folders),
        "up_to_date": up_to_date,
        "refreshed": applied,
        "applied": True,
    }
    if errors:
        payload["errors"] = errors
        payload["hint"] = (
            f"{len(errors)} file write{'s' if len(errors) != 1 else ''} failed; "
            "see errors[]."
        )
    json_ok(**payload)
