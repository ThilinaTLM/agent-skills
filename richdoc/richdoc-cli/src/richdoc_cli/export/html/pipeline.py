"""Pipeline orchestration for `richdoc export html`.

Two flows:

1. **SINGLE** (default) — inline the entry file's relative dependencies
   into one self-contained `.bundle.html`. (Today's behavior.)
2. **MULTI** — for a book, bundle each chapter into its own
   `.bundle.html` mirroring the source tree. Intra-book hrefs stay
   relative and resolve naturally against the mirrored layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..book import discover_chapters
from ..common.modes import ExportMode, OutputPlan, plan_outputs
from .bundler import BundleResult, bundle


@dataclass
class HtmlExportResult:
    """Outcome of one `export html` invocation."""

    plan: OutputPlan
    files_written: list[Path] = field(default_factory=list)
    inlined: dict[str, int] = field(default_factory=lambda: {"css": 0, "js": 0, "images": 0, "other": 0})
    kept_absolute: int = 0
    missing: list[str] = field(default_factory=list)
    is_book: bool = False


def export_html(
    entry: Path,
    *,
    output: Path | None,
    mode: ExportMode = ExportMode.SINGLE,
    no_book: bool = False,
    force: bool = False,
) -> HtmlExportResult:
    discovery = discover_chapters(entry)
    is_book = discovery.is_book and not no_book

    plan = plan_outputs(
        entry=entry,
        chapters=discovery.chapters if is_book else discovery.chapters[:1],
        is_book=is_book,
        mode=mode,
        output=output,
        single_suffix=".bundle.html",
        multi_suffix="-html",
        chapter_suffix=".bundle.html",
    )

    result = HtmlExportResult(plan=plan, is_book=is_book)

    if plan.mode is ExportMode.SINGLE:
        _bundle_one(
            source_path=entry,
            target=plan.root,
            force=force,
            result=result,
        )
    else:
        plan.root.mkdir(parents=True, exist_ok=True)
        for ct in plan.chapter_targets:
            _bundle_one(
                source_path=ct.chapter.path,
                target=ct.target,
                force=force,
                result=result,
                source_text=ct.chapter.html,
            )

    return result


def bundle_to_string(entry: Path) -> str:
    """Bundle one file and return the HTML string (for `-o -` stdout mode)."""
    source = entry.read_text(encoding="utf-8")
    return bundle(source, base_dir=entry.parent).html


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _bundle_one(
    *,
    source_path: Path,
    target: Path,
    force: bool,
    result: HtmlExportResult,
    source_text: str | None = None,
) -> None:
    if target.exists() and not force:
        raise FileExistsError(f"Output file already exists: {target}")
    source = source_text if source_text is not None else source_path.read_text(encoding="utf-8")
    bundle_result = bundle(source, base_dir=source_path.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(bundle_result.html, encoding="utf-8")

    result.files_written.append(target)
    _merge_bundle_stats(result, bundle_result)


def _merge_bundle_stats(result: HtmlExportResult, br: BundleResult) -> None:
    for k, v in br.inlined.items():
        result.inlined[k] = result.inlined.get(k, 0) + v
    result.kept_absolute += br.kept_absolute
    # De-dupe missing across chapters.
    for m in br.missing:
        if m not in result.missing:
            result.missing.append(m)
