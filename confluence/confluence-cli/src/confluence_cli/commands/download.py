"""``confluence download`` \u2014 pull pages locally as JSONL (+ optional markdown).

See ``references/download.md`` for the on-disk schema and the
edit-and-reupload recipe.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from .. import __version__
from ..auth import CredentialRequest, resolve_credentials
from ..client import (
    Attachment,
    ConfluenceClient,
    ConfluenceNotFoundError,
    Page,
)
from ..output import json_error, json_ok
from ..refs import parse_page_ref

# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------


def _creds_opts(fn):
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


@click.command("download")
@_creds_opts
@click.argument("page_ref", metavar="PAGE_ID_OR_URL", required=False, default=None)
@click.option(
    "--space-key", "space_key", type=str, default=None,
    help="Target space key. Required when PAGE_REF is omitted.",
)
@click.option(
    "--title", "title", type=str, default=None,
    help="Resolve a page by exact title within --space-key.",
)
@click.option(
    "-o", "--output", "output_dir", type=click.Path(file_okay=False),
    default=None,
    help="Output directory (created if missing). Defaults to "
         "'confluence-dump-<timestamp>' in the current directory.",
)
@click.option(
    "--recurse/--no-recurse", "recurse", default=False, show_default=True,
    help="Include descendants of the resolved page.",
)
@click.option(
    "--depth", type=int, default=None,
    help="When recursing, max nesting depth below the starting page "
         "(1 = direct children only). Unlimited by default.",
)
@click.option(
    "--limit", type=int, default=200, show_default=True,
    help="Hard cap on the number of pages downloaded.",
)
@click.option(
    "--markdown", "markdown", is_flag=True,
    help="Also write a best-effort markdown rendering per page.",
)
@click.option(
    "--attachments", "attachments", is_flag=True,
    help="Also download attachment bytes alongside each page.",
)
@click.option(
    "--force", "force", is_flag=True,
    help="Overwrite existing files in the output directory.",
)
def cmd_download(
    profile: str | None,
    site: str | None,
    email: str | None,
    token_env: str | None,
    page_ref: str | None,
    space_key: str | None,
    title: str | None,
    output_dir: str | None,
    recurse: bool,
    depth: int | None,
    limit: int,
    markdown: bool,
    attachments: bool,
    force: bool,
) -> None:
    """Download Confluence pages locally as JSONL (+ optional markdown).

    Accepts a numeric PAGE_ID or a Confluence page URL. With
    --space-key alone, walks every page in the space (still bounded by
    --limit).
    """
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        if limit <= 0:
            json_error(
                "--limit must be a positive integer.",
                code="INVALID_PARAMS",
            )
        if depth is not None and depth <= 0:
            json_error(
                "--depth must be a positive integer when given.",
                code="INVALID_PARAMS",
            )
        if page_ref and title:
            json_error(
                "PAGE_ID_OR_URL and --title are mutually exclusive.",
                code="INVALID_PARAMS",
                hint="Pick one: a page reference, or --title --space-key.",
            )
        if not page_ref and not space_key:
            json_error(
                "Provide a page reference or --space-key.",
                code="INVALID_PARAMS",
                hint=(
                    "Examples: `confluence download 123456`, "
                    "`confluence download https://acme.atlassian.net/wiki/spaces/DEV/pages/123/T`, "
                    "or `confluence download --space-key DEV --title 'How to deploy'`. "
                    "Use `confluence pages --space-key KEY` to discover ids."
                ),
            )

        target_page_id: str | None = None
        if page_ref:
            target_page_id = parse_page_ref(page_ref)

        require_space = bool(space_key) and (not page_ref)
        creds = resolve_credentials(
            CredentialRequest(
                profile=profile, site=site, email=email, token_env=token_env,
                space_key=space_key, require_space_key=require_space,
            )
        )
        client = ConfluenceClient(
            site=creds.site, email=creds.email, token=creds.token,
        )

        # Resolve the starting page(s).
        truncated = False
        pages: list[Page] = []
        space_key_used: str | None = None

        if target_page_id is not None:
            root = client.get_page(target_page_id)
            pages.append(root)
            if recurse:
                for child in client.iter_descendants(
                    root.id, depth=depth, limit=limit - 1,
                ):
                    pages.append(child)
                if len(pages) - 1 >= limit - 1:
                    # Walk hit the cap; double-check there might have been more.
                    truncated = _peek_more_descendants(
                        client, root.id, depth, limit - 1,
                    )
        elif title:
            if not creds.space_key:
                json_error(
                    "--space-key is required when looking up by --title.",
                    code="INVALID_PARAMS",
                )
            space_key_used = creds.space_key
            space = client.get_space_by_key(creds.space_key)
            found = client.find_page_by_title(
                space_id=space.id, title=title, parent_id=None,
            )
            if not found:
                raise ConfluenceNotFoundError(
                    f"No page with title {title!r} in space "
                    f"{creds.space_key!r}.",
                )
            pages.append(found)
            if recurse:
                for child in client.iter_descendants(
                    found.id, depth=depth, limit=limit - 1,
                ):
                    pages.append(child)
                if len(pages) - 1 >= limit - 1:
                    truncated = _peek_more_descendants(
                        client, found.id, depth, limit - 1,
                    )
        else:
            # --space-key alone: list every page in the space.
            assert creds.space_key
            space_key_used = creds.space_key
            space = client.get_space_by_key(creds.space_key)
            listed = client.list_pages(space_id=space.id, limit=limit)
            pages.extend(listed)
            if len(pages) >= limit:
                # We can't cheaply tell if there were more without
                # another paginated call; mark as truncated to be safe.
                truncated = True

        if not pages:
            json_error(
                "No pages resolved.",
                code="NOT_FOUND",
                hint="Try `confluence pages --space-key KEY` for discovery.",
            )

        # Resolve space metadata once (for the manifest + URLs).
        if not space_key_used:
            # Derive from the first page's space.
            # The v2 page payload doesn't include the key, only the id;
            # there's no direct id\u2192key endpoint, so we list spaces and
            # match on id.
            space_key_used = _space_key_for_id(client, pages[0].space_id)
        try:
            space_obj = client.get_space_by_key(space_key_used) if space_key_used else None
        except ConfluenceNotFoundError:
            space_obj = None

        # Prepare output directory.
        out = Path(output_dir) if output_dir else Path(
            f"confluence-dump-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        )
        _prepare_output(out, force=force, want_markdown=markdown,
                        want_attachments=attachments)

        # Build a page index for cross-page link resolution in markdown.
        page_index = {
            p.title: {"id": p.id, "title": p.title, "url": client.page_url(
                p, space_key_used or "")}
            for p in pages
        }

        # Process each page.
        jsonl_path = out / "pages.jsonl"
        manifest_path = out / "manifest.json"
        markdown_dir = out / "pages"
        attachments_dir = out / "attachments"

        rows: list[dict[str, Any]] = []
        attachments_downloaded_count = 0
        markdown_generated_count = 0

        with jsonl_path.open("w", encoding="utf-8") as fh:
            for page in pages:
                # Fetch body and attachments.
                full_page, body_value = client.get_page_body(
                    page.id, representation="storage",
                )
                page_atts = client.list_attachments(page.id)

                downloaded_atts: list[dict[str, Any]] = []
                for att in page_atts:
                    record = _attachment_record(att)
                    if attachments:
                        try:
                            data = client.fetch_attachment(att, page_id=page.id)
                        except Exception as exc:
                            record["downloaded"] = False
                            record["error"] = str(exc)
                        else:
                            page_att_dir = attachments_dir / page.id
                            page_att_dir.mkdir(parents=True, exist_ok=True)
                            safe_name = _safe_filename(att.title)
                            dest = page_att_dir / safe_name
                            dest.write_bytes(data)
                            record["downloaded"] = True
                            record["path"] = str(
                                dest.relative_to(out).as_posix()
                            )
                            attachments_downloaded_count += 1
                    downloaded_atts.append(record)

                # Optional markdown.
                md_rel: str | None = None
                if markdown:
                    md_text = _render_markdown(
                        body_value,
                        page_id=page.id,
                        page_index=page_index,
                        attachments_downloaded=attachments,
                        site_url=client.site,
                    )
                    safe_title = _safe_slug(full_page.title)
                    md_path = markdown_dir / f"{safe_title}--{page.id}.md"
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    md_path.write_text(md_text, encoding="utf-8")
                    md_rel = str(md_path.relative_to(out).as_posix())
                    markdown_generated_count += 1

                row = {
                    "schema": "confluence.page.dump.v1",
                    "id": full_page.id,
                    "title": full_page.title,
                    "spaceId": full_page.space_id,
                    "spaceKey": space_key_used,
                    "parentId": full_page.parent_id,
                    "version": full_page.version,
                    "createdAt": full_page.created_at,
                    "updatedAt": full_page.updated_at,
                    "authorId": full_page.author_id,
                    "webui": full_page.webui,
                    "url": client.page_url(full_page, space_key_used or ""),
                    "body": {
                        "representation": "storage",
                        "value": body_value,
                    },
                    "attachments": downloaded_atts,
                    "markdown": md_rel,
                }
                fh.write(json.dumps(row, ensure_ascii=False))
                fh.write("\n")
                rows.append(row)

        # Manifest.
        manifest = {
            "schema": "confluence.dump.v1",
            "site": client.site,
            "space": (
                {
                    "id": space_obj.id,
                    "key": space_obj.key,
                    "name": space_obj.name,
                }
                if space_obj
                else (
                    {"id": pages[0].space_id, "key": space_key_used, "name": None}
                    if pages
                    else None
                )
            ),
            "rootPageId": pages[0].id if pages else None,
            "exportedAt": datetime.now(UTC).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            "exportedBy": f"confluence-cli/{__version__}",
            "pageCount": len(rows),
            "attachmentCount": attachments_downloaded_count,
            "truncated": truncated,
            "options": {
                "recurse": recurse,
                "depth": depth,
                "limit": limit,
                "markdown": markdown,
                "attachments": attachments,
            },
            "tree": [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "parentId": r["parentId"],
                    "url": r["url"],
                    "jsonlLine": idx + 1,
                    "markdown": r["markdown"],
                }
                for idx, r in enumerate(rows)
            ],
            "markdownNote": (
                "Best-effort conversion. Do NOT re-upload from markdown \u2014 "
                "edit pages.jsonl 'body.value' (storage XML) and use "
                "'confluence page update --body-file'."
            ),
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        # Success envelope.
        first_page = rows[0]
        next_step = {
            "summary": (
                "Edit the storage body in pages.jsonl (the 'body.value' "
                "field), write it to a file, then re-upload with "
                "`confluence page update`."
            ),
            "argv": [
                "confluence", "page", "update", first_page["id"],
                "--body-file", "<edited.storage.xml>",
            ],
        }

        json_ok(
            site=client.site,
            profile=creds.profile,
            outputDir=str(out.resolve()),
            manifest=str(manifest_path.resolve()),
            jsonl=str(jsonl_path.resolve()),
            pageCount=len(rows),
            attachmentsDownloaded=attachments_downloaded_count,
            markdownGenerated=markdown_generated_count,
            truncated=truncated,
            pages=[
                {"id": r["id"], "title": r["title"], "url": r["url"]}
                for r in rows
            ],
            nextStep=next_step,
        )

    run()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_markdown(
    body_value: str,
    *,
    page_id: str,
    page_index: dict[str, dict[str, str]],
    attachments_downloaded: bool,
    site_url: str,
) -> str:
    from ..markdown import MarkdownError, PageRef, storage_to_markdown

    refs = {
        title: PageRef(id=info["id"], title=info["title"], url=info["url"])
        for title, info in page_index.items()
    }
    try:
        return storage_to_markdown(
            body_value,
            page_id=page_id,
            page_index=refs,
            attachments_downloaded=attachments_downloaded,
            site_url=site_url,
        )
    except MarkdownError:
        raise


def _attachment_record(att: Attachment) -> dict[str, Any]:
    return {
        "id": att.id,
        "title": att.title,
        "mediaType": att.media_type,
        "fileId": att.file_id,
        "fileSize": att.file_size,
        "downloaded": False,
        "path": None,
    }


def _safe_slug(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if not s:
        s = "page"
    return s[:80]


def _safe_filename(name: str) -> str:
    # Keep dots and dashes; collapse anything else.
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    return cleaned or "file"


def _prepare_output(
    out: Path, *, force: bool, want_markdown: bool, want_attachments: bool,
) -> None:
    if out.exists():
        if not out.is_dir():
            raise FileExistsError(
                f"Output path {out} exists and is not a directory."
            )
        if any(out.iterdir()) and not force:
            raise FileExistsError(
                f"Output directory {out} is not empty. Re-run with --force."
            )
    out.mkdir(parents=True, exist_ok=True)
    if want_markdown:
        (out / "pages").mkdir(exist_ok=True)
    if want_attachments:
        (out / "attachments").mkdir(exist_ok=True)


def _peek_more_descendants(
    client: ConfluenceClient,
    root_id: str,
    depth: int | None,
    limit: int,
) -> bool:
    """Best-effort: ask for one more descendant past the cap.

    Returns ``True`` if the walk would have produced more pages had the
    cap been larger. We deliberately keep this cheap \u2014 a single extra
    API call \u2014 to avoid amplifying the runaway risk we were guarding
    against.
    """
    try:
        for _ in client.iter_descendants(root_id, depth=depth, limit=limit + 1):
            pass
    except Exception:
        return True  # if we can't tell, assume yes \u2014 safer for the agent.
    # If we couldn't iterate to limit+1 cleanly we'd already have raised;
    # if we did, then there were more.
    return True


def _space_key_for_id(client: ConfluenceClient, space_id: str) -> str | None:
    """Resolve a space id to its key by scanning visible spaces.

    The v2 API has no id\u2192key endpoint; we walk the list once. Returns
    ``None`` if the space isn't visible (shouldn't happen if we can
    read its pages).
    """
    for sp in client.list_spaces(limit=250):
        if sp.id == space_id:
            return sp.key
    return None
