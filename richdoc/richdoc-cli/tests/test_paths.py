"""Unit tests for `paths.py`.

These constants are the single source of truth for where the CLI
looks up framework assets / templates / the schema. Tests assert
they resolve to real files relative to the package layout.
"""

from __future__ import annotations

from richdoc_cli import paths


def test_paths_point_at_existing_directories():
    assert paths.CLI_PACKAGE_DIR.is_dir()
    assert paths.CLI_ROOT.is_dir()
    assert paths.FRAMEWORK_ROOT.is_dir()
    assert paths.LIB_ROOT.is_dir()
    assert paths.ASSETS_DIR.is_dir()
    assert paths.TEMPLATES_DIR.is_dir()


def test_schema_path_points_at_real_file():
    assert paths.SCHEMA_PATH.is_file()


def test_assets_dir_contains_richdoc_assets():
    files = {p.name for p in paths.ASSETS_DIR.iterdir() if p.is_file()}
    assert "richdoc.css" in files
    assert "richdoc.js" in files
    assert "schema.json" in files


def test_templates_dir_contains_named_templates():
    files = {p.stem for p in paths.TEMPLATES_DIR.iterdir() if p.suffix == ".html"}
    # The named templates are surfaced via `richdoc new --template <name>`
    # and listed by `commands.new_.DEFAULT_TEMPLATE`. The set may grow over
    # time; this test pins the current floor.
    expected = {"plan", "adr", "research", "runbook", "onepager", "comparison"}
    missing = expected - files
    assert not missing, f"missing templates: {sorted(missing)}"
