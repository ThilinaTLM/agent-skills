"""Supported diagram engines, output formats, and source-file extensions.

This module is the single source of truth used by both pre-flight
`(type, format)` validation and the `diagram types` discovery command.

If Kroki adds a new diagram type or format, update the tables below.
Reference: https://kroki.io/#support
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeInfo:
    name: str  # canonical name accepted on the CLI
    slug: str  # path slug used in Kroki URLs
    extensions: tuple[str, ...]  # file extensions (including leading dot) that map to this type
    formats: tuple[str, ...]  # output formats supported by Kroki for this type


# Each entry: name is the CLI-facing identifier; slug is what Kroki expects in
# the URL path. For most engines name == slug.
_TYPES: tuple[TypeInfo, ...] = (
    TypeInfo("blockdiag", "blockdiag", (".blockdiag",), ("svg", "png", "pdf")),
    TypeInfo("seqdiag", "seqdiag", (".seqdiag",), ("svg", "png", "pdf")),
    TypeInfo("actdiag", "actdiag", (".actdiag",), ("svg", "png", "pdf")),
    TypeInfo("nwdiag", "nwdiag", (".nwdiag",), ("svg", "png", "pdf")),
    TypeInfo("packetdiag", "packetdiag", (".packetdiag",), ("svg", "png", "pdf")),
    TypeInfo("rackdiag", "rackdiag", (".rackdiag",), ("svg", "png", "pdf")),
    TypeInfo("bpmn", "bpmn", (".bpmn",), ("svg",)),
    TypeInfo("bytefield", "bytefield", (".bytefield",), ("svg",)),
    TypeInfo(
        "c4plantuml",
        "c4plantuml",
        (".c4", ".c4puml"),
        ("svg", "png", "pdf", "txt", "base64"),
    ),
    TypeInfo("d2", "d2", (".d2",), ("svg",)),
    TypeInfo("dbml", "dbml", (".dbml",), ("svg",)),
    TypeInfo("ditaa", "ditaa", (".ditaa",), ("svg", "png")),
    TypeInfo("erd", "erd", (".erd",), ("svg", "png", "jpeg", "pdf")),
    TypeInfo("excalidraw", "excalidraw", (".excalidraw",), ("svg",)),
    TypeInfo("graphviz", "graphviz", (".dot", ".gv"), ("svg", "png", "jpeg", "pdf")),
    TypeInfo("mermaid", "mermaid", (".mmd", ".mermaid"), ("svg", "png")),
    TypeInfo("nomnoml", "nomnoml", (".nomnoml",), ("svg",)),
    TypeInfo("pikchr", "pikchr", (".pikchr",), ("svg",)),
    TypeInfo(
        "plantuml",
        "plantuml",
        (".puml", ".plantuml", ".iuml"),
        ("svg", "png", "pdf", "txt", "base64"),
    ),
    TypeInfo(
        "structurizr",
        "structurizr",
        (".structurizr", ".dsl"),
        ("svg", "png", "pdf", "txt", "base64"),
    ),
    TypeInfo("svgbob", "svgbob", (".svgbob",), ("svg",)),
    TypeInfo("symbolator", "symbolator", (), ("svg",)),
    TypeInfo("tikz", "tikz", (".tikz",), ("svg", "png", "jpeg", "pdf")),
    TypeInfo("umlet", "umlet", (), ("svg", "png", "jpeg")),
    TypeInfo("vega", "vega", (".vega",), ("svg", "png", "pdf")),
    TypeInfo("vegalite", "vegalite", (".vl", ".vegalite"), ("svg", "png", "pdf")),
    TypeInfo("wavedrom", "wavedrom", (".wavedrom",), ("svg",)),
    TypeInfo("wireviz", "wireviz", (".wireviz",), ("svg", "png")),
)

TYPES: dict[str, TypeInfo] = {t.name: t for t in _TYPES}


# Map extension (lowercase, with leading dot) to canonical type name.
_EXTENSION_INDEX: dict[str, str] = {}
for _t in _TYPES:
    for _ext in _t.extensions:
        _EXTENSION_INDEX[_ext.lower()] = _t.name


def lookup_type(name: str) -> TypeInfo | None:
    """Return the TypeInfo for a CLI-facing type name, case-insensitive."""
    if not name:
        return None
    return TYPES.get(name.strip().lower())


def type_for_extension(ext: str) -> TypeInfo | None:
    """Return the TypeInfo for a file extension (e.g. '.puml')."""
    if not ext:
        return None
    key = ext.lower()
    if not key.startswith("."):
        key = "." + key
    name = _EXTENSION_INDEX.get(key)
    return TYPES[name] if name else None


def supports_format(info: TypeInfo, fmt: str) -> bool:
    return fmt.lower() in info.formats


def all_types() -> list[TypeInfo]:
    """Return all TypeInfo entries in declared order."""
    return list(_TYPES)
