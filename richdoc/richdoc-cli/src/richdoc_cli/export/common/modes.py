"""Shared types and helpers for `--single` / `--multi` export modes.

`ExportMode` makes the two output shapes explicit:
- `SINGLE` — produce one output file containing the whole book.
- `MULTI`  — produce one output file per chapter, in a folder mirroring
              the source tree.

For a non-book input (or `--no-book`) both modes collapse to a single
file. The pipeline emits a `mode_collapsed` note in the envelope so the
caller knows their flag had no effect.

`OutputPlan` precomputes "given these inputs, here are the on-disk
locations I will write to". Each pipeline calls `plan_outputs()` once and
then writes; the command layer can consult the same plan for the JSON
envelope without re-deriving paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..book import ChapterFile


class ExportMode(str, Enum):
    SINGLE = "single"
    MULTI = "multi"


@dataclass(frozen=True)
class ChapterTarget:
    """One on-disk destination for one chapter."""

    chapter: ChapterFile
    # Absolute path the chapter will be written to.
    target: Path
    # Path relative to the output root (used for envelope reporting).
    relative: Path


@dataclass
class OutputPlan:
    """Resolved output locations for a single export invocation."""

    mode: ExportMode
    # For SINGLE: the one output file. For MULTI: the output folder root.
    root: Path
    # Empty for SINGLE; one entry per chapter for MULTI.
    chapter_targets: list[ChapterTarget] = field(default_factory=list)


def plan_outputs(
    *,
    entry: Path,
    chapters: list[ChapterFile],
    is_book: bool,
    mode: ExportMode,
    output: Path | None,
    single_suffix: str,
    multi_suffix: str,
    chapter_suffix: str,
) -> OutputPlan:
    """Compute the on-disk plan for one export invocation.

    Arguments:
        entry: the entry HTML file the user passed.
        chapters: ordered chapter list from `discover_chapters`.
        is_book: True if the entry has a multi-chapter rd-toc and
            `--no-book` wasn't passed.
        mode: requested `ExportMode`. Collapses to SINGLE for non-books.
        output: user-supplied `-o`. None means "use a default next to
            the entry file".
        single_suffix: filename suffix for single mode (e.g. ".bundle.html",
            ".docx", ".md").
        multi_suffix: default folder-name suffix for multi mode
            (e.g. "-html", "-docx", "-md").
        chapter_suffix: file extension for individual chapters in multi
            mode (e.g. ".html", ".docx", ".md").
    """
    entry = entry.resolve()
    if mode is ExportMode.SINGLE:
        root = output.resolve() if output is not None else entry.with_name(
            entry.stem + single_suffix
        )
        return OutputPlan(mode=mode, root=root)

    # MULTI: one file per chapter inside a folder. For a non-book input the
    # folder contains exactly one file — historically this is what users
    # get from `richdoc export md` on a single-file doc.
    folder = output.resolve() if output is not None else entry.with_name(
        entry.stem + multi_suffix
    )
    targets: list[ChapterTarget] = []
    for ch in chapters:
        rel = ch.relative.with_suffix(chapter_suffix)
        targets.append(
            ChapterTarget(
                chapter=ch,
                target=(folder / rel).resolve(),
                relative=rel,
            )
        )
    return OutputPlan(mode=mode, root=folder, chapter_targets=targets)
