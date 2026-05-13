"""Resolve framework asset and template locations relative to this package.

Layout:
    <FRAMEWORK_ROOT>/
        assets/
            richdoc.css
            richdoc.js
            schema.json
        templates/
            *.html
        richdoc-cli/
            src/
                richdoc_cli/
                    paths.py   <-- this file
"""

from __future__ import annotations

from pathlib import Path

# .../richdoc-cli/src/richdoc_cli/
CLI_PACKAGE_DIR: Path = Path(__file__).resolve().parent

# .../richdoc-cli/
CLI_ROOT: Path = CLI_PACKAGE_DIR.parent.parent

# .../richdoc/
FRAMEWORK_ROOT: Path = CLI_ROOT.parent

ASSETS_DIR: Path = FRAMEWORK_ROOT / "assets"
TEMPLATES_DIR: Path = FRAMEWORK_ROOT / "templates"
SCHEMA_PATH: Path = ASSETS_DIR / "schema.json"
