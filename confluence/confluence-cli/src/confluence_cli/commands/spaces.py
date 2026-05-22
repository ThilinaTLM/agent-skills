"""`confluence spaces` — list spaces visible to the token."""

from __future__ import annotations

import click

from ..auth import CredentialRequest, resolve_credentials
from ..client import ConfluenceClient
from ..output import json_ok


@click.command("spaces")
@click.option(
    "--profile", "profile", type=str, default=None,
    help="Profile name (overrides CONFLUENCE_PROFILE).",
)
@click.option(
    "--site", type=str, default=None,
    help="Confluence site URL (overrides profile/env).",
)
@click.option(
    "--email", type=str, default=None,
    help="Atlassian account email (overrides profile/env).",
)
@click.option(
    "--token-env", "token_env", type=str, default=None,
    help="Name of an env var to read the token from.",
)
@click.option(
    "-q", "--query", "query", type=str, default=None,
    help="Filter spaces by key/name substring (case-insensitive).",
)
@click.option(
    "--limit", type=int, default=50, show_default=True,
    help="Maximum number of spaces to return.",
)
def cmd_spaces(
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    query: str | None,
    limit: int,
) -> None:
    """List Confluence spaces visible to the token."""
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
        json_ok(site=client.site, profile=creds.profile, spaces=out)

    run()
