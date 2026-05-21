"""Server-side diagram rendering via Kroki.

Kroki (https://kroki.io) accepts a POST of diagram source and returns a
rendered image. We use PNG (not SVG) so the output renders identically in
Word, LibreOffice, and Confluence after Word-import — SVG support across
Word versions and Confluence's importer is unreliable.

The function is best-effort: any failure (network, server error, encoding)
returns None and the caller falls back to a code block.

Supported diagram kinds map onto Kroki's URL slugs. Any name accepted by
Kroki works (mermaid, plantuml, graphviz, d2, dbml, bpmn, c4plantuml, erd,
…). The full list is the `lang` enum on `<rd-diagram>` in the schema and
the `--type` enum on `diagram-cli`.

Trust model: the diagram source is POSTed to the configured endpoint. The
default is the public kroki.io instance. For confidential content, pass a
self-hosted endpoint (e.g. an internal Kroki deployment).
"""

from __future__ import annotations

from urllib.error import URLError
from urllib.request import Request, urlopen

# Free-form lang name; the schema's `rd-diagram` lang enum is the
# authoritative whitelist. The render helper just forwards the string
# to Kroki, so any new Kroki-supported type works without code change.
DiagramKind = str


def render_to_png(
    source: str,
    *,
    kind: DiagramKind,
    endpoint: str = "https://kroki.io",
    timeout: float = 15.0,
) -> bytes | None:
    """POST `source` to `<endpoint>/<kind>/png`. Returns PNG bytes or None.

    Strips a trailing slash on `endpoint`. Any exception (network, HTTP
    error, empty body) is swallowed and surfaces as None."""
    text = (source or "").strip()
    if not text:
        return None
    url = f"{endpoint.rstrip('/')}/{kind}/png"
    payload = text.encode("utf-8")
    req = Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Accept": "image/png",
            "User-Agent": "richdoc-export/1.0",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — explicit user-supplied URL
            data = resp.read()
    except (URLError, TimeoutError, OSError, ValueError):
        return None
    if not data:
        return None
    # Sanity check: PNG files start with the magic header.
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    return data
