"""`confluence pages` and `confluence page-by-id` / `confluence page ...`."""

from __future__ import annotations

import click

from ..auth import CredentialRequest, resolve_credentials
from ..client import ConfluenceClient
from ..output import json_ok

# ---------------------------------------------------------------------------
# Shared option decorator
# ---------------------------------------------------------------------------


def _common_creds_opts(fn):
    fn = click.option(
        "--profile", "profile", type=str, default=None,
        help="Profile name (overrides CONFLUENCE_PROFILE).",
    )(fn)
    fn = click.option(
        "--site", type=str, default=None,
        help="Confluence site URL (overrides profile/env).",
    )(fn)
    fn = click.option(
        "--email", type=str, default=None,
        help="Atlassian account email (overrides profile/env).",
    )(fn)
    fn = click.option(
        "--token-env", "token_env", type=str, default=None,
        help="Name of an env var to read the token from.",
    )(fn)
    return fn


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------


@click.command("pages")
@_common_creds_opts
@click.option(
    "--space-key", "space_key", type=str, default=None,
    help="Target space key. Defaults to the profile's spaceKey.",
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
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    space_key: str | None,
    query: str | None,
    parent_id: str | None,
    limit: int,
) -> None:
    """List pages in a Confluence space."""
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        creds = resolve_credentials(
            CredentialRequest(
                profile=profile, site=site, email=email, token_env=token_env,
                space_key=space_key, require_space_key=True,
            )
        )
        client = ConfluenceClient(
            site=creds.site, email=creds.email, token=creds.token,
        )
        assert creds.space_key is not None
        space = client.get_space_by_key(creds.space_key)
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
            profile=creds.profile,
            space={"id": space.id, "key": space.key, "name": space.name},
            pages=out,
        )

    run()


# ---------------------------------------------------------------------------
# page-by-id (compatibility alias for `page get`)
# ---------------------------------------------------------------------------


@click.command("page-by-id")
@_common_creds_opts
@click.argument("page_id", metavar="PAGE_ID")
def cmd_page_by_id(
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    page_id: str,
) -> None:
    """Resolve a Confluence page id to its metadata."""
    _page_get_impl(profile, site, email, token_env, page_id, body=False)


# ---------------------------------------------------------------------------
# page group: get / create / update / delete
# ---------------------------------------------------------------------------


@click.group("page", help="Page management (get / create / update / delete).")
def page_group() -> None:
    pass


@page_group.command("get")
@_common_creds_opts
@click.argument("page_id", metavar="PAGE_ID")
@click.option(
    "--body", "include_body", is_flag=True,
    help="Include the page's storage-format body in the envelope.",
)
def cmd_page_get(
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    page_id: str,
    include_body: bool,
) -> None:
    """Fetch one page's metadata (and optionally its body)."""
    _page_get_impl(profile, site, email, token_env, page_id, body=include_body)


def _page_get_impl(
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    page_id: str,
    *,
    body: bool,
) -> None:
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        creds = resolve_credentials(
            CredentialRequest(
                profile=profile, site=site, email=email, token_env=token_env,
            )
        )
        client = ConfluenceClient(
            site=creds.site, email=creds.email, token=creds.token,
        )
        page = client.get_page(page_id)
        public = (
            f"{client.site}/wiki{page.webui}"
            if page.webui
            else f"{client.site}/wiki/pages/{page.id}"
        )
        payload: dict = {
            "page": {
                "id": page.id,
                "title": page.title,
                "parentId": page.parent_id,
                "spaceId": page.space_id,
                "version": page.version,
                "url": public,
            },
            "profile": creds.profile,
        }
        if body:
            # Body fetch needs a separate v2 call with `body-format=storage`.
            # The current client doesn't expose it as a method — emit a
            # placeholder so the envelope shape stays predictable.
            payload["body"] = None
            payload["body_note"] = (
                "Body fetch is not yet implemented. Use the v2 REST API "
                "directly or extend ConfluenceClient.get_page_body."
            )
        json_ok(**payload)

    run()


@page_group.command("create")
@_common_creds_opts
@click.option(
    "--space-key", "space_key", type=str, default=None,
    help="Target space key. Defaults to the profile's spaceKey.",
)
@click.option("--parent-id", "parent_id", type=str, default=None)
@click.option("--title", "title", type=str, required=True)
@click.option(
    "--body-file", "body_file", type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to a file containing Confluence storage-format XML.",
)
def cmd_page_create(
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    space_key: str | None,
    parent_id: str | None,
    title: str,
    body_file: str,
) -> None:
    """Create a new page from a storage-format XML file."""
    from pathlib import Path

    from ..cli import safe_command

    @safe_command
    def run() -> None:
        creds = resolve_credentials(
            CredentialRequest(
                profile=profile, site=site, email=email, token_env=token_env,
                space_key=space_key, require_space_key=True,
            )
        )
        client = ConfluenceClient(
            site=creds.site, email=creds.email, token=creds.token,
        )
        assert creds.space_key is not None
        space = client.get_space_by_key(creds.space_key)
        body = Path(body_file).read_text(encoding="utf-8")
        page = client.create_page(
            space_id=space.id,
            parent_id=parent_id,
            title=title,
            body_storage=body,
        )
        json_ok(
            site=client.site,
            profile=creds.profile,
            page={
                "id": page.id,
                "title": page.title,
                "parentId": page.parent_id,
                "spaceId": page.space_id,
                "version": page.version,
                "url": client.page_url(page, space.key),
            },
        )

    run()


@page_group.command("update")
@_common_creds_opts
@click.argument("page_id", metavar="PAGE_ID")
@click.option("--title", "title", type=str, default=None)
@click.option(
    "--body-file", "body_file", type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to a file containing Confluence storage-format XML.",
)
@click.option("--comment", "comment", type=str, default="Updated via confluence CLI")
def cmd_page_update(
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    page_id: str,
    title: str | None,
    body_file: str,
    comment: str,
) -> None:
    """Update an existing page with a new body and (optionally) title."""
    from pathlib import Path

    from ..cli import safe_command

    @safe_command
    def run() -> None:
        creds = resolve_credentials(
            CredentialRequest(
                profile=profile, site=site, email=email, token_env=token_env,
            )
        )
        client = ConfluenceClient(
            site=creds.site, email=creds.email, token=creds.token,
        )
        page = client.get_page(page_id)
        new_title = title or page.title
        body = Path(body_file).read_text(encoding="utf-8")
        updated = client.update_page(
            page_id=page.id,
            title=new_title,
            body_storage=body,
            current_version=page.version,
            comment=comment,
        )
        json_ok(
            site=client.site,
            profile=creds.profile,
            page={
                "id": updated.id,
                "title": updated.title,
                "parentId": updated.parent_id,
                "spaceId": updated.space_id,
                "version": updated.version,
            },
        )

    run()
