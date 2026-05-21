"""HTTP client for the Kroki render endpoint.

We use the raw POST form: `POST <endpoint>/<type-slug>/<format>` with
`Content-Type: text/plain; charset=utf-8` and the diagram source as the body.
On 2xx the response body is the rendered diagram bytes.
"""

from __future__ import annotations

import httpx

# Cap the server error body included in JSON `hint` so we never spew megabytes.
_MAX_HINT_BODY = 800


class RenderFailed(Exception):
    """Kroki responded 4xx — usually a syntax error in the diagram source."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class KrokiUnavailable(Exception):
    """Network failure, timeout, or Kroki 5xx."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _trim(body: str) -> str:
    body = body.strip()
    if len(body) <= _MAX_HINT_BODY:
        return body
    return body[:_MAX_HINT_BODY] + " …(truncated)"


def render(
    endpoint: str,
    type_slug: str,
    fmt: str,
    source: str,
    *,
    timeout: float,
) -> bytes:
    """POST the source to Kroki and return the rendered bytes."""
    url = f"{endpoint}/{type_slug}/{fmt}"
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Accept": "*/*",
        "User-Agent": "diagram-cli/0.1 (+https://github.com/ThilinaTLM/agent-skills)",
    }
    try:
        response = httpx.post(
            url,
            content=source.encode("utf-8"),
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.TimeoutException as exc:
        raise KrokiUnavailable(f"Request timed out after {timeout:.0f}s: {exc}") from exc
    except httpx.HTTPError as exc:
        raise KrokiUnavailable(f"Network error contacting Kroki: {exc}") from exc

    status = response.status_code
    if 200 <= status < 300:
        return response.content

    # Body decoding can fail on binary responses; fall back to repr.
    try:
        body_text = response.text
    except Exception:  # pragma: no cover — defensive
        body_text = repr(response.content[:200])

    if 400 <= status < 500:
        raise RenderFailed(status, _trim(body_text) or f"HTTP {status} from Kroki")
    # 5xx (and any other non-2xx)
    raise KrokiUnavailable(
        f"HTTP {status} from Kroki: {_trim(body_text) or 'no body'}"
    )
