"""Snapshot tests for `richdoc export docx`.

DOCX output is not byte-stable across python-docx versions, so we never
snapshot the raw .docx file. Instead we snapshot:

  1. The JSON envelope (counts of paragraphs, images, dropped tags, etc).
  2. The semantic summary produced by ``tests.helpers.docx_summary`` \u2014
     heading levels, paragraph styles, run text, table shapes, image
     counts.

Network calls (Kroki diagram rendering) are disabled with
``--no-render-diagrams`` so the suite stays offline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.docx_summary import summarise_path


def _normalise_paths(payload: dict, *, base: Path) -> dict:
    def fix(value: object) -> object:
        if isinstance(value, str):
            try:
                p = Path(value)
            except ValueError:
                return value
            if p.is_absolute():
                try:
                    return p.relative_to(base).as_posix()
                except ValueError:
                    return p.name
            return value
        if isinstance(value, dict):
            return {k: fix(v) for k, v in value.items()}
        if isinstance(value, list):
            return [fix(v) for v in value]
        return value

    return fix(payload)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Single-file inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    [
        "showcase.html",
        "data-design.html",
        "diagram.html",
        "status-onepager.html",
    ],
)
def test_export_docx_single_file(cli_invoke, examples_dir, tmp_path, snapshot, fixture):
    out = tmp_path / "out.docx"
    result = cli_invoke(
        "export",
        "docx",
        "--no-render-diagrams",
        str(examples_dir / fixture),
        "-o",
        str(out),
    )
    envelope = result.expect_ok()
    # bytes_total fluctuates by python-docx version; drop it from the
    # snapshot.
    envelope.pop("bytes", None)
    assert _normalise_paths(envelope, base=tmp_path) == snapshot(name=f"{fixture}-envelope")
    assert summarise_path(out) == snapshot(name=f"{fixture}-summary")


# ---------------------------------------------------------------------------
# Book inputs
# ---------------------------------------------------------------------------


def test_export_docx_book_single(cli_invoke, examples_dir, tmp_path, snapshot):
    """Default mode for a book docx is SINGLE \u2014 one .docx with page breaks."""
    out = tmp_path / "book.docx"
    result = cli_invoke(
        "export",
        "docx",
        "--no-render-diagrams",
        str(examples_dir / "book" / "index.html"),
        "-o",
        str(out),
    )
    envelope = result.expect_ok()
    envelope.pop("bytes", None)
    assert _normalise_paths(envelope, base=tmp_path) == snapshot(name="envelope")
    assert summarise_path(out) == snapshot(name="summary")


def test_export_docx_book_multi(cli_invoke, examples_dir, tmp_path, snapshot):
    """`--multi` produces one .docx per chapter."""
    out_dir = tmp_path / "book-docx"
    result = cli_invoke(
        "export",
        "docx",
        "--multi",
        "--no-render-diagrams",
        str(examples_dir / "book" / "index.html"),
        "-o",
        str(out_dir),
    )
    envelope = result.expect_ok()
    envelope.pop("bytes", None)
    envelope.pop("per_chapter_bytes", None)
    assert _normalise_paths(envelope, base=tmp_path) == snapshot(name="envelope")

    summaries = {
        p.relative_to(out_dir).as_posix(): summarise_path(p)
        for p in sorted(out_dir.rglob("*.docx"))
    }
    assert summaries == snapshot(name="summaries")


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_export_docx_refuses_to_overwrite(cli_invoke, examples_dir, tmp_path):
    out = tmp_path / "existing.docx"
    out.write_bytes(b"PK\x03\x04 fake zip")
    result = cli_invoke(
        "export",
        "docx",
        "--no-render-diagrams",
        str(examples_dir / "showcase.html"),
        "-o",
        str(out),
    )
    result.expect_error("FILE_EXISTS")


def test_export_docx_non_html_input_is_invalid_params(cli_invoke, tmp_path):
    bad = tmp_path / "not-html.txt"
    bad.write_text("plain text", encoding="utf-8")
    result = cli_invoke(
        "export",
        "docx",
        str(bad),
    )
    result.expect_error("INVALID_PARAMS")
