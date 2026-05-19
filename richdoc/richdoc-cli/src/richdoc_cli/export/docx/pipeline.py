"""Pipeline orchestration for `richdoc export docx`.

Two flows:

1. **SINGLE** (default) — render the entry file, or concatenate every
   chapter into one DOCX with page breaks.
2. **MULTI** — render each chapter into its own .docx, mirror the source
   tree on disk. Assets are embedded per-file (each chapter is fully
   self-contained for Confluence import).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..book import discover_chapters
from ..common.modes import ExportMode, OutputPlan, plan_outputs
from . import chapters_to_docx, html_to_docx
from .state import DocxResult


@dataclass
class DocxExportResult:
    """Outcome of one `export docx` invocation."""

    plan: OutputPlan
    files_written: list[Path] = field(default_factory=list)
    bytes_total: int = 0
    images_embedded: int = 0
    diagrams_rendered: int = 0
    diagrams_failed: int = 0
    missing: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    is_book: bool = False
    # When --multi is requested, surface per-chapter sizes separately so the
    # caller can report them. Empty for SINGLE.
    per_chapter_bytes: list[int] = field(default_factory=list)


def export_docx(
    entry: Path,
    *,
    output: Path | None,
    mode: ExportMode = ExportMode.SINGLE,
    no_book: bool = False,
    render_diagrams: bool = True,
    diagram_endpoint: str = "https://kroki.io",
    force: bool = False,
) -> DocxExportResult:
    discovery = discover_chapters(entry)
    is_book = discovery.is_book and not no_book

    plan = plan_outputs(
        entry=entry,
        chapters=discovery.chapters if is_book else discovery.chapters[:1],
        is_book=is_book,
        mode=mode,
        output=output,
        single_suffix=".docx",
        multi_suffix="-docx",
        chapter_suffix=".docx",
    )

    result = DocxExportResult(plan=plan, is_book=is_book)

    if plan.mode is ExportMode.SINGLE:
        _run_single(
            entry=entry,
            chapters=discovery.chapters,
            is_book=is_book,
            plan=plan,
            render_diagrams=render_diagrams,
            diagram_endpoint=diagram_endpoint,
            force=force,
            result=result,
        )
    else:
        _run_multi(
            chapters=discovery.chapters,
            plan=plan,
            render_diagrams=render_diagrams,
            diagram_endpoint=diagram_endpoint,
            force=force,
            result=result,
        )

    return result


def render_to_bytes(
    entry: Path,
    *,
    no_book: bool = False,
    render_diagrams: bool = True,
    diagram_endpoint: str = "https://kroki.io",
) -> DocxResult:
    """Render to bytes without writing to disk (for `-o -` stdout mode).

    SINGLE-mode semantics: a book becomes one concatenated DOCX.
    """
    discovery = discover_chapters(entry)
    if discovery.is_book and not no_book:
        return chapters_to_docx(
            discovery.chapters,
            book_base=entry.parent,
            render_diagrams=render_diagrams,
            diagram_endpoint=diagram_endpoint,
        )
    source = entry.read_text(encoding="utf-8")
    return html_to_docx(
        source,
        base_dir=entry.parent,
        render_diagrams=render_diagrams,
        diagram_endpoint=diagram_endpoint,
    )


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _run_single(
    *,
    entry: Path,
    chapters,
    is_book: bool,
    plan: OutputPlan,
    render_diagrams: bool,
    diagram_endpoint: str,
    force: bool,
    result: DocxExportResult,
) -> None:
    out_path = plan.root
    if out_path.exists() and not force:
        raise FileExistsError(f"Output file already exists: {out_path}")

    if is_book and len(chapters) > 1:
        docx = chapters_to_docx(
            chapters,
            book_base=entry.parent,
            render_diagrams=render_diagrams,
            diagram_endpoint=diagram_endpoint,
        )
    else:
        source = entry.read_text(encoding="utf-8")
        docx = html_to_docx(
            source,
            base_dir=entry.parent,
            render_diagrams=render_diagrams,
            diagram_endpoint=diagram_endpoint,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(docx.data)
    _record(result, out_path, docx)


def _run_multi(
    *,
    chapters,
    plan: OutputPlan,
    render_diagrams: bool,
    diagram_endpoint: str,
    force: bool,
    result: DocxExportResult,
) -> None:
    plan.root.mkdir(parents=True, exist_ok=True)
    for ct in plan.chapter_targets:
        target = ct.target
        if target.exists() and not force:
            raise FileExistsError(f"Output file already exists: {target}")
        ch = ct.chapter
        docx = html_to_docx(
            ch.html,
            base_dir=ch.path.parent,
            render_diagrams=render_diagrams,
            diagram_endpoint=diagram_endpoint,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(docx.data)
        _record(result, target, docx, track_per_chapter=True)


def _record(
    result: DocxExportResult,
    target: Path,
    docx: DocxResult,
    *,
    track_per_chapter: bool = False,
) -> None:
    result.files_written.append(target)
    result.bytes_total += len(docx.data)
    result.images_embedded += docx.images_embedded
    result.diagrams_rendered += docx.diagrams_rendered
    result.diagrams_failed += docx.diagrams_failed
    for m in docx.missing:
        if m not in result.missing:
            result.missing.append(m)
    for d in docx.dropped:
        if d not in result.dropped:
            result.dropped.append(d)
    if track_per_chapter:
        result.per_chapter_bytes.append(len(docx.data))
    result.dropped = sorted(set(result.dropped))
