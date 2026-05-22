"""Snapshot tests for `richdoc publish confluence push --dry-run`.

All tests run with `--dry-run --no-render-diagrams --no-render-math` so
no network call ever fires. The dry-run path requires the four
CONFLUENCE_* env vars to be set; we fake them in `monkeypatch`.

The dry-run output includes the storage XML body for each page, which
we pretty-print via ``tests.helpers.xml_pretty`` before snapshotting so
diffs surface as structural changes rather than reformatting noise.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.helpers.xml_pretty import pretty_storage_xml

# Decision lists emit `<ac:adf-attribute key="local-id">…uuid…</ac:adf-attribute>`
# with a fresh UUID per call. Snapshot stability requires substituting them.
_LOCAL_ID_RE = re.compile(
    r'(<ac:adf-attribute key="local-id">)([0-9a-f]{32})(</ac:adf-attribute>)'
)


def _stabilise_local_ids(xml: str) -> str:
    """Replace runtime UUIDs with deterministic ``LOCAL-ID-N`` tokens."""
    seen: dict[str, str] = {}

    def sub(match: re.Match[str]) -> str:
        uid = match.group(2)
        token = seen.setdefault(uid, f"LOCAL-ID-{len(seen) + 1}")
        return f"{match.group(1)}{token}{match.group(3)}"

    return _LOCAL_ID_RE.sub(sub, xml)


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


def _prettify_bodies(envelope: dict) -> dict:
    """Replace each dry-run body preview with a normalised, pretty-printed form."""
    bodies = envelope.get("bodies")
    if not isinstance(bodies, list):
        return envelope
    for body in bodies:
        if isinstance(body, dict) and "body_preview" in body:
            xml = body["body_preview"]
            xml = _stabilise_local_ids(xml)
            body["body_preview"] = pretty_storage_xml(xml)
    return envelope


@pytest.fixture
def confluence_env(monkeypatch):
    """Fake env vars + stub the network-touching client methods.

    The dry-run flow still needs to resolve the space id and look up
    existing pages by title; both calls hit Confluence. Patching the
    methods on the client class lets the converter pipeline run end
    to end without any HTTP.
    """
    monkeypatch.setenv("CONFLUENCE_SITE", "https://example.atlassian.net")
    monkeypatch.setenv("CONFLUENCE_EMAIL", "agent@example.com")
    monkeypatch.setenv("CONFLUENCE_TOKEN", "fake-token")
    monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "TEST")

    from richdoc_cli.publish.confluence.client import ConfluenceClient, Space

    monkeypatch.setattr(
        ConfluenceClient,
        "get_space_by_key",
        lambda self, key: Space(
            id="sp-1",
            key=key,
            name="Test Space",
            type="global",
            homepage_id=None,
            webui=f"/spaces/{key}",
        ),
    )
    # No existing pages — every chapter is `(planned)`.
    monkeypatch.setattr(
        ConfluenceClient,
        "find_page_by_title",
        lambda self, *, space_id, title, parent_id=None: None,
    )
    monkeypatch.setattr(
        ConfluenceClient,
        "get_page",
        lambda self, page_id: None,
    )


# ---------------------------------------------------------------------------
# Single-file dry-run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    [
        "showcase.html",
        "data-design.html",
        "status-onepager.html",
    ],
)
def test_publish_dry_run_single(
    cli_invoke,
    confluence_env,
    examples_dir,
    snapshot,
    fixture,
):
    """The publish dry-run path is fully offline; we just exercise the converter."""
    result = cli_invoke(
        "publish",
        "confluence",
        "push",
        "--dry-run",
        "--no-render-diagrams",
        "--no-render-math",
        "--no-lint",
        str(examples_dir / fixture),
    )
    envelope = result.expect_ok()
    normalised = _normalise_paths(envelope, base=examples_dir)
    prettified = _prettify_bodies(normalised)
    assert prettified == snapshot(name=fixture)


# ---------------------------------------------------------------------------
# Book dry-run
# ---------------------------------------------------------------------------


def test_publish_dry_run_book(
    cli_invoke,
    confluence_env,
    examples_dir,
    snapshot,
):
    result = cli_invoke(
        "publish",
        "confluence",
        "push",
        "--dry-run",
        "--no-render-diagrams",
        "--no-render-math",
        "--no-lint",
        str(examples_dir / "book"),
    )
    envelope = result.expect_ok()
    normalised = _normalise_paths(envelope, base=examples_dir)
    prettified = _prettify_bodies(normalised)
    assert prettified == snapshot


# ---------------------------------------------------------------------------
# Env-var resolution
# ---------------------------------------------------------------------------


def test_publish_missing_env_returns_config_missing(cli_invoke, monkeypatch, examples_dir):
    """All four vars missing \u2192 CONFIG_MISSING with a `missing[]` list."""
    for var in (
        "CONFLUENCE_SITE",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_TOKEN",
        "CONFLUENCE_SPACE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    result = cli_invoke(
        "publish",
        "confluence",
        "push",
        "--dry-run",
        "--no-lint",
        str(examples_dir / "showcase.html"),
    )
    envelope = result.expect_error("CONFIG_MISSING")
    assert "missing" in envelope
    assert set(envelope["missing"]) == {
        "CONFLUENCE_SITE",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_TOKEN",
        "CONFLUENCE_SPACE_KEY",
    }


def test_publish_dirty_doc_fails_lint(
    cli_invoke,
    confluence_env,
    fixtures_dir,
):
    """Pre-publish lint blocks pushing a doc with errors."""
    result = cli_invoke(
        "publish",
        "confluence",
        "push",
        "--dry-run",
        "--no-render-diagrams",
        "--no-render-math",
        str(fixtures_dir / "broken" / "unknown-tag.html"),
    )
    result.expect_error("LINT_ERRORS")
