"""Snapshot tests for `richdoc lint`.

Strategy:

- For each fixture, snapshot the *full* JSON envelope. The snapshot is
  the contract \u2014 anything that changes the envelope structure or any
  rule's output text gets caught on the next test run.
- File paths are normalised to a stable form (just the basename) so
  snapshots are portable across checkouts.
- The autofix round-trip test snapshots both the envelope **and** the
  rewritten HTML so changes to the source rewriter surface visibly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_paths(payload: dict, *, base: Path) -> dict:
    """Replace absolute paths in the envelope with paths relative to `base`.

    Lint envelopes embed:
      - top-level ``file`` (single-file mode) or ``path`` + ``files[].file``
        (directory mode) as absolute paths
      - ``input`` may also appear
    """

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
# Clean lint snapshots \u2014 every reference fixture lints clean
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
def test_lint_single_file_examples(cli_invoke, examples_dir, snapshot, fixture):
    result = cli_invoke("lint", str(examples_dir / fixture))
    envelope = result.expect_ok()
    assert envelope == snapshot(name=fixture)


def test_lint_book_directory(cli_invoke, examples_dir, snapshot):
    """Linting the whole `book/` aggregates per-file envelopes."""
    result = cli_invoke("lint", str(examples_dir / "book"))
    envelope = result.expect_ok()
    normalised = _normalise_paths(envelope, base=examples_dir / "book")
    assert normalised == snapshot


def test_lint_book_index(cli_invoke, examples_dir, snapshot):
    """Linting just the book entry chapter."""
    result = cli_invoke("lint", str(examples_dir / "book" / "index.html"))
    envelope = result.expect_ok()
    normalised = _normalise_paths(envelope, base=examples_dir / "book")
    assert normalised == snapshot


# ---------------------------------------------------------------------------
# Broken-fixture snapshots \u2014 each rule's error output is locked in
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    [
        "missing-css.html",
        "missing-rd-page.html",
        "unknown-tag.html",
        "removed-tag.html",
        "self-closing.html",
        "invalid-attr-value.html",
    ],
)
def test_lint_broken_fixtures(cli_invoke, fixtures_dir, snapshot, fixture):
    """Each broken fixture exercises a specific lint rule."""
    path = fixtures_dir / "broken" / fixture
    result = cli_invoke("lint", str(path))
    envelope = result.expect_error("LINT_ERRORS")
    normalised = _normalise_paths(envelope, base=fixtures_dir / "broken")
    assert normalised == snapshot(name=fixture)


# ---------------------------------------------------------------------------
# Book-mode drift detection
# ---------------------------------------------------------------------------


def test_lint_book_drift(cli_invoke, fixtures_dir, snapshot):
    """`book-toc-drift` fires when one chapter's TOC diverges."""
    result = cli_invoke("lint", str(fixtures_dir / "book-drift"))
    envelope = result.expect_error("LINT_ERRORS")
    normalised = _normalise_paths(envelope, base=fixtures_dir / "book-drift")
    assert normalised == snapshot


# ---------------------------------------------------------------------------
# --fix round-trip
# ---------------------------------------------------------------------------


def test_lint_fix_hero_nav_round_trip(cli_invoke, fixtures_dir, copy_to_tmp, snapshot):
    """`lint --fix` removes redundant hero nav links and rewrites the file."""
    src = fixtures_dir / "hero-nav-fixable"
    work = copy_to_tmp(src, name="hero-nav-fixable")

    # First pass: emit errors.
    result = cli_invoke("lint", str(work))
    envelope = result.expect_error("LINT_ERRORS")
    normalised = _normalise_paths(envelope, base=work)
    assert normalised == snapshot(name="before-fix")

    # Apply autofix.
    fixed = cli_invoke("lint", "--fix", str(work))
    fixed_env = fixed.expect_ok()
    fixed_normalised = _normalise_paths(fixed_env, base=work)
    assert fixed_normalised == snapshot(name="after-fix")

    # Idempotent: re-running the fix produces no further changes.
    again = cli_invoke("lint", "--fix", str(work))
    again_env = again.expect_ok()
    again_normalised = _normalise_paths(again_env, base=work)
    assert again_normalised == snapshot(name="idempotent")

    # Snapshot the rewritten HTML bodies so future changes to the
    # source rewriter surface in the diff.
    rewritten = {}
    for p in sorted(work.glob("*.html")):
        rewritten[p.name] = p.read_text(encoding="utf-8")
    assert rewritten == snapshot(name="rewritten-html")


# ---------------------------------------------------------------------------
# Error path \u2014 not an HTML file
# ---------------------------------------------------------------------------


def test_lint_non_html_input_is_input_error(cli_invoke, tmp_path):
    bad = tmp_path / "not-html.txt"
    bad.write_text("nope")
    result = cli_invoke("lint", str(bad))
    result.expect_error("INPUT_ERROR")
