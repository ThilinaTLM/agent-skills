"""Two-pass publisher: bundle -> Confluence pages + attachments.

Algorithm
=========

1. Resolve target space.
2. Resolve ``--parent-title`` to a parent id if requested.
3. **First pass.** For every page in manifest order:
     - compute the Confluence parent id from the manifest's
       ``parentKey`` (cascading through pages resolved earlier in
       this pass, with the explicit ``--parent-id`` for root pages);
     - apply ``--title-prefix``;
     - locate an existing page by ``(space, parent, title)`` or
       ``--page-id`` for the first page;
     - create new pages with a placeholder body so a real page id
       exists before we resolve cross-page link tokens;
     - record ``pageKey -> Page`` and ``pageKey -> public URL``.
4. **Second pass.** For every page:
     - upload its attachments (skip if Confluence already has them
       under the same filename);
     - read the storage XML off disk;
     - substitute ``@@ATTACHMENT:...@@`` tokens with
       ``<ac:image>`` references;
     - substitute ``@@RICHDOC_PAGE_URL:...@@`` tokens with the
       resolved public URL;
     - update the page body; retry once on version conflict.

The publisher refuses to start if any link token in the bundle
references a page key that is not in the manifest — that would
indicate a producer bug and silent broken links on Confluence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .bundle import (
    BundleAttachment,
    BundleLink,
    BundleManifest,
    BundlePage,
    read_attachment,
    read_storage,
)
from .client import (
    ConfluenceClient,
    ConfluenceConflictError,
    Page,
)

_PAGE_URL_TOKEN_RE = re.compile(r"@@RICHDOC_PAGE_URL:([^@]+)@@")


# ---------------------------------------------------------------------------
# Plan / result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PublishBundlePlan:
    bundle_dir: Path
    space_key: str
    parent_id: str | None = None
    parent_title: str | None = None
    page_id_override: str | None = None
    title_prefix: str = ""
    dry_run: bool = False
    update_comment: str = "Updated via confluence CLI"


@dataclass
class PageOutcome:
    id: str
    title: str
    parent_id: str | None
    url: str
    action: str          # "created" | "updated" | "planned"
    version: int


@dataclass
class PublishResult:
    site: str
    space_id: str
    space_key: str
    book: bool
    pages: list[PageOutcome] = field(default_factory=list)
    attachments_uploaded: int = 0
    attachments_skipped: int = 0
    unresolved_links: list[str] = field(default_factory=list)
    dry_run: bool = False


class PublishError(RuntimeError):
    """Raised for publish-side validation errors before any network call."""

    def __init__(self, message: str, *, code: str = "INVALID_BUNDLE") -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def publish_bundle(
    plan: PublishBundlePlan,
    manifest: BundleManifest,
    client: ConfluenceClient,
) -> PublishResult:
    """Run the publish pipeline."""
    _validate_links(manifest)

    space = client.get_space_by_key(plan.space_key)
    parent_id = _resolve_parent_id(plan, space.id, client)

    # Map page_key -> manifest page object for fast lookup.
    pages_by_key: dict[str, BundlePage] = {p.key: p for p in manifest.pages}

    # First pass.
    chapter_pages: dict[str, Page] = {}
    cross_page_urls: dict[str, str] = {}
    outcomes: list[PageOutcome] = []
    for idx, page in enumerate(manifest.pages):
        chapter_parent_id = (
            chapter_pages[page.parent_key].id
            if (page.parent_key and page.parent_key in chapter_pages)
            else parent_id
        )
        full_title = (plan.title_prefix or "") + page.title

        existing = _find_existing(
            client,
            space_id=space.id,
            page_id_override=(plan.page_id_override if idx == 0 else None),
            title=full_title,
            parent_id=chapter_parent_id,
        )

        if plan.dry_run:
            outcomes.append(
                PageOutcome(
                    id=existing.id if existing else "(planned)",
                    title=full_title,
                    parent_id=chapter_parent_id,
                    url=(
                        client.page_url(existing, space.key)
                        if existing
                        else "(planned)"
                    ),
                    action="planned",
                    version=existing.version if existing else 0,
                )
            )
            chapter_pages[page.key] = existing or Page(
                id="(planned)",
                title=full_title,
                space_id=space.id,
                parent_id=chapter_parent_id,
                version=0,
                webui="",
            )
            cross_page_urls[page.key] = "(planned)"
            continue

        if existing is None:
            # First pass always uses a placeholder body. The real body
            # comes in the second pass after attachments are uploaded
            # and cross-page URL tokens are substituted.
            placeholder = (
                "<p><em>Publishing — body coming in a follow-up update.</em></p>"
            )
            created = client.create_page(
                space_id=space.id,
                parent_id=chapter_parent_id,
                title=full_title,
                body_storage=placeholder,
            )
            chapter_pages[page.key] = created
            cross_page_urls[page.key] = client.page_url(created, space.key)
            outcomes.append(
                PageOutcome(
                    id=created.id,
                    title=created.title,
                    parent_id=created.parent_id,
                    url=cross_page_urls[page.key],
                    action="created",
                    version=created.version,
                )
            )
        else:
            chapter_pages[page.key] = existing
            cross_page_urls[page.key] = client.page_url(existing, space.key)
            outcomes.append(
                PageOutcome(
                    id=existing.id,
                    title=existing.title,
                    parent_id=existing.parent_id,
                    url=cross_page_urls[page.key],
                    action="updated",
                    version=existing.version,
                )
            )

    if plan.dry_run:
        return PublishResult(
            site=client.site,
            space_id=space.id,
            space_key=space.key,
            book=manifest.book,
            pages=outcomes,
            dry_run=True,
        )

    # Second pass.
    attachments_uploaded = 0
    attachments_skipped = 0
    for outcome, page in zip(outcomes, manifest.pages, strict=True):
        confluence_page = chapter_pages[page.key]
        body = read_storage(manifest, page)

        # Upload attachments and substitute their tokens.
        if page.attachments:
            existing_atts = {a.title for a in client.list_attachments(confluence_page.id)}
            for att in page.attachments:
                if att.filename in existing_atts:
                    attachments_skipped += 1
                else:
                    data = read_attachment(manifest, att)
                    client.upload_attachment(
                        page_id=confluence_page.id,
                        filename=att.filename,
                        data=data,
                        mime=att.mime,
                        comment=plan.update_comment,
                    )
                    attachments_uploaded += 1
                    existing_atts.add(att.filename)
                body = body.replace(att.token, _image_xml(att))

        # Substitute page-URL tokens.
        body = _substitute_link_tokens(body, page.links, cross_page_urls, pages_by_key)

        # Push the final body. Retry once on version conflict.
        try:
            updated = client.update_page(
                page_id=confluence_page.id,
                title=outcome.title,
                body_storage=body,
                current_version=confluence_page.version,
                parent_id=outcome.parent_id,
                comment=plan.update_comment,
            )
        except ConfluenceConflictError:
            fresh = client.get_page(confluence_page.id)
            updated = client.update_page(
                page_id=fresh.id,
                title=outcome.title,
                body_storage=body,
                current_version=fresh.version,
                parent_id=outcome.parent_id,
                comment=plan.update_comment,
            )
        outcome.version = updated.version

    return PublishResult(
        site=client.site,
        space_id=space.id,
        space_key=space.key,
        book=manifest.book,
        pages=outcomes,
        attachments_uploaded=attachments_uploaded,
        attachments_skipped=attachments_skipped,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_links(manifest: BundleManifest) -> None:
    """Fail fast on broken cross-page links inside the bundle."""
    keys = {p.key for p in manifest.pages}
    broken: list[tuple[str, str]] = []
    for page in manifest.pages:
        for link in page.links:
            if link.target_key not in keys:
                broken.append((page.key, link.target_key))
    if broken:
        first = ", ".join(f"{src} -> {tgt}" for src, tgt in broken[:5])
        raise PublishError(
            f"Bundle contains {len(broken)} unresolved cross-page link(s): {first}",
            code="INVALID_BUNDLE",
        )


def _resolve_parent_id(
    plan: PublishBundlePlan, space_id: str, client: ConfluenceClient
) -> str | None:
    if plan.parent_title and plan.parent_id:
        raise PublishError(
            "--parent-id and --parent-title are mutually exclusive.",
            code="INVALID_PARAMS",
        )
    if plan.parent_title:
        matches = client.list_pages(
            space_id=space_id, query=plan.parent_title, limit=50,
        )
        exact = [p for p in matches if p.title == plan.parent_title]
        if not exact:
            raise PublishError(
                f"No page titled {plan.parent_title!r} in target space.",
                code="NOT_FOUND",
            )
        if len(exact) > 1:
            raise PublishError(
                f"Multiple pages titled {plan.parent_title!r}; use --parent-id.",
                code="AMBIGUOUS_MATCH",
            )
        return exact[0].id
    return plan.parent_id


def _find_existing(
    client: ConfluenceClient,
    *,
    space_id: str,
    page_id_override: str | None,
    title: str,
    parent_id: str | None,
) -> Page | None:
    if page_id_override:
        return client.get_page(page_id_override)
    return client.find_page_by_title(
        space_id=space_id, title=title, parent_id=parent_id
    )


def _image_xml(att: BundleAttachment) -> str:
    safe_name = _xml_attr(att.filename)
    if att.inline:
        return (
            f'<ac:image><ri:attachment ri:filename="{safe_name}"/></ac:image>'
        )
    align = _xml_attr(att.align or "center")
    return (
        f'<ac:image ac:align="{align}">'
        f'<ri:attachment ri:filename="{safe_name}"/>'
        "</ac:image>"
    )


def _substitute_link_tokens(
    body: str,
    declared_links: list[BundleLink],
    urls_by_key: dict[str, str],
    pages_by_key: dict[str, BundlePage],
) -> str:
    """Replace every ``@@RICHDOC_PAGE_URL:<key>@@`` with its resolved URL.

    Falls back to the well-known declared links first; then sweeps the
    body for any straggler tokens the producer didn't pre-declare.
    """
    _ = pages_by_key  # reserved for future title-based fallback

    # 1. Declared links — fast, deterministic.
    for link in declared_links:
        url = urls_by_key.get(link.target_key)
        if url is None:
            continue
        body = body.replace(link.token, url)

    # 2. Sweep stragglers.
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        url = urls_by_key.get(key)
        return url if url else match.group(0)

    return _PAGE_URL_TOKEN_RE.sub(replace, body)


def _xml_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
