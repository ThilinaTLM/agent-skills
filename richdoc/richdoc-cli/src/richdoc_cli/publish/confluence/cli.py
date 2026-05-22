"""Click subcommands for `richdoc confluence …`.

Lives next to the rest of the Confluence integration so changes to the
publisher don't have to round-trip through the generic command modules.
The top-level CLI mounts `confluence_group` directly.

Subcommands:

    richdoc confluence spaces      [--query …]
    richdoc confluence pages       [--query …] [--parent-id …]
    richdoc confluence page-by-id  PAGE_ID
    richdoc confluence publish     INPUT [--parent-id …]

Credentials come from four environment variables: `CONFLUENCE_SITE`,
`CONFLUENCE_EMAIL`, `CONFLUENCE_TOKEN`, and `CONFLUENCE_SPACE_KEY`
(`SPACE_KEY` is required for `pages` and `publish` only). Missing vars
exit with `code: CONFIG_MISSING` so the calling agent can prompt the
user to export them.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from ...commands._safe import safe_command
from ...lint.runner import lint_path
from ...output import json_error, json_ok
from . import (
    Config,
    ConfigError,
    ConfluenceClient,
    PublishPlan,
    resolve_config,
)
from . import (
    publish as run_publish,
)
from .config import AUTH_VARS, PUBLISH_VARS

# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


@click.group(
    "confluence",
    help="Work with Confluence Cloud spaces/pages and publish richdocs via REST.",
)
def confluence_group() -> None:
    pass


# ---------------------------------------------------------------------------
# Shared env-var config + error trapping
# ---------------------------------------------------------------------------


def _load_config(required: tuple[str, ...]) -> Config:
    """Resolve required CONFLUENCE_* env vars or emit a JSON error.

    Missing vars → `code: CONFIG_MISSING` with a `missing[]` list so the
    agent can ask the user to export them. Present-but-malformed values
    (e.g. bad site URL) → `code: AUTH_ERROR`.
    """
    try:
        config, missing = resolve_config(required)
    except ConfigError as exc:
        json_error(str(exc), code="AUTH_ERROR")
    if missing is not None:
        names = ", ".join(missing)
        json_error(
            f"Missing required environment variables: {names}.",
            code="CONFIG_MISSING",
            hint=(
                "Ask the user to export these environment variables and "
                "rerun. See references/publish.md for setup."
            ),
            missing=missing,
        )
    assert config is not None  # narrow for type checkers
    return config


def _make_client(config: Config) -> ConfluenceClient:
    return ConfluenceClient(
        site=config.site, email=config.email, token=config.token,
    )


# ---------------------------------------------------------------------------
# spaces
# ---------------------------------------------------------------------------


@confluence_group.command("spaces")
@click.option(
    "-q", "--query", "query", type=str, default=None,
    help="Filter spaces by key/name substring (case-insensitive).",
)
@click.option(
    "--limit", type=int, default=50, show_default=True,
    help="Maximum number of spaces to return.",
)
@safe_command
def cmd_spaces(query: str | None, limit: int) -> None:
    """List Confluence spaces visible to the token."""
    config = _load_config(AUTH_VARS)
    client = _make_client(config)
    spaces = client.list_spaces(query=query, limit=limit)
    out = [
        {
            "id": sp.id,
            "key": sp.key,
            "name": sp.name,
            "type": sp.type,
            "homepageId": sp.homepage_id,
            "url": f"{client.site}/wiki{sp.webui}" if sp.webui else "",
        }
        for sp in spaces
    ]
    json_ok(site=client.site, spaces=out)


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------


@confluence_group.command("pages")
@click.option(
    "-q", "--query", "query", type=str, default=None,
    help="Filter pages by title substring (case-insensitive).",
)
@click.option(
    "--parent-id", "parent_id", type=str, default=None,
    help="Restrict to direct children of this page id.",
)
@click.option(
    "--limit", type=int, default=50, show_default=True,
    help="Maximum number of pages to return.",
)
@safe_command
def cmd_pages(
    query: str | None, parent_id: str | None, limit: int,
) -> None:
    """List pages in the configured Confluence space ($CONFLUENCE_SPACE_KEY)."""
    config = _load_config(PUBLISH_VARS)
    client = _make_client(config)
    assert config.space_key is not None  # guaranteed by PUBLISH_VARS
    space = client.get_space_by_key(config.space_key)
    pages = client.list_pages(
        space_id=space.id, query=query, parent_id=parent_id, limit=limit,
    )
    out = [
        {
            "id": p.id,
            "title": p.title,
            "parentId": p.parent_id,
            "spaceId": p.space_id,
            "version": p.version,
            "url": client.page_url(p, space.key),
        }
        for p in pages
    ]
    json_ok(
        site=client.site,
        space={"id": space.id, "key": space.key, "name": space.name},
        pages=out,
    )


# ---------------------------------------------------------------------------
# page-by-id
# ---------------------------------------------------------------------------


@confluence_group.command("page-by-id")
@click.argument("page_id", metavar="PAGE_ID")
@safe_command
def cmd_page_by_id(page_id: str) -> None:
    """Resolve a Confluence page id to {id, title, parentId, spaceId, url}."""
    config = _load_config(AUTH_VARS)
    client = _make_client(config)
    page = client.get_page(page_id)
    # Best-effort: derive the public URL even without the space key by
    # using the webui link the API returned.
    public = (
        f"{client.site}/wiki{page.webui}"
        if page.webui
        else f"{client.site}/wiki/pages/{page.id}"
    )
    json_ok(
        page={
            "id": page.id,
            "title": page.title,
            "parentId": page.parent_id,
            "spaceId": page.space_id,
            "version": page.version,
            "url": public,
        }
    )


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


@confluence_group.command("publish")
@click.argument(
    "input_",
    metavar="INPUT",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--parent-id", "parent_id", type=str, default=None,
    help="Parent page id. Pages land under it. Default: space root.",
)
@click.option(
    "--parent-title", "parent_title", type=str, default=None,
    help="Resolve a parent page by exact title (must be unique in the space).",
)
@click.option(
    "--page-id", "page_id_override", type=str, default=None,
    help="Force update of this specific page id (skips title lookup).",
)
@click.option(
    "--title", "title_override", type=str, default=None,
    help="Page title for the single-file case. Ignored in book mode.",
)
@click.option(
    "--title-prefix", "title_prefix", type=str, default="",
    help="Prepended to every page title (e.g. '[richdoc] ').",
)
@click.option(
    "--no-book", "no_book", is_flag=True,
    help="Disable book auto-detection — publish only the entry file.",
)
@click.option(
    "--dry-run", "dry_run", is_flag=True,
    help="Walk every chapter and report what would happen without "
    "calling create/update/upload endpoints.",
)
@click.option(
    "--no-render-diagrams", is_flag=True,
    help="Skip Kroki rendering of rd-diagram; embed source as a code "
    "macro instead.",
)
@click.option(
    "--no-render-math", is_flag=True,
    help="Skip Kroki rendering of rd-math; emit italic source instead.",
)
@click.option(
    "--diagram-endpoint", default="https://kroki.io", show_default=True,
    help="Kroki-compatible server for diagrams and math.",
)
@click.option(
    "--include-remote-images", is_flag=True,
    help="Fetch http(s) <img> sources and upload them as attachments. "
    "Default: link to remote URLs as-is.",
)
@click.option(
    "--comment", "update_comment", type=str,
    default="Updated via richdoc CLI", show_default=True,
    help="Version comment recorded on each updated page.",
)
@click.option(
    "--no-lint", "no_lint", is_flag=True,
    help="Skip the pre-publish `richdoc lint` pass. Use only when "
    "intentionally debugging a publish; otherwise lint must pass before "
    "any page is published.",
)
@safe_command
def cmd_publish(
    input_: Path,
    parent_id: str | None,
    parent_title: str | None,
    page_id_override: str | None,
    title_override: str | None,
    title_prefix: str,
    no_book: bool,
    dry_run: bool,
    no_render_diagrams: bool,
    no_render_math: bool,
    diagram_endpoint: str,
    include_remote_images: bool,
    update_comment: str,
    no_lint: bool,
) -> None:
    """Publish a richdoc HTML document (single file or whole book) to Confluence.

    INPUT may be a `.html` file or a directory. For a directory, the
    entry chapter resolves to `<dir>/index.html`; missing `index.html`
    is a fail-fast error — there is no syntactic difference between a
    book entry and any other chapter, so we don't guess.

    By default `publish` runs `richdoc lint` against INPUT before any
    network call and refuses to publish if there are any errors. Pass
    `--no-lint` to skip the preflight.
    """
    in_path = input_.resolve()

    # Resolve the entry file from a directory input, or validate a
    # direct file input.
    lint_target: Path
    entry_path: Path
    if in_path.is_dir():
        candidate = in_path / "index.html"
        if not candidate.exists():
            json_error(
                f"No index.html in '{in_path}'. Pass the entry .html file "
                "explicitly (book mode has no convention for picking a "
                "non-index entry from a directory).",
                code="INVALID_PARAMS",
            )
        lint_target = in_path
        entry_path = candidate
    else:
        if in_path.suffix.lower() not in (".html", ".htm"):
            json_error(
                f"Input must be a .html file or a directory (got '{in_path}').",
                code="INVALID_PARAMS",
            )
        lint_target = in_path
        entry_path = in_path

    # Pre-publish lint. Errors block; warnings do not.
    # `safe_command` catches SchemaLoadError / OSError uniformly.
    if not no_lint:
        lint_result = lint_path(lint_target, fix=False)
        if lint_result["errors"] > 0:
            json_error(
                f"Refusing to publish: {lint_result['errors']} lint "
                f"error(s) in {lint_target}. Fix and retry, or pass "
                "--no-lint to bypass.",
                code="LINT_ERRORS",
                hint="Run `richdoc lint --fix <input>` for autofixable rules.",
                lint=lint_result,
            )

    config = _load_config(PUBLISH_VARS)
    client = _make_client(config)
    assert config.space_key is not None  # guaranteed by PUBLISH_VARS
    space_key = config.space_key

    # Resolve parent-by-title to an id, if requested.
    if parent_title and parent_id:
        json_error(
            "--parent-id and --parent-title are mutually exclusive.",
            code="INVALID_PARAMS",
        )
    if parent_title:
        space = client.get_space_by_key(space_key)
        matches = client.list_pages(
            space_id=space.id, query=parent_title, limit=50,
        )
        exact = [p for p in matches if p.title == parent_title]
        if not exact:
            json_error(
                f"No page titled {parent_title!r} in space {space_key}.",
                code="NOT_FOUND",
            )
        if len(exact) > 1:
            json_error(
                f"Multiple pages titled {parent_title!r} in {space_key}. "
                "Use --parent-id instead.",
                code="AMBIGUOUS_MATCH",
            )
        parent_id = exact[0].id

    plan = PublishPlan(
        input_path=entry_path,
        space_key=space_key,
        parent_id=parent_id,
        title_override=title_override,
        title_prefix=title_prefix,
        page_id_override=page_id_override,
        no_book=no_book,
        dry_run=dry_run,
        render_diagrams=not no_render_diagrams,
        render_math=not no_render_math,
        diagram_endpoint=diagram_endpoint,
        include_remote_images=include_remote_images,
        update_comment=update_comment,
    )

    result = run_publish(plan, client)

    payload: dict[str, Any] = {
        "input": str(in_path),
        "entry": str(entry_path),
        "site": result.site,
        "space": {
            "id": result.space_id,
            "key": result.space_key,
        },
        "parentId": parent_id,
        "book": result.book,
        "pages": [asdict(po) for po in result.pages],
        "attachments_uploaded": result.attachments_uploaded,
        "attachments_skipped": result.attachments_skipped,
        "diagrams_rendered": result.diagrams_rendered,
        "diagrams_failed": result.diagrams_failed,
        "math_rendered": result.math_rendered,
        "math_failed": result.math_failed,
        "dropped": result.dropped,
        "missing": result.missing,
    }
    if result.dry_run:
        payload["dry_run"] = True
        payload["bodies"] = result.dry_run_bodies
    json_ok(**payload)
