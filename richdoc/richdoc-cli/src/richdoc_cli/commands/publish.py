"""`richdoc publish <target>` — push richdoc HTML to a remote system.

Currently the only target is `confluence`. Three discovery subcommands
plus the actual publisher live under it:

    richdoc publish confluence spaces      [--query …]
    richdoc publish confluence pages       --space-key … [--query …] [--parent-id …]
    richdoc publish confluence page-by-id  PAGE_ID
    richdoc publish confluence push        INPUT [--space-key … --parent-id …]

Credentials are resolved through `auth.resolve_creds()` — flags, env
vars, then interactive prompts (with `getpass` for the token). The token
never appears in any log or JSON envelope.
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import click

from ..output import json_error, json_ok
from ..publish.confluence import (
    ConfluenceClient,
    ConfluenceError,
    CredentialError,
    PublishPlan,
    publish as run_publish,
    resolve_creds,
)


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
# Shared auth flags
# ---------------------------------------------------------------------------


def _auth_options(fn):
    """Decorator: attach --site / --email / --token-stdin to a command."""
    fn = click.option(
        "--site", "site_url", type=str, default=None,
        help="Confluence site URL (e.g. https://acme.atlassian.net). "
        "Falls back to $CONFLUENCE_SITE, then prompt.",
    )(fn)
    fn = click.option(
        "--email", "email", type=str, default=None,
        help="Atlassian account email. Falls back to $CONFLUENCE_EMAIL, "
        "then prompt.",
    )(fn)
    fn = click.option(
        "--token-stdin", "token_stdin", is_flag=True,
        help="Read the API token as one line from stdin. Falls back to "
        "$CONFLUENCE_TOKEN, then a hidden getpass prompt.",
    )(fn)
    return fn


def _make_client(
    *, site_url: str | None, email: str | None, token_stdin: bool,
) -> ConfluenceClient:
    """Resolve credentials and build a client. Errors via json_error."""
    try:
        creds = resolve_creds(
            site=site_url,
            email=email,
            token_stdin=token_stdin,
            allow_prompt=sys.stdin.isatty(),
        )
    except CredentialError as exc:
        json_error(str(exc), code="AUTH_ERROR")
    return ConfluenceClient(
        site=creds.site, email=creds.email, token=creds.token
    )


def _handle_confluence_error(exc: ConfluenceError) -> None:
    code = getattr(exc, "code", "UPSTREAM_ERROR")
    json_error(str(exc), code=code)


# ---------------------------------------------------------------------------
# spaces
# ---------------------------------------------------------------------------


@confluence_group.command("spaces")
@_auth_options
@click.option(
    "-q", "--query", "query", type=str, default=None,
    help="Filter spaces by key/name substring (case-insensitive).",
)
@click.option(
    "--limit", type=int, default=50, show_default=True,
    help="Maximum number of spaces to return.",
)
def cmd_spaces(
    site_url: str | None,
    email: str | None,
    token_stdin: bool,
    query: str | None,
    limit: int,
) -> None:
    """List Confluence spaces visible to the token."""
    client = _make_client(site_url=site_url, email=email, token_stdin=token_stdin)
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
@_auth_options
@click.option(
    "--space-key", "space_key", type=str, required=True,
    help="Space key to list pages from (e.g. DEV).",
)
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
    site_url: str | None,
    email: str | None,
    token_stdin: bool,
    space_key: str,
    query: str | None,
    parent_id: str | None,
    limit: int,
) -> None:
    """List pages in a Confluence space."""
    client = _make_client(site_url=site_url, email=email, token_stdin=token_stdin)
    try:
        space = client.get_space_by_key(space_key)
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
@_auth_options
@click.argument("page_id", metavar="PAGE_ID")
def cmd_page_by_id(
    site_url: str | None,
    email: str | None,
    token_stdin: bool,
    page_id: str,
) -> None:
    """Resolve a Confluence page id to {id, title, parentId, spaceId, url}."""
    client = _make_client(site_url=site_url, email=email, token_stdin=token_stdin)
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
@_auth_options
@click.option(
    "--space-key", "space_key", type=str, required=True,
    help="Target space key (e.g. DEV).",
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
    site_url: str | None,
    email: str | None,
    token_stdin: bool,
    space_key: str,
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

    client = _make_client(site_url=site_url, email=email, token_stdin=token_stdin)

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
