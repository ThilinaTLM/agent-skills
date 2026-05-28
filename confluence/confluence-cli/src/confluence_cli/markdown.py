"""Best-effort Confluence storage XML \u2192 Markdown conversion.

The output is intended for *humans* to skim. It is *not* a faithful
round-trip representation \u2014 macros that aren't explicitly handled
degrade to HTML comments or plain text. Re-uploading from markdown is
unsupported; edit ``body.value`` (storage XML) in ``pages.jsonl``
and call ``confluence page update --body-file \u2026`` instead.

Pipeline:

1. Parse the storage XML (wrap in a synthetic root element so common
   fragments like ``<p>hi</p>`` parse cleanly).
2. Pre-process Confluence-specific elements \u2014 ``ac:structured-macro``
   (info / note / warning / tip / code / expand / panel),
   ``ri:page`` / ``ri:attachment`` link references, ``ac:image``
   wrappers \u2014 rewriting them to plain HTML the next stage understands.
3. Serialise to HTML and run through ``markdownify``.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from markdownify import markdownify as _md

__all__ = [
    "MarkdownError",
    "PageRef",
    "storage_to_markdown",
]


AC_NS = "http://atlassian.com/content"
RI_NS = "http://atlassian.com/resource/identifier"

# ElementTree namespace map. We declare these so .find() / .iter() use
# clark notation, e.g. "{http://atlassian.com/content}structured-macro".
_NS_DECL = (
    f'xmlns:ac="{AC_NS}" '
    f'xmlns:ri="{RI_NS}"'
)


class MarkdownError(RuntimeError):
    """Raised by the markdown pipeline when something we can't recover from
    occurs. Currently used for the missing-``markdownify`` case."""

    def __init__(self, message: str, *, code: str = "INTERNAL_ERROR",
                 hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


@dataclass(frozen=True)
class PageRef:
    """Minimal info the converter needs to resolve a ``ri:page`` link."""

    id: str
    title: str
    url: str


def storage_to_markdown(
    storage_xml: str,
    *,
    page_id: str,
    page_index: Mapping[str, PageRef] | None = None,
    attachments_downloaded: bool = False,
    attachments_base: str = "attachments",
    site_url: str | None = None,
) -> str:
    """Convert Confluence storage XML to a markdown string.

    Parameters
    ----------
    storage_xml:
        The raw ``body.storage.value`` from the Confluence API.
    page_id:
        The numeric id of the page being converted. Used to build
        relative paths to downloaded attachments.
    page_index:
        Mapping of page title \u2192 :class:`PageRef` for cross-page link
        resolution. Optional \u2014 unresolved links fall back to plain
        text.
    attachments_downloaded:
        When ``True`` the converter emits relative ``attachments/{pid}/``
        paths for inline images. When ``False`` it falls back to the
        Confluence public URL (if ``site_url`` is supplied) or the bare
        filename.
    attachments_base:
        Root directory (relative to the markdown file) under which
        attachments live. Should match what the download command wrote.
    site_url:
        Optional ``https://acme.atlassian.net`` for falling back to
        public attachment URLs when local files aren't available.
    """
    html = _to_intermediate_html(
        storage_xml,
        page_id=page_id,
        page_index=page_index or {},
        attachments_downloaded=attachments_downloaded,
        attachments_base=attachments_base,
        site_url=site_url,
    )

    def _code_language(el: Any) -> str:
        # markdownify passes the BeautifulSoup <code> element. Pull a
        # "language-xxx" class set by our pre-processor and return
        # just the language token; markdownify uses it as the fence
        # info string.
        classes = el.get("class") if hasattr(el, "get") else None
        if not classes:
            return ""
        for cls in classes:
            if isinstance(cls, str) and cls.startswith("language-"):
                return cls[len("language-"):]
        return ""

    md = _md(
        html,
        heading_style="ATX",
        bullets="-",
        code_language_callback=_code_language,
    )
    # Collapse runs of blank lines that markdownify sometimes emits.
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


# ---------------------------------------------------------------------------
# Intermediate HTML generation
# ---------------------------------------------------------------------------


def _to_intermediate_html(
    storage_xml: str,
    *,
    page_id: str,
    page_index: Mapping[str, PageRef],
    attachments_downloaded: bool,
    attachments_base: str,
    site_url: str | None,
) -> str:
    if not storage_xml.strip():
        return ""

    # Confluence storage XML uses HTML named entities (&mdash;, &harr;,
    # &nbsp;, …) that XML parsers don't recognise. Pre-expand them to
    # their literal characters so xml.etree can parse the body. We do
    # this *after* extracting the document because doing it before would
    # require knowing which `&amp;`s are entity escapes for `&` vs the
    # opening of a real named entity.
    normalised = _expand_html_entities(storage_xml)

    # Wrap so multiple top-level siblings parse, and inject namespace
    # declarations so ac:* / ri:* parse without ParseError.
    wrapped = (
        f'<root {_NS_DECL}>{normalised}</root>'
    )
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError:
        # Last-ditch: strip ac:/ri: tags by regex and pass the rest
        # through. Markdown quality drops sharply for the affected page
        # but at least we get some output.
        return _regex_fallback(normalised)

    ctx = _Ctx(
        page_id=page_id,
        page_index=page_index,
        attachments_downloaded=attachments_downloaded,
        attachments_base=attachments_base,
        site_url=site_url,
    )
    _transform(root, ctx)

    # Serialise children of the synthetic root (avoid the <root>
    # wrapper showing up in the output).
    parts: list[str] = []
    if root.text:
        parts.append(_escape_text(root.text))
    for child in list(root):
        parts.append(ET.tostring(child, encoding="unicode", method="html"))
    return "".join(parts)


@dataclass
class _Ctx:
    page_id: str
    page_index: Mapping[str, PageRef]
    attachments_downloaded: bool
    attachments_base: str
    site_url: str | None


def _transform(element: ET.Element, ctx: _Ctx) -> None:
    """Recursively rewrite the tree in-place.

    Handlers for ``ac:structured-macro``, ``ac:link``, ``ac:image``,
    ``ac:emoticon`` and ``ac:task`` take full responsibility for their
    own subtree -- they are called pre-order and we do NOT descend into
    them after. They look at structural children (``ac:rich-text-body``
    etc.) by tag, which would be destroyed by the post-order
    unwrap-unknown step below.

    Everything else descends normally; unknown ``ac:*`` / ``ri:*``
    elements get unwrapped to a plain ``<span>`` after their children
    have been processed.
    """
    tag = element.tag

    # Self-contained handlers (no descent below).
    if tag == f"{{{AC_NS}}}structured-macro":
        _handle_macro(element, ctx)
        return
    if tag == f"{{{AC_NS}}}adf-extension":
        _handle_adf_extension(element, ctx)
        return
    if tag == f"{{{AC_NS}}}link":
        _handle_ac_link(element, ctx)
        return
    if tag == f"{{{AC_NS}}}image":
        _handle_ac_image(element, ctx)
        return
    if tag == f"{{{AC_NS}}}emoticon":
        _replace_with_text(element, _emoticon_to_text(element))
        return
    if tag == f"{{{AC_NS}}}task":
        _handle_task(element)
        return

    # Pre-order tweak; descent still happens below.
    if tag == f"{{{AC_NS}}}task-list":
        _rename(element, "ul")

    for child in list(element):
        _transform(child, ctx)

    # Post-order: unknown ac:/ri: container becomes a transparent span.
    if tag.startswith(f"{{{AC_NS}}}") or tag.startswith(f"{{{RI_NS}}}"):
        _unwrap(element)


def _transform_children(element: ET.Element, ctx: _Ctx) -> None:
    """Recursively transform every child of ``element`` in place."""
    for child in list(element):
        _transform(child, ctx)


# ---- macros ---------------------------------------------------------------


def _handle_macro(element: ET.Element, ctx: _Ctx) -> None:
    name = (element.get(f"{{{AC_NS}}}name") or "").lower()
    handler = _MACRO_HANDLERS.get(name)
    if handler is None:
        handler = _macro_unsupported
    handler(element, ctx, name)


def _macro_callout(element: ET.Element, ctx: _Ctx, name: str) -> None:
    """info / note / warning / tip / panel \u2192 <blockquote class=callout-X>."""
    body = _find_child(element, f"{{{AC_NS}}}rich-text-body")
    new = ET.Element("blockquote", {"class": f"callout-{name}"})
    label = ET.SubElement(new, "p")
    label_strong = ET.SubElement(label, "strong")
    label_strong.text = name.capitalize()
    if body is not None:
        _transform_children(body, ctx)
        if body.text and body.text.strip():
            p = ET.SubElement(new, "p")
            p.text = body.text
        for sub in list(body):
            new.append(sub)
    _replace_element(element, new)


def _macro_code(element: ET.Element, ctx: _Ctx, name: str) -> None:
    language = _macro_param(element, "language") or ""
    body = _find_child(element, f"{{{AC_NS}}}plain-text-body")
    code_text = (body.text if body is not None else element.text) or ""
    pre = ET.Element("pre")
    # markdownify reads the code_language_callback against the <pre>,
    # so set the class there (we also keep it on <code> for general
    # HTML readers).
    if language:
        pre.set("class", f"language-{language}")
    code = ET.SubElement(pre, "code")
    if language:
        code.set("class", f"language-{language}")
    code.text = code_text
    _replace_element(element, pre)


def _macro_expand(element: ET.Element, ctx: _Ctx, name: str) -> None:
    # We emit a real <details>/<summary> pair (renders natively in
    # GitHub-flavoured markdown viewers). For plain text consumers we
    # also leave a bold title line inside so the section is still
    # visually labelled.
    title = _macro_param(element, "title") or "Details"
    body = _find_child(element, f"{{{AC_NS}}}rich-text-body")
    details = ET.Element("details")
    summary = ET.SubElement(details, "summary")
    summary_strong = ET.SubElement(summary, "strong")
    summary_strong.text = title
    if body is not None:
        _transform_children(body, ctx)
        if body.text and body.text.strip():
            p = ET.SubElement(details, "p")
            p.text = body.text
        for sub in list(body):
            details.append(sub)
    _replace_element(element, details)


def _macro_status(element: ET.Element, ctx: _Ctx, name: str) -> None:
    title = _macro_param(element, "title") or ""
    colour = _macro_param(element, "colour") or _macro_param(element, "color") or ""
    span = ET.Element("span", {"class": f"status status-{colour.lower()}"})
    span.text = f"[{title}]" if title else "[status]"
    _replace_element(element, span)


def _macro_toc(element: ET.Element, ctx: _Ctx, name: str) -> None:
    placeholder = ET.Element("p")
    placeholder.text = "_Table of contents (auto-generated by Confluence)_"
    _replace_element(element, placeholder)


def _macro_unsupported(element: ET.Element, ctx: _Ctx, name: str) -> None:
    # Try to preserve any rich-text-body content rather than dropping it.
    body = _find_child(element, f"{{{AC_NS}}}rich-text-body")
    container = ET.Element("div", {"class": f"unsupported-macro macro-{name or 'unknown'}"})
    container.append(ET.Comment(f"unsupported confluence macro: {name or 'unknown'}"))
    if body is not None:
        _transform_children(body, ctx)
        if body.text and body.text.strip():
            p = ET.SubElement(container, "p")
            p.text = body.text
        for sub in list(body):
            container.append(sub)
    _replace_element(element, container)


_MACRO_HANDLERS: dict[str, Callable[[ET.Element, _Ctx, str], None]] = {
    "info": _macro_callout,
    "note": _macro_callout,
    "warning": _macro_callout,
    "tip": _macro_callout,
    "success": _macro_callout,
    "error": _macro_callout,
    "panel": _macro_callout,
    "code": _macro_code,
    "expand": _macro_expand,
    "status": _macro_status,
    "toc": _macro_toc,
}


# ---- ADF extension nodes --------------------------------------------------
#
# Modern Confluence pages wrap panels, expands, etc. in
# ``ac:adf-extension`` containers carrying ADF (Atlassian Document
# Format) JSON-like trees serialised as XML:
#
#     <ac:adf-extension>
#       <ac:adf-node type="panel">
#         <ac:adf-attribute key="panel-type">note</ac:adf-attribute>
#         <ac:adf-content>…page content…</ac:adf-content>
#       </ac:adf-node>
#     </ac:adf-extension>
#
# We map the common node types to the same intermediate HTML shapes
# the structured-macro handlers produce.


def _handle_adf_extension(element: ET.Element, ctx: _Ctx) -> None:
    node = _find_child(element, f"{{{AC_NS}}}adf-node")
    if node is None:
        _unwrap(element)
        return
    node_type = (node.get("type") or "").lower()
    handler = _ADF_HANDLERS.get(node_type, _adf_unsupported)
    handler(element, node, ctx, node_type)


def _adf_attr(node: ET.Element, key: str) -> str | None:
    for child in node.findall(f"{{{AC_NS}}}adf-attribute"):
        if child.get("key") == key:
            return child.text or ""
    return None


def _adf_content(node: ET.Element) -> ET.Element | None:
    return _find_child(node, f"{{{AC_NS}}}adf-content")


def _adf_panel(
    element: ET.Element, node: ET.Element, ctx: _Ctx, node_type: str,
) -> None:
    panel_type = (_adf_attr(node, "panel-type") or "note").lower()
    content = _adf_content(node)
    new = ET.Element("blockquote", {"class": f"callout-{panel_type}"})
    label = ET.SubElement(new, "p")
    ET.SubElement(label, "strong").text = panel_type.capitalize()
    if content is not None:
        _transform_children(content, ctx)
        if content.text and content.text.strip():
            p = ET.SubElement(new, "p")
            p.text = content.text
        for sub in list(content):
            new.append(sub)
    _replace_element(element, new)


def _adf_expand(
    element: ET.Element, node: ET.Element, ctx: _Ctx, node_type: str,
) -> None:
    title = _adf_attr(node, "title") or "Details"
    content = _adf_content(node)
    details = ET.Element("details")
    summary = ET.SubElement(details, "summary")
    ET.SubElement(summary, "strong").text = title
    if content is not None:
        _transform_children(content, ctx)
        if content.text and content.text.strip():
            p = ET.SubElement(details, "p")
            p.text = content.text
        for sub in list(content):
            details.append(sub)
    _replace_element(element, details)


def _adf_unsupported(
    element: ET.Element, node: ET.Element, ctx: _Ctx, node_type: str,
) -> None:
    content = _adf_content(node)
    container = ET.Element(
        "div", {"class": f"unsupported-adf adf-{node_type or 'unknown'}"},
    )
    container.append(
        ET.Comment(f"unsupported confluence ADF node: {node_type or 'unknown'}"),
    )
    if content is not None:
        _transform_children(content, ctx)
        if content.text and content.text.strip():
            p = ET.SubElement(container, "p")
            p.text = content.text
        for sub in list(content):
            container.append(sub)
    _replace_element(element, container)


_ADF_HANDLERS: dict[
    str, Callable[[ET.Element, ET.Element, _Ctx, str], None]
] = {
    "panel": _adf_panel,
    "expand": _adf_expand,
    "nestedExpand": _adf_expand,
}


# ---- links and images -----------------------------------------------------


def _handle_ac_link(element: ET.Element, ctx: _Ctx) -> None:
    href: str | None = None
    text: str | None = None

    page = _find_child(element, f"{{{RI_NS}}}page")
    attachment = _find_child(element, f"{{{RI_NS}}}attachment")
    url = _find_child(element, f"{{{RI_NS}}}url")
    body = _find_child(element, f"{{{AC_NS}}}plain-text-link-body")
    rich_body = _find_child(element, f"{{{AC_NS}}}link-body")

    if body is not None and body.text:
        text = body.text
    elif rich_body is not None and (rich_body.text or list(rich_body)):
        text = "".join(rich_body.itertext()).strip()

    if page is not None:
        title = page.get(f"{{{RI_NS}}}content-title") or ""
        ref = ctx.page_index.get(title)
        if ref:
            href = ref.url
            text = text or ref.title
        else:
            href = None
            text = text or title
    elif attachment is not None:
        filename = attachment.get(f"{{{RI_NS}}}filename") or ""
        href = _attachment_href(filename, ctx)
        text = text or filename
    elif url is not None:
        href = url.get(f"{{{RI_NS}}}value") or ""
        text = text or href

    if href:
        link = ET.Element("a", {"href": href})
        link.text = text or href
        _replace_element(element, link)
    else:
        # No usable target \u2014 just keep the text.
        span = ET.Element("span")
        span.text = text or ""
        _replace_element(element, span)


def _handle_ac_image(element: ET.Element, ctx: _Ctx) -> None:
    attachment = _find_child(element, f"{{{RI_NS}}}attachment")
    url = _find_child(element, f"{{{RI_NS}}}url")
    alt = element.get(f"{{{AC_NS}}}alt") or ""

    src: str | None = None
    if attachment is not None:
        filename = attachment.get(f"{{{RI_NS}}}filename") or ""
        src = _attachment_href(filename, ctx)
    elif url is not None:
        src = url.get(f"{{{RI_NS}}}value") or None

    if src:
        img = ET.Element("img", {"src": src, "alt": alt})
        _replace_element(element, img)
    else:
        _replace_with_text(element, f"[image: {alt or 'unknown'}]")


def _attachment_href(filename: str, ctx: _Ctx) -> str:
    if not filename:
        return ""
    if ctx.attachments_downloaded:
        return f"{ctx.attachments_base}/{ctx.page_id}/{filename}"
    if ctx.site_url:
        return f"{ctx.site_url}/wiki/download/attachments/{ctx.page_id}/{filename}"
    return filename


def _handle_task(element: ET.Element) -> None:
    status_el = _find_child(element, f"{{{AC_NS}}}task-status")
    body = _find_child(element, f"{{{AC_NS}}}task-body")
    checked = bool(status_el is not None and (status_el.text or "").strip().lower() == "complete")
    marker = "[x] " if checked else "[ ] "
    li = ET.Element("li")
    li.text = marker + ("".join(body.itertext()).strip() if body is not None else "")
    _replace_element(element, li)


def _emoticon_to_text(element: ET.Element) -> str:
    name = element.get(f"{{{AC_NS}}}name") or ""
    mapping = {
        "tick": "\u2705",
        "cross": "\u274C",
        "warning": "\u26A0\uFE0F",
        "information": "\u2139\uFE0F",
        "question": "\u2753",
        "thumbs-up": "\U0001F44D",
        "thumbs-down": "\U0001F44E",
        "smile": "\U0001F642",
    }
    return mapping.get(name, f":{name}:" if name else "")


# ---- ElementTree helpers --------------------------------------------------


def _find_child(element: ET.Element, tag: str) -> ET.Element | None:
    for child in element:
        if child.tag == tag:
            return child
    return None


def _macro_param(element: ET.Element, name: str) -> str | None:
    for child in element.findall(f"{{{AC_NS}}}parameter"):
        if child.get(f"{{{AC_NS}}}name") == name:
            return child.text or ""
    return None


def _replace_element(old: ET.Element, new: ET.Element) -> None:
    """In-place replace ``old`` with ``new`` within its parent.

    ElementTree doesn't track parents \u2014 we mutate ``old`` to become a
    copy of ``new`` instead. The post-order traversal already returned
    so this is safe.
    """
    old.tag = new.tag
    old.attrib.clear()
    old.attrib.update(new.attrib)
    old.text = new.text
    old.tail = old.tail  # keep tail
    for child in list(old):
        old.remove(child)
    for child in list(new):
        old.append(child)


def _replace_with_text(element: ET.Element, text: str) -> None:
    element.tag = "span"
    element.attrib.clear()
    for child in list(element):
        element.remove(child)
    element.text = text


def _rename(element: ET.Element, new_tag: str) -> None:
    element.tag = new_tag
    # Strip any ac:* attributes that won't render in HTML.
    for key in list(element.attrib):
        if key.startswith("{"):
            del element.attrib[key]


def _unwrap(element: ET.Element) -> None:
    """Drop the element's tag, keep its text + children inline.

    Without parent pointers we can't truly unwrap; the next best thing
    is to demote the tag to a transparent ``<span>`` so markdownify
    treats it as inline. Attributes are stripped.
    """
    element.tag = "span"
    element.attrib.clear()


def _escape_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _regex_fallback(storage_xml: str) -> str:
    """Last-ditch conversion when the XML parser refuses.

    Strips ``ac:*`` / ``ri:*`` start/end tags by regex and leaves the
    rest. The output is then fed to ``markdownify``.
    """
    no_ac = re.sub(r"</?(?:ac|ri):[^>]+>", "", storage_xml)
    return no_ac


_NAMED_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]+);")
# Entities that XML already understands — don't touch them, or the
# subsequent parse would see e.g. literal `&` and complain.
_XML_BUILTIN_ENTITIES = frozenset({"amp", "lt", "gt", "quot", "apos"})


def _expand_html_entities(s: str) -> str:
    """Replace HTML named entities (``&mdash;`` …) with their literal
    characters so an XML parser can read the body.

    Preserves the five XML built-in entities verbatim. Numeric entities
    (``&#8212;`` / ``&#x2014;``) are already valid XML — left alone.
    Unknown names are passed through unchanged so we don't accidentally
    eat content that happened to look entity-shaped.
    """
    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in _XML_BUILTIN_ENTITIES:
            return match.group(0)
        # html.unescape returns the input unchanged for unknown names.
        decoded = html.unescape(match.group(0))
        if decoded == match.group(0):
            return match.group(0)
        return decoded

    return _NAMED_ENTITY_RE.sub(_sub, s)
