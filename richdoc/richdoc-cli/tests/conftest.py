"""Test harness shared by every test module.

Two ways to invoke the CLI:

- `cli_invoke(*argv)` — runs the click group in-process via
  `click.testing.CliRunner`. Fastest path; use this everywhere by
  default. Returns a `CliResult` that parses the JSON envelope on
  stdout (when there is one) and exposes the exit code, stdout, stderr.

- `cli_invoke_subprocess(*argv)` — spawns the actual `richdoc` shell
  launcher in a subprocess via `uv run`. Slower (per-call uv overhead),
  but exercises the full launcher path. Used for the handful of smoke
  tests that need to verify the launcher itself.

Fixtures point at the canonical inputs in `richdoc/examples/` (so we
don't duplicate them) and at the test-local `tests/fixtures/` directory
(for intentionally-broken variants and other inputs only relevant to
the test suite).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from richdoc_cli.cli import main as _cli_group

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# tests/ → richdoc-cli/ → richdoc/
_TESTS_DIR = Path(__file__).resolve().parent
_CLI_ROOT = _TESTS_DIR.parent
_RICHDOC_ROOT = _CLI_ROOT.parent
_EXAMPLES_DIR = _RICHDOC_ROOT / "examples"
_TEMPLATES_DIR = _RICHDOC_ROOT / "templates"
_ASSETS_DIR = _RICHDOC_ROOT / "richdoc-lib" / "assets"
_LAUNCHER = _CLI_ROOT / "richdoc"


# ---------------------------------------------------------------------------
# CLI invocation helpers
# ---------------------------------------------------------------------------


@dataclass
class CliResult:
    """Outcome of one CLI invocation."""

    argv: list[str]
    exit_code: int
    stdout: str
    stderr: str
    # Parsed JSON envelope from the *last* line of stdout when stdout
    # ends with valid JSON. `None` when stdout is empty / not JSON
    # (e.g. `export md -o -` which writes raw markdown).
    envelope: dict[str, Any] | None = None
    # Set when `envelope is not None` and `envelope["ok"] is True`.
    ok: bool = False

    def expect_ok(self) -> dict[str, Any]:
        """Convenience: assert success and return the envelope."""
        assert self.envelope is not None, (
            f"no JSON envelope on stdout for {self.argv}; "
            f"stdout={self.stdout!r} stderr={self.stderr!r}"
        )
        assert self.ok, (
            f"expected ok=True for {self.argv}; got envelope={self.envelope!r}"
        )
        return self.envelope

    def expect_error(self, code: str | None = None) -> dict[str, Any]:
        """Convenience: assert error envelope and return it."""
        assert self.envelope is not None, (
            f"no JSON envelope on stdout for {self.argv}; "
            f"stdout={self.stdout!r}"
        )
        assert not self.ok, (
            f"expected error envelope for {self.argv}; got {self.envelope!r}"
        )
        if code is not None:
            assert self.envelope.get("code") == code, (
                f"expected code={code!r} for {self.argv}; "
                f"got {self.envelope.get('code')!r}"
            )
        return self.envelope


def _parse_envelope(stdout: str) -> tuple[dict[str, Any] | None, bool]:
    """Pull the last JSON line out of stdout, if there is one.

    The CLI contract is "one JSON envelope per invocation, written as a
    single line on stdout." Commands that write file bytes to `-o -`
    (e.g. `export md -o -`, `export docx -o -`) don't emit an envelope
    at all, which is why this returns `(None, False)` instead of raising.
    """
    if not stdout.strip():
        return None, False
    # Look at the last non-empty line — `--version` and `--help` go
    # through click's own writer and may have multiple lines.
    for raw_line in reversed(stdout.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None, False
        if isinstance(payload, dict):
            return payload, bool(payload.get("ok"))
        return None, False
    return None, False


@pytest.fixture
def cli_invoke():
    """Run the click CLI in-process and capture its JSON envelope."""

    def _invoke(*argv: str) -> CliResult:
        # Click 8.2+ separates stdout / stderr by default; older `mix_stderr`
        # arg was removed. `standalone_mode=True` lets click's own SystemExit
        # propagate the exit code; commands themselves call json_ok / json_error
        # which exit before click sees them.
        runner = CliRunner(catch_exceptions=False)
        result = runner.invoke(
            _cli_group,
            list(argv),
            standalone_mode=True,
        )
        envelope, ok = _parse_envelope(result.stdout)
        return CliResult(
            argv=list(argv),
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr or "",
            envelope=envelope,
            ok=ok,
        )

    return _invoke


@pytest.fixture
def cli_invoke_subprocess():
    """Run the actual `richdoc` launcher in a subprocess.

    Slower than `cli_invoke`. Used for smoke tests that have to exercise
    the bash launcher / uv-run path. Most tests should prefer
    `cli_invoke`.
    """

    def _invoke(*argv: str, cwd: Path | None = None) -> CliResult:
        proc = subprocess.run(
            [str(_LAUNCHER), *argv],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
        envelope, ok = _parse_envelope(proc.stdout)
        return CliResult(
            argv=list(argv),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            envelope=envelope,
            ok=ok,
        )

    return _invoke


# ---------------------------------------------------------------------------
# Path fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    """The canonical `richdoc/examples/` directory.

    Use this for inputs we already ship as reference documents
    (`showcase.html`, `book/`, …). Modifying anything under this path
    from a test is forbidden; copy to `tmp_path` first.
    """
    assert _EXAMPLES_DIR.is_dir(), f"missing examples dir: {_EXAMPLES_DIR}"
    return _EXAMPLES_DIR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """The `tests/fixtures/` directory.

    Use this for test-only inputs (intentionally-broken HTML, edge-case
    chapter trees, …) that don't belong in the user-facing examples.
    """
    d = _TESTS_DIR / "fixtures"
    assert d.is_dir(), f"missing tests/fixtures dir: {d}"
    return d


@pytest.fixture(scope="session")
def templates_dir() -> Path:
    return _TEMPLATES_DIR


@pytest.fixture(scope="session")
def assets_dir() -> Path:
    return _ASSETS_DIR


# ---------------------------------------------------------------------------
# tmp_path helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def copy_to_tmp(tmp_path: Path):
    """Copy a source path (file or directory) under `tmp_path` and
    return the new path.

    Use this whenever a test needs to mutate an input — never modify
    `examples/` or `tests/fixtures/` in place.
    """
    import shutil

    def _copy(src: Path, *, name: str | None = None) -> Path:
        dest = tmp_path / (name or src.name)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
        return dest

    return _copy


# ---------------------------------------------------------------------------
# Snapshot extensions (configured via syrupy default)
# ---------------------------------------------------------------------------
#
# Tests use syrupy's `snapshot` fixture as-is. Per-format helpers (the
# DOCX semantic summarizer, the Confluence pretty-XML normaliser) live
# in `tests/helpers/` and are imported by individual test modules.
