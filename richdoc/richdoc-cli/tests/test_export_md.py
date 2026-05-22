"""Snapshot tests for `richdoc export md`.

For single-file exports we snapshot the markdown output and the JSON
envelope separately. For multi-file (book) exports we snapshot the
envelope plus the rendered markdown of each chapter.

Asset materialisation is exercised by checking the `assets/` folder
contents are deterministic across runs (hash-named filenames).
"""

from __future__ import annotations

from pathlib import Path

import pytest


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


def _read_markdown_dir(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*.md")):
        out[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
    return out


def _list_assets(root: Path) -> list[str]:
    assets = root / "assets"
    if not assets.is_dir():
        return []
    return sorted(p.name for p in assets.iterdir() if p.is_file())


# ---------------------------------------------------------------------------
# Single-file inputs (non-book)
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
def test_export_md_single_file(cli_invoke, examples_dir, tmp_path, snapshot, fixture):
    out = tmp_path / "out.md"
    result = cli_invoke(
        "export",
        "md",
        "--single",
        str(examples_dir / fixture),
        "-o",
        str(out),
    )
    envelope = result.expect_ok()
    assert _normalise_paths(envelope, base=tmp_path) == snapshot(name=f"{fixture}-envelope")
    assert out.read_text(encoding="utf-8") == snapshot(name=f"{fixture}-md")


def test_export_md_to_stdout(cli_invoke, examples_dir, snapshot):
    """`-o -` writes markdown directly to stdout; no envelope."""
    result = cli_invoke(
        "export",
        "md",
        "--single",
        str(examples_dir / "showcase.html"),
        "-o",
        "-",
    )
    assert result.exit_code == 0
    assert result.envelope is None
    assert result.stdout == snapshot


# ---------------------------------------------------------------------------
# Book inputs
# ---------------------------------------------------------------------------


def test_export_md_book_multi(cli_invoke, examples_dir, tmp_path, snapshot):
    """Default mode for a book is `--multi`: one .md per chapter."""
    out_dir = tmp_path / "book-md"
    result = cli_invoke(
        "export",
        "md",
        str(examples_dir / "book" / "index.html"),
        "-o",
        str(out_dir),
    )
    envelope = result.expect_ok()
    assert _normalise_paths(envelope, base=tmp_path) == snapshot(name="envelope")
    assert _read_markdown_dir(out_dir) == snapshot(name="chapters")
    assert _list_assets(out_dir) == snapshot(name="assets")


def test_export_md_book_single(cli_invoke, examples_dir, tmp_path, snapshot):
    """`--single` concatenates the whole book into one .md."""
    out = tmp_path / "book.md"
    result = cli_invoke(
        "export",
        "md",
        "--single",
        str(examples_dir / "book" / "index.html"),
        "-o",
        str(out),
    )
    envelope = result.expect_ok()
    assert _normalise_paths(envelope, base=tmp_path) == snapshot(name="envelope")
    assert out.read_text(encoding="utf-8") == snapshot(name="combined")


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_export_md_refuses_to_overwrite(cli_invoke, examples_dir, tmp_path):
    out = tmp_path / "existing.md"
    out.write_text("already here", encoding="utf-8")
    result = cli_invoke(
        "export",
        "md",
        "--single",
        str(examples_dir / "showcase.html"),
        "-o",
        str(out),
    )
    result.expect_error("FILE_EXISTS")


def test_export_md_force_overwrites(cli_invoke, examples_dir, tmp_path):
    out = tmp_path / "existing.md"
    out.write_text("stale", encoding="utf-8")
    result = cli_invoke(
        "export",
        "md",
        "--single",
        "-f",
        str(examples_dir / "showcase.html"),
        "-o",
        str(out),
    )
    result.expect_ok()
    assert out.read_text(encoding="utf-8") != "stale"


def test_export_md_non_html_input_is_invalid_params(cli_invoke, tmp_path):
    bad = tmp_path / "not-html.txt"
    bad.write_text("plain text", encoding="utf-8")
    result = cli_invoke(
        "export",
        "md",
        str(bad),
    )
    result.expect_error("INVALID_PARAMS")


def test_export_md_multi_stdout_rejected(cli_invoke, examples_dir):
    result = cli_invoke(
        "export",
        "md",
        "--multi",
        str(examples_dir / "showcase.html"),
        "-o",
        "-",
    )
    result.expect_error("INVALID_PARAMS")
