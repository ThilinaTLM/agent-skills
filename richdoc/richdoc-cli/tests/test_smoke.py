"""Smoke subset \u2014 the minimum that confirms every entry point still works.

Tagged with ``smoke`` so it can be run alone via ``pytest -m smoke`` in
pre-commit. Snapshot tests live in the dedicated per-command modules.
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_version(cli_invoke):
    """`richdoc --version` exits 0 and prints a version line."""
    result = cli_invoke("--version")
    assert result.exit_code == 0
    assert "richdoc, version" in result.stdout


@pytest.mark.smoke
def test_help(cli_invoke):
    """`richdoc --help` lists every top-level subcommand."""
    result = cli_invoke("--help")
    assert result.exit_code == 0
    out = result.stdout
    for cmd in ("new", "init", "update", "lint", "components", "export", "publish"):
        assert cmd in out, f"missing {cmd!r} in help output"


@pytest.mark.smoke
def test_lint_showcase_is_clean(cli_invoke, examples_dir):
    """The canonical showcase document must always lint clean.

    This is a contract test: if `build.ts`'s sanity check passes, this
    must too. Catches accidental schema or rule regressions.
    """
    result = cli_invoke("lint", str(examples_dir / "showcase.html"))
    envelope = result.expect_ok()
    assert envelope["errors"] == 0
    assert envelope["warnings"] == 0


@pytest.mark.smoke
def test_lint_book_is_clean(cli_invoke, examples_dir):
    """The reference book lints clean as a directory."""
    result = cli_invoke("lint", str(examples_dir / "book"))
    envelope = result.expect_ok()
    assert envelope["errors"] == 0
