"""Pipeline orchestration for `richdoc export md`.

Handles three flows:

1. **Single-file input** — render one HTML to one .md.
2. **Book in MULTI mode** — render each chapter to its own .md, mirror the
   source tree, share one assets/ dir at the root. (Today's behavior.)
3. **Book in SINGLE mode** — concatenate every chapter into one combined
   .md (see `combiner.py` for the layout).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..book import BookDiscovery, discover_chapters
from ..common.assets import AssetStore
from ..common.modes import ExportMode, OutputPlan, plan_outputs
from .combiner import combine_chapters_to_markdown
from .converter import html_to_markdown


@dataclass
class MdExportResult:
    """Outcome of one `export md` invocation."""

    plan: OutputPlan
    chapters_written: list[Path] = field(default_factory=list)
    assets_dir: Path | None = None
    assets_written: int = 0
    missing: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    is_book: bool = False


def export_md(
    entry: Path,
    *,
    output: Path | None,
    mode: ExportMode = ExportMode.MULTI,
    no_book: bool = False,
    include_remote_images: bool = False,
    force: bool = False,
) -> MdExportResult:
    """Run the markdown export. Caller is responsible for surfacing the
    result as a JSON envelope and handling `FILE_EXISTS` errors raised by
    `_write_atomic`."""
    discovery = discover_chapters(entry)
    chapters = discovery.chapters if not no_book else discovery.chapters[:1]
    is_book = discovery.is_book and not no_book

    plan = plan_outputs(
        entry=entry,
        chapters=chapters if is_book else discovery.chapters[:1],
        is_book=is_book,
        mode=mode,
        output=output,
        single_suffix=".md",
        multi_suffix="-md",
        chapter_suffix=".md",
    )

    store = AssetStore()
    result = MdExportResult(plan=plan, is_book=is_book)

    if plan.mode is ExportMode.SINGLE:
        _run_single(
            entry=entry,
            chapters=chapters if is_book else discovery.chapters[:1],
            is_book=is_book,
            plan=plan,
            store=store,
            include_remote_images=include_remote_images,
            force=force,
            result=result,
        )
    else:
        _run_multi(
            chapters=chapters,
            plan=plan,
            store=store,
            include_remote_images=include_remote_images,
            force=force,
            result=result,
        )

    return result


def render_to_string(
    entry: Path,
    *,
    no_book: bool = False,
    include_remote_images: bool = False,
) -> str:
    """Render the entry (and its book, if any) to a combined markdown string.

    Used by `-o -` (stdout) where there is no output folder to materialise
    assets into. Image references survive as the relative
    ``assets/<hash>.<ext>`` strings the caller can resolve later.
    """
    discovery = discover_chapters(entry)
    is_book = discovery.is_book and not no_book
    chapters = discovery.chapters if is_book else discovery.chapters[:1]
    store = AssetStore()
    if is_book and len(chapters) > 1:
        md_text, _ = combine_chapters_to_markdown(
            chapters=chapters,
            book_title=_book_title(entry, chapters),
            asset_store=store,
            include_remote_images=include_remote_images,
        )
    else:
        single = chapters[0]
        md_text, _ = html_to_markdown(
            single.html,
            asset_store=store,
            asset_base=single.path.parent,
            include_remote_images=include_remote_images,
            assets_subdir="assets",
        )
    return md_text


# ---------------------------------------------------------------------------
# Single-file output (one combined .md)
# ---------------------------------------------------------------------------


def _run_single(
    *,
    entry: Path,
    chapters,
    is_book: bool,
    plan: OutputPlan,
    store: AssetStore,
    include_remote_images: bool,
    force: bool,
    result: MdExportResult,
) -> None:
    out_path = plan.root
    _ensure_writable(out_path, force=force, is_dir=False)

    if is_book and len(chapters) > 1:
        # Concatenate every chapter into one combined .md.
        md_text, dropped = combine_chapters_to_markdown(
            chapters=chapters,
            book_title=_book_title(entry, chapters),
            asset_store=store,
            include_remote_images=include_remote_images,
        )
    else:
        single = chapters[0]
        md_text, dropped = html_to_markdown(
            single.html,
            asset_store=store,
            asset_base=single.path.parent,
            include_remote_images=include_remote_images,
            assets_subdir="assets",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md_text, encoding="utf-8")
    result.chapters_written.append(out_path)
    result.dropped.extend(sorted(set(dropped)))
    result.missing.extend(store.missing)
    _materialise_assets(store, out_path.parent / "assets", result)


# ---------------------------------------------------------------------------
# Multi-file output (folder of .md, mirror of source tree)
# ---------------------------------------------------------------------------


def _run_multi(
    *,
    chapters,
    plan: OutputPlan,
    store: AssetStore,
    include_remote_images: bool,
    force: bool,
    result: MdExportResult,
) -> None:
    folder = plan.root
    folder.mkdir(parents=True, exist_ok=True)
    for target in plan.chapter_targets:
        ch = target.chapter
        # Asset paths are relative to the chapter's directory in the output tree.
        depth = len(target.relative.parts) - 1
        assets_subdir = ("../" * depth + "assets") if depth else "assets"
        md_text, ch_dropped = html_to_markdown(
            ch.html,
            asset_store=store,
            asset_base=ch.path.parent,
            include_remote_images=include_remote_images,
            assets_subdir=assets_subdir,
        )
        result.dropped.extend(ch_dropped)
        out_path = target.target
        _ensure_writable(out_path, force=force, is_dir=False)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_text, encoding="utf-8")
        result.chapters_written.append(out_path)

    result.dropped = sorted(set(result.dropped))
    result.missing.extend(store.missing)
    _materialise_assets(store, folder / "assets", result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _materialise_assets(store: AssetStore, dest_dir: Path, result: MdExportResult) -> None:
    if not any(True for _ in store.items()):
        return
    mapping = store.write_to(dest_dir)
    result.assets_dir = dest_dir
    result.assets_written = len(mapping)


def _book_title(entry: Path, chapters) -> str:
    """Best-effort book title for the combined-md H1."""
    # Try the entry's rd-toc title first.
    import lxml.html as LH  # noqa: PLC0415

    try:
        root = LH.document_fromstring(entry.read_text(encoding="utf-8"))
    except OSError:
        return entry.stem
    for toc in root.iter("rd-toc"):
        t = toc.get("title")
        if t and t.strip():
            return t.strip()
    # Fall back to the first chapter's title.
    if chapters:
        return chapters[0].title or entry.stem
    return entry.stem


def _ensure_writable(path: Path, *, force: bool, is_dir: bool) -> None:
    """Raise FileExistsError if `path` exists and `force` is False."""
    if path.exists() and not force:
        kind = "directory" if is_dir else "file"
        raise FileExistsError(f"Output {kind} already exists: {path}")
