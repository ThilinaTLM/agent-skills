"""Confluence Cloud REST client (stdlib only).

Mixes v2 (spaces, pages) and v1 (attachments) endpoints — v2 attachments
are read-only, so create/update needs the legacy v1 path. HTTP Basic auth
with `email:api_token`. The token never appears in error messages.

Errors map to typed exceptions:

    ConfluenceAuthError       — 401
    ConfluencePermissionError — 403
    ConfluenceNotFoundError   — 404
    ConfluenceConflictError   — 409
    ConfluenceTooLargeError   — 413
    ConfluenceUpstreamError   — 5xx
    ConfluenceClientError     — other 4xx
"""

from __future__ import annotations

import base64
import io
import json
import mimetypes
import uuid
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Space:
    id: str
    key: str
    name: str
    type: str
    homepage_id: str | None
    webui: str  # relative path e.g. /spaces/SD


@dataclass(frozen=True)
class Page:
    id: str
    title: str
    space_id: str
    parent_id: str | None
    version: int
    webui: str  # relative


@dataclass(frozen=True)
class Attachment:
    id: str
    title: str       # filename
    media_type: str  # mime
    file_id: str | None = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfluenceError(RuntimeError):
    code: str = "UPSTREAM_ERROR"

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ConfluenceAuthError(ConfluenceError):
    code = "AUTH_ERROR"


class ConfluencePermissionError(ConfluenceError):
    code = "PERMISSION_DENIED"


class ConfluenceNotFoundError(ConfluenceError):
    code = "NOT_FOUND"


class ConfluenceConflictError(ConfluenceError):
    code = "VERSION_CONFLICT"


class ConfluenceTooLargeError(ConfluenceError):
    code = "ATTACHMENT_TOO_LARGE"


class ConfluenceUpstreamError(ConfluenceError):
    code = "UPSTREAM_ERROR"


class ConfluenceClientError(ConfluenceError):
    code = "INVALID_PARAMS"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


@dataclass
class ConfluenceClient:
    """Synchronous REST client. One instance per CLI invocation."""

    site: str           # e.g. https://acme.atlassian.net
    email: str
    token: str
    timeout: float = 30.0
    user_agent: str = "confluence-cli/0.1"
    _auth: str = field(init=False, default="", repr=False)

    def __post_init__(self) -> None:
        creds = f"{self.email}:{self.token}".encode()
        self._auth = "Basic " + base64.b64encode(creds).decode("ascii")

    # ---- public URLs (relative; no token) --------------------------------

    def page_url(self, page: Page, space_key: str) -> str:
        """Public viewer URL for a page."""
        # The v2 API exposes `_links.webui` relative to /wiki — use it
        # verbatim if present, otherwise synthesise the canonical form.
        if page.webui:
            return f"{self.site}/wiki{page.webui}"
        return f"{self.site}/wiki/spaces/{space_key}/pages/{page.id}"

    # ---- whoami / preflight ---------------------------------------------

    def ping(self) -> None:
        """One-shot probe to surface auth errors before any write."""
        self._request("GET", "/wiki/api/v2/spaces?limit=1")

    # ---- spaces ----------------------------------------------------------

    def list_spaces(
        self, *, query: str | None = None, limit: int = 50,
    ) -> list[Space]:
        """All visible spaces. Pagination is followed transparently until
        `limit` is reached. `query` filters by name/key substring locally
        (the v2 endpoint has no fulltext space filter)."""
        spaces: list[Space] = []
        cursor: str | None = None
        per_page = min(250, max(10, limit))
        needle = (query or "").lower().strip()
        while len(spaces) < limit:
            qs = {"limit": str(per_page)}
            if cursor:
                qs["cursor"] = cursor
            payload = self._request("GET", f"/wiki/api/v2/spaces?{urlencode(qs)}")
            for entry in payload.get("results", []):
                sp = _space_from_json(entry)
                if needle and needle not in sp.key.lower() and needle not in sp.name.lower():
                    continue
                spaces.append(sp)
                if len(spaces) >= limit:
                    break
            cursor = _cursor_from_links(payload.get("_links", {}))
            if not cursor:
                break
        return spaces

    def get_space_by_key(self, key: str) -> Space:
        """Resolve a space by its key. Errors if not visible to the token."""
        # v2 supports keys[] filter, more efficient than scanning all spaces.
        qs = urlencode({"keys": key, "limit": "1"})
        payload = self._request("GET", f"/wiki/api/v2/spaces?{qs}")
        results = payload.get("results", [])
        if not results:
            raise ConfluenceNotFoundError(
                f"Space with key {key!r} not found or not visible to this user."
            )
        return _space_from_json(results[0])

    # ---- pages -----------------------------------------------------------

    def list_pages(
        self,
        *,
        space_id: str,
        query: str | None = None,
        parent_id: str | None = None,
        limit: int = 50,
    ) -> list[Page]:
        """List pages in a space. `query` does a title substring filter
        client-side (v2 has no `q=` on this endpoint). `parent_id` restricts
        to direct children."""
        pages: list[Page] = []
        cursor: str | None = None
        per_page = min(250, max(10, limit))
        needle = (query or "").lower().strip()
        while len(pages) < limit:
            qs = {"limit": str(per_page)}
            if cursor:
                qs["cursor"] = cursor
            payload = self._request(
                "GET", f"/wiki/api/v2/spaces/{space_id}/pages?{urlencode(qs)}"
            )
            for entry in payload.get("results", []):
                pg = _page_from_json(entry, default_space_id=space_id)
                if parent_id and pg.parent_id != parent_id:
                    continue
                if needle and needle not in pg.title.lower():
                    continue
                pages.append(pg)
                if len(pages) >= limit:
                    break
            cursor = _cursor_from_links(payload.get("_links", {}))
            if not cursor:
                break
        return pages

    def get_page(self, page_id: str) -> Page:
        payload = self._request("GET", f"/wiki/api/v2/pages/{page_id}")
        return _page_from_json(payload)

    def find_page_by_title(
        self,
        *,
        space_id: str,
        title: str,
        parent_id: str | None,
    ) -> Page | None:
        """Locate a page by (space, parent, title). Title match is exact.

        Walks the space's pages with title-prefix filtering on the server
        side via the `title` query param (supported by v2 in cursor mode)
        and short-circuits on the first exact title hit under the right
        parent.

        When ``parent_id`` is ``None`` the matcher accepts a page under
        any parent. Confluence enforces unique titles per space, so this
        is safe and makes idempotency work for pages published to the
        space root (where Confluence auto-assigns the space's homepage
        as the actual ``parentId``).
        """
        cursor: str | None = None
        # v2 supports a `title` query param on /spaces/{id}/pages but it's
        # an exact match — perfect for our case.
        qs_base = {"limit": "100", "title": title}
        while True:
            qs = dict(qs_base)
            if cursor:
                qs["cursor"] = cursor
            payload = self._request(
                "GET", f"/wiki/api/v2/spaces/{space_id}/pages?{urlencode(qs)}"
            )
            for entry in payload.get("results", []):
                pg = _page_from_json(entry, default_space_id=space_id)
                if pg.title != title:
                    continue
                if parent_id is not None and (pg.parent_id or None) != parent_id:
                    continue
                return pg
            cursor = _cursor_from_links(payload.get("_links", {}))
            if not cursor:
                return None

    def create_page(
        self,
        *,
        space_id: str,
        parent_id: str | None,
        title: str,
        body_storage: str,
    ) -> Page:
        payload: dict[str, Any] = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "body": {
                "representation": "storage",
                "value": body_storage,
            },
        }
        if parent_id:
            payload["parentId"] = parent_id
        resp = self._request("POST", "/wiki/api/v2/pages", json_body=payload)
        return _page_from_json(resp, default_space_id=space_id)

    def update_page(
        self,
        *,
        page_id: str,
        title: str,
        body_storage: str,
        current_version: int,
        parent_id: str | None = None,
        comment: str | None = None,
    ) -> Page:
        version: dict[str, Any] = {
            "number": current_version + 1,
        }
        payload: dict[str, Any] = {
            "id": page_id,
            "status": "current",
            "title": title,
            "body": {
                "representation": "storage",
                "value": body_storage,
            },
            "version": version,
        }
        if comment:
            version["message"] = comment
        if parent_id:
            payload["parentId"] = parent_id
        resp = self._request(
            "PUT", f"/wiki/api/v2/pages/{page_id}", json_body=payload
        )
        return _page_from_json(resp)

    # ---- attachments (v1 — v2 is read-only for writes) -------------------

    def list_attachments(self, page_id: str) -> list[Attachment]:
        atts: list[Attachment] = []
        cursor: str | None = None
        while True:
            qs = {"limit": "250"}
            if cursor:
                qs["cursor"] = cursor
            payload = self._request(
                "GET", f"/wiki/api/v2/pages/{page_id}/attachments?{urlencode(qs)}"
            )
            for entry in payload.get("results", []):
                atts.append(
                    Attachment(
                        id=str(entry.get("id", "")),
                        title=str(entry.get("title", "")),
                        media_type=str(entry.get("mediaType", "")),
                        file_id=str(entry.get("fileId") or "") or None,
                    )
                )
            cursor = _cursor_from_links(payload.get("_links", {}))
            if not cursor:
                break
        return atts

    def upload_attachment(
        self,
        *,
        page_id: str,
        filename: str,
        data: bytes,
        mime: str | None = None,
        comment: str | None = None,
        minor_edit: bool = True,
    ) -> Attachment:
        """PUT a file as a page attachment. Idempotent: if the page already
        has an attachment with the same filename, Confluence versions it
        instead of duplicating.

        Uses the v1 endpoint because v2 doesn't yet support attachment
        writes.
        """
        if mime is None:
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        boundary = uuid.uuid4().hex
        body = _build_multipart(
            boundary=boundary,
            filename=filename,
            data=data,
            mime=mime,
            comment=comment,
            minor_edit=minor_edit,
        )
        # The PUT endpoint matches by filename — create-or-update.
        path = f"/wiki/rest/api/content/{page_id}/child/attachment"
        resp = self._request(
            "PUT",
            path,
            raw_body=body,
            content_type=f"multipart/form-data; boundary={boundary}",
            extra_headers={"X-Atlassian-Token": "nocheck"},
        )
        # v1 returns {"results":[{...}]} on PUT, {"...":...} on direct POST.
        result = (resp.get("results") or [resp])[0]
        return Attachment(
            id=str(result.get("id", "")),
            title=str(result.get("title", filename)),
            media_type=str(
                (result.get("metadata") or {}).get("mediaType") or mime
            ),
        )

    # ---- HTTP plumbing ---------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        raw_body: bytes | None = None,
        content_type: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Internal — issue one request, parse JSON. Raises on non-2xx."""
        url = self.site + path
        headers = {
            "Authorization": self._auth,
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if extra_headers:
            headers.update(extra_headers)

        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif raw_body is not None:
            data = raw_body
            if content_type:
                headers["Content-Type"] = content_type

        req = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except HTTPError as exc:
            raise _classify_http_error(exc) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise ConfluenceUpstreamError(
                f"Network error talking to Confluence: {exc}",
            ) from exc

        if not raw:
            return {}
        try:
            return cast("dict[str, Any]", json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfluenceUpstreamError(
                f"Confluence returned non-JSON body: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _space_from_json(entry: dict[str, Any]) -> Space:
    links = entry.get("_links") or {}
    return Space(
        id=str(entry.get("id", "")),
        key=str(entry.get("key", "")),
        name=str(entry.get("name", "")),
        type=str(entry.get("type", "")),
        homepage_id=str(entry.get("homepageId") or "") or None,
        webui=str(links.get("webui") or ""),
    )


def _page_from_json(entry: dict[str, Any], *, default_space_id: str = "") -> Page:
    links = entry.get("_links") or {}
    version = entry.get("version") or {}
    parent_id = entry.get("parentId")
    return Page(
        id=str(entry.get("id", "")),
        title=str(entry.get("title", "")),
        space_id=str(entry.get("spaceId") or default_space_id or ""),
        parent_id=str(parent_id) if parent_id else None,
        version=int(version.get("number") or 1),
        webui=str(links.get("webui") or ""),
    )


def _cursor_from_links(links: dict[str, Any]) -> str | None:
    """Pull the cursor value out of the `next` URL."""
    nxt = links.get("next")
    if not nxt or not isinstance(nxt, str):
        return None
    # `next` is a relative URL with ?cursor=…&limit=…
    from urllib.parse import parse_qs, urlparse

    qs = parse_qs(urlparse(nxt).query)
    cursors = qs.get("cursor")
    if not cursors:
        return None
    return cursors[0]


def _classify_http_error(exc: HTTPError) -> ConfluenceError:
    status = exc.code
    body = ""
    try:
        body_bytes = exc.read()
        body = body_bytes.decode("utf-8", errors="replace")[:600]
    except Exception:
        pass
    # Extract the Atlassian error message when present.
    msg_summary = _extract_error_message(body) or f"HTTP {status}"

    if status == 401:
        return ConfluenceAuthError(
            f"Authentication rejected by Confluence: {msg_summary}",
            status=status,
        )
    if status == 403:
        return ConfluencePermissionError(
            f"Permission denied by Confluence: {msg_summary}",
            status=status,
        )
    if status == 404:
        return ConfluenceNotFoundError(
            f"Resource not found: {msg_summary}", status=status
        )
    if status == 409:
        return ConfluenceConflictError(
            f"Version conflict: {msg_summary}", status=status
        )
    if status == 413:
        return ConfluenceTooLargeError(
            f"Attachment too large: {msg_summary}", status=status
        )
    if 500 <= status < 600:
        return ConfluenceUpstreamError(
            f"Confluence server error (HTTP {status}): {msg_summary}",
            status=status,
        )
    return ConfluenceClientError(
        f"Confluence rejected request (HTTP {status}): {msg_summary}",
        status=status,
    )


def _extract_error_message(body: str) -> str:
    """Pull the first `message` field out of an Atlassian error body."""
    if not body:
        return ""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body[:300]
    # Single error object: {"errors":[{"title":"…"}]} or {"message":"…"}
    if isinstance(payload, dict):
        if "message" in payload and isinstance(payload["message"], str):
            return payload["message"]
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                for key in ("title", "detail", "message"):
                    val = first.get(key)
                    if isinstance(val, str) and val:
                        return val
    return body[:300]


def _build_multipart(
    *,
    boundary: str,
    filename: str,
    data: bytes,
    mime: str,
    comment: str | None,
    minor_edit: bool,
) -> bytes:
    """Build a multipart/form-data body containing one `file` part and
    optional `comment` / `minorEdit` parts. Hand-rolled to avoid bringing
    in `requests`."""
    buf = io.BytesIO()
    crlf = b"\r\n"

    def write_field(name: str, value: str) -> None:
        buf.write(f"--{boundary}".encode("ascii") + crlf)
        buf.write(
            f'Content-Disposition: form-data; name="{name}"'.encode("ascii") + crlf
        )
        buf.write(b"Content-Type: text/plain; charset=utf-8" + crlf + crlf)
        buf.write(value.encode("utf-8") + crlf)

    # File part — quote() the filename for safety (Confluence preserves it
    # verbatim, including spaces, but quoting avoids header-injection edge
    # cases).
    safe_name = quote(filename, safe=" .-_+")
    buf.write(f"--{boundary}".encode("ascii") + crlf)
    buf.write(
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"'
        .encode() + crlf
    )
    buf.write(f"Content-Type: {mime}".encode("ascii") + crlf + crlf)
    buf.write(data + crlf)

    if comment:
        write_field("comment", comment)
    write_field("minorEdit", "true" if minor_edit else "false")

    buf.write(f"--{boundary}--".encode("ascii") + crlf)
    return buf.getvalue()
