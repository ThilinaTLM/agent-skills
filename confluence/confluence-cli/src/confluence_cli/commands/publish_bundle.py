"""`confluence publish-bundle` — publish a richdoc bundle."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import click

from ..auth import CredentialRequest, resolve_credentials
from ..bundle import read_bundle
from ..client import ConfluenceClient
from ..output import json_ok
from ..publish import PublishBundlePlan, publish_bundle


@click.command("publish-bundle")
@click.argument(
    "bundle_dir",
    metavar="BUNDLE",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
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
    "--space-key", "space_key", type=str, default=None,
    help="Target space key. Defaults to the profile's spaceKey.",
)
@click.option(
    "--parent-id", "parent_id", type=str, default=None,
    help="Parent page id. Pages land under it. Default: profile parentId or space root.",
)
@click.option(
    "--parent-title", "parent_title", type=str, default=None,
    help="Resolve a parent page by exact title (must be unique in the space).",
)
@click.option(
    "--page-id", "page_id_override", type=str, default=None,
    help="Force update of this specific page id for the bundle's first page.",
)
@click.option(
    "--title-prefix", "title_prefix", type=str, default="",
    help="Prepended to every page title (e.g. '[richdoc] ').",
)
@click.option(
    "--dry-run", "dry_run", is_flag=True,
    help="Walk every page and report what would happen without "
    "calling create/update/upload endpoints.",
)
@click.option(
    "--comment", "update_comment", type=str,
    default="Updated via confluence CLI", show_default=True,
    help="Version comment recorded on each updated page.",
)
def cmd_publish_bundle(
    bundle_dir: Path,
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    space_key: str | None,
    parent_id: str | None,
    parent_title: str | None,
    page_id_override: str | None,
    title_prefix: str,
    dry_run: bool,
    update_comment: str,
) -> None:
    """Publish a richdoc.confluence.bundle.v1 directory."""
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        creds = resolve_credentials(
            CredentialRequest(
                profile=profile, site=site, email=email, token_env=token_env,
                space_key=space_key, parent_id=parent_id, require_space_key=True,
            )
        )

        manifest = read_bundle(bundle_dir)

        client = ConfluenceClient(
            site=creds.site, email=creds.email, token=creds.token,
        )
        assert creds.space_key is not None
        plan = PublishBundlePlan(
            bundle_dir=manifest.bundle_dir,
            space_key=creds.space_key,
            parent_id=parent_id or creds.parent_id,
            parent_title=parent_title,
            page_id_override=page_id_override,
            title_prefix=title_prefix,
            dry_run=dry_run,
            update_comment=update_comment,
        )

        result = publish_bundle(plan, manifest, client)

        json_ok(
            bundle=str(manifest.bundle_dir),
            schema=manifest.schema,
            site=result.site,
            profile=creds.profile,
            space={"id": result.space_id, "key": result.space_key},
            parentId=plan.parent_id,
            book=result.book,
            pages=[asdict(p) for p in result.pages],
            attachments_uploaded=result.attachments_uploaded,
            attachments_skipped=result.attachments_skipped,
            unresolved_links=result.unresolved_links,
            dry_run=result.dry_run,
        )

    run()
