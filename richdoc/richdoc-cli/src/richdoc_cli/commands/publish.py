"""`richdoc publish <target>` — push richdoc HTML to a remote system.

Currently the only target is `confluence`. Three discovery subcommands
plus the actual publisher live under it:

    richdoc publish confluence spaces      [--query …]
    richdoc publish confluence pages       [--query …] [--parent-id …]
    richdoc publish confluence page-by-id  PAGE_ID
    richdoc publish confluence push        INPUT [--parent-id …]

Credentials and the target space come from four environment variables:
`CONFLUENCE_SITE`, `CONFLUENCE_EMAIL`, `CONFLUENCE_TOKEN`, and
`CONFLUENCE_SPACE_KEY` (the last is required for `pages` and `push`
only). There are no flags and no interactive prompts. When a required
var is missing the CLI exits with `code: CONFIG_MISSING` and the calling
agent should ask the user to export the listed vars.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import click

from ..output import json_error, json_ok
from ..publish.confluence import (
    Config,
    ConfigError,
    ConfluenceClient,
    ConfluenceError,
    PublishPlan,
    publish as run_publish,
    resolve_config,
)
from ..publish.confluence.config import AUTH_VARS, PUBLISH_VARS


# ---------------------------------------------------------------------------
# Top-level group hierarchy
# ---------------------------------------------------------------------------


@click.group(
    name="publish", help="Publish a richdoc HTML to a remote system."
)
def group() -> None:
    pass


@group.group(
    "confluence",
    help="Publish to Confluence Cloud via the REST API.",
)
def confluence_group() -> None:
    pass


# ---------------------------------------------------------------------------
# Shared env-var config
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


def _handle_confluence_error(exc: ConfluenceError) -> None:
    code = getattr(exc, "code", "UPSTREAM_ERROR")
    json_error(str(exc), code=code)


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
def cmd_spaces(query: str | None, limit: int) -> None:
    """List Confluence spaces visible to the token."""
    config = _load_config(AUTH_VARS)
    client = _make_client(config)
    try:
        spaces = client.list_spaces(query=query, limit=limit)
    except ConfluenceError as exc:
        _handle_confluence_error(exc)
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
def cmd_pages(
    query: str | None, parent_id: str | None, limit: int,
) -> None:
    """List pages in the configured Confluence space ($CONFLUENCE_SPACE_KEY)."""
    config = _load_config(PUBLISH_VARS)
    client = _make_client(config)
    assert config.space_key is not None  # guaranteed by PUBLISH_VARS
    try:
        space = client.get_space_by_key(config.space_key)
        pages = client.list_pages(
            space_id=space.id, query=query, parent_id=parent_id, limit=limit,
        )
    except ConfluenceError as exc:
        _handle_confluence_error(exc)
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
def cmd_page_by_id(page_id: str) -> None:
    """Resolve a Confluence page id to {id, title, parentId, spaceId, url}."""
    config = _load_config(AUTH_VARS)
    client = _make_client(config)
    try:
        page = client.get_page(page_id)
    except ConfluenceError as exc:
        _handle_confluence_error(exc)
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
# push
# ---------------------------------------------------------------------------


@confluence_group.command("push")
@click.argument(
    "input_",
    metavar="INPUT",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
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
    help="Disable book auto-detection — push only the entry file.",
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
def cmd_push(
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
) -> None:
    """Publish a richdoc HTML document (single file or whole book) to Confluence."""
    in_path = input_.resolve()
    if in_path.suffix.lower() not in (".html", ".htm"):
        json_error(
            f"Input must be a .html file (got '{in_path}').",
            code="INVALID_PARAMS",
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
        try:
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
        except ConfluenceError as exc:
            _handle_confluence_error(exc)

    plan = PublishPlan(
        input_path=in_path,
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

    try:
        result = run_publish(plan, client)
    except ConfluenceError as exc:
        _handle_confluence_error(exc)
    except OSError as exc:
        json_error(f"Could not read input: {exc}", code="INPUT_ERROR")

    payload: dict = {
        "input": str(in_path),
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
